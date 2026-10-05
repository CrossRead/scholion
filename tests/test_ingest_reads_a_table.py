"""A folder of results is not necessarily a folder of PDFs.

`ingest()` walked `rglob("*.pdf")`, which is a claim about the world rather than
about the folder in front of it. A laboratory hands out PDFs; an export hands out
CSV, a portal hands out TSV, and a PGP participant's measured values sit in
`hu…_phenotypes_2018.csv`. That participant's genome was read and their lab layer
stayed empty — not because anything failed, but because nothing looked.

The second thing tested here is smaller and worse. `per_file` referred to `ym`, a
month variable that had been removed when a point started keeping its full
timestamp. Every ingest that actually ADDED a point raised NameError — and the
suite stayed green, because not one test ran a successful ingest end to end. So
the first assertion below is deliberately the dullest one in the project: put a
readable file in a folder, run the importer, find the value in the profile.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path

TABLE = """Date,Test,Result,Units,Reference Range
2018-05-22,Ferritin,12,ng/mL,13-150
2018-05-22,Rheumatoid factor,22,IU/mL,0-14
2018-05-22,Glucose,5.1,mmol/L,3.9-5.5
"""

TWO_DATES = """Date,Test,Result,Units,Reference Range
2018-05-22,Ferritin,12,ng/mL,13-150
2019-11-03,Ferritin,31,ng/mL,13-150
"""


class TableCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.forms = self.root / "forms"
        self.forms.mkdir()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.profile)
        # The cache too: the loader's list of already-read files lives beside
        # the profile now, and the loader carries an old list it finds in the
        # cache over into the profile — a test must find nobody's there.
        self._restore_cache = support.pin_cache(self.root / "cache")
        from scholion import core
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        self._restore_cache()
        from scholion import core
        core.reset_cache()
        self.tmp.cleanup()

    def run_ingest(self):
        from scholion import ingest_labs
        return ingest_labs.ingest(str(self.forms), force=True)


class TestMethodPriorityWithPartialClockPrecision(TableCase):
    def test_only_unchanged_completed_sources_restore_a_method(self):
        from scholion import core, ingest_labs
        source = self.forms / "a.pdf"
        source.write_bytes(b"Synthetic extraction fixture")
        rk, mt = str(source.resolve()), source.stat().st_mtime
        origin = {"path": rk, "mtime": mt, "priority": 2}
        pt = {"date": "2018-05-22T10:00", "value": 20, "ingest_method": origin}
        with mock.patch.object(core, "labs", return_value={"markers": {"synthetic": {"series": [pt]}}}):
            self.assertEqual(ingest_labs._seen_ingest_points([source], {rk: mt})[("synthetic", pt["date"])][2], 2)
            self.assertEqual(ingest_labs._seen_ingest_points([source], {}), {})
            self.assertEqual(ingest_labs._seen_ingest_points([source], {rk: mt - 1}), {})
            self.assertEqual(ingest_labs._seen_ingest_points([], {rk: mt}), {})
            for changes in ({"mtime": []}, {"priority": True}, {"priority": 3}, {"path": None}):
                with self.subTest(changes=changes):
                    pt["ingest_method"] = {**origin, **changes}
                    self.assertEqual(ingest_labs._seen_ingest_points([source], {rk: mt}), {})
            pt["ingest_method"] = origin
            for changes in ({"date": "bad"}, {"value": True}, {"value": float("nan")}):
                with self.subTest(changes=changes), mock.patch.object(core, "labs", return_value={
                        "markers": {"synthetic": {"series": [{**pt, **changes}]}}}):
                    self.assertEqual(ingest_labs._seen_ingest_points([source], {rk: mt}), {})

    def test_manual_replacement_drops_the_old_method_witness(self):
        from scholion import core, store
        origin = {"path": str(self.forms / "a.pdf"), "mtime": 1, "priority": 2}
        first = store.add_lab_point("ferritin", "2018-05-22T10:00", 20, unit="ng/mL",
                                   reference_context={"ingest_method": origin})
        self.assertTrue(first["ok"])
        self.assertEqual(core.labs()["markers"]["ferritin"]["series"][0]["ingest_method"], origin)
        self.assertTrue(store.add_lab_point("ferritin", "2018-05-22", 30, unit="ng/mL")["ok"])
        point = core.labs()["markers"]["ferritin"]["series"][0]
        self.assertNotIn("ingest_method", point)
        self.assertEqual((point["date"], point["value"]), ("2018-05-22T10:00", 30))

    def test_resume_preserves_method_priority_and_reports_the_conflict(self):
        from scholion import core, ingest_labs
        class Stop(Exception):
            pass
        for preferred_first in (True, False):
            for ordinary_stamp in ("2018-05-22", "2018-05-22T10:00"):
                with self.subTest(preferred_first=preferred_first, ordinary_stamp=ordinary_stamp):
                    (self.profile / "labs.json").write_text('{"markers":{}}', encoding="utf-8")
                    core.reset_cache()
                    ingest_labs._save_manifest({})
                    paths = [self.forms / "a.pdf", self.forms / "b.pdf"]
                    for path in paths:
                        path.write_bytes(b"Synthetic extraction fixture")
                    texts = ["Collected 2018-05-22 preferred", "Collected 2018-05-22 ordinary"]
                    if not preferred_first:
                        texts.reverse()
                    def parse(text, *args, **kwargs):
                        preferred = "preferred" in text
                        return ("2018-05-22T10:00" if preferred else ordinary_stamp, {"synthetic": {
                            "value": 20 if preferred else 10, "unit": "mg/L", "ref_low": 0, "ref_high": 100}})
                    def stop(done, *args):
                        if done == 1:
                            raise Stop()
                    spec = {"unit": "mg/L", "labels": {"en": {
                        "prefer_form": ["preferred"], "names": ["synthetic"]}}}
                    by_file = dict(zip(paths, texts))
                    with mock.patch.object(core, "lab_markers", return_value={"markers": {"synthetic": spec}}), \
                            mock.patch.object(ingest_labs, "_ensure_extractor", return_value="synthetic"), \
                            mock.patch.object(ingest_labs, "_read_any", side_effect=lambda p: by_file[p]) as read, \
                            mock.patch.object(ingest_labs, "parse_report", side_effect=parse), \
                            mock.patch.object(ingest_labs, "_single_form_problem", return_value=None):
                        with self.assertRaises(Stop):
                            ingest_labs.ingest(str(self.forms), progress=stop)
                        read.reset_mock()
                        result = ingest_labs.ingest(str(self.forms))
                        self.assertEqual(result["skipped"], 1)
                        read.assert_called_once_with(paths[1])
                        self.assertEqual(len(result["conflicts"]), 1, result)
                        self.assertEqual(result["conflicts"][0]["kept"], 20)
                    series = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))["markers"]["synthetic"]["series"]
                    self.assertEqual([(p["date"], p["value"]) for p in series], [("2018-05-22T10:00", 20)])

    def test_partial_precision_keeps_the_preferred_method_in_both_orders(self):
        from scholion import core, ingest_labs
        for preferred_first in (False, True):
            with self.subTest(preferred_first=preferred_first):
                (self.profile / "labs.json").write_text('{"markers":{}}', encoding="utf-8")
                core.reset_cache()
                paths = [self.forms / "a.pdf", self.forms / "b.pdf"]
                for path in paths:
                    path.write_bytes(b"Synthetic extraction fixture")
                texts = ["Дата взятия: 22.05.2018 preferred", "Дата взятия: 22.05.2018 ordinary"]
                if not preferred_first:
                    texts.reverse()
                def parse(text, *args, **kwargs):
                    preferred = "preferred" in text
                    return ("2018-05-22T10:00" if preferred else "2018-05-22", {"synthetic": {
                        "value": 20 if preferred else 10, "unit": "mg/L", "ref_low": 0, "ref_high": 100}})
                spec = {"unit": "mg/L", "direction": "high", "labels": {"en": {
                    "prefer_form": ["preferred"], "names": ["synthetic"]}}}
                with mock.patch.object(core, "lab_markers", return_value={"markers": {"synthetic": spec}}), \
                        mock.patch.object(ingest_labs, "_ensure_extractor", return_value="synthetic"), \
                        mock.patch.object(ingest_labs, "_read_any", side_effect=texts), \
                        mock.patch.object(ingest_labs, "parse_report", side_effect=parse), \
                        mock.patch.object(ingest_labs, "_single_form_problem", return_value=None):
                    result = self.run_ingest()
                self.assertTrue(result["ok"], result)
                self.assertEqual(len(result["conflicts"]), 1, result)
                series = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))["markers"]["synthetic"]["series"]
                self.assertEqual([(p["date"], p["value"]) for p in series], [("2018-05-22T10:00", 20)])


class TestADelimitedExportIsRead(TableCase):

    def test_a_valid_english_date_is_not_also_reported_as_refused(self):
        from scholion import core, ingest_labs
        text = "Date,Test,Result,Units\nMay 22 2018,Ferritin,20,ng/mL\n"
        parsed = ingest_labs.parse_table(text, core.lab_markers()["markers"])
        self.assertEqual(parsed["points"][0]["date"], "2018-05-22")
        self.assertEqual(parsed["refused"], [])
        (self.forms / "english.csv").write_text(text, encoding="utf-8")
        result = self.run_ingest()
        self.assertEqual(result["points_added"], 1)
        self.assertEqual(result["not_ingested"], [])

    def test_an_unrecognised_date_is_reported_once_and_not_written(self):
        from scholion import core, ingest_labs
        parsed = ingest_labs.parse_table(
            "Date,Test,Result,Units\nnot-a-date,Ferritin,20,ng/mL\n", core.lab_markers()["markers"])
        self.assertEqual(parsed["points"], [])
        self.assertEqual(parsed["refused"], [{"row": 2, "reason": "invalid_date"}])

    def test_the_values_reach_the_profile(self):
        (self.forms / "phenotypes.csv").write_text(TABLE, encoding="utf-8")
        r = self.run_ingest()
        self.assertTrue(r["ok"], r.get("error"))
        self.assertEqual(r["files_processed"], 1)
        self.assertGreaterEqual(r["points_added"], 2)
        labs = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))
        self.assertIn("ferritin", labs["markers"])
        self.assertEqual(labs["markers"]["ferritin"]["series"][0]["value"], 12.0)

    def test_the_file_is_reported_as_the_table_it_is(self):
        """The dullest assertion in the project, and the one that was missing.

        It also records which reader took the file: a delimited export goes to
        the row-wise one, where every row keeps its own date, and not to the
        form-shaped reader that would file the whole file under one day.
        """
        (self.forms / "phenotypes.csv").write_text(TABLE, encoding="utf-8")
        r = self.run_ingest()
        entry = r["per_file"][0]
        self.assertEqual(entry["kind"], "table")
        self.assertEqual(entry["rows"], 3)
        self.assertIn("ferritin", entry["markers"])

    def test_the_range_printed_on_the_row_is_the_one_used(self):
        (self.forms / "phenotypes.csv").write_text(TABLE, encoding="utf-8")
        self.run_ingest()
        labs = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))
        self.assertEqual(labs["markers"]["ferritin"]["ref_low"], 13.0)
        self.assertEqual(labs["markers"]["ferritin"]["ref_high"], 150.0)


class TestAHistoryKeepsItsDates(TableCase):
    """The shape a form-shaped reader cannot hold, and the reason for a second one.

    A paper form is one draw: one date at the top, analytes under it. A table is
    the other shape — every row is a measurement with its own date — and a
    person's export usually holds years of them. Read as a form, such a file is
    either flattened onto one day (a history destroyed) or refused (a history
    thrown away). It used to be refused, which was the honest half of a wrong
    choice; now it is read as what it is.
    """

    def test_two_dates_produce_two_points_not_a_refusal(self):
        (self.forms / "history.csv").write_text(TWO_DATES, encoding="utf-8")
        r = self.run_ingest()
        self.assertEqual(r["points_added"], 2)
        labs = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))
        dates = [p["date"][:10] for p in labs["markers"]["ferritin"]["series"]]
        self.assertEqual(sorted(dates), ["2018-05-22", "2019-11-03"])

    def test_a_label_no_marker_matches_is_named_not_approximated(self):
        (self.forms / "odd.csv").write_text(
            TWO_DATES + "2020-02-14,Unobtainium,5,mg/L,1-9\n", encoding="utf-8")
        r = self.run_ingest()
        unknown = [n for n in r["not_ingested"] if n["reason"] == "table_labels_unknown"]
        self.assertTrue(unknown)
        # `{label, unit}`, the shape the PDF path already produced. It was a
        # bare string here, and the two shapes under one name crashed the
        # report renderer on a real file — after the recognised rows had
        # been stored, so the points existed and the person saw a traceback.
        self.assertIn("Unobtainium", [r["label"] for r in unknown[0]["unrecognised"]])


class TestNothingReadable(TableCase):

    def test_an_empty_folder_says_so(self):
        r = self.run_ingest()
        self.assertFalse(r["ok"])

    def test_a_file_with_no_date_is_named_with_its_reason(self):
        (self.forms / "notes.txt").write_text("Ferritin 12 ng/mL\n", encoding="utf-8")
        r = self.run_ingest()
        self.assertEqual(r["points_added"], 0)
        self.assertEqual([n["reason"] for n in r["not_ingested"]], ["no_draw_date"])



class TestTheOwnerIsRereadWhenTheProfileChanges(TableCase):
    """Found by the tests above, and worse than what they were written for.

    `_owner()` cached (sex, age) on first use for the life of the process and
    never looked again. The server holds one process across a whole session, so
    a person who ran an ingest before filling in their profile kept being
    ingested against `(None, None)` — and `(None, None)` is precisely the value
    that switches the multi-line row filter OFF. The failure was towards silence
    in the one place where silence looks like a working filter.
    """

    def test_sex_recorded_after_the_first_read_is_picked_up(self):
        import json as _json
        from scholion import ingest_labs
        (self.profile / "metrics.json").write_text(
            _json.dumps({"profile": {}}), encoding="utf-8")
        self.assertEqual(ingest_labs._owner(), (None, None))
        (self.profile / "metrics.json").write_text(
            _json.dumps({"profile": {"sex": "female", "birth_year": 1985}}),
            encoding="utf-8")
        sex, age = ingest_labs._owner()
        self.assertEqual(sex, "female", "the profile changed and the reader did not look again")
        self.assertIsNotNone(age)

if __name__ == "__main__":
    unittest.main()
