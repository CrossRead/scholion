"""The shared system presentation owns composition and preserves supplied facts."""
import json
import shutil
import unittest
from pathlib import Path

import gene_card_support
import support
from scholion import i18n

WEB = support.SRC / 'scholion/web'


class SystemPresentation(unittest.TestCase):
    def test_shared_boundary_and_style_ownership(self):
        page = (WEB / 'index.html').read_text(encoding='utf-8')
        self.assertEqual(1, page.count('ScholionSystemViews.create('))
        for name in ('systemCardHtml', 'attentionItemHTML', 'visitInsightHTML',
                     'visitReportSystem', 'medItem', 'controlsHtml', 'treatmentHtml'):
            self.assertIn(f'function {name}(...args){{\n  return systemViews.{name}(...args);\n}}', page)
        self.assertIn('href="/system-views.css"', page)
        self.assertIn('src="/system-views.js"', page)
        css = (WEB / 'system-views.css').read_text(encoding='utf-8')
        for selector in ('.attention-item{', '.insight-chart{', '.system-medications-table{'):
            self.assertIn(selector, css)
            self.assertNotIn(selector, page)
        self.assertNotRegex(css, r'https?://|@import|#[0-9a-fA-F]{3,8}\b')

    @unittest.skipUnless(shutil.which('node'), 'Node required for presentation behavior')
    def test_supplied_states_are_escaped_immutable_and_selection_is_live(self):
        fixtures = Path(__file__).parent / 'browser'
        script = 'const assert=require("node:assert/strict");\n'
        script += 'const ScholionSystemViews=require(' + json.dumps(str(WEB / 'system-views.js')) + ');\n'
        script += 'const ScholionSystemCases=require(' + json.dumps(str(fixtures / 'gallery-system-cases.js')) + ');\n'
        script += 'const messages=' + json.dumps({k: i18n.CATALOGUES[k] for k in ('en', 'ru')}) + ';\n'
        script += r'''
let language='en',selected=false;
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const t=(k,a={})=>Object.entries(a).reduce((s,[key,v])=>s.replaceAll('{'+key+'}',v),messages[language][k]||k);
'''
        script += (fixtures / 'gallery-systems.js').read_text(encoding='utf-8')
        script += r'''
const freeze=o=>{if(o&&typeof o==='object'){Object.values(o).forEach(freeze);Object.freeze(o);}return o;};
freeze(ScholionSystemCases);const before=JSON.stringify(ScholionSystemCases);
const component=ScholionSystemViews.create({...systemGalleryServices(),selected:()=>selected});
for(language of ['en','ru'])for(selected of [false,true]){
 const partial=component.comparisonHTML({before_dates:['2026-04-01','2026-05-01'],before_range:[4,6],delta:2});
 assert.ok(partial.includes(esc(t('insight.delta')+': 2')));
 assert.ok(!partial.includes('2026-04-01'));
 for(const c of ScholionSystemCases.cases){
  const html=component[c.method](...c.args);
  assert.equal(typeof html,'string',c.id);assert.ok(!html.includes('<script>unsafe'),c.id);
  if(c.id==='medicine-stopped'){assert.ok(html.includes('b-unknown'));assert.ok(!html.includes('href="#system/'));}
  if(c.id==='attention'){
   assert.equal(html.includes(' checked>'),selected);
   assert.ok(html.startsWith('<details'));assert.ok(html.includes('data-visit-item="system:lipids"'));
   assert.ok(html.includes('5.5'));assert.ok(html.includes('4.4'));assert.ok(html.includes('mmol/L'));
  }
  if(c.id==='system'){
   for(const on_demand of [false,true]){
    const summary=component.systemCardHtml({...c.args[0],on_demand,
      verdict_line:'Panel summary <one>',unread_line:'Coverage summary'});
    const lastLayer=on_demand?t('system.layer.on_demand_genetics'):t('web.system.next_h');
    assert.ok(summary.indexOf(lastLayer)<summary.indexOf('data-system-genetic-summary'));
    assert.equal(summary.split('Panel summary &lt;one&gt;').length,2);
    assert.equal(summary.split('Coverage summary').length,2);
   }
   assert.ok(!html.includes('data-system-genetic-summary'));
  }
 }
}
assert.equal(JSON.stringify(ScholionSystemCases),before);
assert.equal(component.controlsHtml([]),'');assert.equal(component.treatmentHtml(null),'');
'''
        result = gene_card_support.run(script, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)
