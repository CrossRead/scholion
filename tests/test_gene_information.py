"""Gene information stays useful without inventing human genotype effects."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import gene_information as info, reference_updates, variant_annotations as va
from tests.test_variant_annotation_reference import source_entry


class GeneInformation(unittest.TestCase):
    def data(self):
        entry = {**source_entry(), 'comments': [
            {'commentType': 'FUNCTION', 'texts': [{'value': 'Transports a substrate in a cell assay.',
              'evidences': [{'source': 'PubMed', 'id': '100'}]}]},
            {'commentType': 'DISEASE', 'disease': {'diseaseId': 'Synthetic syndrome',
              'description': 'A recessive disorder.'}, 'note': {'texts': [{'value': 'The association is disputed.'}]}},
            {'commentType': 'TISSUE SPECIFICITY', 'texts': [{'value': 'Expressed in liver.'}]}]}
        protein = va.uniprot_context(entry, '2026_04', '2026-11-16')
        return {'genes': {'HGNC:1': {'symbol': 'SYNTH', 'ncbi_id': '1'}},
                'proteins': {'P00001': protein}, 'source_checks': {
                    'hgnc:HGNC:1': {'data': {'name': 'Synthetic gene', 'locus_type': 'gene with protein product'}},
                    'gencc:HGNC:1': {'data': {'SGC-1': {'disease_title': 'Synthetic syndrome',
                        'classification_title': 'Refuted', 'moi_title': 'Autosomal recessive'}},
                        'provider': 'GenCC', 'compared_on': '2026-11-16', 'status': 'current'}}}

    def test_full_source_context_retains_qualifiers_and_primary_links(self):
        result = info.reference(self.data(), 'HGNC:1')
        self.assertTrue(result['dimensions']['source_function'])
        self.assertTrue(result['dimensions']['disease_context'])
        self.assertFalse(result['dimensions']['established_gene_disease'])
        self.assertFalse(result['human_genotype_inferred'])
        self.assertFalse(result['normality_from_reference'])
        self.assertIn('disputed', result['observations'][1]['text'])
        self.assertEqual(result['observations'][0]['publications'], ['https://pubmed.ncbi.nlm.nih.gov/100/'])
        report = '\n'.join(info.lines(result))
        self.assertIn('Transports a substrate', report)
        self.assertIn('Refuted', report)

    def test_current_empty_gencc_does_not_resurrect_previous_assertions(self):
        data = self.data(); data['source_checks']['gencc:HGNC:1']['data'] = {}
        with patch.object(info.core, '_read_knowledge', side_effect=AssertionError('stale fallback')):
            result = info.reference(data, 'HGNC:1')
        self.assertEqual(result['clinical_assertions'], [])

    def test_identity_does_not_count_as_function(self):
        data = self.data(); data['proteins'] = {}
        result = info.reference(data, 'HGNC:1')
        self.assertTrue(result['dimensions']['identity'])
        self.assertFalse(result['dimensions']['source_function'])

    def test_shared_protein_disease_cannot_silently_become_gene_specific(self):
        data = self.data(); data['proteins']['P00001']['gene_ids'].append('HGNC:2')
        result = info.reference(data, 'HGNC:1')
        self.assertTrue(all(row['shared_protein'] for row in result['observations']))
        from scholion.i18n import t
        self.assertIn(t('variant_knowledge.shared_protein'), info.lines(result))

    def test_isoform_qualifier_survives_source_projection(self):
        data = self.data(); data['proteins']['P00001']['functions'][0]['molecule'] = 'Isoform 3'
        result = info.reference(data, 'HGNC:1')
        self.assertTrue(result['observations'][0]['text'].startswith('Isoform 3:\n'))
        self.assertIn('Isoform 3:', '\n'.join(info.lines(result)))
        with patch.object(va, 'catalogue', return_value=data), patch.object(va, 'gene_id', return_value='HGNC:1'), patch.object(va, 'model_references', return_value=[]), patch.object(va, 'index', return_value=({}, {}, {})):
            self.assertTrue(va.reference('SYNTH')['functions'][0]['text'].startswith('Isoform 3: '))

    def test_refresh_observes_changed_and_removed_gene_context(self):
        base = self.data(); base['records'] = []
        changed = self.data(); changed['records'] = []
        changed['proteins']['P00001']['contexts'][0]['note']['texts'][0]['value'] = 'New qualification.'
        events, _, _ = reference_updates._compare(base, changed)
        self.assertIn('gene_context_changed', [row['kind'] for row in events])
        events, _, _ = reference_updates._compare(base, {'records': [], 'proteins': {}})
        self.assertIn('gene_context_changed', [row['kind'] for row in events])
        self.assertIn('gene_function_changed', [row['kind'] for row in events])

    def test_periodic_import_requests_the_content_shown_in_cards(self):
        for field in ('cc_function', 'cc_disease', 'cc_pathway', 'cc_tissue_specificity', 'cc_subcellular_location'):
            self.assertIn(field, reference_updates._FIELDS)

    def test_curated_noncoding_function_is_retained_with_its_review_date(self):
        data = self.data(); data['proteins'] = {}
        book = {'genes': {'SYNTH': {'description': 'A small RNA participates in splicing.',
            'function_status': 'curated_function', 'checked_on': '2026-11-04',
            'source': 'https://pubmed.ncbi.nlm.nih.gov/100/'}}}
        with patch.object(info.core, '_read_knowledge', return_value=book):
            result = info.reference(data, 'HGNC:1')
        self.assertTrue(result['dimensions']['source_function'])
        self.assertEqual(result['observations'][0]['compared_on'], '2026-11-04')

    def test_retained_clinical_snapshot_requires_exact_gene_identity(self):
        data = self.data(); data['source_checks'].pop('gencc:HGNC:1')
        book = {'_meta': {'downloaded': '2026-10-23'}, 'genes': {'SYNTH': {
            'hgnc_id': 'HGNC:1', 'submissions': [{'disease': 'Synthetic syndrome',
            'classification': 'Strong', 'moi_code': 'AR', 'submission_ids': ['SGC-1']}]}}}
        with patch.object(info.core, '_read_knowledge', return_value=book):
            result = info.reference(data, 'HGNC:1')
            self.assertTrue(result['dimensions']['established_gene_disease'])
            book['genes']['SYNTH']['hgnc_id'] = 'HGNC:2'
            self.assertEqual(info.reference(data, 'HGNC:1')['clinical_assertions'], [])

    def test_shipped_catalogue_enables_linked_source_checks_and_keeps_context(self):
        data = va.catalogue()
        self.assertTrue(data['_meta']['check_linked_sources'])
        self.assertEqual(va.gene_id('SHP2'), 'HGNC:9644')
        self.assertTrue(va.model_references('PTPN11', 'rs11066301'))
        self.assertGreater(sum(bool(row.get('functions')) for row in data['proteins'].values()), 5000)
        for gene in ('BRCA1', 'HFE', 'A2M', 'ABCG2'):
            result = va.reference(gene, limit=1)
            self.assertTrue(result['gene_information']['dimensions']['source_function'])
            self.assertIn('What this gene does', va.report(result))
        hfe = va.model_references('HFE', 'rs1800562')
        self.assertTrue(hfe)

    def test_unavailable_source_keeps_original_date_and_content(self):
        data = self.data()
        data['source_checks']['ncbi_gene:1'] = {'data': {'summary': 'Retained function.'},
            'compared_on': '2025-01-01', 'attempted_on': '2026-11-16', 'status': 'unavailable'}
        row = info.reference(data, 'HGNC:1')['observations'][-1]
        self.assertEqual(row['compared_on'], '2025-01-01')
        self.assertEqual(row['status'], 'unavailable')
        self.assertEqual(row['freshness'], 'due')
