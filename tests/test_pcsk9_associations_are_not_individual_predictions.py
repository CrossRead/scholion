"""Curated primary findings cannot exclude other causes or become per-copy forecasts."""
from __future__ import annotations

import json
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, i18n
from scholion.engine import panel_catalogue, system_panels as SP


class TestPcsk9Revision(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_bilingual_primary_findings_do_not_inherit_old_review(self):
        raw = json.loads(core.knowledge_path("system_gene_panels.json").read_text(encoding="utf-8"))
        rows = {p["rsid"]: p for p in raw["systems"]["lipids"]["positions"] if p["gene"] == "PCSK9"}
        self.assertEqual({"rs11591147", "rs28362286"}, set(rows))
        for p in rows.values():
            self.assertEqual("B", p["evidence"]["level"])
            self.assertNotIn("review", p)
            self.assertIn("open", p["note_on_review"])
            for pmid in ("16554528", "17080197", "16909389"):
                self.assertIn("PMID:" + pmid, p["source"])
            for language in ("en", "ru"):
                for field in ("mechanism", "effect_size"):
                    self.assertTrue(p[field][language])
        self.assertIn("did not measurably alter", rows["rs11591147"]["mechanism"]["en"])
        self.assertIn("not detected in the medium", rows["rs28362286"]["mechanism"]["en"])
        self.assertNotIn("per allele", rows["rs11591147"]["effect_size"]["en"])
        self.assertIn("cohort comparison", rows["rs11591147"]["effect_size"]["en"])
        self.assertIn("pooled", rows["rs28362286"]["effect_size"]["en"])
        self.assertIn("not a C679X-specific", rows["rs28362286"]["effect_size"]["en"])
        self.assertIn("does not establish why", rows["rs11591147"]["text"]["het"]["en"])
        self.assertIn("not exclude other causes", rows["rs28362286"]["text"]["het"]["en"])

    def test_readings_and_main_claim_survive_without_reviving_the_old_expectation(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            specs = [p for p in core._read_knowledge("system_gene_panels.json")["systems"]["lipids"]["positions"]
                     if p["gene"] == "PCSK9"]
            for p in specs:
                reference = panel_catalogue._position(p)
                self.assertEqual("complete", reference["conclusion_basis"]["status"])
                self.assertEqual(p["text"], reference["text"])
                self.assertIsNone(reference["expect"])
                self.assertEqual("incomplete", reference["subclaim_basis"]["expect"]["status"])
                for state in ("het", "hom"):
                    with mock.patch.object(SP, "_genotype", return_value={"state": state, "read": True,
                                           "genotype": "SYNTHETIC", "confidence": "called"}), \
                            mock.patch.object(SP, "_has_alignment", return_value=False):
                        row = SP._curated_rows("lipids", {"positions": [p]}, ["ldl"],
                                              {"status": "ok", "input_profile": "whole_genome"}, {})["rows"][0]
                    self.assertEqual(p["text"][state], row["text"])
                    self.assertEqual(state, row["state"])
                    self.assertTrue(row["read"])
                    self.assertIsNone(row["expect_check"])
                    self.assertEqual("open", row["signature"])
