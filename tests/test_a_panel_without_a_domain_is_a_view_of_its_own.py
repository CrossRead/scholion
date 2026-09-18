"""A panel without a radar domain is its own view, never a radar segment (task 199 F).

Dental and behaviour have no laboratory half and will not get one. Shown on
the radar they would teach a reader that an empty half means a clean one; so
they open as a card that says at the top why it is not there, print their
positions through the same gate as a system's genetic half, and carry no score.
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, format as fmt
from scholion.engine import panel_catalogue, system_panels as SP


class TestThePanelOpensAsACard(unittest.TestCase):

    def test_an_on_demand_key_answers_with_a_card_and_no_score(self):
        card = SP.system("behaviour", "patient")
        self.assertEqual("ok", card["status"])
        self.assertTrue(card["on_demand"])
        self.assertTrue(card["why_no_domain"])
        self.assertEqual("no_laboratory_half", card["labs"]["status"])
        self.assertNotIn("score", card["labs"])
        self.assertIn("genetics", card)

    def test_the_radar_never_holds_it(self):
        import importlib
        lifestyle = importlib.import_module("scholion.engine.lifestyle")
        keys = {d["key"] for d in lifestyle.health_radar()["domains"]}
        for p in SP.on_demand_panels():
            self.assertNotIn(p["key"], keys)

    def test_the_index_names_it_apart_from_the_systems(self):
        idx = SP.systems()
        self.assertIn("behaviour", [p["key"] for p in idx["on_demand"]])
        self.assertNotIn("behaviour", [s["key"] for s in idx["systems"]])

    def test_an_unknown_key_is_still_refused_and_names_both_lists(self):
        r = SP.system("teeth-and-nails", "patient")
        self.assertEqual("unknown_system", r["status"])
        self.assertIn("behaviour", r["on_demand"])

    def test_the_catalogue_describes_it_with_its_own_label(self):
        d = panel_catalogue.panel_description("behaviour")
        self.assertEqual("ok", d["status"])
        self.assertNotIn("⟦", d["label"])

    def test_the_printed_card_says_why_and_prints_no_laboratory_layer(self):
        text = fmt.system_report(SP.system("behaviour", "clinician"))
        self.assertNotIn("⟦", text)
        self.assertNotIn("1. ", text.split("\n")[0])
        self.assertIn(SP.system("behaviour")["why_no_domain"], text)

    def test_every_shipped_position_of_every_panel_passes_the_gate(self):
        from scholion.engine import panel_gate
        book = json.loads(core.knowledge_path("on_demand_panels.json").read_text(encoding="utf-8"))
        levels = {x["level"]: x for x in panel_gate.legend()["levels"]}
        for key, spec in book["panels"].items():
            for p in spec.get("positions") or []:
                with self.subTest(panel=key, rsid=p.get("rsid")):
                    self.assertIsNone(panel_gate.refusal(p, [], spec.get("source") or "",
                                                         p.get("source") or spec.get("source") or "", levels))


if __name__ == "__main__":
    unittest.main()
