"""Narrow selection and reused evidence fail closed without losing full tests."""
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
sys.path.insert(0, str(support.ROOT / 'src/tools'))
import candidate_evidence as evidence  # noqa: E402
import test_plan  # noqa: E402


class CandidateChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / 'repository'
        self.root.mkdir()
        self.put('tests/__init__.py', '')
        self.put('tests/helper.py', "ASSET='measurements.js'\n")
        self.put('tests/test_component.py', 'from . import helper\n')
        self.put('tests/test_inherited.py', 'from tests.test_component import Base\n')
        self.put('tests/test_unrelated.py', 'import unittest\n')
        self.put('src/scholion/web/measurements.js', 'module.exports={};\n')
        self.env = support.env()

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    def test_component_includes_transitive_helpers_and_page_consumers(self):
        self.put('tests/test_page.py', "page='index.html'\n")
        plan = test_plan.plan(self.root, ['src/scholion/web/measurements.js'])
        self.assertEqual('targeted', plan['mode'])
        self.assertEqual(['tests.test_component', 'tests.test_inherited', 'tests.test_page'], plan['tests'])
        self.assertIn('tests/helper.py', plan['why']['tests/test_component.py'])
        self.assertFalse(plan['release_acceptance'])
        self.assertEqual({'1', '2', '3', '4', '5'}, set(plan['levels']))

    def test_changed_tests_include_dependents_and_keep_new_tests(self):
        self.put('tests/test_new.py', 'import unittest\n')
        plan = test_plan.plan(self.root, ['tests/test_component.py', 'tests/test_new.py'])
        self.assertEqual(['tests.test_component', 'tests.test_inherited', 'tests.test_new'], plan['tests'])

    def test_dynamic_test_imports_are_always_included(self):
        self.put('tests/test_dynamic.py', "import importlib\nimportlib.import_module(name)\n")
        plan = test_plan.plan(self.root, ['tests/helper.py'])
        self.assertIn('tests.test_dynamic', plan['tests'])

    def test_unknown_deleted_data_and_empty_changes_require_full_discovery(self):
        self.put('knowledge/new.json', '{}')
        self.put('src/scholion/core.py', '')
        self.put('tests/unused.py', '')
        for changed in ([], ['knowledge/new.json'], ['src/scholion/core.py'],
                        ['tests/deleted.py'], ['tests/unused.py']):
            with self.subTest(changed=changed):
                plan = test_plan.plan(self.root, changed)
                self.assertEqual('full', plan['mode'])
                self.assertEqual([], plan['tests'])
                self.assertEqual('--suite-only', plan['command'][-1])
                self.assertTrue(plan['fallback_reasons'])

    def test_mixed_unknown_change_cannot_be_hidden_by_a_known_component(self):
        plan = test_plan.plan(self.root, ['tests/helper.py', 'VERSION'])
        self.assertEqual('full', plan['mode'])

    def test_external_and_absolute_paths_are_refused(self):
        for path in ('../outside.py', str(self.root / 'tests/helper.py')):
            with self.assertRaises(ValueError):
                test_plan.plan(self.root, [path])

    def test_git_selection_uses_null_delimiters_and_includes_untracked(self):
        replies = [subprocess.CompletedProcess([], 0, b'tests/one space.py\0tests/a.py\0'),
                   subprocess.CompletedProcess([], 0, b'tests/new.py\0')]
        with mock.patch.object(test_plan.subprocess, 'run', side_effect=replies) as run:
            changed = test_plan.changed_files(self.root, 'HEAD')
        self.assertEqual(['tests/a.py', 'tests/new.py', 'tests/one space.py'], changed)
        self.assertIn('--no-optional-locks', run.call_args_list[0].args[0])

    def make_record(self, command=None, artifacts=None):
        out = self.base / 'check.json'
        with mock.patch.object(evidence, 'context', return_value={'test': 'stable'}):
            status = evidence.record(self.root, out, command or [sys.executable, '-c', 'print("ok")'],
                                     2, artifacts or [], self.env)
        return status, out, json.loads(out.read_text(encoding='utf-8'))

    def verify(self, record):
        with mock.patch.object(evidence, 'context', return_value={'test': 'stable'}):
            return evidence.verify(self.root, record, self.env)

    def test_success_is_reusable_for_only_its_recorded_scope(self):
        status, _path, record = self.make_record()
        self.assertEqual(0, status)
        result = self.verify(record)
        self.assertTrue(result['reusable'], result)
        self.assertFalse(result['release_acceptance'])
        self.assertEqual(2, result['level'])
        self.assertGreater(result['seconds'], 0)

    def test_content_change_with_preserved_mtime_invalidates_evidence(self):
        _, _, record = self.make_record()
        path = self.root / 'tests/helper.py'
        stat = path.stat()
        self.put('tests/helper.py', 'changed')
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(['tests/helper.py'], self.verify(record)['changed_inputs'])

    def test_added_deleted_files_and_executable_mode_invalidate_evidence(self):
        _, _, record = self.make_record()
        added = self.put('tests/new.py', '')
        self.assertFalse(self.verify(record)['reusable'])
        added.unlink()
        helper = self.root / 'tests/helper.py'
        helper.chmod(helper.stat().st_mode | 0o111)
        if os.name != 'nt':
            self.assertFalse(self.verify(record)['reusable'])
        helper.unlink()
        self.assertFalse(self.verify(record)['reusable'])

    def test_failed_and_interrupted_checks_cannot_be_reused(self):
        status, _, record = self.make_record([sys.executable, '-c', 'raise SystemExit(3)'])
        self.assertEqual(3, status)
        self.assertFalse(self.verify(record)['reusable'])
        record.update(state='running', exit=0, stable=True)
        self.assertFalse(self.verify(record)['reusable'])

    def test_modified_inputs_during_a_successful_check_are_rejected(self):
        command = [sys.executable, '-c', "from pathlib import Path;Path('tests/new.py').write_text('new')"]
        status, _, record = self.make_record(command)
        self.assertEqual(2, status)
        self.assertEqual(['tests/new.py'], record['changed_inputs'])
        self.assertFalse(self.verify(record)['reusable'])

    def test_tampered_log_or_artifact_or_context_invalidates_evidence(self):
        artifact = self.base / 'candidate.whl'
        artifact.write_bytes(b'wheel')
        _, _, record = self.make_record(artifacts=[artifact])
        self.assertTrue(self.verify(record)['reusable'])
        artifact.write_bytes(b'other')
        self.assertFalse(self.verify(record)['reusable'])
        artifact.write_bytes(b'wheel')
        with mock.patch.object(evidence, 'context', return_value={'test': 'another day or interpreter'}):
            self.assertFalse(evidence.verify(self.root, record, self.env)['reusable'])
        Path(record['log']).write_text('replaced', encoding='utf-8')
        self.assertFalse(self.verify(record)['reusable'])

    def test_existing_evidence_is_never_overwritten(self):
        _, path, record = self.make_record()
        with self.assertRaises(ValueError):
            evidence.record(self.root, path, [sys.executable, '-V'], 2, [], self.env)
        self.assertEqual(record, json.loads(path.read_text(encoding='utf-8')))

    def test_personal_profile_and_generated_reports_do_not_enter_manifest(self):
        self.put('profile/private.json', 'private')
        self.put('reports/generated.txt', 'report')
        names = evidence.inputs(self.root)
        self.assertFalse(any(n.startswith(('profile/', 'reports/')) for n in names))

    def test_unknown_product_switches_are_hashed_without_disclosing_values(self):
        with mock.patch.object(evidence, 'digest', return_value='binary'), \
                mock.patch.object(evidence.shutil, 'which', return_value=None):
            first = evidence.context({'SCHOLION_CUSTOM': 'private-value', '_': 'old'})
            volatile = evidence.context({'SCHOLION_CUSTOM': 'private-value', '_': 'new'})
            changed = evidence.context({'SCHOLION_CUSTOM': 'another-value'})
        self.assertEqual(first, volatile)
        self.assertNotEqual(first, changed)
        self.assertNotIn('private-value', json.dumps(first))

    def test_privacy_rules_and_backlog_are_check_inputs(self):
        self.put('.personal_patterns', 'synthetic pattern')
        self.put('backlog/open.md', 'synthetic backlog')
        self.assertIn('.personal_patterns', evidence.inputs(self.root))
        self.assertIn('backlog/open.md', evidence.inputs(self.root))

    def test_dependency_metadata_changes_invalidate_even_the_same_version(self):
        distribution = mock.Mock()
        distribution.metadata = {'Name': 'synthetic-dependency'}
        distribution.version = '1.0'
        distribution.read_text.return_value = 'original installed record'
        with mock.patch.object(evidence.metadata, 'distributions', return_value=[distribution]), \
                mock.patch.object(evidence, 'digest', return_value='binary'), \
                mock.patch.object(evidence.shutil, 'which', return_value=None):
            first = evidence.context({})
            distribution.read_text.return_value = 'changed installed record'
            changed = evidence.context({})
        self.assertNotEqual(first['packages'], changed['packages'])
        self.assertNotIn('original installed record', json.dumps(first))

    def test_distribution_metadata_is_read_as_utf8_without_a_locale_default(self):
        content = 'Metadata-Version: 2.1\nName: synthetic-check\nVersion: 1.0\nSummary: Caf\u00e9\n'
        path = self.put('synthetic_check-1.0.dist-info/METADATA', content)
        distribution = evidence.metadata.PathDistribution(path.parent)
        with mock.patch.object(evidence.metadata, 'distributions', return_value=[distribution]), \
                mock.patch.object(evidence, 'digest', return_value='binary'), \
                mock.patch.object(evidence.shutil, 'which', return_value=None):
            result = evidence.context({})
        expected = evidence.hashlib.sha256((content + '\n\n').encode('utf-8')).hexdigest()
        self.assertEqual(expected, result['packages'][0]['metadata_sha256'])
