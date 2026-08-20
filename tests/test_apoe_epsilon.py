"""APOE epsilon status, derived from haplotypes rather than from allele order.

Audit finding 49. The previous implementation paired the first allele of
rs429358 with the first of rs7412, as though a VCF's allele order encoded phase.
It does not — an unphased genotype is a multiset — so the SAME person came out
ε2/ε4 or ε3/ε4 depending only on whether their file happened to write «CT» or
«TC». That was reproduced before the rewrite, and the difference is not
cosmetic: ε2 is protective for Alzheimer's disease where ε3 is neutral.

The replacement writes down the four haplotype definitions and DERIVES every
genotype combination from them. Typing the table out by hand was tried first and
produced two errors in nine rows — a missing common genotype and a swapped pair.
The biology is four lines; the combinatorics is the computer's job.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401
from scholion import genome


class TestTheTableIsDerivedAndComplete(unittest.TestCase):
    def test_all_nine_genotype_combinations_are_covered(self):
        self.assertEqual(len(genome._APOE_TABLE), 9)

    def test_each_haplotype_pair_appears(self):
        """Ten unordered pairs of four haplotypes; nine genotype keys, because
        ε2/ε4 and ε1/ε3 collapse onto the same one — which is the ambiguity."""
        seen = {d for v in genome._APOE_TABLE.values() for d in v}
        self.assertEqual(len(seen), 10)

    def test_the_known_readings(self):
        want = {("TT", "CC"): "ε3/ε3", ("TT", "CT"): "ε2/ε3", ("TT", "TT"): "ε2/ε2",
                ("CT", "CC"): "ε3/ε4", ("CC", "CC"): "ε4/ε4", ("CT", "TT"): "ε1/ε2",
                ("CC", "CT"): "ε1/ε4", ("CC", "TT"): "ε1/ε1"}
        for key, dip in want.items():
            with self.subTest(genotypes=key):
                self.assertEqual(genome._APOE_TABLE[key], [dip])


class TestAlleleOrderNoLongerChangesTheAnswer(unittest.TestCase):
    def test_ct_and_tc_are_the_same_genotype(self):
        self.assertEqual(genome._unordered("TC"), genome._unordered("CT"))

    def test_the_reproduced_defect_is_gone(self):
        """«CT»/«CT» and «TC»/«CT» are one person written two ways."""
        a = genome._APOE_TABLE[(genome._unordered("CT"), genome._unordered("CT"))]
        b = genome._APOE_TABLE[(genome._unordered("TC"), genome._unordered("CT"))]
        self.assertEqual(a, b)


class TestTheAmbiguousCaseIsNamedNotGuessed(unittest.TestCase):
    def test_both_snps_heterozygous_has_two_readings(self):
        readings = genome._APOE_TABLE[("CT", "CT")]
        self.assertEqual(len(readings), 2)
        self.assertIn("ε2/ε4", readings)
        self.assertIn("ε1/ε3", readings)

    def test_no_other_genotype_is_ambiguous(self):
        ambiguous = [k for k, v in genome._APOE_TABLE.items() if len(v) > 1]
        self.assertEqual(ambiguous, [("CT", "CT")])


if __name__ == "__main__":
    unittest.main()
