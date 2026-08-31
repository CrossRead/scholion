"""A discharge summary one of whose sections DOES parse, taken in pieces.

`ingest-studies` gained a branch that splits a multi-study file and keeps every
section it can make a study of. The fixture that arrived with it has five
sections and none of them yields a conclusion, so the branch ran to its «nothing
came of this file» fallback every time and the keeping half — the lines that name
the section, date it, give it an id and merge it with what was there before —
executed in no test at all. The suite's own reach gate is what said so: 97.0 %
→ 86.9 % on that module.

A file where one section reads and three do not is the case the feature exists
for, and it is also the case that proves the accounting: what was kept and what
was named have to add up to what the file held.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import support

if str(support.SRC) not in sys.path:
    sys.path.insert(0, str(support.SRC))

from scholion import core, ingest_studies                       # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "studies"
SUMMARY = (FIXTURES / "05_summary_with_one_readable_section.txt").read_text(encoding="utf-8")


@contextmanager
def folder_of(texts):
    tmp = Path(tempfile.mkdtemp(prefix="studies-pieces-")).resolve()
    (tmp / "profile").mkdir()
    (tmp / "reports").mkdir()
    for name in texts:
        (tmp / "reports" / name).write_bytes(b"%PDF-1.4\n")
    old = {k: os.environ.get(k) for k in
           ("SCHOLION_PROFILE_DIR", "SCHOLION_CACHE_DIR", "SCHOLION_REPO_DIR")}
    os.environ["SCHOLION_PROFILE_DIR"] = str(tmp / "profile")
    os.environ["SCHOLION_CACHE_DIR"] = str(tmp / "cache")
    os.environ["SCHOLION_REPO_DIR"] = str(tmp)
    core.reset_cache()

    def fake_read(path):
        return texts.get(Path(path).name, "")

    with mock.patch.object(ingest_studies, "_read_pdf", side_effect=fake_read), \
            mock.patch.object(ingest_studies, "_ensure_extractor", return_value=True):
        try:
            yield tmp
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            core.reset_cache()
            shutil.rmtree(tmp, ignore_errors=True)


class TestTheSectionsThatReadAreKept(unittest.TestCase):

    def test_the_section_that_reads_becomes_a_study_of_its_own(self):
        with folder_of({"summary.pdf": SUMMARY}):
            r = ingest_studies.ingest(str(Path(os.environ["SCHOLION_REPO_DIR"]) / "reports"))
            self.assertTrue(r["ok"])
            self.assertEqual(1, r["added"], "the readable section was not kept")
            studies = (core.studies() or {}).get("studies") or []
            kept = [s for s in studies if s.get("part_of") == "summary.pdf"]
            self.assertEqual(1, len(kept))
            self.assertIn("щитовид", kept[0]["kind"].lower(),
                          "the section heading is the better name and was not used")
            self.assertEqual("2026-03-14", kept[0]["date"],
                             "the section's own date is the better date and was not used")

    def test_the_sections_that_did_not_read_are_named_not_dropped(self):
        """The accounting the loader now owes: kept + named == what was inside."""
        with folder_of({"summary.pdf": SUMMARY}):
            r = ingest_studies.ingest(str(Path(os.environ["SCHOLION_REPO_DIR"]) / "reports"))
            named = [m for m in r["not_ingested"] if m["file"] == "summary.pdf"]
            self.assertEqual(1, len(named), "a file read in pieces owes a line about its pieces")
            self.assertEqual(ingest_studies.REASON_PART_NOT_READ, named[0]["reason"])
            self.assertEqual(3, len(named[0]["parts"]),
                             "the parts nothing came of are not all listed")

    def test_a_second_run_updates_the_piece_rather_than_duplicating_it(self):
        """The id is per file and section, so the same summary read twice is one
        study, not two — the branch that merges with what was there before."""
        with folder_of({"summary.pdf": SUMMARY}) as tmp:
            ingest_studies.ingest(str(tmp / "reports"))
            (tmp / "reports" / "summary.pdf").write_bytes(b"%PDF-1.4\n\n")   # touch it
            r = ingest_studies.ingest(str(tmp / "reports"))
            self.assertEqual(0, r["added"], "the same section was added twice")
            self.assertEqual(1, r["updated"], "the second read did not merge")
            kept = [s for s in ((core.studies() or {}).get("studies") or [])
                    if s.get("part_of") == "summary.pdf"]
            self.assertEqual(1, len(kept), "one section became two studies")


if __name__ == "__main__":
    unittest.main()


class TestWhatWasDecidedAboutAPieceSurvives(unittest.TestCase):
    """A merge keeps the reader's own annotations on a section.

    A study read out of a summary can be answered, marked open, or annotated by
    hand; a second import must carry those across rather than write over them —
    they are the only part of the record the loader did not produce.
    """

    def test_an_annotation_on_a_section_survives_the_next_import(self):
        import json

        with folder_of({"summary.pdf": SUMMARY}) as tmp:
            ingest_studies.ingest(str(tmp / "reports"))
            path = Path(os.environ["SCHOLION_PROFILE_DIR"]) / "studies.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            target = next(s for s in data["studies"] if s.get("part_of") == "summary.pdf")
            target["answers"] = ["is the thyroid unchanged since last year?"]
            target["open"] = True
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            core.reset_cache()

            (tmp / "reports" / "summary.pdf").write_bytes(b"%PDF-1.4\n\n")
            ingest_studies.ingest(str(tmp / "reports"))

            again = next(s for s in ((core.studies() or {}).get("studies") or [])
                         if s.get("part_of") == "summary.pdf")
            self.assertEqual(["is the thyroid unchanged since last year?"], again.get("answers"),
                             "the reader's own annotation was written over by the import")
            self.assertTrue(again.get("open"), "the open mark did not survive the import")


class TestOneStudyIsNotSplit(unittest.TestCase):

    def test_a_file_with_a_single_section_is_not_a_multi_document_file(self):
        """`split_documents` answers «not one of those» with an empty list, and
        the caller then reads the file whole, as it always did."""
        single = (FIXTURES / "01_ultrasound.txt").read_text(encoding="utf-8")
        self.assertEqual([], ingest_studies.split_documents(single))
