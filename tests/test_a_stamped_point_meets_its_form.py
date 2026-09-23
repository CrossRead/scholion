"""A point stamped with the draw's day or clock time still meets the form it came from.

The loader stores the full stamp a form prints (`2024-03-14T08:20`), and two
readers kept looking such a point up by month. The provenance audit found no
form for it and called every stamped point «entered by hand»; the reconciliation
found no point for any form and reported every one as missing from the profile.
Both now match a draw by resolution: a month covers its days, a day covers its
clock times, and two different days are two draws.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import support
from scholion import core, provenance
from scholion.reconcile import same_draw


class TestSameDraw(unittest.TestCase):

    def test_resolution_not_string(self):
        self.assertTrue(same_draw("2024-03", "2024-03-14T08:20"))
        self.assertTrue(same_draw("2024-03-14", "2024-03-14T08:20"))
        self.assertTrue(same_draw("2024-03-14T08:20", "2024-03-14T08:20"))
        self.assertFalse(same_draw("2024-03-14", "2024-03-15"))
        self.assertFalse(same_draw("2024-03-14T08:20", "2024-03-14T17:05"))
        self.assertFalse(same_draw(None, "2024-03"))


class TestProvenanceFindsTheFormOfAStampedPoint(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile = Path(self.tmp.name).resolve() / "profile"
        self.profile.mkdir()
        self._restore = support.pin_profile(self.profile)
        core.reset_cache()

    def tearDown(self):
        self._restore()
        core.reset_cache()
        self.tmp.cleanup()

    def test_verdict_is_form(self):
        (self.profile / "labs.json").write_text(json.dumps({"markers": {"glucose": {
            "name": "Glucose", "unit": "mmol/L",
            "series": [{"date": "2024-03-14T08:20", "value": 5.4, "subject": "owner",
                        "date_source": "form"}]}}}), encoding="utf-8")
        (self.profile / "labs_coverage.json").write_text(json.dumps({"coverage": {"glucose": {
            "2024-03": {"file": "a.pdf", "draw_date": "2024-03-14T08:20", "value": 5.4,
                        "sources": [{"file": "a.pdf", "draw_date": "2024-03-14T08:20",
                                     "value": 5.4, "form": "—"}]}}}}), encoding="utf-8")
        core.reset_cache()
        out = provenance.audit(refresh=False)
        self.assertTrue(out.get("ok"), out)
        verdicts = [p["verdict"] for p in out["points"] if p["marker"] == "glucose"]
        self.assertEqual(["form"], verdicts)

    def test_a_form_of_another_day_in_the_month_is_not_this_points_form(self):
        (self.profile / "labs.json").write_text(json.dumps({"markers": {"glucose": {
            "name": "Glucose", "unit": "mmol/L",
            "series": [{"date": "2024-03-14", "value": 5.4, "subject": "owner",
                        "date_source": "form"}]}}}), encoding="utf-8")
        (self.profile / "labs_coverage.json").write_text(json.dumps({"coverage": {"glucose": {
            "2024-03": {"file": "b.pdf", "draw_date": "2024-03-28", "value": 5.4,
                        "sources": [{"file": "b.pdf", "draw_date": "2024-03-28",
                                     "value": 5.4, "form": "—"}]}}}}), encoding="utf-8")
        core.reset_cache()
        out = provenance.audit(refresh=False)
        verdicts = [p["verdict"] for p in out["points"] if p["marker"] == "glucose"]
        self.assertEqual(["manual"], verdicts)


if __name__ == "__main__":
    unittest.main()
