"""The cross-system intake stays complete and does not invent clinical review."""
from __future__ import annotations

import json
import unittest

import support  # noqa: F401
from scholion import core
from scholion.engine import panel_catalogue, panel_gate, panel_genotype, system_panels

KEY = 'folate_histamine_redox_choline'
EXPECTED = {'rs1801133', 'rs1801131', 'rs4680', 'rs10156191', 'rs1049742',
            'rs1049793', 'rs2052129', 'rs6323', 'rs1137070', 'rs1695',
            'rs1138272', 'rs1050450', 'rs1799983', 'rs2070744', 'rs7946',
            'rs12325817'}
EXISTING = {'rs1801133', 'rs1801131', 'rs4680'}


class TestThePanelIntake(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(core.knowledge_path('on_demand_panels.json').read_text(encoding="utf-8"))['panels'][KEY]

    def test_all_positions_are_addressable_in_both_builds(self):
        loci = json.loads(core.knowledge_path('loci.json').read_text(encoding="utf-8"))['loci']
        self.assertEqual(EXPECTED, {p['rsid'] for p in self.spec['positions']})
        self.assertEqual(16, len(self.spec['positions']))
        for rs in EXPECTED:
            self.assertIsInstance(loci[rs]['pos'], int)
            self.assertIsInstance(loci[rs]['pos_grch37'], int)

    def test_new_rows_do_not_claim_review_or_an_allele_direction(self):
        for p in self.spec['positions']:
            if p['rsid'] in EXISTING:
                continue
            with self.subTest(rsid=p['rsid']):
                self.assertIsNone(p['review'])
                self.assertIsNone(p['risk_allele'])
                self.assertFalse(p['text'])
                self.assertEqual('awaiting_clinical_review', p['interpretation_status'])
                self.assertIn(p['evidence']['level'], ('C', 'D'))
                self.assertTrue(p['population'])
                self.assertTrue(p['source'])
                self.assertFalse(panel_gate.level_of(p, {v['level']: v for v in panel_gate.legend()['levels']})['verdict_allowed'])

    def test_existing_interpretations_are_reused_without_reassignment(self):
        book = json.loads(core.knowledge_path('system_gene_panels.json').read_text(encoding="utf-8"))['systems']
        original = {p['rsid']: p for s in book.values() for p in s['positions'] if p.get('rsid') in EXISTING}
        for p in self.spec['positions']:
            if p['rsid'] in EXISTING:
                for field in ('text', 'risk_allele', 'evidence', 'review'):
                    self.assertEqual(original[p['rsid']][field], p[field])

    def test_male_x_ploidy_is_checked_without_assigning_a_risk_allele(self):
        for genotype in ('T', 'TT', 'T/T'):
            call = {'state': 'risk_allele_not_declared', 'read': True, 'genotype': genotype}
            male = panel_genotype.as_hemizygous(call, 'male')
            self.assertTrue(male['hemizygous'])
            self.assertEqual('risk_allele_not_declared', male['state'])
            self.assertFalse(panel_genotype.as_hemizygous(call, None)['read'])
            self.assertEqual(call, panel_genotype.as_hemizygous(call, 'female'))
        het = {'state': 'risk_allele_not_declared', 'read': True, 'genotype': 'G/T'}
        self.assertEqual('het_on_male_x', panel_genotype.as_hemizygous(het, 'male')['why'])
        self.assertFalse(panel_genotype.as_hemizygous(het, 'male')['read'])
        for genotype in ('', 'N'):
            invalid = {'state': 'risk_allele_not_declared', 'read': True, 'genotype': genotype}
            self.assertEqual('genotype_not_comparable', panel_genotype.as_hemizygous(invalid, 'male')['why'])

    def test_the_description_and_card_include_every_position(self):
        self.assertEqual(16, panel_catalogue.panel_description(KEY)['counts']['positions'])
        card = system_panels.system(KEY, 'clinician')
        self.assertTrue(card['on_demand'])
        self.assertEqual(0, card['genetics']['refused']['total'])
        self.assertEqual(EXPECTED, {p['rsid'] for p in card['genetics']['rows']})
        self.assertNotIn('score', card['labs'])


if __name__ == '__main__':
    unittest.main()
