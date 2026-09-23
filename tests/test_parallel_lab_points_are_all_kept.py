"""Twelve lab points written at once from twelve threads are twelve points.

The 0.5.7 review reproduced a lost update: `add_lab_point` read labs.json,
added its point and wrote the file back without holding the profile lock, so
concurrent writers from the web server's threads overwrote one another and one
or two of twelve points survived. The temporary file of each write was named by
the process id alone, so two threads of one process also raced on one name.
"""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

import support
from scholion import core, store


class TestParallelWrites(unittest.TestCase):

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

    def test_every_point_survives(self):
        errors = []

        def write(day):
            try:
                r = store.add_lab_point("ferritin", f"2024-03-{day:02d}", 30.0 + day,
                                        unit="ng/mL", subject="owner", date_source="manual")
                if not r.get("ok"):
                    errors.append(r)
            except Exception as exc:                                 # noqa: BLE001
                errors.append(repr(exc))

        threads = [threading.Thread(target=write, args=(d,)) for d in range(1, 13)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual([], errors)
        labs = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))
        self.assertEqual(12, len(labs["markers"]["ferritin"]["series"]))


if __name__ == "__main__":
    unittest.main()
