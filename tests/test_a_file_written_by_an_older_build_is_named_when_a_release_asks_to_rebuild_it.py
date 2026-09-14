"""A file written by an older build is named when a release asks to rebuild it.

Every release note says what to recompute, and until 13.09.2026 nothing in a
person's files said which build wrote them, so «re-run the import» stayed a request
in a journal. Every profile file now carries the build that wrote it, and
`scholion version` names the files a later release asks to rebuild.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support
import scholion
from scholion import core, format as fmt, updates


class _Profile(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="engine_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.addCleanup(support.pin_profile(self.profile))
        self.addCleanup(support.pin_cache(self.root / "cache"))


class TestTheStamp(_Profile):

    def test_a_profile_file_carries_the_build_that_wrote_it(self):
        core.write_json(self.profile / "labs.json", {"markers": {}})
        meta = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))["_meta"]
        self.assertEqual(scholion.__version__, meta["engine"])
        self.assertEqual(core.PROFILE_SCHEMA, meta["schema"])

    def test_a_file_outside_the_profile_is_not_stamped(self):
        other = self.root / "cache" / "x.json"
        core.write_json(other, {"a": 1})
        self.assertNotIn("_meta", json.loads(other.read_text(encoding="utf-8")))


class TestTheReport(_Profile):

    def _labs(self, engine):
        meta = {"schema": 1}
        if engine:
            meta["engine"] = engine
        (self.profile / "labs.json").write_text(json.dumps({"_meta": meta, "markers": {}}), encoding="utf-8")

    def test_a_file_written_before_a_release_that_asks_for_its_import_is_named(self):
        self._labs("0.4.8")
        wb = updates.written_before()
        (row,) = [f for f in wb["files"] if f["file"] == "labs.json"]
        releases = {a["version"] for a in row["asks"]}
        self.assertIn("0.4.9", releases)
        self.assertNotIn("0.4.8", releases, "the release that wrote it is not asking to rebuild it")
        self.assertTrue(all(c.startswith("scholion ingest-labs") or c.startswith("scholion import-labs")
                            for a in row["asks"] for c in a["commands"]))
        text = fmt.version_report(updates.status())
        self.assertIn("labs.json", text)
        self.assertIn("0.4.8", text)

    def test_a_file_written_by_this_build_is_not_named(self):
        self._labs(scholion.__version__)
        self.assertEqual([], updates.written_before()["files"])

    def test_a_file_without_the_stamp_is_counted_not_guessed(self):
        self._labs(None)
        wb = updates.written_before()
        self.assertEqual([], wb["files"])
        self.assertEqual(["labs.json"], wb["unstamped"])
        self.assertIn("scholion version --since", fmt.version_report(updates.status()))


if __name__ == "__main__":
    unittest.main()
