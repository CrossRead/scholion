"""Screen resources and context are owned once, independently of render markup."""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest

import support


@unittest.skipUnless(shutil.which('node'), 'Node required for the shipped lifecycle component')
class ViewLifecycle(unittest.TestCase):
    def run_js(self, script):
        result = subprocess.run([shutil.which('node'), '-e', script], capture_output=True,
                                text=True, stdin=subprocess.DEVNULL, timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_context_cleanup_timer_cancellation_and_late_registration(self):
        script = 'const assert=require("node:assert/strict"), Lifecycle=require(' + json.dumps(str(support.SRC / 'scholion/web/view-lifecycle.js')) + ');\n'
        script += r'''
let visible,profile='A',revision=1,language='en',mode='patient',epoch=0,disposed=0;
const pending=new Map();let id=0;
const timers={setInterval:fn=>{pending.set(++id,fn);return id;},setTimeout:fn=>{pending.set(++id,fn);return id;},clearInterval:i=>pending.delete(i),clearTimeout:i=>pending.delete(i)};
const node=()=>({isConnected:true,contains(child){return child.parent===this;},cloneNode:()=>node(),replaceWith(next){this.isConnected=false;visible=next;}});
visible=node();
const lifecycle=Lifecycle.create({context:()=>({profile,revision,language,mode,epoch}),timers,dispose:()=>disposed++});
let a=lifecycle.begin(visible,'today'),ticks=0,cleaned=0;
assert.ok(Object.isFrozen(lifecycle.context(a)));
const stamp=lifecycle.snapshot();assert.ok(lifecycle.matches(stamp));
lifecycle.own(a,()=>cleaned++);lifecycle.interval(a,()=>ticks++,150);lifecycle.timeout(a,()=>ticks++,300);
assert.equal(lifecycle.status().resources,3);
const callbacks=[...pending.values()];callbacks[0]();assert.equal(ticks,1);
profile='B';revision=2;language='ru';mode='clinician';epoch++;
const b=lifecycle.begin(a,'visit');
assert.equal(cleaned,1);assert.equal(disposed,1);assert.equal(pending.size,0);
callbacks.forEach(fn=>fn());assert.equal(ticks,1);
assert.ok(!lifecycle.matches(stamp));assert.equal(lifecycle.context(b).profile,'B');
assert.ok(!lifecycle.current(a));assert.ok(lifecycle.current(b));
lifecycle.own(a,()=>cleaned++);assert.equal(cleaned,2,'late resources must be released immediately');
let once=0;const cancel=lifecycle.timeout(b,()=>once++,10);const fn=[...pending.values()][0];fn();
assert.equal(once,1);assert.equal(lifecycle.status().resources,0);cancel();
lifecycle.dispose();lifecycle.dispose();assert.equal(disposed,2);
'''
        self.run_js(script)

    def test_latest_language_and_shared_caches_reject_reordered_replies(self):
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        def function(name):
            start = page.index('async function ' + name + '(')
            return page[start:page.index('\n}\n', start) + 2]
        # Single-line cache helpers are called as exported page adapters here;
        # the module itself is imported, never sliced into a second renderer.
        helpers = '\n'.join(next(line for line in page.splitlines() if line.startswith('async function ' + name + '('))
                            for name in ('sources', 'systemsIndex'))
        script = 'const assert=require("node:assert/strict"), Lifecycle=require(' + json.dumps(str(support.SRC / 'scholion/web/view-lifecycle.js')) + ');\n'
        script += r'''
let LANG='en',LANGS=[],MSG={},_levels=null,_languageRead=0,_languagePending=false,profile='A',revision=1;
let _sources=null,_systems=null;const API='',document={documentElement:{}},sessionStorage={setItem(){}},localStorage=sessionStorage;
const viewLifecycle=Lifecycle.create({context:()=>({profile,revision,language:LANG})});
const replies=[],fetch=url=>new Promise(resolve=>replies.push({url,resolve}));
const requests=[],api=url=>new Promise(resolve=>requests.push({url,resolve}));
'''+function('loadLang')+'\n'+helpers+r'''
(async()=>{
 const first=loadLang('ru'),last=loadLang('en');
 replies[1].resolve({json:async()=>({lang:'en',messages:{title:'English'}})});assert.equal(await last,true);
 replies[0].resolve({json:async()=>({lang:'ru',messages:{title:'Russian'}})});assert.equal(await first,false);
 assert.equal(LANG,'en');assert.equal(MSG.title,'English');assert.equal(document.documentElement.lang,'en');
 const sourcesA=sources(),systemsA=systemsIndex();profile='B';revision++;
 const sourcesB=sources(),systemsB=systemsIndex();
 requests[2].resolve({person:'B'});requests[3].resolve({person:'B'});await sourcesB;await systemsB;
 requests[0].resolve({person:'A'});requests[1].resolve({person:'A'});await sourcesA;await systemsA;
 assert.equal(_sources.person,'B');assert.equal(_systems.person,'B');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        self.run_js(script)

    def test_every_view_entry_uses_the_shared_owner(self):
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        self.assertNotIn('cloneNode(false)', page)
        self.assertIn('src="/view-lifecycle.js"', page)
        self.assertIn("beginView('tab:'+TABS[i][0])", page)
        for key in ('system:', 'panel:', 'visit'):
            self.assertIn("beginView('" + key, page)
        self.assertIn('destroyGoalCharts();if(_loaderTimer)', page)
        self.assertIn('viewLifecycle.timeout(root,()=>pollUpdate(root),3000)', page)
        self.assertIn('viewLifecycle.interval(box,', page)

    def test_background_progress_survives_cache_invalidation_and_rejects_old_profile(self):
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        functions = []
        for name in ('loadRecompute', 'pollRecompute'):
            start = page.index('async function ' + name + '(')
            functions.append(page[start:page.index('\n}\n', start) + 2])
        script = r"""
const assert=require('node:assert/strict');
let _answerEpoch=0,_profileIdentity=null,_rcRequest=0,_recompute=null,_rcTimer=null,_rcOpen=false,_update=null,painted=0;
const calls=[],timers=[],api=path=>new Promise((resolve,reject)=>calls.push({path,resolve,reject}));
const renderRecompute=()=>painted++,renderUpdateNote=()=>{},rcRemember=()=>{},setTimeout=fn=>{timers.push(fn);return timers.length;};
let current=4,mounted=null,_systems=null,_sources=null;const mount=i=>mounted=i,forgetAnswers=()=>_answerEpoch++;
"""+'\n'.join(functions)+r"""
(async()=>{
 // First profile identity can arrive after the startup plan request.
 const initial=loadRecompute();_profileIdentity='A';calls[0].resolve({job:{status:'none'}});
 await new Promise(setImmediate);assert.equal(calls.length,2);
 calls[1].resolve({job:{status:'running'}});await initial;assert.equal(painted,1);
 // An unrelated saved measurement invalidates answers during progress polling.
 const progress=pollRecompute();_answerEpoch++;calls[2].resolve({status:'running'});
 await new Promise(setImmediate);assert.equal(calls[3].path,'/api/recompute');
 calls[3].resolve({job:{status:'running'},fresh:true});await progress;
 assert.equal(_recompute.fresh,true);assert.equal(painted,2);
 // The old patient's late reply cannot replace a newer profile plan.
 const old=pollRecompute();_profileIdentity='B';_answerEpoch++;
 const next=loadRecompute();calls[5].resolve({job:{status:'running'},person:'B'});await next;
 calls[4].resolve({status:'finished'});await old;
 assert.equal(_recompute.person,'B');assert.equal(painted,3);
 // A retry still belongs to the current application job, not a previous screen.
 const retry=pollRecompute();calls[6].reject(Error('temporary transport failure'));await retry;
 assert.equal(timers.length,1);assert.equal(timers[0],pollRecompute);
 const finished=pollRecompute();calls[7].resolve({status:'finished'});await new Promise(setImmediate);
 calls[8].resolve({job:{status:'finished'},person:'B'});calls[9].resolve({version:'synthetic'});await finished;
 assert.equal(mounted,4,'completion reopens the selected tab index');assert.equal(_recompute.job.status,'finished');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        self.run_js(script)
