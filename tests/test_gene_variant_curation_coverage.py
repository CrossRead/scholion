"""Function annotations cannot silently become variant-effect curation."""
import unittest
from unittest.mock import patch

import support
from scholion import core, i18n
from scholion.curation_coverage import describe
from scholion.panel_reference import genome_context, reference_lines


class TestCurationCoverage(unittest.TestCase):
    def test_a_function_only_gene_is_not_counted_as_variant_effect_curated(self):
        result = describe('A2M', True)
        self.assertTrue(result['function_recorded'])
        self.assertFalse(result['variant_effect_curated'])
        self.assertEqual(result['links'], [])

    def test_a_registered_effect_has_a_specific_variant_outcome_and_source(self):
        result = describe('COMT', True)
        self.assertTrue(result['variant_effect_curated'])
        for link in result['links']:
            self.assertTrue(all(link[k] for k in ('gene', 'rsid', 'effect', 'direction', 'study_scope', 'sources', 'checked_on', 'limitations')))
            self.assertFalse(link['clinical_eligibility_upgrade'])
        self.assertGreaterEqual(result['link_count'], int(result['variant_effect_curated']))

    def test_a_stale_source_witness_withdraws_the_coverage(self):
        with patch('scholion.knowledge_provenance.record', return_value={'record_digest': 'changed'}):
            result = describe('COMT', True)
        self.assertFalse(result['variant_effect_curated'])
        self.assertEqual(result['link_count'], 0)

    def test_bibliography_without_an_effect_does_not_qualify(self):
        with patch.object(core, '_read_knowledge', return_value={'variants': {'A2M|rs1': {'sources': ['https://example.org']}}}):
            self.assertEqual(describe('A2M', True)['links'], [])

    def test_core_and_text_expose_both_scopes_in_both_languages(self):
        previous = i18n.lang()
        self.addCleanup(i18n.set_lang, previous)
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            result = genome_context('COMT', 'rs4680')
            coverage = result['reference_context']['curation_coverage']
            self.assertTrue(coverage['variant_effect_curated'])
            self.assertIn(coverage['summary'], reference_lines(result))
            self.assertIn(coverage['notice'], reference_lines(result))

    def test_shared_card_presents_the_core_result(self):
        source = (support.SRC / 'scholion/web/gene-cards.js').read_text(encoding='utf-8')
        self.assertIn('data-curation-coverage', source)
        self.assertIn('esc(c.curation_coverage.summary)', source)


if __name__ == '__main__':
    unittest.main()
