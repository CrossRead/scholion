"""A discharge summary is a set of dated sections, never one inferred draw."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, format as fmt, ingest_labs, ingest_studies, provenance, reconcile

SUMMARY = ("Synthetic discharge summary\n" + "Narrative without measurements. " * 9 + "\n"
           "Общий анализ крови 25.11.2020\n"
           "Глюкоза 5,1 ммоль/л 4,1 - 5,9\n"
           "Биохимический анализ крови 02.12.2020\n"
           "Глюкоза 6,2 ммоль/л 4,1 - 5,9\n"
           "Ферритин 20 нг/мл 10 - 100\n")


class LaboratorySections(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="synthetic-lab-sections-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.profile = self.root / "profile"
        self.forms = self.root / "forms"
        self.profile.mkdir(); self.forms.mkdir()
        self.file = self.forms / "synthetic-summary.pdf"
        self.file.write_bytes(b"%PDF-1.4 synthetic extraction fixture")
        self.addCleanup(support.pin_profile(self.profile))
        self.addCleanup(support.pin_cache(self.root / "cache"))
        core.reset_cache()
        self.addCleanup(core.reset_cache)
        patch = mock.patch.object(ingest_labs, "_ensure_extractor", return_value="synthetic")
        patch.start(); self.addCleanup(patch.stop)
        self.text = SUMMARY
        for name in ("_read_any", "_read_pdf"):
            patch = mock.patch.object(ingest_labs, name, side_effect=lambda *_: self.text)
            patch.start(); self.addCleanup(patch.stop)

    def ingest(self, **kwargs):
        return ingest_labs.ingest(str(self.forms), **kwargs)

    def series(self, key):
        return core.labs()["markers"][key]["series"]

    def test_each_section_has_its_own_date_and_source_witness(self):
        result = self.ingest()
        self.assertFalse(result.get("errors"), result)
        self.assertEqual(1, result["files_processed"])
        self.assertEqual(3, result["points_added"])
        self.assertEqual([("2020-11-25", 5.1), ("2020-12-02", 6.2)],
                         [(p["date"], p["value"]) for p in self.series("glucose")])
        self.assertTrue(all(p["ingest_method"]["section"]["date"] == p["date"]
                            for p in self.series("glucose")))
        self.assertTrue(all(p["ingest_method"]["path"] == str(self.file) for p in self.series("glucose")))

    def test_reconcile_finds_both_missing_draws_before_import(self):
        result = reconcile.reconcile(str(self.forms))
        glucose = [p for p in result["missing"] if p["marker"] == "glucose"]
        self.assertEqual({"2020-11-25", "2020-12-02"}, {p["draw_date"] for p in glucose})
        self.assertEqual(0, result["files_non_lab"])

    def test_import_reconcile_and_reverse_provenance_agree(self):
        self.ingest()
        result = reconcile.reconcile(str(self.forms))
        self.assertEqual([], result["missing"])
        self.assertEqual([], result["mismatch"])
        self.assertEqual(3, result["covered_points"])
        report = provenance.audit(lab_dir=str(self.forms))
        self.assertTrue(report["ok"], report)
        self.assertTrue(all(p["verdict"] == "form" for p in report["points"]), report)

    def test_repeat_and_forced_repeat_do_not_duplicate_draws(self):
        self.ingest()
        self.assertEqual(1, self.ingest()["skipped"])
        self.ingest(force=True)
        self.assertEqual(2, len(self.series("glucose")))

    def test_two_clock_times_on_one_day_remain_distinct(self):
        self.text = ("Общий анализ крови 25.11.2020 08:00\nГлюкоза 5,1 ммоль/л\n"
                     "Биохимический анализ крови 25.11.2020 14:00\nГлюкоза 6,2 ммоль/л\n")
        self.ingest()
        self.assertEqual(["2020-11-25T08:00", "2020-11-25T14:00"],
                         [p["date"] for p in self.series("glucose")])

    def test_single_lab_section_heading_is_also_usable(self):
        self.text = "Общий анализ крови 25.11.2020\nГлюкоза 5,1 ммоль/л\n"
        self.ingest()
        self.assertEqual("2020-11-25", self.series("glucose")[0]["date"])

    def test_invalid_section_date_is_not_repaired_from_another_section(self):
        self.text = SUMMARY.replace("02.12.2020", "31.02.2020")
        result = self.ingest()
        self.assertIn("invalid_section_date", [p["reason"] for p in result["not_ingested"]])
        self.assertEqual(["2020-11-25"], [p["date"] for p in self.series("glucose")])
        self.assertNotIn(str(self.file), ingest_labs._load_manifest())

    def test_invalid_section_is_visible_in_completeness_checks(self):
        self.text = SUMMARY.replace("02.12.2020", "31.02.2020")
        result = reconcile.reconcile(str(self.forms))
        self.assertEqual(1, len(result["unparsed_sections"]))
        self.assertIn("2020-02-31", fmt.reconcile_report(result))
        self.assertIn("not assessed", reconcile.selfcheck_summary(result))

    def test_an_unreadable_changed_file_preserves_previous_bytes(self):
        self.ingest()
        target = self.profile / "labs.json"
        before = target.read_bytes()
        with mock.patch.object(ingest_labs, "_read_any", side_effect=ingest_labs.PdfUnreadable("synthetic")):
            result = self.ingest(force=True)
        self.assertTrue(result.get("errors"))
        self.assertEqual(before, target.read_bytes())

    def test_cancel_before_section_write_preserves_previous_bytes(self):
        self.ingest()
        target = self.profile / "labs.json"
        before = target.read_bytes()
        calls = []
        def stop(*args):
            calls.append(args)
            if len(calls) == 2:
                raise InterruptedError("synthetic cancellation")
        with self.assertRaises(InterruptedError):
            self.ingest(force=True, progress=stop)
        self.assertEqual(before, target.read_bytes())

    def test_reviewed_archive_uses_the_same_section_dates(self):
        from scholion import lab_archive
        preview = lab_archive.preview(str(self.forms))
        self.assertEqual("preview", preview["status"], preview)
        self.assertTrue(preview["approval_token"])
        self.assertFalse((self.profile / "labs.json").exists())
        result = lab_archive.run(str(self.forms), approval=preview["approval_token"])
        self.assertTrue(result["ok"], result)
        self.assertEqual(["2020-11-25", "2020-12-02"], [p["date"] for p in self.series("glucose")])
        for point in self.series("glucose"):
            self.assertEqual(point["date"], point["source"]["section"]["date"])

    def test_an_ordinary_study_heading_does_not_invent_a_lab_draw(self):
        text = "Консультация 25.11.2020\nГлюкоза 5,1 ммоль/л\n"
        self.assertIsNone(ingest_labs.lab_documents(text)[0]["date_hint"])
        self.assertEqual([], ingest_studies.split_documents(text))

    def test_explicit_collection_date_takes_precedence_over_section_date(self):
        self.text = ("Общий анализ крови 25.11.2020\nДата взятия: 24.11.2020 08:15\n"
                     "Глюкоза 5,1 ммоль/л\n")
        self.ingest()
        self.assertEqual("2020-11-24T08:15", self.series("glucose")[0]["date"])
