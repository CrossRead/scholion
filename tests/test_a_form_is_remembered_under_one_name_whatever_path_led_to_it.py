"""A file goes into the manifest under one name, whatever path led to it.

Both loaders remember what they have already read as `path -> mtime`, and skip
a file whose mtime has not moved. The name was whatever string the caller had
typed. A relative one — `ingest-labs ../forms` — was therefore resolved against
the working directory of whoever ran the command, which is a property of the
run and not of the file: the owner's manifest held 184 keys of that shape.

Two folders reached by the same relative name from two different directories,
a file of the same name and the same mtime in each, and the second file is
skipped as «already read» without ever having been opened — a form that exists,
was never refused, and whose points are simply absent. The equal mtime is what
makes it rare; copying is what makes it possible, because `cp -p`, rsync and
every cloud sync carry the mtime over with the bytes.

The name is now the resolved absolute path (`core.manifest_lookup`). The first
test here is that wrong answer. The rest hold the two consequences: several
paths to one file are one entry, and a key written by an earlier version is
honoured once and then renamed, so this change costs nobody a re-read.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

import support
from scholion import core, ingest_labs, ingest_studies

TESTS = pathlib.Path(__file__).resolve().parent

FERRITIN_2018 = """Date,Test,Result,Units,Reference Range
2018-05-22,Ferritin,12,ng/mL,13-150
"""
FERRITIN_2019 = """Date,Test,Result,Units,Reference Range
2019-06-01,Ferritin,40,ng/mL,13-150
"""
ULTRASOUND = (TESTS / "fixtures" / "studies" / "01_ultrasound.txt").read_text(encoding="utf-8")

STAMP = 1_600_000_000.0      # one mtime for every file written here, so that
                             # «unchanged since last run» is true of all of them


class Pinned(unittest.TestCase):
    """A temporary profile and cache, and a place to build folders in.

    The temporary root is resolved in `setUp`: on macOS `TMPDIR` lives under
    `/var`, which is a symlink, so an unresolved root would make every
    assertion about resolved names pass for the wrong reason.
    """

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="one-name-")).resolve()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.cache = self.root / "cache"
        self._restore_profile = support.pin_profile(self.profile)
        self._restore_cache = support.pin_cache(self.cache)
        self._cwd = os.getcwd()
        core.reset_cache()

    def tearDown(self):
        os.chdir(self._cwd)
        self._restore_profile()
        self._restore_cache()
        core.reset_cache()
        shutil.rmtree(self.root, ignore_errors=True)

    def a_form(self, folder: pathlib.Path, text: str, name="phenotypes.csv") -> pathlib.Path:
        folder.mkdir(parents=True, exist_ok=True)
        f = folder / name
        f.write_text(text, encoding="utf-8")
        os.utime(f, (STAMP, STAMP))
        return f

    def a_pdf(self, folder: pathlib.Path, name="u.pdf") -> pathlib.Path:
        folder.mkdir(parents=True, exist_ok=True)
        f = folder / name
        f.write_bytes(b"%PDF-1.4\n")
        os.utime(f, (STAMP, STAMP))
        return f

    def ingest_studies(self, folder, **kw):
        with mock.patch.object(ingest_studies, "_read_pdf", return_value=ULTRASOUND), \
                mock.patch.object(ingest_studies, "_ensure_extractor", return_value=True):
            return ingest_studies.ingest(str(folder), **kw)

    def manifest(self) -> dict:
        return ingest_labs._load_manifest()


class TestTheWrongAnswerThisPrevents(Pinned):

    def test_the_same_relative_name_in_two_places_is_two_files(self):
        """The defect, as a person would have met it: a form present, never
        refused, never counted as skipped for a reason anyone could read, and
        its points missing from the history."""
        a = self.a_form(self.root / "a" / "forms", FERRITIN_2018)
        b = self.a_form(self.root / "b" / "forms", FERRITIN_2019)
        self.assertEqual(a.stat().st_mtime, b.stat().st_mtime,
                         "the two files must be indistinguishable by mtime, or "
                         "this test passes without touching the defect")

        os.chdir(self.root / "a")
        first = ingest_labs.ingest("forms")
        self.assertTrue(first["ok"], first.get("error"))
        self.assertEqual(1, first["files_processed"])

        os.chdir(self.root / "b")
        second = ingest_labs.ingest("forms")
        self.assertTrue(second["ok"], second.get("error"))
        self.assertEqual(0, second["skipped"],
                         "a file in another folder was taken for one already read")
        self.assertEqual(1, second["files_processed"])
        self.assertGreater(second["points_added"], 0,
                           "the second form went in without leaving a point")

    def test_both_files_are_in_the_table_under_absolute_names(self):
        self.a_form(self.root / "a" / "forms", FERRITIN_2018)
        self.a_form(self.root / "b" / "forms", FERRITIN_2019)
        os.chdir(self.root / "a")
        ingest_labs.ingest("forms")
        os.chdir(self.root / "b")
        ingest_labs.ingest("forms")
        keys = set(self.manifest())
        self.assertEqual({str(self.root / "a" / "forms" / "phenotypes.csv"),
                          str(self.root / "b" / "forms" / "phenotypes.csv")}, keys)
        for k in keys:
            self.assertTrue(pathlib.Path(k).is_absolute())
            self.assertNotIn("..", k)


class TestSeveralPathsAreOneEntry(Pinned):

    def test_a_path_that_walks_through_a_parent_is_the_same_file(self):
        self.a_form(self.root / "forms", FERRITIN_2018)
        ingest_labs.ingest(str(self.root / "forms"))
        again = ingest_labs.ingest(str(self.root / "forms" / ".." / "forms"))
        self.assertEqual(1, again["skipped"])
        self.assertEqual(0, again["points_added"])
        self.assertEqual(1, len(self.manifest()))

    def test_a_folder_reached_through_a_symlink_is_the_same_file(self):
        self.a_form(self.root / "forms", FERRITIN_2018)
        link = self.root / "link"
        try:
            link.symlink_to(self.root / "forms", target_is_directory=True)
        except (OSError, NotImplementedError):      # Windows without the privilege
            self.skipTest("this filesystem does not make symbolic links")
        ingest_labs.ingest(str(self.root / "forms"))
        again = ingest_labs.ingest(str(link))
        self.assertEqual(1, again["skipped"], "the same file under a second path was read twice")
        self.assertEqual(1, len(self.manifest()))


class TestAnOlderKeyCostsNoReread(Pinned):
    """The migration. Every manifest in existence is keyed the old way, so a
    change that made those entries invisible would answer one rare defect with
    a full re-read of everybody's folder — and sparing a re-read of 237 forms
    is the whole reason the manifest exists.

    The entry is honoured when the command is run the way it was run before,
    which is how a person runs it: the same folder, typed the same way, out of
    the same directory. That run renames the entry, and the old spelling is
    gone from the file afterwards.
    """

    def seed(self, loader: str, typed: pathlib.Path) -> None:
        core.write_ingest_manifest(loader, {str(typed): typed.stat().st_mtime})

    def test_labs_honours_the_old_spelling_once_and_then_renames_it(self):
        real = self.a_form(self.root / "forms", FERRITIN_2018)
        folder = self.root / "forms" / ".." / "forms"
        typed = folder / "phenotypes.csv"
        self.assertNotEqual(str(typed), str(real))
        self.seed("labs", typed)

        r = ingest_labs.ingest(str(folder))
        self.assertEqual(1, r["skipped"], "an entry written by an earlier version was not seen")
        self.assertEqual(0, r["files_processed"])

        after = set(self.manifest())
        self.assertEqual({str(real)}, after)
        self.assertNotIn(str(typed), after, "the old spelling stayed behind in the file")

    def test_studies_honours_the_old_spelling_once_and_then_renames_it(self):
        real = self.a_pdf(self.root / "docs")
        folder = self.root / "docs" / ".." / "docs"
        self.seed("studies", folder / "u.pdf")

        r = self.ingest_studies(folder)
        self.assertTrue(r["ok"], r.get("error"))
        self.assertEqual(1, r["skipped_unchanged"])
        self.assertEqual({str(real)}, set(ingest_studies._load_manifest()))

    def test_the_renamed_entry_is_what_the_file_on_disk_holds(self):
        """Renaming in memory and not saving would migrate the same entry on
        every run, which looks identical from inside one run."""
        real = self.a_form(self.root / "forms", FERRITIN_2018)
        folder = self.root / "forms" / ".." / "forms"
        self.seed("labs", folder / "phenotypes.csv")
        ingest_labs.ingest(str(folder))
        on_disk = json.loads(ingest_labs._manifest_file().read_text(encoding="utf-8"))
        self.assertEqual([str(real)], list(on_disk["files"]))

    def test_an_entry_typed_another_way_is_not_lost_either_it_is_simply_not_matched(self):
        """The limit of the migration, written down so nobody reads more into
        it. A folder typed differently from last time re-reads its files — the
        idempotent cost the old key was there to avoid, never a wrong value —
        and the stale entry is left in place rather than deleted, because this
        run walked a path that says nothing about it."""
        self.a_form(self.root / "forms", FERRITIN_2018)
        stale = self.root / "elsewhere" / "phenotypes.csv"
        core.write_ingest_manifest("labs", {str(stale): STAMP})
        r = ingest_labs.ingest(str(self.root / "forms"))
        self.assertEqual(0, r["skipped"])
        self.assertEqual(1, r["files_processed"])
        self.assertIn(str(stale), set(self.manifest()))


class TestTheLookupItself(unittest.TestCase):

    def test_a_file_nobody_has_read_has_a_name_and_no_time(self):
        key, known = core.manifest_lookup({}, pathlib.Path("/x/y/../z/a.pdf"))
        self.assertIsNone(known)
        self.assertEqual(str(pathlib.Path("/x/z/a.pdf")), key)

    def test_the_table_is_left_alone_when_the_name_is_already_right(self):
        p = pathlib.Path("/x/z/a.pdf")
        table = {str(p): 5.0}
        key, known = core.manifest_lookup(table, p)
        self.assertEqual((str(p), 5.0), (key, known))
        self.assertEqual({str(p): 5.0}, table)


if __name__ == "__main__":
    unittest.main()
