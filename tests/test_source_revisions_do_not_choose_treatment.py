"""Source-corrected panel wording never promises a drug response or a personal risk."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import support
from scholion import core, i18n
from scholion.engine import pgx, panel_catalogue, system_panels as SP
from scholion.format_genome import panel_report
from scholion.format_system import _system_gene_row


class TestSourceCorrections(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        self.panels = json.loads((support.SRC / "scholion/knowledge/system_gene_panels.json")
                                 .read_text(encoding="utf-8"))["systems"]

    def test_urate_copies_separate_population_odds_from_individual_prediction(self):
        rows = [p for key in ("renal", "amino_acids")
                for p in self.panels[key]["positions"] if p["rsid"] == "rs2231142"]
        self.assertEqual(2, len(rows))
        for p in rows:
            self.assertNotIn("review", p)
            self.assertTrue(p["note_on_review"])
            self.assertEqual("B", p["evidence"]["level"])
            self.assertIn("PMID:19506252", p["source"])
            self.assertIn("PMID:23263486", p["source"])
            self.assertEqual(p["source"], p["evidence"]["source"])
            self.assertIn("odds ratio 1.73", p["effect_size"]["en"])
            self.assertIn("European-ancestry", p["effect_size"]["en"])
            for lang in ("en", "ru"):
                self.assertTrue(p["mechanism"][lang])
                self.assertTrue(p["effect_size"][lang])
                for state in ("het", "hom"):
                    self.assertTrue(p["text"][state][lang])
            for text in p["text"].values():
                self.assertNotIn("allopurinol", text["en"])
                self.assertNotIn("rosuvastatin", text["en"])
                self.assertNotIn("times higher", text["en"])
        for field in ("mechanism", "text", "source", "effect_size"):
            self.assertEqual(rows[0][field], rows[1][field])

    def test_cardiac_position_rows_do_not_choose_treatment_or_promise_response(self):
        rows = [p for p in self.panels["cardio"]["positions"] if p["gene"] == "CYP2C19"]
        self.assertEqual({"rs4244285", "rs12248560"}, {p["rsid"] for p in rows})
        for p in rows:
            self.assertNotIn("review", p)
            self.assertTrue(p["note_on_review"])
            self.assertIn("PMID:35034351", p["source"])
            self.assertEqual(p["source"], p["evidence"]["source"])
            for lang in ("en", "ru"):
                self.assertTrue(p["mechanism"][lang])
            for text in p["text"].values():
                self.assertNotIn("prasugrel", text["en"])
                self.assertNotIn("PPI", text["en"])
                self.assertNotIn("works normally", text["en"])
                self.assertIn("phenotype", text["en"])

    def test_increased_and_no_function_markers_keep_im_without_compensation_claim(self):
        calls = {"rs4244285": "GA", "rs12248560": "CT", "rs4986893": "GG"}
        with mock.patch.object(pgx, "_called_diplotype", return_value=None), \
                mock.patch.object(core, "genome_gaps", return_value=[]), \
                mock.patch.object(core, "genotype_status", side_effect=lambda rs: {
                    "genotype": calls[rs], "confidence": "reported"}):
            for lang in ("en", "ru"):
                i18n.set_lang(lang)
                r = pgx.compute_phenotype("CYP2C19")
                rules = core.cpic_kb()["genes"]["CYP2C19"]["phenotype_rules"]
                plain = next(p["label"] for p in rules if p.get("when") == {"none": ">=1"})
                self.assertEqual("IM", r["phenotype"])
                self.assertEqual("determined", r["certainty"])
                self.assertEqual(plain, r["label"])

    def test_revised_context_reaches_both_languages_and_text_registers(self):
        expected = {"renal": {"rs2231142"}, "amino_acids": {"rs2231142"},
                    "cardio": {"rs4244285", "rs12248560"}}
        for lang in ("en", "ru"):
            i18n.set_lang(lang)
            local = core._read_knowledge("system_gene_panels.json")["systems"]
            for system, ids in expected.items():
                spec = {**local[system], "positions": [p for p in local[system]["positions"]
                                                      if p["rsid"] in ids]}
                with mock.patch.object(SP, "_genotype", return_value={
                        "state": "het", "read": True, "genotype": "GT", "confidence": "called"}), \
                        mock.patch.object(SP, "_has_alignment", return_value=False):
                    rows = SP._curated_rows(system, spec, ["uric_acid"],
                                           {"status": "ok", "input_profile": "whole_genome"}, {})["rows"]
                self.assertEqual(ids, {r["rsid"] for r in rows})
                reference = panel_report(panel_catalogue.panel_description(system))
                for row in rows:
                    self.assertEqual("open", row["signature"])
                    self.assertEqual(row["mechanism"], SP._position_state(row)["mechanism"])
                    self.assertIn(row["mechanism"], reference)
                    self.assertIn(row["source"], reference)
                    for register in ("patient", "clinician"):
                        text = _system_gene_row(row, register)
                        self.assertIn(row["mechanism"], text)
                        self.assertIn(row["source"], text)

    def test_a_newer_local_copy_cannot_restore_the_withdrawn_im_label(self):
        data = json.loads((support.SRC / "scholion/knowledge/cpic_drug_gene.json")
                          .read_text(encoding="utf-8"))
        # A deliberately future fixture stamp tests precedence, not source freshness.
        data["_meta"]["imported"] = {"fetched": "2099-01-01", "synthetic": True}
        for rule in data["genes"]["CYP2C19"]["phenotype_rules"]:
            if rule.get("when") == {"none": ">=1", "increased": ">=1"}:
                rule["label"] = {"en": "legacy compensation claim", "ru": "legacy compensation claim"}
        calls = {"rs4244285": "GA", "rs12248560": "CT", "rs4986893": "GG"}
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp).resolve()
            path = directory / "cpic_drug_gene.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            before = path.read_bytes()
            with mock.patch.object(core, "knowledge_dir_local", return_value=directory), \
                    mock.patch.object(pgx, "_called_diplotype", return_value=None), \
                    mock.patch.object(core, "genome_gaps", return_value=[]), \
                    mock.patch.object(core, "genotype_status", side_effect=lambda rs: {
                        "genotype": calls[rs], "confidence": "reported"}):
                core.reset_cache()
                self.addCleanup(core.reset_cache)
                self.assertEqual(path, core.knowledge_path("cpic_drug_gene.json"))
                for lang in ("en", "ru"):
                    i18n.set_lang(lang)
                    r = pgx.compute_phenotype("CYP2C19")
                    self.assertEqual("IM", r["phenotype"])
                    self.assertEqual(i18n.t("phenotype.label.IM"), r["label"])
                self.assertEqual(before, path.read_bytes(), "display correction rewrote a local reference")


if __name__ == "__main__":
    unittest.main()
