"""Panel framing does not duplicate results or turn gene knowledge into disease."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import support
from scholion import clinical_estimates, i18n
from scholion import core, engine
from scholion.engine.thematic_panels import thematic_reference
from scholion.panel_reference import gene_reference_context, reference_lines


class TestClinicalAndGeneFraming(unittest.TestCase):
    def test_named_clinical_metrics_change_language_without_rewriting_measurements(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        data = {'profile': {}, 'metrics': {key: {'name': key, 'unit': unit,
                'series': [{'date': '2026-10-01', 'value': value}]}
                for key, unit, value in [('systolic_bp', 'mm[Hg]', 120), ('waist_cm', 'cm', 90)]}}
        with patch.object(core, 'metrics_json', return_value=data):
            for language in ('ru', 'en'):
                i18n.set_lang(language)
                result = engine.metrics_summary()
                lifestyle = {r['key']:r for r in engine.lifestyle()['metrics']}
                for key in data['metrics']:
                    self.assertEqual(lifestyle[key]['label'],i18n.t('clinical.metric.'+key))
                rows = {row['key']: row for row in result['metrics']}
                for key in data['metrics']:
                    self.assertEqual(rows[key]['name'], i18n.t('clinical.metric.' + key))
                    self.assertEqual(data['metrics'][key]['name'], key)

    def test_each_clinical_result_has_one_detail_card_and_an_appropriate_limit(self):
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        start = page.index('function renderClinicalPanel(')
        function = page[start:page.index('\n}\n', start)]
        self.assertNotIn('clinicalSummaryHTML(data)', function)
        self.addCleanup(i18n.set_lang, i18n.lang())
        for language in ('ru', 'en'):
            i18n.set_lang(language)
            result = clinical_estimates.panel()
            self.assertEqual(result['disclaimer'], i18n.t('clinical.panel_limit'))
            self.assertNotEqual(result['disclaimer'], i18n.t('clinical.model_limit'))

    def test_named_energy_disorders_are_gene_reference_only_on_both_surfaces(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        genes = {'ACADM', 'ACADVL', 'CPT1A', 'CPT2', 'SLC22A5',
                 'HADHA', 'HADHB', 'PDHA1', 'PDHB'}
        for language in ('ru', 'en'):
            i18n.set_lang(language)
            panel = thematic_reference('metabolic_genetics')
            rows = {g['gene']: g for g in panel['genes']}
            for gene in genes:
                context = gene_reference_context(gene, [])
                disease = context['disease_context']
                self.assertEqual(disease['scope'], 'gene_disease_reference')
                self.assertFalse(disease['personal_diagnosis'])
                self.assertTrue(disease['source'].startswith('https://www.ncbi.nlm.nih.gov/books/'))
                self.assertIsNone(rows[gene]['level'])
                self.assertEqual(rows[gene]['reference_context']['disease_context'], disease)
                self.assertIn(disease['limitations'], reference_lines(rows[gene]))
            self.assertIsNone(rows['FTO']['reference_context']['disease_context'])
