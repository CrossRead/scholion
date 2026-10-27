"""Reference topics must not replace personal readings when opened from the genome."""
from __future__ import annotations

import json
import shutil
import unittest
from unittest import mock

import support
import gene_card_support
from scholion import core, genome, i18n
from scholion.engine import panel_description, system
from scholion.engine.thematic_panels import thematic_catalogue


@unittest.skipUnless(shutil.which('node'), 'requires node for the shipped card renderer')
class ThematicReadingPresentation(unittest.TestCase):
    def test_all_topics_distinguish_reference_unread_and_recorded_calls_in_both_languages(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        cases=[]
        # Sourced, synthetic stored readings; no genome scan or external call.
        recorded={'rs1256328':{'genotype':'AG','source':'Synthetic stored panel reading'},
                  'rs2275376':{'genotype':'GG','source':'Synthetic stored panel reading'},
                  'rs1800562':{'genotype':'GA','source':'Synthetic stored panel reading'}}
        with mock.patch.object(genome,'available',return_value={'ready':False}), \
             mock.patch.object(core,'profile_genotypes',return_value=recorded), \
             mock.patch('scholion.engine.labs.analyze_labs',return_value={'markers':[]}):
            for language in ('en','ru'):
                i18n.set_lang(language)
                for key in thematic_catalogue()['panels']:
                    reference=panel_description(key)
                    personal=system(key)
                    self.assertTrue(reference['reference_only'])
                    self.assertTrue(personal['patient_readings'])
                    cases.append({'key':key,'language':language,'reference':reference,
                                  'personal':personal,'messages':i18n.CATALOGUES[language]})
        self.assertEqual(len(cases),30)
        page=(support.SRC/'scholion/web/index.html').read_text(encoding='utf-8')
        functions=[]
        for name in ('thematicPanelLinks','renderThematicPanel','geneRegionCard'):
            start=page.index('function '+name+'(')
            functions.append(page[start:page.index('\n}\n',start)+2])
        script=r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
let messages={};
const t=(k,a={})=>Object.entries(a).reduce((s,[k,v])=>s.replaceAll('{'+k+'}',v),messages[k]||k);
const pageHead=(h,n,f)=>h+n+f.join(''),factHtml=(v,n)=>v+n,levelChip=String;
const geneticBriefHtml=()=>'',fmtDate=String,fmtNum=String;
'''+'\n'.join(functions)+r'''
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
let called=0,unread=0,referenceRows=0;
for(const c of cases){
 messages=c.messages;
 const before=JSON.stringify(c);
 const personal=renderThematicPanel(c.personal),reference=renderThematicPanel(c.reference);
 assert.ok(personal.includes(t('thematic.readings')),c.key);
 assert.ok(reference.includes(t('thematic.reference')),c.key);
 assert.ok(!reference.includes('class="gene-card-genotype"'),c.key+' reference is not a genotype badge');
 const cards=[...personal.matchAll(/<article class="gene-card"[\s\S]*?<\/article>/g)].map(m=>m[0]);
 for(const p of c.personal.positions){
  const card=cards.find(x=>x.includes('data-position="'+esc(p.rsid)+'"'));
  assert.ok(card,c.key+' '+p.rsid);
  if(p.reading.read){
   called++;
   assert.ok(card.includes('data-reading-kind="called"'),p.rsid);
   assert.ok(card.includes('class="gene-card-genotype">'+esc(p.reading.genotype)+'</span>'),p.rsid);
   assert.ok(!card.includes(t('web.gene_card.reference_reading')),p.rsid);
   assert.ok(card.includes('Synthetic stored panel reading'),p.rsid+' provenance');
  }else{
   unread++;
   assert.ok(card.includes('data-reading-kind="unread"'),p.rsid);
   assert.ok(!card.includes('class="gene-card-genotype"'),p.rsid);
   assert.ok(card.includes(esc(p.reading.message)),p.rsid+' refusal');
  }
 }
 referenceRows+=(reference.match(/data-reading-kind="reference"/g)||[]).length;
 assert.equal(JSON.stringify(c),before,c.key+' input mutated');
 const links=thematicPanelLinks([{key:c.key,label:c.key,genes:1}]);
 assert.ok(links.includes('data-system="'+c.key+'"')&&!links.includes('data-panel='),c.key);
}
assert.ok(called>0&&unread>0&&referenceRows>0);
// A supplied flat reading must not be erased by a thematic presentation adapter.
const flat=renderThematicPanel({label:'Synthetic',counts:{},patient_readings:true,
 genes:[{gene:'ALPL',positions:[{rsid:'rs1256328',genotype:'AG',read:true}]}]});
assert.ok(flat.includes('class="gene-card-genotype">AG</span>'));
// A real complex call is still a reading when its zygosity is not resolved.
const complex=renderThematicPanel({label:'Synthetic',counts:{},patient_readings:true,
 genes:[{gene:'ALPL',positions:[{rsid:'rs1256328',genotype:'AGG/A',read:true}]}]});
assert.ok(complex.includes('class="gene-card-genotype">AGG/A</span>'));
assert.ok(complex.includes(t('finding.zygosity.unknown')));
assert.ok(!complex.includes(t('web.gene_card.not_read')));
'''
        result=gene_card_support.run(gene_card_support.javascript()+script,
                                     input=json.dumps(cases),text=True,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr[-4000:])
