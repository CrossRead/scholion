"""A source-backed position does not validate its route, expectation or next step."""
from __future__ import annotations

import copy
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, i18n
from scholion import format as fmt
from scholion.conclusion_basis import guard_position, guard_subclaims, subclaim_bases
from scholion.engine import panel_book, panel_catalogue, system_panels as SP
from scholion.format_primitives import genotype_conclusion_lines, subclaim_lines
from scholion.format_system import _system_gene_row


class TestIndependentClaims(unittest.TestCase):
    BASIS = {"source": "Synthetic PMID:1", "mechanism": {"en": "Synthetic mechanism", "ru": "Synthetic mechanism"}}
    FIELDS = {"expect": "expect_check", "route": "route", "under_load": "under_load", "next_step": "next_step"}

    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_a_parent_never_supplies_a_missing_subclaim_basis(self):
        for name, destination in self.FIELDS.items():
            for own_basis in ({}, {"source": "Synthetic PMID:1"}, {"mechanism": "Unreferenced"}):
                spec = {**self.BASIS, name: own_basis}
                row = {"level": "B", "read": True, "state": "het", "genotype": {"genotype": "A/G"},
                       "text": "Supported main text", destination: {"claim": "WITHDRAWN"}}
                before = copy.deepcopy((spec, row))
                out = guard_position(spec, row)
                self.assertIsNone(out[destination])
                self.assertEqual("Supported main text", out["text"])
                self.assertEqual("incomplete", out["subclaim_basis"][name]["status"])
                for key in ("genotype", "read", "state", "level"):
                    self.assertEqual(row[key], out[key])
                self.assertEqual(before, (spec, row))

    def test_supported_subclaims_carry_their_own_basis(self):
        for name, destination in self.FIELDS.items():
            for reference in (False, True):
                dest = name if reference else destination
                out = guard_subclaims({**self.BASIS, name: self.BASIS},
                                      {"level": "A", dest: {"claim": "Synthetic claim"}}, reference=reference)
                self.assertEqual("Synthetic claim", out[dest]["claim"])
                self.assertEqual("complete", out[dest]["conclusion_basis"]["status"])
                self.assertIn("Synthetic mechanism", "\n".join(subclaim_lines(out)))
                # A reference surface need not print every kind of adjacent claim.
                missing_surface = guard_subclaims({**self.BASIS, name: self.BASIS}, {"level": "A"})
                self.assertNotIn(destination, missing_surface)

    def test_lower_levels_and_unsupported_parents_cannot_restore_actions(self):
        for level in ("C", "D", "E", None):
            out = guard_position({**self.BASIS, "next_step": self.BASIS},
                                 {"level": level, "next_step": {"text": "WITHDRAWN"}})
            self.assertIsNone(out["next_step"])
            self.assertEqual(["evidence_level"], out["subclaim_basis"]["next_step"]["missing"])
        out = guard_subclaims({"expect": self.BASIS}, {"level": "B", "expect_check": {"direction": "higher"}})
        self.assertEqual(["parent_basis"], out["subclaim_basis"]["expect"]["missing"])
        self.assertIsNone(out["expect_check"])
        self.assertEqual({}, subclaim_bases(self.BASIS, "B"))

    def test_bilingual_completeness_is_not_hidden_by_localization(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            spec = {**self.BASIS, "route": {"source": "Synthetic PMID:1", "mechanism": {"en": "Only English"}}}
            basis = subclaim_bases(core._localize_tree(spec, language), "B")["route"]
            self.assertEqual(["mechanism"], basis["missing"])
            self.assertNotIn("⟦", basis["reason"])

    def test_the_reference_book_and_marker_index_share_the_gate(self):
        original = core._read_knowledge("system_gene_panels.json")["systems"]["renal"]["positions"]
        spec = next(p for p in original if p.get("rsid") == "rs2231142")
        reference = panel_catalogue._position(spec)
        self.assertEqual("complete", reference["conclusion_basis"]["status"])
        self.assertIsNone(reference["expect"])
        self.assertEqual("incomplete", reference["subclaim_basis"]["expect"]["status"])
        with mock.patch.object(panel_book, "_curated", return_value={"systems": {"renal": {"positions": [spec]}}}):
            row = panel_book.positions_by_marker()[spec["expect"]["marker"]][0]
        self.assertIsNone(row["direction"])
        self.assertEqual(reference["subclaim_basis"], row["subclaim_basis"])
        supported = {**spec, "expect": {**spec["expect"], **self.BASIS}}
        with mock.patch.object(panel_book, "_curated", return_value={"systems": {"renal": {"positions": [supported]}}}):
            row = panel_book.positions_by_marker()[spec["expect"]["marker"]][0]
        self.assertEqual(spec["expect"]["direction"], row["direction"])

    def test_engine_projection_and_text_keep_readings_and_explicit_reasons(self):
        raw = core._read_knowledge("system_gene_panels.json")["systems"]["amino_acids"]
        spec = next(p for p in raw["positions"] if p.get("rsid") == "rs2231142")
        for language in ("en", "ru"):
            i18n.set_lang(language)
            with mock.patch.object(SP, "_genotype", return_value={"state": "het", "read": True,
                                   "genotype": "G/T", "confidence": "called"}), \
                    mock.patch.object(SP, "_has_alignment", return_value=False):
                row = SP._curated_rows("amino_acids", {**raw, "positions": [spec]}, [],
                                      {"status": "ok", "input_profile": "whole_genome"}, {})["rows"][0]
            self.assertIsNone(row["route"])
            self.assertTrue(row["read"])
            position = SP._position_state(row)
            reason = row["subclaim_basis"]["route"]["reason"]
            self.assertEqual(row["subclaim_basis"], position["subclaim_basis"])
            self.assertIn(reason, "\n".join(genotype_conclusion_lines([position])))
            for register in ("patient", "clinician"):
                projected = SP._project({"rows": [row]}, register)["rows"][0]
                self.assertEqual(row["subclaim_basis"], projected["subclaim_basis"])
                self.assertIn(reason, _system_gene_row(projected, register))

    def test_a_supported_next_step_reaches_each_basket_with_its_own_basis(self):
        from tests.test_a_system_answers_with_its_seven_layers import _pos
        for kind in SP.BASKETS:
            for supported in (True, False):
                own = {"kind": kind, "text": "Synthetic next step", "source": "Synthetic PMID:3"}
                if supported:
                    own["mechanism"] = "Independent synthetic next-step mechanism"
                pos = _pos("rs1", "G1", next_step=own)
                with mock.patch.object(SP, "_base", return_value={}), \
                        mock.patch.object(SP, "_curated", return_value={"systems": {"thyroid": {"positions": [pos]}}}), \
                        mock.patch("scholion.genome.available", return_value={"ready": True}), \
                        mock.patch.object(SP, "_clinvar_by_gene", return_value={"status": "ok", "by_gene": {}}), \
                        mock.patch.object(SP, "_genotype", return_value={"state": "het", "read": True,
                                          "genotype": "A/G", "confidence": "called"}), \
                        mock.patch.object(SP, "_has_alignment", return_value=False):
                    card = SP.system("thyroid", "clinician")
                steps = [r for r in card["next"][kind]["rows"] if r["origin"] == "author"]
                self.assertEqual(int(supported), len(steps), (kind, card["next"]))
                text = fmt.system_report(card)
                if supported:
                    self.assertEqual("complete", steps[0]["conclusion_basis"]["status"])
                    self.assertEqual(own["mechanism"], steps[0]["mechanism"])
                    self.assertEqual(own["source"], steps[0]["source"])
                    self.assertIn(own["mechanism"], text)
                else:
                    self.assertNotIn(own["text"], text)

    def test_coverage_belongs_to_its_gene_not_the_last_row_or_an_unread_group(self):
        rows = [{"unit": "gene", "gene": "G1", "read": True, "coverage": {"state": "low", "pct_20x": 42}},
                {"unit": "gene", "gene": "G2", "read": False, "read_why": "unknown"}]
        for subset in (rows, rows[:1]):
            baskets = SP._next({"source": "labs"}, {"status": "composed", "scan": {"status": "ok"},
                               "rows": subset}, {}, {}, {})
            cov = [r for r in baskets["genome"]["rows"] if r["origin"] == "coverage"]
            self.assertEqual(["G1"], [r["gene"] for r in cov])
            self.assertIn("42", cov[0]["text"])

    def test_a_next_step_keeps_its_own_evidence_source_without_borrowing_the_parent(self):
        own = {"kind": "lab", "text": "Synthetic step", "evidence": {"source": "Synthetic PMID:3"},
               "mechanism": "Independent synthetic step mechanism"}
        row = guard_position({**self.BASIS, "next_step": own},
                             {"level": "B", "gene": "G1", "next_step": own})
        result = SP._next({"source": "labs"}, {"status": "composed", "rows": [row]}, {}, {}, {})
        step = result["lab"]["rows"][0]
        self.assertEqual(own["evidence"]["source"], step["source"])
        self.assertNotEqual(self.BASIS["source"], step["source"])
        self.assertEqual(own["mechanism"], step["mechanism"])
