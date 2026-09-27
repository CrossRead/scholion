"""A read that failed while loading the profile is not an answer about the person (task 209).

The loaders' half of the broad-`except` review. Each case below swallowed an
error into an ordinary-looking value, and each value had a meaning downstream:

  * a PDF whose readers fell over came back as "" — reported as «a scan without
    OCR», recorded in the manifest as read, and its values never stored;
  * a form whose file could not be stat'ed was dropped without a line;
  * a metrics file bound to another folder, or one that would not parse, gave
    the lab row filter (None, None) — OFF — so a corridor printed for the other
    sex could be stored as this person's;
  * an unreadable corrections file was «no corrections», and the rebuild put
    back every point the person had removed;
  * an unreadable profile file dropped out of «whose data is this», and an
    unreadable SUBJECT.json made a reference genome — a real other person —
    this profile's own;
  * an unreadable pharmacogenomics.json made a demonstration «not synthetic».

The failure is reproduced with a mock or a broken file; the answer must either
raise into a handler that names it, or say that it did not read.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, ingest_labs, subject, wearables

GOOD = """Date,Test,Result,Units,Reference Range
2018-05-22,Ferritin,12,ng/mL,13-150
"""


def _tmp(case: unittest.TestCase) -> Path:
    d = Path(tempfile.mkdtemp(prefix="t209_loaders_")).resolve()
    case.addCleanup(shutil.rmtree, d, True)
    return d


class _Pinned(unittest.TestCase):
    """A temporary profile and cache, put back afterwards."""

    def setUp(self):
        self.root = _tmp(self)
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.addCleanup(support.pin_profile(self.profile))
        self.addCleanup(support.pin_cache(self.root / "cache"))
        core.reset_cache()
        ingest_labs._OWNER_CACHE.clear()
        self.addCleanup(ingest_labs._OWNER_CACHE.clear)
        self.addCleanup(core.reset_cache)


# ── ingest_labs: a PDF the readers fall over on ─────────────────────────────
def _pdfplumber_that_breaks():
    mod = types.ModuleType("pdfplumber")

    def open_(path):
        raise ValueError("broken xref table")
    mod.open = open_
    return mod


class TestAPdfTheReadersFailOnIsAnError(_Pinned):

    def setUp(self):
        super().setUp()
        self.forms = self.root / "forms"
        self.forms.mkdir()
        (self.forms / "bad.pdf").write_bytes(b"%PDF-1.4 not really")
        (self.forms / "good.csv").write_text(GOOD, encoding="utf-8")
        # pdfplumber present and failing; no pdftotext; no pdfminer.
        for p in (mock.patch.dict(sys.modules, {"pdfplumber": _pdfplumber_that_breaks(),
                                                "pdfminer": None,
                                                "pdfminer.high_level": None}),
                  mock.patch.object(ingest_labs.shutil, "which", return_value=None),
                  mock.patch.object(ingest_labs, "_ensure_extractor", return_value="pdfplumber")):
            p.start()
            self.addCleanup(p.stop)

    def test_it_is_named_as_an_error_not_as_a_scan(self):
        r = ingest_labs.ingest(str(self.forms), force=True)
        bad = [n for n in r["not_ingested"] if n["file"] == "bad.pdf"]
        self.assertEqual([n["reason"] for n in bad], ["error"],
                         "a reader that fell over was reported as a page with no text")
        self.assertIn("PdfUnreadable", bad[0]["detail"])
        self.assertIn("broken xref table", bad[0]["detail"])
        self.assertIn("bad.pdf", r["errors"])
        self.assertEqual(r["points_added"], 1, "the good form after it must still be read")

    def test_it_is_tried_again_next_run(self):
        ingest_labs.ingest(str(self.forms), force=True)
        remembered = set(ingest_labs._load_manifest())
        self.assertNotIn(str(self.forms / "bad.pdf"), remembered,
                         "a PDF that was not read was recorded as read")

    def test_the_next_reader_is_asked_when_one_fails(self):
        done = subprocess.CompletedProcess(["pdftotext"], 0, stdout="Ферритин 12", stderr="")
        with mock.patch.object(ingest_labs.shutil, "which", return_value="/usr/bin/pdftotext"), \
                mock.patch.object(ingest_labs.subprocess, "run", return_value=done):
            self.assertEqual(ingest_labs._read_pdf_or_raise(self.forms / "bad.pdf"), "Ферритин 12")

    def test_a_failing_pdftotext_is_a_failure_not_an_empty_page(self):
        failed = subprocess.CompletedProcess(["pdftotext"], 1, stdout="", stderr="Syntax Error")
        with mock.patch.object(ingest_labs.shutil, "which", return_value="/usr/bin/pdftotext"), \
                mock.patch.object(ingest_labs.subprocess, "run", return_value=failed):
            with self.assertRaises(ingest_labs.PdfUnreadable) as cm:
                ingest_labs._read_pdf_or_raise(self.forms / "bad.pdf")
        self.assertIn("pdftotext: exit 1", str(cm.exception))


class TestAFormThatCannotBeStatedIsNamed(_Pinned):

    def test_it_reaches_not_ingested(self):
        forms = self.root / "forms"
        forms.mkdir()
        (forms / "bad.csv").write_text(GOOD, encoding="utf-8")
        (forms / "good.csv").write_text(GOOD, encoding="utf-8")
        armed = {"on": False}
        real_stat = Path.stat

        def stat(self_, *a, **kw):
            if armed["on"] and self_.name == "bad.csv":
                raise PermissionError("denied on purpose")
            return real_stat(self_, *a, **kw)

        def progress(_n, _total, name):
            # Armed only once the walk has begun: the listing itself must see
            # the file, as it does when a file vanishes between the two.
            armed["on"] = name == "bad.csv"

        with mock.patch.object(Path, "stat", stat):
            r = ingest_labs.ingest(str(forms), force=True, progress=progress)
        bad = [n for n in r["not_ingested"] if n["file"] == "bad.csv"]
        self.assertEqual([n["reason"] for n in bad], ["error"],
                         "a listed form was dropped without a line")
        self.assertIn("PermissionError", bad[0]["detail"])
        self.assertIn("bad.csv", r["errors"])


# ── ingest_labs: whose sex and age filter the reference rows ────────────────
class TestTheRowFilterReadsTheMetricsFileWhereItIs(_Pinned):

    def test_a_metrics_file_in_a_chosen_folder_is_read(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / "metrics.json").write_text(
            json.dumps({"profile": {"sex": "male", "birth_year": 1980}}), encoding="utf-8")
        (self.profile / "sources.json").write_text(
            json.dumps({"folders": {"metrics": str(elsewhere)}}), encoding="utf-8")
        core.reset_cache()
        sex, age = ingest_labs._owner()
        self.assertEqual(sex, "male", "the filter read profile/metrics.json and found nobody")
        self.assertIsNotNone(age)

    def test_a_metrics_file_that_will_not_parse_is_not_nobody(self):
        (self.profile / "metrics.json").write_text('{"profile": {"sex": "male",', encoding="utf-8")
        with self.assertRaises(ValueError):
            ingest_labs._owner()

    def test_no_metrics_file_is_still_the_documented_unknown(self):
        self.assertEqual(ingest_labs._owner(), (None, None))


# ── wearables: the person's corrections ─────────────────────────────────────
class TestUnreadableCorrectionsStopTheRebuild(unittest.TestCase):

    def test_nothing_is_rebuilt_over_them(self):
        from test_a_correction_survives_the_rebuild import profile_and_export, rebuild, series_of
        with profile_and_export() as tmp:
            (tmp / "profile" / wearables.CORRECTIONS).write_text(
                json.dumps({"corrections": [
                    {"device": "garmin", "metric": "weight_kg", "month": "2024-10",
                     "action": "remove", "why": "impossible"}]}), encoding="utf-8")
            first = rebuild(tmp)
            self.assertTrue(first["ok"], first.get("error"))
            self.assertNotIn("2024-10", series_of(tmp))
            # Now the file breaks. The rebuild must not bring the point back.
            (tmp / "profile" / wearables.CORRECTIONS).write_text(
                '{"corrections": [', encoding="utf-8")
            r = rebuild(tmp)
            self.assertFalse(r["ok"], "a rebuild ran without the person's corrections")
            self.assertIn(wearables.CORRECTIONS, r["error"])
            self.assertNotIn("2024-10", series_of(tmp),
                             "the removed point came back while its correction could not be read")


# ── subject: whose data, and whose genome ───────────────────────────────────
def _reference_genome(case: unittest.TestCase, sidecar: str) -> Path:
    g = _tmp(case)
    (g / "SUBJECT.json").write_text(sidecar, encoding="utf-8")
    (g / "HG005.vcf.gz").write_bytes(b"")
    return g / "HG005.vcf.gz"


class TestAnUnreadableFileIsStillSomebodys(unittest.TestCase):

    def test_a_profile_of_unreadable_files_does_not_take_a_reference_genome(self):
        pdir = _tmp(self)
        (pdir / "labs.json").write_text('{"markers": {', encoding="utf-8")
        vcf = _reference_genome(self, json.dumps({"subject": "reference", "who": "HG005"}))
        self.assertEqual(subject.profile_subjects(pdir), {"unattributed": ["labs.json"]})
        conflict = subject.genome_conflict(vcf, pdir)
        self.assertIsNotNone(conflict, "another person's genome was read as this profile's")
        self.assertEqual(conflict["reason"], "another_person")

    def test_an_empty_profile_still_takes_the_genome_it_is_given(self):
        pdir = _tmp(self)
        vcf = _reference_genome(self, json.dumps({"subject": "reference"}))
        self.assertIsNone(subject.genome_conflict(vcf, pdir))


class TestAnUnreadableSidecarIsNotSilence(unittest.TestCase):

    def _owner_profile(self) -> Path:
        pdir = _tmp(self)
        (pdir / "metrics.json").write_text(json.dumps({"profile": {}}), encoding="utf-8")
        return pdir

    def test_the_genome_is_refused_and_the_file_is_named(self):
        vcf = _reference_genome(self, '{"subject": "refer')
        self.assertTrue(subject.genome_note(vcf.parent).get(subject.UNREADABLE_NOTE))
        conflict = subject.genome_conflict(vcf, self._owner_profile())
        self.assertIsNotNone(conflict, "an unreadable SUBJECT.json was read as «this profile's»")
        self.assertEqual(conflict["reason"], "subject_unreadable")
        self.assertIn("SUBJECT.json", conflict["message"])
        self.assertIn("SUBJECT.json", conflict["fix"])

    def test_a_folder_with_no_sidecar_is_still_this_profiles(self):
        g = _tmp(self)
        (g / "mine.vcf.gz").write_bytes(b"")
        self.assertEqual(subject.genome_note(g), {})
        self.assertIsNone(subject.genome_conflict(g / "mine.vcf.gz", self._owner_profile()))


# ── core: the demonstration badge ───────────────────────────────────────────
class TestADemonstrationStaysADemonstration(unittest.TestCase):

    def _profile(self, *extra) -> Path:
        d = _tmp(self)
        code, out, err = support.run(["init", *extra, "--dir", str(d / "profile")])
        self.assertEqual(code, 0, err or out)
        return d / "profile"

    def _synthetic_with_broken_pgx(self, pdir: Path) -> bool:
        (pdir / "pharmacogenomics.json").write_text('{"_meta": {', encoding="utf-8")
        restore = support.pin_profile(pdir)
        try:
            core.reset_cache()
            return core.profile_is_synthetic()
        finally:
            restore()
            core.reset_cache()

    def test_a_demo_whose_pgx_file_breaks_still_says_it_is_one(self):
        self.assertTrue(self._synthetic_with_broken_pgx(self._profile("--demo")),
                        "a demonstration was presented as the reader's own data")

    def test_a_real_profile_whose_pgx_file_breaks_is_not_called_a_demo(self):
        self.assertFalse(self._synthetic_with_broken_pgx(self._profile()))


if __name__ == "__main__":
    unittest.main()
