"""A partial C17 integration: curated positions, not every clinical output."""
from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

import support  # noqa: F401 -- source import path and synthetic environment
from scholion import i18n
from scholion.conclusion_basis import conclusion_basis, guard_position, source_has_identifier
from scholion import core
from scholion.engine import panel_book, panel_catalogue, panel_form, system_panels as SP
from scholion.format_primitives import genotype_conclusion_lines
from scholion.format_system import _system_gene_row


class TestBasis(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_identifiers_are_structural_not_a_free_form_guideline_name(self):
        for value in ("PMID:1", "PMID 35152405", "DOI:10.1002/cpt.2557",
                      "https://pubmed.ncbi.nlm.nih.gov/35152405/"):
            self.assertTrue(source_has_identifier(value), value)
        for value in (None, 12345, {}, [], "", "CPIC", "PMID:0000", "PMID:TBD", "10./missing"):
            self.assertFalse(source_has_identifier(value), value)

    def test_bilingual_support_and_missing_fields_without_mutation(self):
        spec = {"source": "PMID:35152405", "mechanism": {"en": "EN context", "ru": "RU context"}}
        before = copy.deepcopy(spec)
        for language in ("en", "ru"):
            i18n.set_lang(language)
            basis = conclusion_basis(spec)
            self.assertEqual("complete", basis["status"])
            self.assertEqual(spec["mechanism"][language], basis["mechanism"])
            self.assertIsNone(basis["reason"])
            for bad in (None, {}, [], 1, True, " ", {"en": "EN"}, {"ru": "RU"},
                        {"en": "EN", "ru": " "}, {"en": "EN", "ru": 4}):
                got = conclusion_basis({**spec, "mechanism": bad})
                self.assertEqual(["mechanism"], got["missing"])
                self.assertIn(i18n.t("conclusion.missing.mechanism"), got["reason"])
        self.assertEqual(before, spec)
        self.assertEqual(["source_identifier", "mechanism"], conclusion_basis(None)["missing"])
        self.assertEqual("complete", conclusion_basis({"evidence": {"source": "PMID:35152405"},
                                                       "mechanism": "Already localised"})["status"])
        self.assertEqual(["source_identifier"], conclusion_basis({"evidence": "bad",
                                                                 "mechanism": "Context"})["missing"])

    def test_missing_support_keeps_reading_and_level_but_no_positive_or_negative_claim(self):
        for state in ("het", "hom", "absent", "unread"):
            row = {"rsid": "rs1", "level": "A", "state": state, "read": state != "unread",
                   "genotype": {"state": state}, "text": "Unsupported conclusion",
                   "findings": 1, "carrier": True, "mechanism": "Unsourced mechanism",
                   "effect_size": "Unsupported effect", "expect_check": {"position": "within"},
                   "next_step": {"kind": "ask"}, "route": {"oral": "claim"},
                   "under_load": {"text": "claim"}, "author_note": {"kind": "opinion"}}
            before = copy.deepcopy(row)
            out = guard_position({}, row)
            for key in ("rsid", "level", "state", "read", "genotype", "author_note"):
                self.assertEqual(row[key], out[key])
            for key in ("text", "mechanism", "effect_size", "expect_check", "next_step", "route", "under_load"):
                self.assertIsNone(out[key])
            self.assertEqual(0, out["findings"])
            self.assertFalse(out["carrier"])
            self.assertTrue(out["pending"])
            self.assertEqual("conclusion_basis", out["pending_why"])
            self.assertEqual(before, row)

    def test_complete_support_preserves_the_claim_and_lower_levels_keep_their_own_policy(self):
        spec = {"source": "PMID:35152405", "mechanism": "Source-backed context"}
        row = {"level": "B", "text": "Supported conclusion", "findings": 1}
        out = guard_position(spec, row)
        self.assertEqual("complete", out.pop("conclusion_basis")["status"])
        self.assertEqual(row, out)
        for level in ("C", "D", "E", None):
            lower = {"level": level, "text": None, "passport": {"reported": "Hypothesis"}}
            out = guard_position({}, lower)
            self.assertIsNone(out.pop("conclusion_basis"))
            self.assertEqual(lower, out)

    def test_the_engine_reference_and_summaries_cannot_call_a_withheld_row_clear(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            original = core._read_knowledge("system_gene_panels.json")["systems"]["lipids"]["positions"][0]
            spec = {**original, "mechanism": None}
            for state in ("het", "absent", "unread"):
                with mock.patch.object(SP, "_genotype", return_value={"state": state,
                        "read": state != "unread", "genotype": "TC", "confidence": "called"}), \
                        mock.patch.object(SP, "_has_alignment", return_value=False):
                    row = SP._curated_rows("lipids", {"positions": [spec]}, [],
                                          {"status": "ok", "input_profile": "whole_genome"}, {})["rows"][0]
                self.assertEqual(state, row["state"])
                self.assertEqual("A", row["level"])
                self.assertIsNone(row["text"])
                self.assertEqual("incomplete", row["conclusion_basis"]["status"])
                position = SP._position_state(row)
                self.assertEqual(row["conclusion_basis"], position["conclusion_basis"])
                v = panel_form.verdict([row], {"status": "ok"})
                self.assertEqual("not_determined", v["kind"])
                self.assertEqual(1, v["withheld"])
                self.assertIn(i18n.t("screen.why.conclusion_basis"), panel_form.verdict_line(v))
                self.assertIn(row["conclusion_basis"]["reason"], "\n".join(genotype_conclusion_lines([position])))
                for register in ("patient", "clinician"):
                    projected = SP._project({"rows": [row]}, register)["rows"][0]
                    self.assertIn(row["conclusion_basis"]["reason"], _system_gene_row(projected, register))
            reference = panel_catalogue._position(spec)
            self.assertEqual({}, reference["text"])
            self.assertIsNone(reference["expect"])
            self.assertIsNone(reference["mechanism"])

    def test_a_supported_finding_does_not_hide_another_rows_missing_basis(self):
        held = guard_position({}, {"gene": "A", "level": "B", "findings": 0, "read": True})
        v = panel_form.verdict([held, {"gene": "B", "findings": 1, "read": True}], {"status": "ok"})
        self.assertEqual("finding", v["kind"])
        self.assertEqual(1, v["withheld"])
        self.assertIn(i18n.t("conclusion.withheld_count", n=1), panel_form.verdict_line(v))

    def test_observed_allele_counts_are_not_reduced_by_missing_interpretation(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            held = guard_position({}, {"gene": "A", "rsid": "rs1", "level": "B",
                                       "state": "het", "read": True, "findings": 1})
            text = "\n".join(genotype_conclusion_lines([held]))
            self.assertIn(i18n.t("system.panel.conclusion_found", found=1,
                                positions=i18n.plural(1, "count.positions"), genes="A rs1"), text)
            self.assertIn(held["conclusion_basis"]["reason"], text)
            self.assertEqual(0, held["findings"])

    def test_missing_support_does_not_erase_other_reasons_to_withhold(self):
        row = {"level": "A", "pending_why": "no_text_for_state",
               "not_a_finding_why": "needs_confirmation", "needs_confirmation": True}
        out = guard_position({}, row)
        for key in row:
            self.assertEqual(row[key], out[key])
        self.assertEqual("incomplete", out["conclusion_basis"]["status"])

    def test_an_unavailable_genome_does_not_hide_the_independent_basis_gap(self):
        held = guard_position({}, {"gene": "A", "level": "B", "read": False})
        for language in ("en", "ru"):
            i18n.set_lang(language)
            v = panel_form.verdict([held], {"status": "unavailable", "reason": "genome_not_connected"})
            self.assertEqual("not_determined", v["kind"])
            self.assertEqual("genome_not_connected", v["why"])
            self.assertEqual(1, v["withheld"])
            self.assertIn(i18n.t("conclusion.withheld_count", n=1), panel_form.verdict_line(v))

    def test_localisation_cannot_hide_a_missing_mechanism_translation(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for mechanism in ({"en": "Only EN"}, {"ru": "Only RU"},
                              {"en": "EN", "ru": " "}, {"en": "EN", "ru": 1}):
                raw = {"source": "PMID:1", "mechanism": mechanism, "label": {"en": "Fallback label"}}
                local = core._localize_tree(raw, language)
                self.assertEqual("Fallback label", local["label"])
                self.assertIsNone(local["mechanism"])
                self.assertEqual(["mechanism"], conclusion_basis(local)["missing"])
            raw = {"mechanism": {"en": "EN", "ru": "RU"}}
            self.assertEqual(language.upper(), core._localize_tree(raw, language)["mechanism"])

    def test_populated_curated_mechanisms_have_both_languages_in_the_raw_book(self):
        found = 0
        for filename, container in (("system_gene_panels.json", "systems"), ("on_demand_panels.json", "panels")):
            book = json.loads((support.SRC / "scholion/knowledge" / filename).read_text(encoding="utf-8"))
            for spec in book[container].values():
                for entry in spec.get("positions", []) + spec.get("groups", []):
                    if entry.get("mechanism"):
                        found += 1
                        self.assertIsInstance(entry["mechanism"], dict)
                        for language in ("en", "ru"):
                            self.assertTrue(entry["mechanism"].get(language, "").strip())
        self.assertGreaterEqual(found, 14)

    def test_a_groups_own_basis_cannot_be_borrowed_from_its_members(self):
        position = {"unit": "position", "rsid": "rs1", "gene": "G", "level": "A",
                    "state": "het", "read": True, "text": "Supported member",
                    "conclusion_basis": {"status": "complete"}}
        group = {"key": "g", "positions": ["rs1"], "evidence": {"level": "A"},
                 "text": {"en": "Group claim", "ru": "Group claim (ru)"}, "source": "PMID:1"}
        for language in ("en", "ru"):
            i18n.set_lang(language)
            out = panel_book._groups("test", {"groups": [group]}, [dict(position)])[0]
            self.assertIsNone(out["text"])
            self.assertEqual(["mechanism"], out["conclusion_basis"]["missing"])
            self.assertEqual("het", out["members"][0]["state"])
            self.assertEqual(1, out["count"])
            supported = {**group, "mechanism": {"en": "Mechanism", "ru": "Mechanism (ru)"}}
            out = panel_book._groups("test", {"groups": [supported]}, [dict(position)])[0]
            self.assertEqual(supported["text"][language], out["text"])
            self.assertEqual(supported["mechanism"][language], out["mechanism"])

    def test_a_marker_does_not_restore_a_withheld_interpretation(self):
        position = {"gene": "G", "rsid": "rs1", "evidence": {"level": "A"},
                    "expect": {"marker": "test", "direction": "higher"}}
        for language in ("en", "ru"):
            i18n.set_lang(language)
            with mock.patch.object(SP, "_curated", return_value={"systems": {"test": {"positions": [position]}}}):
                out = panel_book.positions_by_marker()["test"][0]
            self.assertEqual("rs1", out["rsid"])
            self.assertEqual("A", out["level"])
            self.assertIsNone(out["direction"])
            self.assertEqual("incomplete", out["conclusion_basis"]["status"])
