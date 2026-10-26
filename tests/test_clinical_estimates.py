"""The supported estimates share one read-only panel through every entry point."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import support
from scholion import clinical_estimates as ce, core, store


class TestClinicalScope(unittest.TestCase):
    def test_registered_egfr_spelling_still_has_its_unchanged_measurement_value(self):
        spec = core.lab_markers()['markers']['egfr_ckdepi']
        result = core.convert_to_canonical(spec, 'мл/мин/1.73 м²', 106.6)
        self.assertTrue(result['ok'])
        self.assertEqual(result['value'], 106.6)
        self.assertFalse(core.convert_to_canonical(spec, 'mg/dL', 106.6)['ok'])

    def test_removed_models_and_questionnaire_are_not_offered(self):
        result = ce.panel()
        self.assertEqual([r['key'] for r in result['estimates']], ['fib4', 'phenoage'])
        self.assertEqual(result['context_fields'], [])
        self.assertEqual(result['context_errors'], [])

    def test_remaining_estimates_keep_computed_missing_and_stale_results_distinct(self):
        from scholion import phenoage
        fib = {'sources': [{'url': 'https://example.org/synthetic-method'}], 'value': 0.5,
               'status': 'computed', 'date': date.today().isoformat(), 'inputs': [],
               'missing': [], 'issues': [], 'population': 'Synthetic', 'endpoint': 'Synthetic',
               'horizon': 'Synthetic', 'interpretation': {'reason': 'Synthetic method scope'}}
        pa = {'ok': True, 'phenoage': 40.0, 'draw': date.today().isoformat(),
              'values': {}, 'labs_keys': {}}
        with patch('scholion.engine.validated.fib4', return_value=fib), \
                patch.object(phenoage, 'compute_panel', return_value=pa) as compute:
            rows = ce.panel()['estimates']
            self.assertTrue(all(r['status'] == 'computed' for r in rows))
            self.assertEqual([0.5, 40.0], [r['value'] for r in rows])
            compute.assert_called_once_with('latest', track=False)
            fib['date'] = (date.today() - timedelta(days=366)).isoformat()
            pa.update(ok=False, missing=['Synthetic missing input'], error='draw_unknown')
            rows = ce.panel()['estimates']
            self.assertEqual(['invalid', 'invalid'], [r['status'] for r in rows])
            self.assertTrue(all(r['value'] is None for r in rows))
            self.assertTrue(rows[0]['issues'])
            self.assertEqual([], fib['issues'])
            self.assertEqual(['Synthetic missing input'], rows[1]['missing'])
            pa['error'] = 'missing'
            self.assertEqual('missing', ce.panel()['estimates'][1]['status'])

    def test_retired_questionnaire_write_preserves_all_existing_profile_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'metrics.json'
            original = {'profile': {'height_cm': 180, 'clinical_context': {'source': 'Synthetic historical note'}},
                        'metrics': {'weight': {'series': [{'date': '2026-01-01', 'value': 80}]}}}
            path.write_text(json.dumps(original), encoding='utf-8'); before = path.read_bytes()
            restore = support.pin_profile(Path(folder).resolve())
            try:
                result = store.update_metric_profile({'clinical_context': {}})
            finally:
                restore()
            self.assertFalse(result['ok'])
            self.assertEqual(before, path.read_bytes())

    def test_missing_supported_inputs_have_readable_names_in_both_languages(self):
        from scholion import i18n, phenoage
        from scholion.format_clinical import report
        previous = i18n.lang()
        self.addCleanup(i18n.set_lang, previous)
        fib = {'sources': [{'url': 'https://example.org/synthetic-method'}], 'value': None,
               'status': 'missing', 'date': date.today().isoformat(),
               'inputs': [{'key': 'ast', 'value': 20, 'unit': 'U/L',
                           'date': date.today().isoformat(),
                           'source': {'file': 'Synthetic partial draw'}}],
               'missing': ['alt', 'platelets', 'age'], 'issues': [],
               'population': 'Synthetic', 'endpoint': 'Synthetic', 'horizon': 'Synthetic',
               'interpretation': {'reason': None}}
        missing = ['albumin', 'creatinine', 'glucose', 'crp', 'lymph', 'mcv', 'rdw', 'alp', 'wbc']
        pa = {'ok': False, 'error': 'incomplete_panel', 'missing': missing}
        with patch('scholion.engine.validated.fib4', return_value=fib), \
                patch.object(phenoage, 'compute_panel', return_value=pa):
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                data = ce.panel()
                text = report(data)
                self.assertNotIn('⟦', text)
                self.assertNotIn('clinical.field.', text)
                self.assertIn('20 U/L', text)
                self.assertIn('Synthetic partial draw', text)
                for key in fib['missing'] + missing:
                    self.assertIn(i18n.t('clinical.field.' + key), text)
                self.assertTrue(all(row['value'] is None for row in data['estimates']))
                self.assertTrue(all(row['status'] == 'missing' for row in data['estimates']))


class TestClinicalSurfaces(unittest.TestCase):
    def test_ouroboros_and_mcp_use_the_same_methods_in_both_languages(self):
        from scholion import i18n, mcp_server, ouroboros_tools as ot
        tools={entry.name:entry for entry in ot.get_tools()}
        ot.unpin_session();self.addCleanup(ot.unpin_session)
        previous=i18n.lang();self.addCleanup(i18n.set_lang,previous)
        for language in ('en','ru'):
            i18n.set_lang(language)
            expected=ce.panel()
            direct=tools['sch_system'].handler(None,key='clinical_estimates',register='clinician')
            remote=mcp_server.call_tool('sch_system',{'key':'clinical_estimates','register':'clinician'})
            self.assertFalse(remote['isError'],remote)
            text=remote['content'][0]['text']
            for row in expected['estimates']:
                self.assertIn(row['name'],direct)
                self.assertIn(row['name'],text)
            self.assertNotIn('FRAX',direct.upper());self.assertNotIn('FRAX',text.upper())
            self.assertNotIn('⟦',text)

    def test_shared_supported_results_without_writes_or_network(self):
        from scholion import engine
        from scholion.format_system import system_report
        with patch.object(core,'write_json',side_effect=AssertionError('read-only')):
            result=engine.system('clinical_estimates','clinician')
        self.assertEqual([r['key'] for r in result['estimates']],['fib4','phenoage'])
        self.assertTrue(result['clinical_estimates'])
        self.assertNotIn('frax', [r['key'] for r in result['estimates']])
        self.assertNotIn('⟦',system_report(result))
        self.assertFalse(any(r.get('score') is not None for r in result['estimates']))
