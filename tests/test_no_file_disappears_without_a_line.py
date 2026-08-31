"""No file goes through this loader without leaving a line about itself.

The counts were the whole report, and `files_seen` was never reconciled against
them: a file that was read and then dropped touched no counter at all. That is
how a ten-page discharge summary — eight studies and a laboratory panel in one
PDF — went through the loader and left no trace anywhere, in either report. It
sat in the archive for six years.

What is asserted here is not «the summary is parsed» — it is not, and splitting
it is the open half of the task. What is asserted is that it can no longer
disappear: every file seen is either taken, unchanged since the last run, or
named with a reason, and the three numbers plus the named ones add up to the
files that were looked at. A loader is allowed not to understand a document. It
is not allowed to be silent about one.

Two failures of the older code are pinned here as regressions, because both were
invisible rather than loud:

  · the recogniser accepts «Заключение врача» case-insensitively while the text
    extractor demanded the word in CAPITALS, so any document writing it in mixed
    case was accepted as a study and then produced an empty conclusion — and an
    empty conclusion was the drop condition;

  · a file carrying both a laboratory panel and several studies was declared a
    laboratory form and handed to the other loader, which dropped it for a reason
    of its own. Neither report held a line about it. It is now named here, before
    the handoff, with the count of what is inside it.

The samples live in `tests/fixtures/studies/` rather than in this file: they are
in Russian because that is the language the recogniser reads, and a fixture on
disk keeps the sample out of the source tree's language check.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, format as fmt, ingest_studies

FIXTURES = support.ROOT / "tests" / "fixtures" / "studies"
ULTRASOUND = (FIXTURES / "01_ultrasound.txt").read_text(encoding="utf-8")
LAB_FORM = (FIXTURES / "03_lab_form_not_a_study.txt").read_text(encoding="utf-8")
SUMMARY = (FIXTURES / "04_discharge_summary_many_studies.txt").read_text(encoding="utf-8")

#: A conclusion written the way a clinic writes it: the word in mixed case, the
#: text on the SAME line after a colon. Both are why the old extractor found
#: nothing here.
MIXED_CASE = ULTRASOUND.replace("ЗАКЛЮЧЕНИЕ", "Заключение:")


@contextmanager
def folder_of(texts):
    """A profile, a cache and a folder holding one empty PDF per text."""
    tmp = Path(tempfile.mkdtemp(prefix="studies-lines-")).resolve()
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


class TestEveryFileIsAccountedFor(unittest.TestCase):

    def test_the_numbers_add_up_to_the_files_that_were_looked_at(self):
        """The invariant the old report could not state: taken + unchanged +
        named == seen. Without it a file can be read and dropped and no counter
        moves, which is exactly what happened."""
        texts = {"a.pdf": ULTRASOUND, "b.pdf": LAB_FORM,
                 "c.pdf": SUMMARY, "d.pdf": "", "e.pdf": MIXED_CASE}
        with folder_of(texts) as tmp:
            r = ingest_studies.ingest(str(tmp / "reports"))
            self.assertTrue(r["ok"])
            accounted = (r["added"] + r["updated"] + r["skipped_unchanged"]
                         + len(r["not_ingested"]))
            self.assertEqual(accounted, r["files_seen"],
                             f"{r['files_seen']} files seen, {accounted} accounted for — "
                             "one of them went through without a line")

    def test_a_second_run_accounts_for_the_same_files_as_unchanged(self):
        """The manifest path has to keep the invariant too: on the second run the
        same files are «unchanged», not «gone»."""
        texts = {"a.pdf": ULTRASOUND, "c.pdf": SUMMARY}
        with folder_of(texts) as tmp:
            ingest_studies.ingest(str(tmp / "reports"))
            r = ingest_studies.ingest(str(tmp / "reports"))
            accounted = (r["added"] + r["updated"] + r["skipped_unchanged"]
                         + len(r["not_ingested"]))
            self.assertEqual(accounted, r["files_seen"])
            self.assertEqual(r["skipped_unchanged"], 2)


class TestEveryReasonCanActuallyFire(unittest.TestCase):
    """A verdict nothing ever reaches is not a verdict. Each reason is produced by
    a real document, so none of them is dead text in the report."""

    def test_no_text_at_all(self):
        self.assertEqual(ingest_studies.decline_reason("", None),
                         ingest_studies.REASON_NO_TEXT)

    def test_a_laboratory_form_is_named_as_the_other_loader_s(self):
        st = ingest_studies.parse_study(LAB_FORM, source="x.pdf")
        self.assertEqual(ingest_studies.decline_reason(LAB_FORM, st),
                         ingest_studies.REASON_LAB_FORM)

    def test_several_documents_in_one_file(self):
        st = ingest_studies.parse_study(SUMMARY, source="x.pdf")
        self.assertEqual(ingest_studies.decline_reason(SUMMARY, st),
                         ingest_studies.REASON_SEVERAL)

    def test_a_page_that_is_neither(self):
        text = "Справка выдана по месту требования. " * 12
        self.assertEqual(ingest_studies.decline_reason(text, None),
                         ingest_studies.REASON_UNCLASSIFIED)

    def test_a_study_that_parsed_declines_nothing(self):
        st = ingest_studies.parse_study(ULTRASOUND, source="x.pdf")
        self.assertIsNone(ingest_studies.decline_reason(ULTRASOUND, st))


class TestTheTwoRegressions(unittest.TestCase):

    def test_a_conclusion_written_in_mixed_case_is_still_a_conclusion(self):
        """The recogniser reads the word case-insensitively; the extractor used to
        demand capitals. A document that writes «Заключение:» was accepted and then
        produced an empty body — and an empty body was the drop condition."""
        self.assertTrue(ingest_studies.looks_like_conclusion(MIXED_CASE))
        st = ingest_studies.parse_study(MIXED_CASE, source="x.pdf")
        self.assertTrue(st and st.get("conclusion"),
                        "the conclusion was not lifted out of a mixed-case heading")
        self.assertIsNone(ingest_studies.decline_reason(MIXED_CASE, st))

    def test_the_printed_disclaimer_is_not_mistaken_for_the_finding(self):
        """Case-insensitive and unanchored, the extractor would match the small
        print «Данное заключение не является диагнозом» and lift THAT out."""
        text = "Данное заключение не является диагнозом.\n" + ULTRASOUND
        st = ingest_studies.parse_study(text, source="x.pdf")
        self.assertTrue(st and st.get("conclusion"))
        self.assertNotIn("не является диагнозом", st["conclusion"])

    def test_a_mixed_file_is_not_handed_off_as_somebody_else_s(self):
        """The summary carries a laboratory panel, so the laboratory sign matches.
        Handing it on would be the original defect: the other loader drops it for a
        reason of its own and neither report says anything."""
        self.assertTrue(ingest_studies._LAB.search(SUMMARY),
                        "the fixture no longer carries a laboratory sign — the "
                        "handoff this test is about cannot happen, so it proves nothing")
        st = ingest_studies.parse_study(SUMMARY, source="x.pdf")
        self.assertEqual(ingest_studies.decline_reason(SUMMARY, st),
                         ingest_studies.REASON_SEVERAL)


class TestWhatIsInsideIsNamed(unittest.TestCase):

    def test_the_sections_are_listed_with_their_own_dates(self):
        found = ingest_studies.sections_in(SUMMARY)
        self.assertGreaterEqual(len(found), 5)
        self.assertEqual(sorted({s["date"] for s in found}),
                         ["2020-11-25", "2020-11-26"])

    def test_a_single_study_has_no_sections(self):
        """The detector must not fire on an ordinary form, or every file becomes
        «several documents» and the reason means nothing."""
        for sample in (ULTRASOUND, LAB_FORM):
            self.assertEqual(ingest_studies.sections_in(sample), [])

    def test_the_report_names_the_file_and_what_was_in_it(self):
        texts = {"epicrisis.pdf": SUMMARY}
        with folder_of(texts) as tmp:
            r = ingest_studies.ingest(str(tmp / "reports"))
            out = fmt.ingest_studies_report(r)
        self.assertIn("epicrisis.pdf", out)
        self.assertIn("2020-11-25", out)
        self.assertEqual(r["alarming"], 1)


class TestTheProfileStillGetsTheStudies(unittest.TestCase):

    def test_a_readable_study_is_written_as_before(self):
        """The new bookkeeping must not cost the loader its job."""
        with folder_of({"a.pdf": ULTRASOUND}) as tmp:
            r = ingest_studies.ingest(str(tmp / "reports"))
            self.assertEqual(r["added"], 1)
            saved = json.loads((tmp / "profile" / "studies.json").read_text(encoding="utf-8"))
            self.assertEqual(len(saved["studies"]), 1)
            self.assertTrue(saved["studies"][0]["conclusion"])


if __name__ == "__main__":
    unittest.main()
