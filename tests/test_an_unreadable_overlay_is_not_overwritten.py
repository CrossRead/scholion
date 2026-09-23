"""A local marker file that does not parse is not an empty one.

The 0.5.7 review: the overlay reader returned an empty overlay on a parse
error, and the next proposal wrote that empty overlay back with one entry —
every confirmed marker, unit and row rule the person had vouched for, gone.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import support
from scholion import core, markers_local


class TestTheOverlayIsKept(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile = Path(self.tmp.name).resolve() / "profile"
        self.profile.mkdir()
        self._restore = support.pin_profile(self.profile)
        core.reset_cache()

    def tearDown(self):
        self._restore()
        core.reset_cache()
        self.tmp.cleanup()

    def test_a_write_over_a_broken_file_is_refused_and_the_file_stays(self):
        path = core.markers_overlay_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        broken = '{"markers": {"my_marker": {"status": "confirmed"'
        path.write_text(broken, encoding="utf-8")
        r = markers_local.propose("another", names_en=["another"], unit="mg/L")
        self.assertFalse(r["ok"])
        self.assertEqual(broken, path.read_text(encoding="utf-8"))

    def test_no_file_at_all_is_still_an_empty_overlay(self):
        r = markers_local.propose("another", names_en=["another"], unit="mg/L")
        self.assertTrue(r["ok"], r)


if __name__ == "__main__":
    unittest.main()
