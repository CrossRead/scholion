"""An empty or partial answer from a genome file is not a reading of the reference.

Six shapes, each found by the 0.5.7 review, each once printed as «reference» or
«zero copies»:

* a half call («./0») kept its one index and came out as a called genotype;
* a genotype written on the other strand, or naming another ALT of a
  multi-allelic site, was counted as zero copies of the variant — «normal»;
* a missing row on an exome (or a file whose breadth was never classified) was
  presumed to be the reference, although outside the targets nobody sequenced it;
* a contig the file does not hold returned no rows, which reads as reference —
  and the mitochondrion was looked up as `chrMT` in files that call it `chrM`;
* a multi-sample container was read from its first sample column;
* a gene region in GRCh38 coordinates was asked of a GRCh37 file.
"""
from __future__ import annotations

import gzip
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, genome
from scholion.engine import pgx, system_panels as SP


class TestAHalfCallIsNotACall(unittest.TestCase):

    def setUp(self):
        self._old = os.environ.get("SCHOLION_GENOME_VCF")
        os.environ["SCHOLION_GENOME_VCF"] = str(
            support.ROOT / "tests" / "fixtures" / "genome" / "tiny.vcf.gz")
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_GENOME_VCF", None)
        else:
            os.environ["SCHOLION_GENOME_VCF"] = self._old
        core.reset_cache()

    def _read(self, gt: str, fmt: str = "GT:DP"):
        loc = dict(genome.loci()["loci"]["rs1800462"], rsid="rs1800462")
        row = ["6", str(loc.get("pos")), "rs1800462", "C", "G", "60", "PASS", "DP=32",
               fmt, gt]
        with mock.patch.object(genome, "_query_region", lambda vcf, chrom, pos: [row]):
            return genome._gt_at(loc)

    def test_half_calls_are_refused(self):
        for gt in ("./0:30", "1/.:30", ".|1:30"):
            with self.subTest(gt=gt):
                r = self._read(gt)
                self.assertIsNone(r.get("genotype"), r)
                self.assertEqual("no_call_in_vcf", r["confidence"])

    def test_a_format_without_gt_is_no_genotype(self):
        r = self._read("32", fmt="DP")
        self.assertIsNone(r.get("genotype"), r)

    def test_a_full_call_still_reads(self):
        r = self._read("0/1:32")
        self.assertEqual(("called", "CG"), (r["confidence"], r["genotype"]))


class TestCopiesAreCountedOnlyAtTheLocus(unittest.TestCase):

    def test_the_other_strand_and_another_alt_are_unread(self):
        c = pgx._copies_at_locus
        self.assertEqual(1, c({"genotype": "CT", "ref": "C", "confidence": "called"}, "T"))
        self.assertEqual(0, c({"genotype": "CC", "ref": "C", "confidence": "called"}, "T"))
        self.assertIsNone(c({"genotype": "CG", "ref": "C", "confidence": "called"}, "T"))
        self.assertIsNone(c({"genotype": "AA", "ref": "C", "confidence": "called"}, "T"))
        self.assertIsNone(c({"genotype": "CT", "confidence": "called_array_ambiguous"}, "T"))


class TestPresumedOnlyOnAWholeGenome(unittest.TestCase):

    LOCI = {"loci": {"rs1": {"gene": "G1", "chrom": "1", "pos": 100, "ref": "A", "alt": "G"}}}
    NO_ROW = {"status": "ok", "result": {"genotype": "AA", "confidence": "assumed_ref"}}

    def test_an_exome_or_an_unclassified_file_does_not_presume(self):
        for prof in ("exome", None):
            with self.subTest(input=prof):
                with mock.patch("scholion.genome.lookup", lambda rs: self.NO_ROW), \
                        mock.patch.object(core, "loci", lambda: self.LOCI), \
                        mock.patch("scholion.engine.genomics.gene_coverage",
                                   lambda g, rows=None: {"state": "fine"}):
                    g = SP._genotype("rs1", "NC_000001.11:g.100A>G", "G1", "G",
                                     {"status": "ok", "input_profile": prof}, ("A", "G"),
                                     has_bam=False)
                self.assertNotIn("presumed", g)
                self.assertEqual("not_whole_genome", g["presumed_refused"])


def _vcf(directory: Path, contigs, samples=("S1",), rows=()) -> Path:
    p = directory / "t.vcf.gz"
    head = ["##fileformat=VCFv4.2"] + [f"##contig=<ID={c},length=1000000>" for c in contigs]
    head.append("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t" + "\t".join(samples))
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(head + list(rows)) + "\n")
    return p


class TestAContigTheFileDoesNotHold(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_contig_is_none_and_the_mitochondrion_has_two_names(self):
        p = _vcf(self.dir, ["chr1", "chrX", "chrM"])
        self.assertEqual("chr1", genome.contig_name(str(p), "1"))
        self.assertEqual("chrM", genome.contig_name(str(p), "MT"))
        self.assertIsNone(genome.contig_name(str(p), "Y"))

    def test_a_file_that_declares_nothing_claims_nothing(self):
        p = _vcf(self.dir, [])
        self.assertIsNotNone(genome.contig_name(str(p), "Y"))


class TestAMultiSampleContainerNeedsAChoice(unittest.TestCase):

    def test_two_samples_and_no_choice_is_refused(self):
        from scholion import tabular_genome
        with tempfile.TemporaryDirectory() as d:
            p = _vcf(Path(d), ["1"], samples=("MOTHER", "CHILD"),
                     rows=["1\t100\trs1\tA\tG\t50\tPASS\t.\tGT\t0/0\t0/1"])
            old = os.environ.pop("SCHOLION_GENOME_SAMPLE", None)
            try:
                r = tabular_genome._scan_container_vcf(str(p))
            finally:
                if old is not None:
                    os.environ["SCHOLION_GENOME_SAMPLE"] = old
        self.assertEqual({"ok": False, "reason": "several_samples"}, r)


class TestARegionIsNotAskedAcrossBuilds(unittest.TestCase):

    def test_grch38_coordinates_on_a_grch37_file_are_refused(self):
        from scholion import gene_region, genes
        loc = {"gene": "TESTGENE", "chrom": "1", "start": 10, "end": 90, "cds": [],
               "assembly": "GRCh38"}
        asked = []
        with mock.patch.object(genes, "resolve", lambda g, allow_network=True: loc), \
                mock.patch.object(genome, "available",
                                  lambda: {"ready": True, "assembly": "GRCh37"}), \
                mock.patch.object(genome, "vcf_path", lambda: Path("/nonexistent.vcf.gz")), \
                mock.patch.object(genome, "_query_region_range",
                                  lambda *a, **k: asked.append(a) or []):
            r = gene_region.report("TESTGENE", allow_network=False)
        self.assertEqual("assembly_mismatch", r["status"])
        self.assertEqual([], asked, "the region was queried in the wrong build")


if __name__ == "__main__":
    unittest.main()
