"""A real recalculation, not a read-only probe, preserves input and trust boundaries."""
from __future__ import annotations

import gzip
import io
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import support
from scholion import cli, core, pgs_results, prs, prs_recompute, recompute
from scholion.pgs_validation import recalculation_status, scoring_verified
from scholion.prs import _MCP as MCPClient


class Sidecar:
    reference_contract_verified = True
    def call(self, name, args):
        if name == "compute_prs":
            return {"pgs_id": args["pgs_id"], "score": 100, "percentile": 100}
        if name == "percentile":
            score = args["prs_score"]
            return {"percentile": 50 * math.erfc(-score / math.sqrt(2)),
                    "method": "reference_panel", "reliable": True,
                    "reference_mean": 0, "reference_std": 1, "z_score": score,
                    "reference_panel": "synthetic", "reference_panel_ancestry": "EUR"}
        raise AssertionError(name)
    def close(self):
        pass


class Recalculation(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.profile = self.root / 'profile'
        self.profile.mkdir()
        self.addCleanup(support.pin_profile(self.profile))
        self.vcf = self.root / 'calls.vcf'
        self.vcf.write_text('##fileformat=VCFv4.2\n##reference=GRCh38\n'
                            '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC\n'
                            '1\t1\t.\tA\tG\t50\tPASS\t.\tGT:DP\t0/1:30\n'
                            '1\t2\t.\tA\t.\t50\tPASS\t.\tGT:DP\t0/0:30\n', encoding='utf-8')
        cache = self.root / 'cache' / 'scores'
        cache.mkdir(parents=True)
        self.model = cache / 'PGS000001_hmPOS_GRCh38.txt.gz'
        with gzip.open(self.model, 'wt', encoding='utf-8') as stream:
            stream.write('#HmPOS_build=GRCh38\n#genome_build=GRCh37\n'
                         'hm_chr\thm_pos\teffect_allele\tother_allele\teffect_weight\n'
                         '1\t1\tG\tA\t0.2\n1\t2\tG\tA\t0.8\n')
        self.old = {'traits': [{'term': 'synthetic', 'label': 'Synthetic',
                               'pgs_id': 'PGS000001', 'percentile': 100, 'reliable': True}]}
        self.path = self.profile / 'prs_results.json'
        self.path.write_text(json.dumps(self.old), encoding='utf-8')
        self.original = self.path.read_bytes()
        for patch in (
            mock.patch.dict(os.environ, {'SCHOLION_PRS_VCF': str(self.vcf), 'PRS_MCP_CACHE_DIR': str(cache.parent)}),
            mock.patch.object(prs, '_load_traits', return_value=[{'term': 'synthetic', 'label': 'Synthetic'}]),
            mock.patch.object(prs, '_pinned_models', return_value={'synthetic': {'pgs_id': 'PGS000001'}}),
            mock.patch.object(prs, 'resolve_superpopulation', return_value={'value': 'EUR', 'source': 'stated'}),
            mock.patch.object(prs, '_MCP', return_value=Sidecar()),
            mock.patch.object(prs_recompute.shutil, 'which', return_value='/synthetic/uvx'),
            mock.patch('scholion.genome.vcf_path', return_value=self.vcf),
            mock.patch('scholion.gene_region.bam_path', return_value=None),
            mock.patch('scholion.updates.last_used', return_value=None),
        ):
            patch.start()
            self.addCleanup(patch.stop)
        core.reset_cache()
        self.addCleanup(core.reset_cache)

    def run_calculation(self, **kwargs):
        return prs_recompute.calculate(confirm=True, **kwargs)

    def test_confirmation_is_required_and_reading_starts_no_work(self):
        with mock.patch.object(prs_recompute, '_models') as prepare:
            r = prs_recompute.calculate()
            self.assertEqual('not_confirmed', r['status'])
            prepare.assert_not_called()
        self.assertEqual(self.original, self.path.read_bytes())

    def test_full_operation_scores_flattens_backs_up_and_does_not_repeat_on_update(self):
        with mock.patch.object(prs_recompute, '_augment') as augment:
            result = self.run_calculation()
            augment.assert_not_called()
        self.assertTrue(result['ok'], result)
        self.assertEqual(self.original, Path(result['backup']).read_bytes())
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        row = stored['traits'][0]
        self.assertAlmostEqual(0.2, row['score'])
        self.assertTrue(row['reliable'], row)
        self.assertNotIn('chosen', row)
        self.assertFalse(recalculation_status(stored['traits'])['required'])
        self.assertEqual(self.old['traits'][0]['percentile'], row['previous_result']['percentile'])
        self.assertFalse(any(s.get('key') == 'scholion prs' for s in recompute.plan(text='')['steps']))

    def test_unavailable_calibration_keeps_scored_diagnostics_and_never_p100(self):
        sidecar = Sidecar()
        original = sidecar.call
        def fallback(name, args):
            if name == 'percentile':
                return {'method': 'auroc_fallback', 'percentile': 100, 'reliable': True}
            return original(name, args)
        with mock.patch.object(sidecar, 'call', side_effect=fallback), mock.patch.object(prs, '_MCP', return_value=sidecar):
            result = self.run_calculation()
        self.assertTrue(result['ok'], result)
        row = json.loads(self.path.read_text(encoding='utf-8'))['traits'][0]
        self.assertFalse(row['reliable'])
        self.assertIsNone(row['percentile'])
        self.assertTrue(scoring_verified(row))

    def test_missing_vcf_calls_are_not_imputed_and_vcf_only_is_usable_input(self):
        text = self.vcf.read_text(encoding='utf-8')
        self.vcf.write_text(text[:text.rfind('1\t2\t')], encoding='utf-8')
        result = self.run_calculation()
        self.assertTrue(result['ok'], result)
        self.assertEqual('vcf_only', result['preparation'])
        row = json.loads(self.path.read_text(encoding='utf-8'))['traits'][0]
        self.assertEqual(0.5, row['match_rate'])
        self.assertFalse(row['reliable'])
        self.assertEqual(0, row['scoring_validation']['absent_positions_imputed'])

    def test_failure_and_cancellation_preserve_original_bytes(self):
        with mock.patch.object(prs, 'report', side_effect=RuntimeError('synthetic scorer failed')):
            result = self.run_calculation()
        self.assertEqual('failed', result['status'])
        self.assertEqual(self.original, self.path.read_bytes())
        result = self.run_calculation(stop=lambda: True)
        self.assertEqual('stopped', result['status'])
        self.assertEqual(self.original, self.path.read_bytes())

    def test_failed_or_empty_nested_results_never_replace_the_profile(self):
        for bad in [{'ok': False, 'traits': []}, {'ok': True, 'traits': []},
                    {'ok': True, 'traits': [{'term': 'synthetic', 'status': 'error'}]}]:
            with mock.patch.object(prs, 'report', return_value=bad):
                self.assertEqual('failed', self.run_calculation()['status'])
            self.assertEqual(self.original, self.path.read_bytes())

    def test_moved_report_without_input_is_readable_and_plan_names_the_gap(self):
        self.vcf.unlink()
        plan = prs_recompute.preflight()
        self.assertEqual(('needs_input', 'no_input'), (plan['status'], plan['reason']))
        self.assertEqual(self.original, self.path.read_bytes())
        self.assertIn('VCF', plan['message'])

    def test_wrong_assembly_and_sample_are_refused_before_scoring(self):
        text = self.vcf.read_text(encoding='utf-8')
        self.vcf.write_text(text.replace('##reference=GRCh38\n', ''), encoding='utf-8')
        self.assertEqual('build_unknown', prs_recompute.preflight()['reason'])
        self.vcf.write_text(text, encoding='utf-8')
        from scholion import genome
        genome.assembly_evidence.cache_clear()
        with mock.patch.object(core, 'ancestry_check', return_value={'samples': ['OTHER']}):
            self.assertEqual('sample_mismatch', prs_recompute.preflight()['reason'])
        self.assertEqual(self.original, self.path.read_bytes())

    def test_unknown_population_is_not_an_implicit_eur_default(self):
        with mock.patch.object(prs, 'resolve_superpopulation', return_value={'value': 'EUR', 'source': 'default'}):
            self.assertEqual('population_unknown', prs_recompute.preflight()['reason'])

    def test_the_new_runner_is_executable_and_records_failed_and_stopped_states(self):
        plan = recompute.plan(prs_only=True, force_prs=True)
        self.assertEqual(1, plan['ready'])
        self.assertEqual('scholion prs --recalculate --yes', plan['steps'][0]['command'])
        with mock.patch.object(prs_recompute, 'calculate', return_value={'ok': False, 'status': 'stopped'}):
            result = recompute.run(confirm=True, prs_only=True, force_prs=True)
        self.assertEqual('stopped', result['job']['status'])
        self.assertEqual(self.original, self.path.read_bytes())

    def test_status_is_a_successful_read_even_when_a_job_is_running(self):
        with mock.patch.object(recompute, 'status', return_value={'status': 'running', 'started': '2026-01-01'}), \
             mock.patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(0, cli.main(['recompute', '--status', '--json']))

    def test_per_call_host_uses_a_separate_pgs_worker(self):
        from scholion import prs_worker
        with mock.patch.dict(os.environ, {'SCHOLION_MANAGED_BY': 'Synthetic per-call host'}), \
             mock.patch.object(prs_worker, 'start', return_value={'started': True, 'steps': 1}) as start:
            self.assertTrue(recompute.start_in_background()['started'])
        start.assert_called_once()

    def test_cli_calls_the_packaged_operation_and_reports_nonzero_failure(self):
        with mock.patch.object(prs_recompute, 'calculate', return_value={'ok': False, 'status': 'failed'}), \
             mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            status = cli.main(['prs', '--recalculate', '--yes', '--json'])
        self.assertEqual(1, status)
        self.assertEqual('failed', json.loads(out.getvalue())['job']['status'])

    def test_mcp_plan_has_same_executable_runner_as_cli_and_web(self):
        from scholion import ouroboros_tools as ot
        ot.unpin_session()
        self.addCleanup(ot.unpin_session)
        tools = {t.name: t for t in ot.get_tools()}
        text = tools['sch_recompute'].handler(ot.ToolContext())
        self.assertIn('scholion prs --recalculate --yes', text)
        self.assertNotIn('src/ingest', text)

    def test_changed_input_and_population_request_work_but_version_alone_does_not(self):
        self.assertTrue(self.run_calculation()['ok'])
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertFalse(prs_recompute.recalculation_status(stored)['required'])
        stored['_meta']['engine'] = '0.0.0'
        self.assertFalse(prs_recompute.recalculation_status(stored)['required'])
        with mock.patch.object(prs, 'resolve_superpopulation', return_value={'value': 'AFR', 'source': 'stated'}):
            self.assertEqual('population_changed', prs_recompute.recalculation_status(stored)['reason'])
        self.vcf.write_text(self.vcf.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        self.assertEqual('input_changed', prs_recompute.recalculation_status(stored)['reason'])

    def test_unpinned_diagnostics_do_not_request_an_unfinishable_repeat_job(self):
        with mock.patch.object(prs, '_pinned_models', return_value={}):
            self.assertFalse(prs_recompute.recalculation_status(self.old)['required'])

    def test_model_file_change_requires_recalculation(self):
        self.assertTrue(self.run_calculation()['ok'])
        stored = json.loads(self.path.read_text(encoding='utf-8'))
        with gzip.open(self.model, 'at', encoding='utf-8') as stream:
            stream.write('1\t1\tG\tA\t0.1\n')
        self.assertEqual('model_changed', prs_recompute.recalculation_status(stored)['reason'])

    def test_mcp_stop_calls_the_same_operation(self):
        from scholion import ouroboros_tools as ot
        ot.unpin_session()
        self.addCleanup(ot.unpin_session)
        tool = {t.name: t for t in ot.get_tools()}['sch_recompute']
        with mock.patch.object(recompute, 'stop', return_value={'ok': True, 'status': 'no_job'}) as stop:
            tool.handler(ot.ToolContext(), stop=True)
        stop.assert_called_once()

    def test_waiting_scorer_can_be_cancelled_and_timed_out(self):
        import queue
        client = MCPClient.__new__(MCPClient)
        client._lines = queue.Queue()
        client.timeout = 1
        client.cancelled = lambda: True
        with self.assertRaises(prs.PrsCancelled):
            client._read_id(1)
        client.cancelled = None
        client.timeout = 0.001
        with self.assertRaises(prs.PrsUnavailable):
            client._read_id(1)

    def test_model_identity_and_old_schema_are_checked_before_storage(self):
        with mock.patch.object(prs, '_pinned_models', return_value={'synthetic': {'pgs_id': 'PGS999999'}}):
            result = self.run_calculation()
        self.assertFalse(result['ok'])
        self.assertEqual(self.original, self.path.read_bytes())
        with self.assertRaises(ValueError):
            pgs_results.merge({'ok': True, 'traits': [{}]}, self.old, {})
        self.assertEqual(self.original, self.path.read_bytes())


if __name__ == '__main__':
    unittest.main()
