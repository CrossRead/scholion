"""A position of the amino acid system carries its link, its route and its load (task 200).

Three fields the other systems do not have, each for a reason:

* `link` — the same shift arrives from different links of one chain (digestion,
  carriage, use inside the cell, renal loss), and the link is what decides which
  correction routes can mean anything at all;
* `route` — a drip removes the gut and the first pass through the liver, free
  amino acids remove the digestion of protein and the peptide path, so the same
  genotype is not equally important on all three. What is a mechanistic reading
  says so, rather than borrowing the authority of a measurement;
* `under_load` — the whole product reads a person at rest, and a fasting
  corridor excludes nothing for a carrier whose capacity is partial.

Also here: the second half of the picture — urine, ammonia, the cofactors — is
asked for while it is missing and stops being asked for the day it is taken.
"""
from __future__ import annotations

import unittest
import unittest.mock

import support  # noqa: F401
from scholion import core
from scholion.engine import panel_gate


def _amino():
    """The file as written. `core` hands a reader one language, and the fields
    this test is about are curated in both."""
    import json
    data = json.loads(core.knowledge_path("system_gene_panels.json").read_text(encoding="utf-8"))
    return data["systems"]["amino_acids"]


class TestEveryPositionSitsOnALink(unittest.TestCase):

    def test_every_position_has_a_link_the_system_declares(self):
        spec = _amino()
        links = spec["links"]
        for p in spec["positions"]:
            with self.subTest(rsid=p["rsid"]):
                self.assertIn(p.get("link"), links)
                self.assertIn(p.get("link"), panel_gate.LINKS)

    def test_the_links_sum_to_the_number_of_positions(self):
        spec = _amino()
        by_link = {k: 0 for k in spec["links"]}
        for p in spec["positions"]:
            by_link[p["link"]] += 1
        self.assertEqual(len(spec["positions"]), sum(by_link.values()))

    def test_a_position_with_no_link_is_refused_where_links_are_declared(self):
        spec = _amino()
        p = dict(spec["positions"][0])
        p.pop("link")
        self.assertEqual("link_missing", panel_gate.refusal(
            p, ["homocysteine"], spec["source"], p.get("source") or spec["source"],
            {x["level"]: x for x in panel_gate.legend()["levels"]}, links=spec["links"]))

    def test_a_system_that_declares_no_links_is_not_asked_for_one(self):
        spec = _amino()
        p = dict(spec["positions"][0])
        p.pop("link")
        self.assertIsNone(panel_gate.refusal(
            p, ["homocysteine"], spec["source"], p.get("source") or spec["source"],
            {x["level"]: x for x in panel_gate.legend()["levels"]}))


class TestTheRouteIsDeclaredWithItsBasis(unittest.TestCase):

    def test_every_position_says_how_it_reads_on_the_three_routes(self):
        spec = _amino()
        for p in spec["positions"]:
            with self.subTest(rsid=p["rsid"]):
                route = p["route"]
                self.assertIn(route["basis"], ("source", "mechanism"))
                for name in ("food", "oral_free", "iv"):
                    self.assertIn(route[name], ("matters", "bypassed", "sharper"))

    def test_an_unknown_route_state_is_refused(self):
        spec = _amino()
        p = dict(spec["positions"][0])
        p["route"] = {**p["route"], "iv": "helps"}
        self.assertEqual("route_state_unknown", panel_gate.refusal(
            p, ["homocysteine"], spec["source"], p.get("source") or spec["source"],
            {x["level"]: x for x in panel_gate.legend()["levels"]}, links=spec["links"]))

    def test_a_route_that_claims_a_source_must_name_one(self):
        spec = _amino()
        p = dict(spec["positions"][0])
        p["route"] = {**p["route"], "basis": "source", "source": None}
        self.assertEqual("route_source_missing", panel_gate.refusal(
            p, ["homocysteine"], spec["source"], p.get("source") or spec["source"],
            {x["level"]: x for x in panel_gate.legend()["levels"]}, links=spec["links"]))

    def test_a_route_that_is_not_a_block_at_all_is_refused(self):
        spec = _amino()
        p = dict(spec["positions"][0]); p["route"] = "oral_free"
        self.assertEqual("route_not_a_block", panel_gate.refusal(
            p, ["homocysteine"], spec["source"], p.get("source") or spec["source"],
            {x["level"]: x for x in panel_gate.legend()["levels"]}, links=spec["links"]))

    def test_a_link_the_system_does_not_declare_is_refused(self):
        spec = _amino()
        p = dict(spec["positions"][0]); p["link"] = "gut_feeling"
        self.assertEqual("link_not_in_legend", panel_gate.refusal(
            p, ["homocysteine"], spec["source"], p.get("source") or spec["source"],
            {x["level"]: x for x in panel_gate.legend()["levels"]}, links=spec["links"]))

    def test_a_position_absorption_stops_mattering_when_the_route_skips_absorption(self):
        spec = _amino()
        absorb = [p for p in spec["positions"] if p["link"] == "absorb"]
        self.assertTrue(absorb, "the digestion link has no position at all")
        for p in absorb:
            with self.subTest(rsid=p["rsid"]):
                self.assertEqual("bypassed", p["route"]["iv"])


class TestALoadIsNamedWhereRestSaysNothing(unittest.TestCase):

    def test_a_load_test_is_one_the_system_declares_and_says_what_it_reveals(self):
        spec = _amino()
        loads = spec["load_tests"]
        found = 0
        for p in spec["positions"]:
            ul = p.get("under_load")
            if not ul:
                continue
            found += 1
            with self.subTest(rsid=p["rsid"]):
                self.assertIn(ul["test"], loads)
                for lang in ("en", "ru"):
                    self.assertTrue(ul["what_it_reveals"][lang])
        self.assertGreater(found, 0, "no position names a load at all")

    def test_the_carrier_position_of_the_transsulfuration_names_the_methionine_load(self):
        spec = _amino()
        cbs = [p for p in spec["positions"] if p["gene"] == "CBS"][0]
        self.assertEqual("methionine_load", cbs["under_load"]["test"])


class TestTheSecondHalfOfThePictureIsAskedFor(unittest.TestCase):
    """The plasma panel cannot say what urine, ammonia and the cofactors say."""

    def _rules(self):
        """The RAW file: `core` hands a reader the catalogue already in one
        language, and this test is about both of them."""
        import json
        data = json.loads(core.knowledge_path("test_rules.json").read_text(encoding="utf-8"))
        return {r["id"]: r for r in data["rules"]}

    def test_the_six_mandatory_items_are_rules_that_name_markers_that_exist(self):
        want = ["amino_urine_profile", "amino_urine_cystine", "amino_ammonia",
                "amino_kynurenine", "amino_b6", "amino_fecal_elastase"]
        rules, known = self._rules(), core.lab_markers()["markers"]
        for rid in want:
            with self.subTest(rule=rid):
                self.assertIn(rid, rules)
                r = rules[rid]
                for key in r["covers"]:
                    self.assertIn(key, known)
                for lang in ("en", "ru"):
                    self.assertTrue(r["suggest"][lang] and r["why"][lang])

    def test_an_item_is_asked_for_while_missing_and_not_after_it_is_taken(self):
        from scholion.engine import labs
        rule = self._rules()["amino_ammonia"]
        cond = rule["when"]
        with unittest.mock.patch.object(labs, "_latest_value",
                                        lambda k: 100.0 if k.startswith("aa_") else None):
            self.assertTrue(labs._eval_condition(cond))
        with unittest.mock.patch.object(labs, "_latest_value", lambda k: 100.0):
            self.assertFalse(labs._eval_condition(cond))

    def test_nothing_is_asked_for_when_the_panel_was_never_taken(self):
        from scholion.engine import labs
        cond = self._rules()["amino_urine_profile"]["when"]
        with unittest.mock.patch.object(labs, "_latest_value", lambda k: None):
            self.assertFalse(labs._eval_condition(cond))


if __name__ == "__main__":
    unittest.main()
