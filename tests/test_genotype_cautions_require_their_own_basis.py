"""A genotype observation is retained without lending it unsupported prescribing text."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import unittest
from unittest import mock

import support
from scholion import engine, format as fmt, i18n
from scholion.engine import class_genotype as CG
from scholion.format_prescription import caution_lines
from tests.test_a_genotype_in_the_profile_is_never_shown_as_unread import _Demo


class TestCautionBasis(_Demo):
    def setUp(self):
        super().setUp()
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_the_supported_warning_keeps_its_priority_and_basis_on_every_text_face(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for data, render, field in ((engine.medications_view(), fmt.medications_report, "cautions"),
                                        (engine.overview(), fmt.overview_report, "regimen_cautions"),
                                        (engine.second_opinion(), fmt.second_opinion_report, "regimen_cautions"),
                                        (engine.check_new_prescription("Combined oral contraceptive"),
                                         fmt.prescription_check, "safety_flags")):
                row = next(r for r in data[field] if r.get("origin") == "genotype")
                self.assertEqual("red_flag", row["severity"])
                self.assertEqual("complete", row["conclusion_basis"]["status"])
                self.assertFalse(row["interpretation_withheld"])
                self.assertIn("8164741", row["source"])
                self.assertIn("39106314", row["source"])
                self.assertIn(row["mechanism"], render(data))
                self.assertIn("🔴", "\n".join(render(data).splitlines()[:3]))
                self.assertNotIn("thirty", row["why_it_matters"])
                self.assertIn("U.S. MEC 2024", row["why_it_matters"])

    def test_missing_support_and_lower_levels_keep_the_reading_and_refuse_the_claim(self):
        original = CG._table()[0]
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for change in ({"source": None}, {"source": "Unidentified"}, {"mechanism": None},
                           {"mechanism": {"en": "Only English"}}, {"level": "C"}, {"level": "D"},
                           {"level": "E"}, {"level": None}):
                rule = {**copy.deepcopy(original), **change}
                before = copy.deepcopy(rule)
                with mock.patch.object(CG, "_table", return_value=[rule]):
                    row = CG.cautions([rule["class"]], "Synthetic prescription")[0]
                    check = engine.check_new_prescription("Combined oral contraceptive")
                self.assertTrue(row["interpretation_withheld"])
                self.assertEqual("caution", row["severity"])
                self.assertEqual(("F5", "rs6025", "het", rule.get("level")),
                                 (row["gene"], row["rsid"], row["state"], row["level"]))
                self.assertTrue(row["genotype"])
                for field in ("factor", "why_it_matters", "action", "mechanism"):
                    self.assertIsNone(row[field])
                self.assertTrue(row["uncertainty"])
                self.assertNotIn("⟦", row["uncertainty"])
                self.assertEqual(before, rule)
                self.assertNotEqual("low", check["overall"])
                self.assertNotIn("F5", (check["genetic_context"].get("verdict") or {}).get("genes") or [])
                text = "\n".join(caution_lines([row]))
                if rule.get("level") in ("C", "D", "E"):
                    self.assertNotIn("rs6025", text)
                else:
                    self.assertIn(row["uncertainty"], text)
                self.assertNotIn(rule["why"]["en"] if isinstance(rule["why"], dict) else rule["why"], text)

    def test_the_cautions_own_evidence_source_is_kept_without_borrowing_another_row(self):
        rule = copy.deepcopy(CG._table()[0])
        source = rule.pop("source")
        rule["evidence"] = {"source": source}
        with mock.patch.object(CG, "_table", return_value=[rule]):
            row = CG.cautions([rule["class"]])[0]
        self.assertFalse(row["interpretation_withheld"])
        self.assertEqual(source, row["source"])

    @unittest.skipUnless(shutil.which("node"), "needs node for the actual page renderers")
    def test_browser_preserves_the_supported_mechanism_and_counts_lower_levels(self):
        good = CG.regimen_cautions()[0]
        held = {**good, "interpretation_withheld": True, "severity": "caution", "factor": None,
                "why_it_matters": None, "action": None, "mechanism": None, "uncertainty": "NO_BASIS"}
        lower = {**held, "level": "C", "gene": "LOWER_GENE", "rsid": "rsLOWER"}
        page = (support.SRC / "scholion/web/index.html").read_text(encoding="utf-8")
        functions = []
        for name in ("mechanismHtml", "cautionsHtml", "flagsHTML"):
            start = page.index("function " + name + "(")
            functions.append(page[start:page.index("\n}\n", start) + 2])
        script = "const assert=require('node:assert/strict'),esc=x=>String(x??''),t=(k,a)=>k+JSON.stringify(a||{});\n"
        script += "\n".join(functions) + "\nconst data=" + json.dumps([good, held, lower]) + ";\n"
        script += """
const before=JSON.stringify(data);
for(const render of [cautionsHtml,flagsHTML]){
  assert.ok(render([data[0]]).includes(data[0].mechanism));
  assert.equal(render([data[0]]).split(data[0].source).length-1,1);
  assert.ok(render([data[1]]).includes('NO_BASIS'));
  const counted=render([data[2]]);
  assert.ok(counted.includes('data-caution-count'));
  assert.ok(!counted.includes('LOWER_GENE'));assert.ok(!counted.includes('rsLOWER'));
}
assert.equal(before,JSON.stringify(data));
"""
        result = subprocess.run([shutil.which("node"), "-e", script], text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
