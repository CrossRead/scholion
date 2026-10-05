"""C23: data-workflow routes are not administration routes or clinical orders."""
from __future__ import annotations

import copy
import unittest

import support  # noqa: F401 -- synthetic test environment setup
from scholion import engine, format as fmt, i18n, mcp_server, ouroboros_tools
from scholion.genome_routes import ROUTES, decision_route, route_text
from test_every_face_carries_the_same_positions_and_levels import _Read


class TestDecisionRoutes(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, getattr(i18n._state, 'current', None))
        self.basis = {'status': 'complete', 'source': 'PMID: 99999999', 'mechanism': 'Synthetic mechanism'}
        self.row = {'rsid': 'rs99999999', 'read': True, 'level': 'A', 'state': 'het',
                    'conclusion_basis': self.basis, 'expect_check': {'marker': 'alt'},
                    'subclaim_basis': {'expect': self.basis}}
        self.markers = {'alt': {'value': 20, 'unit': 'U/L', 'date': '2026-01-01', 'series': []}}

    def test_the_three_routes_and_their_distinct_meanings(self):
        now = decision_route(self.row, self.markers)
        self.assertEqual('decision_now', now['kind'])
        self.assertTrue(now['ready'])
        self.assertEqual({'value': 20, 'unit': 'U/L', 'date': '2026-01-01'}, now['observation'])
        first = decision_route(self.row, {})
        self.assertEqual('first_lab', first['kind'])
        self.assertFalse(first['ready'])
        self.assertEqual(['measurement'], first['blocked_by'])
        without = decision_route({**self.row, 'expect_check': None}, {})
        self.assertEqual('no_marker', without['kind'])
        self.assertTrue(without['ready'])
        self.assertIsNone(without['marker'])
        self.assertIn('does not establish', without['reason'])

    def test_a_censored_invalid_or_undated_value_does_not_open_decision_now(self):
        for change in ({'value': True}, {'value': float('nan')}, {'value': float('inf')},
                       {'value': None}, {'date': None}, {'date': True}, {'date': '2026-02-30'},
                       {'unit': ''}, {'unit': None},
                       {'series': [{'date': '2026-01-01', 'value': 20, 'censored': '<'}]}):
            with self.subTest(change=change):
                result = decision_route(self.row, {'alt': {**self.markers['alt'], **change}})
                self.assertEqual('first_lab', result['kind'])
                self.assertFalse(result['ready'])
                self.assertIsNone(result['observation'])

    def test_unread_unsupported_and_lower_levels_remain_blocked_in_any_route(self):
        for change, block in (({'read': False}, 'genotype'), ({'presumed': True}, 'confirmation'),
                              ({'needs_confirmation': True}, 'confirmation'),
                              ({'genotype': {'depth_unverified': True}}, 'confirmation'),
                              ({'genotype': {'confidence': 'profile'}}, 'confirmation'),
                              ({'reading': {'read': True, 'quality': {'depth_unverified': True}}}, 'confirmation'),
                              ({'conclusion_basis': {'status': 'incomplete'}}, 'basis')):
            result = decision_route({**self.row, **change}, self.markers)
            self.assertFalse(result['ready'])
            self.assertIn(block, result['blocked_by'])
        for level in ('C', 'D', 'E', None):
            result = decision_route({**self.row, 'level': level}, self.markers)
            self.assertFalse(result['ready'])
            self.assertIn('evidence_level', result['blocked_by'])
        ref = decision_route(self.row, self.markers, reference=True)
        self.assertFalse(ref['ready'])
        self.assertIn('reference_only', ref['blocked_by'])

    def test_marker_association_never_borrows_a_positions_support(self):
        row = {**self.row, 'subclaim_basis': {'expect': {'status': 'incomplete'}}}
        result = decision_route(row, self.markers)
        self.assertEqual('no_marker', result['kind'])
        self.assertIsNone(result['marker'])
        self.assertFalse(result['ready'])
        self.assertIn('marker_basis', result['blocked_by'])
        self.assertEqual('', route_text({}))
        saved = copy.deepcopy(row)
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            result = decision_route(row, self.markers)
            text = route_text({'decision_route': result})
            self.assertIn(result['label'], text)
            self.assertIn(result['notice'], text)
            self.assertNotIn('⟦', text)
        self.assertEqual(saved, row)


class TestEveryPositionRouteOnExistingDoors(_Read):
    def test_every_position_has_a_route(self):
        count = 0
        keys = [d['key'] for d in engine.domains() if d['genetic_half']]
        keys += ['author_list']
        for key in keys:
            for register in ('patient', 'clinician'):
                result = engine.system(key, register)
                positions = result.get('positions') if key == 'author_list' else result['genetics']['positions']
                for row in positions:
                    with self.subTest(key=key, rsid=row['rsid'], register=register):
                        self.assertIn(row['decision_route']['kind'], ROUTES)
                        self.assertIsInstance(row['decision_route']['blocked_by'], list)
                        self.assertTrue(row['decision_route']['notice'])
                        count += 1
        self.assertGreater(count, 350)

    def test_route_labels_reach_existing_agent_tools_and_clinician_text(self):
        from scholion.i18n import t
        for key in ('cardio', 'thyroid', 'author_list'):
            result = engine.system(key, 'clinician')
            positions = result['positions'] if key == 'author_list' else result['genetics']['positions']
            reports = (fmt.system_report(result),
                       ouroboros_tools._h_system(ouroboros_tools.ToolContext(), key=key),
                       mcp_server.call_tool('sch_system', {'key': key})['content'][0]['text'])
            for row in positions:
                for text in reports:
                    self.assertIn(row['decision_route']['label'], text)
            for text in reports:
                self.assertIn(t('genome.route.notice'), text)
