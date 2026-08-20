"""Two draws in one day are a pair, not a disagreement.

Reported by a user who gave blood before a procedure and again after it. The
engine stored points at month granularity, so the two collapsed into one; the
second was recorded as a discrepancy with the first, and whichever survived was
compared with the previous month as an ordinary trend. Three separate wrong
statements from one missing fact: the clock time the form had printed all along.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest

import support  # noqa: F401
from scholion import core, format as fmt, ingest_labs, store
from scholion.engine import labs

PAIR = {"glucose": {"name": "Глюкоза", "unit": "mmol/L", "ref_low": 4.1, "ref_high": 5.9,
                    "series": [{"date": "2026-08-19T08:15", "value": 5.4},
                               {"date": "2026-08-19T14:30", "value": 7.8}]}}


class _Profile(unittest.TestCase):
    def _with(self, markers):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        (pathlib.Path(d) / "labs.json").write_text(json.dumps({"markers": markers},
                                                              ensure_ascii=False))
        core.reset_cache()
        return pathlib.Path(d)

    def tearDown(self):
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        core.reset_cache()


class TestTheFormsClockTimeIsRead(unittest.TestCase):
    def test_a_time_printed_after_the_date_is_kept(self):
        date, found = ingest_labs.parse_report(
            "Дата взятия: 22.07.2026 08:15\nГлюкоза 5.4 ммоль/л 4.1 - 5.9\n",
            core.lab_markers()["markers"], source="x")
        self.assertEqual(date, "2026-07-22T08:15")
        self.assertTrue(found)

    def test_a_form_without_a_time_still_parses_to_the_day(self):
        date, _ = ingest_labs.parse_report(
            "Дата забора: 22.07.2026\nГлюкоза 5.4 ммоль/л 4.1 - 5.9\n",
            core.lab_markers()["markers"], source="x")
        self.assertEqual(date, "2026-07-22")

    def test_a_clock_time_far_from_the_date_is_not_taken(self):
        """A time elsewhere on the form may be the printing or the opening hours,
        and a wrong time would order the two draws the wrong way round."""
        date, _ = ingest_labs.parse_report(
            "Дата забора: 22.07.2026\nОтчёт сформирован в 19:42\nГлюкоза 5.4 ммоль/л 4.1 - 5.9\n",
            core.lab_markers()["markers"], source="x")
        self.assertEqual(date, "2026-07-22")


class TestThePairIsReadAsAPair(_Profile):
    def test_both_measurements_survive(self):
        self._with(PAIR)
        r = labs.analyze_labs()
        self.assertEqual(len(r["markers"][0]["repeats"]), 1)
        self.assertEqual([p["value"] for p in r["markers"][0]["repeats"][0]["points"]],
                         [5.4, 7.8])

    def test_the_pair_is_not_printed_as_a_trend(self):
        """Eight hours across a procedure is not a course; an arrow saying «+44 %
        since the previous measurement» is the sentence a reader believes."""
        self._with(PAIR)
        r = labs.analyze_labs()
        self.assertIsNone(r["markers"][0].get("trend"))

    def test_a_trend_across_days_still_works(self):
        m = json.loads(json.dumps(PAIR))
        m["glucose"]["series"].insert(0, {"date": "2026-05-02T09:00", "value": 5.0})
        self._with(m)
        r = labs.analyze_labs()
        t = r["markers"][0].get("trend")
        self.assertIsNotNone(t, "a real trend between different days was lost")
        self.assertTrue(t["from_date"].startswith("2026-05-02"))

    def test_the_report_asks_what_happened_between_them(self):
        self._with(PAIR)
        out = fmt.labs_report(labs.analyze_labs())
        self.assertIn("2026-08-19", out)
        self.assertRegex(out, r"(?i)(what happened between|что было между)")


class TestAFastingThresholdIsQualified(_Profile):
    """The base has recorded «glucose is taken fasting» for years while the engine
    applied fasting thresholds to any measurement whatever the hour."""

    def test_the_second_draw_of_the_day_does_not_assert_a_fasting_condition(self):
        self._with(PAIR)
        r = labs.analyze_labs()
        self.assertTrue(r["markers"][0]["fasting_not_established"])

    def test_knowing_what_happened_does_not_restore_the_presumption(self):
        """Learning that an infusion came in between explains why «fasting» fails;
        it does not make the label apply."""
        self._with(PAIR)
        store.set_draw_context("2026-08-19", "control", "intravenous glucose")
        core.reset_cache()
        r = labs.analyze_labs()
        self.assertTrue(r["markers"][0]["fasting_not_established"])
        out = fmt.labs_report(r)
        self.assertIn("intravenous glucose", out)

    def test_a_single_draw_keeps_its_thresholds_unqualified(self):
        one = {"glucose": {"name": "Глюкоза", "unit": "mmol/L", "ref_low": 4.1, "ref_high": 5.9,
                           "series": [{"date": "2026-08-19T08:15", "value": 7.8}]}}
        self._with(one)
        r = labs.analyze_labs()
        self.assertFalse(r["markers"][0].get("fasting_not_established"))


class TestRecordingTheContext(_Profile):
    def test_the_context_attaches_to_the_later_point(self):
        d = self._with(PAIR)
        res = store.set_draw_context("2026-08-19", "control before and after", "infusion")
        self.assertTrue(res["ok"])
        saved = json.loads((d / "labs.json").read_text(encoding="utf-8"))
        pts = saved["markers"]["glucose"]["series"]
        self.assertIsNone(pts[0].get("draw_context"))
        self.assertIn("infusion", pts[1]["draw_context"])

    def test_a_day_with_no_repeat_is_refused_rather_than_silently_stored(self):
        self._with({"glucose": {"name": "Г", "unit": "mmol/L",
                                "series": [{"date": "2026-08-19T08:15", "value": 5.4}]}})
        res = store.set_draw_context("2026-08-19", "x", "y")
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main()
