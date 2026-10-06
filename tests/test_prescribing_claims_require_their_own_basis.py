"""Prescribing support is per statement; a source refresh is not new approval."""
from __future__ import annotations

import copy
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest import mock

import support
from scholion import cli, core, drugsource, engine, format as fmt, i18n, mcp_server, ouroboros_tools, sources
from scholion.engine import pgx
from scholion.prescribing_basis import _guard_guidance, _guard_gene_role, _quote_digest
from tests.test_a_genotype_in_the_profile_is_never_shown_as_unread import _Demo
from tests.test_prescribing_tables_apply_to_the_input import _phenotype


def _supported():
    cp = {"phenotype": "Normal Metabolizer", "recommendation": "SYNTHETIC_QUOTATION",
          "implication": "SYNTHETIC_IMPLICATION", "classification": "Synthetic classification",
          "source": "Synthetic PMID:3", "mechanism": {"en": "QUOTE_MECHANISM", "ru": "QUOTE_MECHANISM"}}
    cp["basis_quote_sha256"] = _quote_digest(cp)
    return {"level": "low", "note": "SYNTHETIC_OWN_NOTE", "source": "Synthetic PMID:2",
            "mechanism": {"en": "OWN_MECHANISM", "ru": "OWN_MECHANISM"}, "cpic": cp}


class TestIndependentBasis(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_note_cannot_borrow_the_quotations_source_or_mechanism(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for change in ({"source": None}, {"source": "CPIC"}, {"source": "PMID:TBD"},
                           {"mechanism": None}, {"mechanism": {"en": "One language"}},
                           {"mechanism": " "}):
                row = {**_supported(), **change}
                before = copy.deepcopy(row)
                out = _guard_guidance(row)
                self.assertTrue(out["interpretation_withheld"])
                self.assertEqual("unknown", out["level"])
                self.assertNotIn("SYNTHETIC_OWN_NOTE", out["note"])
                self.assertTrue(out["gap_reason"])
                self.assertEqual("complete", out["cpic_basis"]["status"])
                self.assertEqual(before, row)

    def test_quote_cannot_borrow_note_support_and_each_refreshed_field_invalidates_identity(self):
        for change in ({"source": None}, {"mechanism": None}, {"basis_quote_sha256": None},
                       {"recommendation": "REFRESHED_QUOTATION"}, {"implication": "REFRESHED_IMPLICATION"},
                       {"phenotype": "Different phenotype"}, {"classification": "Different class"}):
            row = _supported()
            row["cpic"].update(change)
            before = copy.deepcopy(row)
            out = _guard_guidance(row)
            self.assertFalse(out["interpretation_withheld"])
            self.assertEqual("SYNTHETIC_OWN_NOTE", out["note"])
            self.assertIsNone(out["cpic"])
            self.assertEqual("incomplete", out["cpic_basis"]["status"])
            self.assertEqual(before, row)

    def test_complete_independent_basis_keeps_both_and_gene_role_is_not_inherited(self):
        row = _supported()
        out = _guard_guidance(row)
        self.assertEqual("complete", out["conclusion_basis"]["status"])
        self.assertEqual("complete", out["cpic_basis"]["status"])
        self.assertEqual(row["cpic"], out["cpic"])
        role = _guard_gene_role({**row, "why": "GENE_ROLE"})
        self.assertEqual("incomplete", role["basis"]["status"])
        self.assertNotEqual("GENE_ROLE", role["text"])
        role = _guard_gene_role({"why": "GENE_ROLE", "gene_role_basis": row})
        self.assertEqual("GENE_ROLE", role["text"])

    def test_empty_or_malformed_claims_do_not_turn_a_stored_level_into_assessment(self):
        for note in (None, "", " ", [], 3, {}, {"en": "Only English"}):
            out = _guard_guidance({**_supported(), "note": note})
            self.assertTrue(out["interpretation_withheld"])
            self.assertEqual("unknown", out["level"])
            self.assertEqual("low", out["catalogue_level"])
            self.assertIn("claim_text", out["conclusion_basis"]["missing"])
        row = _supported()
        row["note"] = {"en": "EN", "ru": "RU"}
        self.assertFalse(_guard_guidance(row)["interpretation_withheld"])
        for quote in (None, [], 5):
            self.assertIsNone(_guard_guidance({**row, "cpic": quote})["cpic"])
        cp = row["cpic"]
        for recommendation in (None, "", [], " "):
            cp["recommendation"] = recommendation
            cp["basis_quote_sha256"] = _quote_digest(cp)
            self.assertIsNone(_guard_guidance(row)["cpic"])

    def test_missing_translation_cannot_be_hidden_by_knowledge_localisation(self):
        for language in ("en", "ru"):
            for owner in ("note", "quote"):
                row = _supported()
                spec = row if owner == "note" else row["cpic"]
                spec["mechanism"] = {"en": "ONLY_EN"}
                out = _guard_guidance(core._localize_tree(row, language))
                basis = out["conclusion_basis"] if owner == "note" else out["cpic_basis"]
                self.assertEqual("incomplete", basis["status"])
                self.assertIn("mechanism", basis["missing"])
            row = _supported()
            row["note"] = {"en": "ONLY_EN"}
            self.assertTrue(_guard_guidance(core._localize_tree(row, language))["interpretation_withheld"])
            role = _guard_gene_role({"gene_role_basis": _supported(), "why": None})
            self.assertEqual("incomplete", role["basis"]["status"])


class TestPrescribingOutput(_Demo):
    def setUp(self):
        super().setUp()
        ouroboros_tools.unpin_session()
        self.addCleanup(ouroboros_tools.unpin_session)
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_positive_and_negative_phenotypes_are_kept_without_unheld_interpretation(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for code in ("NM", "PM", "unknown", "reported"):
                with mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, {"CYP2D6": code})):
                    row = pgx.check_drug_gene("codeine")
                    check = engine.check_new_prescription("codeine")
                self.assertEqual(code, row["phenotype"])
                self.assertEqual("unknown", row["level"])
                self.assertTrue(row["guidance_gap"])
                self.assertTrue(row["interpretation_withheld"])
                self.assertIsNone(row["cpic"])
                self.assertNotEqual("low", check["overall"])
                self.assertEqual("no_rule", check["genetic_context"]["verdict"]["kind"])
                self.assertIn(row["guidance_gap_reason"], fmt.drug_check(row))
                if code == "unknown":
                    self.assertIn(i18n.t("drug.phenotype_not_determined", gene="CYP2D6"), row["recommendation"])
                if code == "reported":
                    self.assertIn("Synthetic reading", row["recommendation"])

    def test_other_drug_aliases_and_conflicting_names_do_not_borrow_a_table(self):
        for drug in ("esomeprazole", "sertraline", "escitalopram", "imipramine", "mercaptopurine",
                     "simvastatin or atorvastatin", "codeine + tramadol"):
            with mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, {})):
                row = pgx.check_drug_gene(drug)
            self.assertEqual("drug_table_mismatch", row["guidance_applicability"]["status"], drug)
            self.assertIsNone(row["cpic"])
            self.assertTrue(row["guidance_gap"])

    def test_indication_is_not_invented_from_the_drug_name(self):
        for drug in ("clopidogrel", "azathioprine", "amitriptyline"):
            with mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, {})):
                row = pgx.check_drug_gene(drug)
            self.assertEqual("indication_unheld", row["guidance_applicability"]["status"])
            self.assertIsNone(row["cpic"])
            self.assertEqual("unknown", row["level"])
            self.assertIsNone(row["driving_gene"])

    def test_supported_note_and_quote_have_independent_basis_in_text_and_raw_output(self):
        book = copy.deepcopy(core.cpic_kb())
        entry = next(d for d in book["drugs"] if d.get("cpic_drug") == "codeine")
        entry["guidance"]["NM"] = _supported()
        with (mock.patch.object(core, "cpic_kb", return_value=book),
              mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, {}))):
            row = pgx.check_drug_gene("codeine")
        text = fmt.drug_check(row)
        for field in ("OWN_MECHANISM", "Synthetic PMID:2", "QUOTE_MECHANISM", "Synthetic PMID:3", "SYNTHETIC_QUOTATION"):
            self.assertIn(field, text)
        self.assertEqual("low", row["level"])
        self.assertFalse(row["interpretation_withheld"])

    def test_an_empty_guidance_book_is_a_named_gap_not_a_negative_reading(self):
        book = copy.deepcopy(core.cpic_kb())
        entry = next(d for d in book["drugs"] if d.get("cpic_drug") == "codeine")
        entry["guidance"] = {}
        with (mock.patch.object(core, "cpic_kb", return_value=book),
              mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, {}))):
            row = pgx.check_drug_gene("codeine")
        self.assertEqual("unknown", row["level"])
        self.assertEqual("NM", row["phenotype"])
        self.assertTrue(row["guidance_gap"])
        self.assertIn(i18n.t("drug.no_guidance_for_phenotype", phenotype="NM", gene="CYP2D6"), row["recommendation"])

    def test_refreshed_local_quote_cannot_inherit_the_previous_support(self):
        book = copy.deepcopy(core.cpic_kb())
        entry = next(d for d in book["drugs"] if d.get("cpic_drug") == "codeine")
        entry["guidance"]["NM"] = _supported()
        upstream = [{"phenotypes": {"CYP2D6": "Normal Metabolizer"},
                     "drugrecommendation": "REFRESHED_QUOTATION", "classification": "Synthetic classification"}]
        sources._import_cpic_recommendations(lambda _: upstream, book, [])
        book["_meta"]["updated"] = "2099-01-01"
        with mock.patch.dict(os.environ, {"SCHOLION_REPO_DIR": str(self.prof.parent)}):
            local = core.knowledge_dir_local() / "cpic_drug_gene.json"
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_text(json.dumps(book), encoding="utf-8")
            before = local.read_bytes()
            core.reset_cache()
            with mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, {})):
                row = pgx.check_drug_gene("codeine")
            self.assertEqual("local_newer", core.knowledge_precedence(local.name)["why"])
            self.assertEqual("complete", row["conclusion_basis"]["status"])
            self.assertIsNone(row["cpic"])
            self.assertIn("quote_identity", row["cpic_basis"]["missing"])
            self.assertEqual(before, local.read_bytes())
        core.reset_cache()

    def test_online_held_note_and_quote_use_the_same_independent_guard(self):
        info = {"name": "Synthetic online", "internal_class": "opioid", "atc": []}
        for row in (_supported(), {**_supported(), "source": None}):
            with (mock.patch.object(drugsource, "resolve_drug", return_value=info),
                  mock.patch.object(drugsource, "class_gene", return_value=("CYP2D6", "UNHELD_ROLE")),
                  mock.patch.object(pgx, "_guidance_for", return_value={"NM": row}),
                  mock.patch.object(pgx, "compute_phenotype", side_effect=lambda g: _phenotype(g, {}))):
                out = pgx._check_drug_online("Synthetic online")
            self.assertEqual("NM", out["phenotype"])
            self.assertNotIn("UNHELD_ROLE", out["why"])
            self.assertEqual("complete", out["cpic_basis"]["status"])
            self.assertEqual(bool(row.get("source")), out["level"] == "low")

    def test_supported_dpyd_warning_survives_in_drug_prescribing_and_agent_output(self):
        self.files["pharmacogenomics.json"]["star_alleles"] = {
            "DPYD": {"diplotype": "*2A/*2A", "phenotype": "Poor Metabolizer", "source": "Synthetic fixture"}}
        self.write(self.files)
        for language in ("en", "ru"):
            i18n.set_lang(language)
            core.reset_cache()
            for drug in ("5-fu", "capecitabine", "fluorouracil"):
                row = pgx.check_drug_gene(drug)
                rx = engine.check_new_prescription(drug)
                self.assertEqual("PM", row["phenotype"])
                self.assertEqual("high", row["level"])
                self.assertEqual("high", rx["overall"])
                self.assertFalse(row["guidance_gap"])
                self.assertIsNone(row["cpic"])
                self.assertEqual("*2A/*2A", row["markers_found"][0]["diplotype"])
                for text in (fmt.drug_check(row), fmt.prescription_check(rx)):
                    self.assertIn(row["recommendation"], text)
                    self.assertIn("29152729", text)
                    self.assertIn(row["mechanism"], text)
                    self.assertNotIn("Avoid use", text)
                for command in ("drug", "prescription"):
                    output = io.StringIO()
                    with redirect_stdout(output):
                        self.assertEqual(0, cli.main([command, drug, "--json"]))
                    value = json.loads(output.getvalue())
                    self.assertEqual("high", value["level"] if command == "drug" else value["overall"])
                ouroboros_tools.unpin_session()
                value = mcp_server.call_tool("sch_check_drug_gene", {"drug": drug})
                self.assertFalse(value.get("isError"), value)
                self.assertIn("29152729", "\n".join(c.get("text", "") for c in value["content"]))

    @unittest.skipUnless(shutil.which("node"), "needs Node to execute the page renderer")
    def test_actual_browser_renderer_keeps_supported_basis_and_never_prints_a_withheld_quote(self):
        good = _guard_guidance(_supported())
        held = _guard_guidance({**_supported(), "source": None, "cpic": {"recommendation": "NEVER_PRINT"}})
        page = (Path(support.SRC) / "scholion/web/index.html").read_text(encoding="utf-8")
        functions = []
        for name in ("pgxCard", "referenceContextHtml", "mechanismHtml"):
            start = page.index("function " + name + "(")
            functions.append(page[start:page.index("\n}\n", start) + 2])
        data = [{**r, "status": "ok", "drug": "Synthetic", "gene": "GENE", "phenotype": "NM",
                 "recommendation": r["note"], "co_genes": [], "markers_found": [
                     {"diplotype": "*2A/*2A", "phenotype_text": "Synthetic phenotype", "source": "Synthetic fixture"}]} for r in (good, held)]
        script = "const assert=require('node:assert/strict'),esc=x=>String(x??''),t=(k,a)=>k+JSON.stringify(a||{}),badge=()=>'',LEVEL={unknown:{},low:{}};\n"
        script += "\n".join(functions) + "\nconst data=" + json.dumps(data) + ";\n"
        script += "const good=pgxCard(data[0]),held=pgxCard(data[1]);for(const s of ['OWN_MECHANISM','QUOTE_MECHANISM','Synthetic PMID:2','Synthetic PMID:3','SYNTHETIC_QUOTATION','*2A/*2A','Synthetic fixture','data-called-diplotype'])assert.ok(good.includes(s));assert.ok(!held.includes('NEVER_PRINT'));assert.ok(held.includes('data-quote-withheld'));"
        result = subprocess.run([shutil.which("node"), "-e", script], text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
