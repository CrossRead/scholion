"""Shared reference hypotheses never diagnose a cause or order a test."""
from __future__ import annotations

import copy
import unittest
from unittest import mock

import support  # noqa: F401 -- synthetic environment
from scholion import core, i18n
from scholion.conclusion_basis import conclusion_basis
from scholion.engine.panel_labs import panel_view
from scholion.format_system import _panel_lines
from scholion.test_proposals import guard_test_proposal, test_basis_text


class TestSharedContexts(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, getattr(i18n._state, "current", None))
        self.addCleanup(core.reset_cache)

    def panel(self, flag="low", censored=None, display_only=False):
        keys = ["aa_leucine", "valine"]
        dom = {"panel_markers": keys, "display_only": keys if display_only else []}
        rows = {k: {"name": k, "value": 10, "date": "2026-01-01", "flag": flag,
                    "censored": censored, "unit": "umol/L"} for k in keys}
        return panel_view(dom, rows)

    def test_one_dictionary_for_two_values_with_no_score_or_diagnosis(self):
        p = self.panel()
        self.assertFalse(p["scored"])
        self.assertEqual(3, len(p["cause_dictionary"]))
        ids = [c["id"] for c in p["cause_dictionary"]]
        for m in p["markers"]:
            self.assertEqual(ids, m["possible_causes"])
        for c in p["cause_dictionary"]:
            self.assertEqual("reference_only", c["status"])
            self.assertEqual("C", c["level"])
            self.assertEqual("possible_context_not_established", c["interpretation"])
            self.assertTrue(c["caveat"])

    def test_critical_low_is_a_direction_but_critical_high_is_not_low(self):
        self.assertEqual(3, len(self.panel(flag="critical_low")["cause_dictionary"]))
        self.assertEqual([], self.panel(flag="critical_high")["cause_dictionary"])

    def test_bound_on_the_selected_lab_point_reaches_the_panel_gate(self):
        from scholion.engine.labs import analyze_labs
        data = {"markers": {"aa_leucine": {"name": "Synthetic leucine", "unit": "umol/L",
                    "ref_low": 50, "ref_high": 200,
                    "series": [{"value": 10, "censored": "<", "date": "2026-01-01"}]}}}
        with mock.patch.object(core, "labs", return_value=data):
            rows = analyze_labs(["aa_leucine"])["markers"]
        self.assertEqual("<", rows[0]["censored"])
        p = panel_view({"panel_markers": ["aa_leucine"]}, {r["key"]: r for r in rows})
        self.assertEqual([], p["cause_dictionary"])

    def test_normal_high_unknown_censored_and_display_only_do_not_trigger(self):
        for kwargs in ({"flag": "ok"}, {"flag": "high"}, {"flag": "unknown"},
                       {"censored": "<"}, {"display_only": True}):
            with self.subTest(kwargs=kwargs):
                p = self.panel(**kwargs)
                self.assertEqual([], p["cause_dictionary"])
                self.assertTrue(all(not m.get("possible_causes") for m in p["markers"]))

    def test_asparagine_and_other_value_only_markers_keep_no_hypotheses(self):
        p = panel_view({"panel_markers": ["aa_asparagine", "aa_beta_alanine"],
                        "display_only": ["aa_asparagine", "aa_beta_alanine"]},
                       {k: {"value": 10, "flag": "low"} for k in ("aa_asparagine", "aa_beta_alanine")})
        self.assertEqual([], p["cause_dictionary"])

    def test_missing_support_or_raised_level_cannot_release_a_hypothesis(self):
        book = copy.deepcopy(core._read_knowledge("amino_acid_causes.json"))
        book["causes"]["protein_intake"]["basis"] = {}
        book["causes"]["catabolism"]["level"] = "A"
        with mock.patch.object(core, "_read_knowledge", return_value=book):
            p = self.panel()
        for c in p["cause_dictionary"]:
            if c["id"] != "malabsorption":
                self.assertEqual("withheld", c["status"])
                self.assertIsNone(c["mechanism"])

    def test_own_sources_and_bilingual_legend_are_printed_once(self):
        raw = core._read_knowledge_raw("amino_acid_causes.json")
        self.assertEqual(9, len(raw["markers"]))
        self.assertIn("valine", raw["markers"])
        for c in raw["causes"].values():
            self.assertEqual("complete", conclusion_basis(c["basis"])["status"])
            self.assertEqual({"en", "ru"}, set(c["caveat"]))
        for language in ("en", "ru"):
            i18n.set_lang(language)
            p = self.panel()
            text = "\n".join(_panel_lines(p))
            self.assertIn(i18n.t("system.panel_labs.causes_head"), text)
            for c in p["cause_dictionary"]:
                self.assertEqual(1, text.count(c["source"]))
                self.assertIn(c["caveat"], text)
                self.assertIn(c["name"], text)

    def test_urea_nitrogen_has_sources_but_panel_is_not_a_clinical_indication(self):
        rule = next(r for r in core._read_knowledge_raw("test_rules.json")["rules"]
                    if r["id"] == "amino_urine_urea_nitrogen")
        self.assertNotIn("priority", rule)
        self.assertNotIn("recheck_months", rule)
        self.assertIn("valine", rule["when"]["all"][0]["measured"])
        self.assertNotIn("aa_valine", rule["when"]["all"][0]["measured"])
        for name in ("suggest", "why", "condition"):
            self.assertEqual("complete", conclusion_basis(rule[name + "_basis"])["status"])
        for language in ("en", "ru"):
            i18n.set_lang(language)
            local = next(r for r in core.test_rules()["rules"] if r["id"] == rule["id"])
            result = guard_test_proposal(local)
            self.assertEqual("withheld", result["proposal_status"])
            self.assertIsNone(result["priority"])
            self.assertNotIn("recheck_months", result)
            self.assertIn("clinical_scope", result["proposal_basis"]["condition"]["missing"])
            self.assertIn("PMID: 38033373", test_basis_text(result))
            self.assertIn(local["why_basis"]["mechanism"], test_basis_text(result))


if __name__ == "__main__":
    unittest.main()
