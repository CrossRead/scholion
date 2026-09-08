"""Task 127: a gene the curated catalogue does not hold must still be answered.

The regression this guards is not a crash. `genome --gene CASR` returned a clean,
confident sentence — «Gene CASR is not in the coordinate reference» — which is
true about `loci.json` and reads as though it were about the genome. The reads
were on the machine the whole time. A wrong answer shaped like a good one is the
class this whole file is about, so the assertions below are mostly about what the
report is FORBIDDEN to say, not about what it says.

Everything here runs on synthetic data built in a temporary folder: a three-exon
gene on an invented contig, a reference containing that contig, and rows handed
to the region reader directly. No part of it touches the owner's genome — that is
what `test_read_depth_matches_the_native_run.py` is for, and it skips itself when
the real files are absent.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import support

sys.path.insert(0, str(support.SRC))

from scholion import fastalite, gene_region, genes  # noqa: E402
from scholion import genome as genome_mod  # noqa: E402

#: A 120-base contig with a gene of two coding exons. The sequence is written so
#: that the coding sequence starts with ATG and ends with a stop, because a
#: translation that silently begins mid-codon would make every assertion below
#: pass for the wrong reason.
CDS_A = "ATGGCCTGTAAAGGG"          # M A C K G      (positions 21..35)
CDS_B = "CGCTTTGAATTTTAA"          # R F E F *      (positions 61..75)
CONTIG = ("N" * 20 + CDS_A + "N" * 25 + CDS_B + "N" * 45)

GFF3 = """##gff-version 3
chrT\ttest\tgene\t11\t90\t.\t+\t.\tID=gene:ENSGTEST;Name=TESTGENE;biotype=protein_coding
chrT\ttest\tmRNA\t11\t90\t.\t+\t.\tID=transcript:ENSTTEST;Parent=gene:ENSGTEST;tag=Ensembl_canonical
chrT\ttest\tCDS\t21\t35\t.\t+\t0\tID=CDS:ENSTTEST;Parent=transcript:ENSTTEST
chrT\ttest\tCDS\t61\t75\t.\t+\t0\tID=CDS:ENSTTEST;Parent=transcript:ENSTTEST
chrT\ttest\tgene\t200\t260\t.\t-\t.\tID=gene:ENSGOTHER;Name=OTHERGENE;biotype=protein_coding
"""


def _row(pos, ref, alt, gt="0/1", dp=30):
    """One VCF data line in the shape `_query_region_range` returns."""
    return ["chrT", str(pos), ".", ref, alt, "222", "PASS", f"DP={dp}",
            "GT:PL:DP:AD", f"{gt}:255,0,255:{dp}:{dp // 2},{dp - dp // 2}"]


class GeneOutsideTheCatalogue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "ann.gff3").write_text(GFF3, encoding="utf-8")
        fa = d / "ref.fa"
        # 60 bases per line, which is what the .fai below declares. The index and
        # the file have to agree or every fetch is off by the number of newlines.
        body = "\n".join(CONTIG[i:i + 60] for i in range(0, len(CONTIG), 60))
        fa.write_text(">chrT\n" + body + "\n", encoding="utf-8")
        header = len(">chrT\n")
        (d / "ref.fa.fai").write_text(f"chrT\t{len(CONTIG)}\t{header}\t60\t61\n",
                                      encoding="utf-8")
        self.dir = d
        self.env = {"SCHOLION_GENE_GFF3": str(d / "ann.gff3"),
                    "SCHOLION_GENOME_REFERENCE": str(fa),
                    "SCHOLION_CACHE_DIR": str(d / "cache")}
        self._old = {}
        import os
        for k, v in self.env.items():
            self._old[k] = os.environ.get(k)
            os.environ[k] = v
        self._old["SCHOLION_GENOME_BAM"] = os.environ.pop("SCHOLION_GENOME_BAM", None)

    def tearDown(self):
        import os
        for k, v in self._old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    # ---------------------------------------------------------------- resolution
    def test_the_gene_resolves_from_a_local_annotation_without_the_network(self):
        loc = genes.resolve("TESTGENE", allow_network=False)
        self.assertIsNotNone(loc, "a gene present in the annotation did not resolve")
        self.assertEqual((loc["chrom"], loc["start"], loc["end"], loc["strand"]),
                         ("chrT", 11, 90, "+"))
        self.assertEqual(loc["transcript"], "ENSTTEST")
        self.assertEqual([tuple(x) for x in loc["cds"]],
                         [("chrT", 21, 35), ("chrT", 61, 75)])
        self.assertEqual(loc["source"], "gff3")

    def test_the_gene_of_the_next_record_does_not_leak_into_this_one(self):
        """The scan stops at the next `gene` line; otherwise CDS bleed together."""
        loc = genes.resolve("TESTGENE", allow_network=False)
        self.assertTrue(all(b <= 90 for _, a, b in loc["cds"]))

    def test_an_unresolved_gene_names_what_was_read_and_what_would_fix_it(self):
        r = gene_region.report("NOSUCHGENE", allow_network=False)
        self.assertEqual(r["status"], "unresolved_gene")
        # The two situations are never merged: an annotation that was read and
        # does not hold the symbol points at the symbol; no annotation at all
        # points at the machine. They need opposite actions from the reader.
        self.assertTrue(r["consulted"], "the annotation that WAS read is not named")
        self.assertIn("NOSUCHGENE", r["message"])
        self.assertTrue(r["fix"])
        self.assertNotEqual(r["status"], "unknown_gene")

    def test_a_contig_named_with_and_without_chr_is_one_contig(self):
        self.assertEqual(genes.match_contig("chr3", ["1", "3", "X"]), "3")
        self.assertEqual(genes.match_contig("3", ["chr1", "chr3"]), "chr3")
        self.assertIsNone(genes.match_contig("chr3", ["chr1", "chr2"]))

    # ------------------------------------------------------------------- protein
    def test_a_coding_substitution_is_translated_from_the_local_reference(self):
        fa = fastalite.Fasta(self.dir / "ref.fa")
        cds = [("chrT", 21, 35), ("chrT", 61, 75)]
        seq, pos = fastalite.coding_sequence(fa, cds, "+")
        self.assertEqual(seq, CDS_A + CDS_B)
        self.assertEqual(fastalite.translate(seq), "MACKGRFEF*")
        # Third base of the first codon of exon two: CGC → CGA, both arginine.
        self.assertEqual(fastalite.protein_change(fa, cds, "+", 63, "C", "A")["kind"],
                         "synonymous")
        # First base of that codon: CGC → TGC, arginine to cysteine.
        self.assertEqual(fastalite.protein_change(fa, cds, "+", 61, "C", "T")["hgvs_p"],
                         "p.R6C")
        self.assertEqual(fastalite.protein_change(fa, cds, "+", 40, "N", "A")["kind"],
                         "not_coding")

    def test_a_reference_that_disagrees_with_the_vcf_is_reported_not_guessed(self):
        """Two builds talking past each other must stop the answer, not colour it."""
        fa = fastalite.Fasta(self.dir / "ref.fa")
        out = fastalite.protein_change(fa, [("chrT", 21, 35)], "+", 21, "T", "G")
        self.assertEqual(out["kind"], "reference_mismatch")
        self.assertEqual(out["reference_base"], "A")

    def test_an_indel_is_declined_rather_than_answered_wrongly(self):
        fa = fastalite.Fasta(self.dir / "ref.fa")
        out = fastalite.protein_change(fa, [("chrT", 21, 35)], "+", 21, "A", "AT")
        self.assertEqual(out["kind"], "not_substitution")

    # -------------------------------------------------------------------- report
    def _report(self, rows):
        """The report over synthetic rows, with the genome layer stood in for.

        Availability — which file, whose, which build — has its own tests and is
        not what is being checked here; standing it in keeps THIS test about the
        one thing it is for, and keeps it running on a machine with no genome at
        all rather than skipping there, which is where the regression would live.
        """
        saved = (genome_mod._query_region_range, genome_mod.available,
                 genome_mod.vcf_path)
        genome_mod._query_region_range = lambda *a, **k: rows
        genome_mod.available = lambda: {"ready": True}
        genome_mod.vcf_path = lambda: Path(self.dir / "nonexistent.vcf.gz")
        try:
            return gene_region.report("TESTGENE", allow_network=False)
        finally:
            (genome_mod._query_region_range, genome_mod.available,
             genome_mod.vcf_path) = saved

    @unittest.skipUnless(support.IN_SOURCE_REPO, "needs the source tree")
    def test_coding_and_non_coding_variants_are_told_apart(self):
        rows = [_row(15, "N", "A"), _row(61, "C", "T"), _row(63, "C", "A"),
                _row(80, "N", "G")]
        r = self._report(rows)
        self.assertEqual(r["variants"]["total"], 4)
        self.assertEqual(r["variants"]["coding"], 2)
        self.assertEqual(r["variants"]["consequential"], 1)   # R6C, not the silent one

    @unittest.skipUnless(support.IN_SOURCE_REPO, "needs the source tree")
    def test_without_an_alignment_the_answer_says_so_instead_of_implying_coverage(self):
        r = self._report([_row(61, "C", "T")])
        self.assertIsNone(r["coverage"]["source"])
        self.assertTrue(r["coverage"]["why"])
        self.assertTrue(any("BAM" in g["what"] or g.get("fix", "").startswith("SCHOLION_GENOME_BAM")
                            for g in r["gaps"]),
                        "an unmeasured region did not produce a gap")
        self.assertTrue(r["blind_spots"], "the blind spots of short reads are not stated")

    @unittest.skipUnless(support.IN_SOURCE_REPO, "needs the source tree")
    def test_an_uncomputed_consequence_is_never_reported_as_zero(self):
        """`changing the protein: 0` and `not computed` look alike and are opposite."""
        import os
        os.environ.pop("SCHOLION_GENOME_REFERENCE", None)
        r = self._report([_row(61, "C", "T")])
        os.environ["SCHOLION_GENOME_REFERENCE"] = self.env["SCHOLION_GENOME_REFERENCE"]
        self.assertIsNone(r["variants"]["consequential"])
        self.assertFalse(r["variants"]["consequence_computed"])


if __name__ == "__main__":
    unittest.main()
