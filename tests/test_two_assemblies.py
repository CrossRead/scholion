"""A file in GRCh37 is read at GRCh37 coordinates — and nothing is converted.

Seven of the eight real genomes in the PGP corpus turned out to be GRCh37, and
the genome layer switched itself off on every one of them. Nothing was broken:
the locus catalogue existed only in GRCh38, so refusing was the correct answer to
what the catalogue then knew. It was also useless to every one of those people.

The fix is a second coordinate per locus, not a conversion. The offset between
builds is not constant even inside one chromosome — 405 kb of spread on chr1
across the pairs measured on the corpus — so arithmetic would hand back a
plausible position pointing at the wrong base, which is worse than a refusal and
much harder to notice. `test_the_offset_is_not_a_constant` is here to stop anyone
turning the table into a formula later.

A locus with no GRCh37 coordinate is not read out of a GRCh37 file at all. It
says which build it is missing, and it does NOT fall through to the reference
assumptions below — «no coordinate» and «no variant» are different sentences.
"""
from __future__ import annotations

import collections
import os
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import genome


class TestTheCatalogueCarriesTwoBuilds(unittest.TestCase):

    def setUp(self):
        self.loci = genome.loci()["loci"]

    def test_pos_still_means_grch38(self):
        self.assertEqual(genome.catalogue_assembly(), "GRCh38")
        self.assertTrue(all(l.get("pos") for l in self.loci.values()))

    def test_grch37_is_offered_only_because_it_is_carried(self):
        served = genome.catalogue_assemblies()
        self.assertIn("GRCh38", served)
        carried = sum(1 for l in self.loci.values() if l.get("pos_grch37"))
        self.assertEqual("GRCh37" in served, carried > 0,
                         "a build must not be advertised unless a locus can answer in it")

    def test_the_promise_is_stated_as_a_fraction(self):
        """«Supports GRCh37» and «supports 33 of 54 loci» are different promises.

        The fraction is now 54 of 54, and the shape of the answer still has to be
        a fraction rather than a yes: the next locus somebody adds will arrive in
        GRCh38 alone, and the promise has to be able to drop back on its own.
        """
        cov = genome.catalogue_coverage_by_assembly()
        self.assertEqual(cov["GRCh38"], cov["total"])
        self.assertLessEqual(cov["GRCh37"], cov["total"])
        self.assertGreater(cov["GRCh37"], 0)

    def test_every_locus_answers_in_both_builds(self):
        """Task 83. Seven of eight corpus genomes were GRCh37 and got nothing.

        This asserts the state, not the method: if a locus is added without a
        GRCh37 position the build says so here, and the fix is to run
        `src/tools/fill_grch37.py` from a machine with a network — never to type
        the number.
        """
        missing = sorted(rs for rs, l in self.loci.items() if not l.get("pos_grch37"))
        self.assertEqual(missing, [], "run src/tools/fill_grch37.py --apply for these")

    def test_every_second_coordinate_is_a_plausible_position(self):
        for rs, l in self.loci.items():
            g37 = l.get("pos_grch37")
            if g37 is None:
                continue
            with self.subTest(rsid=rs):
                self.assertIsInstance(g37, int)
                self.assertGreater(g37, 0)
                self.assertNotEqual(g37, l["pos"], "the two builds do not agree on any of these")

    def test_the_offset_is_not_a_constant(self):
        """The reason this is a table and not a formula, asserted from the data."""
        by_chrom = collections.defaultdict(set)
        for l in self.loci.values():
            if l.get("pos_grch37"):
                by_chrom[l["chrom"]].add(l["pos"] - l["pos_grch37"])
        varying = [c for c, deltas in by_chrom.items() if len(deltas) > 1]
        self.assertTrue(varying, "if every chromosome had one offset, somebody would "
                                 "eventually replace the table with arithmetic — and be wrong")


class TestReadingAGrch37File(unittest.TestCase):

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in
                     ("SCHOLION_GENOME_ASSEMBLY", "SCHOLION_GENOME_VCF")}
        os.environ["SCHOLION_GENOME_ASSEMBLY"] = "GRCh37"
        os.environ["SCHOLION_GENOME_VCF"] = str(
            support.ROOT / "tests" / "fixtures" / "genome" / "tiny.vcf.gz")

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def a_locus(self, with_grch37=True):
        for rs, l in genome.loci()["loci"].items():
            if bool(l.get("pos_grch37")) == with_grch37:
                return dict(l, rsid=rs)
        if with_grch37:
            self.skipTest("no such locus in the catalogue")
        # Every catalogued locus now carries both builds, so the refusal below has
        # no live example to borrow. Borrowing one was never the point: the
        # behaviour under test is what happens to a locus that lacks the position,
        # and it has to stay asserted for the day somebody adds one.
        return {"rsid": "rs0", "gene": "SYNTHETIC", "chrom": "1",
                "pos": 1000000, "ref": "A", "alt": "G"}

    def test_a_grch37_file_is_no_longer_a_mismatch(self):
        av = genome.available()
        self.assertEqual(av["assembly"], "GRCh37")
        self.assertFalse(av["assembly_mismatch"])
        self.assertEqual(av["coordinates"], "GRCh37")

    def test_the_query_uses_the_grch37_position(self):
        loc = self.a_locus(with_grch37=True)
        seen = []
        original = genome._query_region
        genome._query_region = lambda vcf, chrom, pos: seen.append((chrom, pos)) or []
        try:
            genome._gt_at(loc)
        finally:
            genome._query_region = original
        self.assertTrue(seen)
        self.assertEqual(seen[0][1], loc["pos_grch37"],
                         "the GRCh38 position would land on a real base — the wrong one")

    def test_a_locus_without_a_grch37_coordinate_is_not_read(self):
        loc = self.a_locus(with_grch37=False)
        got = genome._gt_at(loc)
        self.assertEqual(got["confidence"], "no_coordinates_for_assembly")
        self.assertIsNone(got["genotype"])
        self.assertNotIn("assumed_ref", str(got.get("confidence")),
                         "«no coordinate» must never become «reference here»")
        self.assertIn("GRCh37", got["note"])


if __name__ == "__main__":
    unittest.main()
