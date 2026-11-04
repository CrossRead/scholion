"""A mitochondrial System joins existing facts without inventing a health score."""
from datetime import date
import importlib
from unittest import mock

from scholion import core, mitochondrial_system, mitochondria
from scholion.engine import system_panels
from scholion.i18n import set_lang
from tests.test_every_door_of_the_local_server_answers import _Live

L = importlib.import_module('scholion.engine.lifestyle')


class TestMitochondrialSystem(_Live):
    def setUp(self):
        core.reset_cache()
        self.addCleanup(core.reset_cache)
        self.addCleanup(set_lang, 'en')

    def test_system_is_present_across_registry_body_radar_and_api(self):
        self.assertIn('mitochondria', [d['key'] for d in system_panels.domains()])
        self.assertTrue(core._read_knowledge('body_map.json')['places']['mitochondria']['whole_body'])
        radar = L.health_radar()
        new = next(d for d in radar['domains'] if d['key'] == 'mitochondria')
        self.assertIsNone(new['score'])
        self.assertEqual('context', new['status'])
        self.assertEqual([], new['missing'])
        prior = [d['score'] for d in radar['domains'] if d['key'] != 'mitochondria' and d['score'] is not None]
        self.assertEqual(round(sum(prior)/len(prior)), radar['overall'])
        for language in ('en', 'ru'):
            set_lang(language)
            card = system_panels.system('mitochondria')
            self.assertEqual('ok', card['status'])
            self.assertEqual('context', card['labs']['status'])
            self.assertEqual([], card['labs']['missing'])
            self.assertEqual(365, card['dynamics']['period'])
            self.assertIn('mitochondrial_context', card)
            self.assertNotIn('mitochondrial_age', card)
        answer = self.json_of('/api/system?key=mitochondria')
        self.assertEqual('context', answer['labs']['status'])
        self.assertIn('mitochondrial_context', answer)

    def test_exact_allele_stale_source_and_normal_observation_do_not_become_diagnosis(self):
        day = date.today().isoformat()
        lab = {'key': 'glucose', 'name': 'Glucose', 'value': 5.0, 'unit': 'mmol/L',
               'date': day, 'flag': 'ok', 'abnormal': False, 'series': [{'date': day, 'value': 5.0}]}
        good = {'position': 3243, 'ref': 'A', 'alt': 'G', 'fraction': .04, 'status': 'supported'}
        wrong = {**good, 'alt': 'T'}
        for current, state in ((True, 'observations'), (False, 'unconfirmed')):
            core.reset_cache()
            with (mock.patch.object(mitochondria, 'report', return_value={
                    'current': current, 'result': {'reference': mitochondria.RCRS, 'variants': [good, wrong]}}),
                  mock.patch('scholion.engine.labs.analyze_labs', return_value={'markers': [lab]})):
                answer = mitochondrial_system.review()
            self.assertEqual(1, len(answer['pathways']))
            path = answer['pathways'][0]
            self.assertEqual(state, path['status'])
            self.assertFalse(path['causal'])
            self.assertEqual(1, len(path['contrary_observations']))
            self.assertEqual([], path['abnormal_observations'])
            self.assertEqual('normal' if current else 'unconfirmed', path['clinical_context'])
            self.assertEqual(5.0, path['observations'][0]['value'])
            self.assertEqual('labs.json', path['observations'][0]['record'])
            self.assertEqual(day, path['observations'][0]['series'][0]['date'])

    def test_unmeasured_variant_is_not_inferred_from_missing_row(self):
        with mock.patch.object(mitochondria, 'report', return_value={
                'current': True, 'result': {'variants': []}}):
            answer = mitochondrial_system.review()
        self.assertEqual([], answer['pathways'])
        self.assertNotIn('excluded_diseases', answer)

    def test_only_current_drugs_map_to_the_system(self):
        with mock.patch.object(core, 'active_medications', return_value=[{
                'name': 'Gentamicin', 'status': 'active', 'dose': ''}]):
            mapped = system_panels._medications_layer('mitochondria')
        self.assertEqual('Gentamicin', mapped['rows'][0]['name'])
        with mock.patch.object(core, 'active_medications', return_value=[]):
            core.reset_cache()
            self.assertEqual([], system_panels._medications_layer('mitochondria')['rows'])

    def test_shared_web_and_cli_render_context_without_a_score(self):
        from scholion import format_system
        card = system_panels.system('mitochondria')
        output = format_system.system_report(card)
        self.assertIn(card['mitochondrial_context']['message'], output)
        self.assertNotIn('None/100', output)
        self.assertNotIn('None / 100', output)
        listing = system_panels.systems()
        row = next(s for s in listing['systems'] if s['key'] == 'mitochondria')
        self.assertEqual('mitochondrial', row['genetics']['status'])
        self.assertIn('mitochondrial', format_system.systems_report(listing).lower())

    def test_old_or_censored_labs_and_uncertain_alleles_do_not_establish_a_match(self):
        day = date.today().isoformat()
        lab = {'key': 'hba1c', 'name': 'HbA1c', 'value': 7, 'unit': '%',
               'date': '2001-01-01', 'flag': 'high', 'abnormal': True,
               'display_recency': False, 'series': [{'date': '2001-01-01', 'value': 7}]}
        v = {'position': 3243, 'ref': 'A', 'alt': 'G', 'fraction': .04, 'status': 'supported'}
        for status, expected in [('supported', 'reference'), ('uncertain', 'unconfirmed')]:
            core.reset_cache()
            with (mock.patch.object(mitochondria, 'report', return_value={
                    'current': True, 'result': {'reference': mitochondria.RCRS, 'variants': [{**v, 'status': status}], 'created_at': day}}),
                  mock.patch('scholion.engine.labs.analyze_labs', return_value={'markers': [lab]})):
                path = mitochondrial_system.review()['pathways'][0]
            self.assertEqual(expected, path['clinical_context'])
            self.assertEqual([], path['observations'][0]['series'])
            self.assertEqual([], path['abnormal_observations'])
            self.assertEqual(day, path['provenance']['analyzed_at'])

    def test_another_reference_cannot_support_the_context(self):
        v = {'position': 3243, 'ref': 'A', 'alt': 'G', 'fraction': .04, 'status': 'supported'}
        with mock.patch.object(mitochondria, 'report', return_value={
                'current': True, 'result': {'reference': 'unknown', 'variants': [v]}}):
            answer = mitochondrial_system.review()
        self.assertEqual('unconfirmed', answer['pathways'][0]['status'])
