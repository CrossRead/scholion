"""A source-based revision never borrows the former wording's human review."""
from __future__ import annotations

import json
import unittest
from unittest import mock

import support
from scholion import core, i18n
from scholion.engine import panel_catalogue, system_panels as SP
from scholion.format_genome import panel_report
from scholion.format_system import _system_gene_row


class TestStatinPanelRevision(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        book = json.loads((support.SRC / "scholion/knowledge/system_gene_panels.json")
                          .read_text(encoding="utf-8"))
        self.rows = [p for p in book["systems"]["lipids"]["positions"]
                     if p["rsid"] in ("rs4149056", "rs2231142")]

    def test_revision_names_a_primary_source_and_not_the_old_reviewer(self):
        self.assertEqual(2, len(self.rows))
        for p in self.rows:
            self.assertNotIn("review", p)
            self.assertTrue(p["note_on_review"])
            self.assertEqual("2026-10-04", p["curated_on"])
            self.assertIn("PMID:35152405", p["source"])
            self.assertEqual(p["source"], p["evidence"]["source"])
            self.assertEqual("A", p["evidence"]["level"])
            for lang in ("en", "ru"):
                self.assertTrue(p["mechanism"][lang])
                for state in ("het", "hom"):
                    text = p["text"][state][lang]
                    self.assertNotIn("20", text)
                    self.assertNotIn("*5", text)
                    self.assertNotIn("urate", text)
                    self.assertTrue(text)

    def test_the_same_basis_reaches_raw_rows_state_lists_and_both_text_registers(self):
        for lang in ("en", "ru"):
            i18n.set_lang(lang)
            with mock.patch.object(SP, "_genotype", return_value={
                    "state": "het", "read": True, "genotype": "TC", "confidence": "called"}), \
                    mock.patch.object(SP, "_has_alignment", return_value=False), \
                    mock.patch.object(core, "profile_sex", return_value="female"):
                result = SP._curated_rows("lipids", {"positions": self.rows}, [],
                                          {"status": "ok", "input_profile": "whole_genome"}, {})
            self.assertEqual(2, len(result["rows"]))
            for row, spec in zip(result["rows"], self.rows):
                self.assertEqual(spec["mechanism"][lang], row["mechanism"])
                self.assertEqual("open", row["signature"])
                self.assertIsNone(row["review"])
                self.assertEqual(row["mechanism"], SP._position_state(row)["mechanism"])
                self.assertEqual(row["source"], SP._position_state(row)["source"])
                for register in ("patient", "clinician"):
                    projected = SP._project({"rows": [row]}, register)["rows"][0]
                    self.assertEqual(row["mechanism"], projected["mechanism"])
                    self.assertEqual(row["source"], projected["source"])
                    text = _system_gene_row(projected, register)
                    self.assertIn(row["mechanism"], text)
                    self.assertIn(row["source"], text)

    def test_the_reference_catalogue_keeps_localised_mechanisms(self):
        for lang in ("en", "ru"):
            i18n.set_lang(lang)
            book = panel_catalogue.panel_description("lipids")
            text = panel_report(book)
            by_id = {p["rsid"]: p for p in book["positions"]}
            for original in self.rows:
                row = by_id[original["rsid"]]
                self.assertEqual(original["mechanism"][lang], row["mechanism"])
                self.assertEqual("open", row["signature"])
                self.assertIn(row["mechanism"], text)


class TestAnticoagulantAndNsaidRevisions(unittest.TestCase):
    def test_all_affected_panel_copies_have_context_instead_of_single_position_doses(self):
        book = json.loads((support.SRC / "scholion/knowledge/system_gene_panels.json")
                          .read_text(encoding="utf-8"))
        expected = {"cardio": {"rs1799853", "rs1057910", "rs9923231", "rs2108622"},
                    "inflammation": {"rs1799853", "rs1057910"},
                    "renal": {"rs1799853", "rs1057910"}}
        seen = set()
        for system, rsids in expected.items():
            for p in book["systems"][system]["positions"]:
                if p["rsid"] not in rsids:
                    continue
                seen.add((system, p["rsid"]))
                self.assertNotIn("review", p)
                self.assertTrue(p["note_on_review"])
                self.assertEqual("2026-10-04", p["curated_on"])
                pmid = "28198005" if system == "cardio" else "32189324"
                self.assertIn("PMID:" + pmid, p["source"])
                self.assertEqual(p["source"], p["evidence"]["source"])
                for language in ("en", "ru"):
                    self.assertTrue(p["mechanism"][language])
                    for text in p["text"].values():
                        self.assertTrue(text[language])
                        if language == "en":
                            self.assertNotIn("quarter", text[language])
                            self.assertIn("prescriber", text[language])
                            if system != "cardio":
                                self.assertIn("diplotype", text[language])
        self.assertEqual({(s, rs) for s, ids in expected.items() for rs in ids}, seen)
