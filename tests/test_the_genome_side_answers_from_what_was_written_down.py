"""Two answers on the genome side come from files a script wrote, not from memory.

A gene whose bases were read too shallowly to decide is named from the
callability table — the depth was computed all along, and the findings report
never consulted it until it did. And the result of the last database check is
reported from the file that check wrote, marked available only when it holds
a ClinVar block. Both are checked on a pinned throw-away profile; neither
opens a genome.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core
from scholion.engine import genomics

HEAD = ("gene\tpanel\tchrom\tlength_bp\tmean_depth\trel_to_panel\t"
        "pct_1x\tpct_10x\tpct_20x\tpct_30x\n")


class TestAGeneReadTooShallowlyIsNamed(unittest.TestCase):

    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="shallow_"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "profile").mkdir()
        self.profile = root / "profile"
        self.addCleanup(support.pin_profile(self.profile))
        self.addCleanup(support.pin_cache(root / "cache"))

    def _table(self, rows):
        (self.profile / "callability.tsv").write_text(HEAD + "".join(rows), encoding="utf-8")
        core.reset_cache()

    def test_below_ninety_percent_at_ten_x_is_unread_and_the_figure_travels(self):
        self._table(["SHALLOW\tacmg\t1\t1000\t12.0\t0.3\t99.0\t61.25\t40.0\t20.0\n",
                     "DEEP\tacmg\t1\t1000\t35.0\t1.0\t100.0\t99.8\t98.0\t95.0\n"])
        out = genomics._unread_genes(["SHALLOW", "DEEP", "NEVER_MEASURED"])
        self.assertEqual([{"gene": "SHALLOW", "pct": 61.2}], out)

    def test_a_figure_that_is_not_one_is_skipped_rather_than_guessed(self):
        """The table reader is one thing and this rule another: a row it hands
        over without a depth figure, or with one that is not a number, is left
        out rather than read as zero — «unread» is a claim, not a default."""
        from scholion import limits
        rows = {"NO_FIGURE": {"mean_depth": 3.0}, "ODD": {"pct_10x": "n/a"},
                "SHALLOW": {"pct_10x": "12.5"}}
        with mock.patch.object(limits, "callability", lambda: rows):
            out = genomics._unread_genes(["NO_FIGURE", "ODD", "SHALLOW", "ABSENT"])
        self.assertEqual([{"gene": "SHALLOW", "pct": 12.5}], out)


class TestTheLastDatabaseCheckIsReportedFromItsFile(unittest.TestCase):

    def test_a_check_that_ran_is_available_with_its_release(self):
        found = {"last_checked": "2026-09-01",
                 "clinvar": {"release": "2026-08-31", "new": ["rs1"], "changed": [],
                             "counts": {"new": 1, "changed": 0}}}
        with mock.patch.object(core, "whats_new", lambda: found):
            out = genomics.genome_updates()
        self.assertTrue(out["available"])
        self.assertEqual("2026-09-01", out["last_checked"])
        self.assertEqual("2026-08-31", out["clinvar"]["release"])
        self.assertEqual(["rs1"], out["clinvar"]["new"])
        self.assertEqual({"new": 1, "changed": 0}, out["clinvar"]["counts"])

    def test_no_check_and_a_check_without_clinvar_are_both_unavailable(self):
        for data in ({}, {"last_checked": "2026-09-01"}):
            with self.subTest(data=data), mock.patch.object(core, "whats_new", lambda: data):
                self.assertFalse(genomics.genome_updates()["available"])


if __name__ == "__main__":
    unittest.main()
