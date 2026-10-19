"""Variant identity, reading quality and reference knowledge remain separate."""
from unittest import TestCase, mock

import support  # noqa: F401
from scholion import core, i18n, panel_reference
from scholion.engine import panel_gate, system_panels


class CuratedGenetics(TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        i18n.set_lang('en')
        self.specs = [p for p in core._read_knowledge('system_gene_panels.json')['systems']['immune']['positions']
                      if p['gene'] == 'ORAI1']

    def test_coordinates_and_classifications_have_independent_provenance(self):
        self.assertEqual(len(self.specs), 4)
        expected = {'rs118203993': (121627018, 122064924, 'C', 'T'),
                    'rs786204796': (121627039, 122064945, 'G', 'A'),
                    'rs3741596': (121641389, 122079295, 'A', 'G'),
                    'rs781829024': (121626842, 122064747, 'A', 'C')}
        levels = {x['level']: x for x in panel_gate.legend()['levels']}
        for p in self.specs:
            loc = core.loci()['loci'][p['rsid']]
            self.assertEqual(expected[p['rsid']], tuple(loc[k] for k in ('pos','pos_grch37','ref','alt')))
            self.assertIn('ncbi.nlm.nih.gov/clinvar/', loc['coordinate_source'])
            self.assertIsNone(panel_gate.refusal(p, [], '', p['source'], levels))
            self.assertEqual(p['classification'], p['database_assertion']['classification'])

    def rows(self, state, read=True):
        reading = {'state': state, 'read': read, 'genotype': 'synthetic', 'why': None if read else 'low_depth'}
        with mock.patch.object(system_panels, '_genotype', return_value=reading):
            out = system_panels._curated_rows('immune', {'positions': self.specs}, [], {'status':'no_file'}, {})
        return {r['rsid']: r for r in out['rows']}

    def test_recessive_carrier_and_activating_variant_are_different(self):
        rows = self.rows('het')
        self.assertTrue(rows['rs118203993']['clinical_carrier'])
        self.assertEqual(rows['rs118203993']['findings'], 0)
        self.assertFalse(rows['rs786204796']['clinical_carrier'])
        self.assertEqual(rows['rs786204796']['findings'], 0)
        self.assertEqual(self.rows('hom')['rs118203993']['findings'], 0)
        for rsid in ('rs118203993', 'rs786204796'):
            self.assertEqual(rows[rsid]['level'], 'C')
            self.assertTrue(rows[rsid]['interpretation']['summary'])
            self.assertEqual(rows[rsid]['database_assertion']['classification'], 'Pathogenic')

    def test_benign_conflicting_and_unread_do_not_become_clinical_findings(self):
        for state in ('het', 'hom'):
            rows = self.rows(state)
            for rsid in ('rs3741596','rs781829024'):
                self.assertEqual(rows[rsid]['findings'], 0)
        for r in self.rows('unread', False).values():
            self.assertFalse(r['read'])
            self.assertEqual(r['findings'], 0)
            self.assertIsNone(r['interpretation']['summary'])

    def test_longevity_conflict_and_primary_sources_reach_shared_context(self):
        for language in ('en','ru'):
            i18n.set_lang(language)
            spec = core._read_knowledge('longevity_directions.json')['directions']['rs2802292']
            with mock.patch.object(core, 'genotype_status', return_value={'genotype':'GT','confidence':'called','depth':30}):
                row = panel_reference.longevity_interpretation({'rsid':'rs2802292','genotype':'GT'}, spec)
            self.assertTrue(row['interpretation']['personalized'])
            self.assertEqual(row['level'], 'C')
            self.assertIn('27621247', row['interpretation']['source'])
            self.assertIsInstance(row['interpretation']['population'], str)
            self.assertIn(row['interpretation']['evidence_reason'], '\n'.join(panel_reference.interpretation_lines(row)))

    def test_unknown_or_conflicting_call_keeps_reference_without_personal_effect(self):
        spec = core._read_knowledge('longevity_directions.json')['directions']['rs2802292']
        for call in ({}, {'genotype':'GT','confidence':'low_depth'},
                     {'genotype':'GT','confidence':'called','depth_unverified':True},
                     {'genotype':'GT','confidence':'called','conflict':{'reported':'TT'}}):
            with mock.patch.object(core, 'genotype_status', return_value=call):
                row = panel_reference.longevity_interpretation({'rsid':'rs2802292','genotype':'GT'}, spec)
            self.assertFalse(row['interpretation']['personalized'])
            self.assertEqual(row['interpretation']['summary'], spec['label'])
            self.assertEqual(row['stored_genotype'], 'GT')

    def test_database_grade_and_review_are_localized_separately(self):
        i18n.set_lang('ru')
        for p in self.specs:
            context = panel_reference.interpretation_context(p, p['evidence']['level'], 'synthetic')
            assertion = context['database_assertion']
            self.assertIn(assertion['accession'], assertion['description'])
            self.assertNotIn('criteria provided', assertion['description'])
            self.assertNotIn('Pathogenic', assertion['description'])
            self.assertEqual(context['level'], p['evidence']['level'])

    def test_clinician_catalogue_report_carries_variant_identity_and_database_review(self):
        from scholion.engine.panel_catalogue import panel_description
        from scholion.format_genome import panel_report
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            result = panel_description('immune')
            report = panel_report(result)
            for p in result['positions']:
                if p['gene'] == 'ORAI1':
                    self.assertIn(p['transcript'], report)
                    self.assertIn(p['interpretation']['database_assertion']['description'], report)
