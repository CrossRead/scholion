"""Public component contracts on the same synthetic states as the browser gallery."""
from __future__ import annotations
import json
import shutil
import unittest
from pathlib import Path

import support
import gene_card_support
from scholion import i18n


class ComponentGallery(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required; browser acceptance separately requires it')
    def test_gallery_states_are_immutable_and_reading_states_stay_distinct(self):
        script = 'const assert=require("node:assert/strict");\n'
        script += 'const cards=require(' + json.dumps(str(support.SRC / 'scholion/web/gene-cards.js')) + ');\n'
        script += 'const {cases}=require(' + json.dumps(str(Path(__file__).parent / 'browser/gallery-cases.js')) + ');\n'
        script += 'const messages=' + json.dumps({k: i18n.CATALOGUES[k] for k in ('en', 'ru')}) + ';\n'
        script += r'''
const freeze=o=>{if(o&&typeof o==='object'){Object.values(o).forEach(freeze);Object.freeze(o);}return o;};
freeze(cases);const before=JSON.stringify(cases);
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
for(const language of ['en','ru'])for(const register of ['patient','clinician']){
 const t=(k,a={})=>Object.entries(a).reduce((s,[key,v])=>s.replaceAll('{'+key+'}',v),messages[language][k]||k);
 const component=cards.create({t,escape:esc,grade:esc,formatDate:esc,register:()=>register,passport:()=>'',authorNote:()=>'',clinicalBasis:()=>''});
 for(const item of cases){
  const model=cards.project(item.row,item.options),html=component.render(item.row,item.options);
  assert.ok(html.includes('data-gene-card'),item.id);
  assert.ok(!html.includes('<script>unsafe'),item.id);
  if(['unread','assumed','gene-only','screen','region'].includes(item.id))assert.equal(model.genotype,'');
  if(item.id==='reference')assert.equal(model.copies,0);
  if(item.id==='compound')assert.equal(model.zygosity,'');
  if(item.id==='carrier'){assert.equal(model.status,'carrier_context');assert.ok(html.includes('Supplied personal meaning.'));}
  assert.ok(!/<details[^>]*\bopen(?:\s|>)/.test(html));
 }
}
assert.equal(JSON.stringify(cases),before);
'''
        result = gene_card_support.run(script, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_measurement_pages_delegate_to_the_shared_module(self):
        web = support.SRC / 'scholion/web'
        page = (web / 'index.html').read_text(encoding='utf-8')
        self.assertEqual(1, page.count('ScholionMeasurements.create('))
        self.assertIn('src="/measurements.js"', page)
        for view in ('lab', 'metric', 'lifestyle'):
            self.assertIn("measurements.render(m,'" + view + "')", page)
        self.assertIn('measurements.current(c)', page)
        self.assertIn('r.components.map(measurements.annual)', page)
        self.assertNotIn('const annualSeries=', page)
        # Chart coordinates and source grouping have one implementation owner.
        self.assertNotIn('const stamps=series.map', page)
        self.assertNotIn('series.map(p=>measurementLabel(p))', page)
