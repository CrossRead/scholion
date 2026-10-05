"""C18: one goal record, a stated origin, and no invented legacy provenance."""
from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import support
from scholion import cli, core, engine, format as fmt, i18n, store
from scholion.goal_entities import ORIGINS, entity_id, goal_entities, origin_edit, origin_view


class TestGoalOrigins(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.profile = Path(tmp.name).resolve()
        self.addCleanup(support.pin_profile(self.profile))
        self.addCleanup(i18n.set_lang, getattr(i18n._state, 'current', None))
        self.data = {
            'health_goals.json': {'title': 'Synthetic aim', 'targets': [
                {'label': kind, 'source': 'lab:alt', 'target': '<20',
                 'origin': {'kind': kind, 'reason': 'Synthetic stated reason'}} for kind in ORIGINS]},
            'clinician_targets.json': {'targets': [{'marker': 'alt', 'high': 20, 'unit': 'U/L',
                'source': 'Synthetic recorded clinician instruction', 'set_on': '2026-01-01'}]},
            'focus.json': {'focus': {'id': 'synthetic-focus', 'title': 'Synthetic focus',
                'metric': {'target': 10}, 'origin': {'kind': 'complaint', 'reason': 'Synthetic complaint'}},
                'tracks': [{'title': 'Synthetic track', 'origin': {'kind': 'history', 'reason': 'Synthetic history'}}]}}
        self.write_files()

    def write_files(self):
        for filename, data in self.data.items():
            data.setdefault('_meta', {'schema': 1, 'synthetic': True, 'engine': '0.6.0'})
            (self.profile / filename).write_text(json.dumps(data), encoding='utf-8')
        core.reset_cache()

    def test_a_goal_names_where_it_came_from(self):
        before = {p.name: p.read_bytes() for p in self.profile.glob('*.json')}
        rows = goal_entities()
        self.assertEqual(9, len(rows))
        self.assertEqual(set(ORIGINS), {r['origin']['kind'] for r in rows})
        for row in rows:
            self.assertEqual('recorded', row['origin']['status'])
            self.assertTrue(row['origin']['reason'])
            self.assertIn(row['record']['file'], self.data)
        self.assertEqual(9, len({r['id'] for r in rows}))
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            result = engine.goal_dashboard()
            self.assertEqual([r['id'] for r in rows], [r['id'] for r in result['entities']])
            text = fmt.goal_report(result)
            self.assertNotIn('⟦', text)
            for row in result['entities']:
                self.assertIn(row['origin']['label'], text)
                self.assertIn(row['id'], text)
            self.assertEqual(next(r for r in result['entities'] if r['kind'] == 'focus'),
                             engine.focus_dashboard()['goal_entity'])
            focus = engine.focus_dashboard()
            self.assertEqual('recorded_goal', focus['output_kind'])
            self.assertIn(i18n.t('clinical.recorded_focus'), fmt.render_focus(focus))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.profile.glob('*.json')})

    def test_legacy_measurement_source_does_not_invent_a_goal_origin(self):
        for origin in (None, {'kind': 'lab'}, {'kind': 'invented', 'reason': 'Synthetic'},
                       {'kind': 'genome', 'reason': '  '}, True):
            row = {'source': 'lab:alt', '_from': {'source': 'guideline'}, 'origin': origin}
            self.assertEqual('unspecified', origin_view(row, 'health_goals.json')['status'])
            self.assertIsNone(origin_view(row, 'health_goals.json')['kind'])
        self.assertEqual('unspecified', origin_view({}, 'clinician_targets.json')['status'])

    def test_clinician_and_focus_goals_do_not_require_a_separate_health_goal(self):
        self.data['health_goals.json'] = {}
        self.write_files()
        result = engine.goal_dashboard()
        self.assertTrue(result['available'])
        self.assertEqual(3, len(result['entities']))
        self.assertIn('Synthetic focus', fmt.goal_report(result))
        self.data['clinician_targets.json'] = {}
        self.data['focus.json'] = {}
        self.write_files()
        self.assertFalse(engine.goal_dashboard()['available'])

    def test_recording_each_origin_preserves_target_charts_and_other_records(self):
        for kind in ORIGINS:
            entity = next(r for r in goal_entities() if r['title'] == kind)
            before = copy.deepcopy(core.read_profile_json(self.profile / 'health_goals.json'))
            result = store.set_goal_origin(entity['id'], 'prevention', 'Synthetic explicit reason')
            self.assertTrue(result['ok'])
            after = core.read_profile_json(self.profile / 'health_goals.json')
            index = entity['record']['pointer'][1]
            old, new = before['targets'][index], after['targets'][index]
            self.assertEqual({k: v for k, v in old.items() if k != 'origin'},
                             {k: v for k, v in new.items() if k != 'origin'})
            before['targets'][index]['origin'] = new['origin']
            self.assertEqual(before, after)
            self.assertEqual(entity['id'], goal_entities()[index]['id'])
        for title in ('Synthetic focus', 'Synthetic track', 'alt'):
            entity = next(r for r in goal_entities() if r['title'] == title)
            self.assertTrue(store.set_goal_origin(entity['id'], 'history', 'Synthetic testimony')['ok'])

    def test_invalid_or_stale_ids_never_write_and_a_failed_write_does_not_change_cache(self):
        entity = goal_entities()[0]
        before = {p.name: p.read_bytes() for p in self.profile.glob('*.json')}
        for args in ((entity['id'], 'other', 'why'), (entity['id'], 'lab', ''),
                     ('../../outside', 'lab', 'why'), (entity['id'], None, None)):
            self.assertFalse(store.set_goal_origin(*args)['ok'])
        cached = copy.deepcopy(core.read_profile_json(self.profile / 'health_goals.json'))
        with mock.patch.object(store, '_write_json', side_effect=OSError('Synthetic denied write')):
            with self.assertRaises(OSError):
                store.set_goal_origin(entity['id'], 'prevention', 'Synthetic reason')
        self.assertEqual(cached, core.read_profile_json(self.profile / 'health_goals.json'))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.profile.glob('*.json')})
        self.data['health_goals.json']['targets'].reverse()
        self.write_files()
        self.assertFalse(origin_edit(entity['id'], 'lab', 'reason')['ok'])
        self.assertNotEqual(entity_id('health_goals.json', ('targets', 0), {'target': 1}),
                            entity_id('health_goals.json', ('targets', 0), {'target': 2}))

    def test_cli_and_web_use_the_same_core_writer_without_a_new_tool_name(self):
        entity = goal_entities()[0]
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(['target', 'origin', entity['id'], '--origin', 'genome',
                             '--reason', 'Synthetic stated genome reason', '--json'])
        self.assertEqual(0, code)
        self.assertEqual('genome', json.loads(out.getvalue())['origin']['kind'])
        web = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        server = (support.SRC / 'scholion/server.py').read_text(encoding='utf-8')
        self.assertIn("post('/api/targets',{action:'origin'", web)
        self.assertIn('store.set_goal_origin', server)
        self.assertIn('goalEntitiesHTML(g.entities||[])', web)

    def test_goal_origin_reaches_the_existing_agent_tools(self):
        from scholion import mcp_server, ouroboros_tools
        ouroboros_tools.unpin_session()
        self.addCleanup(ouroboros_tools.unpin_session)
        text = ouroboros_tools._h_goal(ouroboros_tools.ToolContext())
        answer = mcp_server.call_tool('sch_goal')['content'][0]['text']
        for row in goal_entities():
            for report in (text, answer):
                self.assertIn(row['id'], report)
                self.assertIn(row['origin']['label'], report)

    def test_http_records_the_same_origin_and_keeps_the_goal_value(self):
        import threading
        import urllib.request
        from scholion import server
        srv = server._Server(('127.0.0.1', 0), server.Handler)
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = 'http://127.0.0.1:' + str(srv.server_address[1])
        entity = goal_entities()[0]
        req = urllib.request.Request(base + '/api/targets',
            data=json.dumps({'action': 'origin', 'goal_id': entity['id'], 'origin': 'history',
                             'reason': 'Synthetic relayed reason'}).encode(),
            headers={'Content-Type': 'application/json', 'Origin': base})
        with urllib.request.urlopen(req, timeout=10) as response:
            self.assertTrue(json.load(response)['ok'])
        with urllib.request.urlopen(base + '/api/goal', timeout=10) as response:
            result = json.load(response)
        saved = next(r for r in result['entities'] if r['id'] == entity['id'])
        self.assertEqual('history', saved['origin']['kind'])
        self.assertEqual(entity['target'], saved['target'])

    def test_accepted_lab_goal_has_origin_but_observations_are_not_auto_written(self):
        result = store.write_goal_targets([{'key': 'alt', 'name': 'New synthetic target',
            'proposed': 'guideline', 'target': {'comparator': '<', 'value': 20},
            'candidates': [{'source': 'guideline', 'proposal_status': 'held',
                            'target_basis': {'status': 'complete', 'source': 'PMID: 99999999',
                                             'mechanism': 'Synthetic independent target basis'}}]}])
        self.assertEqual(['New synthetic target'], result['added'])
        entity = next(r for r in goal_entities() if r['title'] == 'New synthetic target')
        self.assertEqual('lab', entity['origin']['kind'])
        self.assertEqual('lab:alt', entity['origin']['reason'])

    def test_a_withheld_candidate_cannot_be_saved_as_a_goal(self):
        before = copy.deepcopy(core.health_goals())
        result = store.write_goal_targets([{'key': 'alt', 'name': 'Unsupported synthetic target',
            'proposed': 'guideline', 'target': {'comparator': '<', 'value': 20}, 'candidates': []}])
        self.assertEqual([], result['added'])
        self.assertEqual(before['targets'], core.health_goals()['targets'])
