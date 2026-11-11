"""The delivered archive, not just Git, excludes generated/private content."""
import importlib.util
import hashlib
import os
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile
from unittest import mock

import support

spec = importlib.util.spec_from_file_location('distribution_check', support.ROOT / 'src/tools/check_distribution.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class TestActualArchiveBoundary(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def source(self, extra=None):
        path = self.root / 'source.tar.gz'
        files = {'VERSION': b'0.0.0', 'pyproject.toml': b'example',
                 'tests/fixtures/genome/tiny.vcf.gz': b'invented',
                 'tests/fixtures/genome/tiny.vcf.gz.tbi': b'index'}
        files.update(extra or {})
        with tarfile.open(path, 'w:gz') as archive:
            for name, data in files.items():
                member = tarfile.TarInfo('scholion-0.0.0/' + name)
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
        return path

    def test_clean_source_extracts_once_and_preserves_required_fixture(self):
        result = checker.inspect(self.source(), self.root / 'extract')
        source = Path(result['source_root'])
        self.assertEqual((source / 'VERSION').read_bytes(), b'0.0.0')
        with self.assertRaises(FileExistsError):
            checker.inspect(self.root / 'source.tar.gz', self.root / 'extract')

    def test_cache_private_and_traversal_paths_are_refused(self):
        for path in ('tests/fixtures/genome/cache/linear.json', 'src/x/__pycache__/x.pyc',
                     'tests/browser/node_modules/a.js', 'profile/labs.json', '../escape', 'C:/escape'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                checker.inspect(self.source({path: b'not for distribution'}))

    def test_missing_fixture_or_links_cannot_be_accepted(self):
        path = self.source()
        with tarfile.open(path, 'w:gz') as archive:
            member = tarfile.TarInfo('scholion-0.0.0/link')
            member.type = tarfile.SYMTYPE
            member.linkname = '/tmp/outside'
            archive.addfile(member)
        with self.assertRaises(ValueError):
            checker.inspect(path)

    def test_wheel_is_checked_without_extracting_it(self):
        path = self.root / 'package.whl'
        with zipfile.ZipFile(path, 'w') as wheel:
            wheel.writestr('scholion/__init__.py', '')
            wheel.writestr('scholion-0.0.0.dist-info/METADATA', 'Version: 0.0.0')
        self.assertTrue(checker.inspect(path)['ok'])
        with zipfile.ZipFile(path, 'a') as wheel:
            wheel.writestr('node_modules/unexpected.js', '')
        with self.assertRaises(ValueError):
            checker.inspect(path)

    def test_reader_uses_a_private_copy_of_the_tracked_genome(self):
        original = support.ROOT / 'tests/fixtures/genome/tiny.vcf.gz'
        copied = support.isolated_genome(self)
        self.assertEqual(copied.read_bytes(), original.read_bytes())
        self.assertNotEqual(copied.parent, original.parent)
        from scholion import core, linear
        def fingerprint():
            return {str(p.relative_to(original.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in original.parent.rglob('*') if p.is_file()}
        before = fingerprint()
        with mock.patch.dict(os.environ, {'SCHOLION_GENOME_VCF': str(copied),
                                         'SCHOLION_GENOME_DIR': str(copied.parent)}):
            core.reset_cache()
            try:
                reading = linear.snapshot(str(copied))
                self.assertEqual(reading['samples'], ['SAMPLE1'])
                self.assertTrue(list((copied.parent / 'cache').glob('linear-*.json')))
            finally:
                core.reset_cache()
        self.assertEqual(fingerprint(), before)

    def test_publisher_checks_built_artifacts_before_uploading_the_same_files(self):
        workflow = support.ROOT / '.github/workflows/publish.yml'
        if not workflow.is_file():
            self.skipTest('the source distribution carries no workflow')
        text = workflow.read_text(encoding="utf-8")
        self.assertLess(text.index('python -m build'), text.index('Test the exact source distribution'))
        self.assertLess(text.index('Test the exact source distribution'), text.index('actions/upload-artifact'))
        self.assertEqual(text.count('python -m build'), 1)
        self.assertIn('src/tools/run_tests.py', text)
        self.assertIn('env -u PYTHONPATH', text)
        self.assertIn('--installed', text)
