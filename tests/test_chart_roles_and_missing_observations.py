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
