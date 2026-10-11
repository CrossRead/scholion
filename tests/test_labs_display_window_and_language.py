"""Current lab summaries preserve historical data without presenting it as current."""
from __future__ import annotations
import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import support
from scholion import core, engine, i18n, cli
from scholion.engine import _helpers
from scholion.format_labs import labs_report, targets_report
from pgs_support import calibrated


class FrozenDate(datetime.date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 11)


class LabDisplay(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.addCleanup(support.pin_profile(self.root))
        self.addCleanup(i18n.set_lang, getattr(i18n._state, "current", None))
        i18n.set_lang("en")
        self.clock = patch.object(_helpers.datetime, "date", FrozenDate)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.data = {"markers": {
            "glucose": {"name": "Glucose", "unit": "\u043c\u043c\u043e\u043b\u044c/\u043b", "ref_high": 6,
                        "note": "Legacy draft with internal deliberations",
                        "series": [{"date": "2024-01-02", "value": 9},
                                   {"date": "2026-09-02", "value": 7}]},
            "calcium": {"name": "Calcium", "unit": "mmol/L", "ref_high": 2.6,
                        "series": [{"date": "2025-10-10", "value": 3}]}}}
        (self.root / "labs.json").write_text(json.dumps(self.data), encoding="utf-8")
        core.reset_cache()

    def test_one_year_boundary_respects_day_or_month_precision(self):
        self.assertFalse(_helpers._lab_display_recency("2025-10-10"))
        self.assertTrue(_helpers._lab_display_recency("2025-10-11"))
        self.assertTrue(_helpers._lab_display_recency("2025-10"))
        self.assertFalse(_helpers._lab_display_recency("2025-09"))
        for stamp in ("", "invalid", "2026-99", "2026-11-01"):
            self.assertIsNone(_helpers._lab_display_recency(stamp))
        with patch.object(FrozenDate, "today", return_value=FrozenDate(2024, 2, 29)):
            self.assertTrue(_helpers._lab_display_recency("2023-02-28"))

    def test_recent_summary_keeps_original_flags_series_and_input_unchanged(self):
        result = engine.analyze_labs()
        self.assertEqual(2, result["count"])
        self.assertEqual(2, result["abnormal_count"])
        self.assertEqual(1, result["current_stats"]["abnormal_count"])
        self.assertEqual(1, result["historical_count"])
        row = next(m for m in result["markers"] if m["key"] == "glucose")
        self.assertEqual(2, len(row["series"]))
        self.assertEqual("mmol/L", row["unit_display"])
        self.assertEqual(self.data, json.loads((self.root / "labs.json").read_text(encoding="utf-8")))
        text = labs_report(result)
        self.assertNotIn("Calcium:", text)
        self.assertNotIn("internal deliberations", text)
        self.assertIn("7 mmol/L", text)
        self.assertIn("Calcium:", labs_report(result, include_history=True))
        self.assertTrue(cli.build_parser().parse_args(["labs", "--history"]).history)

    def test_historical_target_is_not_a_current_question(self):
        (self.root / "clinician_targets.json").write_text(json.dumps({"targets": [
            {"marker": "calcium", "high": 2.4, "unit": "mmol/L", "set_by": "Synthetic clinician", "set_on": "2026-01-01"}]}), encoding="utf-8")
        core.reset_cache()
        result = engine.targets.clinician_targets_view()
        self.assertEqual([], result["to_discuss"])
        self.assertIn("Historical value", targets_report(result))
        self.assertNotIn("outside the target", targets_report(result))

    def test_verified_calls_with_unavailable_calibration_do_not_claim_bad_coordinates(self):
        row = calibrated({"pgs_id": "PGS000001"})
        row.update(percentile=None, percentile_method="auroc_approx", reference_panel=None,
                   reference_panel_ancestry=None, reference_validation={"checked": False})
        for language in ("en", "ru"):
            i18n.set_lang(language)
            with patch.object(core, "prs_results", return_value={"traits": [row]}), \
                 patch.object(engine.genomics, "_array_only_input", return_value=None):
                result = engine.prs_findings()
            tr = result["categories"][0]["traits"][0]
            self.assertTrue(tr["build_validation"]["valid"])
            self.assertIsNone(tr["percentile"])
            self.assertTrue(tr["calibration_note"].startswith(i18n.t("prs.validation.calibration_only")))
            self.assertFalse(tr["reliable"])


if __name__ == "__main__":
    unittest.main()
