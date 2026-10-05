"""Missing route/recheck support cannot turn into prescribing text or reassurance."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import unittest
from unittest import mock

import support
from scholion import core, format as fmt, i18n
from scholion.engine import routes
from tests.test_a_correction_route_is_conditional_grouped_and_checkable import _rule, _raw


class TestRouteBasis(unittest.TestCase):
    def tearDown(self):
        i18n.set_lang("en")

    def block(self, rule, by_key=None, rows=None):
        book = _raw()
        book["rules"] = [rule]
        with mock.patch.object(routes, "routes_book", return_value=book):
            return routes.correction_routes_for("amino_acids", by_key or {"aa_arginine": {"flag": "low"}},
                                                rows or [], True)

    def test_missing_support_is_named_without_old_instructions(self):
        for target in ("route", "recheck"):
            for missing in ("source", "mechanism"):
                for language in ("en", "ru"):
                    with self.subTest(target=target, missing=missing, language=language):
                        i18n.set_lang(language)
                        rule = _rule()
                        part = rule if target == "route" else rule["recheck"]
                        if missing == "source" and target == "route":
                            part["evidence"]["source"] = "Unidentified source"
                        else:
                            part.pop(missing)
                        before = copy.deepcopy(rule)
                        block = self.block(rule)
                        self.assertEqual(before, rule)
                        self.assertEqual([], block["groups"])
                        self.assertEqual([], block["adds_nothing"])
                        row = block["withheld"][0]
                        self.assertEqual(target + "_basis", row["reason_code"])
                        self.assertEqual(["aa_arginine"], row["on"])
                        for field in ("because", "route", "route_text", "recheck"):
                            self.assertNotIn(field, row)
                        text = "\n".join(fmt._correction_route_lines(block))
                        self.assertIn(row["reason"], text)
                        self.assertNotIn("⟦", text)
                        self.assertNotIn(rule["because"][language], text)
                        self.assertNotIn(rule["recheck"]["what_counts_as_change"][language], text)

    def test_supported_rule_carries_both_bases_without_human_review(self):
        rule = _rule()
        rule.pop("review")
        block = self.block(rule)
        self.assertEqual([], block["withheld"])
        row = block["groups"][0]["rows"][0]
        self.assertEqual("complete", row["conclusion_basis"]["status"])
        self.assertEqual("complete", row["recheck"]["conclusion_basis"]["status"])
        text = "\n".join(fmt._correction_route_lines(block))
        self.assertIn("Synthetic route mechanism", text)
        self.assertIn("Synthetic recheck mechanism", text)
        self.assertIn("Synthetic PMID: 1", text)

    def test_missing_bilingual_recheck_cannot_use_localization_fallback(self):
        rule = _rule()
        rule["recheck"]["mechanism"].pop("ru")
        for candidate in (rule, core._localize_tree(rule, "en")):
            self.assertEqual("recheck_basis", routes.route_refusal(candidate, core.lab_markers()["markers"]))

    def test_held_rules_still_require_observed_applicability(self):
        rule = _rule()
        rule.pop("mechanism")
        rule["depends_on"] = {"positions": ["rs123"], "state": "het"}
        for read, presumed in ((False, False), (True, True)):
            block = self.block(rule, rows=[{"rsid": "rs123", "state": "het", "read": read, "presumed": presumed}])
            self.assertEqual([], block["withheld"])
        block = self.block(rule, rows=[{"rsid": "rs123", "state": "het", "read": True}])
        self.assertEqual(["rs123"], block["withheld"][0]["positions"])
        block = self.block(rule, by_key={"aa_arginine": {"flag": "normal"}})
        self.assertEqual([], block["withheld"])

    def test_below_b_details_are_clinician_only_not_a_patient_backdoor(self):
        rule = _rule()
        rule["evidence"]["level"] = "C"
        rule["depends_on"] = {"positions": ["rs123"], "state": "het"}
        block = self.block(rule, rows=[{"rsid": "rs123", "state": "het", "read": True}])
        before = copy.deepcopy(block)
        patient = "\n".join(fmt._correction_route_lines(block, "patient"))
        clinician = "\n".join(fmt._correction_route_lines(block, "clinician"))
        self.assertNotIn("rs123", patient)
        self.assertIn("rs123", clinician)
        self.assertIn("withheld", patient.lower())
        self.assertNotIn(rule["because"]["en"], clinician)
        self.assertEqual(before, block)

    def test_no_rule_is_a_build_limitation_not_a_negative_genetic_claim(self):
        block = self.block(_rule(), by_key={"aa_arginine": {"flag": "normal"}})
        text = "\n".join(fmt._correction_route_lines(block))
        self.assertIn("does not establish absence", text)
        self.assertNotIn("genotype adds nothing", text)

    def test_unobserved_positions_are_not_silently_treated_as_negative(self):
        rule = _rule()
        rule["depends_on"] = {"positions": ["rs1801133"], "state": "hom"}
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for rows in ([], [{"rsid": "rs1801133", "state": "hom", "read": False}],
                         [{"rsid": "rs1801133", "state": "hom", "read": True, "presumed": True}],
                         [{"rsid": "rs1801133", "state": "risk_allele_not_declared", "read": True}]):
                block = self.block(rule, rows=rows)
                self.assertEqual([], block["groups"])
                self.assertEqual([], block["withheld"])
                self.assertEqual([], block["adds_nothing"])
                gap = block["unobserved"][0]
                self.assertEqual(["rs1801133"], gap["dependencies"])
                for field in ("because", "route", "recheck"):
                    self.assertNotIn(field, gap)
                self.assertIn(gap["reason"], "\n".join(fmt._correction_route_lines(block)))
                self.assertNotIn("⟦", gap["reason"])
        block = self.block(rule, rows=[{"rsid": "rs1801133", "state": "absent", "read": True}])
        self.assertEqual([], block["unobserved"])
        self.assertEqual([], block["groups"])
        block = self.block(rule, by_key={"aa_arginine": {"flag": "normal"}})
        self.assertEqual([], block["unobserved"])

    def test_dependencies_are_alternatives_and_position_rows_do_not_establish_a_gene_carrier(self):
        rule = _rule()
        rule["depends_on"] = {"genes": ["GA", "GB"], "state": "carrier"}
        self.assertEqual([], routes._unobserved_dependencies(None, []))
        rows = [{"unit": "position", "gene": "GA", "carrier": True, "read": True}]
        self.assertEqual(["GA", "GB"], self.block(rule, rows=rows)["unobserved"][0]["dependencies"])
        rows = [{"unit": "gene", "gene": "GA", "carrier": True, "read": True}]
        block = self.block(rule, rows=rows)
        self.assertEqual([], block["unobserved"])
        self.assertEqual(["GA"], block["groups"][0]["rows"][0]["positions"])
        rows += [{"unit": "gene", "gene": "GB", "carrier": False, "read": True}]
        self.assertEqual([], routes._unobserved_dependencies(rule["depends_on"], rows))

    def test_a_real_cross_panel_dependency_is_visible_without_a_clinical_claim(self):
        rows = [{"unit": "position", "rsid": "rs999", "state": "hom", "read": True}]
        block = routes.correction_routes_for("amino_acids", {"homocysteine": {"flag": "high"}}, rows, True)
        gap = next(r for r in block["unobserved"] if r["key"] == "mthfr_folate_form")
        self.assertEqual(["rs1801133"], gap["dependencies"])
        self.assertEqual("C", gap["evidence"]["level"])
        patient = "\n".join(fmt._correction_route_lines(block, "patient"))
        clinician = "\n".join(fmt._correction_route_lines(block, "clinician"))
        self.assertNotIn("rs1801133", patient)
        self.assertIn("rs1801133", clinician)
        self.assertIn(gap["reason"], clinician)

    @unittest.skipUnless(shutil.which("node"), "needs node for the page renderer")
    def test_browser_retains_support_and_refusals_without_mutating_data(self):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("function correctionRoutesHtml(")
        function = page[start:page.index("\n}\n", start) + 2]
        rule = _rule()
        good = self.block(rule)
        rule["evidence"]["level"] = "C"
        held = self.block(rule)
        held["withheld"][0]["positions"] = ["rs123"]
        held["unobserved"] = [{"dependencies": ["rsMissing"], "evidence": {"level": "C"},
                              "reason": "UNOBSERVED_DEPENDENCY"}]
        script = "const assert=require('node:assert/strict'); const esc=x=>String(x??''),t=k=>k,plural=n=>n;\n"
        script += function + "\nconst good=" + json.dumps(good) + ";const held=" + json.dumps(held) + ";\n"
        script += """
const before=JSON.stringify([good,held]);
for(const register of ['patient','clinician']){
  const html=correctionRoutesHtml(good,register);
  assert.ok(html.includes('Synthetic route mechanism'));
  assert.ok(html.includes('Synthetic recheck mechanism'));
  const refusal=correctionRoutesHtml(held,register);
  assert.ok(refusal.includes('data-routes-withheld'));
  assert.equal(refusal.includes('rs123'),register==='clinician');
  assert.ok(!refusal.includes('Synthetic route mechanism'));
  assert.ok(refusal.includes('data-routes-unobserved'));
  assert.equal(refusal.includes('rsMissing'),register==='clinician');
  assert.equal(refusal.includes('UNOBSERVED_DEPENDENCY'),register==='clinician');
}
assert.equal(before,JSON.stringify([good,held]));
"""
        result = subprocess.run([shutil.which("node"), "-e", script], text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
