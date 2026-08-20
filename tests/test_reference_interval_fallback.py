"""A value with no corridor, for a marker the reference base has one for.

Found by sweeping the gap enumerators across the laboratory tree. The engine
took the reference interval from the person's own profile and never from the
catalogue, so a result imported without a printed range — or typed by hand —
was shown as a bare number however far from normal it was. Alkaline phosphatase
at twice the upper limit printed as «0 values out of range».

The rule is narrow on purpose: the person's own form always wins, the catalogue
only fills a hole, and the borrowed interval is labelled — a general population
range is a weaker statement than the one the person's laboratory printed.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest

import support  # noqa: F401
from scholion import core, format as fmt
from scholion.engine import labs


class TestTheCatalogueFillsAMissingInterval(unittest.TestCase):
    def _run(self, marker):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        (pathlib.Path(d) / "labs.json").write_text(json.dumps({"markers": marker}))
        core.reset_cache()
        try:
            return labs.analyze_labs()
        finally:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
            core.reset_cache()

    def test_a_value_far_out_of_range_is_flagged_even_with_no_range_on_file(self):
        r = self._run({"alp": {"name": "ALP", "unit": "U/L",
                               "series": [{"date": "2026-07", "value": 258}]}})
        m = r["markers"][0]
        self.assertEqual(m["flag"], "high")
        self.assertTrue(m["abnormal"])
        self.assertTrue(m["ref_reference_base"])
        self.assertEqual(r["abnormal_count"], 1)

    def test_the_borrowed_interval_says_it_is_borrowed(self):
        r = self._run({"alp": {"name": "ALP", "unit": "U/L",
                               "series": [{"date": "2026-07", "value": 258}]}})
        out = fmt.labs_report(r)
        self.assertIn("reference", out.lower())

    def test_the_persons_own_range_is_never_overridden(self):
        """A form-printed interval is the person's own laboratory's and wins."""
        r = self._run({"alp": {"name": "ALP", "unit": "U/L",
                               "ref_low": 30, "ref_high": 300,
                               "series": [{"date": "2026-07", "value": 258}]}})
        m = r["markers"][0]
        self.assertEqual((m["ref_low"], m["ref_high"]), (30, 300))
        self.assertFalse(m.get("ref_reference_base"))
        self.assertEqual(m["flag"], "ok")

    def test_a_marker_the_base_knows_nothing_about_still_says_norange(self):
        """Filling a hole must not become inventing a corridor."""
        r = self._run({"aa_aaba_unknown_marker": {"name": "X", "unit": "u",
                                                  "series": [{"date": "2026-07", "value": 5}]}})
        self.assertEqual(r["markers"][0]["flag"], "norange")
        self.assertFalse(r["markers"][0].get("ref_reference_base"))


if __name__ == "__main__":
    unittest.main()
