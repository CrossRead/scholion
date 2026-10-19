"""Run the chart code: missing observations are gaps, not interpolated facts."""
from __future__ import annotations

import shutil
import subprocess
import unittest

import support


@unittest.skipUnless(shutil.which("node"), "needs node for the page's JavaScript")
class TestChartRoles(unittest.TestCase):
    def test_all_goal_charts_share_roles_and_preserve_gaps(self):
        page = (support.SRC / "scholion/web/index.html").read_text(encoding="utf-8")
        helpers = page[page.index("let _goalMarksReady="):page.index("// A chart box is emitted")]
        start = page.index("function drawGoalCharts(")
        draw = page[start:page.index("\n}\n", start) + 2]
        start_helpers = page.index("function measurementLabel(")
        helpers += page[start_helpers:page.index("function sparkline(", start_helpers)]
        script = r"""
const assert=require('node:assert/strict');
let theme='light',plugin,charts=[];
const tok=name=>theme+name,$=selector=>selector,t=key=>key;
class Chart{
  static defaults={font:{}};
  static register(p){plugin=p;}
  constructor(node,config){this.config=config;charts.push(this);}
  destroy(){}
}
""" + helpers + draw + r"""
const labels=['2020-01','2021-01','2022-01'];
const values=[13,null,27], targets=[{value:20,label:'target',color:'legacy-colour'}];
const paired={l:labels,a:values,b:[17,20,null],a_label:'first',b_label:'second',
  a_color:'legacy-first',b_color:'legacy-second',targets};
const input={weight:{l:labels,v:values,targets},
 bodycomp:{l:labels,fat:values,mus:[17,20,null],targets},
 minis:[{l:labels,v:values,id:'test',color:'legacy-mini',tgt:20,tlabel:'target'}],
 fit:paired,la:paired};
const before=JSON.stringify(input);
for(theme of ['light','dark']){
  charts=[];drawGoalCharts(input,{});assert.equal(charts.length,5);
  for(const chart of charts){
    const c=chart.config;
    for(const ds of c.data.datasets){
      assert.equal(ds.borderColor,theme+'--chart-series');
      assert.equal(ds.pointBackgroundColor,theme+'--chart-series');
      assert.equal(ds.spanGaps,false);assert.equal(ds.tension,0);
      assert.ok(ds.data.includes(null));assert.equal(ds.fill,false);
    }
    if(c.data.datasets.length===2){
      assert.equal(c.options.plugins.legend.display,true);
      assert.deepEqual(c.data.datasets[0].borderDash,[]);
      assert.deepEqual(c.data.datasets[1].borderDash,[2,3]);
      assert.equal(c.data.datasets[1].pointStyle,'triangle');
      assert.ok(c.options.scales.y.title.text);assert.ok(c.options.scales.y2.title.text);
    }
  }
}
assert.equal(JSON.stringify(input),before);
const painted=[],ctx={save(){},restore(){},beginPath(){},moveTo(){},lineTo(){},
  fillRect(...rect){painted.push(['band',this.fillStyle,rect]);},
  strokeRect(...rect){painted.push(['boundary',this.strokeStyle,rect]);},
  setLineDash(dash){this.dash=dash;},
  stroke(){painted.push(['target',this.strokeStyle,this.dash]);},fillText(){}};
const chart={ctx,chartArea:{left:0,right:100,top:0,bottom:80},data:{labels},
  scales:{x:{getPixelForValue:i=>i*50},y:{getPixelForValue:v=>v}},
  options:{plugins:{marks:{band:{from:'2020-01',to:'2022-01'},targets}}}};
plugin.beforeDraw(chart);plugin.afterDraw(chart);
assert.deepEqual(painted,[['band','dark--chart-band',[0,0,100,80]],
  ['boundary','dark--chart-boundary',[0,0,100,80]],['target','dark--chart-target',[6,4]]]);
for(const band of [{from:'2010',to:'2011'},{from:'2021-06',to:'2021-09'},
                  {from:'2030',to:'2031'}]){
  painted.length=0;chart.options.plugins.marks.band=band;plugin.beforeDraw(chart);
  assert.deepEqual(painted,[]);
}
"""
        result = subprocess.run([shutil.which("node"), "-e", script], text=True,
                                capture_output=True, stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_weight_and_attention_use_the_compact_annual_view(self):
        page = (support.SRC / "scholion/web/index.html").read_text(encoding="utf-8")
        names = ("measurementLabel", "measurementGroups", "bodyMassMetric", "measurementDatasets",
                 "sparkline", "insightContextHTML", "attentionItemHTML", "attentionHTML")
        functions = []
        for name in names:
            start = page.index("function " + name + "(")
            if name in ("measurementGroups", "bodyMassMetric"):
                functions.append(page[start:].splitlines()[0])
            else:
                functions.append(page[start:page.index("\n}", start) + 2])
        script = STUBS + "\n".join(functions) + BEHAVIOR
        result = subprocess.run([shutil.which("node"), "-e", script], text=True,
                                capture_output=True, stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("data-period=", page)
        self.assertNotIn("applyPeriod", page)
        self.assertIn("${[365].map(window=>{", page)


STUBS = "const assert=require('node:assert/strict');const esc=x=>String(x??''),t=(x)=>x,fmtDate=x=>x,fmtNum=x=>String(x),CT={series:'orange',ink2:'black'},gline=(v,c)=>({data:v,borderColor:c});\nconst DISPLAY_MODE='patient',visitSelection=new Set();\nconst insightWindowsHTML=()=>'',levelChip=()=>'',insightFactHTML=f=>f.record,comparisonHTML=()=>'';\n"
BEHAVIOR = 'const points=[{date:\'2026-01\',value:105,measurement_source:\'garmin\',aggregation:\'monthly_mean\'},{date:\'2026-02-20\',value:103,measurement_source:\'recorded\'},{date:\'2026-06\',value:101,measurement_source:\'garmin\',aggregation:\'monthly_mean\'},{date:\'2026-10-19\',value:98,measurement_source:\'recorded\'}];\nassert.equal(measurementDatasets({points},true).length,1);\nassert.deepEqual(measurementDatasets({points},true)[0].data,[105,103,101,98]);\nconst graph=sparkline(points,false,null,true);\nassert.equal((graph.match(/<polyline/g)||[]).length,1);assert.equal((graph.match(/<circle/g)||[]).length,4);\nassert.ok(graph.includes(\'garmin\'));assert.ok(graph.includes(\'web.phenotype.recorded\'));\nassert.equal((sparkline(points,false).match(/<polyline/g)||[]).length,2);\nfor(const key of [\'weight\',\'wear:Weight\',\'metric:weight\',\'BMI\',\'wear:BMI\'])assert.ok(bodyMassMetric(key));\nassert.ok(!bodyMassMetric(\'SleepDuration\'));\nconst item={id:\'system:lipids\',system:\'lipids\',title:\'Lipid trend\',summaries:[\'Measured change\'],context_summary:\'PRIVATE GENETIC SUMMARY\',context_lifestyle_summary:\'PRIVATE LIFESTYLE SUMMARY\',context:{genetics:[{gene:\'SYN\',summary:\'PRIVATE GENE\'}],lifestyle:[{key:\'weight\',value:98}],comparisons:[{summary:\'PRIVATE COMPARISON\'}]},facts:[{record:\'genotype\'},{record:\'labs.json\'}],events:[{kind:\'genetic_phenotype\',detail:{mechanism:\'PRIVATE MECHANISM\'}}]};\nconst card=attentionItemHTML(item);\nassert.ok(card.startsWith(\'<details class="cr-card attention-item" data-attention-card><summary>\'));\nassert.ok(!card.includes(\' open\'));assert.ok(!card.includes(\'PRIVATE\'));assert.ok(!card.includes(\'data-genetic-comparison\'));\nassert.ok(card.includes(\'data-panel="lipids"\'));assert.ok(card.includes(\'data-goto="web.tab.lifestyle"\'));assert.ok(card.includes(\'labs.json\'));\nconst feed=attentionHTML({highlights:Array.from({length:8},(_,i)=>({...item,id:String(i)})),follow_up:[{...item,id:\'follow\'}]});\nassert.equal((feed.match(/data-attention-card/g)||[]).length,9);\nconsole.log(\'Weight, annual controls, collapsed attention and context links PASS\');\n'
