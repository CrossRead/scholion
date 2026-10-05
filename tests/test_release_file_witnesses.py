"""Cross-platform witnesses must not mistake edits for unchanged input."""
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import acmg_scan, core


class TestJsonEditsInvalidateTheCache(unittest.TestCase):
    def test_same_float_time_with_new_nanoseconds_is_reread(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "note.json"
            path.write_text('{"text":"old"}', encoding="utf-8")
            stamp = types.SimpleNamespace(st_mtime=1.0, st_mtime_ns=1,
                                          st_ctime_ns=1, st_size=14, st_dev=1, st_ino=1)
            with mock.patch.object(Path, "stat", return_value=stamp):
                self.assertEqual("old", core._read_json(path)["text"])
                path.write_text('{"text":"new"}', encoding="utf-8")
                stamp.st_mtime_ns = 2
                self.assertEqual("new", core._read_json(path)["text"])

    def test_changed_size_with_restored_mtime_is_not_an_old_valid_note(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "note.json"
            path.write_text('{"text":"old"}', encoding="utf-8")
            self.assertEqual("old", core._read_json(path)["text"])
            stamp = path.stat()
            path.write_text("{broken", encoding="utf-8")
            os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            with self.assertRaises(json.JSONDecodeError):
                core._read_json(path)


class TestWindowsGenomeIdentity(unittest.TestCase):
    def test_path_and_descriptor_ctime_disagreement_is_not_a_changed_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.vcf"
            path.write_bytes(b"synthetic")
            real_fstat = os.fstat

            def descriptor(fd):
                stamp = real_fstat(fd)
                return types.SimpleNamespace(**{
                    name: getattr(stamp, name) for name in
                    ("st_mode", "st_dev", "st_ino", "st_size", "st_mtime_ns")},
                    st_ctime_ns=stamp.st_ctime_ns + 100)

            windows = mock.Mock(wraps=os)
            windows.name = "nt"
            windows.fstat = descriptor
            with mock.patch.object(acmg_scan, "os", windows), \
                    mock.patch.object(acmg_scan, "_windows_change_time", return_value=123):
                identity = acmg_scan.source_identity(path)
            self.assertEqual(123, identity["change_time"])
            self.assertEqual(9, identity["st_size"])

    def test_reopened_path_with_a_new_change_time_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "source.vcf"
            path.write_bytes(b"synthetic")
            windows = mock.Mock(wraps=os)
            windows.name = "nt"
            with mock.patch.object(acmg_scan, "os", windows), \
                    mock.patch.object(acmg_scan, "_windows_change_time", side_effect=[123, 123, 124]):
                with self.assertRaisesRegex(OSError, "source changed"):
                    acmg_scan.source_identity(path)
