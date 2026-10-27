"""Scientific reference scope never supplies a missing clinical mechanism."""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401
from scholion import i18n
from scholion.conclusion_basis import conclusion_basis
from scholion.panel_reference import genome_context, reference_lines
from scholion.scientific_review import context_review


class ScientificScope(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_corrected_bundle_wins_over_a_legacy_local_reference(self):
        import json
        import tempfile
        from pathlib import Path
        from scholion import core
        names = ('system_gene_panels.json', 'on_demand_panels.json',
                 'panel_reference_context.json', 'gencc_reference_context.json',
                 'gene_function_context.json', 'clinical_reference_review.json')
        with tempfile.TemporaryDirectory() as name:
            local = Path(name).resolve()
            with mock.patch.object(core, 'knowledge_dir_local', return_value=local):
                for book in names:
                    (local/book).write_text(json.dumps({'_meta': {'updated': '2026-10-26'},
                                                       'legacy_local_sentinel': True}), encoding='utf-8')
                    self.assertGreaterEqual(core._knowledge_stamp(core._KNOWLEDGE_DIR/book), '2026-10-27')
                    self.assertEqual(core.knowledge_precedence(book)['answers'], 'bundled', book)
                    self.assertNotIn('legacy_local_sentinel', core._read_knowledge(book), book)

    def test_unknown_dynamic_gene_preserves_reference_gaps_without_a_no_evidence_claim(self):
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            row = genome_context('SYNTHETIC_NOT_IN_KNOWLEDGE', 'rs999999999')
            reviews = row['reference_context']['scientific_review']
            self.assertEqual(reviews[0]['status'], 'metadata_incomplete')
            self.assertEqual(reviews[-1]['status'], 'not_reviewed')
            self.assertNotIn('⟦', '\n'.join(reference_lines(row)))

    def test_gene_level_source_does_not_complete_a_variant_basis(self):
        spec = {'gene': 'SYNTHETIC', 'rsid': 'rs999999999', 'source': 'short citation'}
        before = conclusion_basis(spec)
        context_review('SYNTHETIC', spec['rsid'], {'gene_source': 'https://www.ncbi.nlm.nih.gov/gene/1/'})
        self.assertEqual(before, conclusion_basis(spec))
        self.assertEqual(before['status'], 'incomplete')

    def test_source_edit_invalidates_saved_scientific_review(self):
        with mock.patch('scholion.scientific_review._book', return_value={
                'variants': {'SYNTHETIC|rs123': {'status': 'association_supported', 'summary': 'Old claim',
                    'source_records': [{'file': 'synthetic.json', 'selector': ['genes', 'SYNTHETIC'], 'digest': 'old'}]}}}), \
             mock.patch('scholion.scientific_review.record', return_value={'record_digest': 'new'}):
            row = context_review('SYNTHETIC', 'rs123', {})[-1]
        self.assertEqual(row['status'], 'review_stale')
        self.assertNotEqual(row['summary'], 'Old claim')

    def test_retained_inheritance_reference_reaches_genes_outside_system_subset(self):
        # The full exported reference must work beyond the smaller system shelf.
        for gene in ('A2M', 'A2ML1'):
            row = genome_context(gene)
            self.assertTrue(row['reference_context']['gencc_assertions'], gene)
            scopes = {review['scope'] for review in row['reference_context']['scientific_review']}
            self.assertIn('gene_disease', scopes)

    def test_every_catalogue_variant_has_a_current_source_bound_scope(self):
        from scholion import core
        from scholion.knowledge_provenance import record
        book = core._read_knowledge_raw('variant_scientific_review.json')['variants']
        expected = set()
        for name, field in [('system_gene_panels.json', 'systems'), ('on_demand_panels.json', 'panels')]:
            for panel in core._read_knowledge_raw(name)[field].values():
                expected.update(row['gene'].upper() + '|' + row['rsid'] for row in panel.get('positions', []))
        self.assertEqual(expected, set(book))
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            for key, review in book.items():
                for source in review['source_records']:
                    self.assertEqual(source['digest'], record(source['file'], *source['selector'])['record_digest'], key)
                gene, rsid = key.split('|')
                row = genome_context(gene, rsid)
                scopes = row['reference_context']['scientific_review']
                variant = next(s for s in scopes if s['scope'] == 'variant')
                self.assertNotEqual(variant['status'], 'review_stale', key)
                self.assertIsInstance(variant['summary'], str)
                self.assertIsInstance(variant['limitations'], str)
                self.assertFalse(variant['clinical_eligibility_upgrade'])

    def test_previous_longevity_curation_is_not_relabelled_as_new_or_missing_research(self):
        from scholion.scientific_review import _retained_literature
        result = _retained_literature('APOE', 'rs429358')
        self.assertEqual(result['status'], 'retained_curated_literature')
        self.assertTrue(result['sources'])

    def test_database_and_guideline_sources_do_not_require_publication_ids(self):
        source = {'source_type': 'database_assertion', 'database': 'ClinVar',
                  'identifier': 'VCV000000001', 'version': 'synthetic-snapshot-1',
                  'url': 'https://www.ncbi.nlm.nih.gov/clinvar/variation/1/',
                  'claim_scopes': ['variant_classification'], 'reviewed_on': '2026-10-27'}
        spec = {'source_passport': source}
        self.assertEqual(conclusion_basis(spec, claim_type='variant_classification')['status'], 'complete')
        self.assertEqual(set(conclusion_basis(spec)['missing']), {'source_identifier', 'mechanism'})
        source['claim_scopes'].append('personal_inference')
        self.assertIn('source_identifier', conclusion_basis(spec)['missing'], 'a classification is not a personal clinical rule')
        guideline = {'source_type': 'guideline', 'identifier': 'synthetic-guideline-section-2',
                     'title': 'Synthetic clinical recommendation', 'issuer': 'Synthetic issuer',
                     'version': '1', 'url': 'https://example.test/guideline/1',
                     'reviewed_on': '2026-10-27', 'claim_scopes': ['personal_inference']}
        result = conclusion_basis({'source_passport': guideline, 'mechanism': 'Synthetic direct rationale'})
        self.assertEqual(result['status'], 'complete')
        guideline.pop('version')
        self.assertIn('source_identifier', conclusion_basis({'source_passport': guideline})['missing'])

    def test_typed_sources_refuse_an_unidentified_or_wrong_scope_record(self):
        from scholion.conclusion_basis import _source_passport
        base = {'source_type': 'publication', 'identifier': 'PMID:12345678',
                'url': 'https://pubmed.ncbi.nlm.nih.gov/12345678/',
                'claim_scopes': ['variant_classification'], 'reviewed_on': '2026-10-27'}
        scope = 'variant_classification'
        self.assertTrue(_source_passport(base, scope))
        self.assertFalse(_source_passport({**base, 'url': 'file:///private/source'}, scope))
        self.assertFalse(_source_passport({**base, 'identifier': ''}, scope))
        self.assertFalse(_source_passport({**base, 'identifier': 'unidentified'}, scope))
        stable = {**base, 'identifier': 'https://example.test/paper', 'title': 'Synthetic publication'}
        self.assertTrue(_source_passport(stable, scope))
        self.assertFalse(_source_passport(stable, 'personal_inference'))
        self.assertFalse(_source_passport({**base, 'source_type': 'unknown', 'version': '1'}, scope))
        db = {**base, 'source_type': 'database_assertion', 'database': 'ClinVar',
              'identifier': 'VCV000000001', 'version': '1'}
        self.assertTrue(_source_passport(db, scope))
        self.assertFalse(_source_passport({**db, 'identifier': 'a gene name'}, scope))
        self.assertFalse(_source_passport({**db, 'database': 'Unspecified database'}, scope))
