"""A reason that did not substitute, and an annotation that was beside the data all along.

Two small things in one answer, both found on a question about the deiodinases.

The coverage line printed «coverage not measured — » and stopped. The whole value
of that line is the reason: no alignment file, no index, the gene outside the
coverage table — three different states needing three different actions. Printed
empty it reads as text that broke off, and the reader cannot tell which of the
three it was, or whether the render itself failed.

And the annotation search looked in two declared places, neither of which was
where the file actually sat, while the live source was unreachable in the same
moment — both roads closed at once. The file was in the working folder beside the
alignment the profile had already been told about. A search that knows where the
BAM is and does not look next to it sends a reader to set a variable for a file
one directory away.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import format as fmt, genes
from scholion.i18n import en, ru


def _report(cov):
    return fmt._gene_region_report(
        {"gene": "X", "location": {"chrom": "1", "start": 1, "end": 2,
                                   "strand": 1, "assembly": "GRCh38"},
         "coverage": cov, "variants": {}})


def _coverage_line(cov):
    marker = en.MESSAGES["gene.coverage_missing"].split("{")[0].strip()
    ru_marker = ru.MESSAGES["gene.coverage_missing"].split("{")[0].strip()
    for line in _report(cov).split("\n"):
        if marker in line or ru_marker in line:
            return line
    return ""


class TestTheReasonIsNeverEmpty(unittest.TestCase):

    SHAPES = [{}, {"source": None}, {"source": None, "why": ""},
              {"source": None, "why": "   "}, {"source": "chip"}]

    def test_no_shape_produces_a_line_that_breaks_off(self):
        for cov in self.SHAPES:
            with self.subTest(cov=cov):
                line = _coverage_line(cov)
                self.assertTrue(line, "the line vanished instead of saying anything")
                tail = line.rstrip()
                self.assertFalse(tail.endswith(("—", "-", ":")), tail)
                self.assertNotIn("{why}", tail)

    def test_a_real_reason_is_printed_as_given(self):
        self.assertIn("no alignment file",
                      _coverage_line({"source": None, "why": "no alignment file"}))

    def test_the_stand_in_says_that_nothing_said_why(self):
        line = _coverage_line({})
        self.assertTrue(line.strip())
        self.assertNotEqual(line.strip(), en.MESSAGES["gene.coverage_missing"].strip())

    def test_the_phrase_exists_in_both_languages(self):
        for cat, lang in ((en.MESSAGES, "en"), (ru.MESSAGES, "ru")):
            with self.subTest(lang=lang):
                self.assertIn("gene.coverage_not_computed", cat)


class TestTheSearchLooksWhereTheDataIs(unittest.TestCase):

    def test_the_folder_beside_the_alignment_is_searched(self):
        bam = Path("/somewhere/genomic_work/align/sample.bam")
        with mock.patch("scholion.gene_region.bam_path", lambda: bam):
            roots = [str(p) for p in genes.gff3_search_roots()]
        self.assertIn(str(bam.parent), roots)
        self.assertIn(str(bam.parent / "csq"), roots)
        self.assertIn(str(bam.parent.parent / "csq"), roots,
                      "the sibling folder the annotation actually lives in")

    def test_the_home_working_folder_is_searched(self):
        roots = [str(p) for p in genes.gff3_search_roots()]
        self.assertIn(str(Path.home() / "genomic_work" / "csq"), roots)
        self.assertIn(str(Path.home() / "genomic_work"), roots)

    def test_no_alignment_leaves_the_declared_list_alone(self):
        with mock.patch("scholion.gene_region.bam_path", lambda: None):
            roots = [str(p) for p in genes.gff3_search_roots()]
        self.assertTrue(roots)
        self.assertNotIn("", roots)

    def test_a_failure_to_find_the_alignment_does_not_break_the_search(self):
        """The search is a fallback path; an exception reaching it would take out
        every gene question at once."""
        with mock.patch("scholion.gene_region.bam_path", side_effect=RuntimeError("x")):
            self.assertTrue(genes.gff3_search_roots())

    def test_the_roots_are_unique(self):
        roots = [str(p) for p in genes.gff3_search_roots()]
        self.assertEqual(len(roots), len(set(roots)))

    def test_an_explicit_variable_still_switches_the_search_off(self):
        """A test pointed at a small fixture must not silently reach a real
        annotation — adding roots must not weaken that."""
        with mock.patch.dict("os.environ", {"SCHOLION_GENE_GFF3": "/no/such/file.gff3.gz"}):
            self.assertEqual([], genes.gff3_candidates())


if __name__ == "__main__":
    unittest.main()
