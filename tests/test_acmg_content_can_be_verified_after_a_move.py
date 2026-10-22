"""A content check is explicit, cheaper than a clinical scan and fail-safe."""
from __future__ import annotations

import hashlib
import json
import os
from unittest import mock

import support  # noqa: F401
from scholion import acmg_identity, acmg_scan, genome, recompute
from tests.test_an_acmg_table_is_read_with_its_provenance import _Table, hit
from tests.test_the_acmg_screen_can_be_run_from_the_package import (
    _Files, vcf, personal_row, brca1_clinvar,
)


class TestAnExplicitContentCheck(_Table):
    def current(self):
        personal = self.dir / 'me.vcf.gz'
        self.write([hit('BRCA1', 'yes')], {
            'assembly': 'GRCh38', 'clinvar_assembly': 'GRCh38', 'schema_version': 2,
            'personal_sha256': hashlib.sha256(personal.read_bytes()).hexdigest(),
            'catalogue_sha256': acmg_identity.catalogue_digest(),
            'catalogue_version': '3.3', 'rules_version': acmg_identity.RULES_VERSION,
        })
        return personal

    def test_moved_content_is_preserved_until_an_explicit_verification(self):
        personal = self.current()
        table = self.dir / acmg_scan.OUT_NAME
        original = table.read_bytes()
        other = self.dir / 'moved.vcf.gz'
        other.write_bytes(personal.read_bytes())
        with mock.patch.object(genome, 'vcf_path', return_value=other):
            before = genome.acmg_sf_findings()
            self.assertEqual(before['reason'], 'source_verification_needed')
            self.assertEqual(before['hits'], [])
            self.assertEqual(before['saved_hits'][0]['gene'], 'BRCA1')
            self.assertTrue(before['saved_unverified'])
            self.assertEqual(before['recalculation']['operation'], 'verify')
            result = acmg_identity.verify()
            self.assertEqual(result['status'], 'ok', result)
            self.assertEqual(table.read_bytes(), original)
            with mock.patch.object(acmg_identity, 'fingerprint', side_effect=AssertionError('read rehashed')):
                after = genome.acmg_sf_findings()
                self.assertEqual(after['status'], 'ok', after)
                self.assertEqual(after['reportable'][0]['gene'], 'BRCA1')

    def test_same_length_edit_does_not_certify_changed_content(self):
        personal = self.current()
        meta_path = self.dir / acmg_scan.META_NAME
        saved = meta_path.read_bytes()
        original = personal.read_bytes(); stamp = personal.stat()
        personal.write_bytes(original[:-1]+bytes([original[-1]^1]))
        os.utime(personal, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertEqual(acmg_identity.verify()['reason'], 'source_changed')
        self.assertEqual(meta_path.read_bytes(), saved)

    def test_legacy_without_a_content_digest_is_not_certified_by_guessing(self):
        self.write([hit('BRCA1', 'yes')], {'assembly': 'GRCh38', 'clinvar_assembly': 'GRCh38'})
        before = (self.dir / acmg_scan.META_NAME).read_bytes()
        self.assertEqual(acmg_identity.verify()['reason'], 'metadata_unverified')
        self.assertEqual((self.dir / acmg_scan.META_NAME).read_bytes(), before)

    def test_a_changed_catalogue_requires_a_clinical_update_not_identity_verification(self):
        self.current()
        with mock.patch.object(acmg_identity, 'catalogue_digest', return_value='new catalogue'):
            result = genome.acmg_sf_findings()
            self.assertEqual(result['reason'], 'knowledge_changed')
            self.assertEqual(result['recalculation']['operation'], 'scan')
            self.assertEqual(result['saved_hits'][0]['gene'], 'BRCA1')
            self.assertEqual(acmg_identity.verify()['reason'], 'knowledge_changed')

    def test_stop_during_verification_keeps_both_halves(self):
        self.current()
        paths = [self.dir / name for name in (acmg_scan.OUT_NAME, acmg_scan.META_NAME)]
        before = [p.read_bytes() for p in paths]
        def stop(*args):
            raise recompute.Stopped()
        with self.assertRaises(recompute.Stopped):
            acmg_identity.verify(progress=stop)
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_a_source_change_during_hashing_is_detected(self):
        personal = self.current()
        def edit(*args):
            personal.write_bytes(personal.read_bytes()+b'changed')
        with self.assertRaises(OSError):
            acmg_identity.fingerprint(personal, edit)

    def test_a_data_driven_plan_offers_verification_without_clinvar_or_bam(self):
        personal = self.current()
        other = self.dir / 'move.vcf.gz'; other.write_bytes(personal.read_bytes())
        with mock.patch.object(genome, 'vcf_path', return_value=other), \
                mock.patch('scholion.coverage.clinvar_path', return_value=None):
            p = recompute.plan(since='0.7.1', text='')
        steps = [s for s in p['steps'] if s.get('key') == 'scholion acmg-scan']
        self.assertEqual(len(steps), 1, p)
        self.assertEqual(steps[0]['operation'], 'verify')
        self.assertEqual(steps[0]['state'], 'ready')
        self.assertIn('--verify-only', steps[0]['command'])

    def test_a_selected_sample_change_during_verification_cannot_certify_the_old_selection(self):
        self.current()
        before = (self.dir / acmg_scan.META_NAME).read_bytes()
        real = acmg_identity.fingerprint
        changed = [False]
        def fingerprint(*args):
            result = real(*args)
            changed[0] = True
            return result
        with mock.patch.object(acmg_identity, 'fingerprint', side_effect=fingerprint), \
                mock.patch.object(genome, 'sample_index', side_effect=lambda *_: 1 if changed[0] else 0):
            self.assertEqual(acmg_identity.verify()['reason'], 'sample_changed')
        self.assertEqual((self.dir / acmg_scan.META_NAME).read_bytes(), before)

    def test_a_failed_metadata_save_preserves_the_table(self):
        self.current()
        before = (self.dir / acmg_scan.OUT_NAME).read_bytes()
        old_meta = (self.dir / acmg_scan.META_NAME).read_bytes()
        with mock.patch.object(acmg_scan, '_atomic_bytes', side_effect=OSError('disk full')):
            result = acmg_identity.verify()
        self.assertEqual(result['status'], 'verification_refused')
        self.assertEqual((self.dir / acmg_scan.OUT_NAME).read_bytes(), before)
        self.assertEqual((self.dir / acmg_scan.META_NAME).read_bytes(), old_meta)


class TestTheNewScannerWitness(_Files):
    def test_clinvar_changed_after_indexing_preserves_the_previous_result(self):
        personal = vcf(self.dir / 'me.vcf.gz', 'GRCh38', [personal_row('17', 43092919, 'G', 'A')])
        clinical = brca1_clinvar(self.dir)
        self.assertEqual(acmg_scan.scan(str(personal), str(clinical), str(self.dir))['status'], 'ok')
        files = [self.dir / name for name in (acmg_scan.OUT_NAME, acmg_scan.META_NAME)]
        before = [path.read_bytes() for path in files]
        index = acmg_scan._index

        def replaced_source(*args):
            result = index(*args)
            clinical.write_bytes(clinical.read_bytes() + b'changed after indexing')
            return result

        with mock.patch.object(acmg_scan, '_index', side_effect=replaced_source):
            result = acmg_scan.scan(str(personal), str(clinical), str(self.dir))
        self.assertEqual(result['status'], 'source_changed')
        self.assertEqual([path.read_bytes() for path in files], before)

    def test_scanning_hashes_the_exact_compressed_source_and_records_both_sources(self):
        personal = vcf(self.dir / 'me.vcf.gz', 'GRCh38', [personal_row('17', 43092919, 'G', 'A')])
        clinical = brca1_clinvar(self.dir)
        result = acmg_scan.scan(str(personal), str(clinical), str(self.dir))
        self.assertEqual(result['status'], 'ok', result)
        meta = acmg_scan.read_meta(self.dir)
        self.assertEqual(meta['personal_sha256'], hashlib.sha256(personal.read_bytes()).hexdigest())
        self.assertEqual(meta['clinvar_sha256'], hashlib.sha256(clinical.read_bytes()).hexdigest())
        self.assertEqual(meta['rules_version'], acmg_identity.RULES_VERSION)

    def test_second_half_write_failure_keeps_the_previous_pair(self):
        personal = vcf(self.dir / 'me.vcf.gz', 'GRCh38', [personal_row('17', 43092919, 'G', 'A')])
        clinical = brca1_clinvar(self.dir)
        acmg_scan.scan(str(personal), str(clinical), str(self.dir))
        files = [self.dir / name for name in (acmg_scan.OUT_NAME, acmg_scan.META_NAME)]
        before = [p.read_bytes() for p in files]
        real = acmg_scan._atomic_bytes; count = [0]
        def fail_second(path, content):
            count[0] += 1
            if count[0] == 2:
                raise OSError('synthetic failed metadata write')
            return real(path, content)
        with mock.patch.object(acmg_scan, '_atomic_bytes', side_effect=fail_second):
            with self.assertRaises(OSError):
                acmg_scan.scan(str(personal), str(clinical), str(self.dir))
        self.assertEqual([p.read_bytes() for p in files], before)


from tests.test_every_door_of_the_local_server_answers import _Live  # noqa: E402


class TestACMGWebParity(_Live):
    def test_the_web_does_not_replace_unverified_history_with_a_clean_negative(self):
        for lang in ('en', 'ru'):
            result = {'status':'table_unverified', 'hits':[], 'reportable':[],
                      'saved_unverified':True, 'saved_hits':[{'gene':'BRCA1','rsid':'rs1'}],
                      'recalculation':{'operation':'verify','command':'scholion acmg-scan --verify-only'}}
            with mock.patch('scholion.engine.acmg_findings', return_value=result):
                code, text = self.call('/api/acmg?lang='+lang)
            self.assertEqual(code, 200)
            self.assertEqual(json.loads(text), result)
