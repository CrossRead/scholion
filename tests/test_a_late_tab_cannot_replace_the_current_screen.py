"""Run the page's actual mount/cache functions with deliberately reordered replies."""
from __future__ import annotations

import shutil
import subprocess
import unittest

import support

# These check correctness, not process-startup latency on hosted Windows runners.
NODE_TIMEOUT = 60


@unittest.skipUnless(shutil.which("node"), "needs node for the page's JavaScript")
class TestLateResponses(unittest.TestCase):
    def test_printing_opens_provenance_and_restores_the_readers_expansions(self):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("let intakePrintOpened=[];")
        functions = page[start:page.index("async function viewSystem", start)]
        script = r"""
const assert=require('node:assert/strict');
const handlers={},window={addEventListener:(name,fn)=>handlers[name]=fn};
const rows=[{open:true},{open:false},{open:false}];
const document={querySelectorAll:selector=>{
  assert.equal(selector,'#view [data-intake-detail]:not([open]), #view [data-clinical-checks]:not([open])');
  return rows.filter(r=>!r.open);
}};
""" + functions + r"""
for(let i=0;i<2;i++){
  handlers.beforeprint();assert.deepEqual(rows.map(r=>r.open),[true,true,true]);
  handlers.afterprint();assert.deepEqual(rows.map(r=>r.open),[true,false,false]);
}
"""
        result = subprocess.run([shutil.which("node"), "-e", script], text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=NODE_TIMEOUT)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_late_system_cannot_reopen_a_reference_or_patient_list(self):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("async function viewSystem(key, register){")
        function = page[start:page.index("\n}\n", start) + 2]
        script = r"""
const assert=require('node:assert/strict');
let visible,resolveRead,opened=0,DISPLAY_MODE='patient';
const setDisplayMode=mode=>{DISPLAY_MODE=mode;};
function node(){return {innerHTML:'',isConnected:true,cloneNode:()=>node(),
  replaceWith(next){this.isConnected=false;visible=next;}};}
const $=()=>visible,showLoader=()=>{},api=()=>new Promise(resolve=>{resolveRead=resolve;});
const viewPanel=()=>{opened++;visible.innerHTML='OLD LIST';};
""" + function + r"""
(async()=>{
  for(const kind of ['reference_only','patient_readings']){
    visible=node();
    const old=visible,pending=viewSystem('author_list','clinician');
    assert.notEqual(old,visible,'a subview must own a fresh node');
    visible.replaceWith(node());visible.innerHTML='NEW SCREEN';
    resolveRead({status:'ok',[kind]:true});await pending;
    assert.equal(opened,0);assert.equal(visible.innerHTML,'NEW SCREEN');
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        result = subprocess.run([shutil.which("node"), "-e", script], text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=NODE_TIMEOUT)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_panel_subviews_also_own_their_nodes(self):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("async function viewPanel(key,reading=null){")
        function = page[start:page.index("\n}\n", start) + 2]
        script = r"""
const assert=require('node:assert/strict');
let visible;const replies=[];
function node(){return {innerHTML:'',isConnected:true,cloneNode:()=>node(),
  replaceWith(next){this.isConnected=false;visible=next;}};}
const $=()=>visible,showLoader=()=>{},api=()=>new Promise(resolve=>replies.push(resolve));
const t=(key,args)=>args.key,errorHtml=x=>x;
""" + function + r"""
(async()=>{
  visible=node();const a=viewPanel('FIRST'),first=visible;
  const b=viewPanel('SECOND');assert.notEqual(first,visible);
  replies[1]({status:'unknown_system',systems:[]});await b;
  replies[0]({status:'unknown_system',systems:[]});await a;
  assert.equal(visible.innerHTML,'SECOND');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        result = subprocess.run([shutil.which("node"), "-e", script], text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, timeout=NODE_TIMEOUT)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_old_success_and_error_cannot_replace_a_new_render(self):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("function mount(i){")
        function = page[start:page.index("\n}\n", start) + 2]
        mark_start = page.index("function markCurrentTab(i){")
        function = page[mark_start:page.index("\n}\n", mark_start) + 2] + '\n' + function
        script = r"""
const assert=require('node:assert/strict');
let current=0, visible;
function node(){return {innerHTML:'',isConnected:true,cloneNode:()=>node(),
  replaceWith(next){this.isConnected=false;visible=next;}};}
const $=()=>visible,document={querySelectorAll:()=>[]};
const showLoader=()=>{},errorHtml=x=>x,t=x=>x;
let first,second,fail=false;
const TABS=[['a',v=>new Promise((resolve,reject)=>{first=()=>{
  if(fail)reject(Error('old failure'));else {v.innerHTML='A';resolve();}
};})],['b',v=>new Promise(resolve=>{second=()=>{v.innerHTML='B';resolve();};})]];
""" + function + r"""
(async()=>{
  for(fail of [false,true]){
    visible=node();
    const a=mount(0), b=mount(1);
    await Promise.resolve();second();await b;first();await a;
    assert.equal(current,1);assert.equal(visible.innerHTML,'B');
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        result = subprocess.run([shutil.which("node"), "-e", script], text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_old_read_cannot_refill_cache_after_a_write(self):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("const _apiCache=new Map();")
        functions = page[start:page.index("let _loaderTimer", start)]
        script = r"""
const assert=require('node:assert/strict');
const API='',withLang=x=>x,t=x=>x,_net={started:0,done:0};
let resolveRead;
const fetch=()=>new Promise(resolve=>{resolveRead=resolve;});
""" + functions + r"""
(async()=>{
  const pending=api('/api/labs');forgetAnswers();
  resolveRead({ok:true,json:async()=>({value:'old'})});await pending;
  assert.equal(_apiCache.size,0);
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        result = subprocess.run([shutil.which("node"), "-e", script], text=True, capture_output=True, stdin=subprocess.DEVNULL)
        self.assertEqual(0, result.returncode, result.stderr)
