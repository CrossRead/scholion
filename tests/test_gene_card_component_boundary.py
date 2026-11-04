"""The actual component owns card composition, layout and live presentation state."""
from __future__ import annotations

import json
import shutil
import unittest

import gene_card_support
import support
from scholion import i18n

WEB = support.SRC / "scholion/web"


class ComponentOwnership(unittest.TestCase):
    def test_pages_delegate_instead_of_forking_the_component(self):
        page = (WEB / "index.html").read_text(encoding="utf-8")
        bridges = {"geneDisplayCard": "render", "geneFindingCards": "findings",
                   "geneReferenceExtras": "referenceExtras", "referenceContextHtml": "reference",
                   "genePositionCards": "positions", "geneRegionRows": "regionRows",
                   "mechanismHtml": "mechanism", "geneticPreviewHtml": "preview",
                   "geneticBriefHtml": "brief"}
        for name, method in bridges.items():
            self.assertIn(f"function {name}(...args){{\n  return geneCards.{method}(...args);\n}}", page,
                          "Change card content in the component, not a page delegate")
        self.assertEqual(1, page.count("ScholionGeneCards.create("))
        self.assertNotIn("ScholionGeneCards.render(", page)
        for path in WEB.iterdir():
            if path.suffix not in (".js", ".html") or path.name == "gene-cards.js":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r'<article\s+class=[\"\x27]gene-card\b', str(path))
            self.assertNotIn('class="gene-card-grid"', text, str(path))
        inline_style = page.split("<style>", 1)[1].split("</style>", 1)[0]
        self.assertNotRegex(inline_style, r"\.gene-card(?:[\s.:{>-]|\b)")
        self.assertLess(page.index("</style>"), page.index('href="/gene-cards.css"'))
        css = (WEB / "gene-cards.css").read_text(encoding="utf-8")
        for marker in (".gene-card-grid", "@media print", "@media(max-width:760px)",
                       "@media(max-width:380px)", "--gene-card-body", "--gene-card-label"):
            self.assertIn(marker, css)
        self.assertNotRegex(css, r"https?://|@import|#[0-9a-fA-F]{3,8}\b")

    @unittest.skipUnless(shutil.which("node"), "requires the shipped browser component")
    def test_bound_component_preserves_state_slots_and_input_across_consumers(self):
        script = "const cards=require(" + json.dumps(str(WEB / "gene-cards.js")) + ");\n"
        script += "const messages=" + json.dumps({k: i18n.CATALOGUES[k] for k in ("en", "ru")}) + ";\n"
        script += r'''
const assert=require('node:assert/strict');
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let language='en',register='patient';
const calls=[];
const t=(k,a={})=>Object.entries(a).reduce((s,[key,v])=>s.replaceAll('{'+key+'}',v),messages[language][k]||k);
const services={t,escape:esc,grade:esc,formatDate:esc,register:()=>register,
 passport:(p,r)=>{calls.push(['passport',r]);return '<p>Passport</p>';},
 authorNote:(p,r)=>{calls.push(['note',r]);return '<p>Note</p>';},clinicalBasis:()=>'<p>Basis</p>'};
const component=cards.create(services);
const row={gene:'SYNTHETIC',rsid:'rs123',read:true,genotype:'AG',state:'het',level:'B',
 passport:{reported:'Already supplied'},interpretation:{summary:'Supplied interpretation',source:'PMID:123'},
 personal_context:{status:'carrier_context',label:'Supplied carriage',summary:'Supplied meaning',
  zygosity:'heterozygous',alternative_copies:1,inheritance_label:'Supplied inheritance'},
 reference_context:{gene_function:'Supplied function',variant_context:'Variant context',
  gene_source:'https://example.org/gene',variant_source:'PMID:123'}};
const freeze=x=>{if(x&&typeof x==='object'){Object.values(x).forEach(freeze);Object.freeze(x);}return x;};
freeze(row); const before=JSON.stringify(row);
for(language of ['en','ru']) for(register of ['patient','clinician']){
 calls.length=0;
 const html=component.render(row);
 assert.ok(html.includes(t('web.gene_card.confidence')));
 assert.ok(html.includes(t('finding.zygosity.heterozygous')));
 for(const text of ['Supplied carriage','Supplied function','Supplied meaning','Supplied inheritance','PMID:123','Passport','Basis'])assert.ok(html.includes(text));
 assert.deepEqual(calls,[['passport',register],['note',register]]);
 assert.ok(!/<details[^>]*\bopen(?:\s|>)/.test(html));
 const context='<p data-synthetic-context>Measured context</p>';
 const withContext=component.render(row,{contextHtml:context});
 assert.equal(withContext.replace('<section class="gene-card-context">'+context+'</section>',''),html);
 const sourced={...row,personal_meaning:{scope:'genotype_hypothesis',reading_binding:{status:'verified',genotype:'AG'},
  summary:'Hypothesis for the recorded genotype.',comparator:'Comparator from the study.',mechanism:'Mechanism from the study.',
  limitations:'Limitation from the study.'}};
 const ordered=component.render(sourced,{contextHtml:context});
 const sequence=[t('meaning.personal'),sourced.personal_meaning.summary,sourced.personal_meaning.comparator,
  sourced.personal_meaning.mechanism,'Measured context',sourced.personal_meaning.limitations,'gene-card-grid'];
 assert.ok(sequence.every((value,i)=>ordered.includes(value)&&(!i||ordered.indexOf(sequence[i-1])<ordered.indexOf(value))));
 assert.equal(ordered.split(sourced.personal_meaning.comparator).length,2);
 const custom=component.render(row,{annotationHtml:'<p>Annotation slot</p>',
  detailHtml:'<p>Explicit detail slot</p>',extraHtml:'<p>Extra slot</p>',register:register==='patient'?'clinician':'patient'});
 for(const text of ['Annotation slot','Explicit detail slot','Extra slot'])assert.ok(custom.includes(text));
 assert.ok(!custom.includes('Passport'));
 const hit={...row,gene_contexts:[{gene:'FIRST',genotype:'TT',reference_context:row.reference_context},
  {gene:'SECOND',genotype:'TT',reference_context:row.reference_context}]};
 const finding=component.findings(hit);
 assert.equal((finding.match(/data-gene-card /g)||[]).length,2);
 assert.equal((finding.match(/>AG<\/span>/g)||[]).length,2);
 assert.ok(!finding.includes('>TT<'));
 const model=cards.project(row);
 assert.equal(cards.render(row,{t,escape:esc,grade:esc}),cards.renderModel(model,{t,escape:esc,grade:esc}));
 assert.equal(JSON.stringify(row),before);
 const cautions=component.render({...row,personal_context:{...row.personal_context,limitations:t('finding.limitations')},
  interpretation:{...row.interpretation,notice:t('interpretation.notice')},
  reference_context:{...row.reference_context,scientific_review:[{scope:'variant',status:'curated',
    limitations:'Variant-specific study limit. '+t('web.gene_card.literature_caution')}]}});
 assert.ok(cautions.includes(t('web.gene_card.finding_reading_limit')));
 assert.ok(cautions.includes('Variant-specific study limit.'));
 for(const key of ['finding.limitations','interpretation.notice','web.gene_card.literature_caution'])
  assert.ok(!cautions.includes(t(key)),key);
 const missingKey=cards.create({...services,t:(key,args)=>messages[language][key]?t(key,args):'⟦'+key+'⟧'});
 const classification=missingKey.render({...row,personal_context:{status:'classification_only',summary:'Supplied classification context'}});
 assert.ok(classification.includes('Supplied classification context'));
 assert.ok(!classification.includes('⟦web.gene_card.meaning.classification_only⟧'));
}
const next={...row,rsid:'rs124',genotype:'CC',depth:21,level:'C',interpretation:{summary:'Other variant',source:'PMID:456'}};
const count=(html,token)=>html.split(token).length-1;
for(language of ['en','ru']) for(register of ['patient','clinician']){
 const options={rowOptions:p=>({extraHtml:'<b>'+p.rsid+' detail</b>'})};
 const grouped=component.positions([row,next,{...row}],options);
 assert.equal(count(grouped,'data-gene-positions="SYNTHETIC"'),1);
 assert.equal(count(grouped,'Supplied function'),1);
 assert.equal(count(grouped,'data-position="rs123"'),1);
 const search='https://www.ncbi.nlm.nih.gov/gene/?term='+encodeURIComponent('SYNTHETIC[PREF] AND 9606[taxid]');
 assert.equal(count(grouped,'href="'+search+'"'),1);
 assert.ok(grouped.indexOf(search)<grouped.indexOf('data-position="rs123"'));
 assert.ok(!grouped.includes('data-gene-open'));
 assert.ok(grouped.includes('data-rs-open="rs123"'));
 const direct={...row,gene:'CYP2C19',reference_context:{gene_source:'https://www.ncbi.nlm.nih.gov/gene/1557'}};
 const directCard=component.render(direct);
 assert.ok(directCard.includes('href="https://www.ncbi.nlm.nih.gov/gene/1557" target="_blank" rel="noopener noreferrer">CYP2C19'));
 const earlier={...next,gene:direct.gene};
 for(const rows of [[direct,earlier],[earlier,direct]]){
  const html=component.positions(rows);
  assert.equal(count(html,'href="https://www.ncbi.nlm.nih.gov/gene/1557"'),1);
 }
 const disagreement=component.positions([direct,{...earlier,reference_context:{gene_source:'https://www.ncbi.nlm.nih.gov/gene/1234'}}]);
 assert.ok(disagreement.includes(encodeURIComponent('CYP2C19[PREF] AND 9606[taxid]')));
 assert.ok(!disagreement.includes('href="https://www.ncbi.nlm.nih.gov/gene/1557"'));
 const alias={...row,gene:'BMAL1',reference_context:{canonical_symbol:'ARNTL'}};
 assert.ok(component.render(alias).includes(encodeURIComponent('ARNTL[PREF] AND 9606[taxid]')+'" target="_blank"'));
 const region={...row,gene:'HHEX-IDE',reference_context:{gene_source_scope:'genomic_annotation'}};
 assert.ok(component.render(region).includes('<div class="gene-card-name"><strong>HHEX-IDE</strong></div>'));
 for(const piece of ['>AG<','>CC<','PMID:123','PMID:456','rs123 detail','rs124 detail',t('web.gene_card.position')])
  assert.ok(grouped.includes(piece),piece);
 assert.equal(count(component.positions([row,next],{functionAbove:'Supplied function'}),'Supplied function'),0);
 assert.equal(count(component.positions([row,{...row,interpretation:next.interpretation}]),'data-position="rs123"'),2);
 const different=component.positions([row,{...next,reference_context:{gene_function:'Different function'}}]);
 assert.equal(count(different,'Supplied function'),1);
 assert.equal(count(different,'Different function'),1);
}
const call={chrom:'3',pos:123,rsid:'rs456',genotype:'1|2',personal_alleles:['A','T'],depth:0,genotype_quality:41};
const region=component.regionRows([call,{...call,alt:'T'},{...call,pos:124,genotype:'0/0',personal_alleles:['G','G'],depth:null,protein:{hgvs_p:'p.Val2Gly'}}]);
assert.equal(count(region,'<th scope="row">'),2);
for(const piece of ['3:123','A|T','0×','41','3:124','G/G','rs456','p.Val2Gly'])assert.ok(region.includes(piece),piece);
const curated={reading:{source:'vcf',genotype:'AG',raw_genotype:'0/1',depth:24,
  variant_identity:{chrom:'4',pos:123,ref:'A',assembly:'GRCh38'}}};
const same={chrom:'chr4',pos:123,ref:'A',genotype:'0/1',depth:24,personal_alleles:['A','G']};
const rest=component.regionRows([same,{...same,personal_alleles:['A','T']},
  {...same,genotype:'1/1',personal_alleles:['G','G']},{...same,pos:124}], [curated], 'GRCh38');
assert.equal(count(rest,'<th scope="row">'),3);
assert.ok(rest.includes('A/T')&&rest.includes('G/G')&&rest.includes('chr4:124'));
assert.ok(!rest.includes('chr4:123</th><td>A/G'));
assert.ok(component.regionRows([same], [curated], 'GRCh37').includes('A/G'));
// No active-profile or language data is retained between renders/instances.
const other=cards.create({...services,register:()=>'clinician'});
assert.ok(!other.render({gene:'NEXT',rsid:'rs124',read:false}).includes('>AG<'));
assert.ok(component.render({...row,gene:'<img onerror="evil">'}).includes('&lt;img'));
assert.ok(!component.render({...row,gene:'<img onerror="evil">'}).includes('<img'));
'''
        result = gene_card_support.run(script, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr[-4000:])

    @unittest.skipUnless(shutil.which("node"), "requires the shipped browser component")
    def test_resolved_observations_reach_the_card_without_reselecting_a_call(self):
        from unittest.mock import patch
        from scholion import genome, variant_readings as vr
        from scholion.engine import panel_genotype, panel_intake

        current = {'genotype':'AG', 'confidence':'called', 'depth':27, 'source':'vcf',
                   'source_identity':{'file':'synthetic.vcf'}}
        conflict = {'confidence':'conflicting_calls', 'genotype':None, 'source':'vcf',
                    'conflict':{'kind':'sites_disagreement'}, 'interpretation_applicable':False,
                    'observations':[{'genotype':'AA','depth':21,'evidence_file':'sites-a.vcf'},
                                    {'genotype':'AG','depth':24,'evidence_file':'sites-b.vcf'}]}
        cases = []
        for language in ('en', 'ru'):
            with patch.object(i18n._state, "current", language, create=True):
                readings = [vr.resolve('rs123', current),
                            vr.resolve('rs123', {**current,'depth':4,'low_depth':True,'note':'Synthetic low depth'}),
                            vr.resolve('rs123', {**current,'interpretation_applicable':False}),
                            vr.resolve('rs123', current, {'genotype':'AA','source':'pharmacogenomics.json'}),
                            vr.resolve('rs123', {'confidence':'no_row','depth':3},
                                       {'genotype':'AG','source':'longevity_findings.json'}),
                            vr.resolve('rs123', conflict)]
                for result in readings:
                    # Exercise actual system-panel and thematic-panel adapters as well
                    # as the raw resolver; the card must see the same selected reading.
                    with patch.object(genome,'lookup',return_value={'status':'ok','result':result}), \
                         patch.object(genome,'resolve_rsid',return_value={'chrom':'1','pos':1,'ref':'A','alt':'G'}), \
                         patch.object(genome,'_indel_event',return_value=False), \
                         patch.object(genome,'_gt_at',return_value=result):
                        system = panel_genotype._genotype('rs123','','SYNTHETIC','G',{'status':'ok'},at=('A','G'))
                        thematic = panel_intake._intake_reading('rs123',{'ready':True})
                    # A resolved saved report is not a new current VCF call.
                    adapters = [result, system] + ([] if result['confidence']=='reported' else [thematic])
                    for reading in adapters:
                        cases.append({'language':language,'reading':reading,
                                      'expected':{'genotype':result.get('genotype') or '',
                                                  'depth':result.get('depth'),
                                                  'conflict':bool(result.get('conflict')),
                                                  'blocked':not vr.permits_interpretation(result)}})
        script = 'const cards=require(' + json.dumps(str(WEB / 'gene-cards.js')) + ');\n'
        script += 'const messages=' + json.dumps({k:i18n.CATALOGUES[k] for k in ('en','ru')}) + ';\n'
        script += 'const cases=' + json.dumps(cases) + ';\n'
        script += r'''
const assert=require('node:assert/strict');
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
for(const {language,reading,expected} of cases){
 const t=(k,a={})=>Object.entries(a).reduce((s,[key,v])=>s.replaceAll('{'+key+'}',v),messages[language][k]||k);
 for(const register of ['patient','clinician']){
  const component=cards.create({t,escape:esc,grade:esc,formatDate:esc,register:()=>register,
   passport:()=>'',authorNote:()=>'',clinicalBasis:()=>''});
  for(const shape of ['flat','reading','result','genotype']){
   const base={gene:'SYNTHETIC',rsid:'rs123',level:'B',reference_context:{gene_function:'Synthetic function'},
    personal_context:{alternative_copies:1},read:!!expected.genotype};
   const input=shape==='flat'?{...base,...reading}:{...base,[shape]:reading};
   const before=JSON.stringify(input),model=cards.project(input),html=component.render(input);
   if(expected.genotype){
    const stale={...base,genotype:'TT',depth:999,read:false,reading,summary:'Stale personal effect'};
    const repaired=cards.project(stale);
    assert.equal(repaired.genotype,expected.genotype);
    assert.equal(repaired.depth??null,expected.depth);
    assert.equal(repaired.interpretationBlocked,true);
    assert.equal(repaired.copies,null);
    assert.ok(!component.render(stale).includes('Stale personal effect'));
    const unknown={...stale,reading:{...reading,reading_record:{...reading.reading_record,schema:2}}};
    const refused=cards.project(unknown);
    assert.equal(refused.genotype,'');
    assert.equal(refused.interpretationBlocked,true);
    assert.ok(component.render(unknown).includes('Synthetic function'));
   }
   assert.equal(model.genotype,expected.genotype,shape);
   assert.equal(model.depth??null,expected.depth,shape);
   assert.equal(model.conflict,expected.conflict);
   assert.equal(model.interpretationBlocked,expected.blocked);
   if(expected.blocked)assert.equal(model.copies,null);
   if(reading.low_depth || reading.quality?.low_depth)assert.ok(html.includes(expected.depth == null ? t('genlab.quality.low_depth') : t('web.gene_card.low_depth',{value:expected.depth})));
   assert.ok(html.includes('Synthetic function'));
   assert.ok(html.includes('data-reading-observations'));
   assert.ok(!html.includes('999'));
   if(expected.conflict)assert.ok(html.includes(t('genome.source_conflict')));
   if(reading.reading_record?.selected==='recorded')assert.equal(model.source,'longevity_findings.json');
   if(reading.reading_record?.observations[0]?.underlying_observations.length){
    assert.ok(html.includes('sites-a.vcf')&&html.includes('sites-b.vcf'));
   }
   assert.equal(JSON.stringify(input),before);
   assert.ok(!/<details[^>]*\bopen(?:\s|>)/.test(html));
  }
 }
}
'''
        result = gene_card_support.run(script, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr[-4000:])

    @unittest.skipUnless(shutil.which('node'), 'node is needed for the actual renderer')
    def test_curated_catalogues_share_the_role_and_reading_order(self):
        from scholion import core
        from scholion.panel_reference import _function_fields, genome_context
        from scholion.variant_readings import sample_quality

        self.assertEqual({'depth': 21, 'genotype_quality': 42, 'allele_depth': [9, None, 12]},
                         sample_quality({'DP': '21', 'GQ': '42', 'AD': '9,.,12'}))
        genes = sorted({
            gene for book in ('panel_reference_context.json', 'gencc_reference_context.json',
                              'gene_function_context.json')
            for gene, entry in core._read_knowledge_raw(book).get('genes', {}).items()
            if entry.get('description') and entry.get('source')
        })
        self.assertGreater(len(genes), 1400)
        previous = i18n.lang()
        self.addCleanup(i18n.set_lang, previous)
        cases = {}
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            examples = [genome_context(gene, rsid) for gene, rsid in (
                ('COMT', 'rs4680'), ('DRD2', 'rs1800497'), ('DRD2', 'rs6277'), ('DRD4', 'rs1800955'),
            )]
            self.assertTrue(all(any(isinstance(row.get('patient_summary'), str) and row['patient_summary'] for row in
                                    item['reference_context']['scientific_review']) for item in examples))
            cases[language] = {'roles': [{'gene': gene, 'reference_context': _function_fields(gene)}
                                         for gene in genes], 'examples': examples}
        script = 'const cards=require(' + json.dumps(str(WEB / 'gene-cards.js')) + ');\n'
        script += r'''
const assert=require('node:assert/strict');
const {cases,messages}=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const esc=x=>String(x??'').replaceAll('<','&lt;').replaceAll('"','&quot;');
for(const [lang,{roles,examples}] of Object.entries(cases)){
 const t=(key,args={})=>Object.entries(args).reduce((s,[k,v])=>s.replaceAll('{'+k+'}',v),messages[lang][key]||key);
 for(const register of ['patient','clinician']){
  const component=cards.create({t,escape:esc,grade:esc,formatDate:esc,register:()=>register,
   passport:()=>'',authorNote:()=>'',clinicalBasis:()=>''});
  for(const role of roles){
   const model=cards.project(role);
   const html=component.render(role);
   assert.ok(model.functionText, role.gene);
   assert.ok(html.indexOf(esc(model.functionText)) < html.indexOf('gene-card-reading'), role.gene);
   if(['ACTA2','ACTC1','ALDH4A1','AMT'].includes(role.gene)){
    const detail=esc(role.reference_context.gene_role_detail);
    assert.ok(detail.length>80, role.gene);
    assert.ok(html.indexOf(detail)>html.indexOf('data-gene-inheritance'), role.gene);
   }
  }
  for(const item of examples){
   const row={...item,result:{genotype:'CC',confidence:'called',depth:123}};
   const model=cards.project(row), html=component.render(row);
   assert.ok(html.indexOf('gene-card-function') < html.indexOf('gene-card-description'));
   assert.ok(html.indexOf('gene-card-description') < html.indexOf('gene-card-reading'));
   const curated=row.reference_context.scientific_review.find(entry=>entry.patient_summary);
   assert.equal(model.summary,curated.patient_summary);
   assert.ok(html.includes(esc(curated.patient_summary)));
   assert.equal(html.split('123×').length,2);
   assert.ok(html.indexOf('gene-card-reading') < html.indexOf('123×'));
   assert.ok(html.indexOf('123×') < html.indexOf('data-gene-inheritance'));
   if(row.rsid==='rs1800497')assert.ok(html.includes('ANKK1'));
   if(row.rsid==='rs1800955'){
    const note=t('web.gene_card.separate_repeat');
    assert.equal(html.split(note).length,2);
    assert.ok(html.indexOf(note)>html.indexOf('gene-card-reading'));
   }
  }
 }
}
'''
        result = gene_card_support.run(script, input=json.dumps({
            'cases': cases, 'messages': {k: i18n.CATALOGUES[k] for k in ('en', 'ru')},
        }), capture_output=True, text=True, timeout=60)
        self.assertEqual(0, result.returncode, result.stderr[-4000:])
