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
 const custom=component.render(row,{geneHtml:'<b data-custom-link>Gene</b>',annotationHtml:'<p>Annotation slot</p>',
  detailHtml:'<p>Explicit detail slot</p>',extraHtml:'<p>Extra slot</p>',register:register==='patient'?'clinician':'patient'});
 for(const text of ['data-custom-link','Annotation slot','Explicit detail slot','Extra slot'])assert.ok(custom.includes(text));
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
}
// No active-profile or language data is retained between renders/instances.
const other=cards.create({...services,register:()=>'clinician'});
assert.ok(!other.render({gene:'NEXT',rsid:'rs124',read:false}).includes('>AG<'));
assert.ok(component.render({...row,gene:'<img onerror="evil">'}).includes('&lt;img'));
assert.ok(!component.render({...row,gene:'<img onerror="evil">'}).includes('<img'));
'''
        result = gene_card_support.run(script, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr[-4000:])
