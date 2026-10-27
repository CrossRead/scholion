"""Unknown lipid direction and PGS technical validity survive the summary view."""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest

import support
import gene_card_support


@unittest.skipUnless(shutil.which("node"), "Node is needed for renderer probes")
class GenomeSummary(unittest.TestCase):
    def function(self, name):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("function " + name + "(")
        return page[start:page.index("\n}", start) + 2]

    def execute(self, script):
        script = gene_card_support.javascript() + script
        result = gene_card_support.run(script,
                                capture_output=True, text=True, timeout=20,
                                stdin=subprocess.DEVNULL)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def test_unknown_direction_is_not_a_negative_carrier_result_in_findings(self):
        script = """
const t=k=>k, esc=x=>String(x), badge=(cls,text)=>text;
const genomeGeneTable=()=>'', isRsid=()=>true,levelChip=x=>x,geneticBriefHtml=()=>'';
""" + self.function("genomeFindings") + """
const variants=[null,false,true].map((carrier,i)=>({carrier,status:'read',gene:'PCSK9',rsid:'rs'+i}));
console.log(JSON.stringify(variants.map(x=>genomeFindings(null,null,null,{status:'ok',pcsk9:[x]}))));
"""
        rows = self.execute(script)
        self.assertIn("lipidgen.direction_unknown", rows[0])
        self.assertNotIn("lipidgen.not_carrier", rows[0])
        self.assertIn("lipidgen.not_carrier", rows[1])
        self.assertIn("lipidgen.carrier", rows[2])

    def test_pgs_accuracy_is_separate_and_reference_urls_are_checked(self):
        script = """
const t=(k,args)=>k+JSON.stringify(args||{}), esc=x=>String(x);
""" + self.function("prsModelDetails") + """
const row={stability:{coverage_pct:100,weight_pct:95},informativeness:{auroc:0.7},reference_note:'Approximate reference',reference_validation:{source:'https://example.org/reference'}};
console.log(JSON.stringify([prsModelDetails(row),prsModelDetails({}),prsModelDetails({...row,reference_validation:{source:'javascript:bad()'}})]));
"""
        rows = self.execute(script)
        self.assertIn("web.prs.coverage", rows[0])
        self.assertIn("prs.info_auroc", rows[0])
        self.assertIn("web.prs.accuracy_note", rows[0])
        self.assertIn("Approximate reference", rows[0])
        self.assertIn('href="https://example.org/reference"', rows[0])
        self.assertIn("web.prs.accuracy_missing", rows[1])
        self.assertNotIn("javascript:", rows[2])

    def test_missing_genotypes_have_vcf_help_in_calculation_details(self):
        script = "const t=k=>k, esc=x=>String(x);\n" + self.function("prsModelDetails") + "\nconsole.log(JSON.stringify(prsModelDetails({reading_note:'VCF with called reference genotypes; BAM optional'})));"
        html = self.execute(script)
        self.assertIn('VCF with called reference genotypes', html)
        self.assertIn('<details', html)

    def test_absence_summary_names_alleles_in_both_languages(self):
        from scholion import i18n
        for language, phrase in [('en', 'Catalogue allele'), ('ru', 'Аллель справочника')]:
            i18n.set_lang(language)
            text = i18n.t('web.second.gen_absent', genes='AGXT2')
            self.assertIn(phrase, text)
            self.assertNotIn('Not carried', text)
        i18n.set_lang('en')


    def test_lipid_card_keeps_unverified_values_out_of_the_percentile_label(self):
        script = "const t=k=>k, esc=x=>String(x), clinicalBasisHTML=()=>'';\n" + "function prsPercentile(p){return p==null?'—':Number(p.toFixed(2))>=100?'≥P99.99':'P'+p;}" + "\n" + self.function("renderLipidGenetics") + """
const render=(reliable,percentile)=>renderLipidGenetics({status:'ok',lpa:{measured:{value:10,unit:'SOURCE_UNIT',unit_display:'nmol/L'},estimate:{label:'Synthetic Lp(a)',pgs_id:'PGS002101',reliable,percentile,calibration_note:reliable?null:'CALIBRATION_GAP'}}});
const badge=()=>'';
console.log(JSON.stringify([render(true,99.9999),render(false,99),render(false,null)]));
"""
        rows = self.execute(script)
        self.assertIn('≥P99.99', rows[0])
        self.assertNotIn('P100', rows[0])
        self.assertIn('10 nmol/L', rows[0])
        self.assertNotIn('SOURCE_UNIT', rows[0])
        for html in rows[1:]:
            self.assertIn('web.prs.unverified', html)
            self.assertIn('CALIBRATION_GAP', html)
            self.assertIn('<details', html)
            self.assertNotIn('>99', html)
            self.assertNotIn('>null', html)

    def test_screening_omits_empty_extra_classes_and_folds_available_ones(self):
        script = "const t=k=>k, esc=x=>String(x);\n" + self.function("renderScreen") + """
console.log(JSON.stringify([renderScreen({held:[],named:[]}),renderScreen({held:[],named:[{key:'test',label:'Synthetic class',count:1}]})]));
"""
        empty, named = self.execute(script)
        self.assertNotIn('screen.no_named', empty)
        self.assertNotIn('screen.named_header', empty)
        self.assertIn('<details class="fold">', named)
        self.assertIn('Synthetic class', named)
