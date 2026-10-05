"""A dated control is a recorded plan, never an inferred medical prescription."""
import copy
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import support
from scholion import core, format_prescription, store
from scholion.engine import treatment


class TestTreatmentTimeline(unittest.TestCase):
    def setUp(self):
        self.plan = {"marker": "tsh", "from": "2026-03-01", "due": "2026-03-15",
                     "source": "Synthetic recorded plan"}
        self.med = {"name": "Synthetic prescription", "start_date": "2026-01-15",
                    "status": "active", "monitoring_schedule": [self.plan]}

    def timeline(self, points=(), meds=None, day=date(2026, 4, 1)):
        with patch.object(core, "medications_json", return_value={"medications": meds or [self.med]}), \
                patch.object(core, "labs", return_value={"markers": {"tsh": {
                    "name": "TSH", "series": list(points)}}}):
            return treatment.treatment_timeline(day)

    def test_every_prescription_shows_where_it_is_in_time(self):
        second = {"name": "Undated", "status": "stopped"}
        result = self.timeline([{"date": "2026-01-12", "value": 2.5}], [self.med, second])
        self.assertEqual([e["kind"] for e in result["events"]], ["measurement", "prescription_start"])
        self.assertEqual(result["events"][1]["date"], "2026-01-15")
        self.assertEqual(result["undated"][0]["name"], "Undated")
        self.assertFalse(result["undated"][0]["current"])
        self.assertFalse(result["response_assessed"])

    def test_an_overdue_control_reaches_the_first_screen(self):
        self.assertEqual(self.timeline()["overdue"][0]["due"], "2026-03-15")
        from scholion.engine import profile_view
        from scholion import format_views
        with patch.object(profile_view, "treatment_timeline", return_value=self.timeline()):
            result = profile_view.overview()
            self.assertEqual(result["overdue_controls"], self.timeline()["overdue"])
            self.assertIn("Synthetic recorded plan", format_views.overview_report(result))

    def test_only_a_draw_in_the_recorded_window_resolves_a_control(self):
        for stamp, source, value, expected in (
            ("2026-03-03", "form", 2.5, "recorded"),
            ("2026-03-03T09:00", "form", 2.5, "recorded"),
            ("2026-02-28", "form", 2.5, "overdue"),
            ("2026-04-02", "form", 2.5, "overdue"),
            ("2026-03", "form", 2.5, "overdue"),
            ("2026-03-03", "ordered", 2.5, "overdue"),
            ("2026-03-03", None, 2.5, "overdue"),
            ("2026-03-03", "form", None, "overdue"),
        ):
            with self.subTest(stamp=stamp, source=source, value=value):
                got = self.timeline([{"date": stamp, "date_source": source, "value": value}])
                self.assertEqual(got["controls"][0]["status"], expected)

    def test_inactive_and_not_yet_due_are_not_overdue(self):
        self.med["status"] = "paused"
        self.assertEqual(self.timeline()["controls"][0]["status"], "inactive")
        self.med["status"] = "active"
        self.assertEqual(self.timeline(day=date(2026, 3, 15))["controls"][0]["status"], "scheduled")

    def test_invalid_or_unknown_plan_never_claims_a_missed_control(self):
        for field, value in (("marker", "not_a_marker"), ("from", "2026-04-01"),
                             ("due", "2026-03"), ("due", "2026-02-30"), ("source", "")):
            med = copy.deepcopy(self.med)
            med["monitoring_schedule"][0][field] = value
            result = self.timeline(meds=[med])
            self.assertEqual(result["controls"][0]["status"], "unresolved")
            self.assertEqual(result["overdue"], [])
        for schedule in ("check later", [None]):
            med = {**self.med, "monitoring_schedule": schedule}
            self.assertEqual(self.timeline(meds=[med])["controls"][0]["status"], "unresolved")

    def test_legacy_text_stays_unresolved_and_is_not_parsed_as_a_deadline(self):
        med = {"name": "Synthetic", "monitoring": ["TSH in 6–8 weeks"]}
        result = self.timeline(meds=[med])
        self.assertEqual(result["controls"][0]["reason"], "unstructured_plan")
        self.assertEqual(result["overdue"], [])

    def test_rendered_regimen_keeps_start_missing_dates_and_plan_source(self):
        data = self.timeline(meds=[self.med, {"name": "Undated"}])
        with patch.object(format_prescription, "_pgx_mark", return_value=""):
            text = format_prescription.medications_report({"medications": [self.med], "treatment": data})
        for fragment in ("2026-01-15", "Undated", "Synthetic recorded plan", "2026-03-15"):
            self.assertIn(fragment, text)

    def test_dates_never_fill_in_a_day_for_a_month(self):
        self.med["start_date"] = "2026-01"
        self.assertEqual(self.timeline()["events"][0]["date"], "2026-01")
        self.med["start_date"] = "2026-13"
        self.assertEqual(self.timeline()["undated"][0]["reason"], "invalid_start")


class TestRecordedPlanWrite(unittest.TestCase):
    def test_cli_can_record_the_same_dated_plan_as_the_web(self):
        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp)
            args = ["add-med", "Synthetic", "--start-date", "2026-01-01", "--control-marker", "tsh",
                    "--control-from", "2026-03-01", "--control-due", "2026-03-15",
                    "--control-source", "Synthetic plan"]
            self.assertTrue(support.run_json(args, profile_dir=prof)["ok"])
            # A different control remains when this one is added again.
            args[args.index("tsh")] = "ferritin"
            self.assertTrue(support.run_json(args, profile_dir=prof)["ok"])
            args[args.index("ferritin")] = "tsh"
            self.assertTrue(support.run_json(args, profile_dir=prof)["ok"])
            med = support.run_json(["medications"], profile_dir=prof)["medications"][0]
            self.assertEqual(med["start_date"], "2026-01-01")
            self.assertEqual(len(med["monitoring_schedule"]), 2)
            before = (prof / "medications.json").read_bytes()
            bad = args.copy()
            bad[bad.index("2026-03-15")] = "2026-02-30"
            code, out, _ = support.run(bad + ["--json"], profile_dir=prof)
            self.assertNotEqual(code, 0)
            self.assertFalse(json.loads(out)["ok"])
            self.assertEqual((prof / "medications.json").read_bytes(), before)

    def test_invalid_dates_or_partial_plans_refuse_before_claiming_a_profile(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(support.pin_profile(Path(tmp.name)))
        with patch.object(store, "_subject_gate", side_effect=AssertionError("must not claim")):
            self.assertFalse(store.add_medication("Synthetic", start_date="yesterday")["ok"])
            self.assertFalse(store.add_medication("Synthetic", start_date=True)["ok"])
            self.assertFalse(store.add_medication("Synthetic", control={"marker": "tsh"})["ok"])
            self.assertFalse(store.add_medication("Synthetic", control="invalid")["ok"])
