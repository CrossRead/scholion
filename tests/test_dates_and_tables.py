"""Dates on an American form, and a table whose rows each carry their own.

Two findings from the corpus, both about the same wrong assumption: that a page
of results is a paper form with one draw date at the top.

DATES. The English branch existed and accepted ISO only — `YYYY-MM-DD`. American
laboratories print `07/27/2015` and `July 27, 2015`, so the branch matched none
of the sixteen real cases. Both are read now, and the third case is the one worth
the file: `07/12/2015` is the twelfth of July in the United States and the
seventh of December almost everywhere else. Nothing on the page says which
laboratory printed it. So it is NAMED, not guessed — the same rule as the
sex-specific interval that is left empty rather than borrowed, and for the same
reason: a point filed under the wrong month joins a series and moves a trend.

A date in the FILE NAME is usable and is marked as what it is. People rename
files to the day they downloaded them, so it is read only when the page carries
nothing, and the report says where it came from.

TABLES. A form is one draw; a table is one measurement per row, usually years of
them. Read as a form it is either flattened onto a single day or refused. Both
are wrong answers to a question that should not have been asked, so a delimited
export with a date column now goes to its own reader.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, ingest_labs


class TestEnglishDates(unittest.TestCase):

    def test_iso_still_reads(self):
        self.assertEqual(ingest_labs.english_date("Specimen collected: 2015-07-27")[0],
                         "2015-07-27")

    def test_a_spelt_month_reads_in_either_order(self):
        for text in ("Collected July 27, 2015", "Draw date 27 July 2015",
                     "Collection date: Jul. 27, 2015"):
            with self.subTest(text=text):
                self.assertEqual(ingest_labs.english_date(text)[0], "2015-07-27")

    def test_a_slashed_date_reads_when_the_order_is_decidable(self):
        self.assertEqual(ingest_labs.english_date("Collected 07/27/2015")[0], "2015-07-27")
        self.assertEqual(ingest_labs.english_date("Collected 27/07/2015")[0], "2015-07-27")

    def test_an_ambiguous_slashed_date_is_refused_and_named(self):
        date, ambiguity = ingest_labs.english_date("Collected 07/12/2015")
        self.assertIsNone(date, "half of these would be filed under the wrong month")
        self.assertEqual(sorted(ambiguity["both"]), ["2015-07-12", "2015-12-07"])

    def test_a_date_with_no_label_beside_it_is_not_a_draw_date(self):
        self.assertEqual(ingest_labs.english_date("Printed 2015-07-27 by LabCorp")[0], None)


class TestADateInTheFileName(unittest.TestCase):

    def test_it_is_read(self):
        self.assertEqual(ingest_labs.date_from_filename("hu1234_phenotypes_2018-05-22.csv"),
                         "2018-05-22")
        self.assertEqual(ingest_labs.date_from_filename("results_20180522.pdf"), "2018-05-22")

    def test_nonsense_is_not(self):
        self.assertIsNone(ingest_labs.date_from_filename("results.pdf"))
        self.assertIsNone(ingest_labs.date_from_filename("panel_2018-99-99.csv"))


class IngestCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.forms = Path(self.tmp.name) / "forms"
        self.forms.mkdir()
        self.profile = Path(self.tmp.name) / "profile"
        self.profile.mkdir()
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.profile)
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        core.reset_cache()
        self.tmp.cleanup()

    def run_ingest(self):
        return ingest_labs.ingest(str(self.forms), force=True)


class TestTheAmbiguousDateReachesTheReport(IngestCase):

    def test_the_file_is_named_with_the_two_readings(self):
        (self.forms / "us_panel.txt").write_text(
            "LabCorp\nCollected 07/12/2015\nFerritin 12 ng/mL 13-150\n", encoding="utf-8")
        r = self.run_ingest()
        entry = [n for n in r["not_ingested"] if n["reason"] == "ambiguous_date"]
        self.assertTrue(entry, "«no date on this form» would be untrue — there is one")
        self.assertIn("2015-12-07", entry[0]["detail"])


class TestTheFilenameDateIsMarked(IngestCase):

    def test_it_is_used_and_said_to_be_from_the_name(self):
        (self.forms / "panel_2018-05-22.txt").write_text(
            "Ferritin 12 ng/mL 13-150\n", encoding="utf-8")
        r = self.run_ingest()
        marks = r.get("date_from_filename") or []
        self.assertTrue(marks, "the page has no date and the name does — say which was used")
        self.assertEqual(marks[0]["date"], "2018-05-22")
        self.assertIn("FILE NAME", marks[0]["note"])


class TestTheTableReaderTakesPrecedence(IngestCase):

    TABLE = ("Timestamp,Test,Result,Units,Reference Range\n"
             "2018-05-22T09:15,Ferritin,12,ng/mL,13-150\n"
             "2019-11-03T08:40,Ferritin,31,ng/mL,13-150\n")

    def test_each_row_keeps_its_own_date_and_clock(self):
        (self.forms / "history.csv").write_text(self.TABLE, encoding="utf-8")
        self.run_ingest()
        labs = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))
        stamps = sorted(p["date"] for p in labs["markers"]["ferritin"]["series"])
        self.assertEqual(stamps, ["2018-05-22T09:15", "2019-11-03T08:40"])

    def test_a_file_with_no_date_column_still_goes_to_the_form_reader(self):
        (self.forms / "form.txt").write_text(
            "Дата взятия 22.05.2018\nФерритин 12 нг/мл 13-150\n", encoding="utf-8")
        r = self.run_ingest()
        self.assertEqual([e.get("kind") for e in r["per_file"]], [None],
                         "a Russian paper form must not be read as a table")



class TestAUnitInsideTheLabel(IngestCase):
    """`Rheumatoid factor - IU / mL` — a real export writes the unit into the label.

    A table with one value column has nowhere else to put it. The split is decided
    by the DICTIONARY and not by the shape of the string: a dash is an ordinary
    character in an analyte's name («anti-CCP», «Complete Blood Count -
    Hematocrit»), so the whole label is offered first and only a failure earns a
    second attempt without the tail. The tail is called a unit exactly when
    removing it is what made the marker resolvable.
    """

    def test_the_marker_resolves_and_the_unit_is_taken_from_the_label(self):
        key, label, unit = ingest_labs.split_label_unit("Rheumatoid factor - IU / mL")
        self.assertEqual(key, "rheumatoid_factor")
        self.assertEqual(label, "Rheumatoid factor")
        self.assertEqual(unit, "IU / mL")

    def test_a_dash_inside_a_name_is_not_a_unit(self):
        key, label, unit = ingest_labs.split_label_unit("Complete Blood Count - Hematocrit")
        self.assertIsNone(unit, "cutting here would rename the marker")
        self.assertEqual(label, "Complete Blood Count - Hematocrit")

    def test_a_plain_label_is_left_alone(self):
        key, label, unit = ingest_labs.split_label_unit("Ferritin")
        self.assertEqual(key, "ferritin")
        self.assertIsNone(unit)

    def test_end_to_end_on_the_shape_the_corpus_actually_holds(self):
        (self.forms / "phenotypes.csv").write_text(
            "Phenotype,Value,Timestamp\n"
            "Rheumatoid factor - IU / mL,401,2/15/2016\n"
            "Ferritin - ng/mL,286.85,10/30/2014\n"
            "Adenomatous polyps of colon - All 3 to 6 mm,3,3/30/2017\n", encoding="utf-8")
        r = self.run_ingest()
        self.assertEqual(r["points_added"], 2)
        markers = r["per_file"][0]["markers"]
        self.assertIn("rheumatoid_factor", markers)
        self.assertIn("ferritin", markers)
        unknown = [n for n in r["not_ingested"] if n["reason"] == "table_labels_unknown"]
        # The shape here is `{label, unit}` — the same one the PDF path produces.
        # It used to be a bare string, and that difference crashed the report
        # renderer on a real file (see `TestTheTwoDefectsTheCorpusRunFound`). The
        # assertion is on the label, not on the container, so that the next
        # change to the container is caught there rather than here.
        labels = [row["label"] for row in unknown[0]["unrecognised"]]
        self.assertIn("Adenomatous polyps of colon - All 3 to 6 mm", labels,
                      "a row nobody can place is named, not stored under an approximate marker")


class TestTheTwoDefectsTheCorpusRunFound(unittest.TestCase):
    """Found by running 0.4.0 over other people's records, not by any test here.

    Both are the cost of a refusal or a shape being decided in the wrong place,
    and both cost real measurements on real forms.
    """

    def test_a_table_with_an_unknown_label_still_renders(self):
        """`ingest-labs` crashed with `'str' object has no attribute 'get'`.

        Two producers filled one field with two different shapes: the PDF path
        returns `{label, unit}`, the table path returned bare strings, and the
        renderer knows only the first. Seven points had already been stored when
        it crashed — the person got a traceback instead of their results.
        """
        from scholion import format as fmt
        from scholion import core
        table = ingest_labs.parse_table(
            "Phenotype,Value,Timestamp\n"
            "Rheumatoid factor - IU / mL,401,2/15/2016\n"
            "Krypton saturation - qq/L,17,2/15/2016\n",
            core.lab_markers().get("markers", {}))
        self.assertTrue(table["ok"], table)
        self.assertTrue(table["unrecognised"], "the invented marker should be unrecognised")
        for row in table["unrecognised"]:
            self.assertIsInstance(row, dict, "the two producers must agree on the shape")
            self.assertIn("label", row)
        out = fmt.ingest_labs_report({"ok": True, "files_processed": 1, "points_added": 1,
                                 "skipped": 0,
                                 "not_ingested": [{"file": "x.csv", "reason": "table_labels_unknown",
                                                   "detail": "d",
                                                   "unrecognised": table["unrecognised"]}]})
        self.assertIn("Krypton", out)

    def test_the_same_day_and_month_is_not_an_ambiguity(self):
        """«04/04/2017» reads the same in both orders.

        The refusal printed «which is either 2017-04-04 or 2017-04-04» and threw
        the form away. A refusal costs a real measurement, so it is spent only
        where there is a real choice to be wrong about.
        """
        date, ambiguity = ingest_labs.english_date("Collected: 04/04/2017")
        self.assertEqual(date, "2017-04-04")
        self.assertIsNone(ambiguity)

    def test_a_real_ambiguity_is_still_refused(self):
        """The reverse, so the fix above cannot become «guess at everything»."""
        date, ambiguity = ingest_labs.english_date("Collected: 08/12/2010")
        self.assertIsNone(date)
        self.assertEqual(sorted(ambiguity["both"]), ["2010-08-12", "2010-12-08"])


if __name__ == "__main__":
    unittest.main()
