"""The genes a «nothing found» cannot rest on, in a form somebody can act on.

«Zero pathogenic findings across the ACMG genes» is honest exactly as far as
those genes were read, and the coverage table has known which ones were not since
it was written. What it could not do is hand that list to anybody: a percentage
names a gene, and a laboratory asked to re-read something needs coordinates. The
intervals were computed by the pipeline and thrown away one line later.

So they are written down, and the weak list becomes a BED. Two things are
deliberate and are asserted here rather than described:

  · **coordinates are never invented from a gene name.** A table written before
    the columns existed names its weak genes and not their intervals, and the
    export refuses with the run that would fill them in. Deriving them from the
    gene symbol is exactly the plausible substitution this module exists against;
  · **the intervals are gene loci with a margin, not coding sequence**, and the
    track line says so. A 200 bp dropout inside an exon moves a locus-wide
    percentage by about 0.07 %, so this file is a worklist of genes to look at
    again — not a map of the bases that were missed. Printing it without that
    sentence would be the quiet substitution one level up.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path

from scholion import core, limits

HEAD_OLD = "gene\tpanel\tchrom\tlength_bp\tmean_depth\trel_to_panel\tpct_1x\tpct_10x\tpct_20x\tpct_30x"
HEAD_NEW = HEAD_OLD + "\tstart\tend"


def row(gene, panel, chrom, p10, start=None, end=None, old=False):
    base = f"{gene}\t{panel}\t{chrom}\t300000\t31.0\t1.00\t99.0\t{p10}\t80.0\t60.0"
    return base if old else base + f"\t{start if start is not None else ''}\t{end if end is not None else ''}"


class _Profile(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="bed-"))
        (self.dir / "profile").mkdir()
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.dir / "profile")
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        core.reset_cache()
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, head, rows):
        (self.dir / "profile" / "callability.tsv").write_text(
            "\n".join([head] + rows) + "\n", encoding="utf-8")
        core.reset_cache()


class TestWhenThereIsNothingToExport(_Profile):

    def test_a_profile_that_never_measured_coverage_is_told_what_to_run(self):
        r = limits.weak_regions_bed()
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "never_computed")
        self.assertIn("qc_callability.sh", r["note"])

    def test_a_panel_read_above_the_floor_exports_nothing_and_says_why(self):
        self.write(HEAD_NEW, [row("BRCA1", "ACMG", "chr17", 99.4, 100, 200)])
        r = limits.weak_regions_bed()
        self.assertTrue(r["ok"])
        self.assertEqual(r["regions"], 0)
        self.assertEqual(r["bed"], "")


class TestCoordinatesAreNotInvented(_Profile):

    def test_an_older_table_refuses_and_names_the_genes_and_the_remedy(self):
        self.write(HEAD_OLD, [row("BRCA2", "ACMG", "chr13", 71.2, old=True)])
        r = limits.weak_regions_bed()
        self.assertFalse(r["ok"])
        self.assertEqual(r["reason"], "no_coordinates")
        self.assertEqual(r["genes"], ["BRCA2"])
        self.assertIn("BRCA2", r["note"])
        self.assertIn("qc_callability.sh", r["note"])

    def test_one_gene_without_coordinates_stops_the_whole_export(self):
        """A partial BED is worse than none: whoever receives it re-reads what it
        lists and believes the rest was fine."""
        self.write(HEAD_NEW, [row("BRCA2", "ACMG", "chr13", 71.2, 100, 200),
                              row("PMS2", "ACMG", "chr7", 55.0)])
        r = limits.weak_regions_bed()
        self.assertFalse(r["ok"])
        self.assertEqual(r["genes"], ["PMS2"])


class TestTheFileItself(_Profile):

    def setUp(self):
        super().setUp()
        self.write(HEAD_NEW, [
            row("BRCA2", "ACMG", "chr13", 71.2, 32300000, 32400000),
            row("PMS2", "ACMG", "chr7", 55.0, 5980000, 6040000),
            row("CYP2D6", "PGX", "chr22", 61.0, 42120000, 42135000),
            row("BRCA1", "ACMG", "chr17", 99.4, 43040000, 43130000),
        ])

    def test_only_the_genes_below_the_floor_are_in_it(self):
        r = limits.weak_regions_bed()
        self.assertTrue(r["ok"])
        self.assertEqual(r["regions"], 3)
        self.assertNotIn("BRCA1", r["bed"])

    def test_the_worst_gene_comes_first(self):
        r = limits.weak_regions_bed()
        body = [l for l in r["bed"].splitlines() if not l.startswith("track")]
        self.assertEqual([l.split("\t")[3] for l in body], ["PMS2", "CYP2D6", "BRCA2"])

    def test_every_line_is_a_bed_interval_carrying_its_percentage(self):
        r = limits.weak_regions_bed()
        for line in r["bed"].splitlines():
            if line.startswith("track"):
                continue
            chrom, start, end, name, score = line.split("\t")
            self.assertTrue(chrom.startswith("chr"))
            self.assertLess(int(start), int(end))
            self.assertTrue(name)
            self.assertLess(float(score), limits.WEAK_10X)

    def test_the_track_line_says_the_intervals_are_not_coding_sequence(self):
        """Without this sentence the file reads as «these bases were missed»,
        which is not what a locus-wide percentage can say."""
        track = r"" 
        track = limits.weak_regions_bed()["bed"].splitlines()[0]
        self.assertTrue(track.startswith("track "))
        self.assertIn("not coding sequence", track)

    def test_a_panel_can_be_asked_for_on_its_own(self):
        r = limits.weak_regions_bed(panels=["PGX"])
        self.assertEqual(r["regions"], 1)
        self.assertIn("CYP2D6", r["bed"])
        self.assertNotIn("PMS2", r["bed"])


if __name__ == "__main__":
    unittest.main()
