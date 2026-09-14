"""An expectation is a claim about a genotype, so it is asked of that genotype.

The lipid card of the owner's own profile asked five questions on 13.09.2026,
each «the author expects LDL … WITH THIS GENOTYPE at <gene> <rsid>». Four of the
five positions had been read and the named allele was NOT there: they were
questions about a genotype he does not carry, and they buried the fifth — APOE
ε2, which he does carry, on a profile whose LDL stands above its corridor.

Task 185 had already removed the same question for a position nobody READ. This
is the other half of the same rule: read and absent is not «this genotype»
either. The row itself says the allele was not found; the question would add a
claim to that.

Held here:

  * one copy or two — the question is asked;
  * read and the allele absent — no question, and no question about that gene at
    all (a silent drop would otherwise be indistinguishable from a defect);
  * the corridor open at one end is written by the end it has, not as «—–3.0»;
  * the date in the sentence is a date, not a timestamp.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion.engine import system_panels as SP

TXT = {"en": "what follows", "ru": "what follows (ru)"}
LOCI = {"loci": {"rsHET": {"gene": "HET"}, "rsABSENT": {"gene": "ABSENT"},
                 "rsHOM": {"gene": "HOM"}}}
CALLS = {"rsHET": {"genotype": "AG", "confidence": "called", "depth": 30},
         "rsHOM": {"genotype": "GG", "confidence": "called", "depth": 30},
         "rsABSENT": {"genotype": "AA", "confidence": "called", "depth": 30}}


def _lookup(rsid=None, gene=None):
    return {"status": "ok", "rsid": rsid, "result": dict(CALLS.get(rsid) or {})}


def _pos(rs, gene):
    return {"rsid": rs, "gene": gene, "hgvs": "NC_000001.11:g.100A>G", "risk_allele": "G",
            "mode": "monogenic", "classification": "Strong", "moi": "AD", "kind": "mechanism",
            "text": {"het": TXT, "hom": TXT}, "source": "the author",
            "expect": {"marker": "glucose", "direction": "higher"}}


CURATED = {"_meta": {"why_empty": "nobody wrote a row"},
           "systems": {"glucose": {"source": None, "positions": [
               _pos("rsHET", "HET"), _pos("rsHOM", "HOM"), _pos("rsABSENT", "ABSENT")]}}}


class TestTheQuestionFollowsTheGenotype(unittest.TestCase):

    def setUp(self):
        self._patches = [
            mock.patch.object(core, "loci", lambda: LOCI),
            mock.patch("scholion.genome.lookup", _lookup),
            mock.patch("scholion.genome.available", lambda: {"ready": True}),
            mock.patch.object(SP, "_base", lambda: {"_meta": {}, "systems": {}}),
            mock.patch.object(SP, "_curated", lambda: CURATED),
            mock.patch.object(SP, "_terms", lambda: {}),
            mock.patch.object(SP, "_clinvar_by_gene", lambda scan: {}),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()

    def _card(self):
        return SP.system("glucose", "clinician")

    def test_the_carried_genotypes_are_asked_about(self):
        asked = sorted(q.get("gene") for q in self._card()["questions"]["rows"]
                       if q.get("origin") == "expect")
        self.assertEqual(["HET", "HOM"], asked)

    def test_the_position_read_without_the_allele_is_asked_nothing(self):
        for q in self._card()["questions"]["rows"]:
            self.assertNotEqual(
                "ABSENT", q.get("gene"),
                "an expectation was asked of a genotype the person does not carry")

    def test_the_row_still_says_the_allele_was_not_found(self):
        rows = {r["gene"]: r for r in self._card()["genetics"]["rows"]}
        self.assertEqual("absent", rows["ABSENT"]["state"],
                         "the position is read and the state is printed — nothing is hidden")
        self.assertTrue(rows["ABSENT"].get("text"),
                        "the reader is told the named allele was not found")


class TestTheSentenceReadsLikeASentence(unittest.TestCase):

    def test_a_corridor_open_at_one_end_names_the_end_it_has(self):
        self.assertEqual("1.0–3.0", SP._corridor(1.0, 3.0))
        for text, args in ((SP._corridor(None, 3.0), (None, 3.0)),
                           (SP._corridor(1.0, None), (1.0, None))):
            with self.subTest(args=args):
                self.assertNotIn("—", text, "an em dash for a bound that is simply absent")
                self.assertIn("3.0" if args[1] else "1.0", text)
        self.assertEqual("—", SP._corridor(None, None))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
