"""Release review regressions: selected evidence, stable identity and recovery."""
from __future__ import annotations

import copy
from datetime import date, timedelta
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest import TestCase, mock, skipUnless

import support
from scholion import core, i18n, insight_history
from scholion.engine.goals import _phenotype_rows
from scholion.engine.insights import attention_feed
from scholion.insight_synthesis import _responses
from scholion.measurements import history
from scholion.period_summary import period_summary
from scholion.trend_qualification import comparable_observations, period_shift


class EvidenceRegressions(TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        i18n.set_lang('en')

    def test_stale_agenda_http_error_is_localized_without_exposing_internal_errors(self):
        from scholion.server import Handler
        from scholion.engine.visit import VisitSelectionChanged
        handler = object.__new__(Handler)
        with mock.patch.object(handler, '_json') as response:
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                handler._fail(VisitSelectionChanged('untrusted detail'))
                response.assert_called_with({'error': i18n.t('visit.selection_changed')}, 409)
            with mock.patch('scholion.server.traceback.print_exc'):
                handler._fail(ValueError('private internal path'))
            response.assert_called_with({'error': i18n.t('server.internal_error')}, 500)

    def test_unselected_devices_never_supply_a_mixed_delta(self):
        points = [{'date': d, 'value': v, 'measurement_source': src,
                   'device': src, 'aggregation': 'monthly_mean', 'unit': 'kg'}
                  for d, v, src in [('2026-01', 80, 'garmin'), ('2026-02', 80, 'garmin'),
                                     ('2026-09', 110, 'whoop'), ('2026-10', 110, 'whoop')]]
        rows = [{'components': [{'ref': 'wear:Weight', 'series': points,
                                 'missing': 'several_devices', 'aggregation': 'monthly_mean'}]}]
        for primary in (None, 'garmin', 'whoop'):
            with self.subTest(primary=primary), mock.patch.object(core, 'wearable_primary', return_value=primary):
                period = period_summary(rows, 365, date(2026, 10, 18))[0]['components'][0]['period']
                self.assertEqual(period['series'], points)
                self.assertEqual(period['delta'], 0 if primary else None)
                self.assertEqual(period['comparison_source'], primary)
                self.assertEqual(len(period['comparison_series']), 2 if primary else 0)
        self.assertEqual(rows[0]['components'][0]['series'], points)

    def test_trend_insights_follow_the_same_selected_device_as_current_values(self):
        from scholion.engine.insight_events import _annual_events
        for window,days in [(365,[340,240,140,40]),(90,[85,60,35,5]),(30,[28,20,12,2])]:
            for values in ([80,80,80,80],[100,90,80,70]):
                points=[{'date':(date.today()-timedelta(days=d)).isoformat(),'value':v,
                         'measurement_source':source,'device':source,'aggregation':'observation','unit':'kg'}
                        for source,vals in [('garmin',values),('whoop',[60,70,90,100])]
                        for d,v in zip(days,vals)]
                rows=[{'label':'Weight','components':[{'ref':'wear:Weight','series':points}]}]
                with mock.patch.object(core,'wearable_primary',return_value='garmin'):
                    events=_annual_events(rows,{'markers':[]},window)
                self.assertEqual(len(events),0 if values[0]==values[-1] else 1)
                for event in events:
                    self.assertEqual(event['detail']['direction'],'down')
                    self.assertEqual(event['detail']['measurement_source'],'garmin')
                self.assertEqual(len(rows[0]['components'][0]['series']),8)

    def test_effective_reference_changes_are_visible_in_review_history(self):
        row = {'key': 'synthetic-marker', 'name': 'Synthetic marker', 'unit': 'u',
               'date': date.today().isoformat(), 'value': 12, 'ref_low': 1, 'ref_high': 10,
               'ref_origin': 'profile', 'flag': 'high', 'abnormal': True,
               'display_recency': True, 'series': [{'date': date.today().isoformat(),
                   'value': 12, 'method': 'same', 'date_source': 'form'}]}
        with mock.patch('scholion.engine.goals.goal_dashboard', return_value={}):
            old = attention_feed({'markers': [row]}, [], [], {}, [])
            snapshot = insight_history._snapshot(old)
            row.update(ref_low=15, ref_high=20, flag='low')
            new = attention_feed({'markers': [row]}, [], [], {}, [])
            diff = next(x for x in insight_history.compare_review(new, snapshot)['items']
                        if x['id'] == 'lab:synthetic-marker')
            self.assertEqual((diff['status'], diff['reason']), ('changed', 'data'))
            row.update(flag='ok', abnormal=False)
            normal = attention_feed({'markers': [row]}, [], [], {}, [])
            diff = next(x for x in insight_history.compare_review(normal, snapshot)['items']
                        if x['id'] == 'lab:synthetic-marker')
            self.assertNotEqual(diff['status'], 'resolved', 'a changed corridor is not a new normal measurement')

    def test_reference_origin_is_evidence_but_translation_is_not(self):
        from scholion.engine.insight_events import _fact, _fact_identity
        point = {'date': '2026-10-01', 'value': 12}
        row = {'unit': 'u', 'ref_low': 1, 'ref_high': 10, 'ref_origin': 'profile'}
        inherited = _fact_identity(_fact('x', point, row))
        own = _fact_identity(_fact('x', {**point, 'ref_low': 1, 'ref_high': 10}, row))
        self.assertNotEqual(inherited, own)
        self.assertEqual(inherited, _fact_identity(_fact('x', point, {**row, 'unit_display': 'translated'})))

    def test_device_only_review_and_confirmation_are_language_independent(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, support.env(Path(tmp).resolve())):
            for name in ('Weight', 'StepsDaily', 'SleepHours'):
                wear = {'sources': {'garmin': {'metrics': {name: {
                    '2026-01': 100, '2026-03': 90, '2026-06': 80, '2026-09': 70}}}}}
                with self.subTest(metric=name), mock.patch.object(core, 'metrics_json', return_value={'profile': {}, 'metrics': {}}), \
                     mock.patch.object(core, 'wearable_trends', return_value=wear), \
                     mock.patch.object(core, 'medications_json', return_value={}), \
                     mock.patch.object(core, 'focus_log', return_value={}):
                    def feed():
                        rows = _phenotype_rows([{'label': name, 'source': 'wear:' + name}])
                        with mock.patch('scholion.engine.goals.goal_dashboard', return_value={'phenotype': rows}):
                            return attention_feed({'markers': []}, [], [], {'metrics': []}, [])
                    i18n.set_lang('en')
                    before = history(name)
                    old = feed()
                    self.assertTrue(old['items'])
                    snapshot = insight_history._snapshot(old)
                    with mock.patch('scholion.engine.overview', side_effect=lambda: {'attention': feed()}):
                        token = insight_history.review_snapshot()['confirmation']
                        i18n.set_lang('ru')
                        self.assertEqual(history(name), before)
                        self.assertEqual(insight_history.review_snapshot()['confirmation'], token)
                        self.assertTrue(insight_history.review_snapshot(token)['saved'])
                    self.assertTrue(all(x['status'] == 'unchanged'
                                        for x in insight_history.compare_review(feed(), snapshot)['items']))

    def test_approximate_dates_do_not_establish_trend_or_treatment_order(self):
        points = [{'date': (date.today()-timedelta(days=d)).isoformat(), 'value': v,
                   'record': 'labs.json', 'key': 'ldl', 'unit': 'mmol/L', 'method': 'same'}
                  for d, v in [(340, 9), (240, 8), (140, 5), (40, 4)]]
        med = {'name': 'Synthetic', 'status': 'active',
               'start_date': (date.today()-timedelta(days=190)).isoformat(),
               'monitoring_schedule': [{'marker': 'ldl'}]}
        for basis in ('filename', 'ordered', 'form', 'manual'):
            sample = [{**p, 'date_source': basis} for p in points]
            original = copy.deepcopy(sample)
            approximate = basis in ('filename', 'ordered')
            qualification = comparable_observations(sample)
            self.assertEqual(qualification['eligible'], not approximate)
            self.assertEqual(period_shift(sample)['eligible'], not approximate)
            if approximate:
                self.assertIn('date_approximate', qualification['reasons'])
                self.assertEqual(len(qualification['approximate_dates']), 4)
            with mock.patch.object(core, 'medications_json', return_value={'medications': [med]}), \
                 mock.patch.object(core, 'classify_drug', return_value=['synthetic']), \
                 mock.patch('scholion.engine.system_panels.class_systems', return_value={'classes': {'synthetic': ['lipids']}}):
                result = _responses('lipids', [{'kind': 'period_shift', 'name': 'LDL',
                                               'facts': sample, 'detail': {}}])[0]
            self.assertFalse(result['causal'])
            self.assertEqual(result['status'], 'not_assessable' if approximate else 'temporal_comparison')
            if approximate:
                self.assertEqual(result['comparisons'], [])
                self.assertEqual(result['summary'], i18n.t('insight.rx.date_uncertain', drug='Synthetic'))
            self.assertEqual(sample, original)


@skipUnless(shutil.which('node'), 'needs node for the actual view function')
class VisitRecovery(TestCase):
    def test_refusal_network_failure_retry_and_reselection(self):
        page = (support.ROOT / 'src/scholion/web/index.html').read_text(encoding='utf-8')
        start = page.index('async function viewVisitSheet(')
        function = page[start:page.index('\nasync function viewLabs(', start)]
        script = r"""
const assert=require('node:assert/strict');
let overviewRead=0,visitSelection=new Set(['lab:removed']),visitSelectionTouched=true,DISPLAY_MODE='patient';
let visitFocusSystems=['lipids'],visitFocusPanels=['methylation'],visitFocusQuestion='Synthetic question';
const nodes={},$=id=>nodes[id]??={};
let forgotten=0, mounted=0;
const forgetAnswers=()=>forgotten++,mount=()=>mounted++,setDisplayMode=m=>{DISPLAY_MODE=m;mounted++;};
const t=k=>k,esc=x=>String(x).replaceAll('<','&lt;'),fmtDate=String;
const showLoader=r=>r.innerHTML='Loading',markCurrentTab=()=>{},wireSystems=()=>{};
const cautionsHtml=()=>'',controlsHtml=()=>'',reviewChangesHTML=()=>'',visitInsightHTML=()=>'';
const root={isConnected:true,innerHTML:'',className:''};
let answer,requested;
const api=async url=>{requested=url;if(answer instanceof Error)throw answer;return answer;};
""" + function + r"""
(async()=>{
 for(const failure of [{error:'Changed <topic>'},new Error('network'),{},null]){
   answer=failure;await viewVisitSheet(root);
   assert.notEqual(root.innerHTML,'Loading');assert.ok(root.innerHTML.includes('role="alert"'));
   assert.ok(!root.innerHTML.includes('<topic>'));assert.ok(visitSelection.has('lab:removed'));
   answer={container:{id:'synthetic'},treatment:{controls:[]},sources:{},reference_appendix:{included:false}};
   await $('#visit-retry').onclick();assert.ok(root.innerHTML.includes('visit-cover'));
   assert.ok(requested.includes('item=lab%3Aremoved'),'retry preserves explicit selection');
   assert.ok(requested.includes('system=lipids')&&requested.includes('panel=methylation')&&requested.includes('focus=Synthetic+question'),'retry preserves visit focus');
 }
 answer={error:'stale'};await viewVisitSheet(root);
 $('#visit-reselect').onclick();assert.equal(visitSelection.size,0);assert.equal(visitSelectionTouched,false);
 assert.equal(mounted,1);assert.equal(forgotten,5);
 DISPLAY_MODE='clinician';await viewVisitSheet(root);$('#visit-reselect').onclick();
 assert.equal(DISPLAY_MODE,'patient');assert.equal(mounted,2);
 let finish;answer={};const oldApi=api;
 root.isConnected=false;await viewVisitSheet(root);assert.equal(mounted,2);
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        result = subprocess.run([shutil.which('node'), '-e', script], capture_output=True, text=True,
                                stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
