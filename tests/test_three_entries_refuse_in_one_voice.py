"""Three entries, one data state, one refusal — word for word.

Task 171. A list of genes is generated three ways — by a prescription
(`decision`), by a class of disease (`screening`) and by a body system
(`system_panels`) — and the form is the same for all three: the gate that
prints an entry only with a sentence and a source and counts what it dropped,
the pending row for a gene named without a sentence, a row that says whether
the gene was read, and a four-state verdict with the unread count inside it.

The neighbouring branch named the risk: three modules written by copy diverge
into three refusal sentences within a week, and one of them will eventually
call a list clear that nobody read. The refusal is the product. So the form
lives once, in `panel_form`, and this test puts one synthetic state — four
genes, one of them unread; one entry with no source; one entry with a source
and no sentence — through all three entries and requires the SAME verdict
kind, the same unread count, the same dropped count and the same sentence.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion.engine import decision as D
from scholion.engine import panel_form as PF
from scholion.engine import screening as S
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru

#: The state. GA read and reference, GB NOT read, GC read and reference, PEND
#: read with one copy of the named allele and no phrase written for it.
LOCI = {"loci": {"rsGA": {"gene": "GA"}, "rsGB": {"gene": "GB"},
                 "rsGC": {"gene": "GC"}, "rsPEND": {"gene": "PEND"}}}
CALLS = {"rsGA": {"genotype": "AA", "confidence": "called", "depth": 30},
         "rsGB": {"genotype": None, "confidence": "assumed_ref"},
         "rsGC": {"genotype": None, "confidence": "confirmed_ref", "depth": 22},
         "rsPEND": {"genotype": "AG", "confidence": "called", "depth": 28}}


def _lookup(rsid=None, gene=None):
    return {"status": "ok", "rsid": rsid, "result": dict(CALLS.get(rsid) or
                                                        {"confidence": "no_call_in_vcf"})}


TEXT = {"en": "a sentence", "ru": "a sentence (ru)"}
DRUG_BOOK = {"drugs": {"x": {"genes": {
    "GA": {"kind": "mechanism", "text": TEXT, "source": "s"},
    "GB": {"kind": "mechanism", "text": TEXT, "source": "s"},
    "GC": {"kind": "mechanism", "text": TEXT, "source": "s"},
    "PEND": {"kind": "mechanism", "source": "s"},
    "NOSRC": {"kind": "mechanism", "text": TEXT}}}}}
CLASS_BOOK = {"classes": {"x": {"source": "s", "genes": ["GA", "GB", "GC", "PEND"]},
                          "nosrc": {"genes": ["GA"]}}}


def _pos(rs, gene, text=None, **extra):
    return {"rsid": rs, "gene": gene, "hgvs": "NC_000001.11:g.100A>G", "risk_allele": "G",
            "mode": "monogenic", "classification": "Strong", "moi": "AD",
            "text": {"het": text, "hom": text}, **extra}


SYSTEM_BOOK = {"_meta": {"why_empty": "empty"}, "systems": {"thyroid": {"source": None, "positions": [
    _pos("rsGA", "GA", TEXT, source="s"), _pos("rsGB", "GB", TEXT, source="s"),
    _pos("rsGC", "GC", TEXT, source="s"), _pos("rsPEND", "PEND", None, source="s"),
    _pos("rsGA", "NOSRC", TEXT)]}}}


def _acmg_scan():
    return {"status": "ok", "scanned": "2026-09-01", "hits": [],
            "coverage": {"weak": [{"gene": "GB", "pct_10x": 70.0}], "unmeasured": []}}


class TestOneStateThreeEntriesOneSentence(unittest.TestCase):

    def setUp(self):
        self._patches = [
            mock.patch.object(core, "loci", lambda: LOCI),
            mock.patch("scholion.genome.lookup", _lookup),
            mock.patch("scholion.genome.available", lambda: {"ready": True}),
            mock.patch.object(D, "_context", lambda: DRUG_BOOK),
            mock.patch.object(S, "_curated", lambda: CLASS_BOOK),
            mock.patch("scholion.engine.genomics.acmg_findings", _acmg_scan),
            mock.patch.object(SP, "_curated", lambda: SYSTEM_BOOK),
            mock.patch.object(SP, "_base", lambda: {}),
            mock.patch.object(SP, "_clinvar_by_gene",
                              lambda scan: {"status": "ok", "by_gene": {}}),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()

    def _three(self):
        d = D.classify({"genes": [], "cpic": {"asked": True}}, "x")
        s = S.screen("x")
        y = SP.system("thyroid", register="clinician")
        return d, s, y

    def test_the_verdict_kind_and_the_unread_count_are_the_same(self):
        d, s, y = self._three()
        kinds = (d["panel_verdict"]["kind"], s["verdict"]["kind"], y["verdict"]["kind"])
        self.assertEqual(("clear_partial",) * 3, kinds)
        self.assertEqual((1, 1, 1), (d["panel_verdict"]["unread"], s["verdict"]["unread"],
                                     y["verdict"]["unread"]))
        self.assertEqual((4, 4, 4), (d["panel_verdict"]["total"], s["verdict"]["total"],
                                     y["verdict"]["total"]))
        self.assertEqual((["GB"],) * 3, (d["panel_verdict"]["genes"], s["verdict"]["genes"],
                                         y["verdict"]["genes"]))

    def test_the_dropped_count_is_the_same_number(self):
        d, s, y = self._three()
        self.assertEqual((1, 1, 1), (d["curated"]["refused"], s["classes"]["refused"],
                                     y["genetics"]["refused"]["total"]))

    def test_the_pending_row_is_kept_by_all_three(self):
        d, s, y = self._three()
        self.assertEqual(["PEND"], [r["gene"] for r in d["curated"]["pending"]])
        self.assertIn("PEND", [r["gene"] for r in s["genes"]])
        self.assertEqual(["PEND"], [r["gene"] for r in y["genetics"]["rows"] if r["pending"]])

    def test_the_refusal_sentence_is_one_text_in_both_languages(self):
        from scholion import i18n
        try:
            for code in ("en", "ru"):
                i18n.set_lang(code)
                core.reset_cache()
                d, s, y = self._three()
                lines = {PF.verdict_line(d["panel_verdict"]), S.verdict_line(s["verdict"]),
                         y["verdict_line"]}
                self.assertEqual(1, len(lines), f"{code}: three sentences for one state: {lines}")
                line = next(iter(lines))
                self.assertIn("GB", line)
                self.assertNotIn("⟦", line)
                self.assertNotIn("{", line)
        finally:
            i18n.set_lang(None)
            core.reset_cache()

    def test_a_list_read_end_to_end_is_measured_clear_in_all_three(self):
        calls = dict(CALLS, rsGB={"genotype": None, "confidence": "confirmed_ref", "depth": 20})
        scan = dict(_acmg_scan(), coverage={"weak": [], "unmeasured": []})
        with mock.patch.dict(CALLS, calls), \
             mock.patch("scholion.engine.genomics.acmg_findings", lambda: scan):
            d, s, y = self._three()
        self.assertEqual(("clear_measured",) * 3,
                         (d["panel_verdict"]["kind"], s["verdict"]["kind"], y["verdict"]["kind"]))

    def test_a_genome_nobody_could_open_is_not_determined_in_all_three(self):
        with mock.patch("scholion.genome.available", lambda: {"ready": False, "reason": "no_file"}), \
             mock.patch("scholion.engine.genomics.acmg_findings",
                        lambda: {"status": "not_run", "reason": "not_ready"}):
            d, s, y = self._three()
        self.assertEqual(("not_determined",) * 3,
                         (d["panel_verdict"]["kind"], s["verdict"]["kind"], y["verdict"]["kind"]))


class TestTheFormIsOneCopy(unittest.TestCase):

    def test_the_two_older_entries_call_the_form_rather_than_carrying_a_copy(self):
        self.assertIs(D.KINDS, PF.KINDS)
        self.assertIs(S.VERDICTS, PF.VERDICTS)
        self.assertIs(SP.verdict, PF.verdict)
        self.assertIs(SP.verdict_line, PF.verdict_line)
        import inspect
        self.assertIn("panel_form.verdict(", inspect.getsource(S.verdict))
        self.assertIn("panel_form.gate(", inspect.getsource(D.curated_genes))

    def test_the_gate_drops_only_what_has_no_source_and_counts_it(self):
        got = PF.gate({"A": {"text": TEXT, "source": "s"}, "B": {"source": "s"},
                       "C": {"text": TEXT}, "D": {"kind": "invented", "text": TEXT, "source": "s"},
                       "E": "not a row"})
        self.assertEqual(["A"], [r["gene"] for r in got["genes"]])
        self.assertEqual(["B"], [r["gene"] for r in got["pending"]])
        self.assertEqual(3, got["refused"])

    def test_the_list_source_stands_in_for_a_row_that_has_none(self):
        got = PF.gate({"C": {"text": TEXT}}, "the list")
        self.assertEqual("the list", got["genes"][0]["source"])

    def test_every_verdict_sentence_exists_in_both_catalogues(self):
        for key in ("screen.finding", "screen.and_unread", "screen.and_carriers",
                    "screen.clear_measured", "screen.clear_partial", "screen.not_determined",
                    "screen.why.not_ready", "screen.why.no_panel", "screen.why.no_genetic_half"):
            for cat in (en.MESSAGES, ru.MESSAGES):
                with self.subTest(key=key):
                    self.assertIn(key, cat)

    def test_a_reason_the_catalogue_does_not_know_is_printed_as_itself(self):
        line = PF.verdict_line({"kind": "not_determined", "why": "SomethingElse"})
        self.assertIn("SomethingElse", line)
        self.assertNotIn("⟦", line)


if __name__ == "__main__":
    unittest.main()
