"""A held quote cannot be lent to another drug or an unsupported joint state."""
from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
from unittest import mock

from scholion import cli, core, drugsource, engine, format as fmt, i18n, mcp_server
from scholion.engine import pgx
from tests.test_a_genotype_in_the_profile_is_never_shown_as_unread import _Demo


def _phenotype(gene, codes):
    return {"gene": gene, "phenotype": codes.get(gene, "NM"), "label": "Synthetic reading",
            "certainty": "called", "found": [], "basis": {}}


class TestGuidanceInput(_Demo):
    def setUp(self):
        super().setUp()
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_exact_drugs_keep_their_table_but_other_drugs_and_classes_do_not(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for drug, expected in (("simvastatin", True), ("simvastatin 20 mg", True),
                                   ("codeine", True), ("codeine phosphate", True),
                                   ("atorvastatin", False), ("rosuvastatin", False),
                                   ("pravastatin", False), ("statin", False), ("tramadol", False)):
                codes = {"SLCO1B1": "normal_function", "CYP2D6": "PM"}
                with mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, codes)):
                    row = pgx.check_drug_gene(drug)
                self.assertEqual(expected, row["guidance_applicability"]["status"] == "applicable")
                self.assertIsNone(row["cpic"])
                self.assertTrue(row["guidance_gap"])
                if expected:
                    self.assertEqual("incomplete", row["conclusion_basis"]["status"])
                self.assertTrue(row["phenotype"])
                if not expected:
                    self.assertEqual("unknown", row["level"])
                    self.assertTrue(row["guidance_gap_reason"])
                    self.assertEqual(i18n.t("drug.guidance.context"), row["why"])
                    self.assertNotIn("⟦", row["recommendation"])
                    self.assertNotIn("morphine", fmt.drug_check(row).lower())
                    self.assertEqual({}, pgx._guidance_for(drug, row["gene"]))

    def test_a_newer_reference_cannot_restore_the_mismatched_quote(self):
        local = copy.deepcopy(core.cpic_kb())
        local["_meta"]["updated"] = "2099-01-01"
        before = copy.deepcopy(local)
        with (mock.patch.object(core, "cpic_kb", return_value=local),
              mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, {"CYP2D6": "PM"}))):
            row = pgx.check_drug_gene("tramadol")
        self.assertIsNone(row["cpic"])
        self.assertEqual("drug_table_mismatch", row["guidance_applicability"]["status"])
        self.assertEqual(before, local)

    def test_joint_im_is_not_answered_from_the_single_im_table(self):
        for codes, joint in (({"TPMT": "IM", "NUDT15": "IM"}, True),
                             ({"TPMT": "NM", "NUDT15": "IM"}, False),
                             ({"TPMT": "IM", "NUDT15": "NM"}, False),
                             ({"TPMT": "PM", "NUDT15": "IM"}, False),
                             ({"TPMT": "NM", "NUDT15": "NM"}, False)):
            with mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, codes)):
                row = pgx.check_drug_gene("azathioprine")
                check = engine.check_new_prescription("azathioprine")
            self.assertEqual(joint, row["guidance_applicability"]["status"] == "joint_phenotype_unheld")
            self.assertIsNone(row["cpic"])
            self.assertEqual(codes["TPMT"], row["phenotype"])
            self.assertEqual(codes["NUDT15"], row["co_genes"][0]["phenotype"])
            if joint:
                self.assertEqual("unknown", row["level"])
                self.assertEqual(i18n.t("drug.guidance.context"), row["why"])
                self.assertEqual(["NUDT15", "TPMT"], row["guidance_applicability"]["genes"])
                self.assertNotEqual("low", check["overall"])
                self.assertEqual("no_rule", check["genetic_context"]["verdict"]["kind"])
                self.assertTrue(any(r["detail"] == row["guidance_gap_reason"] for r in check["unresolved"]))

    def test_an_online_normal_reading_with_no_table_is_not_clearance(self):
        info = {"name": "Synthetic online drug", "internal_class": "ppi", "atc": []}
        with (mock.patch.object(drugsource, "resolve_drug", return_value=info),
              mock.patch.object(drugsource, "class_gene", return_value=("CYP2C19", "Synthetic class role")),
              mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, {}))):
            row = pgx._check_drug_online("Synthetic online drug")
        self.assertEqual("NM", row["phenotype"])
        self.assertEqual("unknown", row["level"])
        self.assertTrue(row["guidance_gap"])
        self.assertTrue(row["guidance_gap_reason"])

    def test_cli_json_text_and_agent_tools_retain_the_same_refusal(self):
        codes = {"TPMT": "IM", "NUDT15": "IM"}
        with mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, codes)):
            for command in ("drug", "prescription"):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(0, cli.main([command, "azathioprine", "--json"]))
                row = json.loads(output.getvalue())
                drug = row if command == "drug" else row["pharmacogenetics"]
                self.assertEqual("joint_phenotype_unheld", drug["guidance_applicability"]["status"])
                self.assertIsNone(drug["cpic"])
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(0, cli.main([command, "azathioprine"]))
                self.assertIn(drug["guidance_gap_reason"], output.getvalue())
                tool = "sch_check_drug_gene" if command == "drug" else "sch_check_prescription"
                answer = mcp_server.call_tool(tool, {"drug": "azathioprine"})
                self.assertFalse(answer.get("isError"), answer)
                text = "\n".join(c.get("text", "") for c in answer["content"])
                self.assertIn(drug["guidance_gap_reason"], text)
