"""What a loader has already read is remembered beside the profile it went into.

Task 133. `ingest-labs` and `ingest-studies` keep a manifest — path and mtime of
every file taken — so that a second run over the same folder reads only what
changed. It lived in the application-wide cache, `core.cache_dir()`, and the
cache does not follow `SCHOLION_PROFILE_DIR`. So every ingest test of the
suite, pinning a temporary profile as it should, still wrote its temporary
folders into the OWNER's real list of processed files: 412 KB of dead paths on
the day this was written. Harmless in effect and the same class of defect as
task 125 — a test touching state outside its fixture — which the suite promises
in its own header not to do.

The manifest now lives in the profile directory, so a pinned profile has its
own. Three things are held here:

  * the manifest is written INSIDE the pinned profile, and nothing is written
    under the cache directory at all;
  * a list left in the cache by an earlier version is carried over on first use,
    the run says so once, and no file is read as new because of the move;
  * every in-process test that runs an ingest pins the cache as well as the
    profile — because the carry-over reads the cache, and a test that leaves it
    unpinned reads whatever the machine holds there — and the shared fixture
    `tests/fixtures/profile` holds no manifest, so no test ingested into it.
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil
import tempfile
import unittest
from unittest import mock

import support
from scholion import core, ingest_labs, ingest_studies

TESTS = pathlib.Path(__file__).resolve().parent

TABLE = """Date,Test,Result,Units,Reference Range
2018-05-22,Ferritin,12,ng/mL,13-150
2018-05-22,Glucose,5.1,mmol/L,3.9-5.5
"""

ULTRASOUND = (TESTS / "fixtures" / "studies" / "01_ultrasound.txt").read_text(encoding="utf-8")


class Pinned(unittest.TestCase):
    """A temporary profile, a temporary cache that is NOT created, and a folder.

    The cache directory is left uncreated on purpose: the assertion «nothing was
    written there» is then «it still does not exist», which cannot be satisfied
    by a write that happened to be empty.
    """

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="manifest-")).resolve()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.cache = self.root / "cache"
        self.forms = self.root / "forms"
        self.forms.mkdir()
        self._restore_profile = support.pin_profile(self.profile)
        self._restore_cache = support.pin_cache(self.cache)
        core.reset_cache()

    def tearDown(self):
        self._restore_profile()
        self._restore_cache()
        core.reset_cache()
        shutil.rmtree(self.root, ignore_errors=True)

    def a_table(self) -> pathlib.Path:
        f = self.forms / "phenotypes.csv"
        f.write_text(TABLE, encoding="utf-8")
        return f

    def a_pdf(self) -> pathlib.Path:
        f = self.forms / "u.pdf"
        f.write_bytes(b"%PDF-1.4\n")
        return f

    def ingest_studies(self, **kw):
        """What a PDF contains is the reader's business and is stubbed; the
        walk, the manifest and the mtimes are real."""
        with mock.patch.object(ingest_studies, "_read_pdf", return_value=ULTRASOUND), \
                mock.patch.object(ingest_studies, "_ensure_extractor", return_value=True):
            return ingest_studies.ingest(str(self.forms), **kw)

    def written_under_cache(self):
        return sorted(str(p) for p in self.cache.rglob("*") if p.is_file()) \
            if self.cache.exists() else []


class TestTheManifestFollowsTheProfile(Pinned):

    def test_labs_writes_its_manifest_inside_the_profile_and_nothing_in_the_cache(self):
        table = self.a_table()
        r = ingest_labs.ingest(str(self.forms), force=True)
        self.assertTrue(r["ok"], r.get("error"))
        manifest = ingest_labs._manifest_file()
        self.assertEqual(manifest.parent, self.profile.resolve())
        self.assertTrue(manifest.exists(), "the run left no manifest beside the profile")
        self.assertEqual({str(table)}, set(ingest_labs._load_manifest()))
        self.assertEqual([], self.written_under_cache())
        self.assertIsNone(r["manifest_moved"], "nothing was in the cache to carry over")

    def test_studies_writes_its_manifest_inside_the_profile_and_nothing_in_the_cache(self):
        pdf = self.a_pdf()
        r = self.ingest_studies()
        self.assertTrue(r["ok"], r.get("error"))
        manifest = ingest_studies._manifest_file()
        self.assertEqual(manifest.parent, self.profile.resolve())
        self.assertEqual({str(pdf)}, set(ingest_studies._load_manifest()))
        self.assertEqual([], self.written_under_cache())
        self.assertIsNone(r["manifest_moved"])

    def test_the_two_loaders_keep_separate_files(self):
        """One file for both would make two commands writers of one table, and
        each loads at its start and saves at its end."""
        self.assertNotEqual(ingest_labs._manifest_file(), ingest_studies._manifest_file())

    def test_the_file_explains_itself_to_whoever_opens_it(self):
        """It sits next to `labs.json` now, where a person will open it."""
        self.a_table()
        ingest_labs.ingest(str(self.forms), force=True)
        data = json.loads(ingest_labs._manifest_file().read_text(encoding="utf-8"))
        self.assertIn("files", data)
        self.assertIn("shape", data["_meta"])
        self.assertEqual("labs", data["_meta"]["loader"])

    def test_a_second_run_skips_what_the_first_one_read(self):
        """The reason a manifest exists at all, checked in its new place."""
        self.a_table()
        ingest_labs.ingest(str(self.forms), force=True)
        r = ingest_labs.ingest(str(self.forms))
        self.assertEqual(1, r["skipped"])
        self.assertEqual(0, r["files_processed"])


class TestTheOldListIsCarriedOver(Pinned):

    def old_manifest(self, loader: str, entries) -> pathlib.Path:
        """The shape the file had in the cache: the table itself, nothing around it."""
        self.cache.mkdir()
        old = self.cache / f"ingest_{loader}_manifest.json"
        old.write_text(json.dumps(entries), encoding="utf-8")
        return old

    def test_labs_reads_nothing_as_new_because_of_the_move(self):
        table = self.a_table()
        old = self.old_manifest("labs", {str(table): table.stat().st_mtime})
        r = ingest_labs.ingest(str(self.forms))
        self.assertTrue(r["ok"], r.get("error"))
        self.assertEqual(1, r["skipped"], "a file already read was read again after the move")
        self.assertEqual(0, r["files_processed"])
        moved = r["manifest_moved"]
        self.assertEqual(1, moved["entries"])
        self.assertEqual(str(old), moved["from"])
        self.assertEqual(str(ingest_labs._manifest_file()), moved["to"])
        self.assertIn("1 entry", moved["note"])
        self.assertEqual({str(table)}, set(ingest_labs._load_manifest()))

    def test_it_is_said_once(self):
        table = self.a_table()
        self.old_manifest("labs", {str(table): table.stat().st_mtime})
        ingest_labs.ingest(str(self.forms))
        again = ingest_labs.ingest(str(self.forms))
        self.assertIsNone(again["manifest_moved"])
        self.assertEqual(1, again["skipped"])

    def test_the_old_file_is_left_where_it_was(self):
        """Copied, not moved: one list served every profile ever pointed at, so
        the loader cannot tell whose it is running for — and deleting is the one
        step that cannot be undone."""
        table = self.a_table()
        old = self.old_manifest("labs", {str(table): table.stat().st_mtime})
        ingest_labs.ingest(str(self.forms))
        self.assertTrue(old.exists())

    def test_studies_reads_nothing_as_new_because_of_the_move(self):
        pdf = self.a_pdf()
        self.old_manifest("studies", {str(pdf): pdf.stat().st_mtime})
        r = self.ingest_studies()
        self.assertTrue(r["ok"], r.get("error"))
        self.assertEqual(1, r["skipped_unchanged"])
        self.assertEqual(0, r["added"])
        self.assertEqual(1, r["manifest_moved"]["entries"])
        self.assertEqual({str(pdf)}, set(ingest_studies._load_manifest()))

    def test_a_profile_with_a_list_of_its_own_keeps_it(self):
        """The old list is for a profile that has none; one that has is not overwritten."""
        table = self.a_table()
        ingest_labs.ingest(str(self.forms), force=True)          # the profile now has its own
        self.old_manifest("labs", {"/somewhere/else.pdf": 1.0})
        r = ingest_labs.ingest(str(self.forms))
        self.assertIsNone(r["manifest_moved"])
        self.assertEqual({str(table)}, set(ingest_labs._load_manifest()))

    def test_an_old_list_that_will_not_parse_costs_one_read_and_is_left_alone(self):
        table = self.a_table()
        old = self.old_manifest("labs", {})
        old.write_text("{ broken", encoding="utf-8")
        r = ingest_labs.ingest(str(self.forms))
        self.assertTrue(r["ok"], r.get("error"))
        self.assertEqual(1, r["files_processed"])
        self.assertIsNone(r["manifest_moved"])
        self.assertTrue(old.exists())
        self.assertEqual({str(table)}, set(ingest_labs._load_manifest()))


#: an ingest run inside the test process — the CLI's own entry point included
INGESTS = re.compile(r"ingest_(?:labs|studies)\.ingest\(|cli\.main\(\[\"ingest-(?:labs|studies)\"")
#: the cache pinned in that file, either by hand or through the helper
CACHE_PINNED = re.compile(r"SCHOLION_CACHE_DIR|pin_cache\(")


class TestNoTestReadsAnyoneElsesCache(unittest.TestCase):

    def test_every_test_that_ingests_in_process_pins_the_cache(self):
        """The carry-over reads `core.cache_dir()`. A test that pins only the
        profile therefore reads whatever the machine holds in its cache — on the
        owner's machine, the owner's list — and carries it into its temporary
        profile. The result differs by machine, which is the defect this file is
        about, one step removed."""
        unpinned = []
        for path in sorted(TESTS.glob("test_*.py")):
            text = path.read_text(encoding="utf-8")
            if INGESTS.search(text) and not CACHE_PINNED.search(text):
                unpinned.append(path.name)
        self.assertEqual([], unpinned,
                         "these tests run an ingest without pinning SCHOLION_CACHE_DIR "
                         "(support.pin_cache): " + ", ".join(unpinned))

    def test_the_shared_fixture_holds_no_manifest(self):
        """`tests/fixtures/profile` is tracked by git. A manifest there means a
        test ingested into the shared fixture, and every later run of that test
        starts from what the previous one left."""
        left = sorted(p.name for p in support.FIXTURE_PROFILE.glob("ingest_*_manifest.json"))
        self.assertEqual([], left)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
