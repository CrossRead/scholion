"""The finite longevity set has reference context without manufactured benefits."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import core, i18n
from scholion.engine import genomics
from scholion.panel_reference import longevity_interpretation

EXPECTED={'rs429358','rs7412','rs2802292','rs12206094','rs2253310','rs4946935','rs2764264','rs13217795','rs2075650'}


class TestNinePositions(unittest.TestCase):
    def test_source_passports_and_no_additive_score(self):
        book=core._read_knowledge_raw('longevity_directions.json')
        self.assertEqual(set(book['_meta']['reviewed_positions_228']),EXPECTED)
        for rs in EXPECTED:
            row=book['directions'][rs]
            self.assertIn(row['level'],'ABCDE');self.assertTrue(row['source'])
            self.assertTrue(row['source_passport']['sources']);self.assertTrue(row['source_passport']['license'])
            self.assertTrue(row['population_caveat']['ru']);self.assertTrue(row['mechanism']['en'])
        self.assertNotIn('29255262',book['directions']['rs12206094']['pmids'])
        self.assertIn('29234056',book['directions']['rs12206094']['pmids'])
        self.assertFalse(book['directions']['rs2075650']['personal_effect_permitted'])

    def test_reference_is_available_before_a_legacy_report_exists(self):
        with patch.object(core,'longevity_data',return_value={}), \
             patch.object(core,'genotype_status',return_value={}), \
             patch.object(genomics,'apoe',return_value={'status':'no_genome'}):
            result=genomics.longevity_findings()
        self.assertTrue(result['available'])
        self.assertEqual({r['rsid'] for r in result['known']},EXPECTED)
        self.assertTrue(all(not r.get('read') and r.get('genotype') is None for r in result['known']))
        self.assertNotIn('score',result)
        pointers=[r['rsid'] for r in result['known'] if r.get('joint_interpretation_pointer')=='apoe']
        self.assertEqual(set(pointers),{'rs429358','rs7412'})

    def test_positive_reading_does_not_imply_an_effect_or_independent_benefit(self):
        spec=core._read_knowledge('longevity_directions.json')['directions']['rs2075650']
        observed={'confidence':'called','genotype':'AG','depth':30,'assembly':'GRCh38','interpretation_applicable':False}
        with patch.object(core,'genotype_status',return_value=observed):
            result=longevity_interpretation({'gene':'TOMM40','rsid':'rs2075650','genotype':'AA','verdict_token':'plus'},spec)
        self.assertEqual(result['genotype'],'AG');self.assertTrue(result['read'])
        self.assertFalse(result['interpretation']['personalized'])
        self.assertIsNone(result['verdict_token']);self.assertIsNone(result['carries_named_allele'])
        self.assertEqual(result['ld_group'],'APOE_region')
        self.assertEqual(result['stored_genotype'],'AA')

    def test_low_quality_never_gets_a_genotype_specific_longevity_sentence(self):
        spec=core._read_knowledge('longevity_directions.json')['directions']['rs2802292']
        for flag in ({'low_depth':True},{'filtered':True},{'imputed':True},{'depth_unverified':True},{'conflict':True}):
            with patch.object(core,'genotype_status',return_value={'confidence':'called','genotype':'GG','depth':30,**flag}):
                r=longevity_interpretation({'gene':'FOXO3','rsid':'rs2802292'},spec)
            self.assertFalse(r['interpretation']['personalized'],flag)
            self.assertEqual(r['genotype'],'GG')

    def test_both_languages_keep_source_retraction_and_phase_limits(self):
        previous=i18n.lang();self.addCleanup(i18n.set_lang,previous)
        for language in ('en','ru'):
            i18n.set_lang(language)
            spec=core._read_knowledge('longevity_directions.json')['directions']['rs12206094']
            with patch.object(core,'genotype_status',return_value={}):
                row=longevity_interpretation({'gene':'FOXO3','rsid':'rs12206094'},spec)
            self.assertIn('29234056',row['interpretation']['source'])
            self.assertIsNone(row['genotype'])
