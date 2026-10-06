"""Reference precision must not become personal clinical permission."""
import unittest

import support  # noqa: F401 -- isolated synthetic profile and genome
from scholion import core, i18n
from scholion.conclusion_basis import guard_position
from scholion.panel_reference import reference_context


class TestResearchedReferenceBoundaries(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        i18n.set_lang('en')

    def context(self, gene, rsid, level):
        return reference_context({'gene': gene, 'rsid': rsid}, level)

    def test_star17_mechanism_is_not_the_star2_splice_defect(self):
        increased = self.context('CYP2C19', 'rs12248560', 'A')
        splice = self.context('CYP2C19', 'rs4244285', 'A')
        self.assertIn('increased CYP2C19 transcription', increased['variant_context'])
        self.assertIn('*2/*17 is an intermediate', increased['variant_context'])
        self.assertIn('abnormal splice site', splice['variant_context'])
        self.assertIn('35034351', increased['variant_source'])

    def test_a_tag_and_a_molecular_experiment_do_not_unlock_a_clinical_sentence(self):
        for gene, rsid, level in [('HLA-B', 'rs9263726', 'A'),
                                 ('AOC1', 'rs2052129', 'C'),
                                 ('GSTP1', 'rs1695', 'D')]:
            context = self.context(gene, rsid, level)
            self.assertEqual('described', context['variant_status'])
            plain = {'level': level, 'text': 'unsupported diagnosis', 'findings': 1}
            before = guard_position({}, plain)
            after = guard_position({}, {**plain, 'reference_context': context})
            self.assertEqual(context, after.pop('reference_context'))
            self.assertEqual(before, after)

    def test_e_level_keeps_gene_biology_without_adopting_research_risk_direction(self):
        for gene, rsid in [('AGT', 'rs699'), ('WDR12', 'rs6725887')]:
            row = self.context(gene, rsid, 'E')
            self.assertEqual('not_curated', row['variant_status'])
            self.assertIsNone(row['variant_source'])
            self.assertTrue(row['gene_source'])

    def test_negative_results_and_orientation_are_visible_with_their_sources(self):
        self.assertIn('no ADRB1-based recommendation', self.context('ADRB1', 'rs1801253', 'C')['variant_context'])
        nos = self.context('NOS3', 'rs1799983', 'C')
        self.assertIn('Reference T already encodes', nos['variant_context'])
        self.assertIn('11331296', nos['variant_source'])
        gc = self.context('GC', 'rs2282679', 'B')
        self.assertIn('no overall genotype-by-time-by-dose interaction', gc['variant_context'])
        self.assertIn('36579074', gc['variant_source'])

    def test_research_metadata_is_bilingual_and_never_a_review_or_grade_assignment(self):
        raw = core._read_knowledge_raw('panel_reference_context.json')
        revised = {k: v for k, v in raw['variants'].items() if v.get('curated_on')}
        self.assertEqual(38, len(revised))
        for rsid, entry in revised.items():
            self.assertEqual('reference_only', entry['scope'])
            self.assertNotIn('review', entry)
            self.assertNotIn('level', entry)
            for key in ('reading', 'mechanism', 'possible_influence'):
                self.assertEqual({'en', 'ru'}, set(entry[key]))
            self.assertTrue(all(ref['url'].startswith('https://') for ref in entry['references']))
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                context = self.context(entry['gene'], rsid, 'B')
                self.assertEqual(entry['description'][language], context['variant_context'])
