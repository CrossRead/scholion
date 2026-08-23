"""Conclusions reach the profile, and a judgement about them is never overwritten.

The defect this loader exists for was not theoretical. `ingest_labs` takes
NUMBERS out of a PDF by the marker dictionary, and the conclusion of an
ultrasound, an ECG or a consultation holds no numbers from that dictionary at
all — so those files passed the profile by entirely. The assistant then called a
study that had in fact been done «not done», and wrote that into the questions
for the doctor.

At 26.7% reach, what was tested here was two functions on two strings.
`ingest()` — the walk, the manifest, the identity of a record and the rule that
protects the assistant's own judgements — had nothing.

That last rule is the one worth stating. `answers` and `does_not_answer` say
which questions a study answers and which it does not; they are a judgement, not
an extraction, and a PDF cannot restore them. Re-running the ingest over the same
folder must therefore refresh what was read from the file and leave everything
that was reasoned about it alone. There is no way to notice that being wrong by
looking at the output — the fields simply become empty again.

The fixtures are invented forms in `tests/fixtures/studies/`, in Russian because
that is the language the recogniser reads. Nothing here opens a PDF: `_read_pdf`
is replaced by a table from file name to text, which is exactly the seam between
«can this project read a PDF» (tested elsewhere) and «does it understand what it
read» (tested here).
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
from scholion import core, ingest_studies

FIXTURES = support.ROOT / "tests" / "fixtures" / "studies"
ULTRASOUND = (FIXTURES / "01_ultrasound.txt").read_text(encoding="utf-8")
CONSULTATION = (FIXTURES / "02_consultation.txt").read_text(encoding="utf-8")
LAB_FORM = (FIXTURES / "03_lab_form_not_a_study.txt").read_text(encoding="utf-8")


@contextmanager
def folder_of(texts):
    """A profile, a cache and a folder holding one empty PDF per text.

    The files are empty on purpose: what a PDF contains is `_read_pdf`'s business
    and it is stubbed here. What the loader does with a folder — the order, the
    manifest, the mtimes — is real.
    """
    tmp = Path(tempfile.mkdtemp(prefix="studies-")).resolve()
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


def studies_in(tmp):
    p = tmp / "profile" / "studies.json"
    return json.loads(p.read_text(encoding="utf-8"))["studies"] if p.exists() else []


class TestTellingAConclusionFromAForm(unittest.TestCase):

    def test_an_ultrasound_protocol_is_a_conclusion(self):
        self.assertTrue(ingest_studies.looks_like_conclusion(ULTRASOUND))

    def test_a_consultation_is_a_conclusion(self):
        self.assertTrue(ingest_studies.looks_like_conclusion(CONSULTATION))

    def test_a_laboratory_form_is_not_one_even_though_it_says_the_word(self):
        """The order of the checks is the whole content of this function: a form
        can carry «ЗАКЛЮЧЕНИЕ» in its own footer, and the laboratory signs have
        to outweigh it or every lab result becomes a study."""
        self.assertTrue("ЗАКЛЮЧЕНИЕ" in LAB_FORM)
        self.assertFalse(ingest_studies.looks_like_conclusion(LAB_FORM))

    def test_a_page_too_short_to_be_anything_is_not_a_conclusion(self):
        self.assertFalse(ingest_studies.looks_like_conclusion("ЗАКЛЮЧЕНИЕ: норма"))

    def test_nothing_at_all_is_not_a_conclusion(self):
        self.assertFalse(ingest_studies.looks_like_conclusion(""))
        self.assertFalse(ingest_studies.looks_like_conclusion(None))


class TestWhatIsTakenOutOfAConclusion(unittest.TestCase):

    def test_the_date_of_the_study_is_taken_and_not_the_date_of_birth(self):
        """The birth date stands higher on the page and used to match first,
        which dated every study to the year somebody was born."""
        got = ingest_studies.parse_study(ULTRASOUND, source="u.pdf")
        self.assertEqual("2026-03-14", got["date"])

    def test_the_organ_reaches_the_kind_so_two_scans_can_be_told_apart(self):
        """In an ultrasound protocol the organ stands on the row after the
        heading. Without it every ultrasound looks identical in the profile."""
        got = ingest_studies.parse_study(ULTRASOUND, source="u.pdf")
        self.assertTrue(got["kind"].startswith("УЗИ"), got["kind"])
        self.assertIn("Щитовидной", got["kind"])

    def test_the_conclusion_stops_before_the_boilerplate(self):
        got = ingest_studies.parse_study(ULTRASOUND, source="u.pdf")
        self.assertIn("очаговой патологии", got["conclusion"])
        self.assertNotIn("не является диагнозом", got["conclusion"],
                         "the disclaimer was stored as part of the finding")

    def test_the_recommendations_come_out_as_separate_items(self):
        got = ingest_studies.parse_study(CONSULTATION, source="c.pdf")
        self.assertGreaterEqual(len(got["recommendations"]), 2)
        self.assertTrue(any("Холтер" in r for r in got["recommendations"]))

    def test_each_recommendation_becomes_an_open_question(self):
        got = ingest_studies.parse_study(CONSULTATION, source="c.pdf")
        self.assertEqual(len(got["recommendations"]), len(got["open"]))
        self.assertTrue(all(o.get("note") for o in got["open"]))

    def test_the_doctor_is_named(self):
        got = ingest_studies.parse_study(CONSULTATION, source="c.pdf")
        self.assertEqual("Иванова Мария Сергеевна", got["doctor"])

    def test_judgement_fields_start_empty_because_nothing_may_invent_them(self):
        got = ingest_studies.parse_study(ULTRASOUND, source="u.pdf")
        self.assertEqual([], got["answers"])
        self.assertEqual([], got["does_not_answer"])

    def test_a_form_is_not_parsed_into_a_study_at_all(self):
        self.assertIsNone(ingest_studies.parse_study(LAB_FORM, source="l.pdf"))


class TestTheIdentityOfARecord(unittest.TestCase):

    def test_two_russian_names_do_not_collapse_into_one_id(self):
        """They did. The stem was stripped of everything but ASCII, Russian file
        names became the empty string, and different studies overwrote each
        other."""
        a = ingest_studies._sid(Path("Щитовидная железа.pdf"), "2026-03-14")
        b = ingest_studies._sid(Path("Брюшная полость.pdf"), "2026-03-14")
        self.assertNotEqual(a, b)

    def test_a_name_with_nothing_usable_in_it_still_gets_an_id(self):
        got = ingest_studies._sid(Path("--.pdf"), "2026-03-14")
        self.assertTrue(got.startswith("study_"))

    def test_a_very_long_name_is_shortened_without_colliding(self):
        long_a = Path(("щитовидная" * 6) + "A.pdf")
        long_b = Path(("щитовидная" * 6) + "B.pdf")
        self.assertNotEqual(ingest_studies._sid(long_a, "2026-03-14"),
                            ingest_studies._sid(long_b, "2026-03-14"))

    def test_a_study_with_no_date_still_has_an_id(self):
        self.assertTrue(ingest_studies._sid(Path("ecg.pdf"), None).endswith("nodate"))


class TestWalkingTheFolder(unittest.TestCase):

    TEXTS = {"u.pdf": ULTRASOUND, "c.pdf": CONSULTATION, "l.pdf": LAB_FORM}

    def test_the_conclusions_land_in_the_profile_and_the_form_does_not(self):
        with folder_of(self.TEXTS) as tmp:
            res = ingest_studies.ingest(str(tmp / "reports"))
        self.assertTrue(res["ok"])
        self.assertEqual(3, res["files_seen"])
        self.assertEqual(2, res["added"], "the laboratory form was filed as a study")
        self.assertEqual(2, res["total"])

    def test_the_records_are_ordered_by_date(self):
        with folder_of(self.TEXTS) as tmp:
            ingest_studies.ingest(str(tmp / "reports"))
            dates = [s["date"] for s in studies_in(tmp)]
        self.assertEqual(sorted(dates), dates)

    def test_a_second_run_over_an_unchanged_folder_does_nothing(self):
        with folder_of(self.TEXTS) as tmp:
            ingest_studies.ingest(str(tmp / "reports"))
            again = ingest_studies.ingest(str(tmp / "reports"))
        self.assertEqual(3, again["skipped_unchanged"])
        self.assertEqual(0, again["added"])
        self.assertEqual(2, again["total"], "the same file was filed twice")

    def test_force_reads_everything_again_without_duplicating_anything(self):
        with folder_of(self.TEXTS) as tmp:
            ingest_studies.ingest(str(tmp / "reports"))
            again = ingest_studies.ingest(str(tmp / "reports"), force=True)
        self.assertEqual(0, again["skipped_unchanged"])
        self.assertEqual(2, again["updated"])
        self.assertEqual(2, again["total"])

    def test_a_judgement_survives_the_file_being_read_again(self):
        """The rule that cannot be checked by looking at the output: these fields
        are the assistant's reasoning about a study, a PDF cannot restore them,
        and losing them silently turns an answered question back into an open
        one."""
        with folder_of(self.TEXTS) as tmp:
            ingest_studies.ingest(str(tmp / "reports"))
            p = tmp / "profile" / "studies.json"
            data = json.loads(p.read_text(encoding="utf-8"))
            for s in data["studies"]:
                s["answers"] = ["whether the thyroid holds a nodule"]
                s["does_not_answer"] = ["whether it is functioning"]
                s["note"] = "read against the 2025 scan"
            p.write_text(json.dumps(data), encoding="utf-8")

            ingest_studies.ingest(str(tmp / "reports"), force=True)
            after = studies_in(tmp)
        for s in after:
            self.assertEqual(["whether the thyroid holds a nodule"], s["answers"])
            self.assertEqual(["whether it is functioning"], s["does_not_answer"])
            self.assertEqual("read against the 2025 scan", s["note"])

    def test_a_folder_that_is_not_there_is_refused_by_name(self):
        with folder_of({}) as tmp:
            res = ingest_studies.ingest(str(tmp / "no-such-folder"))
        self.assertFalse(res["ok"])
        self.assertIn("no-such-folder", res["error"])

    def test_a_file_that_is_not_a_folder_is_refused_too(self):
        with folder_of({"u.pdf": ULTRASOUND}) as tmp:
            res = ingest_studies.ingest(str(tmp / "reports" / "u.pdf"))
        self.assertFalse(res["ok"])

    def test_without_a_pdf_reader_it_says_so_instead_of_reporting_nothing_found(self):
        with folder_of({"u.pdf": ULTRASOUND}) as tmp:
            with mock.patch.object(ingest_studies, "_ensure_extractor", return_value=False):
                res = ingest_studies.ingest(str(tmp / "reports"))
        self.assertFalse(res["ok"])
        self.assertTrue(res["error"])

    def test_an_empty_folder_is_a_successful_run_that_found_nothing(self):
        with folder_of({}) as tmp:
            res = ingest_studies.ingest(str(tmp / "reports"))
        self.assertTrue(res["ok"])
        self.assertEqual(0, res["files_seen"])
        self.assertEqual("", res["hint"], "a hint about new studies with no new studies")


class TestTheManifest(unittest.TestCase):

    def test_a_manifest_that_will_not_parse_is_treated_as_empty(self):
        with folder_of({"u.pdf": ULTRASOUND}):
            ingest_studies._manifest_file().write_text("{ broken", encoding="utf-8")
            self.assertEqual({}, ingest_studies._load_manifest())

    def test_what_was_read_is_remembered_by_path_and_mtime(self):
        with folder_of({"u.pdf": ULTRASOUND}) as tmp:
            ingest_studies.ingest(str(tmp / "reports"))
            manifest = ingest_studies._load_manifest()
        self.assertEqual(1, len(manifest))
        self.assertTrue(next(iter(manifest)).endswith("u.pdf"))


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
