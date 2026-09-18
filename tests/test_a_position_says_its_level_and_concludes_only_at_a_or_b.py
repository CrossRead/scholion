"""A panel position says its evidence level, and concludes only at A or B (task 199).

The level is part of the answer, not a field of the card: it rides on the row,
on the state list every register keeps, on the summary, in the report and on the
page. A row whose level is below B — or that has none yet — keeps its value and
loses its conclusion. The letters recorded on 17.09.2026 are the ones the rows'
own curated fields decide; nothing else was graded, and that is held here too.
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, format as F, i18n
from scholion.engine import panel_gate as G
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru

TXT = {"en": "what follows", "ru": "what follows (ru)"}
LOCI = {"loci": {f"rs{i}": {"gene": f"G{i}"} for i in range(1, 5)}}
CALLS = {f"rs{i}": {"genotype": "AG", "confidence": "called", "depth": 30} for i in range(1, 5)}


def _pos(i, level=None, **over):
    row = {"rsid": f"rs{i}", "gene": f"G{i}", "hgvs": f"NC_000001.11:g.{i}00A>G", "risk_allele": "G",
           "mode": "monogenic", "classification": "Strong", "moi": "AD", "text": {"het": TXT, "hom": TXT},
           "source": "s", "review": {"by_role": "panel_author", "on": "2026-09-13"}}
    if level:
        row["evidence"] = {"level": level, "basis": "gencc", "source": "s"}
    row.update(over)
    return row


CURATED = {"_meta": {}, "systems": {"thyroid": {"source": "s", "positions": [
    _pos(1, "A"), _pos(2, "C"), _pos(3),
    _pos(4, "B", mode="common_variant", classification=None, moi=None, effect_size="OR 1.3",
         study="a study")]}}}


def _lookup(rsid=None, gene=None):
    return {"status": "ok", "rsid": rsid, "result": dict(CALLS.get(rsid) or {})}


class TestTheLevelDecidesTheConclusion(unittest.TestCase):

    def setUp(self):
        self._patches = [
            mock.patch.object(core, "loci", lambda: LOCI),
            mock.patch("scholion.genome.lookup", _lookup),
            mock.patch("scholion.genome.available", lambda: {"ready": True, "input_profile": "whole_genome"}),
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

    def gen(self, register="clinician"):
        return SP.system("thyroid", register)["genetics"]

    def test_a_concludes_and_c_and_none_do_not(self):
        rows = {r["gene"]: r for r in self.gen()["rows"]}
        self.assertEqual(1, rows["G1"]["findings"])
        for g in ("G2", "G3"):
            with self.subTest(gene=g):
                self.assertEqual(0, rows[g]["findings"])
                self.assertEqual("level", rows[g]["not_a_finding_why"])
        self.assertEqual("A", rows["G1"]["level"])
        self.assertIsNone(rows["G3"]["level"])

    def test_no_row_concludes_below_b(self):
        allowed = set(G.legend()["verdict_levels"])
        for r in self.gen()["rows"]:
            if r.get("findings"):
                self.assertIn(r.get("level"), allowed, r["gene"])

    def test_the_level_rides_on_every_registers_state_list(self):
        for register in SP.REGISTERS:
            with self.subTest(register=register):
                states = {p["gene"]: p for p in self.gen(register)["positions"]}
                self.assertEqual("A", states["G1"]["level"])
                self.assertTrue(states["G1"]["level_short"])
                self.assertIsNone(states["G3"]["level"])

    def test_the_summary_counts_the_levels(self):
        self.assertEqual({"A": 1, "B": 1, "C": 1, "none": 1}, self.gen()["level_counts"])

    def test_the_ladder_rides_on_a_common_variant_and_marks_its_top(self):
        states = {p["gene"]: p for p in self.gen("patient")["positions"]}
        self.assertEqual({"base": "AA", "het": "AG", "hom": "GG"}, states["G4"]["ladder"])
        self.assertIsNone(states["G1"]["ladder"], "a ladder is the common variants' form")

    def test_the_report_names_the_level_in_both_languages(self):
        for lang, words in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            with self.subTest(lang=lang):
                i18n.set_lang(lang)
                try:
                    text = F.system_report(SP.system("thyroid", "clinician"))
                finally:
                    i18n.set_lang(None)
                self.assertIn(words["system.row.level_none"], text)
                self.assertIn(words["system.row.not_finding_level"], text)
                self.assertIn("**AG**", text, "the person's own rung is not marked")


class TestTheShippedLevels(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = json.loads(core.knowledge_path("system_gene_panels.json").read_text(encoding="utf-8"))

    def rows(self):
        return [p for s in self.raw["systems"].values() for p in s["positions"]]

    def test_every_row_carries_a_letter_and_says_what_it_rests_on(self):
        """32 letters follow from the row's own fields and say so (`by_rule`);
        the rest are a judgement of the evidence and say what it rests on
        (`judged`). No row is left without one, and none carries both."""
        for p in self.rows():
            ev = p.get("evidence") or {}
            decided = ((p["mode"] == "pgx" and p.get("kind") == "guideline")
                       or (p["mode"] == "monogenic" and p.get("classification") in ("Definitive", "Strong")))
            with self.subTest(rsid=p["rsid"], gene=p["gene"]):
                self.assertIn(ev.get("level"), ("A", "B", "C", "D", "E"))
                if decided:
                    self.assertEqual("A", ev["level"])
                    self.assertTrue(ev.get("by_rule"))
                    self.assertNotIn("judged", ev)
                else:
                    self.assertTrue(ev.get("judged"), "a judged letter with no word on what it rests on")
                    self.assertNotIn("by_rule", ev)

    def test_a_row_with_a_sentence_is_never_at_e(self):
        for p in self.rows():
            if p.get("text"):
                self.assertNotEqual("E", (p.get("evidence") or {}).get("level"), p["rsid"])

    def test_every_common_variant_ladder_tops_at_the_risk_allele(self):
        for p in self.rows():
            lad = G.ladder(p)
            if p["mode"] == "common_variant" and p.get("risk_allele"):
                with self.subTest(rsid=p["rsid"]):
                    self.assertEqual(p["risk_allele"].upper() * 2, lad["hom"])


class TestThePageShowsTheLevel(unittest.TestCase):

    def test_the_position_cards_draw_the_chip_and_the_ladder(self):
        page = (support.ROOT / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("${levelChip(p.level,p.level_short)}<b>${esc(p.gene)}</b>", page)
        self.assertIn("${levelNoteHtml(p)}${routeHtml(p)}${underLoadHtml(p)}${ladderHtml(p)}", page)


if __name__ == "__main__":
    unittest.main()
