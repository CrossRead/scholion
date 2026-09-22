"""A long panel is read the way its author reads it — and says no more for it (task 205 D, E, G, H).

The panel author's answer of 21.09.2026 on the amino acid panel gave four pieces
of structure, none of them a statement about a person:

* five pathway groups — branched-chain, the urea cycle, methionine metabolism,
  phenylalanine → tyrosine, the sulphur chain — where a marker may stand in two;
* five markers read as values only (β-alanine, β-aminoisobutyric acid,
  aspartate, asparagine, pipecolic acid): shown, never judged, never scored;
* which markers to read beside which, and in which direction that holds;
* three tests «not for everyone» — faecal elastase, the methionine load, the
  dimethylarginines — which stop being offered until she names who they are for;
* and one ratio she reads in practice that the build lacked, Hyp:Pro, shown as a
  value because no range was given.
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

import support
import importlib

from scholion import core, format as fmt

# By module path: the engine's facade exports functions under some of these names.
LB = importlib.import_module("scholion.engine.labs")
L = importlib.import_module("scholion.engine.lifestyle")
PL = importlib.import_module("scholion.engine.panel_labs")

KNOW = support.SRC / "scholion" / "knowledge"


def _domain():
    (d,) = [x for x in json.loads((KNOW / "radar_domains.json").read_text(encoding="utf-8"))["domains"]
            if x.get("key") == "amino_acids"]
    return d


def _row(key, value, flag=None, date="2026-09-01"):
    return {"key": key, "name": key, "value": value, "unit": "µmol/L", "date": date, "flag": flag,
            "abnormal": bool(flag), "ref_low": 1, "ref_high": 100}


class TestTheDeclaration(unittest.TestCase):

    def setUp(self):
        self.d = _domain()
        self.shown = set(self.d["panel_markers"]) | set(self.d["markers"])
        self.base = set(json.loads((KNOW / "lab_markers.json").read_text(encoding="utf-8")).get("markers")
                        or json.loads((KNOW / "lab_markers.json").read_text(encoding="utf-8")))

    def test_value_only_markers_are_panel_markers(self):
        self.assertEqual(5, len(self.d["display_only"]))
        self.assertLessEqual(set(self.d["display_only"]), set(self.d["panel_markers"]))

    def test_a_group_holds_only_what_the_system_shows(self):
        self.assertEqual(["bcaa", "urea_cycle", "methionine_cycle", "phe_tyr", "sulfur"],
                         [g["key"] for g in self.d["panel_groups"]])
        for g in self.d["panel_groups"]:
            self.assertLessEqual(set(g["markers"]), self.shown, g["key"])
            self.assertLessEqual(set(g.get("ratios") or []), set(self.d["derived"]), g["key"])

    def test_a_companion_is_a_key_the_build_knows(self):
        for k, rule in self.d["interpret_with"].items():
            self.assertIn(k, self.d["panel_markers"])
            self.assertIn(rule["when"], ("any", "low", "high"))
            for c in rule["with"]:
                self.assertTrue(c in self.base or c in self.d["derived"], f"{k} → {c}")


class TestTheScore(unittest.TestCase):

    def test_a_value_only_marker_is_never_judged(self):
        only = _domain()["display_only"][0]
        self.assertNotIn(only, L._RADAR_PANELS["amino_acids"])
        bk = {only: _row(only, 999, "H"), "aa_leucine": _row("aa_leucine", 50)}
        with mock.patch.object(L, "_marker_health", return_value=1.0):
            term = L._panel_term("amino_acids", bk)
        self.assertEqual((1, 0), (term["judged"], term["outside"]))


class TestTheView(unittest.TestCase):

    def view(self, rows):
        return PL.panel_view(_domain(), {r["key"]: r for r in rows})

    def test_value_only_is_said_on_the_marker(self):
        v = self.view([_row("aa_baiba", 3), _row("aa_leucine", 120)])
        by = {m["key"]: m for m in v["markers"]}
        self.assertTrue(by["aa_baiba"]["display_only"])
        self.assertFalse(by["aa_leucine"]["display_only"])

    def test_companions_follow_the_direction_the_author_named(self):
        low = self.view([_row("aa_histidine", 40, "L"), _row("ferritin", 80)])
        normal = self.view([_row("aa_histidine", 80)])
        comp = {m["key"]: m["companions"] for m in low["markers"]}["aa_histidine"]
        self.assertEqual(["crp_hs", "ferritin"], [c["key"] for c in comp])
        self.assertEqual([False, True], [c["measured"] for c in comp])
        self.assertEqual([], {m["key"]: m["companions"] for m in normal["markers"]}["aa_histidine"])

    def test_a_marker_stands_in_every_group_the_author_put_it_in(self):
        v = self.view([_row("aa_methionine", 25)])
        holding = [g["key"] for g in v["groups"] if any(x["key"] == "aa_methionine" and x["measured"]
                                                         for x in g["members"])]
        self.assertEqual(["methionine_cycle", "sulfur"], holding)

    def test_hyp_pro_is_computed_and_shown_as_a_value(self):
        v = self.view([_row("aa_hydroxyproline", 10), _row("aa_proline", 200)])
        (r,) = [x for x in v["ratios"] if x["key"] == "aa_ratio_hyp_pro"]
        self.assertEqual(("computed", 0.05, False), (r["origin"], r["value"], r["has_range"]))


class TestTheHeldTests(unittest.TestCase):

    def test_a_held_rule_never_fires(self):
        rules = {"rules": [{"id": "held_one", "when": {"measured": ["x"]}, "held": {"reason": "r"}},
                           {"id": "free_one", "when": {"measured": ["x"]}}]}
        with mock.patch.object(core, "test_rules", return_value=rules), \
                mock.patch.object(LB, "_eval_condition", return_value=True):
            ids = [s["id"] for s in LB.suggest_tests()["suggestions"]]
        self.assertEqual(["free_one"], ids)

    def test_the_three_the_author_declined_are_held_and_say_why(self):
        rules = {r["id"]: r for r in json.loads((KNOW / "test_rules.json").read_text(encoding="utf-8"))["rules"]}
        for rid in ("amino_fecal_elastase", "amino_methionine_load", "amino_dimethylarginines"):
            self.assertTrue(rules[rid]["held"]["reason"], rid)
        self.assertNotIn("held", rules["amino_urine_urea_nitrogen"])


class TestTheCardCarriesIt(unittest.TestCase):
    """The card reads the domain through `domains()`, which copies the fields it
    knows. The first version of this work passed every test above on the JSON and
    printed the old flat list on the owner's own card: the copy did not carry the
    new fields. Checked here through the path the card takes."""

    def test_the_domain_the_card_reads_carries_the_structure(self):
        SP = importlib.import_module("scholion.engine.system_panels")
        (d,) = [x for x in SP.domains() if x["key"] == "amino_acids"]
        for k in ("display_only", "panel_groups", "interpret_with"):
            self.assertEqual(_domain()[k], d[k], k)


class TestTheFaces(unittest.TestCase):

    def test_the_command_line_prints_the_groups_and_the_value_only_note(self):
        v = PL.panel_view(_domain(), {"aa_baiba": _row("aa_baiba", 3), "aa_leucine": _row("aa_leucine", 120)})
        text = "\n".join(fmt._panel_lines(v))
        for g in v["groups"]:
            self.assertIn(g["label"], text)
        self.assertIn(core_t("system.panel_labs.display_only"), text)

    def test_the_page_renders_groups_value_only_and_companions(self):
        page = (support.SRC / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        for needle in ("p.groups", "m.display_only", "m.companions", "system.panel_labs.groups_head"):
            self.assertIn(needle, page)


def core_t(key):
    from scholion.i18n import t
    return t(key)


if __name__ == "__main__":
    unittest.main()
