"""A clinician can read the panel itself, with its studies — and no person in it.

The radar reads a panel against one person's genome, in the density a patient
can carry to an appointment. A clinician asked for the panel as such: every
position, the sentence it prints for each genotype, the guideline or study it
rests on, what it expects of a marker, who signed it. That page describes
knowledge, not a person, so it must read the same for anybody and touch neither
the genome nor the laboratory results — held here by pointing the genome at
nothing and finding every position of the catalogue described all the same.
"""
from __future__ import annotations

import json
import unittest

import support
from scholion import format as fmt
from scholion.engine import panel_catalogue as PC

ROOT = support.ROOT
CATALOGUE = json.loads((ROOT / "src" / "scholion" / "knowledge" / "system_gene_panels.json")
                       .read_text(encoding="utf-8"))["systems"]


class TestTheDescription(unittest.TestCase):

    def test_every_position_of_the_catalogue_is_described_with_its_source(self):
        for key, spec in CATALOGUE.items():
            with self.subTest(system=key):
                d = PC.panel_description(key)
                self.assertEqual("ok", d["status"])
                self.assertEqual(len(spec.get("positions") or []), d["counts"]["positions"])
                for p in d["positions"]:
                    self.assertTrue(p["source"], f"{key} {p['rsid']} has no source")
                    self.assertIn(p["signature"], ("clinician", "author", "open"))
                    # A row named without a sentence is a draft the card prints
                    # as waiting; the description shows it the same way — empty.
                    self.assertIsInstance(p["text"], dict)
                self.assertEqual(len(spec.get("unreadable") or {}), len(d["unreadable"]))

    def test_it_reads_the_same_with_no_genome_and_no_labs(self):
        d = PC.panel_description("lipids")
        for p in d["positions"]:
            for personal in ("state", "read", "read_why", "genotype", "value", "findings", "carrier"):
                self.assertNotIn(personal, p, f"{p['rsid']} carries a person's field «{personal}»")
        self.assertTrue(all(p["text"].get("het") for p in d["positions"]))

    def test_the_listing_and_the_refusal(self):
        listing = PC.panel_description()
        self.assertEqual(sorted(CATALOGUE), sorted(s["key"] for s in listing["systems"]))
        r = PC.panel_description("nope")
        self.assertEqual("unknown_system", r["status"])
        self.assertIn("lipids", r["systems"])

    def test_the_report_names_the_study_and_the_signature_in_both_languages(self):
        for lang in ("en", "ru"):
            with self.subTest(lang=lang):
                code, out, err = support.run(["panel", "thyroid", "--lang", lang])
                self.assertEqual(0, code, err[-600:])
                self.assertIn("Panicker 2009 JCEM", out)
                self.assertIn("DIO2", out)
                self.assertNotIn("⟦", out)
        text = fmt.panel_report(PC.panel_description())
        self.assertIn("lipids", text)


class TestThePageLinksToIt(unittest.TestCase):

    def test_the_radar_block_and_the_card_link_to_the_panel_page(self):
        html = (ROOT / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("async function viewPanel(key)", html)
        self.assertIn("/api/panel?key=", html)
        self.assertEqual(2, html.count('data-panel="${esc('), "the radar block and the card both open it")
        self.assertIn("closest('[data-panel]')", html)


if __name__ == "__main__":
    unittest.main()
