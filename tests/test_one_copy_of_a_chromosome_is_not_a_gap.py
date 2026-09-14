"""A locus read in one copy is judged against one copy.

A hemizygous chromosome comes at half the depth of a diploid one by
construction, so the fraction of its bases at 20× collapses. On the owner's 26×
genome the chrX median fell to 9 % against 80 % on the autosomes, and the engine
— which compared every gene with one median and one absolute floor — called
every gene of the X «read too thinly to decide»: 62 of the 108 such rows on the
radar, all of them false. The coverage script was taught this in August («chrX in
a male comes at half depth by construction — that is not a gap»); the engine,
written later, was not.

Nothing here asks for a sex and nothing reads one from a profile: the table says
it. What changes is the threshold, not the tolerance — a hemizygous call needs
10× where a heterozygous one needs 20× — and the reference point becomes the
median of the same kind of locus.

Held here:

  * one copy is MEASURED from the table, by the depth of the sex chromosomes
    against the autosomes, and a table without autosomes to compare against
    keeps the stricter threshold;
  * with one copy, a gene of the X is judged at 10× against the median of the X;
  * with two, nothing changes for anybody;
  * a gene of the X that is thin even for the X is still called thin;
  * the mitochondrion is not treated as a single-copy locus.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion.engine import genomics as G


def _row(chrom, depth, p10, p20):
    return {"chrom": chrom, "mean_depth": depth, "pct_10x": p10, "pct_20x": p20,
            "rel_to_panel": 1.0, "panel": "PANEL"}


def _table(x_depth, x_p10, x_p20, extra=None):
    """A dozen autosomal genes read well, and four on the X."""
    rows = {f"AUT{i}": _row("chr7", 26.0, 97.0, 80.0) for i in range(12)}
    rows.update({f"X{i}": _row("chrX", x_depth, x_p10, x_p20) for i in range(4)})
    rows.update(extra or {})
    return rows


class TestOneCopyIsMeasuredNotAssumed(unittest.TestCase):

    def test_half_the_depth_on_the_sex_chromosomes_reads_as_one_copy(self):
        self.assertTrue(G._single_copy(_table(13.0, 79.0, 9.0)))

    def test_the_same_depth_reads_as_two(self):
        self.assertFalse(G._single_copy(_table(26.0, 97.0, 80.0)))

    def test_a_table_with_nothing_to_compare_against_keeps_the_strict_rule(self):
        only_x = {f"X{i}": _row("chrX", 13.0, 79.0, 9.0) for i in range(4)}
        self.assertFalse(G._single_copy(only_x),
                         "without autosomes the ratio is unknown, and the stricter"
                         " threshold is the safe answer")


class TestWhatTheGeneIsJudgedBy(unittest.TestCase):

    def test_a_gene_of_a_single_copy_chromosome_is_judged_at_ten(self):
        rows = _table(13.0, 79.0, 9.0)
        r = G.gene_coverage("X1", rows)
        self.assertEqual(1, r["copies"])
        self.assertEqual("fine", r["state"], "9 % at 20× is one copy, not a gap")
        self.assertIn("pct_10x", r)
        self.assertNotIn("pct_20x", r, "the fraction it was NOT judged by is not shown")
        self.assertEqual(79.0, r["median_pct_10x"],
                         "the reference point is the median of the single-copy loci,"
                         " not of the whole table (97 % here)")

    def test_a_gene_thin_even_for_its_own_kind_is_still_thin(self):
        rows = _table(13.0, 79.0, 9.0, extra={"XBAD": _row("chrX", 4.0, 20.0, 2.0)})
        self.assertEqual("low", G.gene_coverage("XBAD", rows)["state"])

    def test_with_two_copies_nothing_changes(self):
        rows = _table(26.0, 97.0, 80.0, extra={"XLOW": _row("chrX", 6.0, 30.0, 9.0)})
        r = G.gene_coverage("X1", rows)
        self.assertEqual(2, r["copies"])
        self.assertEqual("fine", r["state"])
        self.assertIn("pct_20x", r)
        self.assertEqual("low", G.gene_coverage("XLOW", rows)["state"])

    def test_an_autosomal_gene_is_never_measured_against_the_x(self):
        rows = _table(13.0, 79.0, 9.0, extra={"AUTLOW": _row("chr7", 8.0, 40.0, 20.0)})
        r = G.gene_coverage("AUTLOW", rows)
        self.assertEqual(2, r["copies"])
        self.assertEqual("low", r["state"],
                         "20 % at 20× on an autosome is thin whatever the X looks like")
        self.assertEqual(80.0, r["median_pct_20x"], "the median is taken over autosomes")

    def test_the_mitochondrion_is_not_a_single_copy_locus(self):
        rows = _table(13.0, 79.0, 9.0, extra={"MT-TK": _row("chrM", 1997.0, 99.0, 90.0)})
        r = G.gene_coverage("MT-TK", rows)
        self.assertEqual(2, r["copies"], "the mitochondrion needs no allowance")
        self.assertEqual("fine", r["state"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
