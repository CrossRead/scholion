"""An unsupported threshold is unresolved, not a negative safety finding.

Clinical curation is not certified by these structural checks. The positive
catalogue regression retains the qualified urgent warning, strict comparison
and point-specific upper bound of the identified EAS rule.
"""
import copy
import math
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, i18n
from scholion.engine import labs
from scholion.format_primitives import _decision_suffix
from scholion.threshold_basis import compare_threshold, guard_threshold, upper_bound_known


def synthetic_rule():
    return {'value': 54.0, 'side': 'high', 'label': 'SYNTHETIC_THRESHOLD', 'action': 'SYNTHETIC_ACTION',
            'threshold_basis': {'source': 'Synthetic PMID:1', 'mechanism': 'THRESHOLD_MECHANISM'},
            'action_basis': {'source': 'Synthetic PMID:2', 'mechanism': 'ACTION_MECHANISM'},
            'applicability': {'status': 'held', 'context': 'Synthetic test only'}}


class TestIndependentThresholdBasis(unittest.TestCase):
    def setUp(self):
        self.previous = i18n.lang()
        self.addCleanup(i18n.set_lang, self.previous)

    def rows(self, rule, value=55, **context):
        with mock.patch.object(core, 'clinical_thresholds', return_value={'markers': {'hct': [rule]}}):
            return labs._decision_limits('hct', value, **context)

    def test_threshold_and_action_do_not_borrow_support(self):
        for field in ('threshold_basis', 'action_basis'):
            rule = synthetic_rule()
            rule.pop(field)
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                row = self.rows(rule)[0]
                text = _decision_suffix({'decisions': [row]}, context=True)
                self.assertIsNone(row['action'])
                self.assertNotIn('SYNTHETIC_ACTION', text)
                if field == 'threshold_basis':
                    self.assertIsNone(row['crossed'])
                    self.assertIsNone(row['label'])
                    self.assertTrue(row['catalogue_comparison']['crossed'])
                    self.assertNotIn('SYNTHETIC_THRESHOLD', text)
                    self.assertNotIn('not reached', text)
                else:
                    self.assertTrue(row['crossed'])
                    self.assertIn('SYNTHETIC_THRESHOLD', text)
                    self.assertIn('THRESHOLD_MECHANISM', text)

    def test_a_supported_action_keeps_its_own_mechanism(self):
        original = synthetic_rule()
        saved = copy.deepcopy(original)
        row = self.rows(original)[0]
        text = _decision_suffix({'decisions': [row]}, context=True)
        self.assertIn('ACTION_MECHANISM', text)
        self.assertIn('Synthetic PMID:2', text)
        self.assertEqual(saved, original)
        below = self.rows(original, 40)[0]
        self.assertFalse(below['crossed'])
        self.assertIsNone(below['action'])

    def test_context_gaps_do_not_give_a_negative_verdict(self):
        for scope in (None, False, {}, {'status': 'unheld', 'context': 'context'},
                      {'status': 'held', 'context': 123}, {'status': 'held', 'context': {'en': 'only one'}}):
            rule = synthetic_rule()
            rule['applicability'] = scope
            row = self.rows(rule, 40)[0]
            self.assertIsNone(row['crossed'])
            self.assertIn('clinical_scope', row['threshold_basis']['missing'])
        rule['applicability'] = {'status': 'held', 'context': {'en': 'Synthetic', 'ru': 'Synthetic'}}
        self.assertTrue(self.rows(rule)[0]['crossed'])

    def test_nonfinite_censored_and_absent_bound_are_not_negative(self):
        for value in (None, 'bad', True, math.nan, math.inf):
            row = self.rows(synthetic_rule(), value)[0]
            self.assertIsNone(row['crossed'])
            self.assertEqual('not_comparable', row['why'])
        row = self.rows(synthetic_rule(), 40, censored='<')[0]
        self.assertIsNone(row['crossed'])
        self.assertEqual('censored', row['why'])
        rule = synthetic_rule()
        rule.pop('value')
        rule['multiple_of_ref_high'] = 10
        with mock.patch.object(core, 'lab_markers', return_value={'markers': {}}):
            row = self.rows(rule)[0]
        self.assertIsNone(row['crossed'])
        self.assertIn('reference_high', row['threshold_basis']['missing'])

    def test_supported_urgent_warning_uses_the_actual_bound_and_strict_above(self):
        for high in (170, 190, 250):
            below = labs._decision_limits('ck', high * 10, {'statin'}, reference_high=high)
            above = labs._decision_limits('ck', high * 10 + 1, {'statin'}, reference_high=high)
            boundary = next(r for r in below if r.get('multiple_of_ref_high') == 10)
            urgent = next(r for r in above if r.get('multiple_of_ref_high') == 10)
            self.assertFalse(boundary['crossed'])
            self.assertTrue(urgent['crossed'])
            self.assertEqual(high * 10, urgent['value'])
            self.assertIn('PMID:25694464', urgent['threshold_basis']['source'])
            self.assertIn('clinician', urgent['action'])
            self.assertIn('secondary cause', urgent['action'])
            self.assertNotIn('immediate withdrawal', urgent['label'])
            text = _decision_suffix({'decisions': above})
            self.assertIn('❗', text)
            self.assertIn('rhabdomyolysis', text)
        self.assertEqual([], labs._decision_limits('ck', 9000, set(), reference_high=190))

    def test_a_missing_action_is_not_a_proposal(self):
        rule = synthetic_rule()
        rule.pop('action')
        row = guard_threshold(rule, {'crossed': True, 'reference_high_known': True})
        self.assertIsNone(row['action'])
        self.assertIsNone(row['action_basis'])

    def test_boundary_arithmetic_has_no_clinical_side_effect(self):
        for side, comparison, value, crossed in (('high', None, 54, True), ('low', None, 54, True),
                                                 ('high', 'gt', 54, False), ('low', 'lt', 53, True)):
            rule = {'value': 54, 'side': side, 'comparison': comparison}
            self.assertIs(crossed, compare_threshold(value, rule)['crossed'])
        self.assertIsNone(compare_threshold(1, {'value': 0, 'side': 'high'})['distance_pct'])
        for rule in ({'value': True, 'side': 'high'}, {'value': math.inf, 'side': 'high'},
                     {'value': 1, 'side': 'wrong'}, {'value': 1, 'side': 'low', 'comparison': 'gt'},
                     {'value': 1, 'side': 'high', 'comparison': 'invalid'}):
            self.assertIsNone(compare_threshold(2, rule)['crossed'])
        for bound in (None, True, '170', 0, -1, math.inf, math.nan):
            self.assertFalse(upper_bound_known(bound))
            if bound is not None:
                row = labs._threshold_value('ck', {'multiple_of_ref_high': 10}, bound)
                self.assertIsNone(row['value'])


if __name__ == '__main__':
    unittest.main()
