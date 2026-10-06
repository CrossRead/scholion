"""Execute the page's renderers: C–E are counts, not patient-facing rows."""
from __future__ import annotations

import shutil
import subprocess
import unittest

import support


@unittest.skipUnless(shutil.which("node"), "needs node for the page's JavaScript")
class TestPatientPresentation(unittest.TestCase):
    def test_all_three_renderers_hide_rows_without_mutating_the_reply(self):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        functions = []
        for name in ("shownGenetics", "hypothesisCountHtml", "referenceContextHtml", "mechanismHtml", "genTableRow", "genTableHtml",
                     "panelHtml", "genSummaryHtml", "markerGeneticsRow", "basketRowHtml"):
            start = page.index("function " + name + "(")
            functions.append(page[start:page.index("\n}\n", start) + 2])
        script = r"""
const assert=require('node:assert/strict');
const esc=x=>String(x??''),t=(k,a)=>k+JSON.stringify(a||{}),plural=n=>String(n);
const levelChip=x=>x,pnlStateBadge=()=>'',badge=()=>'',geneStateBadge=()=>'';
const authorNoteHtml=()=>'',passportHtml=p=>p.passport?.reported||'',levelNoteHtml=()=>'';
const routeHtml=()=>'',underLoadHtml=()=>'',ladderHtml=()=>'',geneRowDetail=()=>'';
const systemPolygenicHtml=()=>'',pnlExpect=()=>'',PNL_KIND={},PNL_KIND_BADGE={};
const systemLinkHtml=()=>'';
const positions=['A','C','D','E'].map(level=>({gene:'GENE_'+level,rsid:'rs_'+level,
  level,unit:'position',state:'het',read:true,text:'TEXT_'+level,
  mechanism:'MECHANISM_'+level,source:'SOURCE_'+level,
  passport:['C','D'].includes(level)?{reported:'HYPOTHESIS_'+level}:null,value_only:level==='E'}));
const gen={status:'composed',positions,rows:positions,groups:[]};
const before=JSON.stringify(gen);
""" + "\n".join(functions) + r"""
for(const render of [genTableHtml,panelHtml,genSummaryHtml]){
  const patient=render(gen,{register:'patient'},'patient');
  assert.ok(patient.includes('GENE_A'));
  assert.ok(patient.includes('MECHANISM_A'));assert.ok(patient.includes('SOURCE_A'));
  for(const level of ['C','D','E']){
    assert.ok(!patient.includes('GENE_'+level),patient);
    assert.ok(!patient.includes('rs_'+level),patient);
    assert.ok(!patient.includes('TEXT_'+level),patient);
    assert.ok(!patient.includes('MECHANISM_'+level),patient);
  }
  const clinician=render(gen,{register:'clinician'},'clinician');
  for(const level of ['A','C','D','E'])assert.ok(clinician.includes('GENE_'+level));
}
const summary=genSummaryHtml(gen,{register:'patient'});
assert.ok(summary.includes('"hyp":2'));assert.ok(summary.includes('"values":1'));
const onlyLower={...gen,positions:positions.slice(1),rows:positions.slice(1)};
assert.ok(genSummaryHtml(onlyLower,{register:'patient'}).includes('data-hypothesis-count'));
assert.equal(JSON.stringify(gen),before);
assert.equal(shownGenetics(gen,'clinician'),gen);
const referenceGen={...gen,positions:positions.map(p=>({...p,text:null,mechanism:null,
  reference_context:{level:p.level,gene_function:'FUNCTION_'+p.level,
  variant_context:'REFERENCE_'+p.level,gene_source:'GENE_SOURCE_'+p.level,
  variant_source:p.level==='E'?null:'VARIANT_SOURCE_'+p.level}}))};
referenceGen.rows=referenceGen.positions;
const referenceBefore=JSON.stringify(referenceGen);
for(const render of [genTableHtml,panelHtml,genSummaryHtml]){
  const html=render(referenceGen,{register:'patient'},'patient');
  for(const level of ['A','C','D','E']){
    assert.ok(html.includes('GENE_'+level),html);
    assert.ok(html.includes('FUNCTION_'+level),html);
    assert.ok(html.includes('REFERENCE_'+level),html);
    assert.ok(!html.includes('TEXT_'+level),html);
  }
}
assert.equal(JSON.stringify(referenceGen),referenceBefore);

const grouped={...gen,groups:[{level:'C',members:positions},{level:'A',members:positions}]};
const displayed=shownGenetics(grouped,'patient');
assert.equal(displayed.groups.length,1);assert.equal(displayed.groups[0].members.length,1);
assert.equal(grouped.groups[1].members.length,4);
const held={...positions[0],text:null,mechanism:null,source:null,
  conclusion_basis:{status:'incomplete',reason:'MISSING_BASIS'},direction:null};
const heldGen={status:'composed',positions:[held],rows:[held],groups:[]};
for(const render of [genTableHtml,panelHtml,genSummaryHtml]){
  for(const register of ['patient','clinician']){
    const html=render(heldGen,{register},register);
    assert.ok(html.includes('MISSING_BASIS'),html);
    assert.ok(!html.includes('TEXT_A'),html);
    assert.ok(!html.includes('system.panel.none_found'),html);
    if(render===genSummaryHtml){assert.ok(html.includes('"found":1'));assert.ok(html.includes('"read":1'));}
  }
}
assert.ok(markerGeneticsRow({positions:[held]}).includes('MISSING_BASIS'));
const heldGroup={key:'g',label:'Group',level:'A',count:1,positions:['rs_A'],members:[held],
  conclusion_basis:held.conclusion_basis};
const html=genTableHtml({...heldGen,groups:[heldGroup]},{register:'clinician'},'clinician');
assert.ok(html.includes('MISSING_BASIS'));assert.ok(html.includes('data-conclusion-withheld'));
const sub={...positions[0],subclaim_basis:{expect:{status:'incomplete',reason:'MISSING_EXPECTATION'}}};
const subGen={positions:[sub],rows:[sub],groups:[]};
for(const render of [genTableHtml,panelHtml,genSummaryHtml]){
  for(const register of ['patient','clinician']){
    assert.ok(render(subGen,{register},register).includes('MISSING_EXPECTATION'));
  }
}
assert.ok(markerGeneticsRow({positions:[sub]}).includes('MISSING_EXPECTATION'));
const supportedSub={...sub,subclaim_basis:{expect:{status:'complete',mechanism:'OWN_MECHANISM',source:'OWN_SOURCE'}}};
assert.ok(mechanismHtml(supportedSub).includes('OWN_MECHANISM — OWN_SOURCE'));
assert.ok(mechanismHtml({...sub,mechanism:null,source:null}).includes('MISSING_EXPECTATION'));
const next={origin:'author',text:'NEXT_STEP',mechanism:'OWN_STEP_MECHANISM',source:'OWN_STEP_SOURCE',
  conclusion_basis:{status:'complete'}};
const nextBefore=JSON.stringify(next),stepHtml=basketRowHtml(next);
assert.ok(stepHtml.includes('NEXT_STEP'));assert.ok(stepHtml.includes('OWN_STEP_MECHANISM'));
assert.ok(stepHtml.includes('OWN_STEP_SOURCE'));assert.equal(JSON.stringify(next),nextBefore);
"""
        result = subprocess.run([shutil.which("node"), "-e", script], text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
