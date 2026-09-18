"""A panel says it was checked whole, and what to look at.

On the radar the patient's register withholds the rows where nothing was found,
so a seven-position panel printed two rows and no word about the other five — as
if they had not been checked — and the two rows were a paragraph with no
conclusion (owner, 14.09.2026). The genetics layer now carries every position
of the panel as a state in both registers: gene, position, kind of link,
genotype state, whether it was read and why not, and the author's expectation
with where the measured value sits. The page draws the panel from that list —
what to look at first, a card per position found, the rest folded by name — and
the command line prints the same summary line.

No verdict is added: whether an expectation and a value agree stays the question
the card already asks.
"""
from __future__ import annotations

import unittest

import support
from scholion import format as fmt
from scholion.engine import system_panels as SP

ROOT = support.ROOT


class TestEveryPositionIsAState(unittest.TestCase):

    def test_both_registers_carry_every_position_with_the_same_fields(self):
        clin = SP.system("lipids", "clinician")["genetics"]
        pat = SP.system("lipids", "patient")["genetics"]
        self.assertEqual(clin.get("positions"), pat.get("positions"),
                         "the patient's density withholds rows, never the panel's states")
        for p in pat.get("positions") or []:
            # Since task 199 a state also carries its evidence level, the genotype
            # ladder and why it concludes nothing — in every register.
            self.assertEqual({"gene", "rsid", "kind", "state", "read", "read_why", "read_why_text", "text",
                              "expect", "unit", "genotype", "level", "level_short", "ladder",
                              "not_a_finding_why", "needs_confirmation",
                          # task 200: the chain link, the intake route and the
                          # load a fasting corridor cannot stand in for
                          "link", "link_text", "route", "under_load",
                          # task 200 / owner 18.09.2026: a position with no row
                          # in a variant-only file, and the value the reference
                          # implies when there is no alignment to check it
                          "read_state", "presumed", "closes_text", "depth_note",
                          # task 199 G/H: the group a position belongs to, and
                          # the clinician's own note from the profile
                          "local_note", "group"},
                             set(p), p)
            self.assertIn(p["state"], ("het", "hom", "absent", "unread", "risk_allele_not_declared", None))
            if p["expect"]:
                self.assertEqual({"marker", "name", "direction", "gap", "position"}, set(p["expect"]))

    def test_the_states_count_the_whole_panel(self):
        gen = SP.system("lipids", "clinician")["genetics"]
        rows = [r for r in gen.get("rows") or [] if r.get("unit") == "position"]
        self.assertEqual(len(rows), len(gen.get("positions") or []))
        self.assertEqual((gen.get("curated") or {}).get("positions"), len(gen["positions"]))

    def test_the_conclusion_names_found_absent_and_unread(self):
        line = "\n".join(fmt.genotype_conclusion_lines([
            {"gene": "ABCG2", "rsid": "rs2231142", "state": "het", "read": True},
            {"gene": "SLCO1B1", "rsid": "rs4149056", "state": "absent", "read": True},
            {"gene": "APOB", "rsid": "rs5742904", "state": "unread", "read": False},
        ]))
        self.assertIn("ABCG2 rs2231142", line)
        self.assertIn("SLCO1B1 rs4149056", line)
        self.assertIn("APOB rs5742904", line)
        self.assertIn("Genotype against the measurements", line)
        line2 = "\n".join(fmt.genotype_conclusion_lines([
            {"gene": "TSHR", "rsid": "rs121908876", "state": "absent", "read": True,
             "expect": {"marker": "tsh", "name": "TSH", "direction": "lower", "gap": False, "position": "within"}}]))
        self.assertIn("expectation for TSH does not apply", line2)
        self.assertIn("TSHR rs121908876", line2)
        self.assertNotIn("⟦", line)

    def test_the_patient_card_prints_the_summary_and_the_clinician_card_the_rows(self):
        pat = fmt.system_report(SP.system("lipids", "patient"))
        clin = fmt.system_report(SP.system("lipids", "clinician"))
        for text in (pat, clin):
            self.assertIn("Genotype of the system", text, "both registers carry the conclusion")
            self.assertIn("not read, 7 positions", text, "with no genome the panel is not read, not «none found»")
            self.assertNotIn("none of the named alleles", text)


class TestThePageDrawsThePanelFromTheStates(unittest.TestCase):

    def test_a_radar_label_and_a_wide_hit_area_open_the_system_like_the_dot(self):
        """The dot's hit area was 18 px and the label beside it opened nothing,
        so a click on «Lipids 56» looked like a hang (owner, 14.09.2026)."""
        html = (ROOT / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<g class="rlabel" data-dom="${esc(dom.key)}"', html)
        self.assertIn('<circle class="rhit"', html)
        self.assertIn("box.querySelectorAll('[data-dom]').forEach(el=>{", html,
                      "the labels bind through the same selector as the dots")


    def test_the_radar_block_uses_the_panel_and_folds_the_rest(self):
        html = (ROOT / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("function panelHtml(gen,card,register)", html)
        # Task 195: the block leads with the genotype's summary (`genSummaryHtml`)
        # and keeps every position's card under «More».
        self.assertIn("more+=genTableHtml(gen,card,card.register);", html,
                      "the radar block draws the genetic table, folded (task 200, owner 17.09.2026)")
        self.assertIn("h+=genSummaryHtml(gen,card);", html, "and says what was found above it")
        self.assertIn("b+=genTableHtml(gen,r,r.register);", html,
                      "and so does the card page, in its register")
        self.assertNotIn("panel.map(x=>`<div class=\"row-l\">${systemGeneRow(x,'patient')}</div>`)", html,
                         "the radar no longer prints the panel as a paragraph per row")
        for key in ("system.panel.conclusion_h", "system.panel.compare_h", "system.panel.prescribing_h",
                    "system.panel.polygenic_fold", "system.panel.question_ref"):
            self.assertIn(key, html)


if __name__ == "__main__":
    unittest.main()
