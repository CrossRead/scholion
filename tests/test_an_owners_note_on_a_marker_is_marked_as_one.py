"""A `genome_link` written into the person's own labs.json is an owner's note, and says so.

Task 168, §4.3. The link «marker ↔ gene» existed in exactly three lines of a
personal labs.json as free text with no source, and the second look printed
them in the same voice as a curated sentence that had passed the gate — which
is precisely what the gate forbids, only in a personal file. Two ways out were
allowed: mark the line as the owner's note, or move it into the curated layer
and through the gate. This build marks it: `genome_link_kind` travels beside
the text so that every renderer can style it as a note, the profile is not
touched, and there is no third state — a link is either marked or absent.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import core
from scholion.engine import labs as L


class TestTheNoteIsMarkedNeverDropped(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        shutil.copytree(support.FIXTURE_PROFILE, self.tmp / "profile")
        p = self.tmp / "profile" / "labs.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        first = next(iter(data["markers"]))
        data["markers"][first]["genome_link"] = "GENE-X (a note the owner typed)"
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.first = first
        self.restore = support.pin_profile(self.tmp / "profile")
        core.reset_cache()

    def tearDown(self):
        self.restore()
        core.reset_cache()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_link_travels_with_its_kind(self):
        rows = {m["key"]: m for m in L.analyze_labs()["markers"]}
        self.assertEqual("GENE-X (a note the owner typed)", rows[self.first]["genome_link"])
        self.assertEqual("owner_note", rows[self.first]["genome_link_kind"])

    def test_a_marker_without_a_link_has_no_kind(self):
        rows = {m["key"]: m for m in L.analyze_labs()["markers"]}
        others = [m for k, m in rows.items() if k != self.first]
        self.assertTrue(others)
        for m in others:
            self.assertIsNone(m.get("genome_link"))
            self.assertIsNone(m.get("genome_link_kind"), "a kind with no link is a third state")

    def test_the_profile_itself_is_not_rewritten(self):
        before = (self.tmp / "profile" / "labs.json").read_text(encoding="utf-8")
        L.analyze_labs()
        self.assertEqual(before, (self.tmp / "profile" / "labs.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
