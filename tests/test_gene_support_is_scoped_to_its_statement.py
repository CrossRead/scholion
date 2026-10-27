"""A reference citation is not missing support for a different clinical claim."""
from __future__ import annotations

import json
import shutil
import unittest

import gene_card_support
import support
from scholion import core, i18n
from scholion.conclusion_basis import guard_position
from scholion.panel_reference import interpretation_context, reference_context


@unittest.skipUnless(shutil.which('node'), 'requires the actual web renderer')
class ScopedSupport(unittest.TestCase):
    def test_cyp2r1_reference_identifiers_remain_distinct_from_automatic_claim_support(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        catalogue = core._read_knowledge('system_gene_panels.json')
        spec = next(p for p in catalogue['systems']['micronutrients']['positions']
                    if p.get('rsid') == 'rs10741657')
        cases = []
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            summary = core._localized(spec['text']['het'], language)
            interpretation = interpretation_context(spec, 'B', summary)
            row = guard_position(spec, {
                'gene': 'CYP2R1', 'rsid': 'rs10741657', 'level': 'B',
                'genotype': 'AG', 'read': True, 'state': 'het', 'findings': 0,
                'interpretation': interpretation,
                'reference_context': reference_context(spec, 'B')})
            self.assertEqual(['mechanism'], row['conclusion_basis']['missing'])
            self.assertIn('20541252', row['conclusion_basis']['source'])
            self.assertEqual(0, row['findings'])
            self.assertIn('PMID:20541252', row['reference_context']['variant_source'])
            cases.append({'row': row, 'messages': i18n.CATALOGUES[language]})
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        functions = []
        for name in ('referenceContextHtml', 'mechanismHtml', 'geneticBriefHtml'):
            start = page.index('function ' + name + '(')
            functions.append(page[start:page.index('\n}\n', start) + 2])
        script = r'''
const assert=require('node:assert/strict'),fs=require('node:fs');
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
const levelChip=String,passportHtml=()=>'',authorNoteHtml=()=>'',clinicalBasisHTML=()=>'';
let messages={};
const t=(k,a={})=>Object.entries(a).reduce((s,[k,v])=>s.replaceAll('{'+k+'}',v),messages[k]||k);
''' + '\n'.join(functions) + r'''
for(const c of JSON.parse(fs.readFileSync(0,'utf8'))){
 messages=c.messages;
 const before=JSON.stringify(c.row),html=geneDisplayCard(c.row);
 assert.equal((html.match(/data-conclusion-withheld/g)||[]).length,1);
 assert.equal((html.match(/data-subclaim-basis/g)||[]).length,1);
 assert.equal((html.match(/class="gene-support"/g)||[]).length,1);
 assert.ok(!html.includes('data-catalogue-support'), 'same gaps repeated at catalogue and clinical levels');
 assert.ok(!html.includes(t('interpretation.gaps',{missing:c.row.interpretation.missing.map(k=>t('conclusion.missing.'+k)).join(', ')})));
 for(const text of [c.row.interpretation.summary,c.row.interpretation.source,
  t('web.gene_card.support_scope'),
  t('web.gene_card.reference_separate'),t('conclusion.subclaim.expect'),
  t('conclusion.missing.mechanism'),t('conclusion.missing.parent_basis')])assert.ok(html.includes(esc(text)),text);
 assert.ok(html.includes('https://pubmed.ncbi.nlm.nih.gov/20541252/'));
 assert.equal(JSON.stringify(c.row),before,'presentation changed the guarded facts');
}
// A separate catalogue-only gap and an unknown refusal reason must survive.
const partial={gene:'SYNTHETIC',rsid:'rs123',interpretation:{summary:'Qualified interpretation',missing:['mechanism']}};
assert.ok(geneDisplayCard(partial).includes('data-catalogue-support'));
const refused={...partial,conclusion_basis:{status:'incomplete',reason:'Unknown structural refusal'}};
assert.ok(geneDisplayCard(refused).includes('Unknown structural refusal'));
'''
        result = gene_card_support.run(gene_card_support.javascript() + script,
                                       input=json.dumps(cases), text=True,
                                       capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
