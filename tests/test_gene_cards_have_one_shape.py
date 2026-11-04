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
 reference_context:{gene_function:'Function.',variant_status:'described',variant_context:'Variant interpretation.'}};
 const before=JSON.stringify(base),plain=ScholionGeneCards.render(base,options);
 assert.ok(!plain.includes('data-personal-status'));
 assert.ok(plain.includes(t('finding.zygosity.heterozygous')));
 assert.ok(plain.indexOf(t('web.gene_card.confidence'))<plain.indexOf(t('web.gene_card.identity')));
 assert.ok(plain.indexOf(t('web.gene_card.identity'))<plain.indexOf(t('web.gene_card.reading')));
 assert.ok(plain.indexOf('Function.')<plain.indexOf(t('meaning.personal')) && plain.indexOf(t('meaning.personal'))<plain.indexOf(t('web.gene_card.reading')));
 assert.ok(plain.includes(encodeURIComponent('GENE[PREF] AND 9606[taxid]')+'" target="_blank"'));
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
 assert.ok(gene.includes(t('web.gene_card.no_personal_reading'))&&!gene.includes('Scholion interpretation'));
 const joint=ScholionGeneCards.render({gene:'APOE',display_genotype:'e2/e4',rs429358:'CT',rs7412:'CT'}, {...options,compound:true});
 assert.ok(joint.includes(t('web.gene_card.combination'))&&!joint.includes(t('finding.zygosity.heterozygous')));
 const low=ScholionGeneCards.render({...base,reading:{genotype:'AG',confidence:'called',depth:4,note:'Low depth'}},options);
 assert.ok(low.indexOf('Low depth')<low.indexOf('data-gene-annotations'));
 const longNote=t('genome.low_depth',{depth:7});
 const compact=ScholionGeneCards.render({...base,reading:{genotype:'AG',confidence:'called',depth:7,low_depth:true,
   note:'Source note'+t('genome.low_depth_suffix',{depth:7})}},options);
 const [visible,details]=compact.split('data-gene-inheritance');
 assert.equal(visible.split('7×').length,2);
 assert.ok(visible.includes(t('web.gene_card.low_depth',{value:7}))&&visible.includes('Source note'));
 assert.ok(!visible.includes(longNote)&&!visible.includes(t('genlab.quality.low_depth')+'</p>'));
 assert.ok(!details.includes(longNote) && !details.includes('7×'));
 assert.ok(!/<details[^>]*\bopen(?:\s|>)/.test(plain));
 assert.equal(JSON.stringify(base),before);
}
''')

    def test_genome_panels_radar_screening_labs_and_visit_share_the_base(self):
        page = (support.SRC/'scholion/web/index.html').read_text(encoding='utf-8')
        names = ('genomeCard','genomeGeneTable','shownGenetics','hypothesisCountHtml',
                 'genSummaryHtml','genTableHtml','panelHtml','markerGeneticsRow',
                 'renderClinvar','renderACMG','screenClassHtml','visitReportGenes','renderLipidGenetics',
                 'prescriptionGeneCard','pgxCard','contextHtml','variantStateLine')
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
const coverageLine=()=> 'Supplied coverage.', LEVEL={unknown:{cls:'unknown',key:'unknown'}};
'''+'\n'.join(functions)+r'''
const row={gene:'GENE',rsid:'rs123',read:true,genotype:'AG',state:'het',unit:'position',level:'A',tier:'pathogenic',
 reference_context:{gene_function:'Shared biology.',variant_context:'Shared variant context.',
  gene_source:'https://www.ncbi.nlm.nih.gov/gene/1557'},
 personal_meaning:{scope:'genotype_hypothesis',reading_binding:{status:'verified',genotype:'AG'},
  summary:'Supplied possible meaning.',comparator:'Supplied comparison.',mechanism:'Supplied mechanism.',
  context:[{comparison:'Supplied lab context.'}],limitations:'Supplied limitation.'},
 personal_context:{status:'carrier_context',label:'Existing carriage',summary:'Existing meaning',zygosity:'heterozygous',alternative_copies:1}};
const gen={rows:[row],positions:[row]},before=JSON.stringify(gen);
const views=[genomeCard(row),genomeGeneTable([row]),genSummaryHtml(gen,{register:'patient'}),
 genTableHtml(gen,{register:'patient'},'patient'),panelHtml(gen,{register:'patient'},'patient'),
 markerGeneticsRow({positions:[row]}),renderClinvar({status:'ok',count:1,hits:[row],counts:{}}),
 renderACMG({status:'ok',carriers:[row]}),screenClassHtml({genes:[row]}),visitReportGenes([row],'synthetic'),
 pgxCard({status:'ok',gene:'GENE',markers_found:[row]})];
const baseOf=html=>html.match(/<div class="gene-card-grid">[\s\S]*?(?=<details)/)[0].replace(/<\/?(?:a|b|strong)(?:\s[^>]*)?>/g,'');
const base=baseOf(views[0]);
for(const html of views){
 assert.equal((html.match(/data-gene-card /g)||[]).length,1);
 assert.equal(baseOf(html),base);
 assert.ok(!/<details[^>]*\bopen(?:\s|>)/.test(html));
 assert.ok(html.includes('Existing carriage')&&html.includes('Existing meaning'));
 const chain=['Shared biology.','meaning.personal','Supplied possible meaning.','Supplied comparison.',
  'Supplied mechanism.','Supplied lab context.','Supplied limitation.','data-grade="A"'];
 assert.ok(chain.every((value,i)=>html.includes(value) && (!i || html.indexOf(chain[i-1]) < html.indexOf(value))));
 assert.ok(html.includes('href="https://www.ncbi.nlm.nih.gov/gene/1557" target="_blank" rel="noopener noreferrer">GENE</a>'));
 assert.ok(html.includes('href="#variant/rs123" data-rs-open="rs123"'));
}
assert.equal(JSON.stringify(gen),before);
const prescription={...row,rsid:null,personal_meaning:null,personal_context:null,genotype:null,
 label:'Supplied drug assessment.',phenotype:'IM',cpic_level:'A',coverage:{state:'low'},markers:[row]};
for(const computable of [true,false]){
 const html=prescriptionGeneCard({...prescription,computable});
 assert.ok(html.includes('href="https://www.ncbi.nlm.nih.gov/gene/1557"')&&html.includes('Supplied drug assessment.'));
 assert.ok(html.includes('Supplied coverage.')&&html.includes('CPIC A'));
 assert.ok(!html.includes('gene-card-genotype')&&!html.includes('web.gene_card.no_personal_reading'));
 if(computable)assert.ok(html.includes('web.rx.your_phenotype IM'));
 else assert.ok(html.includes('href="#variant/rs123"')&&html.includes('AG'));
}
const decisions=contextHtml({blocks:{mechanism:[{gene:'GENE',text:'Supplied drug context.',
 variant:{state:'variant_called',called:2},source:'Supplied source'}]}});
assert.ok(decisions.includes('data-gene-card')&&decisions.includes(encodeURIComponent('GENE[PREF] AND 9606[taxid]')));
assert.ok(decisions.includes('Supplied drug context.')&&decisions.includes('decision.variant.variant_called2'));
assert.ok(decisions.includes('Supplied source')&&!decisions.includes('web.gene_card.no_personal_reading'));
const lipid=renderLipidGenetics({status:'ok',pcsk9:[{...row,status:'unread',read:true,copies:null,
 verdict:'Do not show a result from a conflicted reading.',
 reading:{genotype:'AG',depth:23,conflict:{kind:'source_disagreement'},interpretation_applicable:false}}]});
assert.ok(lipid.includes('gene-card-genotype">AG</span>'));
assert.ok(lipid.includes('genome.source_conflict'));
assert.ok(!lipid.includes('Do not show a result from a conflicted reading.'));
const lipidRead=renderLipidGenetics({status:'ok',pcsk9:[{...row,status:'read',label:'Supplied possible meaning.',
 verdict:'Supplied copy count.',action:'Supplied action.',population_note:'Population limit.'}]});
assert.equal(lipidRead.split('Supplied possible meaning.').length,2);
const lipidChain=['Supplied possible meaning.','Supplied copy count.','Supplied mechanism.','Supplied action.','Population limit.'];
assert.ok(lipidChain.every((value,i)=>lipidRead.includes(value)&&(!i||lipidRead.indexOf(lipidChain[i-1])<lipidRead.indexOf(value))));

// A conflict between sites files has no historical-report/current-call pair.
// The shared card owns its notice; a page must not print missing pair fields.
for(const conflict of [{kind:'sites_disagreement'},{kind:'recorded_disagreement'}]){
 const hit={...row,result:{genotype:'AG',confidence:'called',conflict,interpretation_applicable:false}};
 const html=genomeCard(hit);
 assert.ok(html.includes('genome.source_conflict'));
 assert.ok(!html.includes('genome.conflict'));
 assert.ok(!html.includes('undefined'));
 assert.ok(!html.includes('Supplied possible meaning.')&&!html.includes('Supplied mechanism.'));
}
''')
