"""Coordinate failures remain distinguishable through a local genome lookup."""
from __future__ import annotations

from contextlib import ExitStack
import unittest
from unittest.mock import patch

from scholion import genome, i18n
from scholion.engine import genomics
from scholion.format_genome import genome_report


class CoordinateResolution(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(i18n.set_lang, i18n.lang())
        for target, value in (
            ('scholion.genome.locus', None), ('scholion.panel_reference.catalogue_records', {}),
            ('scholion.genome._load_cache', {}), ('scholion.genome._save_cache', None),
            ('scholion.net.offline', False),
            ('scholion.genome.available', {'ready': False, 'reason': 'no_file'}),
            ('scholion.core.profile_genotypes', {}),
        ):
            self.stack.enter_context(patch(target, return_value=value))

    def mapping(self, **fields):
        return {'assembly_name': 'GRCh38', 'seq_region_name': '1', 'start': 100,
                'end': 100, 'allele_string': 'A/G', 'strand': 1, **fields}

    def test_unavailable_empty_ambiguous_and_wrong_orientation_are_not_one_answer(self):
        scenarios = [(None, 'source_unavailable'), ({}, 'not_found'),
                     ({'mappings': []}, 'no_supported_mapping'),
                     ({'error': 'bad response'}, 'invalid_response'),
                     ({'mappings': [self.mapping(strand=-1)]}, 'orientation_unverified'),
                     ({'mappings': [self.mapping(), self.mapping(start=101)]}, 'ambiguous_mapping')]
        for data, reason in scenarios:
            for language in ('en', 'ru'):
                with self.subTest(reason=reason, language=language), patch('scholion.net.get_json', return_value=data):
                    i18n.set_lang(language)
                    result = genome.lookup(rsid='rs999999999')
                    self.assertEqual('unknown_rsid', result['status'])
                    self.assertEqual(reason, result['resolution']['reason'])
                    self.assertIn(result['message'], genome_report(result))
                    self.assertNotIn('⟦', result['message'])
                    self.assertNotIn('result', result)

    def test_single_forward_placement_is_reproducible_and_only_identifier_leaves(self):
        with patch('scholion.net.get_json', return_value={'mappings': [self.mapping(), self.mapping()]}) as get:
            details = {}
            result = genome.resolve_rsid('rs999999999', details=details)
            self.assertEqual(('1', 100, 'A', 'G', 1), tuple(result[k] for k in ('chrom','pos','ref','alt','mapping_strand')))
            self.assertEqual('resolved', details['status'])
            get.assert_called_once_with(genome._ENSEMBL.format('rs999999999'))
        with patch('scholion.net.get_json') as get:
            details = {}
            self.assertIsNone(genome.resolve_rsid('private query / genotype=TT', details=details))
            self.assertEqual('invalid_identifier', details['reason'])
            get.assert_not_called()

    def test_local_refusal_and_nested_gene_reader_do_not_reenable_the_network(self):
        with patch('scholion.net.get_json') as get:
            result = genome.lookup(rsid='rs999999999', allow_network=False)
            self.assertEqual('local_only', result['resolution']['reason'])
            get.assert_not_called()
        with patch('scholion.genome.lookup', return_value={'status':'ok','gene':'FOXO3','loci':[]}) as lookup, \
             patch('scholion.engine.genomics.gene_layers', return_value={}), \
             patch('scholion.engine.genomics.gene_coverage', return_value={}), \
             patch('scholion.gene_region.report', return_value={'status':'unresolved_gene'}) as report:
            genomics.genome_lookup(gene='FOXO3', allow_network=False)
            self.assertFalse(lookup.call_args.kwargs['allow_network'])
            report.assert_called_once_with('FOXO3', allow_network=False)

    def test_saved_reading_survives_failed_coordinate_refresh_with_its_own_quality(self):
        old = {'gene':'SYNTHETIC','genotype':'AG','depth':17,'source':'synthetic-record'}
        with patch('scholion.core.profile_genotypes', return_value={'rs999999999':old}), \
             patch('scholion.net.get_json', return_value=None):
            result = genome.lookup(rsid='rs999999999')
        self.assertEqual('source_unavailable', result['resolution']['reason'])
        self.assertEqual('AG', result['result']['genotype'])
        self.assertEqual(17, result['result']['depth'])
        self.assertEqual('reported', result['result']['confidence'])
