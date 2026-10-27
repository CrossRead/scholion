"""All web entry points use the same card without reinterpreting clinical facts."""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest

import support
import gene_card_support
from scholion import i18n


@unittest.skipUnless(shutil.which('node'), 'requires node for the shipped web renderer')
class SharedCards(unittest.TestCase):
    def execute(self, script):
        result = subprocess.run([shutil.which('node')], input=gene_card_support.javascript()+script,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr[-4000:])

    def test_reading_status_and_inheritance_are_never_inferred_from_allele_presence(self):
        messages = {lang: i18n.CATALOGUES[lang] for lang in ('en', 'ru')}
        self.execute('const messages='+json.dumps(messages)+r''';
const assert=require('node:assert/strict');
const esc=x=>String(x??'').replaceAll('<','&lt;').replaceAll('"','&quot;'),levelChip=String;
const geneticBriefHtml=()=>'';
for(const lang of ['en','ru']){
 const t=(key,args={})=>Object.entries(args).reduce((s,[k,v])=>s.replaceAll('{'+k+'}',v),messages[lang][key]||key);
 const options={t,escape:esc,grade:String};
 const base={gene:'GENE',rsid:'rs123',level:'A',read:true,state:'het',genotype:'AG',carrier:true,
 reference_context:{gene_function:'Function.',variant_context:'Variant interpretation.'}};
 const before=JSON.stringify(base),plain=ScholionGeneCards.render(base,options);
 assert.ok(!plain.includes('data-personal-status'));
 assert.ok(plain.includes(t('finding.zygosity.heterozygous')));
 assert.ok(plain.indexOf(t('web.gene_card.confidence'))<plain.indexOf(t('web.gene_card.identity')));
 assert.ok(plain.indexOf(t('web.gene_card.identity'))<plain.indexOf(t('web.gene_card.reading')));
 assert.ok(plain.indexOf(t('web.gene_card.reading'))<plain.indexOf(t('web.gene_card.meaning')));
 for(const state of ['carrier_context','dominant_review','recessive_review','x_linked_review','phase_unresolved','inheritance_mixed']){
  const p={...base,personal_context:{status:state,label:'STATUS '+state,summary:'Existing personal meaning.',
   zygosity:'heterozygous',alternative_copies:1,inheritance_label:'Existing inheritance',limitations:'Existing caveat'}};
  const html=ScholionGeneCards.render(p,options);
  assert.ok(html.includes('STATUS '+state)&&html.includes('Existing caveat'));
  assert.ok(html.indexOf('STATUS '+state)<html.indexOf('gene-card-grid'));
  assert.ok(html.includes('Existing inheritance'));
  assert.equal((html.match(/data-gene-inheritance/g)||[]).length,1);
 }
 const unavailable=ScholionGeneCards.render({...base,reading:{genotype:'AA',confidence:'assumed_ref',note:'Not called'},genotype:'AA'},options);
 assert.ok(!unavailable.includes('>AA<')&&!unavailable.includes(t('finding.zygosity.homozygous')));
 assert.ok(unavailable.includes('Not called')&&unavailable.includes(t('web.genome.assumed_ref')));
 const multi=ScholionGeneCards.project({...base,genotype:'0/2',personal_context:{allele_identity_supported:false,alternative_copies:null}});
 assert.equal(multi.copies,null);
 const gene=ScholionGeneCards.render({gene:'GENE',level:'A',reference_context:{gene_function:'Function.'}},options);
 assert.ok(gene.includes(t('web.gene_card.no_position'))&&!gene.includes('Scholion interpretation'));
 const joint=ScholionGeneCards.render({gene:'APOE',display_genotype:'e2/e4',rs429358:'CT',rs7412:'CT'}, {...options,compound:true});
 assert.ok(joint.includes(t('web.gene_card.combination'))&&!joint.includes(t('finding.zygosity.heterozygous')));
 const low=ScholionGeneCards.render({...base,reading:{genotype:'AG',confidence:'called',depth:4,note:'Low depth'}},options);
 assert.ok(low.indexOf('Low depth')<low.indexOf('data-gene-annotations'));
 assert.ok(!/<details[^>]*\bopen(?:\s|>)/.test(plain));
 assert.equal(JSON.stringify(base),before);
}
''')

    def test_genome_panels_radar_screening_labs_and_visit_share_the_base(self):
        page = (support.SRC/'scholion/web/index.html').read_text(encoding='utf-8')
        names = ('genomeCard','genomeGeneTable','shownGenetics','hypothesisCountHtml',
                 'genSummaryHtml','genTableHtml','panelHtml','markerGeneticsRow',
                 'renderClinvar','renderACMG','screenClassHtml','visitReportGenes')
        functions=[]
        for name in names:
            start=page.index('function '+name+'(')
            functions.append(page[start:page.index('\n}\n',start)+2])
        self.execute(r'''
const assert=require('node:assert/strict');
const esc=x=>String(x??''),t=(k,a={})=>k+Object.values(a).join(' '),plural=String,fmtDate=String;
const levelChip=x=>`<span data-grade="${x}">${x}</span>`,systemGeneLink=g=>g;
const geneticBriefHtml=()=>'',geneticComparisonHTML=()=>'',clinicalBasisHTML=()=>'',geneRowDetail=()=>'';
const levelNoteHtml=()=>'',routeHtml=()=>'',underLoadHtml=()=>'',ladderHtml=()=>'',systemPolygenicHtml=()=>'';
const screenVerdictLine=()=>'',clnsigText=String,diseaseText=String,visitSourceLinks=()=>'',systemLinkHtml=()=>'';
const badge=(a,b)=>b;
'''+'\n'.join(functions)+r'''
const row={gene:'GENE',rsid:'rs123',read:true,genotype:'AG',state:'het',unit:'position',level:'A',tier:'pathogenic',
 reference_context:{gene_function:'Shared biology.',variant_context:'Shared variant context.'},
 personal_context:{status:'carrier_context',label:'Existing carriage',summary:'Existing meaning',zygosity:'heterozygous',alternative_copies:1}};
const gen={rows:[row],positions:[row]},before=JSON.stringify(gen);
const views=[genomeCard(row),genomeGeneTable([row]),genSummaryHtml(gen,{register:'patient'}),
 genTableHtml(gen,{register:'patient'},'patient'),panelHtml(gen,{register:'patient'},'patient'),
 markerGeneticsRow({positions:[row]}),renderClinvar({status:'ok',count:1,hits:[row],counts:{}}),
 renderACMG({status:'ok',carriers:[row]}),screenClassHtml({genes:[row]}),visitReportGenes([row],'synthetic')];
const baseOf=html=>html.match(/<div class="gene-card-grid">[\s\S]*?(?=<details)/)[0].replace(/<\/?(?:a|b|strong)(?:\s[^>]*)?>/g,'');
const base=baseOf(views[0]);
for(const html of views){
 assert.equal((html.match(/data-gene-card /g)||[]).length,1);
 assert.equal(baseOf(html),base);
 assert.ok(!/<details[^>]*\bopen(?:\s|>)/.test(html));
 assert.ok(html.includes('Existing carriage')&&html.includes('Existing meaning'));
}
assert.equal(JSON.stringify(gen),before);
''')
