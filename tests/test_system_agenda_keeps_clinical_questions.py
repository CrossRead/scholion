"""A visit agenda keeps clinical questions; catalogue repair stays with variants."""
from __future__ import annotations

import copy
import shutil
import subprocess
import unittest
from unittest import mock

import support
from scholion import core, i18n
from scholion.engine import system_panels as panels


class TestClinicalAgenda(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_catalogue_gaps_do_not_become_questions_but_carriership_still_does(self):
        rows = [{"gene": "SYNTHETIC", "rsid": "rsSynthetic", "pending": True,
                 "pending_why": reason, "unit": "position", "read": True,
                 "conclusion_basis": {"status": "incomplete", "reason": "Missing mechanism"}}
                for reason in ("conclusion_basis", "risk_allele", "no_text_for_state")]
        rows.append({"gene": "CARRIER", "rsid": "rsCarrier", "clinical_carrier": True, "moi": "AR"})
        original = copy.deepcopy(rows)
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for register in ("patient", "clinician"):
                result = panels._questions({"rows": rows, "register": register}, {"missing": []}, {"rows": []}, {})
                self.assertEqual(["moi"], [q["origin"] for q in result["rows"]])
                self.assertEqual("CARRIER", result["rows"][0]["gene"])
        self.assertEqual(original, rows)

    def test_medication_labels_use_the_localised_dictionary_without_changing_mapping(self):
        raw = [{"name": "Synthetic", "dose": "Recorded regimen", "status": "current",
                "classes": ["statin"], "via": {"statin": ["lipids"]}, "systems": ["lipids"], "map_status": "mapped"}]
        for language in ("en", "ru"):
            i18n.set_lang(language)
            with mock.patch.object(panels, "prescriptions", return_value=raw):
                layer = panels._medications_layer("lipids")
            self.assertEqual(["statin"], layer["rows"][0]["via"])
            self.assertEqual([core.med_classes()["classes"]["statin"]["label"]], layer["rows"][0]["via_labels"])
            self.assertEqual("Recorded regimen", layer["rows"][0]["dose"])

    @unittest.skipUnless(shutil.which("node"), "requires node for the shared renderer")
    def test_medication_uncertainty_is_folded_and_never_rendered_as_a_class_code_link(self):
        page = (support.SRC / "scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("function systemMedicationsHtml(")
        function = page[start:page.index("\n}\n", start)+2]
        script = "const assert=require('node:assert/strict');const esc=x=>String(x??'');const t=(k,a)=>k+JSON.stringify(a||{});\n" + function
        script += """
const med={rows:[{name:'MAPPED',dose:'Recorded regimen',via:['RAW_CLASS'],via_labels:['Readable class']}],
 unmapped:[{name:'UNMAPPED',dose:'Other regimen',classes:['RAW_UNMAPPED'],class_labels:['Other class']}],
 unclassified:[{name:'UNCLASSIFIED'}]};
const before=JSON.stringify(med),html=systemMedicationsHtml(med);
assert.ok(html.includes('<table class="cr-table system-medications-table">'));
assert.ok(html.includes('Readable class'));assert.ok(html.includes('Recorded regimen'));
assert.ok(!html.includes('RAW_CLASS'));assert.ok(!html.includes('RAW_UNMAPPED'));
assert.ok(!html.includes('<a '));assert.ok(!html.includes(' open'));
const detail=html.indexOf('data-medications-unplaced');
assert.ok(detail>0);assert.ok(html.indexOf('UNMAPPED')>detail);assert.ok(html.indexOf('UNCLASSIFIED')>detail);
assert.equal(before,JSON.stringify(med));
"""
        result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
