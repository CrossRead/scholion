"""A visit handout retains identity and sources without promoting hypotheses."""
from __future__ import annotations

import json
from unittest import mock

from scholion import engine, format as fmt, i18n, store, ouroboros_tools
from tests.test_ingest_reads_a_table import TableCase


class TestVisitSheet(TableCase):
    def test_sources_and_unassessed_values_survive_without_writing(self):
        source = {"path": "synthetic-form.pdf", "pages": [2, 3], "specimen": "blood"}
        self.assertTrue(store.add_lab_point("creatinine", "2026-02-01T08:30", 150,
                         unit="µmol/L", ref_low=60, ref_high=110, date_source="form",
                         reference_context={"source": source})["ok"])
        before = {p.name: p.read_bytes() for p in self.profile.iterdir()}
        data = engine.visit_sheet()
        self.assertEqual("visit_sheet", data["kind"])
        self.assertEqual(source, data["measurements"][0]["source"])
        self.assertEqual("form", data["measurements"][0]["date_source"])
        self.assertIn("version", data)
        self.assertIn("id", data["container"])
        self.assertFalse(data["reference_appendix"]["included"])
        text = fmt.visit_report(data)
        self.assertIn("synthetic-form.pdf", text)
        self.assertIn("2026-02-01T08:30", text)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.profile.iterdir()})

    def test_an_appendix_retains_passports_and_never_copies_a_clinical_text(self):
        from scholion.engine import system_panels
        position = {"gene": "SYNTHETIC", "rsid": "rs123", "level": "C", "read": True,
                    "state": "het", "text": "This must not enter the appendix as a clinical finding",
                    "interpretation": {"level": "C", "summary": "Recorded qualified interpretation",
                                       "notice": "Clinician qualification", "source": "PMID:123",
                                       "missing": ["mechanism"]},
                    "passport": {"level": "C", "reported": "A labelled hypothesis",
                                 "mechanism": "Recorded mechanism", "missing": ["replication"]},
                    "reference_context": {"scope": "reference_only", "gene_function": "Gene biology",
                                          "variant_context": "Variant context", "gene_source": "Gene source",
                                          "variant_source": "Variant source"}}
        with mock.patch.object(system_panels, "systems", return_value={"systems": [{"key": "synthetic"}]}), \
                mock.patch.object(system_panels, "system", return_value={"label": "Synthetic panel",
                          "genetics": {"positions": [position, {**position, "level": "A"}]}}):
            data = engine.visit_sheet(True)
        row = data["reference_appendix"]["panels"][0]["positions"][0]
        self.assertEqual(position["passport"], row["passport"])
        self.assertNotIn("text", row)
        self.assertEqual(1, len(data["reference_appendix"]["panels"][0]["positions"]))
        self.assertNotIn("This must not enter", json.dumps(data))
        text = fmt.visit_report(data)
        for expected in ("Synthetic panel", "SYNTHETIC rs123", "Recorded qualified interpretation",
                         "Clinician qualification", "PMID:123", "Gene biology", "Variant context",
                         "Gene source", "Variant source", "A labelled hypothesis", "Recorded mechanism",
                         i18n.t("system.hyp.name.replication")):
            self.assertIn(expected, text)
        self.assertNotIn("This must not enter", text)

    def test_the_tool_and_cli_options_reach_the_same_core_structure(self):
        from scholion import cli
        args = cli.build_parser().parse_args(["overview", "--visit-sheet", "--reference-appendix"])
        with mock.patch.object(engine, "visit_sheet", return_value={"kind": "visit_sheet"}) as read, \
                mock.patch.object(fmt, "visit_report", return_value="Synthetic visit sheet"):
            result, render = cli._cmd_overview(args)
            self.assertEqual("visit_sheet", result["kind"])
            self.assertEqual("Synthetic visit sheet", ouroboros_tools._h_overview(None, visit_sheet=True,
                                                                                  include_reference=True))
            self.assertEqual("Synthetic visit sheet", ouroboros_tools._h_overview.both(visit_sheet=True)[0])
            read.assert_any_call(True)

    def test_russian_sheet_has_translated_headings_and_date_basis(self):
        previous = i18n.lang()
        self.addCleanup(i18n.set_lang, previous)
        i18n.set_lang("ru")
        data = engine.visit_sheet()
        self.assertEqual(i18n.t("visit.title"), data["title"])
        self.assertNotIn("⟦", fmt.visit_report(data))
