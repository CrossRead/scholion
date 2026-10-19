"""System conclusions use recorded criteria and preserve treatment uncertainty."""
from datetime import date, timedelta
from unittest import TestCase, mock

import support  # noqa: F401
from scholion import core
from scholion.insight_synthesis import assess_direction, _responses
from scholion.engine.insights import attention_feed


class SystemSynthesisTests(TestCase):
    def points(self, values=(9, 8, 5, 4)):
        return [{"date": (date.today()-timedelta(days=340-i*100)).isoformat(),
                 "value": v, "ref_low": 1, "ref_high": 6, "method": "same",
                 "unit": "g/L", "record": "labs.json", "key": "ldl"}
                for i, v in enumerate(values)]

    def row(self):
        points = self.points()
        return {"key": "ldl", "name": "LDL", "series": points, "date": points[-1]["date"],
                "value": 4, "unit": "g/L", "ref_low": 1, "ref_high": 6, "flag": "ok"}

    def test_whole_laboratory_year_is_not_limited_to_phenotype_selection(self):
        with mock.patch('scholion.engine.goals.goal_dashboard', return_value={}), \
             mock.patch('scholion.core.medications_json', return_value={}), \
             mock.patch('scholion.engine.insight_links.linked_pgs_events', return_value=[]):
            feed = attention_feed({"markers": [self.row()]}, [], [], {}, [], period=30)
        group = feed['highlights'][0]
        self.assertEqual(group['system'], 'lipids')
        self.assertEqual(group['trajectory']['period'], 365)
        self.assertEqual(group['trajectory']['status'], 'toward')
        self.assertEqual(len(group['facts']), 4)

    def test_changed_reference_is_not_a_health_direction(self):
        points = self.points()
        points[0]['ref_high'] = 10
        result = assess_direction({'before': 8.5, 'after': 4.5}, self.row(), points)
        self.assertEqual(result['status'], 'unclassified')
        self.assertEqual(result['basis'], 'reference_changed')

    def test_old_history_flags_do_not_override_this_years_stable_bounds(self):
        row = {**self.row(), 'flags_comparable': False}
        self.assertEqual(assess_direction({'before': 8.5, 'after': 4.5}, row,
                                         self.points())['status'], 'toward')

    def test_latest_reversal_is_not_hidden_by_period_medians(self):
        change = {'before': 9, 'after': 5, 'latest': {'value': 10}}
        self.assertTrue(assess_direction(change, self.row(), self.points())['latest_reversal'])

    def test_explicit_target_wins_over_reference(self):
        row = {**self.row(), 'clinician_target': {'high': 3, 'unit': 'g/L'}}
        result = assess_direction({'before': 4, 'after': 5}, row, self.points())
        self.assertEqual((result['status'], result['basis']), ('away', 'target'))
        row['clinician_target']['unit'] = 'other'
        self.assertEqual(assess_direction({'before': 4, 'after': 5}, row,
                                         self.points())['basis'], 'unit_conflict')

    def test_treatment_comparison_needs_actual_start_and_monitored_marker(self):
        points = self.points()
        med = {'name': 'Synthetic', 'status': 'active', 'start_date':
               (date.today()-timedelta(days=190)).isoformat(),
               'monitoring_schedule': [{'marker': 'ldl'}]}
        event = {'kind': 'period_shift', 'name': 'LDL', 'facts': points, 'detail': {}}
        def result():
            with mock.patch('scholion.core.medications_json', return_value={'medications':[med]}), \
                 mock.patch('scholion.core.classify_drug', return_value=['synthetic']), \
                 mock.patch('scholion.engine.system_panels.class_systems', return_value={'classes':{'synthetic':['lipids']}}):
                return _responses('lipids', [event])
        response = result()[0]
        self.assertEqual(response['status'], 'temporal_comparison')
        self.assertFalse(response['causal'])
        self.assertEqual(response['comparisons'][0]['before_n'], 2)
        self.assertEqual(response['comparisons'][0]['after_n'], 2)
        med['monitoring_schedule'] = []
        self.assertEqual(result()[0]['selection'], 'system_context')
        self.assertFalse(result()[0]['response_assessed'])
        med['status'] = 'completed'
        self.assertEqual(result(), [])

    def test_expired_course_is_not_current_even_with_legacy_active_status(self):
        yesterday = (date.today()-timedelta(days=1)).isoformat()
        self.assertFalse(core.is_active_medication({'status':'active', 'end_date':yesterday}))
        self.assertFalse(core.is_active_medication({'end_date':'2020-01'}))
        self.assertTrue(core.is_active_medication({'status':'active', 'end_date':'invalid'}))
        self.assertTrue(core.is_active_medication({'status':'active', 'end_date':date.today().isoformat()}))


class MultipleWindowsTests(TestCase):
    def test_recent_reversal_does_not_replace_the_long_term_direction(self):
        points = [{"date": (date.today()-timedelta(days=d)).isoformat(), "value": v,
                   "ref_low": 1, "ref_high": 2, "unit": "u", "method": "same"}
                  for d,v in [(340,10),(280,9),(210,8),(150,7),(80,4),(60,4.5),(40,5),
                              (28,5.1),(20,5.2),(10,5.3),(0,5.4)]]
        row = {"key":"ldl", "name":"LDL", "unit":"u", "series":points,
               "date":points[-1]["date"], "value":5.4, "ref_low":1, "ref_high":2}
        with mock.patch('scholion.engine.goals.goal_dashboard',return_value={}), \
             mock.patch('scholion.core.medications_json',return_value={}), \
             mock.patch('scholion.core.focus_log',return_value={}), \
             mock.patch('scholion.engine.insight_links.linked_pgs_events',return_value=[]):
            feed=attention_feed({"markers":[row]},[],[],{},[])
        changes=feed['highlights'][0]['trajectory']['changes']
        by_window={c['window']:c for c in changes}
        self.assertEqual(set(by_window),{365,90,30})
        self.assertEqual(by_window[365]['comparison']['direction'],'down')
        for window in (90,30):
            self.assertEqual(by_window[window]['comparison']['direction'],'up')
            self.assertEqual(by_window[window]['comparison']['stage'],'forming')
            self.assertEqual(by_window[window]['status'],'away')
        self.assertEqual(feed['highlights'][0]['trajectory']['status'],'mixed')
        self.assertEqual(len(by_window[30]['series']),4)

    def test_missing_treatment_baseline_does_not_recommend_more_tests(self):
        from scholion.insight_synthesis import enrich_system
        group={'system':'lipids','name':'Lipids','events':[], 'summaries':[], 'priority':3}
        group['events']=[{'kind':'reported_response','date':date.today().isoformat(),
            'facts':[{'note':'felt better'}], 'detail':{'summary':'felt better','change':'better'}}]
        with mock.patch('scholion.insight_synthesis._responses',return_value=[
                {'summary':'No baseline recorded','comparisons':[]} ]):
            enrich_system(group)
        from scholion.i18n import t
        self.assertNotIn(t('insight.question.treatment'), group['questions'])
