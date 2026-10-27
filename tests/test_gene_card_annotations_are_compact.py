"""Compact cards preserve qualifications and independent database assertions."""
from __future__ import annotations

import json
import shutil
import unittest

import gene_card_support
from scholion import finding_context, i18n
from scholion.panel_reference import attach_finding_biology


@unittest.skipUnless(shutil.which('node'), 'requires the shipped card renderer')
class CompactAnnotations(unittest.TestCase):
    def test_comparison_separates_observations_conditions_and_reference_explanation(self):
        page = gene_card_support.source()
        start = page.index('function geneticComparisonHTML(')
        function = page[start:page.index('\n}\n', start) + 2]
        script = r'''
const assert=require('node:assert/strict');
const esc=String,t=k=>k,fmtDate=String,levelChip=String,systemGeneLink=String;
const geneticBriefHtml=()=>'';
''' + function + r'''
const row={gene:'HFE',rsid:'rs1800562',genotype:'GA',state:'het',status:'hypothesis',
 status_label:'Not an established individual link',eligible:false,applicable:false,
 level:'B',variant_level:'A',summary:'Reference explanation for two copies',
 comparison:'Qualified comparison',reason_labels:['Unknown specimen','Wrong units','Unknown specimen'],
 observations:[{point:{name:'Synthetic ferritin',value:194.6,unit:'ng/mL',date:'2026-10-13'}}],
 limitations:'Synthetic caveat',knowledge:{},quality:{},source_links:['https://example.org/evidence']};
const before=JSON.stringify(row),html=geneticComparisonHTML([row],true),context=html.split('class="genlab-comparison"')[1];
const main=context.split('<details class="fold genlab-details">')[0];
assert.ok(main.includes('Not an established individual link'));
assert.ok(main.includes('data-genlab-not-applicable'));
assert.ok(main.includes('<dl class="genlab-measurements">'));
assert.ok(main.includes('<dt>Synthetic ferritin</dt>'));
assert.ok(main.includes('194.6 ng/mL')&&main.includes('<time>2026-10-13</time>'));
assert.equal((main.match(/class="genlab-applicability"/g)||[]).length,2);
assert.ok(!main.includes(row.summary)&&!main.includes(row.comparison));
for(const text of [row.summary,row.comparison,row.limitations,row.source_links[0]])assert.ok(context.includes(text));
const applicable=geneticComparisonHTML([{...row,applicable:true,eligible:true}],true).split('<details class="fold genlab-details">')[0];
assert.ok(applicable.includes(row.comparison));
assert.equal(JSON.stringify(row),before);
'''
        result = gene_card_support.run(gene_card_support.javascript() + script,
                                       text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])

    def test_real_prss1_context_has_one_compact_meaning_and_no_repeated_gencc_section(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        cases = []
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            row = {'gene': 'PRSS1', 'rsid': 'rs202003805', 'genotype': '0/1',
                   'chrom': '7', 'pos': '1', 'ref': 'C', 'alt': 'T', 'filter': 'PASS',
                   'clnsig': 'Pathogenic/Likely_pathogenic', 'clndn': 'Hereditary pancreatitis'}
            finding_context.attach([row])
            attach_finding_biology([row])
            cases.append({'row': row, 'messages': i18n.CATALOGUES[language]})
        page = gene_card_support.source()
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
 const before=JSON.stringify(c.row),row=c.row,html=geneFindingCards(row);
 const visible=html.split('data-gene-description>')[1].split('</div></div>')[0];
 assert.ok(visible.includes(row.gene_contexts[0].reference_context.gene_function));
 assert.ok(!visible.includes(row.personal_context.inclusion_reason));
 assert.ok(!visible.includes(t('reference.variant_unknown')));
 assert.ok(html.includes(esc(row.personal_context.inclusion_reason)));
 assert.ok(html.includes(esc(row.personal_context.summary)));
 assert.ok(html.includes(esc(t('reference.variant_unknown'))));
 const annotations=html.split('data-gene-annotations>')[1].split('<details class="gene-card-fold" data-gene-inheritance>')[0];
 assert.ok(!annotations.includes('data-gencc-assertion'), 'legacy section repeated the same GenCC assertions');
 const assertions=row.gene_contexts[0].reference_context.gencc_assertions;
 assert.ok(assertions.length>1);
 assert.equal((annotations.match(/data-gene-db="GenCC"/g)||[]).length,ScholionGeneCards.groupAssertions(assertions).length);
 assert.ok(annotations.includes('data-gencc-submissions'));
 assert.equal(JSON.stringify(row),before);
}
// Equivalent claims can share a heading; distinct sources, dates, IDs and
// contradictory classifications or inheritance must survive unchanged.
const a={gene:'GENE',disease_id:'MONDO:synthetic',disease:'Synthetic disease',
 moi_code:'AD',classification:'Definitive',submitter:'Source A',curated_on:'2024-01-01',
 public_report:'https://example.org/a',submission_ids:['record-a']};
const rows=[a,{...a},{...a,submitter:'Source B',public_report:'https://example.org/b'},
 {...a,curated_on:'2025-01-01'}, {...a,submission_ids:['record-b']},
 {...a,classification:'Disputed'}, {...a,moi_code:'AR'}, {...a,disease_id:'MONDO:another'}];
const before=JSON.stringify(rows),groups=ScholionGeneCards.groupAssertions(rows);
assert.equal(groups.length,4);
assert.deepEqual(groups.map(g=>g.witnesses.length),[4,1,1,1]);
assert.equal(JSON.stringify(rows),before);
const options={t,escape:esc,grade:String};
const html=ScholionGeneCards.render({gene:'GENE',rsid:'rs123',reference_context:{gencc_assertions:rows}},options);
assert.equal((html.match(/data-gene-db="GenCC"/g)||[]).length,4);
assert.equal((html.match(/data-gencc-witness/g)||[]).length,7);
for(const value of ['Source A','Source B','2025-01-01','record-a','record-b','Disputed','AR','https://example.org/b'])assert.ok(html.includes(value),value);
'''
        result = gene_card_support.run(gene_card_support.javascript() + script,
                                       input=json.dumps(cases), text=True,
                                       capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
