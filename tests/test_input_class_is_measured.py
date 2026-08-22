"""What kind of input this is, measured — and what may be claimed from it.

Task 87. The input had two classes, `array` and `sequenced`, and every readable
VCF was described to the reader as «a whole genome — every base the sequencing
reached, so both single variants and polygenic scores are computable». Run over
a corpus of real third-party files that sentence was printed above seven inputs
and was false for all seven: an imputed call set, two genotyping chips shipped
as VCF, a low-pass screen, and two DRAGEN call sets holding indels and not one
substitution.

The sharpest consequence is here as an end-to-end case: on an indel-only file
the catalogue's SNVs used to come back as «TT (reference)», which is a statement
about the person derived from a property of the file.

Tasks 64 and 83 travel with it, because all three are the same sentence-level
failure: a report that says more than the data supports. The renderer is checked
directly for those two — they are claims made in text, and text is where they
have to be refused.
"""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholion import callset, format as fmt, genome  # noqa: E402


def bgzf(data: bytes) -> bytes:
    """One BGZF member, written by hand so no htslib is needed to run this."""
    comp = zlib.compressobj(6, zlib.DEFLATED, -15)
    body = comp.compress(data) + comp.flush()
    extra = b"BC" + struct.pack("<H", 2) + struct.pack("<H", len(body) + 25)
    head = b"\x1f\x8b\x08\x04" + b"\0" * 6 + struct.pack("<H", len(extra)) + extra
    return head + body + struct.pack("<II", zlib.crc32(data) & 0xFFFFFFFF, len(data))


def _indel_only_vcf(rows: int = 1500) -> bytes:
    head = ("##fileformat=VCFv4.2\n"
            "##contig=<ID=1,length=249250621>\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tME\n")
    body = "".join(
        f"1\t{100000 + i * 97}\t.\tCTT\tC\t50\tPASS\t.\tGT\t0/1\n" for i in range(rows))
    return (head + body).encode()


class TestPartialCallSet(unittest.TestCase):
    """A file that holds no substitutions cannot answer for one."""

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("SCHOLION_GENOME_DIR", "SCHOLION_GENOME_VCF")}
        for k in self._env:
            os.environ.pop(k, None)
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "genome.vcf.gz").write_bytes(bgzf(_indel_only_vcf()))
        (self.dir / "genome.vcf.gz.tbi").write_bytes(b"\x1f\x8b")
        os.environ["SCHOLION_GENOME_DIR"] = str(self.dir)

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_the_composition_is_measured_not_assumed(self):
        m = callset.measure(str(self.dir / "genome.vcf.gz"))
        self.assertTrue(m["only_indels"], m)
        self.assertEqual(0, m["snv"])
        self.assertEqual("partial_callset_indels", m["class"])

    def test_a_substitution_is_refused_and_not_called_reference(self):
        self.assertFalse(callset.answers_variant(
            {"only_indels": True}, "T", "C"))
        self.assertTrue(callset.answers_variant(
            {"only_indels": True}, "CTT", "C"))
        report = genome.lookup(rsid="rs429358")
        res = report.get("result") or {}
        text = fmt.genome_report(report)
        if res:
            self.assertNotEqual("assumed_ref", res.get("confidence"), text)
        self.assertNotIn("⟦", text)


class TestTheReportClaimsOnlyWhatWasMeasured(unittest.TestCase):
    """Task 87 in the renderer, plus tasks 64 and 83."""

    def test_an_imputed_genotype_is_not_called_observed(self):
        out = fmt.genome_report({
            "status": "ok", "rsid": "rs1801133", "gene": "MTHFR",
            "chrom": "1", "pos": 11796321,
            "result": {"genotype": "GA", "confidence": "called", "imputed": True,
                       "assembly": "GRCh38", "read_pos": 11796321,
                       "note": "imputed"}})
        self.assertIn("imputed", out.lower())
        self.assertNotIn("called from the VCF", out)

    def test_a_filtered_row_says_the_caller_flagged_it(self):
        out = fmt.genome_report({
            "status": "ok", "rsid": "rs1801133", "gene": "MTHFR",
            "chrom": "1", "pos": 11796321,
            "result": {"genotype": "GA", "confidence": "called",
                       "filtered": "LowQual", "assembly": "GRCh38",
                       "read_pos": 11796321}})
        self.assertIn("LowQual", out)

    def test_an_array_is_never_reported_as_a_connected_genome(self):
        # Task 64. «**Genome connected.** File: None» — two false statements in
        # eight words — was printed to every one of the twelve array owners in
        # the reference corpus. The path to the array was in the JSON all along.
        out = fmt.genome_status_report({
            "ready": True, "input_class": "array", "vcf": None,
            "array": {"vendor": "23andMe", "markers": 601885,
                      "path": "/somewhere/genome_Full.txt"}})
        self.assertNotIn("File: None", out)
        self.assertNotIn("Genome connected", out)
        self.assertIn("23andMe", out)
        self.assertIn("genome_Full.txt", out)

    def test_the_answer_names_the_coordinate_set_it_was_read_in(self):
        # Task 83, last acceptance item. A GRCh37 file is read at GRCh37
        # positions; printing the catalogue's GRCh38 number sends the reader to
        # a base that is not the one that answered.
        out = fmt.genome_report({
            "status": "ok", "rsid": "rs429358", "gene": "APOE",
            "chrom": "19", "pos": 44908684,
            "result": {"genotype": "TC", "confidence": "called",
                       "assembly": "GRCh37", "read_pos": 45411941}})
        self.assertIn("GRCh37", out)
        self.assertIn("45411941", out)

    def test_a_refusal_names_the_coordinate_set_too(self):
        out = fmt.genome_report({
            "status": "ok", "rsid": "rs429358", "gene": "APOE",
            "chrom": "19", "pos": 44908684,
            "result": {"genotype": None, "confidence": "no_call_in_vcf",
                       "assembly": "GRCh37", "read_pos": 45411941,
                       "note": "no call"}})
        self.assertIn("GRCh37", out)
        self.assertIn("45411941", out)
        self.assertNotIn("⟦", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
