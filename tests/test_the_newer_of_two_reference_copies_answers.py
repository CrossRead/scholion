"""The newer of two reference copies answers.

A reference file refreshed on this machine lives beside the data; the package
carries its own copy. The local one used to win by EXISTING, so after an upgrade a
newer bundled copy lost to a months-old import and nothing said so (13.09.2026).
Now the newer stamp answers, a local copy with no stamp keeps the old precedence
and says it could not be compared, and every bundled file carries a stamp so the
comparison is possible at all.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401
from scholion import core, sources


class TestEveryBundledFileCarriesAStamp(unittest.TestCase):

    def test_a_stamp_the_comparison_can_read(self):
        missing = [p.name for p in sorted(core._KNOWLEDGE_DIR.glob("*.json"))
                   if core._knowledge_stamp(p) is None]
        self.assertEqual([], missing, "a bundled reference file carries no date to compare a local copy with")


class TestThePrecedence(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="kprec_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        patch = mock.patch.dict(os.environ, {"SCHOLION_REPO_DIR": str(self.root)})
        patch.start(); self.addCleanup(patch.stop)
        self.local_dir = core.knowledge_dir_local()
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.bundled = core._KNOWLEDGE_DIR / "units.json"
        self.bundled_stamp = core._knowledge_stamp(self.bundled)

    def _local(self, meta):
        data = json.loads(self.bundled.read_text(encoding="utf-8"))
        data["_meta"] = meta
        (self.local_dir / "units.json").write_text(json.dumps(data), encoding="utf-8")

    def test_a_bundled_copy_newer_than_the_local_import_answers(self):
        self._local({"imported": {"fetched": "2020-01-01"}})
        prec = core.knowledge_precedence("units.json")
        self.assertEqual(("bundled", "bundled_newer"), (prec["answers"], prec["why"]))
        self.assertEqual(self.bundled, core.knowledge_path("units.json"))
        self.assertFalse(core.knowledge_is_local("units.json"))

    def test_a_local_import_newer_than_the_bundle_answers(self):
        self._local({"fetched": "2099-01-01"})
        prec = core.knowledge_precedence("units.json")
        self.assertEqual(("local", "local_newer"), (prec["answers"], prec["why"]))
        self.assertTrue(core.knowledge_is_local("units.json"))

    def test_a_local_copy_with_no_stamp_keeps_the_old_precedence_and_says_so(self):
        self._local({"purpose": "no date here"})
        prec = core.knowledge_precedence("units.json")
        self.assertEqual(("local", "unstamped"), (prec["answers"], prec["why"]))

    def test_no_local_copy_is_the_bundle(self):
        prec = core.knowledge_precedence("units.json")
        self.assertEqual(("bundled", "no_local"), (prec["answers"], prec["why"]))
        self.assertEqual(self.bundled_stamp, prec["bundled_stamp"])

    def test_the_sources_register_says_which_copy_answers(self):
        for s in sources.state():
            for f in s["files"]:
                with self.subTest(file=f["file"]):
                    self.assertIn(f["answers"], ("local", "bundled"))
                    self.assertIn(f["why_answers"], ("no_local", "bundled_newer", "local_newer", "unstamped"))


if __name__ == "__main__":
    unittest.main()
