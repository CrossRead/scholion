"""Native platform branches plus the common non-destructive source setting."""
from __future__ import annotations

import base64
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, folder_picker, store


class TestWindowsPickerProtocol(unittest.TestCase):
    def choose(self, result):
        with mock.patch.object(folder_picker.sys, 'platform', 'win32'), \
                mock.patch.object(folder_picker.subprocess, 'run', return_value=result) as run:
            answer = folder_picker.choose('A quoted "prompt"; write-host unsafe')
        return answer, run.call_args

    def test_unicode_and_unc_paths_are_json_data_and_not_shell_code(self):
        for path in ('C:\\Users\\Example\\Мои анализы', '\\\\server\\share\\Lab results'):
            result = subprocess.CompletedProcess([], 0, json.dumps({'ok':True,'path':path}), '')
            got, call = self.choose(result)
            self.assertEqual(got['path'], path)
            command = call.args[0]
            self.assertIn('-STA', command)
            self.assertIn('-EncodedCommand', command)
            script = base64.b64decode(command[-1]).decode('utf-16le')
            self.assertNotIn('write-host unsafe', script)
            self.assertIn('FromBase64String', script)
            self.assertFalse(call.kwargs.get('shell', False))
            self.assertEqual(call.kwargs['encoding'], 'utf-8')

    def test_cancel_failure_and_empty_output_are_different_states(self):
        for code, output, stderr, expected in (
                (0, '{"ok":false,"canceled":true}', '', 'canceled'),
                (1, '', 'synthetic process failure', 'dialog_failed'),
                (0, '{}', '', 'empty_path')):
            got, _ = self.choose(subprocess.CompletedProcess([], code, output, stderr))
            self.assertFalse(got['ok'])
            self.assertTrue(got['manual_available'])
            self.assertTrue(got.get('canceled') if expected=='canceled' else got['reason']==expected)

    def test_timeout_and_missing_process_keep_manual_entry_available(self):
        for failure, reason in ((subprocess.TimeoutExpired('synthetic', 300), 'dialog_timeout'),
                                (FileNotFoundError('synthetic missing PowerShell'), 'dialog_unavailable')):
            with mock.patch.object(folder_picker.sys, 'platform', 'win32'), \
                    mock.patch.object(folder_picker.subprocess, 'run', side_effect=failure):
                got = folder_picker.choose('Synthetic prompt')
            self.assertEqual(got['reason'], reason)
            self.assertTrue(got['manual_available'])


class TestSourceSettingTransaction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.profile = self.root/'profile'; self.profile.mkdir()
        self.addCleanup(support.pin_profile(self.profile))
        self.source = self.root/'Мои анализы'; self.source.mkdir()
        self.config = self.profile/'sources.json'
        self.config.write_text(json.dumps({'folders':{'labs_docs':'old-source'}}), encoding="utf-8")
        self.before = self.config.read_bytes()
        core.reset_cache()
        self.addCleanup(core.reset_cache)

    def test_empty_invalid_and_unavailable_paths_do_not_change_the_old_choice(self):
        for path in ('', '   ', None, 42, str(self.root/'absent')):
            with self.subTest(path=path):
                got = store.set_source_folder('labs_docs', path)
                self.assertFalse(got['ok'])
                self.assertEqual(self.config.read_bytes(), self.before)

    def test_unicode_path_is_saved_by_the_common_store_and_survives_cache_reset(self):
        got = store.set_source_folder('labs_docs', str(self.source))
        self.assertTrue(got['ok'], got)
        core.reset_cache()
        self.assertEqual(core.source_config()['labs_docs'], str(self.source))
        self.assertEqual(json.loads(self.config.read_text(encoding="utf-8"))['folders']['labs_docs'], str(self.source))

    def test_copy_failure_cannot_switch_sources(self):
        (self.profile/'labs.json').write_text('{"markers":{}}', encoding="utf-8")
        with mock.patch.object(Path, 'read_bytes', side_effect=PermissionError('synthetic source denied')):
            got = store.set_source_folder('labs', str(self.source))
        self.assertFalse(got['ok'])
        self.assertEqual(self.config.read_bytes(), self.before)
        self.assertFalse((self.source/'labs.json').exists())

    def test_settings_write_failure_rolls_back_only_the_new_copy(self):
        (self.profile/'labs.json').write_text('{"markers":{}}', encoding="utf-8")
        with mock.patch.object(store, '_write_json', side_effect=OSError('synthetic write failure')):
            got = store.set_source_folder('labs', str(self.source))
        self.assertFalse(got['ok'])
        self.assertEqual(self.config.read_bytes(), self.before)
        self.assertFalse((self.source/'labs.json').exists())

    def test_an_existing_destination_is_never_overwritten(self):
        (self.profile/'labs.json').write_text('{"markers":{}}', encoding="utf-8")
        existing = self.source/'labs.json'; existing.write_text('existing-source-bytes', encoding="utf-8")
        got = store.set_source_folder('labs', str(self.source))
        self.assertTrue(got['ok'])
        self.assertEqual(existing.read_text(encoding="utf-8"), 'existing-source-bytes')

    def test_a_folder_setting_does_not_start_genome_preparation(self):
        with mock.patch('scholion.population_preparation.prepare', side_effect=AssertionError('unexpected job')):
            result = store.set_source_folder('genome', str(self.source))
        self.assertTrue(result['ok'])
        self.assertEqual(result['population_assignment']['status'], 'deferred_to_genome_selection')


from tests.test_every_door_of_the_local_server_answers import _Live  # noqa: E402


class TestFolderSettingAPI(_Live):
    def config_bytes(self):
        path = self._profile/'sources.json'
        return path.read_bytes() if path.exists() else None

    def test_empty_manual_path_is_not_a_request_to_open_the_native_dialog(self):
        before = self.config_bytes()
        with mock.patch('scholion.server._choose_folder_native', side_effect=AssertionError('unexpected dialog')):
            got = self.json_of('/api/pick-folder', data={'domain':'labs_docs','path':''})
        self.assertFalse(got['ok'])
        self.assertEqual(got['reason'], 'empty_path')
        self.assertEqual(self.config_bytes(), before)

    def test_native_preview_and_cancel_never_change_the_configuration(self):
        before = self.config_bytes()
        for reply in ({'ok':True,'path':str(self._profile)}, {'ok':False,'canceled':True}):
            with mock.patch('scholion.server._choose_folder_native', return_value=reply):
                got = self.json_of('/api/pick-folder', data={'domain':'labs_docs','preview':True})
            self.assertEqual(got, reply)
            self.assertEqual(self.config_bytes(), before)

    def test_manual_save_uses_the_same_setting_and_does_not_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()/'Lab source with spaces'; folder.mkdir()
            with mock.patch('scholion.ingest_labs.ingest', side_effect=AssertionError('unexpected import')):
                result = self.json_of('/api/pick-folder', data={'domain':'labs_docs','path':str(folder)})
            self.assertTrue(result['ok'])
            config = self.json_of('/api/source-config')
            self.assertEqual(config['folders']['labs_docs'], str(folder))

    def test_a_stale_patient_context_cannot_write_another_persons_setting(self):
        before = self.config_bytes()
        result = self.json_of('/api/pick-folder', data={
            'domain':'labs_docs','path':str(self._profile),'container_id':'another-synthetic-container'})
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'container_changed')
        self.assertEqual(self.config_bytes(), before)
