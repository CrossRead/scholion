"""A reference explanation is neither a call nor analytical permission."""
from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

import support  # noqa: F401 -- source path and synthetic environment
from scholion import core, i18n
from scholion.conclusion_basis import guard_position
from scholion.engine import panel_catalogue, system_panels as SP
from scholion.format_genome import panel_report
from scholion.panel_reference import reference_context, reference_lines


class TestReferencePanels(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def positions(self):
        return [p for name, key in (("system_gene_panels.json", "systems"),
                                    ("on_demand_panels.json", "panels"))
                for s in core._read_knowledge(name)[key].values() for p in s.get("positions", [])]

    def test_every_curated_gene_has_bilingual_sourced_reference_biology(self):
        raw = json.loads(core.knowledge_path("panel_reference_context.json").read_text(encoding="utf-8"))
        seen = set()
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for p in self.positions():
                seen.add(p["gene"])
                context = reference_context(p, p["evidence"]["level"])
                with self.subTest(language=language, gene=p["gene"], rsid=p["rsid"]):
                    self.assertEqual(raw["genes"][p["gene"]]["description"][language], context["gene_function"])
                    self.assertTrue(context["gene_source"].startswith("https://www.ncbi.nlm.nih.gov/gene/"))
                    self.assertEqual("gene_function", context["gene_source_scope"])
                    self.assertTrue(context["variant_context"])
                    self.assertEqual("reference_only", context["scope"])
                    self.assertEqual(p["evidence"]["level"], context["level"])
        self.assertEqual(set(raw["genes"]), seen)
        # Retired NCBI records bearing the same symbol must not replace these.
        for gene, uid in (("CYP2C19", "1557"), ("CYP2R1", "120227"), ("PRKN", "5071")):
            self.assertTrue(raw["genes"][gene]["source"].endswith("/" + uid))

    def test_f2_and_f5_keep_their_mechanisms_at_every_reading_state_without_a_claim(self):
        i18n.set_lang("en")
        cardio = core._read_knowledge("system_gene_panels.json")["systems"]["cardio"]
        for rsid, word, pmid in (("rs6025", "protein C", "8164741"),
                                 ("rs1799963", "prothrombin", "8916933")):
            p = next(p for p in cardio["positions"] if p["rsid"] == rsid)
            for state in ("het", "hom", "absent", "unread"):
                geno = {"state": state, "read": state != "unread", "genotype": "GA" if state == "het" else None}
                with mock.patch.object(SP, "_genotype", return_value=geno), \
                        mock.patch.object(SP, "_has_alignment", return_value=False):
                    row = SP._curated_rows("cardio", {"positions": [p]}, [],
                        {"status": "ok", "input_profile": "whole_genome"}, {})["rows"][0]
                self.assertEqual(state, row["state"])
                self.assertEqual(geno["read"], row["read"])
                self.assertIn(word, row["reference_context"]["variant_context"])
                self.assertIn(pmid, row["reference_context"]["variant_source"])
                self.assertIsNone(row["text"])
                self.assertEqual(0, row["findings"])
                self.assertFalse(row["carrier"])
                self.assertEqual("incomplete", row["conclusion_basis"]["status"])
                self.assertEqual(row["reference_context"], SP._position_state(row)["reference_context"])
                for register in ("patient", "clinician"):
                    projected = SP._project({"rows": [row]}, register)
                    self.assertEqual(row["reference_context"], projected["rows"][0]["reference_context"])

    def test_reference_context_does_not_change_the_clinical_guard_or_subclaims(self):
        row = {"level": "A", "text": "bad clinical claim", "findings": 1, "carrier": True,
               "route": {"text": "unsupported action"}, "expect_check": {"marker": "LDL"}}
        context = {"scope": "reference_only", "gene_function": "biology", "variant_context": "association"}
        guarded = guard_position({}, row)
        richer = guard_position({}, {**row, "reference_context": context})
        self.assertEqual(context, richer.pop("reference_context"))
        self.assertEqual(guarded, richer)

    def test_lower_levels_and_e_retain_gene_biology_but_never_invent_an_allele_effect(self):
        for level in ("C", "D", "E"):
            p = {"gene": "F5", "rsid": "rs6025", "mechanism": "should not grant a claim"}
            context = reference_context(p, level)
            self.assertTrue(context["gene_source"])
            self.assertEqual(level, context["level"])
            if level == "E":
                self.assertEqual("not_curated", context["variant_status"])
                self.assertIsNone(context["variant_source"])
                self.assertEqual(i18n.t("reference.variant_unknown"), context["variant_context"])
            else:
                self.assertEqual("described", context["variant_status"])
        self.assertIn("not", reference_context({"gene": "unknown", "rsid": "rs0"}, None)["gene_function"])
        # Do not borrow another gene's rsID context, or an unsourced mechanism.
        changed = reference_context({"gene": "F2", "rsid": "rs6025", "mechanism": "unsourced"}, "D")
        self.assertEqual("not_curated", changed["variant_status"])
        self.assertEqual([], reference_lines({}))

    def test_the_reference_catalogue_and_report_work_without_reading_a_genome(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            with mock.patch.object(SP, "_genotype", side_effect=AssertionError("reference must not read")):
                r = panel_catalogue.panel_description("cardio")
            before = copy.deepcopy(r)
            rendered = panel_report(r)
            for p in r["positions"]:
                self.assertIn(p["reference_context"]["gene_function"], rendered)
                self.assertIn(p["reference_context"]["variant_context"], rendered)
                self.assertIn(i18n.t("reference.level", level=p["level"]), rendered)
            self.assertEqual(before, r)
            self.assertNotIn("5-fold", rendered)
            self.assertNotIn("transdermal", rendered)
            self.assertNotIn("2–3-fold", rendered)

    def test_explicit_mechanism_with_its_own_source_and_unknown_fields(self):
        i18n.set_lang("en")
        c = reference_context({"gene": "unknown", "rsid": "rs0", "mechanism": "held mechanism",
                               "evidence": {"source": "PMID:1"}}, "B")
        self.assertEqual("held mechanism", c["variant_context"])
        self.assertEqual("PMID:1", c["variant_source"])
        lines = reference_lines({"reference_context": c})
        self.assertTrue(any("PMID:1" in line for line in lines))
        self.assertFalse(any("Gene-function source" in line for line in lines))
