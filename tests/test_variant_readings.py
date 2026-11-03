"""Stored observations must not silently disagree between product surfaces."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import core, genome, variant_readings as vr
from scholion.engine import panel_genotype, panel_intake, pgx
from scholion.genetic_comparison import genotype_quality
from tests.test_a_row_at_the_position_is_not_the_locus import _Reader, row


class TestStoredObservations(unittest.TestCase):
    def test_drug_marker_cards_keep_selected_reading_and_compound_identity(self):
        markers = [{'rsid': 'rs1801133', 'genotype': 'CC', 'depth': 99,
                    'copies': 1, 'interpretation': 'Old effect', 'function': 'decreased'}]
        before = deepcopy(markers)
        reading = vr.resolve('rs1801133',
                             {'genotype': 'CT', 'confidence': 'called', 'depth': 23},
                             {'genotype': 'CC', 'source': 'pharmacogenomics.json'})
        with patch.object(core, 'genotype_status', return_value=reading):
            card = pgx._marker_cards(markers, 'MTHFR')[0]
        self.assertEqual(card['genotype'], 'CT')
        self.assertEqual(card['depth'], 23)
        self.assertEqual(card['reading_record'], reading['reading_record'])
        self.assertIsNone(card['copies'])
        self.assertFalse(card['interpretation'])
        self.assertTrue(card['reference_context']['gene_function'])
        self.assertEqual(markers, before)
        compound = {'diplotype': '*1/*2', 'phenotype_text': 'Intermediate metabolizer',
                    'source': 'synthetic caller'}
        with patch.object(core, 'genotype_status') as lookup:
            card = pgx._marker_cards([compound], 'CYP2C19')[0]
        lookup.assert_not_called()
        self.assertEqual(card['diplotype'], '*1/*2')
        self.assertTrue(card['reference_context']['gene_function'])

    def test_a_saved_conflict_is_not_a_drug_caution_or_a_panel_allele_effect(self):
        from scholion.engine import class_genotype
        saved = {'rsid':'rs1801133','genotype':'CT','depth':23,
                 'source':'pharmacogenomics.json',
                 'conflict':{'kind':'recorded_disagreement'}}
        resolved = vr.resolve('rs1801133', None, saved)
        with patch.object(core,'genotype_status',return_value=resolved):
            self.assertIsNone(class_genotype._state({'rsid':'rs1801133','risk_allele':'T'}))
        with patch.object(core,'profile_genotypes',return_value={'rs1801133':saved}), \
             patch.object(genome,'lookup',return_value={'status':'ok','result':resolved}):
            for scan in ({'status':'ok'}, {'status':'unavailable'}):
                row = panel_genotype._genotype('rs1801133','','MTHFR','T',scan,at=('C','T'))
                self.assertEqual(row['genotype'], 'CT')
                self.assertEqual(row['depth'], 23)
                self.assertEqual(row['state'], 'risk_allele_not_declared')
                self.assertEqual(row['why'], 'source_conflict')

    def test_all_lipid_positions_retain_reading_and_quality_when_effect_is_withheld(self):
        from scholion.engine import genomics
        result = vr.resolve('rs11591147',
                            {'genotype':'GT','confidence':'called','depth':23,'source':'vcf'},
                            {'genotype':'GG','source':'pharmacogenomics.json'})
        with patch.object(core,'genotype_status',return_value=result):
            report = genomics.lipid_genetics()
            rows = report['pcsk9']
        from scholion.format_genome import lipid_genetics_report
        from scholion.i18n import t
        text = lipid_genetics_report(report)
        self.assertIn(t('genome.source_conflict'), text)
        self.assertIn('GT', text)
        self.assertEqual(len(rows), 4)
        for value in rows:
            self.assertTrue(value['read'])
            self.assertEqual(value['status'], 'read')
            self.assertEqual(value['genotype'], 'GT')
            self.assertEqual(value['reading']['depth'], 23)
            self.assertTrue(value['reading']['conflict'])
            self.assertIsNone(value['copies'])
            self.assertIsNone(value['carrier'])

    def test_hgvs_fallback_keeps_the_same_source_resolution_as_catalogue_lookup(self):
        saved = {'rsid':'rs1801133','genotype':'CC','source':'pharmacogenomics.json'}
        current = {'genotype':'CT','confidence':'called','source':'vcf','depth':28}
        with patch.object(core,'profile_genotypes',return_value={'rs1801133':saved}), \
             patch.object(genome,'lookup',return_value={'status':'unknown_rsid'}), \
             patch.object(panel_genotype,'_loc_from_hgvs',return_value={'chrom':'1','pos':1}), \
             patch.object(genome,'_gt_at',return_value=current):
            row = panel_genotype._genotype('rs1801133','','MTHFR','T',{'status':'ok'},at=('C','T'))
        self.assertEqual(row['genotype'], 'CT')
        self.assertEqual(row['why'], 'source_conflict')
        self.assertEqual(len(row['reading_record']['observations']), 2)

    def test_text_and_gene_listing_keep_report_source_and_conflict_in_both_languages(self):
        from scholion import format_genome, i18n
        previous = i18n.lang()
        try:
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                row = {'status':'ok','rsid':'rs1801133','gene':'MTHFR',
                       'result':vr.resolve('rs1801133', None,
                           {'genotype':'CT','source':'pharmacogenomics.json',
                            'conflict':{'kind':'recorded_disagreement'}})}
                single = format_genome.genome_report(row)
                listing = format_genome.genome_report({'status':'ok','gene':'MTHFR','loci':[row]})
                for text in (single, listing):
                    self.assertIn(i18n.t('genome.refused_head.reported'), text)
                    self.assertIn(i18n.t('genome.source_conflict'), text)
        finally:
            i18n.set_lang(previous)

    def test_legacy_annotated_call_keeps_depth_and_raw_text_without_false_conflict(self):
        pgx_data = {'genotypes':[{'rsid':'rs429358','genotype':'TT'}]}
        longevity = {'apoe':{'rs429358':'T/T (DP=17)'}}
        with patch.object(core,'pharmacogenomics',return_value=pgx_data), \
             patch.object(core,'read_profile_json',return_value=longevity):
            saved = vr.recorded_genotypes()['rs429358']
        self.assertNotIn('conflict', saved)
        old = saved['observations'][1]
        self.assertEqual(old['raw_recorded_genotype'], 'T/T (DP=17)')
        self.assertEqual(old['quality']['depth'], 17)
        self.assertEqual(old['genotype'], 'T/T')

    def test_comparison_keeps_allele_boundaries_and_requires_literal_bases(self):
        self.assertTrue(vr.same_genotype('G|A', 'AG'))
        self.assertTrue(vr.same_genotype('AT/A', 'A/AT'))
        for a, b in [('AT/A', 'AA/T'), ('0/1', '1/0'), ('A/.', 'A/.'), ('ATG', 'TAG')]:
            self.assertFalse(vr.same_genotype(a, b), (a, b))

    def test_presentation_language_does_not_change_observation_identity(self):
        call = {'genotype':'AG','confidence':'called','note':'First wording'}
        first = vr.resolve('rs1', call)
        second = vr.resolve('rs1', {**call, 'note':'Another wording'})
        self.assertEqual(first['reading_record']['source_digest'], second['reading_record']['source_digest'])
        changed = vr.resolve('rs1', {**call, 'depth':25})
        self.assertNotEqual(first['reading_record']['source_digest'], changed['reading_record']['source_digest'])

    def test_saved_result_cannot_hide_current_conflict(self):
        result = vr.resolve('rs1', {'confidence':'conflicting_calls','interpretation_applicable':False},
                            {'genotype':'AG','source':'pharmacogenomics.json'})
        self.assertEqual(result['genotype'], 'AG')
        self.assertFalse(vr.permits_interpretation(result))
        self.assertEqual(result['conflict']['kind'], 'conflicting_calls')

    def test_apoe_keeps_conflicting_readings_unconfirmed(self):
        first = {'genotype':'TT','confidence':'called','conflict':{'kind':'source_disagreement'}}
        second = {'genotype':'CC','confidence':'called'}
        result = genome._apoe_from_readings(first, second)
        self.assertEqual(result['status'], 'unconfirmed')
        self.assertNotIn('genotype', result)

    def test_gene_lookup_keeps_saved_readings_without_a_vcf(self):
        saved = {'rsid':'rs1801133','genotype':'CT','source':'pharmacogenomics.json'}
        with patch.object(genome,'available',return_value={'ready':False,'reason':'no_file'}), \
             patch.object(core,'profile_genotypes',return_value={'rs1801133':saved}):
            result = genome.lookup(gene='MTHFR',allow_network=False)
        reading = next(r for r in result['loci'] if r['rsid']=='rs1801133')['result']
        self.assertEqual(reading['genotype'], 'CT')
        self.assertEqual(reading['confidence'], 'reported')

    def test_adapters_preserve_duplicate_quality_and_conflict_without_mutation(self):
        pgx_data = {'genotypes': [{'gene':'SYNTH', 'rsid':'rsTEST', 'genotype':'AG', 'depth':28},
                                  {'gene':'SYNTH', 'rsid':'rsTEST', 'genotype':'AA', 'depth':12}]}
        longevity = {'known': [{'gene':'SYNTH', 'rsid':'rstest', 'genotype':'GG', 'date':'2020-01-01'}]}
        before = deepcopy((pgx_data, longevity))
        with patch.object(core, 'pharmacogenomics', return_value=pgx_data), \
             patch.object(core, 'read_profile_json', return_value=longevity):
            saved = vr.recorded_genotypes()['rstest']
        self.assertEqual((pgx_data, longevity), before)
        self.assertEqual(len(saved['observations']), 3)
        self.assertEqual(saved['depth'], 28)
        self.assertEqual(saved['conflict']['values'], ['AG','AA','GG'])
        self.assertFalse(saved['interpretation_applicable'])
        self.assertEqual(len({r['source']['record_digest'] for r in saved['observations']}), 3)

    def test_reference_call_outranks_report_but_conflict_prevents_effect(self):
        saved = {'genotype':'CT','source':'pharmacogenomics.json'}
        called = {'genotype':'CC','confidence':'confirmed_ref','depth':32,'source':'vcf'}
        result = vr.resolve('rs1801133', called, saved)
        self.assertEqual(result['genotype'], 'CC')
        self.assertEqual(result['confidence'], 'confirmed_ref')
        self.assertIsNone(pgx._copies_at_locus(result, 'T'))
        self.assertFalse(vr.permits_interpretation(result))
        self.assertIn('source_conflict', genotype_quality({'read':True,'genotype':result})['reasons'])
        self.assertEqual(len(result['reading_record']['observations']), 2)

    def test_unread_row_does_not_erase_saved_value_or_inherit_its_depth(self):
        result = vr.resolve('rs1', {'genotype':'AA','confidence':'assumed_ref','depth':3},
                            {'genotype':'AG','source':'longevity_findings.json'})
        self.assertEqual(result['genotype'], 'AG')
        self.assertNotIn('depth', result)
        self.assertEqual(result['reading_record']['selected'], 'recorded')
        self.assertEqual(result['reader_refusal'], 'assumed_ref')

    def test_catalogue_change_invalidates_record_identity_without_changing_observation(self):
        value = {'genotype':'AG','confidence':'called','source':'vcf','depth':21}
        with patch.object(core, 'loci', return_value={'loci':{'rs1':{'alt':'G'}}}):
            first = vr.resolve('rs1', value)
        with patch.object(core, 'loci', return_value={'loci':{'rs1':{'alt':'C'}}}):
            second = vr.resolve('rs1', value)
        self.assertNotEqual(first['reading_record']['catalogue_digest'], second['reading_record']['catalogue_digest'])
        self.assertEqual(first['reading_record']['source_digest'], second['reading_record']['source_digest'])

    def test_core_and_panels_keep_the_same_conflict_and_literal_reading(self):
        value={'genotype':'CC','confidence':'called','source':'vcf','depth':29}
        recorded={'rsid':'rs1801133','genotype':'CT','source':'pharmacogenomics.json'}
        with patch.object(core,'profile_genotypes',return_value={'rs1801133':recorded}), \
             patch.object(genome,'genotype_from_vcf',return_value=value), \
             patch.object(genome,'_gt_at',return_value=value), \
             patch.object(genome,'available',return_value={'ready':True}):
            a=core.genotype_status('rs1801133')
            b=genome.lookup('rs1801133',allow_network=False)['result']
            c=panel_genotype._genotype('rs1801133','NC_000001.11:g.11796321G>A','MTHFR','T',{'status':'ok'},at=('C','T'))
            d=panel_intake._intake_reading('rs1801133',{'ready':True},recorded=recorded)
        for r in [a,b,c,d]:
            self.assertEqual(r['genotype'],'CC')
            self.assertTrue(r['conflict'])
            self.assertEqual(r['reading_record']['source_digest'],a['reading_record']['source_digest'])
            self.assertFalse(r['interpretation_applicable'])
        self.assertEqual(c['state'],'risk_allele_not_declared')

    def test_sequential_profiles_do_not_share_saved_observations(self):
        with patch.object(core,'pharmacogenomics',return_value={'genotypes':[{'rsid':'rs1','genotype':'AA'}]}), \
             patch.object(core,'read_profile_json',return_value={}):
            first=vr.recorded_genotypes()
        with patch.object(core,'pharmacogenomics',return_value={'genotypes':[{'rsid':'rs1','genotype':'GG'}]}), \
             patch.object(core,'read_profile_json',return_value={}):
            second=vr.recorded_genotypes()
        self.assertEqual(first['rs1']['genotype'],'AA')
        self.assertEqual(second['rs1']['genotype'],'GG')


class TestSitesAgreement(_Reader):
    def test_a_second_sites_file_cannot_silently_disagree_with_the_first_reference(self):
        loc=dict(genome.locus('rs6025'))
        with patch.object(genome,'_sites_vcfs',return_value=['a.vcf','b.vcf']), \
             patch.object(genome,'_query_region',side_effect=lambda file,*_: [row('C','T',gt='0/0' if file=='a.vcf' else '0/1')]):
            r=genome._ref_evidence(loc)
        self.assertEqual(r['confidence'],'conflicting_calls')
        self.assertIsNone(r['genotype'])
        self.assertEqual(len(r['observations']),2)

    def test_matching_reference_calls_retain_all_sources_and_the_best_depth(self):
        loc=dict(genome.locus('rs6025'))
        with patch.object(genome,'_sites_vcfs',return_value=['a.vcf','b.vcf']), \
             patch.object(genome,'_query_region',side_effect=lambda file,*_: [row('C','T',fmt='GT:DP',extra='0/0:'+('3' if file=='a.vcf' else '25'))]):
            r=genome._ref_evidence(loc)
        self.assertEqual(r['depth'],25)
        self.assertEqual(len(r['observations']),2)
        self.assertEqual(r['genotype'],'CC')
