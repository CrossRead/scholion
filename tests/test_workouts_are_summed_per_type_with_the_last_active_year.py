"""Workouts are summed per type, hours beside sessions, with the last active year.

Sessions are counted per device on purpose: two straps worn on the same day
are two records of one workout, and adding them would report a training
volume nobody did. A file written in the old single-device schema is still
read. Checked on a pinned throw-away profile.
"""
from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import core

# `scholion.engine` re-exports the FUNCTION under this name, so the module has
# to be asked for by its full path.
L = importlib.import_module("scholion.engine.lifestyle")


class _Pinned(unittest.TestCase):

    def _lifestyle_with(self, data: dict) -> dict:
        root = Path(tempfile.mkdtemp(prefix="workouts_"))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "profile").mkdir()
        self.addCleanup(support.pin_profile(root / "profile"))
        self.addCleanup(support.pin_cache(root / "cache"))
        (root / "profile" / "wearable_trends.json").write_text(json.dumps(data), encoding="utf-8")
        core.reset_cache()
        return L.lifestyle()


class TestOneDevice(_Pinned):

    def test_sessions_and_hours_are_summed_and_the_last_year_is_the_latest(self):
        out = self._lifestyle_with({"_meta": {"shape": "x"}, "sources": {"garmin": {
            "metrics": {},
            "workouts": {"2024": {"Running": {"count": 10, "hours": 8.0}},
                         "2025": {"Running": {"count": 4, "hours": 3.5},
                                  "Cycling": {"count": 6, "hours": 9.0}},
                         "junk": "not a table"}}}})
        by = {w["type"]: w for w in out["workouts"]}
        self.assertEqual({"type": "Running", "total": 14, "hours": 11.5,
                          "last_year": "2025", "last_count": 4}, by["Running"])
        self.assertEqual(6, by["Cycling"]["total"])
        self.assertEqual(["Running", "Cycling"], [w["type"] for w in out["workouts"]],
                         "ordered by sessions, most first")

    def test_a_bare_count_is_read_as_sessions_without_hours(self):
        out = self._lifestyle_with({"_meta": {}, "sources": {"apple": {
            "metrics": {}, "workouts": {"2026": {"Walking": 3}}}}})
        (w,) = out["workouts"]
        self.assertEqual(("Walking", 3, 0.0), (w["type"], w["total"], w["hours"]))


class TestTwoDevices(_Pinned):

    def test_the_same_type_on_two_devices_stays_two_rows(self):
        out = self._lifestyle_with({"_meta": {}, "sources": {
            "garmin": {"metrics": {}, "workouts": {"2025": {"Running": {"count": 4, "hours": 3.0}}}},
            "whoop": {"metrics": {}, "workouts": {"2025": {"Running": {"count": 4, "hours": 3.0}}}}}})
        types = sorted(w["type"] for w in out["workouts"])
        self.assertEqual(["Running · garmin", "Running · whoop"], types)
        self.assertNotIn("Running", types, "two records of one workout were added up")


class TestTheOldSchema(_Pinned):

    def test_a_file_with_type_then_year_is_still_read(self):
        out = self._lifestyle_with({"Workouts": {"Walking": {"2023": 5, "2024": 7}, "Odd": {}}})
        (w,) = out["workouts"]
        self.assertEqual(("Walking", 12, "2024", 7),
                         (w["type"], w["total"], w["last_year"], w["last_count"]))


if __name__ == "__main__":
    unittest.main()
