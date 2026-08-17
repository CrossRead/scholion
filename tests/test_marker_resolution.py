"""A name a person types finds the marker, or is refused with near misses.

Before this, `add-lab` took whatever string it was given as a key. A typo did not
fail — it created a marker of that name with an empty history, and from then on
one analyte had two series under two spellings. Nothing in any screen says that
happened: each series looks perfectly ordinary, one is simply shorter than the
person's memory of it.

That is the defect this file guards. The second one it guards is subtler and
belongs to the multilingual dictionary: a person may know a marker as `glucose` or
as «глюкоза», and which of the two they type has nothing to do with the language
they asked the output to be in. Matching therefore runs across every language at
once, and the test for it is that both spellings land in the SAME series — not
that both are accepted.

The CSV import is here for the same reason: it is the same resolution, applied
thirty times, where the cost of getting it wrong is thirty times higher and the
person is least likely to be watching.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support

from scholion import core, import_csv, store


class _Profile(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "profile").mkdir()
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.dir / "profile")
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        core.reset_cache()
        shutil.rmtree(self.dir, ignore_errors=True)

    def keys(self):
        return sorted(core.labs().get("markers", {}))


class TestBothLanguagesReachOneSeries(_Profile):

    def test_an_english_and_a_russian_name_land_in_the_same_key(self):
        store.add_lab_point("Glucose", "2026-08-01", 5.4, unit="mmol/L")
        store.add_lab_point("глюкоза", "2026-09-01", 5.6, unit="mmol/L")
        self.assertEqual(self.keys(), ["glucose"],
                         "the same test opened two series under two spellings — the exact "
                         "failure this gate exists for")
        self.assertEqual(len(core.labs()["markers"]["glucose"]["series"]), 2)

    def test_the_key_itself_still_works(self):
        self.assertEqual(core.resolve_marker("hba1c")["key"], "hba1c")

    def test_case_does_not_matter(self):
        for spelling in ("Ferritin", "FERRITIN", "ferritin"):
            self.assertEqual(core.resolve_marker(spelling)["key"], "ferritin")

    def test_an_english_display_name_resolves(self):
        self.assertEqual(core.resolve_marker("LDL cholesterol")["key"], "ldl")
        self.assertEqual(core.resolve_marker("Thyroid-stimulating hormone (TSH)")["key"], "tsh")


class TestATypoDoesNotOpenASecondSeries(_Profile):

    def test_an_unknown_name_writes_nothing(self):
        r = store.add_lab_point("glocose", "2026-08-01", 5.4, unit="mmol/L")
        self.assertFalse(r.get("ok"))
        self.assertEqual(self.keys(), [])

    def test_the_refusal_suggests_the_marker_that_was_meant(self):
        """A refusal with no suggestion is the moment somebody reaches for --new."""
        r = store.add_lab_point("glocose", "2026-08-01", 5.4, unit="mmol/L")
        self.assertIn("glucose", [c["key"] for c in r.get("candidates", [])])

    def test_a_misspelling_in_russian_is_also_caught(self):
        r = core.resolve_marker("гемоглабин")
        self.assertIsNone(r["key"])
        self.assertIn("hemoglobin", [c["key"] for c in r["candidates"]])

    def test_an_ambiguous_name_asks_rather_than_guesses(self):
        r = core.resolve_marker("cholesterol")
        self.assertIsNone(r["key"], "«cholesterol» names four markers — picking one silently "
                                    "would put HDL into the total cholesterol series")
        self.assertIn("cholesterol_total", [c["key"] for c in r["candidates"]])

    def test_a_deliberate_new_marker_is_allowed(self):
        r = store.add_lab_point("my_own_thing", "2026-08-01", 1.0, unit="mg/L", new=True)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(self.keys(), ["my_own_thing"])


class TestTheCsvImportIsAllOrNothing(_Profile):

    HEAD = "marker,date,value,unit,ref_low,ref_high\n"

    def _file(self, body, name="panel.csv"):
        p = self.dir / name
        p.write_text(self.HEAD + body, encoding="utf-8")
        return str(p)

    def test_a_clean_file_is_imported(self):
        path = self._file("Glucose,2026-08-01,95,mg/dL,70,99\n"
                          "Ferritin,2026-08-01,41,ng/mL,30,400\n")
        r = import_csv.run(path)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["written"], 2)
        self.assertEqual(self.keys(), ["ferritin", "glucose"])

    def test_the_reference_range_is_converted_with_the_value(self):
        """Found by running the import, not by reading the code.

        The value was converted and the corridor was not, so 95 mg/dL became
        5.27 mmol/L against a range of 70–99 and read as far below normal — the
        original defect, one level down.
        """
        path = self._file("Glucose,2026-08-01,95,mg/dL,70,99\n")
        import_csv.run(path)
        m = core.labs()["markers"]["glucose"]
        self.assertAlmostEqual(m["ref_low"], 3.886, places=2)
        self.assertAlmostEqual(m["ref_high"], 5.496, places=2)
        self.assertLess(m["series"][0]["value"], m["ref_high"],
                        "a normal result must not read as out of range after conversion")

    def test_one_bad_row_writes_nothing_at_all(self):
        path = self._file("Glucose,2026-08-01,5.4,mmol/L,3.9,6.1\n"
                          "Ferritn,2026-08-01,41,ng/mL,30,400\n")
        r = import_csv.run(path)
        self.assertFalse(r["ok"])
        self.assertEqual(self.keys(), [],
                         "half a panel was written — and half a panel in a profile looks "
                         "exactly like a whole one")

    def test_the_report_names_the_row_and_the_reason(self):
        path = self._file("Glucose,2026-08-01,5.4,mmol/L,,\n"
                          "Ferritn,2026-08-01,41,ng/mL,,\n")
        r = import_csv.run(path)
        self.assertEqual(r["problems"][0]["row"], 3)
        self.assertIn("ferritin", r["problems"][0]["reason"])

    def test_a_bad_unit_is_caught_before_anything_is_written(self):
        path = self._file("Glucose,2026-08-01,95,parsec,,\n")
        r = import_csv.run(path)
        self.assertFalse(r["ok"])
        self.assertEqual(self.keys(), [])

    def test_a_dry_run_writes_nothing_and_says_so(self):
        path = self._file("Glucose,2026-08-01,95,mg/dL,70,99\n")
        r = import_csv.run(path, dry_run=True)
        self.assertTrue(r["ok"])
        self.assertTrue(r["dry_run"])
        self.assertEqual(r["written"], 0)
        self.assertEqual(self.keys(), [])

    def test_semicolons_and_a_comma_decimal_mark_are_understood(self):
        """A European spreadsheet exports this, and refusing it means explaining why."""
        p = self.dir / "eu.csv"
        p.write_text("marker;date;value;unit\nGlucose;2026-08-01;5,4;mmol/L\n", encoding="utf-8")
        r = import_csv.run(str(p))
        self.assertTrue(r["ok"], r)
        self.assertEqual(core.labs()["markers"]["glucose"]["series"][0]["value"], 5.4)

    def test_a_missing_column_is_named(self):
        p = self.dir / "short.csv"
        p.write_text("marker,value\nGlucose,5.4\n", encoding="utf-8")
        r = import_csv.run(str(p))
        self.assertFalse(r["ok"])
        self.assertIn("date", r["error"])


if __name__ == "__main__":
    unittest.main()
