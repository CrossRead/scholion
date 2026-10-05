"""Own target support, not a borrowed citation or a population guessed by default."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, format as fmt, i18n, store
from scholion.engine import goals
from scholion.goal_basis import guard_goal_candidate, goal_basis_text


def supported_entry():
    return {'unit': 'U/L', 'value': 20, 'comparator': '<',
            'source': {'body': 'Synthetic society', 'document': 'Synthetic document',
                       'year': 2026, 'url': 'https://example.invalid', 'quote': 'Synthetic quote'},
            'note': 'Synthetic note',
            'target_basis': {'source': 'PMID: 99999999', 'mechanism': 'Synthetic target mechanism'},
            'applicability': {'status': 'held', 'context': 'Synthetic scope only'}}


class TestIndependentGoalSupport(unittest.TestCase):
    def setUp(self):
        self.previous = i18n.lang()
        self.addCleanup(i18n.set_lang, self.previous)

    def run_goal(self, entry, value=35, censored=None):
        data = {'markers': {'alt': {'name': 'ALT', 'unit': 'U/L', 'ref_high': 33,
                                    'series': [{'date': '2026-01-01', 'value': value, 'censored': censored}]}}}
        with mock.patch.object(core, 'labs', return_value=data), \
                mock.patch.object(core, 'goal_targets', return_value={'targets': {'alt': entry}}):
            return goals.suggest_goal_targets(['alt'])

    def test_supported_target_and_existing_comparison_are_kept(self):
        r = self.run_goal(supported_entry())
        (p,) = r['proposals']
        self.assertEqual({'comparator': '<', 'value': 20}, p['target'])
        (c,) = [c for c in p['candidates'] if c['source'] == 'guideline']
        self.assertEqual('held', c['proposal_status'])
        self.assertIsNone(c['quote'])
        self.assertIsNone(c['note'])
        self.assertEqual('Synthetic society', c['citation']['body'])
        met = self.run_goal(supported_entry(), 19)
        self.assertFalse(met['proposals'])
        self.assertEqual(20, met['already_met'][0]['met'][0]['value'])
        self.assertIn('Synthetic target mechanism', fmt.goal_suggest_report(met))

    def test_censored_result_does_not_establish_target_met(self):
        r = self.run_goal(supported_entry(), 19, censored='>')
        self.assertFalse(r['proposals'])
        self.assertFalse(r['already_met'])
        self.assertEqual('censored', r['skipped'][0]['reason'])

    def test_target_quote_and_note_never_borrow_one_anothers_support(self):
        for field in ('source', 'mechanism'):
            spec = supported_entry()
            del spec['target_basis'][field]
            r = self.run_goal(spec)
            self.assertFalse(r['proposals'])
            self.assertEqual(1, r['unresolved_count'])
            self.assertEqual('target_basis', r['skipped'][0]['reason'])
        spec = supported_entry()
        spec['quote_basis'] = {'source': 'PMID: 99999998', 'mechanism': 'Independent quote mechanism'}
        c = self.run_goal(spec)['proposals'][0]['candidates'][0]
        self.assertEqual('Synthetic quote', c['quote'])
        self.assertIsNone(c['note'])

    def test_an_assumed_risk_or_unconfirmed_diagnosis_does_not_select_a_target(self):
        for change in ({'applies_when': {'has_condition': 'synthetic condition'}},
                       {'by_category': [{'category': 'moderate', 'value': 20, 'comparator': '<'}],
                        'default_category': 'moderate', 'depends_on': 'synthetic risk'}):
            spec = supported_entry()
            spec.update(change)
            r = self.run_goal(spec)
            self.assertFalse(r['proposals'])
            c = r['skipped'][0]['candidates'][0]
            self.assertIn('individual_applicability', c['target_basis']['missing'])
            self.assertIsNone(c['value'])
            self.assertEqual(20, c['catalogue_comparison']['value'])

    def test_units_finite_value_comparator_and_scope_are_not_guessed(self):
        for change in ({'unit': '%'}, {'value': True}, {'value': float('nan')},
                       {'value': float('inf')}, {'comparator': '='}, {'applicability': False},
                       {'applicability': {'status': 'held', 'context': {'en': 'Only English'}}}):
            spec = supported_entry()
            spec.update(change)
            self.assertFalse(self.run_goal(spec)['proposals'])
        spec['applicability'] = {'status': 'held', 'context': {'en': 'Fixture', 'ru': 'Fixture'}}
        self.assertTrue(self.run_goal(spec)['proposals'])

    def test_a_no_target_sentence_needs_its_own_support_too(self):
        spec = supported_entry()
        spec['no_target'] = True
        c = self.run_goal(spec)['skipped'][0]['candidates'][0]
        self.assertTrue(c['no_target'])
        spec.pop('target_basis')
        c = self.run_goal(spec)['skipped'][0]['candidates'][0]
        self.assertFalse(c['no_target'])
        self.assertTrue(c['catalogue_comparison']['no_target'])
        self.assertEqual('withheld', c['proposal_status'])

    def test_raw_catalogue_is_not_mutated_and_support_reaches_both_languages(self):
        spec = supported_entry()
        saved = copy.deepcopy(spec)
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            r = self.run_goal(spec)
            text = fmt.goal_suggest_report(r)
            self.assertIn('PMID: 99999999', text)
            self.assertIn('Synthetic target mechanism', text)
            self.assertNotIn('Synthetic quote', text)
            self.assertNotIn('Synthetic note', text)
            self.assertEqual(saved, spec)
            absent = dict(spec, target_basis=None)
            r = self.run_goal(absent)
            c = r['skipped'][0]['candidates'][0]
            self.assertIn(c['target_basis']['reason'], fmt.goal_suggest_report(r))
            self.assertNotIn('⟦', fmt.goal_suggest_report(r))
        self.assertEqual('', goal_basis_text({}))
        self.assertTrue(goal_basis_text({'proposal_status': 'observation'}))
        raw = {'source': 'guideline', 'value': 20, 'comparator': '<', 'unit': 'U/L', 'observation_unit': 'U/L'}
        self.assertEqual('withheld', guard_goal_candidate({}, raw)['proposal_status'])

    def test_supported_write_keeps_support_and_does_not_overwrite_a_persons_goal(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        profile = Path(tmp.name).resolve()
        self.addCleanup(support.pin_profile(profile))
        result = self.run_goal(supported_entry())
        written = store.write_goal_targets(result['proposals'])
        self.assertEqual(['ALT'], written['added'])
        path = profile / 'health_goals.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        entry = next(t for t in data['targets'] if t['label'] == 'ALT')
        self.assertEqual('PMID: 99999999', entry['_from']['target_basis']['source'])
        entry['target'] = '<123'
        path.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(['ALT'], store.write_goal_targets(result['proposals'])['kept'])
        after = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual('<123', next(t for t in after['targets'] if t['label'] == 'ALT')['target'])
