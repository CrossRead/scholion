"""Every personal topic reads existing gene intervals, without a fresh BAM job."""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401
from scholion import gene_region, genome
from scholion.engine import thematic_panels
from scholion.format_genome import panel_report


class GeneTopicReadings(unittest.TestCase):
    def test_every_topic_reads_each_gene_and_reference_never_reads(self):
        def report(gene):
            return {'status': 'ok', 'gene': gene, 'region': True,
                    'location': {'chrom': '1', 'start': 10, 'end': 20, 'strand': '+', 'assembly': 'GRCh38'},
                    'coverage': {'source': None, 'why': 'Synthetic unmeasured coverage'},
                    'variants': {'total': 1, 'coding': 0, 'consequential': None,
                                 'noncoding_rows': [], 'coding_rows': [], 'reference_calls': []},
                    'reading_summary': {'message': 'Synthetic existing interval read'}}
        with mock.patch.object(genome, 'available', return_value={'ready': True}), \
             mock.patch('scholion.engine.panel_intake._intake_reading', return_value={'read': False, 'message': 'Synthetic unavailable position'}), \
             mock.patch('scholion.engine.labs.analyze_labs', return_value={'markers': []}), \
             mock.patch.object(gene_region, 'preview', side_effect=report) as read:
            for key in thematic_panels.thematic_catalogue()['panels']:
                reference = thematic_panels.thematic_reference(key)
                before = read.call_count
                self.assertTrue(all('region_reading' not in row for row in reference['genes']))
                personal = thematic_panels.thematic_readings(key, 'patient')
                self.assertEqual(read.call_count - before, len(personal['genes']))
                for row in personal['genes']:
                    self.assertEqual(row['region_reading']['status'], 'ok')
                    self.assertEqual(row['region_reading']['variants']['total'], 1)
                rendered = panel_report(personal)
                self.assertIn('Synthetic existing interval read', rendered)

    def test_panel_preview_parses_actual_calls_without_depth_or_protein_work(self):
        location = {'gene': 'SYNTHETIC', 'chrom': '1', 'start': 10, 'end': 30,
                    'strand': '+', 'assembly': 'GRCh38', 'cds': [['1', 10, 30]]}
        rows = [['1', '15', '.', 'A', 'G', '30', 'PASS', '.', 'GT:DP', '0/1:21'],
                ['1', '16', '.', 'C', 'T', '30', 'PASS', '.', 'GT:DP', '0/0:22'],
                ['1', '17', '.', 'C', 'T', '30', 'PASS', '.', 'GT:DP', './.:0']]
        with mock.patch.object(gene_region.genes, 'resolve', return_value=location), \
             mock.patch.object(genome, 'available', return_value={'ready': True, 'assembly': 'GRCh38'}), \
             mock.patch.object(genome, 'vcf_path', return_value='synthetic.vcf.gz'), \
             mock.patch.object(genome, 'sample_index', return_value=0), \
             mock.patch.object(genome, '_query_region_range', return_value=rows), \
             mock.patch.object(gene_region, '_coverage', side_effect=AssertionError('no BAM scan')), \
             mock.patch.object(gene_region, '_protein', side_effect=AssertionError('no protein prediction')), \
             mock.patch.object(gene_region, '_clinvar_in_region', return_value=[]):
            result = gene_region.report('SYNTHETIC', allow_network=False, panel_preview=True)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['variants']['total'], 1)
        self.assertEqual(result['variants']['reference_calls'][0]['personal_alleles'], ['C', 'C'])
        self.assertEqual(result['variants']['uncalled_rows'], 1)
        self.assertIsNone(result['variants']['consequential'])
        self.assertFalse(result['reading_summary']['reference_identity_confirmed'])

    def test_preview_cache_is_bound_to_profile_and_vcf_identity(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            vcf = root / 'synthetic.vcf.gz'
            vcf.write_text('first input', encoding='utf-8')
            with mock.patch.object(genome, 'vcf_path', return_value=vcf), \
                 mock.patch.object(gene_region.genes, 'gff3_candidates', return_value=[]), \
                 mock.patch.object(gene_region.genes, '_cache_file', return_value=root/'no-cache'), \
                 mock.patch.object(gene_region.core, 'genome_bases', return_value=[]), \
                 mock.patch.object(gene_region.core, 'profile_dir', return_value=root/'person-a') as person, \
                 mock.patch.object(gene_region, 'report', return_value={'status': 'ok', 'variants': []}) as read:
                first = gene_region.preview('SYNTHETIC')
                first['variants'].append('caller mutation')
                self.assertEqual(gene_region.preview('SYNTHETIC')['variants'], [])
                self.assertEqual(read.call_count, 1)
                vcf.write_text('changed input bytes', encoding='utf-8')
                gene_region.preview('SYNTHETIC')
                self.assertEqual(read.call_count, 2)
                person.return_value = root/'person-b'
                gene_region.preview('SYNTHETIC')
                self.assertEqual(read.call_count, 3)
                read.assert_called_with('SYNTHETIC', allow_network=False, panel_preview=True)
