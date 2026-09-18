"""A rare variant read off a chip is a signal to confirm, never a finding.

Task 99 closed ClinVar, the ACMG list and polygenic scores on a narrow input and
named task 2 — the frequency floor — as the condition for anything rare to be
said from one. The curated panels were never behind that gate: a monogenic row
is read position by position, and on a chip the card would have printed «one
copy» of a rare pathogenic variant with the author's sentence about what it
means. A chip's positive predictive value for such variants is 4.2 % for
BRCA1/2 (Weedon, BMJ 2021).

Now a monogenic row read off a narrow input, below the floor or with no
frequency at all, counts as no finding and says what to do first; the same row
off a full genome is read as before, and a common variant off a chip is not
touched.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, format as F, i18n
from scholion.engine import panel_gate as G
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru

TXT = {"en": "one copy means this", "ru": "one copy means this (ru)"}
LOCI = {"loci": {"rsRARE": {"gene": "RARE"}, "rsCOMMON": {"gene": "COMMON"}}}
CALLS = {"rsRARE": {"genotype": "AG", "confidence": "called", "depth": 30},
         "rsCOMMON": {"genotype": "AG", "confidence": "called", "depth": 30}}
REVIEW = {"by_role": "panel_author", "on": "2026-09-13", "scope": "sentence_against_source"}

CURATED = {"_meta": {}, "systems": {"thyroid": {"source": "s", "positions": [
    {"rsid": "rsRARE", "gene": "RARE", "hgvs": "NC_000001.11:g.100A>G", "risk_allele": "G",
     "mode": "monogenic", "classification": "Definitive", "moi": "AD",
     "evidence": {"level": "A", "basis": "gencc", "source": "s"},
     "text": {"het": TXT, "hom": TXT}, "source": "s", "review": REVIEW},
    {"rsid": "rsCOMMON", "gene": "COMMON", "hgvs": "NC_000001.11:g.200A>G", "risk_allele": "G",
     "mode": "common_variant", "effect_size": "OR 1.2", "study": "a study",
     "text": {"het": TXT, "hom": TXT}, "source": "s", "review": REVIEW}]}}}


def _lookup(rsid=None, gene=None):
    return {"status": "ok", "rsid": rsid, "result": dict(CALLS.get(rsid) or {})}


class _Card(unittest.TestCase):
    PROFILE = "array"

    def setUp(self):
        profile = self.PROFILE
        self._patches = [
            mock.patch.object(core, "loci", lambda: LOCI),
            mock.patch("scholion.genome.lookup", _lookup),
            mock.patch("scholion.genome.available", lambda: {"ready": True, "input_profile": profile}),
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

    def rows(self, register="clinician"):
        return {r["gene"]: r for r in SP.system("thyroid", register)["genetics"]["rows"]}


class TestOffAChip(_Card):

    def test_the_rare_row_is_a_signal_and_not_a_finding(self):
        r = self.rows()["RARE"]
        self.assertEqual("het", r["state"])
        self.assertTrue(r["needs_confirmation"])
        self.assertEqual(0, r["findings"])
        self.assertEqual("needs_confirmation", r["not_a_finding_why"])
        self.assertNotIn("one copy means this", r["text"])
        self.assertIn("rsRARE", r["text"])

    def test_the_common_row_is_untouched(self):
        r = self.rows()["COMMON"]
        self.assertFalse(r["needs_confirmation"])
        self.assertEqual("one copy means this", r["text"])

    def test_both_registers_and_both_languages_say_it(self):
        for lang, words in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            for register in SP.REGISTERS:
                with self.subTest(lang=lang, register=register):
                    i18n.set_lang(lang)
                    try:
                        text = F.system_report(SP.system("thyroid", register))
                    finally:
                        i18n.set_lang(None)
                    self.assertIn(words["system.row.needs_confirmation"], text)

    def test_the_patient_register_carries_the_flag(self):
        self.assertTrue(self.rows("patient")["RARE"]["needs_confirmation"])


class TestOffAFullGenome(_Card):
    PROFILE = "wgs"

    def test_the_rare_row_is_read_as_before(self):
        r = self.rows()["RARE"]
        self.assertFalse(r["needs_confirmation"])
        self.assertEqual(1, r["findings"])
        self.assertEqual("one copy means this", r["text"])


class TestTheFloor(unittest.TestCase):

    def test_a_row_says_it_is_common_enough_to_be_read(self):
        row = {"mode": "monogenic", "population_af": 0.02}
        self.assertFalse(G.needs_confirmation(row, "array"))
        self.assertTrue(G.needs_confirmation({"mode": "monogenic", "population_af": 0.0001}, "array"))
        self.assertTrue(G.needs_confirmation({"mode": "monogenic"}, "genotype_table"))
        self.assertFalse(G.needs_confirmation({"mode": "monogenic"}, "exome"),
                         "an exome is sequenced; the floor is for inputs that are not")


if __name__ == "__main__":
    unittest.main()
