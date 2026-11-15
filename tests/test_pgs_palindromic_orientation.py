"""A coordinate match cannot resolve a model's palindromic effect allele."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import support  # noqa: F401
from pgs_support import calibrated
from scholion.pgs_scoring import ScoringVCF
from scholion import prs_recompute
from scholion.pgs_validation import recalculation_status, retain_saved_value, validate


class PalindromicOrientation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.vcf, self.model = self.root / 'calls.vcf', self.root / 'model.txt'

    def inputs(self, ref='A', alt='T', gt='0/0', other=None):
        self.vcf.write_text('##fileformat=VCFv4.2\n##reference=GRCh38\n'
                           '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC\n'
                           f'1\t10\t.\t{ref}\t{alt}\t.\tPASS\t.\tGT\t{gt}\n', encoding='utf-8')
        self.model.write_text('#HmPOS_build=GRCh38\n'
                              'hm_chr\thm_pos\teffect_allele\tother_allele\teffect_weight\n'
                              f'1\t10\t{ref}\t{alt if other is None else other}\t0.4\n', encoding='utf-8')

    def score(self, references=()):
        with patch('scholion.core._read_knowledge', return_value={'references':list(references)}):
            reader = ScoringVCF(self.vcf)
            try:
                return reader.score(self.model, 'GRCh38')
            finally:
                reader.close()

    def proof(self):
        return {'model_sha256_by_build':{'GRCh38':hashlib.sha256(self.model.read_bytes()).hexdigest()},
                'allele_orientation':{'status':'verified_forward','scope':'all_scoring_alleles',
                                      'checked_on':'2026-11-15','source':'Synthetic source review'}}

    def test_unknown_orientation_refuses_both_homozygotes_for_both_pairs(self):
        for ref,alt in [('A','T'),('C','G')]:
            for gt in ('0/0','1/1'):
                for other in (None,''):
                    with self.subTest(ref=ref,gt=gt,other=other):
                        self.inputs(ref,alt,gt,other)
                        result = self.score()
                        self.assertFalse(result['scoring_validation']['checked'])
                        self.assertEqual(result['scoring_validation']['counts']['strand_ambiguous'],1)
                        self.assertEqual(result['variants_matched'],0)
                        self.assertEqual(result['scoring_validation']['absent_positions_imputed'],0)

    def test_heterozygous_dosage_is_invariant_under_both_orientations(self):
        for ref,alt in [('A','T'),('C','G')]:
            self.inputs(ref,alt,'0/1')
            result = self.score()
            self.assertTrue(result['scoring_validation']['checked'])
            self.assertAlmostEqual(result['score'],0.4)

    def test_exact_reviewed_model_preserves_known_orientation(self):
        self.inputs()
        proof = self.proof()
        self.assertAlmostEqual(self.score([proof])['score'],0.8)
        self.assertTrue(self.score([proof])['scoring_validation']['checked'])
        variants=[]
        wrong=deepcopy(proof);wrong['model_sha256_by_build']['GRCh38']='0'*64;variants.append(wrong)
        wrong=deepcopy(proof);wrong['model_sha256_by_build']={'GRCh37':proof['model_sha256_by_build']['GRCh38']};variants.append(wrong)
        wrong=deepcopy(proof);wrong['review_required']=True;variants.append(wrong)
        for key in ('scope','status','source','checked_on'):
            wrong=deepcopy(proof);wrong['allele_orientation'].pop(key);variants.append(wrong)
        for wrong in variants:
            self.assertFalse(self.score([wrong])['scoring_validation']['checked'])
        self.model.write_text(self.model.read_text(encoding='utf-8').replace('0.4','0.8'), encoding='utf-8')
        self.assertFalse(self.score([proof])['scoring_validation']['checked'])

    def test_legacy_witness_cannot_retain_a_verified_percentile(self):
        row=calibrated({'pgs_id':'PGS999999','percentile':95.0})
        row['scoring_validation']['algorithm']='scholion-called-alleles-v1'
        result=validate(row)
        self.assertIsNone(result['percentile'])
        self.assertEqual(result['diagnostic_percentile'],95.0)
        self.assertTrue(recalculation_status([row])['required'])
        current=calibrated({'pgs_id':'PGS999999','percentile':95.0})
        current['scoring_validation'].pop('allele_orientation')
        self.assertIsNone(validate(current)['percentile'])

    def test_current_source_ambiguity_requests_review_not_repeated_scoring(self):
        row=calibrated({'pgs_id':'PGS999999','percentile':95.0})
        row['scoring_validation']['checked']=False
        row['scoring_validation']['allele_orientation']['unresolved_rows']=1
        result=validate(row)
        self.assertIn('allele_orientation_unresolved',result['calibration']['reasons'])
        self.assertIsNone(result['percentile'])
        status=recalculation_status([row])
        self.assertFalse(status['required'])
        self.assertTrue(status['source_review_required'])
        retain_saved_value(result)
        self.assertEqual(result['saved_result']['value'],95.0)
        self.assertFalse(result['saved_result']['recalculation_required'])

    def test_malformed_witness_cannot_hide_the_need_to_recheck_a_saved_score(self):
        witnesses = ['invalid', ['invalid'],
                     {'algorithm':'scholion-called-alleles-v2','allele_orientation':'invalid'},
                     {'algorithm':'scholion-called-alleles-v2','allele_orientation':['invalid']}]
        for witness in witnesses:
            with self.subTest(witness=witness):
                row = calibrated({'pgs_id':'PGS999999','percentile':95.0})
                row['scoring_validation'] = witness
                status = recalculation_status([row])
                self.assertTrue(status['required'])
                self.assertFalse(status['source_review_required'])
                result = validate(row)
                self.assertIsNone(result['percentile'])
                self.assertEqual(result['diagnostic_percentile'],95.0)
                self.assertIn('scoring_unverified',result['calibration']['reasons'])

    def test_a_new_exact_model_review_makes_rescoring_useful(self):
        row=calibrated({'term':'synthetic','pgs_id':'PGS999999','percentile':95.0})
        row['scoring_validation'].update(checked=False,genome_build='GRCh38')
        row['scoring_validation']['allele_orientation']['unresolved_rows']=1
        with patch.object(prs_recompute.prs,'_pinned_models',return_value={'synthetic':{'pgs_id':'PGS999999'}}), \
             patch.object(prs_recompute.genome,'vcf_path',return_value=None), \
             patch.object(prs_recompute.prs,'resolve_superpopulation',return_value={'source':'profile','value':'EUR'}):
            for verified in (False,True):
                with patch.object(prs_recompute,'_forward_model_verified',return_value=verified):
                    status=prs_recompute.recalculation_status({'traits':[row]})
                self.assertEqual(status['required'],verified)
                if verified:
                    self.assertEqual(status['reason'],'allele_orientation_reviewed')


if __name__ == '__main__':
    unittest.main()
