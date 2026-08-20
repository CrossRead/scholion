"""The gap enumerators must work, and must not be able to pretend they do.

`check_coverage.py` compares what the build carries against what it ought to,
in three ways. The danger of such a tool is not that it reports a wrong gap; it
is that it reports NONE because it is structurally incapable of finding one. The
first draft of the orphan-fact enumerator called a demo function that does not
exist, got an empty profile, and reported «0 orphans» — a clean bill of health
produced by a bug. It would have kept doing so forever.

So these tests check the enumerators can fire, not merely that they run.
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

import support  # noqa: F401

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "tools"))
import check_coverage as cc  # noqa: E402


class TestTheEnumeratorsCanActuallyFire(unittest.TestCase):
    def test_the_orphan_scan_finds_the_writers(self):
        """The specific bug that made this file necessary: no writers found,
        so nothing to compare, so a permanent zero."""
        orphans = cc.orphan_facts()          # raises if the writers vanish
        self.assertIsInstance(orphans, list)
        self.assertTrue(orphans, "the orphan scan found nothing at all — either every "
                                 "written fact is now read (update the baseline) or the "
                                 "scan has stopped working")

    def test_the_authority_list_is_not_empty(self):
        delta = cc.authority_delta()
        self.assertGreater(delta["total"], 50,
                           "the CPIC level-A pair list is missing or truncated, so the "
                           "comparison would report full coverage of nothing")
        self.assertGreater(delta["carried"], 0)

    def test_a_collection_key_is_not_mistaken_for_a_schema_field(self):
        """Marker names and rsids are data. Treating them as fields buried the
        eleven real findings under five hundred false ones."""
        self.assertTrue(cc.orphan_facts.__doc__)
        collection = {f"marker_{i}": {"series": [], "unit": "x"} for i in range(9)}
        self.assertNotIn("marker_3", "\n".join(cc.orphan_facts()))
        del collection


class TestNoNewGapAppeared(unittest.TestCase):
    """The gate itself, in the project's existing idiom: known gaps are listed in
    the baseline; a new one fails until it is fixed or accepted deliberately."""

    def test_the_baseline_still_covers_what_is_found(self):
        base = json.loads((ROOT / "src" / "tools" / "coverage_baseline.json")
                          .read_text(encoding="utf-8"))
        now = cc.collect()
        new = []
        for key in ("authority_partial", "coverage_holes", "orphan_facts", "authority_absent"):
            was = set(base.get(key, []))
            new += [f"{key}: {i}" for i in now.get(key, []) if i not in was]
        self.assertEqual(new, [],
                         "a gap that did not exist before has appeared. Fix it, or run\n"
                         "  python3 src/tools/check_coverage.py --accept\n"
                         "so the new gap is recorded and visible in review:\n  " +
                         "\n  ".join(new))

    def test_the_severe_classes_stay_empty(self):
        """Two of the four classes are held at zero rather than baselined: a
        phenotype with no row answers as «unknown» for a person who has the
        variant, and that is not a limit worth accepting quietly."""
        now = cc.collect()
        self.assertEqual(now["coverage_holes"], [])


if __name__ == "__main__":
    unittest.main()
