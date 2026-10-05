"""C8-C10: whole-container receipts, deliberate erasure and an anonymous surviving journal."""
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import threading
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import support
from scholion import cli, container, core, lifecycle

A, B = 'demo-aaa', 'demo-bbb'


class TestContainerLifecycle(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='lifecycle-')
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.addCleanup(support.workstation(self.base, {
            A: {'labs.json': {'_meta': {'synthetic': True}, 'markers': {}}},
            B: {'labs.json': {'_meta': {'synthetic': True}, 'markers': {}}},
        }))
        env = {'SCHOLION_' + s.upper() + '_DIR': '' for s in (*core.DATA_SLOTS, 'cache')}
        env['SCHOLION_GENOME_VCF'] = ''
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        self.addCleanup(patch.stop)
        self.folder = self.base / 'patients' / B
        for slot in ('genome', 'raw', 'work', 'archive'):
            (self.folder / slot).mkdir()
            (self.folder / slot / 'synthetic.txt').write_text(slot, encoding='utf-8')
        identity = self.folder / 'container.json'
        identity.write_text(json.dumps({'id': B, 'label': 'SYNTHETIC-PRIVATE-LABEL'}), encoding='utf-8')

    def sources(self, cid, values):
        (self.base / 'patients' / cid / 'profile/sources.json').write_text(json.dumps(values), encoding='utf-8')

    def external(self, slot='raw'):
        path = self.base / ('external-' + slot)
        path.mkdir()
        (path / 'original.txt').write_text('synthetic original', encoding='utf-8')
        (path / lifecycle.OWNER_FILE).write_text(json.dumps({'container': B, 'scope': '.'}), encoding='utf-8')
        self.sources(B, {'folders': {slot: str(path)}})
        return path

    def test_export_is_the_whole_container(self):
        ext = self.external()
        before = lifecycle.inventory(B)
        target = self.base / 'export.tar.gz'
        r = lifecycle.export(B, str(target), surface='web')
        self.assertTrue(r['ok'])
        with tarfile.open(target) as archive:
            names = set(archive.getnames())
            expected = {f['member'] for f in before['files']}
            self.assertEqual(expected | {'profile/container-journal.jsonl', 'export-manifest.json'}, names)
            self.assertEqual(b'synthetic original', archive.extractfile('raw/original.txt').read())
            manifest = json.load(archive.extractfile('export-manifest.json'))
            self.assertEqual(names - {'export-manifest.json'}, {f['path'] for f in manifest['files']})
            self.assertNotIn('workstation.json', names)
        self.assertTrue(ext.exists())
        if os.name != 'nt':
            self.assertEqual(0o600, target.stat().st_mode & 0o777)

    def test_erase_leaves_nothing_and_says_so(self):
        ext = self.external()
        preview = lifecycle.erase(B)
        self.assertTrue(preview['preview'])
        self.assertTrue((ext / 'original.txt').exists())
        result = lifecycle.erase(B, confirm=B, digest=preview['digest'], surface='web')
        self.assertTrue(result['ok'], result)
        self.assertIn('raw/original.txt', result['removed'])
        self.assertIn('container.json', result['removed'])
        self.assertFalse(ext.exists())
        self.assertEqual([], list(self.folder.iterdir()))
        self.assertTrue(container.path_of(A).exists())
        self.assertNotIn(B, container.registry())

    def test_the_clinic_journal_survives_and_names_nobody(self):
        preview = lifecycle.erase(B)
        lifecycle.erase(B, confirm=B, digest=preview['digest'])
        journal = (self.base / 'clinic-journal.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('SYNTHETIC-PRIVATE-LABEL', journal)
        rows = [json.loads(line) for line in journal.splitlines()]
        self.assertEqual(['erase-started', 'erase-completed'], [r['action'] for r in rows])
        for row in rows:
            self.assertEqual({'id', 'time', 'action', 'surface'}, set(row))
            self.assertEqual(B, row['id'])

    def test_active_container_is_never_erasable(self):
        with self.assertRaises(container.ContainerError):
            lifecycle.erase(A)

    def test_wrong_confirmation_changes_no_data(self):
        before = lifecycle.inventory(B)
        with self.assertRaises(container.ContainerError):
            lifecycle.erase(B, confirm=A, digest=before['digest'])
        self.assertEqual(before, lifecycle.inventory(B))

    def test_stale_plan_changes_no_data(self):
        before = lifecycle.erase(B)
        (self.folder / 'raw/new.txt').write_text('new synthetic input', encoding='utf-8')
        with self.assertRaises(container.ContainerError):
            lifecycle.erase(B, confirm=B, digest=before['digest'])
        self.assertTrue((self.folder / 'raw/synthetic.txt').exists())

    def test_external_storage_requires_an_explicit_ownership_declaration(self):
        path = self.external()
        (path / lifecycle.OWNER_FILE).unlink()
        with self.assertRaises(container.ContainerError):
            lifecycle.inventory(B)

    def test_a_declaration_does_not_override_another_containers_reference(self):
        path = self.external()
        self.sources(A, {'folders': {'raw': str(path)}})
        with self.assertRaises(container.ContainerError):
            lifecycle.inventory(B)
        self.assertTrue((path / 'original.txt').exists())

    def test_nested_external_roots_are_refused(self):
        path = self.external()
        (path / 'nested').mkdir()
        self.sources(B, {'folders': {'raw': str(path), 'work': str(path / 'nested')}})
        with self.assertRaises(container.ContainerError):
            lifecycle.inventory(B)

    def test_missing_declared_source_does_not_become_an_empty_export(self):
        self.sources(B, {'folders': {'raw': str(self.base / 'absent')}})
        with self.assertRaises(container.ContainerError):
            lifecycle.export(B, str(self.base / 'nothing.tar.gz'))
        self.assertFalse((self.base / 'nothing.tar.gz').exists())

    def test_malformed_sources_refuse_before_erasure(self):
        self.sources(B, {'folders': []})
        with self.assertRaises(container.ContainerError):
            lifecycle.erase(B)

    def test_symlink_inside_a_slot_is_refused(self):
        link = self.folder / 'raw/link'
        try:
            link.symlink_to(self.base / 'patients' / A, target_is_directory=True)
        except OSError:
            self.skipTest('OS does not permit creation of test symlinks')
        with self.assertRaises(container.ContainerError):
            lifecycle.inventory(B)

    def test_hardlinked_files_are_refused(self):
        source = self.folder / 'raw/synthetic.txt'
        try:
            os.link(source, self.base / 'shared.txt')
        except OSError:
            self.skipTest('filesystem has no hardlinks')
        with self.assertRaises(container.ContainerError):
            lifecycle.inventory(B)

    def test_export_never_replaces_a_file(self):
        target = self.base / 'existing'
        target.write_text('keep me', encoding='utf-8')
        with self.assertRaises(container.ContainerError):
            lifecycle.export(B, str(target))
        self.assertEqual('keep me', target.read_text(encoding='utf-8'))

    def test_export_cannot_write_into_another_container(self):
        with self.assertRaises(container.ContainerError):
            lifecycle.export(B, str(self.base / 'patients' / A / 'profile/export.tar.gz'))

    def test_failed_export_publishes_no_partial_archive(self):
        target = self.base / 'failed.tar.gz'
        with mock.patch.object(tarfile.TarFile, 'addfile', side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError):
                lifecycle.export(B, str(target))
        self.assertFalse(target.exists())
        self.assertEqual([], list(self.base.glob('.scholion-export-*')))

    def test_a_file_changed_during_export_is_refused(self):
        target = self.base / 'changed.tar.gz'
        original = tarfile.TarFile.addfile
        changed = False

        def add(archive, info, stream=None):
            nonlocal changed
            result = original(archive, info, stream)
            if info.name == 'raw/synthetic.txt' and not changed:
                changed = True
                (self.folder / 'raw/synthetic.txt').write_text('changed', encoding='utf-8')
            return result

        with mock.patch.object(tarfile.TarFile, 'addfile', add):
            with self.assertRaises(container.ContainerError):
                lifecycle.export(B, str(target))
        self.assertFalse(target.exists())

    def test_running_recompute_refuses_erasure(self):
        (self.folder / 'profile/.recompute.claim').write_text('synthetic lock', encoding='utf-8')
        plan = lifecycle.erase(B)
        with self.assertRaises(container.ContainerError):
            lifecycle.erase(B, confirm=B, digest=plan['digest'])

    def test_partial_erasure_is_not_reported_as_success(self):
        plan = lifecycle.erase(B)
        original = Path.unlink
        failing = self.folder / 'raw/synthetic.txt'

        def unlink(path, *args, **kwargs):
            if path == failing:
                raise PermissionError('synthetic failure')
            return original(path, *args, **kwargs)

        with mock.patch.object(Path, 'unlink', unlink):
            result = lifecycle.erase(B, confirm=B, digest=plan['digest'])
        self.assertFalse(result['ok'])
        self.assertTrue(failing.exists())
        self.assertEqual('erasing', container.read(self.folder)['lifecycle'])
        with self.assertRaises(container.ContainerError):
            container.use(B)
        self.assertEqual(A, container.workstation()['active'])

    def test_cli_preview_does_not_change_active_selection(self):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(io.StringIO()):
            code = cli.main(['erase', '--patient', B, '--json'])
        self.assertEqual(0, code)
        self.assertEqual(B, json.loads(output.getvalue())['container']['id'])
        self.assertEqual(A, container.workstation()['active'])

    def test_cli_requires_an_explicit_patient(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(2, cli.main(['erase']))

    def test_read_journals_do_not_include_arguments_or_labels(self):
        lifecycle.record_current('read', 'web')
        clinic = (self.base / 'clinic-journal.jsonl').read_text(encoding='utf-8')
        local = (self.base / 'patients' / A / 'profile' / lifecycle.JOURNAL).read_text(encoding='utf-8')
        self.assertEqual(clinic, local)
        self.assertEqual({'id', 'time', 'action', 'surface'}, set(json.loads(clinic)))

    def test_mcp_and_ouroboros_have_distinct_surface_records(self):
        from scholion import mcp_server, ouroboros_tools
        result = mcp_server.call_tool('sch_rules')
        self.assertFalse(result['isError'], result)
        tool = next(tool for tool in ouroboros_tools.get_tools() if tool.name == 'sch_rules')
        tool.handler(None)
        rows = [json.loads(line) for line in (self.base / 'clinic-journal.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(['mcp', 'ouroboros'], [row['surface'] for row in rows])

    def test_lock_failure_does_not_allow_unlocked_export(self):
        with mock.patch.object(os, 'open', side_effect=PermissionError('synthetic failure')):
            with self.assertRaises(PermissionError):
                lifecycle.export(B, str(self.base / 'refused.tar.gz'))
        self.assertFalse((self.base / 'refused.tar.gz').exists())

    def test_windows_junction_metadata_refuses_even_without_a_symlink(self):
        path = self.folder / 'raw'
        original = Path.lstat

        def lstat(p):
            result = original(p)
            if p == path:
                return SimpleNamespace(st_mode=result.st_mode, st_file_attributes=0x400)
            return result

        with mock.patch.object(Path, 'lstat', lstat):
            with self.assertRaises(container.ContainerError):
                lifecycle.inventory(B)
        self.assertTrue((path / 'synthetic.txt').is_file())

    def test_creation_and_switch_are_recorded_without_labels(self):
        result = container.create('demo-ccc', 'SYNTHETIC-PRIVATE-LABEL')
        container.use(result['id'], surface='web')
        rows = [json.loads(line) for line in
                (self.base / 'clinic-journal.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(['create', 'use'], [r['action'] for r in rows])
        self.assertEqual(['cli-script', 'web'], [r['surface'] for r in rows])
        self.assertTrue(all(r['id'] == 'demo-ccc' for r in rows))
        local = self.base / 'patients/demo-ccc/profile' / lifecycle.JOURNAL
        self.assertEqual(rows, [json.loads(line) for line in local.read_text(encoding='utf-8').splitlines()])


class TestLifecycleHttp(unittest.TestCase):
    def setUp(self):
        TestContainerLifecycle.setUp(self)
        from scholion import server
        self.server = server._Server(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = 'http://127.0.0.1:' + str(self.server.server_address[1])

    def post(self, route, body, origin=None):
        req = urllib.request.Request(self.url + route, data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json',
                                              'Origin': origin or self.url})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.load(response)

    def test_web_export_preview_and_confirm_keep_the_other_person(self):
        destination = self.base / 'web-export.tar.gz'
        exported = self.post('/api/export', {'id': B, 'to': str(destination)})
        self.assertTrue(exported['ok'], exported)
        self.assertTrue(destination.is_file())
        plan = self.post('/api/erase', {'id': B})
        self.assertTrue(plan['preview'], plan)
        self.assertTrue(self.folder.exists())
        erased = self.post('/api/erase', {'id': B, 'confirm': B, 'digest': plan['digest']})
        self.assertTrue(erased['ok'], erased)
        self.assertEqual([], list(self.folder.iterdir()))
        self.assertEqual(A, container.workstation()['active'])
        rows = [json.loads(line) for line in
                (self.base / 'clinic-journal.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertTrue(all(r['surface'] == 'web' and r['id'] == B for r in rows))

    def test_foreign_origin_cannot_export_or_erase(self):
        before = lifecycle.inventory(B)['digest']
        for route in ('/api/export', '/api/erase'):
            with self.subTest(route=route), self.assertRaises(urllib.error.HTTPError) as ctx:
                self.post(route, {'id': B, 'to': str(self.base / 'forbidden.tar.gz')},
                          origin='https://foreign.invalid')
            self.assertEqual(403, ctx.exception.code)
        self.assertEqual(before, lifecycle.inventory(B)['digest'])
        self.assertFalse((self.base / 'forbidden.tar.gz').exists())
        self.assertFalse((self.base / 'clinic-journal.jsonl').exists())
