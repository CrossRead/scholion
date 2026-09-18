"""«If a decision to correct has been made» — the narrowest gate in the product (task 200).

This screen stands closest to a prescription, so the rules are stricter than
anywhere else and every one of them is asserted here:

* printed only at evidence level A or B, with a named source and a `recheck`;
* the sentence begins with the decision, in both languages — never with the
  product telling somebody to correct anything;
* grouped by what the genotype says, never ranked;
* `adds_nothing` is printed, not left as silence: whoever speaks to the reader
  next fills a silence, and that sentence does not come from this build.

The shipped rules go through the same gate as a fixture would: a rule that
cannot be printed is refused by reason, and the refusals are counted.
"""
from __future__ import annotations

import copy
import unittest

import support  # noqa: F401
from scholion import core, i18n
from scholion.engine import routes


def _raw():
    """The file as written: `core` hands the engine one language, and half of
    what this gate promises is about both of them."""
    import json
    return json.loads(core.knowledge_path("correction_routes.json").read_text(encoding="utf-8"))


def _rule():
    for r in _raw()["rules"]:
        if r["key"] == "arginine_through_citrulline":
            return copy.deepcopy(r)
    raise AssertionError("the starting rule is gone")


class TestTheShippedRulesPassTheirOwnGate(unittest.TestCase):

    def test_every_shipped_rule_is_printable(self):
        known = core.lab_markers()["markers"]
        for book in (_raw(), routes.routes_book()):
            refused = [(r.get("key"), routes.route_refusal(r, known)) for r in book["rules"]]
            # A rule below B is the one refusal a shipped rule may carry: it is
            # not printed as a route but as «adds nothing», with its own reason.
            self.assertEqual([], [x for x in refused if x[1] and x[1] != "level_below_b"], refused)

    def test_a_rule_below_b_that_matches_prints_as_adds_nothing_with_its_reason(self):
        by_key = {"homocysteine": {"key": "homocysteine", "flag": "high"}}
        rows = [{"unit": "position", "rsid": "rs1801133", "gene": "MTHFR", "state": "hom", "read": True}]
        block = routes.correction_routes_for("amino_acids", by_key, rows, True)
        quiet = [q for q in block["adds_nothing"] if q["key"] == "mthfr_folate_form"]
        self.assertEqual(1, len(quiet), block)
        self.assertIn("C", quiet[0]["because"])
        self.assertIsNone(quiet[0]["route"])
        self.assertEqual([], [g for g in block["groups"] if any(r["key"] == "mthfr_folate_form" for r in g["rows"])])

    def test_a_class_outside_the_five_and_the_fact_is_refused(self):
        r = _rule(); r["says"] = "recommends"
        self.assertEqual("unknown_class", routes.route_refusal(r, core.lab_markers()["markers"]))

    def test_below_b_nothing_is_printed(self):
        known = core.lab_markers()["markers"]
        for level in ("C", "D", "E", None):
            with self.subTest(level=level):
                r = _rule(); r["evidence"]["level"] = level
                self.assertEqual("level_below_b", routes.route_refusal(r, known))

    def test_a_route_without_a_recheck_is_refused(self):
        known = core.lab_markers()["markers"]
        for drop in ("marker", "after_weeks", "what_counts_as_change"):
            with self.subTest(missing=drop):
                r = _rule(); r["recheck"].pop(drop)
                self.assertEqual("no_recheck", routes.route_refusal(r, known))

    def test_a_sentence_that_does_not_start_with_the_decision_is_refused(self):
        known = core.lab_markers()["markers"]
        r = _rule()
        r["because"]["ru"] = "Принимайте цитруллин вместо аргинина."
        self.assertEqual("phrasing_not_conditional", routes.route_refusal(r, known))
        r = _rule()
        r["because"]["en"] = "Take citrulline instead of arginine."
        self.assertEqual("phrasing_not_conditional", routes.route_refusal(r, known))

    def test_a_marker_named_by_a_rule_exists_in_the_base(self):
        known = core.lab_markers()["markers"]
        r = _rule(); r["recheck"]["marker"] = "aa_nosuchthing"
        self.assertEqual("recheck_marker_not_in_base", routes.route_refusal(r, known))
        r = _rule(); r["trigger"]["markers"] = ["aa_nosuchthing"]
        self.assertEqual("trigger_marker_not_in_base", routes.route_refusal(r, known))

    def test_a_rule_that_names_no_system_is_refused(self):
        r = _rule(); r.pop("system")
        self.assertEqual("no_system", routes.route_refusal(r, core.lab_markers()["markers"]))

    def test_a_below_b_rule_is_still_checked_whole_before_it_speaks(self):
        """The level is judged last: a level-C rule without a recheck is refused
        for the recheck, never rendered unchecked (review, 18.09.2026)."""
        known = core.lab_markers()["markers"]
        r = _rule(); r["evidence"]["level"] = "C"; r["recheck"].pop("marker")
        self.assertEqual("no_recheck", routes.route_refusal(r, known))

    def test_an_assumed_or_unread_genotype_satisfies_no_rule(self):
        by_key = {"aa_lysine": {"key": "aa_lysine", "flag": "low"}}
        for rows in ([{"unit": "gene", "gene": "SLC7A9", "carrier": True, "read": False}],
                     [{"unit": "gene", "gene": "SLC7A9", "carrier": True, "read": True, "presumed": True}]):
            block = routes.correction_routes_for("amino_acids", by_key, rows, True)
            self.assertEqual([], [g for g in block["groups"] if g["says"] in ("against", "favours")], block)

    def test_a_rule_nobody_reviewed_is_refused(self):
        known = core.lab_markers()["markers"]
        r = _rule(); r.pop("review")
        self.assertEqual("no_review", routes.route_refusal(r, known))

    def test_no_rule_carries_a_dose_or_a_brand(self):
        """Not a style rule: a dose is the line between material and a prescription."""
        import re
        bad = []
        for r in _raw()["rules"]:
            for lang in ("en", "ru"):
                text = r["because"][lang]
                if re.search(r"\d+\s*(mg|мг|g\b|г\b|mcg|мкг|IU|МЕ)", text):
                    bad.append((r["key"], lang))
        self.assertEqual([], bad, "a route names a dose")


class TestTheBlockAnswersADecisionItDidNotMake(unittest.TestCase):

    def _block(self, by_key, rows, deviating=True):
        return routes.correction_routes_for("amino_acids", by_key, rows, deviating)

    def test_a_deviation_with_no_matching_rule_says_the_genotype_adds_nothing(self):
        block = self._block({}, [], True)
        self.assertEqual("ok", block["status"])
        self.assertEqual([], block["groups"])
        self.assertEqual(["no_rule"], [x["key"] for x in block["adds_nothing"]])
        self.assertTrue(block["adds_nothing"][0]["because"])

    def test_with_nothing_off_the_block_does_not_appear(self):
        block = self._block({}, [], False)
        self.assertEqual("nothing_deviates", block["status"])

    def test_a_carrier_with_the_deviation_gets_both_sides_of_the_same_answer(self):
        by_key = {"aa_lysine": {"key": "aa_lysine", "flag": "low"}}
        rows = [{"unit": "gene", "gene": "SLC7A9", "carrier": True, "read": True}]
        block = self._block(by_key, rows)
        says = {g["says"] for g in block["groups"]}
        self.assertIn("against", says, block)
        self.assertIn("favours", says, block)
        for g in block["groups"]:
            for row in g["rows"]:
                self.assertTrue(row["recheck"]["what_counts_as_change"])
                self.assertEqual(["aa_lysine"], row["on"])

    def test_the_same_deviation_without_the_genotype_prints_no_route(self):
        by_key = {"aa_lysine": {"key": "aa_lysine", "flag": "low"}}
        block = self._block(by_key, [])
        self.assertEqual([], [g for g in block["groups"] if g["says"] in ("against", "favours")])

    def test_the_groups_are_classes_in_a_fixed_order_and_carry_no_rank(self):
        by_key = {"aa_lysine": {"key": "aa_lysine", "flag": "low"}}
        rows = [{"unit": "gene", "gene": "SLC3A1", "carrier": True, "read": True}]
        block = self._block(by_key, rows)
        order = [g["says"] for g in block["groups"]]
        self.assertEqual(order, [c for c in routes.ROUTE_ORDER if c in order])
        for g in block["groups"]:
            for row in g["rows"]:
                self.assertNotIn("rank", row)
                self.assertNotIn("best", str(row.get("because")).lower())

    def test_the_block_speaks_both_languages(self):
        by_key = {"aa_lysine": {"key": "aa_lysine", "flag": "low"}}
        rows = [{"unit": "gene", "gene": "SLC7A9", "carrier": True, "read": True}]
        for lang in ("en", "ru"):
            with self.subTest(language=lang):
                i18n.set_lang(lang)
                block = self._block(by_key, rows)
                self.assertNotIn("⟦", block["head"] + block["caveat"])
                for g in block["groups"]:
                    for row in g["rows"]:
                        self.assertNotIn("⟦", row["because"])
                        self.assertTrue(row["says_text"])
        i18n.set_lang("en")


class TestThePrintedReportCarriesTheBlock(unittest.TestCase):
    """The printed entry says the same as the page — the parity rule, on the
    surface that a clinician actually takes to a consultation."""

    def _block(self):
        by_key = {"aa_lysine": {"key": "aa_lysine", "flag": "low"}}
        rows = [{"unit": "gene", "gene": "SLC7A9", "carrier": True, "read": True}]
        return routes.correction_routes_for("amino_acids", by_key, rows, True)

    def test_the_lines_carry_the_route_the_recheck_and_the_source(self):
        from scholion import format as fmt
        lines = fmt._correction_route_lines(self._block())
        text = "\n".join(lines)
        self.assertIn("If a decision", text)
        self.assertIn("recheck", text.lower())
        self.assertIn("PMID", text)

    def test_a_block_that_says_nothing_prints_nothing(self):
        from scholion import format as fmt
        self.assertEqual([], fmt._correction_route_lines(None))
        self.assertEqual([], fmt._correction_route_lines({"status": "nothing_deviates"}))

    def test_the_position_lines_of_a_report_carry_the_link_and_the_load(self):
        from scholion import format as fmt
        from scholion.engine import system_panels as SP
        rows = [r for r in SP.system("amino_acids", "clinician")["genetics"]["rows"]
                if r.get("rsid") == "rs5742905"]
        if not rows:
            self.skipTest("the transsulfuration position is not in this build")
        printed = fmt.system_report(SP.system("amino_acids", "clinician"))
        self.assertIn("link:", printed)
        self.assertIn("intake route:", printed)


if __name__ == "__main__":
    unittest.main()
