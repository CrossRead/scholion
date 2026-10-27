"""Regression cases for the technical release: unchanged success, safe refusal."""
from __future__ import annotations

import email.message
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import gene_card_support
import support
from scholion import acmg_scan, core, genome, server, i18n
from scholion.clinvar_reference import header_metadata
from tests import test_acmg_content_can_be_verified_after_a_move as content_tests
from tests.test_the_acmg_screen_can_be_run_from_the_package import _Files, vcf, personal_row, clinvar_row


class RequestFraming(unittest.TestCase):
    def test_unsupported_framing_never_becomes_an_empty_request(self):
        for pairs in ([('Transfer-Encoding', 'chunked')],
                      [('Transfer-Encoding', 'identity'), ('Content-Length', '2')],
                      [('Content-Length', '2'), ('Content-Length', '2')]):
            headers = email.message.Message()
            for key, value in pairs:
                headers[key] = value
            body = io.BytesIO(b'2\r\n{}\r\n0\r\n\r\n')
            handler = types.SimpleNamespace(headers=headers, rfile=body, _json=mock.Mock())
            self.assertIsNone(server.Handler._read_body(handler))
            self.assertEqual(0, body.tell())
            self.assertEqual(400, handler._json.call_args.args[1])
            self.assertTrue(handler.close_connection)

    def test_normal_json_is_unchanged(self):
        handler = types.SimpleNamespace(headers={'Content-Length': '12'},
                                        rfile=io.BytesIO(b'{"path":"x"}'), _json=mock.Mock())
        self.assertEqual({'path': 'x'}, server.Handler._read_body(handler))
        handler._json.assert_not_called()


class SmallContentIdentity(unittest.TestCase):
    def test_coarse_stat_collision_cannot_accept_changed_bytes(self):
        fixture = content_tests.TestAnExplicitContentCheck('test_same_length_edit_does_not_certify_changed_content')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.tearDown)
        real = acmg_scan.source_identity
        def coarse(path):
            result = real(path)
            result['st_ctime_ns'] = 0
            result['change_time'] = None
            return result
        with mock.patch.object(acmg_scan, 'source_identity', side_effect=coarse):
            personal = fixture.current()
            old = personal.read_bytes(); stamp = personal.stat()
            personal.write_bytes(old[:-1] + bytes([old[-1] ^ 1]))
            os.utime(personal, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            answer = genome.acmg_sf_findings()
            self.assertEqual('table_unverified', answer['status'])
            self.assertTrue(answer['saved_hits'])

    def test_previous_full_digest_migrates_without_rescan(self):
        fixture = content_tests.TestAnExplicitContentCheck('test_same_length_edit_does_not_certify_changed_content')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.tearDown)
        fixture.current()
        path = fixture.dir / acmg_scan.META_NAME
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata['personal_identity'].pop('sha256')
        path.write_text(json.dumps(metadata), encoding="utf-8")
        self.assertEqual('ok', genome.acmg_sf_findings()['status'])

    def test_large_witness_does_not_hash_a_genome_on_read(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'large'
            with p.open('wb') as f:
                f.truncate(9 * 1024 * 1024)
            self.assertNotIn('sha256', acmg_scan.source_identity(p))


class AlleleSpecificReference(_Files):
    def test_explicit_per_allele_classification_matches_only_carried_allele(self):
        for alts, sig, gt, found in [('A,T', 'Benign,Pathogenic', '0/2', 1),
                                    ('A,T', 'Benign,Pathogenic', '0/1', 0),
                                    ('T,A', 'Pathogenic,Benign', '1/2', 1),
                                    ('T,A', 'Pathogenic,Benign', './1', 1),
                                    ('A,T', 'Benign,Pathogenic', '1/1', 0),
                                    ('A,T', 'Benign,Pathogenic', '2/2', 1)]:
            with self.subTest(alts=alts, gt=gt):
                clinical = vcf(self.dir / 'cv.vcf.gz', 'GRCh38',
                    [clinvar_row('17', '43092919', 'G', alts, 'BRCA1', sig=sig)],
                    clinvar=True, sample=False,
                    extra=('##INFO=<ID=CLNSIG,Number=A,Type=String,Description="Per allele">',))
                personal = vcf(self.dir / 'me.vcf.gz', 'GRCh38',
                               [personal_row('17', '43092919', 'G', alts, gt=gt)])
                answer = acmg_scan.scan(str(personal), str(clinical), str(self.dir))
                self.assertEqual('ok', answer['status'], answer)
                lines = (self.dir / acmg_scan.OUT_NAME).read_text(encoding="utf-8").splitlines()[1:]
                self.assertEqual(found, len(lines))
                if lines:
                    self.assertIn('\tT\t', lines[0])

    def test_ambiguous_source_preserves_previous_table(self):
        clinical = vcf(self.dir / 'cv.vcf.gz', 'GRCh38',
                    [clinvar_row('17', '43092919', 'G', 'A,T', 'BRCA1')], clinvar=True, sample=False)
        personal = vcf(self.dir / 'me.vcf.gz', 'GRCh38',
                       [personal_row('17', '43092919', 'G', 'T')])
        table = self.dir / acmg_scan.OUT_NAME
        table.write_bytes(b'previous result')
        result = acmg_scan.scan(str(personal), str(clinical), str(self.dir))
        self.assertEqual('clinvar_allele_ambiguous', result['status'])
        self.assertEqual(b'previous result', table.read_bytes())


class ReferenceAssembly(unittest.TestCase):
    def test_reference_uri_and_lengths_are_supported(self):
        self.assertEqual('GRCh38', header_metadata(['##reference=file:///references/GRCh38.fa'])['assembly'])
        self.assertEqual('GRCh37', header_metadata(['##reference=GRCh38', '##contig=<ID=1,length=249250621>'])['assembly'])
        self.assertIsNone(header_metadata(['##contig=<ID=1,length=249250621>', '##contig=<ID=2,length=242193529>'])['assembly'])


class HostContext(unittest.TestCase):
    def test_installed_host_constructor_does_not_break_mcp(self):
        # A strict host-shaped registry in a fresh process, not a patched global
        # already imported by other tests. The real checkout is checked at release.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / 'ouroboros' / 'tools'
            package.mkdir(parents=True)
            (root / 'ouroboros/__init__.py').touch()
            (package / '__init__.py').touch()
            (package / 'registry.py').write_text('''from dataclasses import dataclass
@dataclass
class ToolContext:
    repo_dir: object
    drive_root: object
@dataclass
class ToolEntry:
    name: str
    schema: dict
    handler: object
    is_code_tool: bool = False
    timeout_sec: int = 360
    mutates_worktree: bool = False
''', encoding='utf-8')
            code = '''
from pathlib import Path
from scholion import ouroboros_tools as o, mcp_server as m
from ouroboros.tools.registry import ToolContext
assert o._HAVE_OURO
for version in ('2024-11-05', '2025-11-25', '2026-07-28'):
    for name in ('sch_rules', 'sch_analyze_labs'):
        result = m.call_tool(name, {}, version)
        assert not result.get('isError'), result
entry = next(t for t in o.get_tools() if t.name == 'sch_rules')
assert entry.handler(ToolContext(Path('.'), Path('.')))
'''
            env = dict(os.environ, PYTHONPATH=str(root) + os.pathsep + os.environ.get('PYTHONPATH', ''))
            result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
            self.assertEqual(0, result.returncode, result.stderr)


class RefreshTransaction(unittest.TestCase):
    def test_download_or_annotation_failure_preserves_all_previous_files(self):
        from tests import test_annotate_clinvar_runs_every_branch as shell_tests
        if not shell_tests._stubs_run_here():
            self.skipTest('POSIX stubs unavailable')
        fixture = shell_tests.TestEveryBranchRunsToTheEnd('test_the_plain_branch')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.tearDown)
        cache = fixture.root / 'cache'
        cache.mkdir()
        paths = [cache / 'clinvar.vcf.gz', cache / 'clinvar.vcf.gz.tbi']
        paths += [fixture.genome / name for name in ('clinvar_hits.tsv', 'clinvar_meta.json',
                    'clinvar_norm.json', 'SAMPLE.clinvar.vcf.gz', 'SAMPLE.clinvar.vcf.gz.tbi')]
        for path in paths:
            path.write_bytes(b'previous ' + path.name.encode())
        before = [p.read_bytes() for p in paths]
        curl = fixture.bin / 'curl'
        curl.write_text(shell_tests._CURL.replace('exit 0', 'exit 22'), encoding='utf-8')
        result = fixture.run_it(False, False)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, [p.read_bytes() for p in paths])
        curl.write_text(shell_tests._CURL, encoding='utf-8')
        bcftools = fixture.bin / 'bcftools'
        bcftools.write_text(shell_tests._BCFTOOLS.replace('# anything with -o OUT: write OUT',
                           'if [ "$1" = "norm" ]; then exit 17; fi\n# anything with -o OUT: write OUT'), encoding='utf-8')
        result = fixture.run_it(False, False)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(before, [p.read_bytes() for p in paths])

    def test_crossed_build_refuses_before_annotation(self):
        from tests import test_annotate_clinvar_runs_every_branch as shell_tests
        if not shell_tests._stubs_run_here():
            self.skipTest('POSIX stubs unavailable')
        fixture = shell_tests.TestEveryBranchRunsToTheEnd('test_the_plain_branch')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.tearDown)
        stub = shell_tests._BCFTOOLS.replace('##contig=<ID=chr1,length=248956422>',
                                             '##contig=<ID=chr1,length=249250621>')
        (fixture.bin / 'bcftools').write_text(stub, encoding="utf-8")
        result = fixture.run_it(True, False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn('Assembly mismatch', result.stderr)
        self.assertFalse((fixture.genome / 'clinvar_hits.tsv').exists())


class CacheGenerations(unittest.TestCase):
    def test_builds_are_separate_and_failed_promotion_restores_pointers(self):
        from scholion import clinvar_reference as reference
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); cache = root / 'cache'; cache.mkdir()
            genome_dir = root / 'genome'; genome_dir.mkdir()
            def prepare(build, name):
                stage = cache / ('staged-' + name); stage.mkdir()
                (stage / 'clinvar.vcf.gz').write_bytes(build.encode())
                (stage / 'clinvar.vcf.gz.tbi').write_bytes(b'synthetic index')
                work = root / ('work-' + name); work.mkdir()
                for item in ('S.clinvar.vcf.gz', 'S.clinvar.vcf.gz.tbi', 'clinvar_norm.json', 'clinvar_hits.tsv'):
                    (work / item).write_bytes(name.encode())
                (work / 'clinvar_meta.json').write_text(json.dumps({'assembly': build, 'clinvar_date': '20261027'}), encoding='utf-8')
                return stage, work
            for build in ('GRCh37', 'GRCh38'):
                stage, work = prepare(build, build)
                reference.promote_generation(stage, cache, work, genome_dir, 'S')
            old = {b: reference.cached_reference(cache, b) for b in ('GRCh37', 'GRCh38')}
            self.assertEqual(b'GRCh37', old['GRCh37'].read_bytes())
            self.assertEqual(b'GRCh38', old['GRCh38'].read_bytes())
            stage, work = prepare('GRCh38', 'unchanged')
            reference.promote_generation(stage, cache, work, genome_dir, 'S')
            self.assertEqual(old['GRCh38'], reference.cached_reference(cache, 'GRCh38'))
            before = {p: p.read_bytes() for p in genome_dir.iterdir()}
            stage, work = prepare('GRCh38', 'failed')
            real_replace = os.replace
            def fail_once(src, dst):
                if Path(src) == work / 'clinvar_hits.tsv':
                    raise OSError('synthetic promotion interruption')
                return real_replace(src, dst)
            with mock.patch.object(os, 'replace', side_effect=fail_once), self.assertRaises(OSError):
                reference.promote_generation(stage, cache, work, genome_dir, 'S')
            self.assertEqual(before, {p: p.read_bytes() for p in genome_dir.iterdir()})
            self.assertEqual(old, {b: reference.cached_reference(cache, b) for b in old})
            old['GRCh38'].write_bytes(b'damaged')
            self.assertIsNone(reference.cached_reference(cache, 'GRCh38'))
            self.assertIsNotNone(reference.cached_reference(cache, 'GRCh37'))

    def test_pointer_cannot_escape_cache(self):
        from scholion.clinvar_reference import cached_reference
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); cache = root / 'cache'; cache.mkdir()
            (root / 'outside').write_bytes(b'outside')
            (cache / 'current.json').write_text(json.dumps({'path': '../outside'}), encoding='utf-8')
            self.assertIsNone(cached_reference(cache))

    def test_clnalle_scopes_assertion_to_one_alt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'reference.vcf.gz'
            row = clinvar_row('17', '43092919', 'G', 'A,T', 'BRCA1')
            row[7] += ';CLNALLE=2'
            vcf(path, 'GRCh38', [row], clinvar=True, sample=False)
            index, _ = acmg_scan._index(str(path), {'BRCA1': {}})
            self.assertEqual([('17', '43092919', 'G', 'T')], list(index))


class SampleSelection(unittest.TestCase):
    def test_multiple_samples_require_an_existing_explicit_choice(self):
        from scholion.clinvar_reference import select_sample
        header = ['#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tFIRST\tSECOND']
        with self.assertRaises(ValueError):
            select_sample(header)
        with self.assertRaises(ValueError):
            select_sample(header, 'MISSING')
        self.assertEqual('SECOND', select_sample(header, 'SECOND'))
        self.assertEqual('FIRST', select_sample([header[0].rsplit('\t', 1)[0]]))
        with self.assertRaises(ValueError):
            select_sample([])


class ClinVarTableProvenance(unittest.TestCase):
    def test_known_provenance_is_checked_without_discarding_saved_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            personal = root / 'personal.vcf'
            personal.write_bytes(b'synthetic genome')
            table = root / 'clinvar_hits.tsv'
            content = b'chrom\tpos\tref\talt\tgene\tclnsig\n1\t100\tA\tG\tGNMT\tBenign\n'
            table.write_bytes(content)
            metadata = {'assembly': 'GRCh38', 'sample': 'ME',
                        'table_sha256': hashlib.sha256(content).hexdigest(),
                        'personal_identity': {'st_size': personal.stat().st_size}}
            with mock.patch.object(core, 'genome_bases', return_value=[root]), \
                 mock.patch.object(genome, 'vcf_path', return_value=personal), \
                 mock.patch.object(genome, 'assembly_of', return_value='GRCh38'), \
                 mock.patch.object(genome, 'samples_of', return_value=['ME']), \
                 mock.patch.object(genome, 'sample_index', return_value=0), \
                 mock.patch.object(genome, '_clinvar_local_gene_map', return_value={}):
                cases = [({}, None), ({'assembly': 'GRCh37'}, 'assembly_mismatch'),
                         ({'assembly': 'unknown'}, 'assembly_mismatch'),
                         ({'sample': 'OTHER'}, 'sample_changed'),
                         ({'table_sha256': 'changed'}, 'table_changed'),
                         ({'personal_identity': {'st_size': 999}}, 'source_changed')]
                for change, reason in cases:
                    with self.subTest(reason=reason):
                        (root / 'clinvar_meta.json').write_text(json.dumps(dict(metadata, **change)), encoding='utf-8')
                        result = genome.clinvar_hits()
                        if reason:
                            self.assertEqual('table_unverified', result['status'])
                            self.assertEqual(reason, result['reason'])
                            self.assertEqual(1, len(result['saved_hits']))
                            self.assertEqual([], result['hits'])
                        else:
                            self.assertEqual('ok', result['status'])
                            self.assertEqual(1, len(result['hits']))
                        self.assertEqual(content, table.read_bytes())
                personal.unlink()
                (root / 'clinvar_meta.json').write_text(json.dumps(metadata), encoding='utf-8')
                self.assertEqual('source_unavailable', genome.clinvar_hits()['reason'])


class ClinVarRefusalPresentation(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'requires the browser renderer')
    def test_unverified_findings_are_not_presented_as_a_negative_screen(self):
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        start = page.index('function renderClinvar(')
        renderer = page[start:page.index('\n}\n', start) + 2]
        script = 'const messages=' + json.dumps({k: i18n.CATALOGUES[k] for k in ('en', 'ru')}) + ';\n'
        script += r'''const assert=require('node:assert/strict');
const esc=x=>String(x??'').replaceAll('<','&lt;').replaceAll('>','&gt;');
let language='en';const t=k=>messages[language][k]||k;
'''+renderer+r'''
for(language of ['en','ru']){
 const message=t('genome.clinvar_table_unverified');
 const html=renderClinvar({status:'table_unverified',message,hits:[],saved_hits:[{gene:'SYNTHETIC'}]});
 assert.ok(html.includes(message));
 assert.ok(!html.includes(t('web.clinvar.nothing')));
 assert.ok(!html.includes('SYNTHETIC'));
 assert.ok(renderClinvar({status:'ok',count:0}).includes(t('web.clinvar.nothing')));
 assert.ok(renderClinvar({status:'table_unverified',message:'<source>'}).includes('&lt;source&gt;'));
}
'''
        result = gene_card_support.run(script, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)
