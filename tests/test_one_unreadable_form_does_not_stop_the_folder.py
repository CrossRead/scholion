"""A file the reader falls over on is named, and the files after it are still read.

Task 124, and the second suggestion in GitHub issue #1. The per-file loop of
`ingest-labs` had no `try`: an exception inside one file aborted the whole
batch, the remaining files were never opened, and from the outside the command
had simply died on a folder. `not_ingested` (task 69) already named every file
dropped for a reason somebody had foreseen; a reason nobody had did not reach
it.

What a person could have got: forty forms in a folder, one of them odd, and a
traceback instead of thirty-nine panels — with no way to tell which file was
the odd one short of bisecting the folder by hand.

The owner's decision of 08.09.2026, held here: the exception is caught at file
level and recorded as `reason: error` with its type and text; the walk goes on;
the errors are printed at the end; and the command exits non-zero, because a
partial result reported as a clean one would be silence of the kind rule 9
forbids. The failed file is also left out of the manifest, so the next run
tries it again rather than skipping it as «unchanged».
"""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import support

GOOD = """Date,Test,Result,Units,Reference Range
2018-05-22,Ferritin,12,ng/mL,13-150
"""


class _Folder(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.forms = self.root / "forms"
        self.forms.mkdir()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self._restore = support.pin_profile(self.profile)
        # The cache too: the loader's list of already-read files lives beside
        # the profile now, and an old list found in the cache is carried over.
        self._restore_cache = support.pin_cache(self.root / "cache")
        from scholion import core, ingest_labs
        core.reset_cache()
        # `bad.csv` sorts before `good.csv`: the file that raises comes FIRST,
        # so a good form reaching the profile proves the walk went on past it.
        (self.forms / "bad.csv").write_text(GOOD, encoding="utf-8")
        (self.forms / "good.csv").write_text(GOOD, encoding="utf-8")
        self._read_any = ingest_labs._read_any

        def read_or_raise(path):
            if path.name == "bad.csv":
                raise RuntimeError("a shape nobody foresaw")
            return self._read_any(path)
        ingest_labs._read_any = read_or_raise

    def tearDown(self):
        from scholion import core, ingest_labs
        ingest_labs._read_any = self._read_any
        self._restore()
        self._restore_cache()
        core.reset_cache()
        self.tmp.cleanup()

    def ingest(self):
        from scholion import ingest_labs
        return ingest_labs.ingest(str(self.forms), force=True)


class TestTheGoodFormStillReachesTheProfile(_Folder):

    def test_the_points_after_the_failure_are_stored(self):
        r = self.ingest()
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["points_added"], 1)
        labs = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))
        self.assertEqual(labs["markers"]["ferritin"]["series"][0]["value"], 12.0)

    def test_the_failed_file_is_named_with_the_exception(self):
        r = self.ingest()
        failed = [n for n in r["not_ingested"] if n["reason"] == "error"]
        self.assertEqual([n["file"] for n in failed], ["bad.csv"])
        self.assertIn("RuntimeError", failed[0]["detail"])
        self.assertIn("a shape nobody foresaw", failed[0]["detail"])
        self.assertEqual(r["errors"], ["bad.csv"])

    def test_the_failed_file_is_tried_again_next_run(self):
        from scholion import ingest_labs
        self.ingest()
        # Full paths: the manifest is one for the whole application, so it also
        # remembers what other tests fed it from other temporary folders.
        remembered = set(ingest_labs._load_manifest())
        self.assertIn(str(self.forms / "good.csv"), remembered)
        self.assertNotIn(str(self.forms / "bad.csv"), remembered,
                         "a file that was not read was recorded as read")

    def test_the_report_prints_the_failure_and_the_footer(self):
        from scholion import format as fmt
        text = fmt.ingest_labs_report(self.ingest())
        self.assertIn("bad.csv", text)
        self.assertIn("RuntimeError", text)


class TestTheCommandExitsNonZero(_Folder):

    def test_the_exit_status_says_the_run_was_partial(self):
        from scholion import cli
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["ingest-labs", str(self.forms), "--force", "--json"])
        self.assertNotEqual(code, 0, "a partial result exited as a clean one")
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["errors"], ["bad.csv"])
        self.assertEqual(payload["points_added"], 1)

    def test_a_folder_with_no_failure_still_exits_clean(self):
        from scholion import cli, ingest_labs
        ingest_labs._read_any = self._read_any
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["ingest-labs", str(self.forms), "--force", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["errors"], [])


if __name__ == "__main__":
    unittest.main()
