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
                  'rs1800562':{'genotype':'GA','source':'Synthetic stored panel reading'},
                  'rs1800497':{'genotype':'GA','source':'Synthetic stored panel reading'},
                  'rs11174811':{'genotype':'CC','source':'Synthetic stored panel reading'}}
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
        for language in ('en', 'ru'):
            panels = {c['key']: c['personal'] for c in cases if c['language'] == language}
            readings = []
            for key in ('vitamin_genetics', 'methylation'):
                gene = next(g for g in panels[key]['genes'] if g['gene'] == 'FOLR1')
                position = next(p for p in gene['positions'] if p['rsid'] == 'rs121918405')
                readings.append(position['reading'])
                self.assertEqual(position['reference_context']['catalogue_annotation']['panels'], ['vitamin_genetics'])
            self.assertEqual(*readings)
        page=(support.SRC/'scholion/web/index.html').read_text(encoding='utf-8')
        functions=[]
        for name in ('thematicPanelLinks','cataloguePositionCards','renderThematicPanel','geneRegionCard','bindPanelRegionDetails'):
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
 if(c.key==='neuro_associations'){
  const taq=cards.filter(card=>card.includes('data-position="rs1800497"'));
  assert.equal(taq.length,1);
  assert.ok(taq[0].includes('data-gene="ANKK1"'));
  for(const card of [taq[0],cards.find(row=>row.includes('data-position="rs11174811"'))]){
   assert.ok(card.includes(t('meaning.personal')));
   assert.ok(card.includes('class="gene-card-genotype"'));
  }
 }
 for(const card of cards.filter(card=>card.includes('data-gene-description'))){
  assert.ok(card.includes('<div class="gene-card-label">'+esc(t('meaning.personal'))+'</div>'),c.key);
 }
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
// Every gene with curated positions starts with those positions, not an empty
// region summary pretending to be the person's reading (AMN regression).
for(const c of cases){
 messages=c.messages;
 for(const gene of c.personal.genes.filter(g=>g.positions.length)){
  const html=renderThematicPanel({...c.personal,genes:[gene],regions:[]});
  assert.ok(!html.includes('data-reading-kind="gene_region"'),c.key+' '+gene.gene);
  assert.equal((html.match(/data-panel-region=/g)||[]).length,1,gene.gene);
 }
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
// A region-only card keeps the technical table in the gene-region details.
const region={gene:'SYNTHETIC',positions:[],reading_request:{gene:'SYNTHETIC'},reference_context:{gene_function:'Synthetic function'},
 region_reading:{status:'ok',gene:'SYNTHETIC',location:{assembly:'GRCh38',chrom:'1',start:1,end:100},
 variants:{unannotated_rows:Array.from({length:100},(_,i)=>({chrom:'1',pos:i+1,genotype:'0/1',personal_alleles:['A','G'],depth:22}))}}};
const before=JSON.stringify(region),shell=renderThematicPanel({label:'Synthetic',counts:{},patient_readings:true,genes:[region]});
assert.ok(shell.includes('data-reading-kind="gene_region" data-card-kind="gene"'));
const coordinate = shell.indexOf('GRCh38 · 1:1–100');
assert.ok(coordinate >= 0 && coordinate < shell.indexOf('data-panel-region-body'));
assert.ok(shell.includes(t('thematic.region_reading')));
assert.ok(!shell.includes(t('web.gene_card.no_position')));
assert.ok(!shell.includes(t('web.gene_card.inheritance_unknown')));
assert.ok(shell.includes('data-panel-region-body'));
assert.ok(shell.includes(t('thematic.region_details')));
assert.ok(shell.indexOf('data-gene-inheritance')<shell.indexOf('data-panel-region='));
assert.ok(shell.indexOf('data-panel-region=')<shell.indexOf('data-read-gene='));
assert.ok(shell.indexOf('data-read-gene=')<shell.indexOf('</article>'));
const withPositions={...region,positions:[{rsid:'rs1',genotype:'AG',read:true},{rsid:'rs2',genotype:'AA',read:true}]};
const grouped=renderThematicPanel({label:'Synthetic',counts:{},patient_readings:true,genes:[withPositions]});
assert.equal((grouped.match(/data-panel-region=/g)||[]).length,1);
assert.match(grouped, /<\/article><details class="gene-card-fold gene-card-region"[\s\S]*?<\/details><\/div>\s*<\/section>/);
assert.ok(!shell.includes('data-gene-region-records'));
assert.equal((shell.match(/data-gene-card /g)||[]).length,1);
const handlers={},close={},body={innerHTML:'',querySelector:()=>close};
const detail={open:false,dataset:{panelRegion:'SYNTHETIC'},querySelector:()=>body,addEventListener:(k,f)=>handlers[k]=f};
bindPanelRegionDetails({querySelectorAll:()=>[detail]},{genes:[region]});
assert.equal(body.innerHTML,'');handlers.toggle();assert.equal(body.innerHTML,'');
detail.open=true;handlers.toggle();
const expected=geneRegionCard({...region.region_reading,reference_context:region.reference_context},[]).replace('id="gc-close"','data-close-gene');
assert.equal(body.innerHTML,expected);
assert.ok(body.innerHTML.includes('data-gene-region-records'));
assert.equal((body.innerHTML.match(/<th scope="row">/g)||[]).length,100);
assert.ok(body.innerHTML.includes('A/G')&&body.innerHTML.includes('22×'));
assert.ok(!body.innerHTML.includes('<details'));
close.onclick();assert.equal(detail.open,false);
body.innerHTML+='USER STATE';detail.open=true;handlers.toggle();handlers['scholion:expand']();
assert.equal(body.innerHTML,expected+'USER STATE');
assert.equal(JSON.stringify(region),before);

'''
        result=gene_card_support.run(gene_card_support.javascript()+script,
                                     input=json.dumps(cases),text=True,capture_output=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr[-4000:])
