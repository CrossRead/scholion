"""A portable interval opens exact local calls, without inventing coding exons."""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401
from scholion import genes


class PackagedGeneIntervals(unittest.TestCase):
    def test_any_packaged_interval_is_available_without_local_annotation_or_network(self):
        from scholion import core
        rows = core._read_knowledge('gene_reference_regions.json')['genes']
        self.assertGreater(len(rows), 6000)
        with mock.patch.object(genes, '_load_cache', return_value={}), \
             mock.patch.object(genes, '_save_cache'), \
             mock.patch.object(genes, 'gff3_candidates', return_value=[]), \
             mock.patch.object(genes, 'from_ensembl', side_effect=AssertionError('offline')):
            for gene in ('CDKN2B-AS1', 'COL6A4P1', 'ALDH4A1', 'AMT', 'A2M'):
                row = genes.resolve(gene, allow_network=False)
                self.assertEqual(row['assembly'], 'GRCh38')
                self.assertEqual(row['source'], 'ncbi_reference')
                self.assertEqual(row['cds'], [])
                self.assertIsNone(row['transcript'])
                self.assertEqual(row['start'], rows[gene]['start'])
                self.assertLess(row['start'], row['end'])
                self.assertTrue(row['reference_record_digest'])
            self.assertIsNone(genes.resolve('SYNTHETIC_NO_IDENTITY', allow_network=False))

    def test_other_build_is_not_used_and_stale_coordinate_cache_is_not_reused(self):
        with mock.patch.object(genes.core, '_read_knowledge', return_value={
                'genes': {'SYNTHETIC': {'assembly': 'GRCh37'}}}):
            self.assertIsNone(genes._portable_region('SYNTHETIC'))
        old = {'gene': 'SYNTHETIC', 'source': 'ncbi_reference', 'start': 10,
               'reference_record_digest': 'old'}
        current = {**old, 'start': 20, 'reference_record_digest': 'current'}
        with mock.patch.object(genes, '_load_cache', return_value={'SYNTHETIC': old}), \
             mock.patch.object(genes, '_portable_region', return_value=current), \
             mock.patch.object(genes, '_save_cache'), \
             mock.patch.object(genes, 'gff3_candidates', return_value=[]):
            self.assertEqual(genes.resolve('SYNTHETIC', allow_network=False)['start'], 20)
