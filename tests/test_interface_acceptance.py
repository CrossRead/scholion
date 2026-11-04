"""Executable level-five selection and comparison cannot silently lose meaning."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import support
from scholion import contract

sys.path.insert(0, str(support.ROOT / 'src/tools'))
import check_interfaces as checks  # noqa: E402


class InterfaceAcceptance(unittest.TestCase):
    def test_research_meaning_survives_every_adapter_and_low_depth(self):
        from scholion import container, core, i18n, ouroboros_tools
        from tests.test_a_file_without_an_index_is_still_a_file import bgzf, vcf_text

        rsid = 'rs13217795'
        locus = core.loci()['loci'][rsid]
        case = checks.Scenario('research-meaning', ('genome', rsid), 'GET /api/genome',
                               {'rsid': rsid}, 'rsid=' + rsid)
        self.addCleanup(i18n.set_lang, i18n.lang())
        self.addCleanup(ouroboros_tools.unpin_session)
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary).resolve()
            profile = work / 'profile'
            profile.mkdir()
            for gt, depth, expected in (('1/1', 23, 'genotype_hypothesis'),
                                        ('0/1', 23, 'genotype_hypothesis'),
                                        ('1/1', 3, 'reference_only')):
                path = work / f'{gt.replace("/", "-")}-{depth}.vcf.gz'
                content = vcf_text([[str(locus['chrom']), str(locus['pos']), rsid,
                    locus['ref'], 'T', '60', 'PASS', '.', 'GT:DP', f'{gt}:{depth}']])
                path.write_bytes(bgzf(content.replace(b'ID=19,length=58617616', b'ID=6,length=170805979')))
                for language in ('en', 'ru'):
                    env = {**support.env(profile, lang=language), 'SCHOLION_GENOME_VCF': str(path),
                           'SCHOLION_GENOME_ASSEMBLY': 'GRCh38', 'SCHOLION_GENOME_DIR': str(work / 'none'),
                           'SCHOLION_CACHE_DIR': str(work / 'cache')}
                    with self.subTest(gt=gt, depth=depth, language=language), mock.patch.dict(os.environ, env):
                        i18n.set_lang(language)
                        container.ensure()
                        ouroboros_tools.unpin_session()
                        entries = {entry.name: entry for entry in ouroboros_tools.get_tools()}
                        with checks.http_server() as base:
                            checks.read_case(case, base, env, entries, None)
                        data = checks.cli(case.command, env)
                        result = data['personal_meaning']
                        self.assertEqual(expected, result['status'], data.get('result'))
                        self.assertIn('34436732', str(result['sources']))
                        self.assertFalse(result['clinical_eligibility_upgrade'])

    def test_selection_uses_routes_and_keeps_both_system_registers(self):
        selected, write = checks.select(['system'], contract.PARITY, contract.PLUGIN)
        self.assertEqual({'system-patient', 'system-clinician', 'systems-list', 'mitochondrial-system', 'mitochondrial-system-clinician'}, {s.name for s in selected})
        self.assertFalse(write)
        selected, write = checks.select(['focus-log'], contract.PARITY, contract.PLUGIN)
        self.assertEqual([], selected)
        self.assertTrue(write)

    def test_unknown_capabilities_or_changed_contract_refuse_acceptance(self):
        for commands, parity, plugins in (
            (['not-a-command'], contract.PARITY, contract.PLUGIN),
            (['metrics'], {**contract.PARITY, 'GET /api/metrics': 'labs'}, contract.PLUGIN),
            (['metrics'], contract.PARITY, {}),
            (['focus-log'], {}, contract.PLUGIN),
        ):
            with self.subTest(commands=commands), self.assertRaises(ValueError):
                checks.select(commands, parity, plugins)

    def test_comparison_retains_dates_sources_qualifications_and_actions(self):
        data = {'container': {'id': 'synthetic'}, 'value': 42, 'date': '2026-01-01',
                'source': 'synthetic-lab', 'qualified': True,
                'action': {'available': False, 'reason': 'missing_input'}}
        for key in ('value', 'date', 'source', 'qualified', 'action'):
            changed = {**data, key: None}
            with self.subTest(field=key), self.assertRaises(AssertionError):
                checks.equal(checks.payload(data), checks.payload(changed), 'different meaning')

    def test_actual_write_adapters_refuse_and_persist_equivalently(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary).resolve() / 'evidence.json'
            result = subprocess.run([sys.executable, str(support.ROOT / 'src/tools/check_interfaces.py'),
                                     '--commands', 'focus-log', '--out', str(out)],
                                    env=support.env(), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            evidence = json.loads(out.read_text(encoding='utf-8'))
            self.assertTrue(evidence['ok'])
            self.assertTrue(evidence['profile_preserved'])
            self.assertEqual(['en', 'ru'], [r['language'] for r in evidence['checks']])
            self.assertTrue(all(r['equal_persisted_records'] for r in evidence['checks']))
            self.assertIn('recompute', evidence['unexercised_commands'])
            original = out.read_bytes()
            repeated = subprocess.run([sys.executable, str(support.ROOT / 'src/tools/check_interfaces.py'),
                                       '--out', str(out)], env=support.env(), stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
            self.assertNotEqual(0, repeated.returncode)
            self.assertEqual(original, out.read_bytes())

    def test_one_snp_keeps_the_call_and_no_call_explanation_across_surfaces(self):
        from scholion import i18n, mcp_server
        from tests.test_a_file_without_an_index_is_still_a_file import bgzf, vcf_text

        rsid = 'rs429358'
        name = 'sch_genome_lookup'
        command = ('genome', rsid)
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary).resolve()
            profile = work / 'profile'
            profile.mkdir()
            self.addCleanup(i18n.set_lang, i18n.lang())
            for gt, state, genotype in (('0/1', 'called', 'TC'), ('./.', 'no_call_in_vcf', None)):
                path = work / (state + '.vcf.gz')
                row = ['19', '44908684', rsid, 'T', 'C', '60', 'PASS', '.', 'GT:DP', gt + ':32']
                path.write_bytes(bgzf(vcf_text([row])))
                for language in ('en', 'ru'):
                    with self.subTest(state=state, language=language):
                        env = {**support.env(profile, lang=language),
                               'SCHOLION_GENOME_VCF': str(path),
                               'SCHOLION_GENOME_ASSEMBLY': 'GRCh38',
                               'SCHOLION_GENOME_DIR': str(work / 'no-genome'),
                               'SCHOLION_CACHE_DIR': str(work / 'cache')}
                        with mock.patch.dict(os.environ, env), checks.http_server() as base:
                            i18n.set_lang(language)
                            status, web = checks.request(base, '/api/genome?rsid=' + rsid + '&lang=' + language)
                        self.assertEqual(200, status)
                        cli = checks.cli(command, env)
                        reply = checks.rpc([sys.executable, '-m', 'scholion', 'mcp'], name, {'rsid': rsid}, env)
                        self.assertFalse(reply['isError'], reply)
                        self.assertIn('structuredContent', reply)
                        result = reply['structuredContent']
                        report = result.pop(mcp_server.REPORT_FIELD)
                        self.assertEqual(checks.payload(cli), checks.payload(web))
                        self.assertEqual(checks.payload(cli), checks.payload(result))
                        self.assertEqual(report, reply['content'][0]['text'])
                        self.assertIn(checks.cli(command, env, as_json=False), report)
                        reading = web['result']
                        self.assertEqual((state, genotype), (reading['confidence'], reading['genotype']))
                        self.assertEqual(('GRCh38', 44908684), (reading['assembly'], reading['read_pos']))
                        if genotype is not None:
                            self.assertEqual(32, reading['reading_record']['observations'][0]['quality']['depth'])
                        else:
                            self.assertEqual(i18n.t('genome.no_call_in_vcf'), reading['note'])
                            self.assertIn(reading['note'], report)
