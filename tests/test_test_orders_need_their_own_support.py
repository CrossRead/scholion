"""Synthetic support tests; no invented identifier is offered as real evidence."""
from __future__ import annotations

import datetime
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, format as fmt, i18n
from scholion.engine import labs
from scholion.test_proposals import guard_test_proposal, test_basis_text


def supported():
    rule = {'id': 'synthetic', 'suggest': 'Synthetic test', 'why': 'Synthetic reason',
            'priority': 'high', 'specialist': 'Synthetic role', 'recheck_months': 3,
            'when': {'measured': ['a']}, 'covers': ['a', 'b'],
            'applicability': {'status': 'held', 'context': 'Synthetic context only'}}
    for name in ('suggest', 'why', 'condition', 'priority', 'specialist', 'recheck'):
        rule[name + '_basis'] = {'source': 'PMID: 99999999', 'mechanism': name + ' fixture mechanism only'}
    return rule


class TestIndependentTestProposals(unittest.TestCase):
    def engine(self, rule, date=None):
        with mock.patch.object(core, 'test_rules', return_value={'rules': [rule]}), \
                mock.patch.object(labs, '_eval_condition', return_value=True), \
                mock.patch.object(labs, '_marker_last_date', return_value=date):
            return labs.suggest_tests()

    def test_no_source_loan_and_no_false_low_or_recent(self):
        today = datetime.date.today().isoformat()
        for name in ('suggest', 'why', 'condition'):
            rule = supported()
            del rule[name + '_basis']
            r = self.engine(rule, today)
            row = r['suggestions'][0]
            self.assertEqual('withheld', row['proposal_status'])
            self.assertNotIn('Synthetic test', row['suggest'])
            self.assertIsNone(row['priority'])
            self.assertIsNone(row['specialist'])
            self.assertFalse(row.get('done_recently'))
            self.assertEqual(today, row['last_measured'])
            self.assertEqual(1, r['unresolved_count'])
            self.assertEqual(1, r['count'])

    def test_a_supported_proposal_is_not_erased(self):
        r = self.engine(supported(), datetime.date.today().isoformat())
        row = r['suggestions'][0]
        self.assertEqual('held', row['proposal_status'])
        self.assertEqual('Synthetic test', row['suggest'])
        self.assertTrue(row['done_recently'])
        self.assertEqual(0, r['count'])
        self.assertEqual(0, r['unresolved_count'])
        self.assertIn('recheck fixture mechanism', fmt.tests_report(r))

    def test_referral_priority_and_interval_do_not_borrow_selection_support(self):
        for name in ('priority', 'specialist', 'recheck'):
            rule = supported()
            del rule[name + '_basis']
            row = self.engine(rule, datetime.date.today().isoformat())['suggestions'][0]
            self.assertEqual('held', row['proposal_status'])
            field = 'recheck_months' if name == 'recheck' else name
            self.assertIsNone(row.get(field))
            if name == 'recheck':
                self.assertFalse(row.get('done_recently'))
            self.assertIn(name, [g['claim'] for g in row['proposal_gaps']])

    def test_no_default_interval_and_no_malformed_interval(self):
        for months in (None, True, 0, -1, '3', float('inf'), 0.5):
            rule = supported()
            rule['recheck_months'] = months
            row = self.engine(rule, datetime.date.today().isoformat())['suggestions'][0]
            self.assertFalse(row.get('done_recently'))
            self.assertNotIn('recheck_months', row)

    def test_scope_and_sentence_are_required(self):
        for scope in (None, False, {}, {'status': 'held', 'context': ''},
                      {'status': 'held', 'context': {'en': 'Only English'}},
                      {'status': 'candidate', 'context': 'Unreviewed'}):
            rule = supported()
            rule['applicability'] = scope
            self.assertEqual('withheld', guard_test_proposal(rule)['proposal_status'])
        rule = supported()
        rule['applicability']['context'] = {'en': 'Fixture', 'ru': 'Fixture'}
        self.assertEqual('held', guard_test_proposal(rule)['proposal_status'])
        for text in ('', None, {'en': 'Only English'}):
            rule['why'] = text
            self.assertEqual('withheld', guard_test_proposal(rule)['proposal_status'])

    def test_all_covered_markers_not_one_latest_marker_establish_recent(self):
        today = datetime.date.today().isoformat()
        old = '2001-01-01'
        for b, expected in ((None, None), (old, old), (today, today), ('unreadable', 'unreadable')):
            markers = {'a': {'series': [{'date': today}]}}
            if b:
                markers['b'] = {'series': [{'date': b}]}
            with mock.patch.object(core, 'labs', return_value={'markers': markers}):
                self.assertEqual(expected, labs._marker_last_date(['a', 'b']))
                self.assertIsNone(labs._marker_last_date([]))

    def test_held_and_nonfiring_rules_do_not_become_orders(self):
        rule = supported()
        rule['held'] = True
        self.assertEqual([], self.engine(rule)['suggestions'])
        del rule['held']
        with mock.patch.object(core, 'test_rules', return_value={'rules': [rule]}), \
                mock.patch.object(labs, '_eval_condition', return_value=False):
            self.assertIn('does not establish', fmt.tests_report(labs.suggest_tests()))

    def test_support_and_refusals_reach_text_and_aggregations_in_both_languages(self):
        for language in ('en', 'ru'):
            with mock.patch.object(i18n, 'lang', return_value=language):
                for held in (True, False):
                    rule = supported()
                    if not held:
                        del rule['condition_basis']
                    r = self.engine(rule)
                    row = r['suggestions'][0]
                    texts = [fmt.tests_report(r), fmt.overview_report({
                        'markers_total': 0, 'abnormal_count': 0, 'pending_suggestions': [row],
                        'suggestions_count': 1, 'genome': {}, 'disclaimer': 'Fixture'}),
                        fmt.second_opinion_report({'suggestions': [row], 'disclaimer': 'Fixture'})]
                    from scholion.format_system import _test_row
                    texts.append(_test_row(row))
                    for text in texts:
                        self.assertIn('suggest fixture mechanism', text)
                        self.assertIn('PMID: 99999999', text)
                        self.assertIn(row['suggest'], text)
                        if not held:
                            self.assertIn(row['proposal_basis']['condition']['reason'], text)
                self.assertEqual('', test_basis_text({}))

    def test_rule_errors_stay_visible(self):
        with mock.patch.object(core, 'test_rules', return_value={'rules': [supported()]}), \
                mock.patch.object(labs, '_eval_condition', side_effect=ValueError('fixture error')):
            r = labs.suggest_tests()
        self.assertEqual(1, r['unresolved_count'])
        self.assertIn('fixture error', fmt.tests_report(r))
