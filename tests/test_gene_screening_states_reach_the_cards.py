"""Gene screening and explicit reference pages must not impersonate unread SNPs."""
from __future__ import annotations

import json
import shutil
import unittest
from unittest import mock

import gene_card_support
import support
from scholion import i18n
from scholion.engine import screening


@unittest.skipUnless(shutil.which('node'), 'requires the shipped web renderer')
class GeneScreeningCards(unittest.TestCase):
    def test_every_acmg_class_preserves_reading_limits_findings_and_unknown_states(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        names = sorted(screening._panel()['genes'])
        self.assertEqual(len(names), 84)
        states = {name: ('fine', 'low', 'not_measured', 'gene_not_in_table')[i % 4]
                  for i, name in enumerate(names)}
        cases = []
        with mock.patch('scholion.limits.callability', return_value={}), \
             mock.patch('scholion.engine.genomics.gene_coverage',
                        side_effect=lambda gene, rows=None: {'state': states[gene]}):
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                for status in ('ok', 'not_run', 'metadata_unverified'):
                    with mock.patch('scholion.engine.genomics.acmg_findings', return_value={
                            'status': status, 'hits': [{'gene': names[0]}], 'coverage': {}}):
                        for group in screening.disease_classes()['held']:
                            data = screening.screen(group['key'])
                            cases.append({'data': data, 'messages': i18n.CATALOGUES[language]})
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        functions = []
        for name in ('screenVerdictLine', 'screenClassHtml', 'systemGeneRow', 'systemGeneLink', 'insightContextHTML'):
            start = page.index('function ' + name + '(')
            functions.append(page[start:page.index('\n}\n', start) + 2])
        script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const levelChip=String,geneticBriefHtml=()=>'',ladderHtml=()=>'',geneRowDetail=()=>'';
let messages={};
const t=(k,a={})=>Object.entries(a).reduce((s,[k,v])=>s.replaceAll('{'+k+'}',v),messages[k]||k);
''' + '\n'.join(functions) + r'''
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
assert.equal(cases.length,24);
for(const c of cases){
 messages=c.messages;const r=c.data,before=JSON.stringify(r),html=screenClassHtml(r);
 const cards=[...html.matchAll(/<article class="gene-card"[\s\S]*?<\/article>/g)].map(x=>x[0]);
 assert.equal(cards.length,r.genes.length);
 for(const [i,g] of r.genes.entries()){
  const card=cards[i];assert.ok(card.includes('data-reading-kind="gene_screen"'));
  assert.ok(!card.includes('class="gene-card-genotype"'));
  assert.ok(!card.includes(t('web.gene_card.no_position')));
  assert.ok(!card.includes(t('web.gene_card.reference_reading')));
  const state=r.scan_status!=='ok'||g.read==null?'unknown':g.read?'checked':'limited';
  assert.ok(card.includes(t('web.gene_card.screen_state.'+state)),g.gene+' '+state);
  if(r.scan_status==='ok')assert.ok(card.includes(t('screen.gene_findings',{n:g.findings})),g.gene);
  if(g.read_why==='coverage_low')assert.ok(card.includes(t('web.gene_card.screen_reason.low')));
 }
 assert.equal(JSON.stringify(r),before);
}
for(const read of [true,false,null]){
 const html=systemGeneRow({gene:'SYNTHETIC',unit:'gene',read,scan_status:'ok',read_why:'coverage_low',findings:0},'patient');
 assert.ok(html.includes('data-reading-kind="gene_screen"'));
 assert.ok(!html.includes(t('web.gene_card.no_position')));
}
for(const gene of ['SYNTHETIC','OTHER']){
 const link=systemGeneLink(gene,'synthetic_system');
 assert.ok(link.includes('data-gene-open="'+gene+'"'));
 assert.ok(!link.includes('data-panel='),'a personal gene click opened a reference page');
}
const context=insightContextHTML({system:'synthetic',context:{genetics:[{}]}});
assert.ok(context.includes('data-system="synthetic"')&&!context.includes('data-panel='));
const row={gene:'SYNTHETIC',rsid:'rs123'};
assert.equal(ScholionGeneCards.project(row).referenceOnly,false,'missing reading is not proof of reference mode');
const reference=geneDisplayCard(row,{referenceOnly:true});
assert.ok(reference.includes(t('web.gene_card.reference_status')));
assert.ok(reference.includes(t('web.gene_card.reference_reading')));
'''
        result = gene_card_support.run(gene_card_support.javascript() + script,
                                       input=json.dumps(cases), text=True,
                                       capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
