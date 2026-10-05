"""C17: independent dose, longevity and penetrance claims, not borrowed citations.

Synthetic identifiers test the gate, not the truth of a clinical assertion.
Observations, source tokens and calculation methods remain visible on refusal.
"""
from __future__ import annotations

import copy
import unittest
from unittest import mock

import support  # noqa: F401 -- synthetic environment
from scholion import core, engine, format as fmt, genome, i18n, phenoage
from scholion.clinical_claims import basis_lines, guard_dose_context, guard_fields
from scholion.format_prescription import _rx_dose_lines
from scholion.engine import genomics, pgx
from test_every_face_carries_the_same_positions_and_levels import _Read

BASIS = {'source': 'PMID: 99999999', 'mechanism': {'en': 'Synthetic mechanism', 'ru': 'Синтетический механизм'}}


class TestIndependentSentences(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, getattr(i18n._state, 'current', None))

    def test_no_neighbour_or_parent_can_supply_a_claim_basis(self):
        row = {'value': 25, 'date': '2026-01-01', 'claim': 'Synthetic sentence',
               'action': 'Synthetic action', 'items': ['Synthetic list'], 'empty': '', 'absent': None}
        raw = copy.deepcopy(row)
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            result = guard_fields({'source': 'PMID: 99999999', 'mechanism': BASIS['mechanism'],
                                   'claim_basis': BASIS}, row, ('claim', 'action', 'items', 'empty', 'absent'))
            self.assertEqual('Synthetic sentence', result['claim'])
            self.assertIsNone(result['action'])
            self.assertEqual([], result['items'])
            self.assertEqual(2, result['unresolved_count'])
            self.assertEqual((25, '2026-01-01'), (result['value'], result['date']))
            text = '\n'.join(basis_lines(result))
            self.assertIn('PMID: 99999999', text)
            self.assertIn(i18n.t('conclusion.withheld', missing=', '.join(
                i18n.t('conclusion.missing.' + k) for k in ('source_identifier', 'mechanism'))), text)
            self.assertNotIn('⟦', text)
        self.assertEqual(raw, row)
        own = guard_fields({'claim_bases': {'action': BASIS}}, row, ('action',))
        self.assertEqual('Synthetic action', own['action'])
        self.assertEqual(0, own['unresolved_count'])
        for invalid in ({'source': BASIS['source']}, {'mechanism': BASIS['mechanism']},
                        {'source': BASIS['source'], 'mechanism': {'en': 'Only one language'}}):
            self.assertIsNone(guard_fields({'claim_basis': invalid}, row, ('claim',))['claim'])

    def test_dose_effect_form_alternative_and_action_are_independent(self):
        spec = {'forms_basis': BASIS, 'alternatives_basis': BASIS,
                'critical': [{'claim_basis': BASIS}], 'alternatives': [{'name_basis': BASIS}]}
        row = {'matched': True, 'forms': 'Synthetic form', 'verdict_rule': 'Unsupported action',
               'alternatives': [{'name': 'Synthetic alternative', 'metabolic': 'Unsupported effect'}],
               'items': [{'claim': 'Synthetic claim', 'effect_size': 'Unsupported number',
                          'patient': [{'value': 25, 'date': '2026-01-01', 'measured': True}]}]}
        result = guard_dose_context(spec, row)
        self.assertEqual('Synthetic form', result['forms'])
        self.assertIsNone(result['verdict_rule'])
        self.assertEqual('Synthetic claim', result['items'][0]['claim'])
        self.assertIsNone(result['items'][0]['effect_size'])
        self.assertEqual(row['items'][0]['patient'], result['items'][0]['patient'])
        self.assertEqual('Synthetic alternative', result['alternatives'][0]['name'])
        self.assertIsNone(result['alternatives'][0]['metabolic'])
        self.assertEqual(3, result['unresolved_count'])
        result = guard_dose_context({}, {**row, 'alternatives': []})
        self.assertEqual([], result['alternatives'])

    def test_catalogue_verdict_does_not_licence_its_action_or_population_sentence(self):
        data = {'known': [{'rsid': 'rs99999999', 'gene': 'SYN1', 'genotype': 'AG', 'copies_favorable': 1,
                            'verdict': 'plus', 'label': 'Unsupported effect', 'action': 'Unsupported action',
                            'note': 'Unsupported stored clinical note'}],
                'apoe': {'epsilon': 'ε3/ε3', 'note': 'Unsupported APOE risk sentence'}}
        direction = {'verdict_by_copies': {'1': 'plus'}, 'verdict_basis': BASIS,
                     'action': {'en': 'Unsupported action', 'ru': 'Необоснованное действие'},
                     'label': {'en': 'Unsupported effect', 'ru': 'Необоснованный эффект'}}
        with mock.patch.object(core, 'longevity_data', return_value=data), \
             mock.patch.object(core, '_read_knowledge', return_value={'directions': {'rs99999999': direction}}):
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                result = genomics.longevity_findings()
                row = result['known'][0]
                self.assertEqual('AG', row['genotype'])
                self.assertTrue(row['verdict_label'])
                self.assertIsNone(row['action'])
                self.assertIsNone(row['note'])
                self.assertIsNone(result['apoe']['note'])
                text = fmt.longevity_report(result)
                self.assertNotIn('Unsupported', text)
                self.assertIn('PMID: 99999999', text)
                self.assertIn('AG', text)
        self.assertEqual('Unsupported stored clinical note', data['known'][0]['note'])

    def test_penetrance_title_and_body_require_their_own_support(self):
        principle = {'id': 'synthetic', 'source': BASIS['source'], 'title': 'Unsupported title',
                     'text': 'Supported body', 'text_basis': BASIS}
        with mock.patch.object(genome, 'penetrance_notes', return_value={'principles': [principle]}):
            result = genomics._penetrance_block()
        self.assertEqual('product_boundary', result['output_kind'])
        self.assertIsNone(result['principles'][0]['title'])
        self.assertEqual('Supported body', result['principles'][0]['text'])
        self.assertEqual('ClinVar review_status: practice_guideline', genome._review_confidence('practice_guideline'))
        self.assertIsNone(genome._review_confidence(''))


class TestRemainingOutputOnTheSyntheticProfile(_Read):
    def setUp(self):
        super().setUp()
        self.addCleanup(i18n.set_lang, getattr(i18n._state, 'current', None))

    def test_dose_refusal_reaches_the_decision_and_preserves_observations(self):
        spec = {'entries': {'synthetic': {'forms': 'Unsupported synthetic form',
            'critical': [{'claim': 'Unsupported synthetic claim', 'source': BASIS['source'],
                          'compare_marker': ['alt', 'unmeasured-synthetic']}], 'verdict_rule': 'Unsupported action'}}}
        with mock.patch.object(core, 'dose_evidence', return_value=spec):
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                dc = pgx._dose_context('synthetic')
                self.assertTrue(dc['matched'])
                self.assertGreater(dc['unresolved_count'], 0)
                self.assertIsNone(dc['forms'])
                patient = dc['items'][0]['patient'][0]
                self.assertTrue(patient['measured'])
                self.assertTrue(patient['date'])
                self.assertEqual('labs.json:alt', patient['source'])
                self.assertFalse(dc['items'][0]['patient'][1]['measured'])
                text = '\n'.join(_rx_dose_lines({'dose_context': dc}))
                self.assertNotIn('Unsupported', text)
                self.assertIn(patient['date'], text)
                self.assertIn('labs.json:alt', text)
                result = engine.check_new_prescription('synthetic')
                self.assertNotEqual('low', result['overall'])
                self.assertTrue(any(x.get('what') == 'dose_basis' for x in result['unresolved']))
        self.assertFalse(pgx._dose_context('does-not-match-any-dose')['matched'])

    def test_bmi_is_a_calculation_not_an_unsupported_clinical_grade(self):
        bmi = engine.metrics_summary()['bmi']
        self.assertIsNotNone(bmi['value'])
        self.assertIsNone(bmi['category'])
        self.assertEqual('unknown', bmi['flag'])
        self.assertEqual('derived_measurement', bmi['output_kind'])
        self.assertTrue(bmi['method'])
        self.assertEqual('incomplete', bmi['clinical_basis']['category']['status'])

    def test_wearable_indices_are_labelled_as_display_comparisons_on_both_languages(self):
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            result = engine.lifestyle()
            self.assertEqual('display_index', result['output_kind'])
            self.assertIn(i18n.t('clinical.display_limit'), fmt.lifestyle_report(result))
            for row in result['metrics']:
                self.assertEqual('display_reference_comparison', row.get('output_kind'))
                if row.get('clinical_basis'):
                    self.assertIsNone(row['why'])

    def test_missing_or_censored_lpa_bound_does_not_make_a_green_grade(self):
        for point, marker in (({'value': 50, 'censored': '<'}, {'ref_high': 75}),
                              ({'value': 130, 'ref_high': 200, 'ref_origin': 'form'}, {'ref_high': 75})):
            data = {'markers': {'lpa': {**marker, 'name': 'Lp(a)', 'unit': 'nmol/L',
                      'series': [{**point, 'date': '2026-01-01'}]}}}
            with mock.patch.object(core, 'labs', return_value=data):
                core.reset_cache()
                measured = engine.lipid_genetics()['lpa']['measured']
                self.assertEqual(point['value'], measured['value'])
                if point.get('censored'):
                    self.assertIsNone(measured['above'])
                    self.assertEqual('<', measured['censored'])
                else:
                    self.assertEqual(200, measured['ref_high'])
                    self.assertFalse(measured['above'])
        core.reset_cache()

    def test_population_model_result_has_its_method_and_is_not_personal_prognosis(self):
        values = {'albumin': 40, 'creatinine': 70, 'glucose': 5, 'crp': 1, 'lymph': 30,
                  'mcv': 90, 'rdw': 13, 'alp': 70, 'wbc': 6}
        with mock.patch.object(phenoage, 'panel_months', return_value=['2026-01']), \
             mock.patch.object(phenoage, '_selected_draw', return_value='2026-01-15'), \
             mock.patch.object(phenoage, 'collect_panel', return_value=(values, [], {k: k for k in values})):
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                result = phenoage.compute_panel('2026-01', age=40)
                self.assertTrue(result['ok'])
                self.assertEqual('population_model_calculation', result['output_kind'])
                text = phenoage.format_result(result)
                self.assertIn('DOI: 10.18632/aging.101414', text)
                self.assertIn(i18n.t('clinical.model_limit'), text)


if __name__ == '__main__':
    unittest.main()
