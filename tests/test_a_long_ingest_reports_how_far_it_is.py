"""A long ingest reports how far it is, and a stop records no form as read.

Reading a folder of forms again took minutes and printed nothing until the end,
so a person looking at it could not tell working from hung. The loaders now call
a progress function once per file — outside the per-file `try`, so a stop raised
from it ends the run rather than being recorded as «this file failed».

What a stop leaves is held as it is: the points of the forms already read are in
the profile (the loader writes as it reads), and the list of forms read is saved
only at the end, so no form is remembered and the next run reads the whole
folder again.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import support

GOOD = """Date,Test,Result,Units,Reference Range
2018-05-22,Ferritin,12,ng/mL,13-150
"""


class Stop(Exception):
    pass


class TestTheLabsLoaderReportsProgress(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.forms = self.root / "forms"
        self.forms.mkdir()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self._restore = support.pin_profile(self.profile)
        self._restore_cache = support.pin_cache(self.root / "cache")
        from scholion import core
        core.reset_cache()
        for name in ("a.csv", "b.csv", "c.csv"):
            (self.forms / name).write_text(GOOD, encoding="utf-8")

    def tearDown(self):
        from scholion import core
        self._restore()
        self._restore_cache()
        core.reset_cache()
        self.tmp.cleanup()

    def test_one_call_per_file_with_its_name(self):
        from scholion import ingest_labs
        calls = []
        r = ingest_labs.ingest(str(self.forms), force=True,
                               progress=lambda done, total, item=None: calls.append((done, total, item)))
        self.assertTrue(r["ok"], r)
        self.assertEqual([(0, 3, "a.csv"), (1, 3, "b.csv"), (2, 3, "c.csv")], calls)

    def test_a_stop_from_the_progress_remembers_no_form_and_the_next_run_reads_them_all(self):
        from scholion import ingest_labs

        def tick(done, total, item=None):
            if done == 1:
                raise Stop()

        with self.assertRaises(Stop):
            ingest_labs.ingest(str(self.forms), force=True, progress=tick)
        remembered = set(ingest_labs._load_manifest())
        for name in ("a.csv", "b.csv", "c.csv"):
            self.assertNotIn(str(self.forms / name), remembered,
                             "a stopped run recorded a form as read")
        calls = []
        r = ingest_labs.ingest(str(self.forms), progress=lambda d, n, item=None: calls.append(item))
        self.assertTrue(r["ok"], r)
        self.assertEqual(["a.csv", "b.csv", "c.csv"], calls)
        self.assertEqual(0, r["skipped"], "the run after a stop skipped a form as unchanged")


if __name__ == "__main__":
    unittest.main()
