"""Navigation preserves the difference between a substance and its clinical effect."""
from __future__ import annotations

import shutil
import subprocess
import unittest

import support
import gene_card_support
from scholion import i18n
from scholion.engine import class_genotype, system_panels
from scholion.format_prescription import medications_report
from tests.test_a_prescription_reaches_its_genes_through_the_system import _Pinned


class TestRegimenContext(_Pinned):
    def test_known_nutrients_get_links_without_a_treatment_effect(self):
        self.write_meds([{'name': 'zinc', 'dose': 'as recorded'}, {'name': 'glycine'},
                         {'name': 'melatonin', 'status': 'stopped'}])
        before=(self.profile/'medications.json').read_bytes()
        self.addCleanup(i18n.set_lang, i18n.lang())
        for language in ('en','ru'):
            i18n.set_lang(language)
            result=class_genotype.medications_view()
            zinc,glycine,stopped=result['medications']
            self.assertEqual(zinc['system_context']['systems'], ['immune','micronutrients'])
            self.assertEqual(glycine['system_context']['systems'], ['amino_acids'])
            self.assertTrue(all(x['relation']=='nutrient_context' and x['source']
                                for x in zinc['system_context']['system_links']))
            self.assertNotIn('system_context',stopped)
            formatted=medications_report(result)
            self.assertIn(i18n.t('radar.domain.immune'),formatted)
            self.assertIn(i18n.t('system.meds.relation.nutrient_context'),formatted)
            layer=system_panels._medications_layer('amino_acids')
            self.assertIn('glycine',[x['name'] for x in layer['rows']])
        self.assertEqual((self.profile/'medications.json').read_bytes(),before)

    def test_an_outside_context_is_not_a_forced_immune_indication(self):
        row=system_panels.medication_system_context({'name':'Lactoflorene'})
        self.assertEqual(row['map_status'],'outside_model')
        self.assertEqual(row['systems'],[])
        self.assertEqual(row['outside_contexts'][0]['disposition'],'outside_model')
        self.assertTrue(row['outside_contexts'][0]['note'])
        unknown=system_panels.medication_system_context({'name':'unrecognised synthetic compound'})
        self.assertEqual(unknown['map_status'],'no_class')

    def test_source_identity_never_validates_another_formulation(self):
        result=system_panels.medication_system_context({'name':'elamipretide'})
        self.assertEqual({x['relation'] for x in result['system_links']},{'substance_context'})
        self.assertTrue(all(x['source'].startswith('https://www.fda.gov/') for x in result['system_links']))
        self.assertTrue(all(x['note'] for x in result['system_links']))
        experimental=system_panels.medication_system_context({'name':'BPC-157'})
        self.assertEqual({x['relation'] for x in experimental['system_links']},{'research_context'})


class TestSharedGeneCard(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'node is needed for the actual renderer')
    def test_region_readings_keep_function_first_and_noncoding_variants_folded(self):
        text=(support.SRC/'scholion/web/index.html').read_text(encoding='utf-8')
        start=text.index('function geneRegionCard(')
        function=text[start:text.index('\n}\n',start)+2]
        script="""
const assert=require('node:assert/strict');
const esc=x=>String(x??''),t=(k,a)=>k+' '+Object.values(a||{}).join(' ');
const DISPLAY_MODE='patient',levelChip=x=>x,geneticBriefHtml=r=>r.reference_context.gene_function;
"""+function+"""
const html=geneRegionCard({gene:'SYNTHETIC',reference_context:{gene_function:'Known function'},
 location:{},coverage:{source:null},variants:{total:2,coding:1,
 coding_rows:[{chrom:'1',pos:123,ref:'A',alt:'G',genotype:'0/1',personal_alleles:['A','G'],depth:29,
 protein:{kind:'missense',hgvs_p:'p.A1G'}}],
 noncoding_rows:[{chrom:'1',pos:456,ref:'C',alt:'T',genotype:'1/1',personal_alleles:['T','T'],depth:25}]},
 reading_summary:{message:'Coverage explicitly unknown'}});
assert.ok(html.indexOf('Known function')<html.indexOf('A/G'));
assert.ok(html.includes('p.A1G')&&html.includes('1:456')&&html.includes('T/T'));
assert.match(html,/<details class="fold"><summary>gene.noncoding_rows 1/);
assert.ok(html.includes('Coverage explicitly unknown')&&html.includes('gene.annotation_scope'));
"""
        script = gene_card_support.javascript() + script
        completed=gene_card_support.run(script,capture_output=True,text=True,
                                 stdin=subprocess.DEVNULL,timeout=10)
        self.assertEqual(completed.returncode,0,completed.stderr)

    @unittest.skipUnless(shutil.which('node'),'node is needed for the actual renderer')
    def test_locus_card_puts_known_function_before_the_reading_and_support(self):
        text=(support.SRC/'scholion/web/index.html').read_text(encoding='utf-8')
        functions=[]
        for name in ('geneticPreviewHtml','geneticBriefHtml','genomeCard'):
            start=text.index('function '+name+'(')
            functions.append(text[start:text.index('\n}\n',start)+2])
        script="""
const assert=require('node:assert/strict');
const esc=x=>String(x??''),t=(k,a)=>k+' '+Object.values(a||{}).join(' ');
const DISPLAY_MODE='patient';
const mechanismHtml=()=>'',authorNoteHtml=()=>'',clinicalBasisHTML=()=>'';
const levelChip=x=>x;
"""+'\n'.join(functions)+"""
const r={rsid:'rsSynthetic',gene:'SYNTHETIC',chrom:'1',pos:1,level:'E',
 reference_context:{gene_function:'Known gene function',variant_status:'unknown',level:'E'},
 result:{genotype:'GG',confidence:'confirmed_ref',depth:31}};
const html=genomeCard(r);
assert.ok(html.includes('Known gene function')&&html.includes('GG'));
assert.ok(html.indexOf('gene-card-reading')<html.indexOf('gene-card-description'));
assert.ok(html.indexOf('GG')<html.indexOf('data-gene-annotations'));
assert.equal((html.match(/data-gene-description/g)||[]).length,1);
"""
        script = gene_card_support.javascript() + script
        completed=gene_card_support.run(script,capture_output=True,text=True,
                                 stdin=subprocess.DEVNULL,timeout=10)
        self.assertEqual(completed.returncode,0,completed.stderr)
