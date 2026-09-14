"""Every row of a panel says who signed its sentence — or that nobody did.

Ninety-one of the ninety-two positions shipped in `system_gene_panels.json`
once carried `note_on_signature` — «a draft from the named source; a clinician's
signature is still open» — and **nothing read that field**: a drafted sentence
and a signed one printed identically. The owner signed the phrases on
13.09.2026, so the shipped state is now «signed by the panel's author, not by a
clinician», and the unsigned state stays in the engine for a panel that arrives
without a signature.

Held here:

  * every key a shipped row uses reaches the engine's row, under its own name or
    under a named transformation — the general form of the guard, because the
    field that was read by nobody is a shape this project keeps finding;
  * the shipped rows say, in the clinician's density, that their author signed
    them and that no clinician did, with the date; the count of such rows stands
    in the summary, which both registers print;
  * a row with a note and no signer still prints as unsigned, in both registers
    and both languages;
  * a signer the engine does not know is not treated as a signature — the card
    would have to name whom, and it cannot.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, format as F
from scholion import i18n
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru

#: A field of the file whose value reaches the reader under another name: the
#: phrase is chosen by the state of the genotype, the expectation is filled in
#: with the person's own numbers, and the signer becomes a state because the
#: file says it in one language and a row prints in two.
RENAMED = {"text": "text", "expect": "expect_check",
           "note_on_signature": "signature", "signed_by": "signature"}


def _shipped() -> dict:
    return core._read_knowledge("system_gene_panels.json")


class TestEveryFieldOfAShippedRowReachesTheRow(unittest.TestCase):

    def test_no_field_of_the_shipped_panel_is_written_for_nobody(self):
        systems = (_shipped().get("systems") or {})
        used = set()
        for spec in systems.values():
            for p in (spec.get("positions") or []):
                used |= {str(k) for k in p.keys()}
        self.assertTrue(used, "the shipped panel holds no positions at all")
        carried = set()
        for key in systems:
            for r in SP.system(key, "clinician")["genetics"].get("rows") or []:
                if r.get("origin") == "curated":
                    carried |= {str(k) for k in r.keys()}
        self.assertTrue(carried, "no curated row was built from the shipped panel")
        lost = sorted(f for f in used
                      if f not in carried and RENAMED.get(f) not in carried)
        self.assertEqual([], lost,
                         "a field of the shipped panel reaches no row: " + ", ".join(lost))

    def test_every_shipped_row_is_signed_by_the_author_and_by_no_clinician(self):
        systems = (_shipped().get("systems") or {})
        signed = {(k, p["rsid"]) for k, spec in systems.items()
                  for p in (spec.get("positions") or []) if p.get("signed_by")}
        self.assertTrue(signed, "no shipped row names a signer")
        seen, unsigned = set(), []
        for key in systems:
            for r in SP.system(key, "clinician")["genetics"].get("rows") or []:
                if r.get("origin") != "curated":
                    continue
                if r.get("signature") == "author":
                    seen.add((key, r.get("rsid")))
                else:
                    unsigned.append((key, r.get("gene"), r.get("signature")))
        self.assertEqual([], unsigned, "a shipped row carries no signature")
        self.assertEqual(signed, seen)

    def test_the_count_and_the_date_of_the_signing_reach_both_registers(self):
        i18n.set_lang("en")
        try:
            text = F.system_report(SP.system("thyroid", "clinician"))
        finally:
            i18n.set_lang(None)
        self.assertNotIn(en.MESSAGES["system.row.signature_open"], text,
                         "a shipped row reads as unsigned")
        gen = SP.system("thyroid", "clinician")["genetics"]
        self.assertGreater(gen["signature_author_count"], 0,
                           "the shipped thyroid panel counts no signed row")
        for register in SP.REGISTERS:
            i18n.set_lang("en")
            try:
                t = F.system_report(SP.system("thyroid", register))
            finally:
                i18n.set_lang(None)
            self.assertIn(en.MESSAGES["system.genetics.signature_author"].format(
                n=gen["signature_author_count"],
                date=gen["signature_author_date"]), t,
                f"the count and the date are missing from the {register}'s summary")
            self.assertIn(str(gen["signature_author_date"]), t,
                          "the date the rows were signed reaches nobody")


TXT = {"en": "what follows", "ru": "what follows (ru)"}
LOCI = {"loci": {"rsSIGNED": {"gene": "SIGNED"}, "rsDRAFT": {"gene": "DRAFT"},
                 "rsSTRANGE": {"gene": "STRANGE"}}}
CALLS = {rs: {"genotype": "AG", "confidence": "called", "depth": 30}
         for rs in ("rsSIGNED", "rsDRAFT", "rsSTRANGE")}


def _lookup(rsid=None, gene=None):
    return {"status": "ok", "rsid": rsid, "result": dict(CALLS.get(rsid) or {})}


def _pos(rs, gene, **over):
    row = {"rsid": rs, "gene": gene, "hgvs": "NC_000001.11:g.100A>G", "risk_allele": "G",
           "mode": "monogenic", "classification": "Strong", "moi": "AD", "kind": "mechanism",
           "text": {"het": TXT, "hom": TXT}, "source": "the author"}
    row.update(over)
    return row


CURATED = {"_meta": {"why_empty": "nobody wrote a row"},
           "systems": {"thyroid": {"source": None, "positions": [
               _pos("rsSIGNED", "SIGNED", signed_by="owner", signed_on="2026-09-13"),
               _pos("rsDRAFT", "DRAFT",
                    note_on_signature="a draft; a clinician's signature is still open"),
               _pos("rsSTRANGE", "STRANGE", signed_by="somebody nobody knows")]}}}


class TestTheUnsignedRowSaysSoOnTheScreen(unittest.TestCase):

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

    def _rows(self):
        return {r["gene"]: r for r in SP.system("thyroid", "clinician")["genetics"]["rows"]}

    def test_a_signer_the_engine_does_not_know_is_not_a_signature(self):
        self.assertEqual("open", self._rows()["STRANGE"]["signature"],
                         "a row whose signer cannot be named must not read as signed")
        self.assertEqual("author", self._rows()["SIGNED"]["signature"])
        self.assertEqual("open", self._rows()["DRAFT"]["signature"])

    def test_both_registers_and_both_languages_say_which_rows_are_unsigned(self):
        for lang, words in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            phrase = words["system.row.signature_open"]
            for register in SP.REGISTERS:
                with self.subTest(lang=lang, register=register):
                    i18n.set_lang(lang)
                    try:
                        text = F.system_report(SP.system("thyroid", register))
                    finally:
                        i18n.set_lang(None)
                    self.assertIn(phrase, text)
                    said = [ln for ln in text.splitlines() if phrase in ln]
                    self.assertTrue(all(("rsDRAFT" in ln or "rsSTRANGE" in ln) for ln in said), said)

    def test_the_summary_counts_the_signed_and_the_unsigned_apart(self):
        gen = SP.system("thyroid", "clinician")["genetics"]
        self.assertEqual(2, gen["signature_open_count"])
        self.assertEqual(1, gen["signature_author_count"])
        i18n.set_lang("en")
        try:
            text = F.system_report(SP.system("thyroid", "clinician"))
        finally:
            i18n.set_lang(None)
        self.assertIn(en.MESSAGES["system.genetics.signature_open"].format(n=2), text)
        self.assertIn(en.MESSAGES["system.genetics.signature_author"].format(
            n=1, date="2026-09-13"), text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
