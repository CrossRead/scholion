"""A zero variant count is qualified by real depth, not interpreted as an absent gene."""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401
from scholion import bamlite, format as fmt, gene_region

LOC = {'gene': 'SYNTHETIC', 'chrom': 'chr1', 'start': 10, 'end': 19,
       'assembly': 'GRCh38', 'strand': '+', 'transcript': 'SYNTHETIC_TX'}


class ReadingSummary(unittest.TestCase):
    def report(self, depths=None, variants=None):
        cov = {'source': None, 'why': 'synthetic absent BAM'} if depths is None else {
            'source': 'bam', 'gene': bamlite.summarise(depths)}
        variant = {'total': 0, 'coding': 0, 'consequential': 0, 'uncalled_rows': 0}
        variant.update(variants or {})
        return {'status': 'ok', 'region': True, 'gene': 'SYNTHETIC', 'location': LOC,
                'coverage': cov, 'variants': variant,
                'reading_summary': gene_region.reading_summary(LOC, variant, cov),
                'reference_region': gene_region.reference_region(LOC)}

    def test_partial_reading_has_explicit_read_and_unread_fractions(self):
        result = self.report([0, 0, 10, 30])
        summary = result['reading_summary']
        self.assertEqual('partial_coverage', summary['state'])
        self.assertEqual(50, summary['coverage']['pct_1x'])
        self.assertEqual(50, summary['coverage']['pct_zero'])
        self.assertEqual(10, summary['coverage']['mean'])
        self.assertFalse(summary['reference_identity_confirmed'])
        for lang in ('en', 'ru'):
            with mock.patch.dict('os.environ', {'SCHOLION_LANG': lang}):
                text = fmt.genome_report(self.report([0, 0, 10, 30]))
            self.assertIn('50.0%', text)
            self.assertIn('GRCh38', text)
            self.assertIn('SYNTHETIC_TX', text)
            self.assertIn('ensembl.org', text)
            self.assertNotIn('⟦', text)

    def test_zero_coverage_is_not_a_checked_negative_and_unknown_is_not_zero(self):
        self.assertEqual('no_coverage', self.report([0, 0])['reading_summary']['state'])
        unknown = self.report()['reading_summary']
        self.assertEqual('coverage_unknown', unknown['state'])
        self.assertIsNone(unknown['coverage'])

    def test_full_depth_never_confirms_per_base_reference_identity(self):
        summary = self.report([30, 30])['reading_summary']
        self.assertEqual('covered', summary['state'])
        self.assertFalse(summary['reference_identity_confirmed'])
        self.assertEqual(100, summary['coverage']['pct_1x'])

    def test_noncoding_differences_and_uncalled_rows_stay_in_the_answer(self):
        result = self.report([20, 20], {'total': 1, 'uncalled_rows': 2,
            'noncoding_rows': [{'chrom': 'chr1', 'pos': 11, 'ref': 'A', 'alt': 'G', 'genotype': '0/1'}]})
        self.assertFalse(result['reading_summary']['variant_search_complete'])
        self.assertIn('chr1:11 A>G', fmt.genome_report(result))

    def test_region_refusal_does_not_hide_previously_read_catalogue_positions(self):
        response = {'status': 'ok', 'gene': 'SYNTHETIC', 'loci': [
            {'status': 'ok', 'rsid': 'rs1', 'gene': 'SYNTHETIC', 'result': {'genotype': 'AG'}}],
            'region_report': {'status': 'unresolved_gene', 'message': 'Annotation missing'}}
        text = fmt.genome_report(response)
        self.assertIn('Annotation missing', text)
        self.assertIn('rs1', text)
        self.assertIn('AG', text)

    def test_region_reader_keeps_reference_genotypes_noncoding_variants_and_failed_calls_distinct(self):
        from scholion import genome
        rows = [
            'chr1\t11\t.\tA\tG\t50\tPASS\t.\tGT:DP:GQ\t0/0:30:60',
            'chr1\t12\t.\tA\tG\t50\tPASS\t.\tGT:DP:GQ\t0/1:30:60',
            'chr1\t13\t.\tA\tG\t50\tLowQual\t.\tGT:DP:GQ\t0/1:2:1']
        with mock.patch.object(gene_region.genes, 'resolve', return_value={**LOC, 'cds': []}), \
             mock.patch.object(genome, 'available', return_value={'ready': True, 'assembly': 'GRCh38'}), \
             mock.patch.object(genome, 'vcf_path', return_value='synthetic.vcf'), \
             mock.patch.object(genome, 'sample_index', return_value=0), \
             mock.patch.object(genome, '_query_region_range', return_value=[row.split('\t') for row in rows]), \
             mock.patch.object(gene_region, '_coverage', return_value={'source': None, 'why': 'No synthetic BAM'}), \
             mock.patch.object(gene_region, '_clinvar_in_region', return_value=[]):
            result = gene_region.report('SYNTHETIC', allow_network=False)
        variants = result['variants']
        self.assertEqual(1, variants['total'])
        self.assertEqual(1, variants['uncalled_rows'])
        self.assertEqual(['A', 'A'], variants['reference_calls'][0]['personal_alleles'])
        self.assertEqual(['A', 'G'], variants['noncoding_rows'][0]['personal_alleles'])
        text = fmt.genome_report(result)
        self.assertIn('REF A', text)
        self.assertIn('0/0', text)
        self.assertFalse(result['reading_summary']['reference_identity_confirmed'])

    def test_reference_link_uses_the_actual_assembly_and_interval(self):
        result = gene_region.reference_region(dict(LOC, assembly='GRCh37'))
        self.assertIn('grch37.ensembl.org', result['url'])
        self.assertIn('chr1%3A10-19', result['url'])
        self.assertEqual('SYNTHETIC_TX', result['transcript'])


if __name__ == '__main__':
    unittest.main()
