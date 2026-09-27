"""A reader that failed never answers «reference».

An empty list of rows at a position is read as «no row here — the person
carries the reference», which is a sentence about a person. The single-pass
reader already raised `linear.Unreadable` instead of returning `[]`, and pysam
already answered `None` rather than `[]`. Two seeking readers still turned a
failure into that sentence:

- bcftools: an exception, a timeout on a large file included, returned `[]`;
  and a non-zero exit — «Could not load the index» — left stdout empty, which
  parsed into no rows and came out as `[]` all the same;
- the own tabix reader: any exception returned `[]`.

Both now raise, and the locus answer names the failure instead of assuming the
reference. Found by an external review on 25.09.2026.
"""
from __future__ import annotations

import subprocess
import unittest
from unittest import mock

import support  # noqa: F401  (puts src/ on the path)
from scholion import genome as g
from scholion import linear as lin

VCF = "/nonexistent/sample.vcf.gz"


class _SeekingReader(unittest.TestCase):
    """Pin `_query_region` onto the bcftools branch, whatever this machine has."""

    def setUp(self):
        self._patches = [
            mock.patch.object(g, "contig_name", return_value="chr1"),
            mock.patch.object(g, "engine_pin", return_value="auto"),
            mock.patch.object(g, "_index_usable", return_value=True),
            mock.patch.object(g, "_region_key", return_value=None),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()


class TestBcftoolsFailureIsNotAnEmptyPosition(_SeekingReader):

    def test_a_non_zero_exit_raises(self):
        done = subprocess.CompletedProcess([], 1, stdout="", stderr="[E::hts_idx_load3] Could not load the index")
        with mock.patch.object(g, "_have_bcftools", return_value=True), \
                mock.patch.object(g.subprocess, "run", return_value=done):
            with self.assertRaises(lin.Unreadable) as cm:
                g._query_region(VCF, "1", 12345)
        self.assertEqual("reader_failed", cm.exception.why)
        self.assertIn("Could not load the index", cm.exception.detail)

    def test_a_timeout_raises(self):
        with mock.patch.object(g, "_have_bcftools", return_value=True), \
                mock.patch.object(g.subprocess, "run", side_effect=subprocess.TimeoutExpired("bcftools", 60)):
            with self.assertRaises(lin.Unreadable):
                g._query_region(VCF, "1", 12345)

    def test_a_missing_binary_raises(self):
        with mock.patch.object(g, "_have_bcftools", return_value=True), \
                mock.patch.object(g.subprocess, "run", side_effect=FileNotFoundError("bcftools")):
            with self.assertRaises(lin.Unreadable):
                g._query_region(VCF, "1", 12345)

    def test_an_empty_answer_of_a_successful_run_is_still_the_reference(self):
        """The other side of the line: a clean run with no rows IS «no row here»."""
        done = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with mock.patch.object(g, "_have_bcftools", return_value=True), \
                mock.patch.object(g.subprocess, "run", return_value=done):
            self.assertEqual([], g._query_region(VCF, "1", 12345))


class TestTheOwnTabixReaderFailureIsNotAnEmptyPosition(_SeekingReader):

    def test_an_exception_raises(self):
        from scholion import tabixlite
        with mock.patch.object(g, "_have_bcftools", return_value=False), \
                mock.patch.object(g, "_query_pysam", return_value=None), \
                mock.patch.object(tabixlite, "query", side_effect=OSError("truncated block")):
            with self.assertRaises(lin.Unreadable) as cm:
                g._query_region(VCF, "1", 12345)
        self.assertEqual("reader_failed", cm.exception.why)


class TestTheOwnTabixReaderDoesNotSwallowItsOwnFailure(_SeekingReader):
    """The test above mocks `tabixlite.query` into raising. The real one did not
    raise: an index it could not load, and a block cut short, were caught inside
    it and answered `[]`, so the wrapper in `_query_region` was never reached."""

    def test_an_index_that_cannot_be_loaded_is_not_the_reference(self):
        with mock.patch.object(g, "_have_bcftools", return_value=False), \
                mock.patch.object(g, "_query_pysam", return_value=None):
            with self.assertRaises(lin.Unreadable) as cm:
                g._query_region(VCF, "1", 12345)
        self.assertEqual("reader_failed", cm.exception.why)

    def test_a_block_cut_short_is_not_the_reference(self):
        import gzip
        import os
        import tempfile
        from scholion import tabixlite
        with tempfile.TemporaryDirectory() as d:
            vcf = os.path.join(d, "cut.vcf.gz")
            body = ("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"
                    "chr1\t12345\trsX\tA\tG\t60\tPASS\t.\n").encode()
            data = gzip.compress(body)
            with open(vcf, "wb") as fh:
                fh.write(data[:-5])
            fake = mock.Mock()
            fake.voffset.return_value = 0
            with mock.patch.object(g, "_have_bcftools", return_value=False), \
                    mock.patch.object(g, "_query_pysam", return_value=None), \
                    mock.patch.object(tabixlite, "_index", return_value=fake):
                with self.assertRaises(lin.Unreadable) as cm:
                    g._query_region(vcf, "1", 12345)
        self.assertEqual("reader_failed", cm.exception.why)


class TestAFailedMeasurementIsNotAWholeGenome(unittest.TestCase):
    """`_callset_of` answered None when the measurement raised. None carries no
    class, no class is not a narrow input, and so ClinVar, the ACMG list and the
    scores opened — and `limits` printed the whole-genome sentence — over a file
    nobody measured."""

    def test_the_failure_is_unmeasured(self):
        from scholion import callset
        with mock.patch.object(callset, "measure", side_effect=OSError("boom")):
            cs = g._callset_of("/nonexistent/sample.vcf.gz")
        self.assertIsNotNone(cs)
        self.assertEqual("unmeasured", cs["class"])
        self.assertFalse(cs["measured"])
        self.assertIn("boom", cs["failed"])

    def test_unmeasured_closes_what_needs_breadth(self):
        paths = {p["path"]: p for p in g.answerable_paths("unmeasured", True, "bcftools")}
        for name in ("clinvar", "acmg", "pgs"):
            self.assertFalse(paths[name]["open"], name)
            self.assertEqual("input_too_narrow", paths[name]["why"], name)


class TestTheLocusAnswerNamesTheFailure(unittest.TestCase):

    def test_the_refusal_is_not_a_genotype(self):
        out = g._linear_refusal("reader_failed", "bcftools exit 1: Could not load the index")
        self.assertIsNone(out["genotype"])
        self.assertEqual("unreadable_file", out["confidence"])
        self.assertEqual("reader_failed", out["reason"])
        self.assertIn("Could not load the index", out["note"])
        self.assertNotIn("⟦", out["note"])

    def test_the_sentence_exists_in_both_languages(self):
        from scholion.i18n import en, ru
        for cat in (en.MESSAGES, ru.MESSAGES):
            self.assertIn("genome.unreadable_reader_failed", cat)
            self.assertIn("{detail}", cat["genome.unreadable_reader_failed"])


if __name__ == "__main__":
    unittest.main()
