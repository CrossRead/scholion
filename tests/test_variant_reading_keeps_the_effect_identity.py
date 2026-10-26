"""A literal reading and a sourced effect allele have different identities."""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, genome
from scholion.engine import panel_gate, panel_genotype
from tests.test_a_row_at_the_position_is_not_the_locus import _Reader, row


class TestLiteralObservations(_Reader):
    def test_another_snp_is_retained_without_borrowing_a_leiden_effect(self):
        result = self.read([row('C', 'G', fmt='GT:DP', extra='0|1:35')])
        self.assertIsNone(result['genotype'])
        self.assertFalse(result['interpretation_applicable'])
        self.assertEqual(result['observations'][0]['genotype'], 'CG')
        self.assertEqual(result['observations'][0]['depth'], 35)
        self.assertFalse(result['observations'][0]['interpretation_applicable'])

    def test_partial_calls_and_events_are_not_made_into_snp_observations(self):
        for alt, gt in [('G', './1'), ('G', '3/3'), ('CT', '0/1'), ('*', '1/1')]:
            with self.subTest(alt=alt, gt=gt):
                result = self.read([row('C', alt, gt=gt)])
                self.assertEqual(result.get('observations', []), [])

    def test_raw_phase_and_actual_identity_survive_a_call(self):
        result = self.read([row('C', 'G,T', gt='2|1')])
        self.assertEqual(result['genotype'], 'TG')
        self.assertEqual(result['raw_genotype'], '2|1')
        self.assertTrue(result['phased'])
        self.assertEqual(result['variant_identity']['assembly'], 'GRCh38')
        self.assertEqual(result['variant_identity']['ref'], 'C')

    def test_the_public_multi_allelic_locus_can_be_read_without_claiming_its_effect(self):
        result = self.read([row('A', 'G', gt='1/1')], rsid='rs53576')
        self.assertEqual(result['confidence'], 'called')
        self.assertEqual(result['genotype'], 'GG')
        other = self.read([row('A', 'T', gt='0/1')], rsid='rs53576')
        self.assertEqual(other['genotype'], 'AT')
        self.assertFalse(other['interpretation_applicable'])
        with mock.patch.object(genome, 'lookup', return_value={'status': 'ok', 'result': other}):
            g = panel_genotype._genotype('rs53576', 'NC_000003.12:g.8762685A>G', 'OXTR',
                                         'A', {'status': 'ok'}, at=('A', 'G'))
        self.assertTrue(g['read'])
        self.assertEqual(g['state'], 'risk_allele_not_declared')
        self.assertNotIn(g['state'], ('hom', 'het', 'absent'))

    def test_conflicting_calls_are_not_resolved_by_file_order(self):
        calls = [row('C', 'T', gt='0/1'), row('C', 'T', gt='1/1')]
        for variants in (calls, list(reversed(calls))):
            result = self.read(variants)
            self.assertEqual(result['confidence'], 'conflicting_calls')
            self.assertIsNone(result['genotype'])

    def test_reordered_alternatives_with_the_same_actual_call_are_not_a_conflict(self):
        result = self.read([row('C', 'G,T', gt='0/2'), row('C', 'T,G', gt='0/1')])
        self.assertEqual(result['genotype'], 'CT')
        self.assertEqual(result['confidence'], 'called')

    def test_same_rsid_does_not_override_a_reference_mismatch(self):
        result = self.read([row('T', 'G')], rsid='rs53576')
        self.assertEqual(result['confidence'], 'reference_mismatch')
        self.assertIsNone(result['genotype'])


class TestAssemblySpecificReference(_Reader):
    def test_the_grch37_reference_is_not_the_grch38_reference_for_f5(self):
        genome.assembly_of = lambda *_: 'GRCh37'
        result = self.read([row('T', 'C', gt='0/1')], rsid='rs6025')
        self.assertEqual(result['genotype'], 'TC')
        self.assertEqual(result['confidence'], 'called')
        self.assertEqual(result['variant_identity']['ref'], 'T')

    def test_mboat7_keeps_the_same_effect_allele_when_reference_and_alternate_swap(self):
        genome.assembly_of = lambda *_: 'GRCh37'
        result = self.read([row('C', 'T', gt='1/1')], rsid='rs641738')
        self.assertEqual(result['genotype'], 'TT')
        self.assertEqual(result['confidence'], 'called')
        self.assertEqual(genome.locus('rs641738')['ref'], 'T')

    def test_reference_evidence_preserves_the_actual_base_and_rejects_partial_calls(self):
        loc = dict(genome.locus('rs6025'))
        genome.assembly_of = lambda *_: 'GRCh37'
        with mock.patch.object(genome, '_sites_vcfs', return_value=['synthetic-sites.vcf.gz']):
            for gt, expected in [('0/0', 'TT'), ('0', 'T'), ('./0', None), ('0/.', None), ('0/1', None)]:
                genome._query_region = lambda *_, gt=gt: [row('T','C',gt=gt,pos=loc['pos_grch37'])]
                observed = genome._ref_evidence(loc)
                self.assertEqual((observed or {}).get('genotype'), expected, gt)


class TestTheWholeCuratedCatalogue(unittest.TestCase):
    def test_panel_hgvs_and_effect_alleles_agree_with_the_coordinate_catalogue(self):
        catalogue = core._read_knowledge_raw('loci.json')['loci']
        count = 0
        for file, section in [('system_gene_panels.json', 'systems'), ('on_demand_panels.json', 'panels')]:
            for panel in core._read_knowledge_raw(file)[section].values():
                for p in panel.get('positions', []):
                    loc = catalogue.get(p.get('rsid'))
                    if not loc or loc.get('repeat_call'):
                        continue
                    hgvs = panel_gate.HGVS.match(p.get('hgvs') or '')
                    if not hgvs:
                        continue
                    count += 1
                    with self.subTest(rsid=p['rsid']):
                        self.assertEqual((int(hgvs[2]), hgvs[3], hgvs[4]),
                                         (loc['pos'], loc['ref'], loc['alt']))
                        risk = panel_gate.risk_on_plus(p)
                        if risk:
                            self.assertIn(risk, (loc['ref'], loc['alt']))
        self.assertGreater(count, 200)

    def test_reviewed_identity_has_a_source_and_both_assembly_witnesses(self):
        checked = 0
        literal = 0
        for rsid, loc in core._read_knowledge_raw('loci.json')['loci'].items():
            if 'allele_identity' not in loc:
                continue
            identity = loc['allele_identity']
            observation_only = identity.get('scope') == 'literal_genotype_only'
            if observation_only:
                literal += 1
            else:
                checked += 1
            with self.subTest(rsid=rsid):
                self.assertTrue(identity['source'].endswith('/'+rsid[2:]))
                self.assertEqual(set(identity['builds']), {'GRCh37', 'GRCh38'})
                for build, key in [('GRCh38', 'pos'), ('GRCh37', 'pos_grch37')]:
                    self.assertEqual(identity['builds'][build]['position'], loc[key])
                    if observation_only:
                        self.assertEqual(set(loc['reading_alternatives']),
                                         set(identity['builds'][build]['alternatives']))
                    else:
                        self.assertIn(loc['alt'], identity['builds'][build]['alternatives'])
                if not observation_only:
                    self.assertIn(loc['alt'], loc['reading_alternatives'])
        self.assertEqual(checked, 7)
        self.assertGreaterEqual(literal, 59)

    def test_r325w_is_ct_in_both_the_catalogue_and_the_curated_association(self):
        loc = core._read_knowledge_raw('loci.json')['loci']['rs13266634']
        self.assertEqual((loc['ref'], loc['alt']), ('C', 'T'))
        rows = core._read_knowledge_raw('system_gene_panels.json')['systems']['glucose']['positions']
        p = next(p for p in rows if p.get('rsid') == 'rs13266634')
        self.assertTrue(p['hgvs'].endswith('C>T'))
        self.assertEqual(p['risk_allele'], 'C')
        self.assertEqual(p['protein'], 'p.Arg325Trp')


if __name__ == '__main__':
    unittest.main()
