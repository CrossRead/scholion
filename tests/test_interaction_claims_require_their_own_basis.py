"""A class match stays an observation; unsupported effects are not a clearance."""
from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from scholion import cli, core, engine, format as fmt, i18n, mcp_server, ouroboros_tools
from scholion.engine import pgx
from scholion.interaction_basis import _guard, matched_rows
from tests.test_a_genotype_in_the_profile_is_never_shown_as_unread import _Demo


def supported():
    return {"a": "A", "b": "B", "severity": "high", "effect": "SYNTHETIC_EFFECT",
            "source": "Synthetic PMID:2", "mechanism": {"en": "EFFECT_MECHANISM", "ru": "EFFECT_MECHANISM"},
            "manage": "SYNTHETIC_MANAGEMENT", "manage_basis": {"source": "Synthetic PMID:3",
            "mechanism": {"en": "MANAGEMENT_MECHANISM", "ru": "MANAGEMENT_MECHANISM"}}}


class TestIndependentStatements(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_missing_effect_basis_withholds_severity_not_the_pair(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for severity in ("high", "low"):
                for change in ({"source": None}, {"source": "Guideline"}, {"source": "PMID:TBD"},
                               {"source": []}, {"mechanism": None}, {"mechanism": " "},
                               {"mechanism": {"en": "ONE_LANGUAGE"}}):
                    row = {**supported(), "severity": severity, **change}
                    before = copy.deepcopy(row)
                    out = _guard(row, True)
                    self.assertTrue(out["interpretation_withheld"])
                    self.assertEqual("unknown", out["severity"])
                    self.assertEqual(severity, out["catalogue_severity"])
                    self.assertEqual("A", out["a"])
                    self.assertNotIn("SYNTHETIC_EFFECT", out["effect"])
                    self.assertIsNone(out["manage"])
                    self.assertIsNone(out["mechanism"])
                    self.assertIn("parent_basis", out["management_basis"]["missing"])
                    self.assertEqual(before, row)

    def test_management_cannot_borrow_its_effects_basis(self):
        for change in (None, {}, {"source": "Synthetic PMID:3"},
                       {"mechanism": "MANAGEMENT_MECHANISM"}):
            row = {**supported(), "manage_basis": change}
            out = _guard(row, True)
            self.assertFalse(out["interpretation_withheld"])
            self.assertEqual("high", out["severity"])
            self.assertEqual("SYNTHETIC_EFFECT", out["effect"])
            self.assertIsNone(out["manage"])
            self.assertEqual("incomplete", out["management_basis"]["status"])
        out = _guard(supported(), True)
        self.assertEqual("SYNTHETIC_MANAGEMENT", out["manage"])
        self.assertEqual("complete", out["management_basis"]["status"])
        out = _guard({**supported(), "manage": None}, True)
        self.assertIsNone(out["management_basis"])

    def test_missing_statement_and_translation_cannot_hide_behind_support(self):
        for field in ("effect", "manage"):
            for text in ([], 1, " ", {"en": "ONE_LANGUAGE"}):
                row = {**supported(), field: text}
                out = _guard(row, True)
                if field == "effect":
                    self.assertTrue(out["interpretation_withheld"])
                else:
                    self.assertIsNone(out["manage"])
            row = {**supported(), field: {"en": "ONLY_EN"}}
            for language in ("en", "ru"):
                out = _guard(core._localize_tree(row, language), True)
                self.assertTrue(out["interpretation_withheld"] if field == "effect" else out["manage"] is None)
        row = {**supported(), "effect": {"en": "EN", "ru": "RU"}}
        self.assertFalse(_guard(row, True)["interpretation_withheld"])

    def test_scope_and_mixed_partners_preserve_each_observation(self):
        names = {"A": {"names": ["HeldDrug", "OtherDrug"]}}
        rule = {**supported(), "drug_scope": {"A": {"names": ["HeldDrug"]}}}
        rows = matched_rows(rule, "Partner", ["B"], "A", ["HeldDrug 20 mg", "OtherDrug"], names, pgx.name_matches)
        self.assertEqual(2, len(rows))
        self.assertEqual(["HeldDrug 20 mg"], rows[0]["with_meds"])
        self.assertEqual("high", rows[0]["severity"])
        self.assertEqual("unknown", rows[1]["severity"])
        self.assertEqual(["OtherDrug"], rows[1]["with_meds"])
        for new in ("OtherDrug", "HeldDrug or OtherDrug"):
            out = matched_rows(rule, new, ["A"], "B", ["Partner"], names, pgx.name_matches)[0]
            self.assertTrue(out["interpretation_withheld"])
            self.assertIn("drug_scope", out["conclusion_basis"]["missing"])
        rows = matched_rows(rule, "HeldDrug", ["A"], "B", ["Partner"], names, pgx.name_matches)
        self.assertFalse(rows[0]["interpretation_withheld"])
        self.assertTrue(matched_rows(rule, "Partner", ["B"], "A", [], names, pgx.name_matches)[0]["interpretation_withheld"])
        self.assertFalse(matched_rows(supported(), "New", ["A"], "B", [], names, pgx.name_matches)[0]["interpretation_withheld"])


class TestInteractionOutputs(_Demo):
    def setUp(self):
        super().setUp()
        self.addCleanup(i18n.set_lang, i18n.lang())
        ouroboros_tools.unpin_session()
        self.addCleanup(ouroboros_tools.unpin_session)

    def meds(self, names):
        self.files["medications.json"]["medications"] = [
            {"name": name, "status": "active"} for name in names]
        self.write(self.files)
        core.reset_cache()

    def test_unheld_matching_rule_is_neither_silence_nor_a_green_verdict(self):
        self.meds(["atorvastatin"])
        for language in ("en", "ru"):
            i18n.set_lang(language)
            out = pgx.check_interactions("fluconazole")
            self.assertTrue(out["interactions"])
            row = out["interactions"][0]
            self.assertTrue(row["interpretation_withheld"])
            self.assertEqual(["atorvastatin"], row["with_meds"])
            self.assertFalse(out["baseline"]["empty"])
            rx = engine.check_new_prescription("fluconazole")
            self.assertNotEqual("low", rx["overall"])
            self.assertTrue(any(u["what"] == "interaction_basis" and u["detail"] == row["effect"] for u in rx["unresolved"]))
            text = fmt.prescription_check(rx)
            self.assertIn(row["effect"], text)
            self.assertNotIn(i18n.t("prescription.no_interactions"), text)
            self.assertNotIn("CYP3A4", text)

    def test_supported_warfarin_warning_remains_high_in_both_directions(self):
        for partner, new in (("warfarin", "ibuprofen"), ("ibuprofen", "warfarin")):
            self.meds([partner])
            for language in ("en", "ru"):
                i18n.set_lang(language)
                out = pgx.check_interactions(new)
                row = next(r for r in out["interactions"] if r["a"] == "anticoagulant_vka" and r["b"] == "nsaid")
                self.assertEqual("high", row["severity"])
                self.assertFalse(row["interpretation_withheld"])
                self.assertIsNone(row["manage"])
                rx = engine.check_new_prescription(new)
                self.assertEqual("high", rx["overall"])
                text = fmt.prescription_check(rx)
                self.assertIn(row["effect"], text)
                self.assertIn("32455439", text)
                self.assertIn(row["mechanism"], text)
                self.assertIn("🧬 **" + i18n.t("prescription.genome_header") + ":**", text)
                self.assertNotIn("gastroprotection", text)
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(0, cli.main(["prescription", new, "--json"]))
                self.assertEqual("high", json.loads(output.getvalue())["overall"])
                ouroboros_tools.unpin_session()
                answer = mcp_server.call_tool("sch_check_prescription", {"drug": new})
                self.assertFalse(answer.get("isError"), answer)
                self.assertIn("32455439", "\n".join(c.get("text", "") for c in answer["content"]))

    def test_mixed_vka_partners_keep_the_supported_warning_and_name_the_unheld_one(self):
        rule = next(r for r in core.drug_interactions()["interactions"] if r["a"] == "anticoagulant_vka" and r["b"] == "nsaid")
        held = rule["drug_scope"]["anticoagulant_vka"]["names"]
        for other in (n for n in core.med_classes()["classes"]["anticoagulant_vka"]["names"] if n not in held):
            self.meds(["warfarin", other])
            rx = engine.check_new_prescription("ibuprofen")
            rows = rx["interactions"]["interactions"]
            self.assertEqual({"warfarin", other}, {n for r in rows for n in r["with_meds"]})
            self.assertEqual("high", rx["overall"])
            self.assertTrue(any(r["interpretation_withheld"] and r["with_meds"] == [other] for r in rows))
            self.assertTrue(any(u.get("with_meds") == [other] for u in rx["unresolved"]))

    def test_supported_effect_does_not_license_a_management_statement(self):
        self.meds(["warfarin"])
        rule = {**supported(), "a": "anticoagulant_vka", "b": "nsaid", "manage_basis": None}
        with mock.patch.object(core, "drug_interactions", return_value={"interactions": [rule]}):
            rx = engine.check_new_prescription("ibuprofen")
        text = fmt.prescription_check(rx)
        self.assertEqual("high", rx["overall"])
        self.assertNotIn("SYNTHETIC_MANAGEMENT", text)
        self.assertIn("Synthetic PMID:2", text)
        self.assertTrue(any(u["what"] == "interaction_management" for u in rx["unresolved"]))
        rule["manage_basis"] = supported()["manage_basis"]
        with mock.patch.object(core, "drug_interactions", return_value={"interactions": [rule]}):
            text = fmt.prescription_check(engine.check_new_prescription("ibuprofen"))
        self.assertIn("SYNTHETIC_MANAGEMENT", text)
        self.assertIn("Synthetic PMID:3", text)
        self.assertIn("MANAGEMENT_MECHANISM", text)
