"""Interpretation confidence qualifies display without promoting clinical findings."""
from __future__ import annotations

import shutil
import subprocess
import unittest

import support
from scholion import i18n
from scholion.conclusion_basis import guard_position
from scholion.panel_reference import interpretation_context, interpretation_lines
from scholion.engine.panel_catalogue import _position
from scholion.engine.system_panels import _position_state, _project


class TestInterpretationConfidence(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_incomplete_support_retains_interpretation_without_promoting_finding(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for level in "ABCDE":
                spec = {"gene": "SYNTHETIC", "rsid": "rsSynthetic", "level": level,
                        "evidence": {"level": level, "basis": "none" if level == "E" else "candidate"},
                        "text": {"het": {"en": "Recorded interpretation.", "ru": "Recorded interpretation."}},
                        "mechanism": None, "source": None}
                context = interpretation_context(spec, level, spec["text"]["het"][language])
                row = guard_position(spec, {"gene": "SYNTHETIC", "rsid": "rsSynthetic", "level": level,
                                           "read": True, "state": "het", "findings": 0, "interpretation": context})
                self.assertEqual(row["interpretation"], context)
                self.assertEqual(row["findings"], 0)
                self.assertEqual(context["missing"], ["source_identifier", "mechanism"])
                self.assertIn(context["summary"], "\n".join(interpretation_lines(row)))
                self.assertEqual(_position_state(row)["interpretation"], context)
                projected = _project({"rows": [{**row, "pending": True}]}, "patient")
                self.assertEqual(projected["rows"][0]["interpretation"], context)
                reference = _position(spec)
                self.assertEqual(reference["interpretation"]["summary"]["het"], context["summary"])
                self.assertEqual(reference["interpretation"]["level"], level)

    def test_retired_display_suffix_is_removed_but_biological_caveat_is_retained(self):
        spec = {"source": "PMID:123", "mechanism": "A recorded mechanism."}
        for suffix in ("; no verdict.", "; no conclusion.", "; no conclusion follows.", "; "+"\u0432\u044b\u0432\u043e\u0434\u0430 \u043d\u0435\u0442."):
            context = interpretation_context(spec, "C", "An uncertain association" + suffix)
            self.assertEqual(context["summary"], "An uncertain association.")
        caveat = "An uncertain association; no conclusion about dopamine and no prescription on genotype alone."
        self.assertEqual(interpretation_context(spec, "D", caveat)["summary"], caveat)

    @unittest.skipUnless(shutil.which("node"), "requires node for actual JavaScript renderers")
    def test_called_held_variants_stay_in_the_table_in_both_registers(self):
        page = (support.SRC / "scholion/web/index.html").read_text(encoding="utf-8")
        functions = []
        for name in ("systemGeneLink", "shownGenetics", "hypothesisCountHtml", "clinicalBasisHTML", "referenceContextHtml",
                     "mechanismHtml", "passportHtml", "geneticPreviewHtml", "geneticBriefHtml", "genSummaryHtml"):
            start = page.index("function " + name + "(")
            functions.append(page[start:page.index("\n}\n", start)+2])
        script = r"""
const assert=require('node:assert/strict');
const esc=x=>String(x??''),t=(k,a)=>k+JSON.stringify(a||{}),plural=n=>String(n);
const levelChip=x=>`<a data-level="${x}">${x}</a>`,pnlStateBadge=p=>p.state;
const authorNoteHtml=()=>'',pnlExpect=()=>'';
""" + "\n".join(functions) + r"""
for(const register of ['patient','clinician']){
 const positions=['A','B','C','D','E'].map(level=>({gene:'GENE_'+level,rsid:'rs_'+level,
  level,read:true,state:'het',passport:['C','D'].includes(level)?{level,reported:'INTERPRETATION_'+level}:null,conclusion_basis:{status:'incomplete',reason:'GAP_'+level},
  interpretation:{level,summary:'INTERPRETATION_'+level,missing:['mechanism'],notice:'QUALIFIED'},
  reference_context:{level,gene_function:'FUNCTION_'+level,variant_context:'CONTEXT_'+level,
   gene_source:'SOURCE_'+level}}));
 positions.push({...positions[0],gene:'ABSENT',state:'absent'});
 positions.push({...positions[0],gene:'UNREAD',read:false,state:null});
 const gen={positions,rows:positions},before=JSON.stringify(gen);
 const html=genSummaryHtml(gen,{key:'synthetic',register});
 const table=html.slice(html.indexOf('<tbody>'),html.indexOf('</tbody>'));
 assert.equal((table.match(/<tr>/g)||[]).length,5);
 assert.ok(!table.includes('ABSENT'));assert.ok(!table.includes('UNREAD'));
 for(const level of ['A','B','C','D','E']){
  assert.ok(table.includes('INTERPRETATION_'+level));assert.ok(table.includes('FUNCTION_'+level));
  assert.ok(table.includes('data-panel-gene="GENE_'+level+'"'));assert.ok(table.includes('data-level="'+level+'"'));
  const disclosure=table.match(new RegExp('<details class="gen-context"[^>]*>','g'));
  assert.equal(disclosure.length,5);assert.ok(!disclosure.some(x=>x.includes(' open')));
  assert.ok(!table.includes('system.hyp.no_sentence'));
  assert.ok(table.includes('GAP_'+level));assert.ok(table.includes('SOURCE_'+level));
 }
 assert.ok(html.includes('"found":5'));assert.ok(html.includes('"read":6'));
 assert.ok(!html.includes('system.panel.compare_none'));assert.ok(!html.includes('system.panel.compare_h'));
 assert.equal(JSON.stringify(gen),before);
}
"""
        result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("node"), "requires node for actual JavaScript renderers")
    def test_every_catalogue_disclosure_retains_its_own_explanation_and_sources(self):
        import json
        from scholion import core
        from scholion.panel_reference import gene_reference_context
        from scholion.engine.panel_catalogue import panel_description
        page = (support.SRC / "scholion/web/index.html").read_text(encoding="utf-8")
        names = ("systemGeneLink", "shownGenetics", "clinicalBasisHTML", "referenceContextHtml", "mechanismHtml",
                 "geneticPreviewHtml", "passportHtml", "authorNoteHtml", "geneticBriefHtml",
                 "genTableRow", "genTableHtml", "geneRowDetail", "geneStateBadge", "pnlStateBadge")
        functions = []
        for name in names:
            start = page.index("function " + name + "(")
            functions.append(page[start:page.index("\n}\n", start)+2])
        cases = []
        genes = set()
        positions = set()
        for language in ("en", "ru"):
            i18n.set_lang(language)
            keys = [s["key"] for s in panel_description()["systems"]]
            keys += list(core._read_knowledge("on_demand_panels.json")["panels"])
            for key in keys:
                for original in panel_description(key)["positions"]:
                    genes.add(original["gene"])
                    positions.add((original["gene"], original["rsid"]))
                    sentences = original["interpretation"]["summary"]
                    for state in ("het", "hom", "hemi", "absent", "unread"):
                        sentence = sentences.get(state) if state in ("het", "hom", "hemi") else None
                        row = {**original, "unit": "position", "read": state != "unread",
                               "state": state, "interpretation": {**original["interpretation"], "summary": sentence}}
                        if original["level"] in ("C", "D"):
                            row["passport"] = {"level": original["level"], "reported": sentence}
                        cases.append({"kind": "position", "key": key, "language": language, "row": row})
            base = core._read_knowledge("gencc_gene_disease.json")
            for key, panel in base["systems"].items():
                for gene, entry in panel["genes"].items():
                    assertions = entry["submissions"]
                    context = gene_reference_context(gene, assertions)
                    row = {"unit": "gene", "gene": gene, "read": False,
                           "reference_context": context, "classifications": sorted({a["classification"] for a in assertions}),
                           "assertions": assertions}
                    cases.append({"kind": "gene", "key": key, "language": language, "row": row})
        self.assertGreater(len(positions), 200)
        self.assertGreater(len(genes), 100)
        script = r"""
const assert=require('node:assert/strict');
const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const t=(k,a)=>k+' '+Object.values(a||{}).join(' '),plural=n=>String(n),fmtDate=x=>x;
const levelChip=x=>`<a data-level="${x}">${x}</a>`,badge=(c,text)=>text||'';
const PNL_KIND={},PNL_KIND_BADGE={};
const levelNoteHtml=()=>'',routeHtml=()=>'',underLoadHtml=()=>'',ladderHtml=()=>'';
""" + "\n".join(functions) + r"""
const cases=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
for(const c of cases)for(const register of ['patient','clinician']){
 const p=c.row,before=JSON.stringify(p);
 const gen={positions:c.kind==='position'?[p]:[],rows:[p]},card={key:c.key,register};
 const html=genTableHtml(gen,card,register),id=(c.kind==='position'?'p:'+p.gene+':'+p.rsid:'g:'+p.gene);
 assert.ok(html.includes('data-gendet="'+esc(id)+'" hidden'),id);
 assert.ok(html.includes('data-panel-gene="'+esc(p.gene)+'"'),id);
 const detail=html.slice(html.indexOf('data-gendet='));
 const context=p.reference_context;
 for(const field of ['gene_function','variant_context','gene_source','variant_source','limitations'])
  if(context[field])assert.ok(detail.includes(esc(context[field])),id+' '+field);
 if(c.kind==='position'){
  if(p.level)assert.ok(html.includes('data-level="'+p.level+'"'),id);
  const sentence=p.interpretation.summary;
  if(sentence){
   assert.ok(detail.includes(esc(sentence)),id+' missing interpretation');
   assert.ok(detail.includes(esc(p.interpretation.notice)),id+' missing qualification');
   if(p.interpretation.mechanism)assert.ok(detail.includes(esc(p.interpretation.mechanism)),id+' missing mechanism');
   assert.ok(!detail.includes('system.hyp.no_sentence'),id+' contradictory missing sentence');
  }
  if(p.interpretation.source&&sentence)assert.ok(detail.includes(esc(p.interpretation.source)),id+' missing source');
  const brief=geneticBriefHtml(p,register);
  assert.ok(brief.startsWith('<details class="gen-context" data-genetic-context>'),id);
  assert.ok(!brief.includes('data-genetic-context open'),id);
 }else{
  assert.ok(html.includes('GenCC:'),id);
  for(const a of context.gencc_assertions){
   for(const field of ['disease_label','classification_label','moi_label','submitter','curated_on'])
    if(a[field])assert.ok(detail.includes(esc(a[field])),id+' '+field);
  }
  assert.ok(!html.includes('data-level='),id+' invented Scholion variant grade');
 }
 assert.equal(JSON.stringify(p),before,id+' mutated input');
}
"""
        result = subprocess.run([shutil.which("node"), "-e", script], input=json.dumps(cases),
                                capture_output=True, text=True, stdin=None, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr[-2500:])

    def test_product_copy_qualifies_interpretations_without_development_notes(self):
        import re
        from scholion import core
        from scholion.engine.panel_catalogue import panel_description
        prohibited = re.compile(r"\btask \d|\u0437\u0430\u0434\u0430\u0447[\u0430\u0438] \d|canon, rule|\u043a\u0430\u043d\u043e\u043d, \u043f\u0440\u0430\u0432\u0438\u043b\u043e|we (?:tried|decided)|\u043c\u044b (?:\u0440\u0435\u0448\u0438\u043b\u0438|\u043f\u0440\u043e\u0431\u043e\u0432\u0430\u043b\u0438)", re.I)
        for language in ("en", "ru"):
            i18n.set_lang(language)
            for key, sentence in i18n.CATALOGUES[language].items():
                if key.startswith("tool."):
                    continue
                self.assertFalse(prohibited.search(sentence), (language, key))
            boundary = i18n.t("evidence.boundary", levels="A, B")
            self.assertIn("A–E", boundary)
            self.assertNotIn("only at levels", boundary)
            self.assertNotIn("\u0412\u044b\u0432\u043e\u0434 \u043f\u0435\u0447\u0430\u0442\u0430\u0435\u0442\u0441\u044f \u0442\u043e\u043b\u044c\u043a\u043e", boundary)
            keys = [s["key"] for s in panel_description()["systems"]]
            keys += list(core._read_knowledge("on_demand_panels.json")["panels"])
            for key in keys:
                for p in panel_description(key)["positions"]:
                    for field in ("source", "reason"):
                        self.assertFalse(prohibited.search(str(p.get(field) or "")), (key, p["gene"], field))

    @unittest.skipUnless(shutil.which("node"), "requires node for the click handler")
    def test_catalogue_rows_open_inside_a_fold_without_intercepting_native_controls(self):
        page = (support.SRC / "scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("document.addEventListener('click',e=>{", page.index("// A row of the genetic table"))
        code = page[start:page.index("\nfunction renderChrome", start)]
        script = r"""
const assert=require('node:assert/strict');
let click;const document={addEventListener:(name,handler)=>{click=handler;}},CSS={escape:x=>x};
""" + code + r"""
for(const kind of ['plain','fold','native','link']){
 const detail={hidden:true},row={getAttribute:()=> 'p:SYNTHETIC:rs1',parentNode:{querySelector:()=>detail},classList:{toggle:()=>{}}};
 const ancestors={a:kind==='link'?{}:null,button:null,'.lvl':null,details:['fold','native'].includes(kind)?{}:null,'tr.genrow details':kind==='native'?{}:null,'tr.genrow':row};
 const event={target:{closest:selector=>selector.split(',').map(x=>ancestors[x]).find(Boolean)||null}};
 click(event);assert.equal(detail.hidden,kind==='native'||kind==='link',kind);
 if(!detail.hidden){click(event);assert.equal(detail.hidden,true,kind+' close');}
}
"""
        result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
