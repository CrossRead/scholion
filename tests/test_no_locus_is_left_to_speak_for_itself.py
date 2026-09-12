"""A genotype printed with nothing beside it is read as meaning something.

Two ways that happened. A locus could carry no curated note and belong to a gene
with no guideline table and no verdict — and then the answer was a genotype and a
full stop. And a locus that did carry the sentence that mattered lost it to the
one-line cut a gene listing makes: UGT1A1's note says the variant read here is the
minor one for most readers and that the main one is not a SNP at all, so it cannot
be read from this kind of file. A physician asking «do I have Gilbert's» met the
genotype and not the sentence.

Both are the same shape. Where the product stops talking, whoever is talking to
the reader carries on — and what they supply is not from this build, not from its
catalogue, and not filtered by any of its rules. It happened once already, on a
locus this build does not interpret, and the reader was given a confident reading
of it out of an assistant's general knowledge.

So: every locus resolves to exactly one of five bases, the two that license
nothing say so out loud, and a caveat is printed where the reader is, not only
where the data model finds it convenient.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import core, format as fmt
from scholion.engine import genomics as G


class TestEveryLocusStandsOnSomething(unittest.TestCase):

    def test_every_locus_in_the_catalogue_resolves_to_one_named_basis(self):
        for rsid, entry in (core.loci().get("loci") or {}).items():
            with self.subTest(rsid=rsid, gene=entry.get("gene")):
                b = G.locus_basis(rsid)
                self.assertIn(b["kind"], G.BASIS_ORDER)
                self.assertEqual(entry.get("gene", "").upper(), b["gene"])

    def test_the_catalogue_walked_is_not_empty(self):
        """An enumeration that walks nothing passes exactly like a clean one."""
        self.assertGreater(len(core.loci().get("loci") or {}), 40)

    def test_a_verdict_outranks_a_phenotype_model(self):
        """MTHFR carries both, and the model is the thing the verdict exists to
        say must not be used for dosing. Deciding by order of the files instead
        would print an activity phenotype under a sentence forbidding it."""
        self.assertEqual("verdict", G.locus_basis("rs1801133")["kind"])

    def test_a_locus_with_a_note_is_a_note_and_not_a_guess_about_its_text(self):
        self.assertEqual("note", G.locus_basis("rs4148323")["kind"])

    def test_a_locus_standing_on_nothing_is_found_by_the_enumeration(self):
        book = dict(core.loci().get("loci") or {})
        book["rs00000000"] = {"gene": "NOTHINGATALL", "chrom": "1", "pos": 1,
                              "ref": "A", "alt": "G"}
        with mock.patch.object(core, "loci", lambda: {"loci": book}):
            self.assertEqual("none", G.locus_basis("rs00000000")["kind"])

    def test_a_gene_known_as_a_pair_but_without_a_table_is_its_own_state(self):
        """Not «no rule» and not «here is the rule»: the pair is recognised and
        this build holds no table for it, which is a fact about the build."""
        book = {"rsX": {"gene": "ABCG2", "chrom": "4", "pos": 1, "ref": "A", "alt": "G"}}
        with mock.patch.object(core, "loci", lambda: {"loci": book}):
            self.assertEqual("pair", G.locus_basis("rsX")["kind"])


class TestTheOnesThatLicenseNothingSaySo(unittest.TestCase):

    def test_a_baseless_locus_prints_a_named_refusal(self):
        lines = fmt._locus_basis_lines({"basis": {"kind": "none", "gene": "X"}})
        self.assertTrue(lines)
        self.assertNotIn("{", lines[0], "a phrase placeholder reached the reader")

    def test_a_recognised_pair_with_no_table_names_the_gene(self):
        lines = fmt._locus_basis_lines({"basis": {"kind": "pair", "gene": "ABCG2"}})
        self.assertTrue(lines)
        self.assertIn("ABCG2", lines[0])

    def test_the_three_bases_that_carry_their_own_words_add_nothing(self):
        for kind in ("verdict", "note", "guideline"):
            with self.subTest(kind=kind):
                self.assertEqual([], fmt._locus_basis_lines({"basis": {"kind": kind}}))

    def test_the_refusal_reaches_the_single_locus_answer(self):
        r = {"status": "ok", "rsid": "rs00000000", "gene": "NOTHINGATALL",
             "chrom": "1", "pos": 1, "result": {"genotype": "AG", "confidence": "called"},
             "basis": {"kind": "none", "gene": "NOTHINGATALL"}, "disclaimer": "—"}
        out = fmt.genome_report(r)
        self.assertIn(fmt._locus_basis_lines(r)[0].strip("_"), out)


class TestACaveatSurvivesTheCutAGeneListingMakes(unittest.TestCase):

    NOTE = "the main European variant is not a SNP and cannot be read from this file"

    def _listing(self):
        item = {"status": "ok", "rsid": "rs4148323", "gene": "UGT1A1", "chrom": "2",
                "pos": 1, "result": {"genotype": "GG", "confidence": "called"},
                "note": self.NOTE, "basis": {"kind": "note", "gene": "UGT1A1"},
                "disclaimer": "—"}
        return fmt.genome_report({"gene": "UGT1A1", "loci": [item], "disclaimer": "—"}), item

    def test_the_note_is_in_the_listing(self):
        out, _ = self._listing()
        self.assertIn(self.NOTE, out,
                      "the sentence that decides the answer was cut off with the second line")

    def test_and_it_was_not_on_the_line_the_listing_keeps(self):
        """Proof that the previous assertion is about the repair and not about
        the note having been on the first line all along."""
        _, item = self._listing()
        self.assertNotIn(self.NOTE, fmt.genome_report(item).split("\n")[0])

    def test_a_note_about_this_particular_read_survives_too(self):
        item = {"status": "ok", "rsid": "rs4149056", "gene": "SLCO1B1", "chrom": "12",
                "pos": 1, "result": {"genotype": "TC", "confidence": "called",
                                     "note": "depth is low (4 reads)"},
                "basis": {"kind": "note", "gene": "SLCO1B1"}, "disclaimer": "—"}
        out = fmt.genome_report({"gene": "SLCO1B1", "loci": [item], "disclaimer": "—"})
        self.assertIn("4 reads", out)

    def test_a_locus_with_nothing_to_add_adds_nothing(self):
        item = {"status": "ok", "rsid": "rs1", "gene": "CYP2C19", "chrom": "10",
                "pos": 1, "result": {"genotype": "GG", "confidence": "called"},
                "basis": {"kind": "guideline", "gene": "CYP2C19"}, "disclaimer": "—"}
        self.assertEqual([], fmt._locus_qualifier_lines(item))


if __name__ == "__main__":
    unittest.main()
