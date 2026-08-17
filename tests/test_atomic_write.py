"""Writing the profile never leaves a file half-written.

The point of this test is not "writing works" (the smoke pass checks that) but
the behaviour on an INTERRUPTION. Overwriting in place first truncates the file:
a process killed at that moment leaves behind truncated JSON, and a `labs.json`
holding years of history stops parsing at all. We check the property the write
was reworked for: at any moment the target path holds either the old version in
full, or the new one.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from scholion import core


class TestAtomicWrite(unittest.TestCase):

    def test_interruption_during_write_does_not_damage_the_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "labs.json"
            core.write_json(target, {"markers": {"ldl": 3.1}})

            # an object that serialises halfway and then fails: exactly what a
            # killed process does, only deterministically
            class Explosion:
                def __repr__(self): return "<Explosion>"

            with self.assertRaises(TypeError):
                core.write_json(target, {"markers": {"ldl": 3.1}, "bad": Explosion()})

            # the previous content is in place and parses
            data = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(data["markers"]["ldl"], 3.1,
                             "a failed write damaged the previous file")

    def test_temporary_file_does_not_remain(self):
        """Debris next to the profile reads to a human as "something broke"."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "labs.json"
            core.write_json(target, {"a": 1})
            with self.assertRaises(TypeError):
                core.write_json(target, {"b": object()})
            leftovers = [p.name for p in Path(tmp).iterdir() if p.name != "labs.json"]
            self.assertEqual(leftovers, [], f"files were left behind: {leftovers}")

    def test_directory_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "missing" / "nested" / "labs.json"
            core.write_json(target, {"a": 1})
            self.assertTrue(target.exists())

    def test_file_permissions_are_not_widened(self):
        """The temporary file is created with the process umask, not with 0666:
        medical data must not become more accessible than before after a rewrite."""
        if os.name != "posix":
            self.skipTest("the permissions check is POSIX-only")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "labs.json"
            core.write_json(target, {"a": 1})
            mode = target.stat().st_mode & 0o777
            self.assertEqual(mode & 0o007, 0, f"the file is readable by outsiders: {oct(mode)}")


if __name__ == "__main__":
    unittest.main()
