"""`7` and `chr7` are one contig, and the alignment's own header says which it is.

The coordinate layer names a chromosome without a prefix. An alignment against a
UCSC or GATK reference names it with one. The depth reader looked the name up
exactly, missed, and every gene on such a file was answered «coverage not
measured — the alignment carries no contig 7»: a defect of the lookup, printed
as a fact about the person's file, on the commonest kind of reference there is.

The calibration against the native run could not see it — it pins the arithmetic
on a file whose spelling already agreed. So the alignments here are written in
BOTH spellings, byte by byte, and the same reads must give the same depth
whichever name they are asked by.
"""
from __future__ import annotations

import gzip
import shutil
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401
from scholion import bamlite, gene_region
from scholion.engine import genomics


def write_alignment(path: Path, contigs, reads) -> None:
    """A BAM and its .bai, small enough to read in a test and real enough to parse.

    `contigs` is [(name, length)], `reads` is [(contig index, 0-based start, length)].
    One compressed block holds everything, and one index chunk per contig points
    at the first record — the reader filters by contig and by position itself.
    """
    text = "".join(f"@SQ\tSN:{n}\tLN:{l}\n" for n, l in contigs).encode()
    head = b"BAM\x01" + struct.pack("<i", len(text)) + text + struct.pack("<i", len(contigs))
    for name, length in contigs:
        raw = name.encode() + b"\x00"
        head += struct.pack("<i", len(raw)) + raw + struct.pack("<i", length)
    body = b""
    for ref, pos, length in sorted(reads):
        name = b"r\x00"
        rec = struct.pack("<iiBBHHHiiii", ref, pos, len(name), 60, 4680, 1, 0, length, -1, -1, 0)
        rec += name + struct.pack("<I", length << 4) + b"\x11" * ((length + 1) // 2) + b"\x28" * length
        body += struct.pack("<i", len(rec)) + rec
    packed = gzip.compress(head + body)
    path.write_bytes(packed)
    chunk = struct.pack("<QQ", len(head), len(packed) << 16)
    index = b"BAI\x01" + struct.pack("<i", len(contigs))
    for _ in contigs:
        index += struct.pack("<i", 1) + struct.pack("<Ii", 0, 1) + chunk + struct.pack("<i", 0)
    Path(str(path) + ".bai").write_bytes(index)


READS = [(1, 100, 50), (1, 120, 50), (2, 10, 20)]


class TestTheSameReadsGiveTheSameDepthUnderEitherName(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.prefixed = self.tmp / "prefixed.bam"
        self.bare = self.tmp / "bare.bam"
        write_alignment(self.prefixed, [("chr1", 1000), ("chr7", 1000), ("chrM", 500)], READS)
        write_alignment(self.bare, [("1", 1000), ("7", 1000), ("MT", 500)], READS)

    def test_the_fixture_is_an_alignment_the_reader_reads(self):
        self.assertEqual({"chr1": 0, "chr7": 1, "chrM": 2}, bamlite.references(self.prefixed))
        cov = bamlite.depth(self.prefixed, "chr7", 101, 170)
        self.assertEqual([1] * 20 + [2] * 30 + [1] * 20, cov)

    def test_a_bare_name_is_found_in_a_prefixed_header(self):
        self.assertEqual(bamlite.depth(self.prefixed, "chr7", 95, 175),
                         bamlite.depth(self.prefixed, "7", 95, 175))

    def test_a_prefixed_name_is_found_in_a_bare_header(self):
        self.assertEqual(bamlite.depth(self.bare, "7", 95, 175),
                         bamlite.depth(self.bare, "chr7", 95, 175))

    def test_the_two_files_agree(self):
        self.assertEqual(bamlite.depth(self.bare, "7", 95, 175),
                         bamlite.depth(self.prefixed, "7", 95, 175))
        self.assertEqual(2, max(bamlite.depth(self.prefixed, "7", 95, 175)))

    def test_the_mitochondrion_is_found_under_each_of_its_names(self):
        want = [1] * 20
        for bam in (self.prefixed, self.bare):
            for asked in ("MT", "M", "chrM", "chrMT"):
                with self.subTest(file=bam.name, asked=asked):
                    self.assertEqual(want, bamlite.depth(bam, asked, 11, 30))

    def test_a_contig_the_file_does_not_hold_is_still_a_refusal(self):
        for bam in (self.prefixed, self.bare):
            with self.subTest(file=bam.name):
                with self.assertRaises(KeyError):
                    bamlite.depth(bam, "Y", 1, 10)

    def test_one_name_is_never_taken_for_another(self):
        """`1` must not find `chr11`, and `7` must not find `chr17`."""
        other = self.tmp / "other.bam"
        write_alignment(other, [("chr11", 1000), ("chr17", 1000)], [(0, 100, 50)])
        for asked in ("1", "7", "chr1", "chr7"):
            with self.subTest(asked=asked):
                with self.assertRaises(KeyError):
                    bamlite.depth(other, asked, 101, 110)


class TestTheGeneAnswerCarriesWhatTheAlignmentSaid(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bam = self.tmp / "sample.bam"
        write_alignment(self.bam, [("chr1", 1000), ("chr7", 1000)], READS[:2])

    def test_the_gene_region_reader_measures_a_prefixed_file(self):
        with mock.patch.object(gene_region, "bam_path", return_value=self.bam):
            cov = gene_region._coverage("7", 101, 170, [["7", 121, 150]])
        self.assertEqual("bam", cov["source"], cov)
        self.assertEqual(70, cov["gene"]["bases"])
        self.assertEqual(1, cov["gene"]["min"])
        self.assertEqual(2, cov["cds"]["min"])

    def test_a_missing_contig_is_said_once_the_header_was_asked_both_ways(self):
        with mock.patch.object(gene_region, "bam_path", return_value=self.bam):
            cov = gene_region._coverage("Y", 1, 10, [])
        self.assertIsNone(cov["source"])
        self.assertTrue(cov["why"])

    def test_the_lookup_does_not_write_the_table_over_the_measurement(self):
        from scholion import genome
        measured = {"source": "bam", "file": str(self.bam), "min_mapq": 20,
                    "gene": bamlite.summarise([30] * 10, gene_region.THRESHOLDS)}
        answer = {"status": "ok", "gene": "ABCB4", "coverage": dict(measured)}
        with mock.patch.object(genome, "lookup", return_value=answer):
            r = genomics.genome_lookup(gene="ABCB4")
        self.assertEqual(measured, r["coverage"])

    def test_a_named_absence_is_not_written_over_either(self):
        from scholion import genome
        absent = {"source": None, "why": "no alignment file is declared", "fix": ""}
        answer = {"status": "ok", "gene": "ABCB4", "coverage": dict(absent)}
        with mock.patch.object(genome, "lookup", return_value=answer):
            r = genomics.genome_lookup(gene="ABCB4")
        self.assertEqual(absent, r["coverage"])

    def test_the_printed_answer_carries_the_numbers(self):
        from scholion import format as _f  # noqa: F401  (the facade loads the screens)
        from scholion import format_genome as FG
        from scholion import genome
        measured = {"source": "bam", "file": str(self.bam), "min_mapq": 20,
                    "gene": bamlite.summarise([36] * 10, gene_region.THRESHOLDS)}
        loc = {"gene": "ABCB4", "chrom": "7", "start": 1, "end": 10, "strand": "-",
               "assembly": "GRCh38"}
        answer = {"status": "ok", "gene": "ABCB4", "location": loc, "coverage": measured,
                  "variants": [], "counts": {"total": 0, "coding": 0, "consequential": 0}}
        with mock.patch.object(genome, "lookup", return_value=answer):
            r = genomics.genome_lookup(gene="ABCB4")
        out = FG._gene_region_report(r)
        self.assertIn("36", out)
        self.assertNotIn(FG._t("gene.coverage_not_computed"), out)

    def test_a_locus_still_gets_the_tables_answer(self):
        from scholion import genome
        with mock.patch.object(genome, "lookup", return_value={"status": "ok", "gene": "MTHFR",
                                                                "rsid": "rs1801133"}):
            r = genomics.genome_lookup(rsid="rs1801133")
        self.assertIn("state", r["coverage"])


if __name__ == "__main__":
    unittest.main()
