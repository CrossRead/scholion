"""Stored PGS remain visible without reinstating withdrawn clinical conclusions."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import support
from pgs_support import calibrated
from scholion import core, engine, format as fmt, i18n
from scholion.engine import genomics, system_panels
from scholion.format_system import _system_polygenic
from scholion.pgs_validation import retain_saved_value, validate


class SavedValues(unittest.TestCase):
    def test_legacy_numbers_survive_reading_on_all_shared_surfaces(self):
        rows = [{"term": "coronary artery disease", "label": "CAD", "pgs_id": "PGS000001",
                 "percentile": 99.86, "reliable": True},
                {"term": "lipoprotein a", "label": "Lp(a)", "pgs_id": genomics._LPA_PGS,
                 "percentile": 91.2, "reliable": True}]
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp)
            original = json.dumps({"traits": rows}).encode()
            target = profile / "prs_results.json"
            target.write_bytes(original)
            restore = support.pin_profile(profile)
            try:
                for lang in ("en", "ru"):
                    with mock.patch.object(i18n._state, "current", lang, create=True):
                        core.reset_cache()
                        findings = engine.prs_findings()
                        self.assertEqual([], findings["high"])
                        self.assertEqual(0, findings["stats"]["reliable"])
                        stored = [r for c in findings["categories"] for r in c["traits"]]
                        self.assertEqual([99.86, 91.2], [r["saved_result"]["value"] for r in stored])
                        text = fmt.prs_report(findings)
                        for row in stored:
                            self.assertIn(row["saved_result"]["label"], text)
                            self.assertIn(row["saved_result"]["note"], text)
                        with mock.patch.object(system_panels, "prs_system_map", return_value={"systems": {"test": {"traits": [rows[0]["term"]]}}}):
                            poly = system_panels._polygenic_block("test", findings)
                        self.assertEqual([], poly["high"])
                        for register in ("patient", "clinician"):
                            display = "\n".join(_system_polygenic(poly, register))
                            self.assertIn(stored[0]["saved_result"]["label"], display)
                            self.assertIn(stored[0]["saved_result"]["note"], display)
                        estimate = engine.lipid_genetics()["lpa"]["estimate"]
                        self.assertEqual(91.2, estimate["saved_result"]["value"])
                        self.assertIn(estimate["saved_result"]["note"], fmt.lipid_genetics_report(engine.lipid_genetics()))
                        self.assertEqual(original, target.read_bytes())
            finally:
                restore()
                core.reset_cache()

    def test_changed_input_removes_current_confirmation_but_preserves_the_number(self):
        row = calibrated({"term": "coronary artery disease", "label": "CAD",
                          "pgs_id": "PGS000001", "percentile": 97})
        original = copy.deepcopy(row)
        with mock.patch.object(core, "prs_results", return_value={"traits": [row]}), \
             mock.patch("scholion.prs_recompute.recalculation_status", return_value={"required": True, "traits": 1, "reason": "input_changed"}):
            findings = engine.prs_findings()
        current = findings["categories"][0]["traits"][0]
        self.assertEqual(97, current["saved_result"]["value"])
        self.assertTrue(current["saved_result"]["recalculation_required"])
        self.assertIsNone(current["percentile"])
        self.assertEqual([], findings["high"])
        self.assertEqual(original, row)

    def test_successful_confirmed_result_does_not_display_previous_history_as_current(self):
        row = calibrated({"pgs_id": "PGS000001", "percentile": 50,
                          "previous_result": {"percentile": 100}})
        current = validate(row)
        retain_saved_value(current)
        self.assertNotIn("saved_result", current)
        self.assertEqual(50, current["percentile"])
        self.assertEqual(100, current["previous_result"]["percentile"])

    def test_invalid_stored_values_are_not_fabricated(self):
        for value in (None, float("nan"), float("inf"), -1, 101, True):
            row = {"reliable": False, "diagnostic_percentile": value}
            retain_saved_value(row)
            self.assertNotIn("saved_result", row)
