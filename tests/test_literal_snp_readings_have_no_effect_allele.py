"""A verified position can have a literal genotype without an effect allele."""
from __future__ import annotations

import copy
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import genome
from scholion.engine import panel_genotype
from scholion.panel_reference import genome_context
from tests.test_a_row_at_the_position_is_not_the_locus import _Reader, row


class TestLiteralSnpPassports(_Reader):
    def test_reference_evidence_keeps_its_own_build_and_coordinate(self):
        for assembly in ('GRCh37', 'GRCh38'):
            genome.assembly_of = lambda *_: 'GRCh38'
            evidence = {'genotype': 'GG', 'depth': 31, 'assembly': assembly,
                        'evidence_file': 'synthetic-sites.vcf.gz'}
            with mock.patch.object(genome, '_ref_evidence', return_value=evidence):
                result = self.read([], rsid='rs3733890')
            self.assertEqual(result['confidence'], 'confirmed_ref')
            self.assertEqual(result['genotype'], 'GG')
            self.assertEqual(result['assembly'], assembly)
            self.assertEqual(result['read_pos'], genome.locus_position(genome.locus('rs3733890'), assembly))
            self.assertFalse(result['interpretation_applicable'])

    def observed(self, ref, alt, gt='0|1', assembly='GRCh38'):
        locus = genome.locus('rs4588')
        passport = locus['allele_identity']['builds'][assembly]
        genome.assembly_of = lambda *_: assembly
        return self.read([row(ref, alt, gt=gt, chrom=passport['chrom'],
                              pos=str(passport['position']), fmt='GT:DP', extra=gt+':31')], rsid='rs4588')

    def test_each_verified_alternative_is_read_in_both_builds_without_an_effect(self):
        for assembly in ('GRCh37', 'GRCh38'):
            for alt in ('A', 'C', 'T'):
                result = self.observed('G', alt, assembly=assembly)
                self.assertEqual(result['genotype'], 'G'+alt)
                self.assertEqual(result['confidence'], 'called')
                self.assertEqual(result['depth'], 31)
                self.assertTrue(result['phased'])
                self.assertEqual(result['assembly'], assembly)
                self.assertFalse(result['interpretation_applicable'])

    def test_a_caller_cannot_borrow_a_named_allele_for_an_observation_only_passport(self):
        result = self.observed('G', 'C')
        with mock.patch.object(genome, 'lookup', return_value={'status': 'ok', 'result': result}):
            answer = panel_genotype._genotype('rs4588', 'NC_000004.12:g.71752606G>C',
                                              'GC', 'C', {'status': 'ok'}, at=('G', 'C'))
        self.assertTrue(answer['read'])
        self.assertEqual(answer['state'], 'risk_allele_not_declared')
        self.assertNotIn(answer['state'], ('het', 'hom', 'absent'))
        self.assertEqual(genome_context('GC', 'rs4588')['level'], 'E')

    def test_reference_mismatch_indel_partial_and_conflicting_calls_remain_refused(self):
        wrong = self.observed('A', 'C')
        self.assertEqual(wrong['confidence'], 'reference_mismatch')
        self.assertIsNone(wrong['genotype'])
        event = self.observed('G', 'GAA')
        self.assertIsNone(event['genotype'])
        partial = self.observed('G', 'C', gt='./1')
        self.assertIsNone(partial['genotype'])
        locus = genome.locus('rs4588')
        different = self.read([row('G','A',gt='0/1',chrom='4',pos=str(locus['pos'])),
                               row('G','A',gt='1/1',chrom='4',pos=str(locus['pos']))], rsid='rs4588')
        self.assertEqual(different['confidence'], 'conflicting_calls')
        self.assertIsNone(different['genotype'])

    def test_incomplete_passport_is_refused_before_the_genome_is_queried(self):
        original = genome.locus('rs4588')
        for damage in ('missing_source', 'reference_mismatch', 'wrong_position', 'invalid_alternatives'):
            locus = copy.deepcopy(original)
            record = locus['allele_identity']['builds']['GRCh37']
            if damage == 'missing_source':
                record.pop('sequence_source')
            elif damage == 'reference_mismatch':
                record['sequence_reference'] = 'T'
            elif damage == 'wrong_position':
                record['position'] += 1
            else:
                record['alternatives'] = [{}]
            with mock.patch.object(genome, '_query_region', side_effect=AssertionError('no unsafe query')):
                result = genome._gt_at(locus)
            self.assertEqual(result['confidence'], 'alleles_not_comparable', damage)
            self.assertIsNone(result['genotype'])
        ordinary = {k:v for k,v in original.items() if k != 'allele_identity'}
        self.assertEqual(genome._gt_at(ordinary)['confidence'], 'multiallelic')

    def test_unknown_assembly_does_not_become_a_grch38_call(self):
        genome.assembly_of = lambda *_: None
        result = self.read([row('G','C',chrom='4',pos=str(genome.locus('rs4588')['pos']))], rsid='rs4588')
        self.assertIsNone(result['genotype'])
        self.assertEqual(result['confidence'], 'no_coordinates_for_assembly')

    def test_array_observation_also_carries_no_association_permission(self):
        from scholion import array_genome
        with mock.patch.object(genome, 'vcf_path', return_value=None), \
             mock.patch.object(array_genome, 'status', return_value={'status':'called', 'genotype':'GC', 'vendor':'synthetic'}):
            result = genome._gt_at(dict(genome.locus('rs4588'), rsid='rs4588'))
        self.assertEqual(result['genotype'], 'GC')
        self.assertEqual(result['confidence'], 'called_array')
        self.assertFalse(result['interpretation_applicable'])


class TestLiteralSnpCatalogue(unittest.TestCase):
    def test_every_literal_record_has_two_verified_sequence_passports_without_a_risk_allele(self):
        entries = [(rs, loc) for rs,loc in genome.loci()['loci'].items()
                   if (loc.get('allele_identity') or {}).get('scope')=='literal_genotype_only']
        self.assertGreater(len(entries), 50)
        for rs, locus in entries:
            self.assertNotIn('risk_allele', locus)
            for assembly in ('GRCh37','GRCh38'):
                self.assertTrue(genome._literal_snp_identity(locus, assembly), (rs, assembly))
            context = genome_context(locus['gene'],rs)['reference_context']
            if context['variant_status']=='described':
                # A separately reviewed literature association remains visible;
                # the coordinate passport still cannot provide an effect allele.
                from scholion import core
                reviewed=core._read_knowledge('longevity_directions.json')['directions'][rs]
                self.assertFalse(reviewed['personal_effect_permitted'],rs)
                self.assertTrue(reviewed['source_passport']['sources'],rs)
                self.assertIn(context['level'],('C','D'),rs)

    def test_intergenic_record_does_not_invent_a_gene_function(self):
        result = genome_context('—','rs17085007')
        self.assertEqual(result['reference_context']['function_status'], 'intergenic_region')
        self.assertEqual(result['reference_context']['gene_source_scope'], 'genomic_annotation')
        self.assertEqual(result['level'], 'E')
