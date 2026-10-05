"""Source wording is shared reference material, never a genotype verdict."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, panel_notes
from scholion.engine import panel_catalogue, system_panels as SP
from scholion import i18n

KNOW = support.SRC / "scholion" / "knowledge"


class TestAuthorNotes(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        self.notes = json.loads((KNOW / "panel_author_notes.json").read_text(encoding="utf-8"))["notes"]
        self.intake = json.loads((KNOW / "panel_intake.json").read_text(encoding="utf-8"))

    def test_registry_has_original_translation_anonymous_review_and_cells(self):
        panel_notes.validate(self.notes, self.intake)
        self.assertEqual(5, len(self.notes))
        self.assertNotIn("rs3816873", self.notes)
        self.assertIn("rs17782313", self.notes)
        self.assertIn("rs1799768", self.notes, "unreadable is not silently discarded")
        for rsid, note in self.notes.items():
            self.assertNotEqual(note["ru"], note["en"], rsid)

    def test_unknown_position_and_incomplete_or_named_review_refuse(self):
        note = self.notes["rs6356"]
        for notes in (None, {}, {"rs000000": note}):
            with self.subTest(notes=notes), self.assertRaises(ValueError):
                panel_notes.validate(notes, self.intake)
        mutations = (("en", ""), ("ru", None), ("review", {}),
                     ("review", {"by_role": "named_person", "on": "2026-09-23", "scope": "author_wording"}),
                     ("review", {"by_role": "panel_author", "on": "2026-09", "scope": "author_wording"}),
                     ("review", {"by_role": "panel_author", "on": "20260923", "scope": "author_wording"}),
                     ("provenance", {"document_id": "x", "sha256": "bad", "cells": ["E9"]}))
        for key, value in mutations:
            bad = copy.deepcopy(note); bad[key] = value
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                panel_notes.validate({"rs6356": bad}, self.intake)
        bad = dict(note, genotype="AG")
        with self.assertRaises(ValueError):
            panel_notes.validate({"rs6356": bad}, self.intake)

    def test_original_is_retained_but_display_language_and_translation_are_explicit(self):
        for language in ("en", "ru"):
            with mock.patch.dict("os.environ", {"SCHOLION_LANG": language}):
                i18n.set_lang(language)
                n = panel_notes.author_note("rs6356", "D")
                self.assertEqual(n[language], n["text"])
                self.assertEqual(language == "en", n["translated"])
                self.assertEqual("D", n["level"])
                self.assertEqual("author_opinion_not_a_conclusion", n["interpretation"])
                self.assertIn(n["text"], panel_notes.note_lines(n))
                self.assertIn(n["label"], panel_notes.note_lines(n))
        self.assertIsNone(panel_notes.author_note("rs000000", "E"))
        self.assertEqual("", panel_notes.note_lines(None))

    def test_attaching_a_note_changes_neither_findings_nor_local_note(self):
        raw = json.loads((KNOW / "system_gene_panels.json").read_text(encoding="utf-8"))
        spec = raw["systems"]["gonads"]
        p = next(p for p in spec["positions"] if p["rsid"] == "rs5934505")
        with mock.patch.object(SP, "_genotype", return_value={"state": "hom", "read": True, "genotype": "TT"}), \
                mock.patch.object(SP, "_has_alignment", return_value=False), \
                mock.patch.object(core, "profile_sex", return_value="male"):
            out = SP._curated_rows("gonads", {"positions": [p]}, [], {"status": "ok"}, {})
            with mock.patch.object(panel_notes, "author_note", return_value=None):
                baseline = SP._curated_rows("gonads", {"positions": [p]}, [], {"status": "ok"}, {})
        row = out["rows"][0]
        self.assertIsNotNone(row.pop("author_note"))
        baseline["rows"][0].pop("author_note")
        self.assertEqual(baseline, out)
        row["author_note"] = panel_notes.author_note("rs5934505", row["level"])
        row["local_note"] = {"text": "Synthetic patient-specific note"}
        state = SP._position_state(row)
        self.assertEqual(row["author_note"], state["author_note"])
        self.assertEqual(row["local_note"], state["local_note"])

    def test_panel_cli_and_system_cli_label_the_note(self):
        from scholion import format as fmt
        from scholion.format_system import _system_gene_row
        r = panel_catalogue.panel_description("gonads")
        n = next(p["author_note"] for p in r["positions"] if p["rsid"] == "rs5934505")
        self.assertIn(n["label"], fmt.panel_report(r))
        self.assertIn(n["text"].splitlines()[0], fmt.panel_report(r))
        row = {"unit": "position", "gene": "SYNTHETIC", "rsid": "rs5934505", "author_note": n}
        self.assertIn(n["label"], _system_gene_row(row, "clinician"))
        self.assertNotIn(n["label"], _system_gene_row(row, "patient"))

    def test_full_reference_list_includes_every_waiting_and_refused_position(self):
        from scholion import format as fmt
        expected = [p for spec in self.intake["lists"].values() for p in spec["positions"]]
        r = panel_catalogue.panel_description("author_list")
        self.assertEqual(195, len(r["positions"]))
        rows = {p["rsid"]: p for p in r["positions"]}
        self.assertEqual({p["rsid"] for p in expected}, set(rows))
        text = fmt.panel_report(r)
        for p in expected:
            self.assertIn(p["rsid"], text)
            self.assertEqual(p["disposition"], rows[p["rsid"]]["disposition"])
            if p.get("reason"):
                self.assertIn(p["reason"], text)
        self.assertIsNotNone(rows["rs1799768"]["author_note"])
        self.assertIsNone(rows["rs3816873"]["author_note"])
        self.assertTrue(all("genotype" not in p for p in r["positions"]))
        index = panel_catalogue.panel_description()
        self.assertEqual(195, next(s["positions"] for s in index["systems"] if s["key"] == "author_list"))

    def test_import_is_all_or_nothing_and_never_overwrites(self):
        path = support.ROOT / "src" / "ingest" / "import_panel_author_notes.py"
        spec = importlib.util.spec_from_file_location("import_panel_notes", path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            inp, out = Path(tmp) / "input.json", Path(tmp) / "out.json"
            inp.write_text(json.dumps({"notes": self.notes}), encoding="utf-8")
            self.assertEqual(0, module.main([str(inp), "--check"]))
            self.assertEqual(0, module.main([str(inp), "--output", str(out)]))
            before = out.read_bytes()
            self.assertEqual(1, module.main([str(inp), "--output", str(out)]))
            self.assertEqual(before, out.read_bytes())
            inp.write_text(json.dumps({"notes": {"rs000000": self.notes["rs6356"]}}), encoding="utf-8")
            refused = Path(tmp) / "refused.json"
            self.assertEqual(1, module.main([str(inp), "--output", str(refused)]))
            self.assertFalse(refused.exists())
            inp.write_text(json.dumps({"notes": {"rs6356": self.notes["rs6356"]}}), encoding="utf-8")
            self.assertEqual(1, module.main([str(inp), "--check"]))


if __name__ == "__main__":
    unittest.main()
