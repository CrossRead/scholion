"""A source that could not be read is not a source that is empty.

The data-preparation scripts in `src/ingest/` read the person's own exports — a
watch, a phone, a laboratory PDF — and fold them into the profile. Each of them
had a broad handler that skipped whatever failed to read: a damaged file of the
export, a page of the report, a sleep record with a malformed date. The fold then
went on as if the thing had never existed. A month's mean was taken over fewer
days than it seemed, a page of genotypes was missing from the output, a damaged
labs.json was announced as «no lab results — a normal start».

Each case below damages exactly one input and asserts that the failure is named
in what the script produces or prints. Every one of them passed silently before.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

INGEST = support.ROOT / "src" / "ingest"


def _load(name: str, alias: str):
    spec = importlib.util.spec_from_file_location(alias, INGEST / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel: str, text: str) -> Path:
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p


class TestTheWatchExport(_Tmp):
    """A Garmin export is hundreds of files; one of them truncated took its days
    out of every monthly mean with nothing in the output to say so."""

    def _export(self):
        good = [{"calendarDate": "2024-10-0%d" % d, "restingHeartRate": 55 + d,
                 "totalSteps": 8000} for d in range(1, 4)]
        self.write("DI_CONNECT/DI-Connect-Aggregator/UDSFile_2024-10-01_2024-10-31.json",
                   json.dumps(good))
        # Garmin puts the account e-mail in front of some file names
        self.write("DI_CONNECT/DI-Connect-Aggregator/UDSFile_2024-11-01_2024-11-30.json",
                   '[{"calendarDate": "2024-11-01", "restingHeart')
        self.write("DI_CONNECT/DI-Connect-Wellness/someone@example.org_0_sleepData.json",
                   "{not json")

    def test_a_damaged_file_is_named_in_the_meta(self):
        self._export()
        g = _load("ingest_garmin.py", "_g_unread")
        out = g.build(str(self.tmp))
        bad = out["_meta"].get("unreadable_files")
        self.assertEqual(len(bad or []), 2, out["_meta"])
        self.assertTrue(any("UDSFile_2024-11-01" in b for b in bad), bad)
        # the months that did read are still there
        self.assertIn("2024-10", out["metrics"]["RestingHeartRate"])

    def test_the_account_address_is_not_repeated_in_the_report(self):
        self._export()
        g = _load("ingest_garmin.py", "_g_unread2")
        bad = g.build(str(self.tmp))["_meta"]["unreadable_files"]
        self.assertFalse(any("@" in b for b in bad), bad)
        self.assertTrue(any("sleepData.json" in b for b in bad), bad)

    def test_a_complete_export_says_nothing_is_missing(self):
        self.write("DI_CONNECT/DI-Connect-Aggregator/UDSFile_2024-10-01_2024-10-31.json",
                   json.dumps([{"calendarDate": "2024-10-01", "restingHeartRate": 55}]))
        g = _load("ingest_garmin.py", "_g_unread3")
        self.assertEqual(g.build(str(self.tmp))["_meta"]["unreadable_files"], [])


@unittest.skipUnless((INGEST / "cgm_join.py").exists(),
                     "a loader for one instrument, kept in the source repository only")
class TestTheGlucoseJoin(_Tmp):
    """A night whose HR/HRV file failed to read joined with no HR/HRV, and the
    group means were taken over fewer nights than `n` said."""

    def test_an_unreadable_health_file_is_named_in_the_result(self):
        prof = self.tmp / "profile"
        self.write("profile/cgm_nights.json",
                   json.dumps({"nights": [{"date": "2024-10-01", "min": 3.5,
                                           "min_time": "03:10"}]}))
        self.write("profile/sleep_nightly.json",
                   json.dumps({"nights": [{"date": "2024-10-01", "deep_min": 60}]}))
        self.write("export/DI-Connect-Wellness/a_healthStatusData.json", "[{broken")
        cgm = _load("cgm_join.py", "_cgm_unread")
        res = cgm.join(str(prof), str(self.tmp / "export"))
        self.assertEqual(len(res.get("unreadable_files") or []), 1, res)
        self.assertEqual(res["matched_nights"], 1)


class TestTheFirstRunCheck(_Tmp):
    """The first thing a new owner runs. A damaged labs.json read as {} and was
    announced as «no lab results — that is a normal start»."""

    def _run(self, **patches):
        frc = _load("first_run_check.py", "_frc_unread")
        buf = io.StringIO()
        with mock.patch.object(frc, "PROFILE", self.tmp), redirect_stdout(buf):
            with mock.patch.dict(frc.UNREADABLE, clear=True):
                if patches.get("genome"):
                    from scholion import genome
                    with mock.patch.object(genome, "available",
                                           side_effect=OSError("index unreadable")):
                        frc.main()
                else:
                    frc.main()
        return buf.getvalue()

    def test_a_damaged_lab_file_is_not_called_a_normal_start(self):
        self.write("labs.json", '{"markers": {"hgb": {"series": [')
        out = self._run()
        self.assertIn("labs.json exists but cannot be read", out)
        self.assertNotIn("no lab results", out)

    def test_damaged_prescriptions_are_not_called_empty(self):
        self.write("medications.json", "{oops")
        out = self._run()
        self.assertIn("medications.json exists but cannot be read", out)
        self.assertNotIn("no prescriptions", out)

    def test_a_failed_genome_probe_is_not_called_a_missing_vcf(self):
        out = self._run(genome=True)
        self.assertIn("genome not checked", out)
        self.assertNotIn("no full VCF", out)

    def test_an_absent_file_is_still_a_normal_start(self):
        out = self._run()
        self.assertIn("no lab results", out)
        self.assertNotIn("exists but cannot be read", out)


class TestTheDrawChecklist(_Tmp):
    """With the threshold map unreadable the checklist listed no crossed
    threshold, which reads on paper as «none crossed»."""

    def test_an_unreadable_threshold_map_is_said_on_the_form(self):
        dc = _load("draw_checklist.py", "_dc_unread")
        md, js = self.tmp / "c.md", self.tmp / "c.json"
        with mock.patch.object(dc.core, "clinical_thresholds", return_value={}), \
             mock.patch.object(dc, "ROOT", self.tmp), \
             mock.patch.object(dc, "OUT_MD", md), mock.patch.object(dc, "OUT_JSON", js), \
             redirect_stdout(io.StringIO()) as buf:
            info, items = dc.from_thresholds()
            dc.main()
        self.assertIn("error", info)
        self.assertEqual(items, [])
        self.assertIn("Clinical thresholds were NOT checked", md.read_text(encoding="utf-8"))
        self.assertIn("error", json.loads(js.read_text(encoding="utf-8"))["thresholds"])
        self.assertIn("NOT checked", buf.getvalue())

    def test_a_readable_map_carries_no_error(self):
        dc = _load("draw_checklist.py", "_dc_unread2")
        info, _ = dc.from_thresholds()
        self.assertEqual(info, {})


class TestTheLaboratoryReport(_Tmp):
    """A page whose words could not be extracted was skipped, and its rsIDs were
    missing from the output exactly like rsIDs the report never had."""

    def test_an_unread_page_is_reported(self):
        class Page:
            def __init__(self, fail):
                self.fail = fail

            def extract_words(self, **_):
                if self.fail:
                    raise ValueError("broken content stream")
                return []

        class Pdf:
            pages = [Page(True), Page(False)]

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        fake = types.ModuleType("pdfplumber")
        fake.open = lambda _path: Pdf()
        with mock.patch.dict(sys.modules, {"pdfplumber": fake}), \
             mock.patch.dict(os.environ, {"EVOGEN_PDF": str(self.tmp / "r.pdf")}):
            ev = _load("parse_evogen_pdf.py", "_ev_unread")
            unread = []
            rows = ev.parse(unread)
        self.assertEqual(rows, [])
        self.assertEqual([p for p, _ in unread], [1])


class TestThePhoneExport(_Tmp):
    """A sleep segment with a malformed date was dropped, and its night counted
    short in the yearly mean."""

    def test_a_segment_with_an_unreadable_date_is_counted(self):
        xml = self.write("export.xml", "\n".join([
            '<Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="W" '
            'startDate="2024-10-01 23:00:00 +0300" endDate="2024-10-02 06:00:00 +0300" '
            'value="HKCategoryValueSleepAnalysisAsleepCore"/>',
            '<Record type="HKCategoryTypeIdentifierSleepAnalysis" sourceName="W" '
            'startDate="2024-13-45 23:00:00 +0300" endDate="2024-10-03 06:00:00 +0300" '
            'value="HKCategoryValueSleepAnalysisAsleepCore"/>',
        ]))
        out_json = self.tmp / "out.json"
        r = subprocess.run([sys.executable, str(INGEST / "parse_health_export.py"),
                            str(xml), str(out_json)],
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 sleep segment(s)", r.stdout)
        res = json.loads(out_json.read_text(encoding="utf-8"))
        self.assertEqual(res["SleepSegmentsWithoutADate"], 1)
        self.assertEqual(res["SleepNights"], {"2024": 1})


if __name__ == "__main__":
    unittest.main()
