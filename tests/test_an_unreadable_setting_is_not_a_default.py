"""A setting, an export file or a PDF that could not be read is not a default (task 209, round 2).

Four places where a failure still turned into a statement about the person:

  * a corrupt `profile/sources.json` was read as an absent one. Labs kept in a
    chosen folder then answered from `profile/labs.json` («no labs»), the genome
    file the person had named was replaced by whatever else lay in the genome
    folder, and `source_status` reported the defaults as connected;
  * `wearables.reingest` dropped the Garmin builder's list of export files it
    could not read, so the report said nothing about days missing from the means;
  * `ingest_studies` read a PDF whose readers all fell over as "" — «no study in
    this file» — and recorded it in the manifest as read;
  * the draw checklist put PhenoAge's `error` into the JSON and never onto the
    printed form, where an empty section reads as «nothing missing».

Each case reproduces the failure (a broken file or a mock) and asserts that the
answer says it could not read, instead of answering from a default.
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
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
from scholion import core, format as fmt, ingest_labs, ingest_studies, server, wearables


def _tmp(case: unittest.TestCase) -> Path:
    d = Path(tempfile.mkdtemp(prefix="t209r2_")).resolve()
    case.addCleanup(shutil.rmtree, d, True)
    return d


class _Profile(unittest.TestCase):
    """A temporary profile, put back afterwards; the slot variables are cleared so
    that `slot_dir` reaches `sources.json` at all."""

    def setUp(self):
        self.root = _tmp(self)
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.addCleanup(support.pin_profile(self.profile))
        self.addCleanup(support.pin_cache(self.root / "cache"))
        env = mock.patch.dict(os.environ, {"SCHOLION_REPO_DIR": str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        for slot in core.EXTERNAL_SLOTS:
            os.environ.pop(f"SCHOLION_{slot.upper()}_DIR", None)
        core.reset_cache()
        self.addCleanup(core.reset_cache)

    def sources(self, text: str) -> Path:
        p = self.profile / "sources.json"
        p.write_text(text, encoding="utf-8")
        core.reset_cache()
        return p


# ── 1. profile/sources.json ─────────────────────────────────────────────────
class TestAnAbsentSettingsFileIsTheDefault(_Profile):
    """The half that must not change: no file is the ordinary state."""

    def test_absent_means_the_profile(self):
        self.assertEqual({}, core.source_config())
        self.assertIsNone(core.chosen_genome_vcf())
        self.assertIsNone(core.chosen_genome_bam())
        self.assertIsNone(core.chosen_genome_reference())
        self.assertEqual(self.profile / "labs.json", core.source_path("labs"))
        self.assertEqual(self.root / "raw", core.slot_dir("raw"))

    def test_a_readable_file_is_read_as_before(self):
        labs_dir = self.root / "elsewhere"
        labs_dir.mkdir()
        self.sources(json.dumps({"folders": {"labs": str(labs_dir)},
                                 "external_sources": {"cgm": "/x"},
                                 "genome_vcf": "/g/me.vcf.gz"}))
        self.assertEqual({"labs": str(labs_dir), "cgm": "/x"}, core.source_config())
        self.assertEqual(labs_dir / "labs.json", core.source_path("labs"))
        self.assertEqual("/g/me.vcf.gz", core.chosen_genome_vcf())
        self.assertIsNone(core.chosen_genome_bam())


class TestAnUnreadableSettingsFileIsSaid(_Profile):

    def assert_every_reader_refuses(self):
        for name, call in (("source_config", core.source_config),
                           ("chosen_genome_vcf", core.chosen_genome_vcf),
                           ("chosen_genome_bam", core.chosen_genome_bam),
                           ("chosen_genome_reference", core.chosen_genome_reference),
                           ("source_path", lambda: core.source_path("labs")),
                           ("slot_dir", lambda: core.slot_dir("raw")),
                           ("source_status", core.source_status),
                           ("labs", core.labs)):
            with self.subTest(reader=name):
                with self.assertRaises(core.SourcesUnreadable) as e:
                    call()
                self.assertIn("sources.json", str(e.exception))

    def test_a_file_that_does_not_parse(self):
        # labs.json in the profile holds somebody's numbers; with the setting
        # unread, answering from it is answering from the wrong folder.
        (self.profile / "labs.json").write_text('{"markers": {}}', encoding="utf-8")
        self.sources('{"folders": {"labs": "/my/labs"')
        self.assert_every_reader_refuses()

    def test_a_file_that_is_not_an_object(self):
        self.sources('["/my/labs"]')
        self.assert_every_reader_refuses()

    def test_a_section_of_the_wrong_shape(self):
        self.sources('{"folders": ["/my/labs"]}')
        self.assert_every_reader_refuses()

    def test_a_file_that_cannot_be_opened_does_not_leak_its_path(self):
        self.sources("{}")
        err = PermissionError(13, "Permission denied", str(self.profile / "sources.json"))
        with mock.patch.object(core, "_read_json", side_effect=err):
            with self.assertRaises(core.SourcesUnreadable) as e:
                core.source_config()
        self.assertIn("Permission denied", str(e.exception))
        self.assertNotIn(str(self.profile), str(e.exception))

    def test_it_is_a_value_error_with_a_name(self):
        self.assertTrue(issubclass(core.SourcesUnreadable, ValueError))

    def test_writes_stay_loud(self):
        self.sources("{bad")
        folder = self.root / "labs"
        folder.mkdir()
        from scholion import store
        with self.assertRaises(ValueError):
            store.set_source_folder("labs", str(folder))


class TestTheEntryPointsSayIt(_Profile):

    def test_the_command_line_names_it_and_fails(self):
        self.sources("{bad")
        env = dict(os.environ, PYTHONPATH=str(support.SRC), SCHOLION_LANG="en",
                   SCHOLION_OFFLINE="1")
        r = subprocess.run([sys.executable, "-m", "scholion", "labs"], env=env,
                           capture_output=True, text=True, timeout=120,
                           stdin=subprocess.DEVNULL)
        self.assertEqual(5, r.returncode, r.stdout + r.stderr)
        self.assertIn("sources.json", r.stderr)
        self.assertIn("cannot be read", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_the_local_server_answers_with_the_reason(self):
        self.sources("{bad")
        httpd = server._Server(("127.0.0.1", 0), server.Handler)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/source-config?lang=en")
        with redirect_stdout(io.StringIO()):
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req, timeout=30)
        body = json.loads(e.exception.read().decode("utf-8"))
        self.assertEqual(500, e.exception.code)
        self.assertTrue(body.get("sources_unreadable"))
        self.assertIn("sources.json", body["error"])


# ── 2. wearables.reingest: the export files the builder could not read ──────
FRESH = {
    "ok": True,
    "_meta": {"range": "2024-10–2024-11",
              "unreadable_files": ["UDSFile_2024-11-01_2024-11-30.json: JSONDecodeError"]},
    "metrics": {"resting_hr": {"2024-10": 58, "2024-11": 57}},
}


class TestAWatchFileThatDidNotReadIsReported(_Profile):

    def test_the_rebuild_names_it_and_the_report_prints_it(self):
        (self.root / "export" / "DI_CONNECT").mkdir(parents=True)
        builder = SimpleNamespace(build=lambda path: json.loads(json.dumps(FRESH)))
        with mock.patch.object(wearables, "_builder", return_value=builder):
            r = wearables.reingest(str(self.root / "export"), source="garmin")
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(FRESH["_meta"]["unreadable_files"], r.get("unreadable_files"))
        text = fmt.wearable_ingest_report(r)
        self.assertIn("UDSFile_2024-11-01_2024-11-30.json", text)
        self.assertIn("could NOT be read", text)

    def test_a_clean_export_says_nothing_about_it(self):
        (self.root / "export" / "DI_CONNECT").mkdir(parents=True)
        clean = json.loads(json.dumps(FRESH))
        clean["_meta"].pop("unreadable_files")
        builder = SimpleNamespace(build=lambda path: json.loads(json.dumps(clean)))
        with mock.patch.object(wearables, "_builder", return_value=builder):
            r = wearables.reingest(str(self.root / "export"), source="garmin")
        self.assertEqual([], r.get("unreadable_files"))
        self.assertNotIn("could NOT be read", fmt.wearable_ingest_report(r))


# ── 3. ingest_studies: a PDF every reader fell over on ──────────────────────
class TestAStudyThatDidNotReadIsNotNoStudy(_Profile):

    def setUp(self):
        super().setUp()
        self.reports = self.root / "reports"
        self.reports.mkdir()
        (self.reports / "uzi.pdf").write_bytes(b"%PDF-1.4\n")
        p = mock.patch.object(ingest_studies, "_ensure_extractor", return_value=True)
        p.start()
        self.addCleanup(p.stop)

    def test_the_file_is_named_as_unreadable_and_read_again_next_time(self):
        broken = ingest_labs.PdfUnreadable("pdfplumber: ValueError: broken xref table")
        with mock.patch.object(ingest_labs, "_read_pdf_or_raise", side_effect=broken):
            r = ingest_studies.ingest(str(self.reports))
        self.assertTrue(r["ok"], r)
        self.assertEqual(["unreadable"], [m["reason"] for m in r["not_ingested"]])
        self.assertIn("broken xref table", r["not_ingested"][0]["detail"])
        self.assertEqual(1, r["alarming"])
        self.assertIn("uzi.pdf", fmt.ingest_studies_report(r))
        # Not in the manifest: the next run with a working reader reads it.
        with mock.patch.object(ingest_labs, "_read_pdf_or_raise", return_value=""):
            r2 = ingest_studies.ingest(str(self.reports))
        self.assertEqual(0, r2["skipped_unchanged"], r2)
        self.assertEqual(["no_text"], [m["reason"] for m in r2["not_ingested"]])

    def test_an_empty_text_layer_is_still_a_scan_without_text(self):
        with mock.patch.object(ingest_labs, "_read_pdf_or_raise", return_value=""):
            r = ingest_studies.ingest(str(self.reports))
        self.assertEqual(["no_text"], [m["reason"] for m in r["not_ingested"]])


# ── 4. the draw checklist: PhenoAge not checked ─────────────────────────────
def _load_checklist(alias: str):
    spec = importlib.util.spec_from_file_location(
        alias, support.ROOT / "src" / "ingest" / "draw_checklist.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestAnUnreadPhenoAgeIsSaidOnTheForm(unittest.TestCase):

    def setUp(self):
        self.tmp = _tmp(self)

    def run_checklist(self, dc):
        md, js = self.tmp / "c.md", self.tmp / "c.json"
        with mock.patch.object(dc, "OUT_MD", md), mock.patch.object(dc, "OUT_JSON", js), \
                redirect_stdout(io.StringIO()) as buf:
            dc.main()
        return md.read_text(encoding="utf-8"), json.loads(js.read_text(encoding="utf-8")), buf.getvalue()

    def test_a_failed_read_of_the_panels_is_a_section_of_its_own(self):
        dc = _load_checklist("_dc_r2_pheno")
        with mock.patch.object(dc.phenoage, "panels_overview",
                               side_effect=ValueError("labs.json: Expecting value")):
            md, js, out = self.run_checklist(dc)
        self.assertIn("error", js["phenoage"])
        self.assertIn("## Biological age (PhenoAge) was NOT checked", md)
        self.assertIn("Expecting value", md)
        self.assertIn("PhenoAge panel NOT checked", out)

    def test_a_readable_panel_carries_no_such_section(self):
        dc = _load_checklist("_dc_r2_pheno2")
        md, js, _ = self.run_checklist(dc)
        self.assertNotIn("error", js["phenoage"])
        self.assertNotIn("PhenoAge) was NOT checked", md)


if __name__ == "__main__":
    unittest.main()
