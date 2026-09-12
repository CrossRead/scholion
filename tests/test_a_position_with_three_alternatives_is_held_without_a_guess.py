"""Three alternative alleles, and which one a paper meant is not in the source.

The catalogue holds one alternative nucleotide per position, and that is right
for comparing genotypes: the comparison reads one base from each side. But some
positions people actually study are three-allele — among the nine of the
deiodinase set, three come back from the source as `C>A/G/T` and `A>C/G/T`.
Until now they simply could not be entered, and a locus that cannot be entered is
a locus nobody is told about.

Guessing which of the three is «the studied one» would be writing down a number
nobody published. So the position is held WITHOUT an alternative: its coordinate
is a fact, the alleles observed there are a fact, and every reader refuses on it
by name — the coordinate is given, the observed set is named, no verdict is
offered. Comparing a genotype against a guessed allele is worse than not
comparing.

Never both shapes at once. An entry carrying an `alt` beside the observed set
would be compared against the chosen one while looking like it had refused to
choose, which is the most expensive of the three possible states.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import core, format as fmt, genome
from scholion.i18n import en, ru

ROOT = Path(support.__file__).resolve().parents[1]


def _uc():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "update_catalog_167", ROOT / "src" / "ingest" / "update_catalog.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


UC = _uc()
HELD = {"rsid": "rs1", "gene": "GX", "chrom": "14", "pos": 100,
        "ref": "C", "alleles_observed": ["C", "A", "G", "T"]}


class TestTheReaderRefusesBeforeItReads(unittest.TestCase):

    def test_it_refuses_and_names_why(self):
        res = genome._gt_at(dict(HELD))
        self.assertEqual("multiallelic", res["confidence"])
        self.assertNotIn("genotype", res)

    def test_the_refusal_carries_the_observed_alleles(self):
        self.assertIn("C/A/G/T", genome._gt_at(dict(HELD))["note"])

    def test_nothing_is_read_at_all(self):
        """The refusal stands before the file is opened: there is nothing to
        compare, whatever the file holds."""
        with mock.patch.object(genome, "vcf_path",
                               side_effect=AssertionError("the file was opened")):
            genome._gt_at(dict(HELD))

    def test_an_ordinary_locus_is_untouched(self):
        with mock.patch.object(genome, "vcf_path", return_value=None), \
             mock.patch("scholion.array_genome.status", return_value={"status": "no_array"}), \
             mock.patch("scholion.tabular_genome.status", return_value={"status": "no_tabular"}):
            res = genome._gt_at({"rsid": "rs2", "chrom": "1", "pos": 1,
                                 "ref": "A", "alt": "G"})
        self.assertNotEqual("multiallelic", (res or {}).get("confidence"))

    def test_an_entry_that_somehow_has_both_is_read_as_a_pair(self):
        """The invariant forbids it; if one ever appears, the `alt` is what the
        comparison would use, so the reader must not pretend to have refused."""
        res = genome._gt_at({**HELD, "alt": "A"})
        self.assertNotEqual("multiallelic", (res or {}).get("confidence"))


class TestTheAnswerSaysItOnTheScreen(unittest.TestCase):

    def test_the_line_is_a_refusal_and_not_a_genotype(self):
        out = fmt.genome_report({"status": "ok", "rsid": "rs1", "gene": "GX",
                                 "chrom": "14", "pos": 100, "locus": dict(HELD),
                                 "result": genome._gt_at(dict(HELD)), "disclaimer": "—"})
        self.assertIn("rs1", out)
        self.assertNotIn("⟦", out)
        self.assertNotIn("genotype **", out)

    def test_both_languages_carry_the_phrases(self):
        for key in ("genome.refused_head.multiallelic", "genome.refused.multiallelic"):
            for cat, lang in ((en.MESSAGES, "en"), (ru.MESSAGES, "ru")):
                with self.subTest(key=key, lang=lang):
                    self.assertIn(key, cat)


class TestTheInvariantAcceptsExactlyTwoShapes(unittest.TestCase):

    def test_a_pair_passes(self):
        self.assertEqual([], UC.invariant_problems(
            {"loci": {"rs1": {"ref": "A", "alt": "G"}}}))

    def test_a_held_position_passes(self):
        self.assertEqual([], UC.invariant_problems(
            {"loci": {"rs1": {"ref": "C", "alleles_observed": ["C", "A", "G"]}}}))

    def test_both_at_once_is_refused(self):
        problems = UC.invariant_problems(
            {"loci": {"rs1": {"ref": "C", "alt": "A", "alleles_observed": ["C", "A", "G"]}}})
        self.assertEqual(1, len(problems))
        self.assertIn("both", problems[0])

    def test_a_two_allele_observed_set_is_refused(self):
        """Two alleles are a pair and belong in `ref`/`alt`; carrying them as an
        observed set would be a refusal where an answer is possible."""
        self.assertTrue(UC.invariant_problems(
            {"loci": {"rs1": {"ref": "C", "alleles_observed": ["C", "A"]}}}))

    def test_a_missing_reference_base_is_still_refused(self):
        self.assertTrue(UC.invariant_problems(
            {"loci": {"rs1": {"alleles_observed": ["C", "A", "G"]}}}))

    def test_the_shipped_catalogue_still_satisfies_it(self):
        cat = json.loads((ROOT / "src" / "scholion" / "knowledge" / "loci.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual([], UC.invariant_problems(cat))


class TestTheUpdateToolEntersSuchAPosition(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _add(self, answer):
        path = self.tmp / "loci.json"
        path.write_text(json.dumps({"loci": {}}), encoding="utf-8")
        with mock.patch.object(UC, "LOCI", path), \
             mock.patch.object(UC, "fetch", lambda rs: answer), \
             mock.patch.object(UC.time, "sleep", lambda *_: None), \
             mock.patch.object(sys, "argv", ["update_catalog.py", "--add", "rs9"]):
            code = UC.main()
        return code, json.loads(path.read_text(encoding="utf-8"))

    def test_it_is_entered_with_the_observed_set_and_no_alt(self):
        code, out = self._add({"chrom": "14", "pos": 100,
                               "alleles": ["C", "A", "G", "T"],
                               "clinical_significance": [],
                               "consequence": "intron_variant"})
        self.assertEqual(0, code)
        entry = out["loci"]["rs9"]
        self.assertEqual(["C", "A", "G", "T"], entry["alleles_observed"])
        self.assertNotIn("alt", entry)
        self.assertEqual("C", entry["ref"])

    def test_the_locus_the_reader_then_meets_is_the_refusal(self):
        _, out = self._add({"chrom": "14", "pos": 100,
                            "alleles": ["C", "A", "G", "T"],
                            "clinical_significance": [], "consequence": "x"})
        res = genome._gt_at({"rsid": "rs9", **out["loci"]["rs9"]})
        self.assertEqual("multiallelic", res["confidence"])

    def test_a_two_allele_position_is_still_entered_as_a_pair(self):
        _, out = self._add({"chrom": "1", "pos": 1, "alleles": ["A", "G"],
                            "clinical_significance": [], "consequence": "x"})
        self.assertEqual("G", out["loci"]["rs9"]["alt"])
        self.assertNotIn("alleles_observed", out["loci"]["rs9"])


if __name__ == "__main__":
    unittest.main()
