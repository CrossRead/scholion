"""Testimony is shown without requiring laboratory proof or implying causation."""
import io
from contextlib import redirect_stdout
from datetime import date, timedelta
from unittest import mock

from tests.test_a_journal_factor_is_the_persons_not_the_builds import _Profile
from scholion import cli, core, store, ouroboros_tools
from scholion.reported_response import events
from scholion.engine.insights import attention_feed


class ReportedResponseTests(_Profile):
    def setUp(self):
        super().setUp()
        ouroboros_tools.unpin_session()
        self.addCleanup(ouroboros_tools.unpin_session)
        self.day = date.today().isoformat()
        self.response = {'system': 'lipids', 'aspect': 'function', 'change': 'better', 'medication': 'Example'}

    def record(self, **kwargs):
        return store.add_focus_entry(self.day, note='Walking feels easier.', response={**self.response, **kwargs})

    def test_report_without_labs_is_not_lost_or_called_a_measured_effect(self):
        self.assertTrue(self.record()['ok'])
        with mock.patch('scholion.engine.goals.goal_dashboard', return_value={}), \
             mock.patch('scholion.engine.insight_links.linked_pgs_events', return_value=[]):
            feed = attention_feed({}, [], [], {}, [])
        item = feed['highlights'][0]
        self.assertEqual(item['system'], 'lipids')
        self.assertEqual(item['trajectory']['status'], 'reported')
        self.assertIn('Walking feels easier.', item['summaries'][0])
        self.assertFalse(item['events'][0]['detail']['causal'])
        self.assertFalse(item['facts'][0]['during_recorded_course'])

    def test_each_system_and_aspect_is_retained_beside_old_journal(self):
        store.add_focus_entry(self.day, note='Existing journal entry')
        self.record()
        self.record(aspect='tolerability', change='worse')
        self.record(change='mixed')
        store.add_focus_entry(self.day, note='Updated journal entry')
        data = core.focus_log()
        self.assertEqual(len(data['responses']), 2)
        self.assertEqual(data['entries'][0]['note'], 'Updated journal entry')
        self.assertEqual({r['response']['change'] for r in data['responses']}, {'mixed', 'worse'})

    def test_invalid_or_future_observation_preserves_bytes(self):
        self.record()
        p = self.d/'focus_log.json'; before = p.read_bytes()
        for value in ({**self.response, 'system':'unknown'}, {**self.response, 'change':'effective'}, None):
            if value is not None:
                self.assertFalse(store.add_focus_entry(self.day, note='Test', response=value)['ok'])
        self.assertFalse(store.add_focus_entry((date.today()+timedelta(days=1)).isoformat(), note='Test', response=self.response)['ok'])
        self.assertFalse(store.add_focus_entry(self.day, note='', response=self.response)['ok'])
        self.assertEqual(p.read_bytes(), before)

    def test_actual_course_dates_qualify_chronology_only(self):
        meds = {'medications':[{'name':'Example', 'start_date':self.day, 'status':'active'}]}
        self.record()
        with mock.patch('scholion.core.medications_json', return_value=meds):
            self.assertTrue(events()[0]['facts'][0]['during_recorded_course'])
            meds['medications'][0]['start_date'] = (date.today()+timedelta(days=1)).isoformat()
            self.assertFalse(events()[0]['facts'][0]['during_recorded_course'])

    def test_cli_and_tool_write_the_same_testimony(self):
        args = ['focus-log', self.day, '--note', 'Walking feels easier.', '--json']
        for k,v in self.response.items(): args.extend(['--response-'+k, v])
        with redirect_stdout(io.StringIO()): cli.main(args)
        first = core.focus_log()['responses'][0]
        tool = next(t for t in ouroboros_tools.get_tools() if t.name=='sch_focus_log')
        with mock.patch('scholion.upgrade.session_note', return_value=''):
            tool.handler(ouroboros_tools.ToolContext(), date=self.day, note='Walking feels easier.',
                         **{'response_'+k:v for k,v in self.response.items()})
        self.assertEqual(core.focus_log()['responses'], [first])
        self.assertIn('response_change', tool.schema['parameters']['properties'])

    def test_old_reports_remain_in_journal_but_not_current_insights(self):
        day = (date.today()-timedelta(days=400)).isoformat()
        store.add_focus_entry(day, note='Walking felt easier.', response=self.response)
        self.assertEqual(events(), [])
        self.assertEqual(len(core.focus_log()['responses']), 1)
