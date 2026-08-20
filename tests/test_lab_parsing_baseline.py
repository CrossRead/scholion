"""Russian lab forms parse exactly as they did before the dictionary was migrated.

The marker dictionary is moving to a multilingual schema: names and recognition
rules go under `labels.ru`, `material` becomes `specimen`, units become UCUM
codes. Every reader of the dictionary changes with it. Behind those keys sit
series seven years long, and the failure mode of a migration like this is not a
crash — it is a marker that quietly stops being recognised, so the next draw
starts a new series under the same name and the chart shows a break that never
happened in the person.

The baseline in `fixtures/labforms/expected.json` was recorded **before** the
migration, at v2.11.0. That timing is the whole value of this file, and it is
worth being explicit about why: a test that records the baseline after the change
and then compares against it states that the code equals itself. It passes on any
behaviour, including the broken one. The rule is written in the track's
specification and repeated here because it is easy to lose in a rebase.

The forms are invented — five layouts covering the paths that differ:

* `01_biochem` — the ordinary numeric collector: a value, a range, a unit;
* `02_cbc` — two columns in one row (percent and absolute count of one cell type,
  told apart by `require`), plus a name broken by a line wrap;
* `03_hormones` — a marker printed in the non-canonical unit (25-OH vitamin D in
  nmol/L, converted by the `units` gate to ng/mL), next to a legend block that
  must not be read as a result;
* `04_coprogram` — a word result mapped onto an ordinal scale, with the same word
  («слизь») printed in both the macroscopic and the microscopic section;
* `05_dysbiosis` — powers of ten with censoring («менее 10^4» kept at the bound).

If this file fails after a change to the dictionary or to `ingest_labs`, the
answer is not to refresh the baseline. It is to find which marker stopped being
recognised.
ONE deliberate refresh has happened since (19.08.2026): the `date` field of all
five forms gained the clock time the form prints, because a point stored at month
granularity made two draws in a single day indistinguishable and the second was
reported as a discrepancy with the first. Only the date changed — every marker
and every parsed record stayed identical, which is what made the refresh safe to
accept rather than a symptom to investigate.

"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import support

from scholion import core, ingest_labs

FORMS = support.ROOT / "tests" / "fixtures" / "labforms"
BASELINE = FORMS / "expected.json"


class TestParsingIsUnchanged(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads(BASELINE.read_text(encoding="utf-8"))["reports"]
        cls.markers = core.lab_markers().get("markers", {})

    def _parse(self, name):
        text = (FORMS / name).read_text(encoding="utf-8")
        date, found = ingest_labs.parse_report(text, self.markers, source=name)
        return {"date": date, "found": found}

    def test_every_form_in_the_baseline_still_parses_the_same(self):
        for name, want in self.expected.items():
            with self.subTest(form=name):
                got = self._parse(name)
                self.assertEqual(got["date"], want["date"], f"{name}: the draw date changed")
                lost = sorted(set(want["found"]) - set(got["found"]))
                self.assertEqual(lost, [], f"{name}: markers no longer recognised: {lost}")
                extra = sorted(set(got["found"]) - set(want["found"]))
                self.assertEqual(extra, [], f"{name}: markers recognised that were not before: "
                                            f"{extra} — that is also a change of behaviour")
                for key, w in want["found"].items():
                    self.assertEqual(got["found"][key], w,
                                     f"{name}/{key}: the parsed record changed")

    def test_the_baseline_covers_the_paths_that_differ(self):
        """A baseline of one easy form would pass a migration that broke the rest."""
        found = {k for r in self.expected.values() for k in r["found"]}
        self.assertTrue(any(k.startswith("dysb_") for k in found), "the dysbacteriosis branch")
        self.assertTrue(any(k.startswith("stool_") for k in found), "the word-scale branch")
        self.assertIn("neut_pct", found, "the two-column row")
        self.assertIn("neut_abs", found, "the two-column row")
        self.assertIn("vitamin_d", found, "the unit conversion gate")
        self.assertGreaterEqual(len(found), 25)

    def test_the_unit_gate_converted_rather_than_copied(self):
        """25-OH vitamin D was printed as 62.5 nmol/L and must be stored as 25 ng/mL.

        Pinned as its own case because it is the one place in the fixture where a
        silent regression would look plausible: 62.5 is a believable ng/mL value,
        and it is exactly twice the lower reference bound instead of below it.
        """
        self.assertEqual(self.expected["03_hormones.txt"]["found"]["vitamin_d"]["value"], 25.0)
        got = self._parse("03_hormones.txt")
        self.assertEqual(got["found"]["vitamin_d"]["value"], 25.0)

    def test_the_forms_declare_themselves_invented(self):
        for p in sorted(FORMS.glob("*.txt")):
            with self.subTest(form=p.name):
                head = p.read_text(encoding="utf-8")[:200].upper()
                self.assertTrue("СИНТЕТИЧЕСКАЯ" in head or "SYNTHETIC" in head,
                                "a lab form in the repository must say outright that it is not "
                                "anyone's — the build audit judges by that declaration. Either "
                                "alphabet: the fixture is written in the language of the form "
                                "it imitates, and the declaration belongs with it")


class TestAnEnglishFormParsesToo(unittest.TestCase):
    """A forward baseline, not a historical one — and it says so.

    The Russian baseline above is evidence about the past: it was recorded before a
    migration, and its value is the timing. This one is the opposite kind. It was
    recorded the moment English form parsing first worked, and it exists so that
    the next change cannot quietly take it away again — the failure mode of an
    input path is not a crash but a marker that stops being found, and nobody
    reads a form to notice.

    16 markers off one invented American panel. What it demonstrates is that the
    obstacle was never the names: the names were added in v2.13.0 and 31 of the 76
    still did not parse, all of them stopped by gates that spelled their units in
    Russian only.
    """

    @classmethod
    def setUpClass(cls):
        cls.markers = core.lab_markers().get("markers", {})
        cls.text = (FORMS / "06_english_panel.txt").read_text(encoding="utf-8")

    def setUp(self):
        self.date, self.found = ingest_labs.parse_report(
            self.text, self.markers, source="06_english_panel.txt")

    def test_the_iso_date_is_read(self):
        self.assertEqual(self.date, "2024-03-14")

    def test_the_panel_is_recognised(self):
        for key in ("glucose", "cholesterol_total", "ldl", "hdl", "triglycerides",
                    "alt", "ast", "creatinine", "ferritin", "vitamin_d", "tsh",
                    "hemoglobin", "wbc", "platelets", "neut_abs", "neut_pct"):
            with self.subTest(marker=key):
                self.assertIn(key, self.found)

    def test_the_unit_of_a_blood_count_is_not_taken_for_the_result(self):
        """«10^9/L» holds a ten, and a neutrophil count of 10 is plausible.

        The mask that removes unit digits knew «10^9/л» and not «10^9/L», so the
        English row returned the ten of the unit. Nothing downstream could catch
        it: 10 is a believable number for that marker.
        """
        self.assertEqual(self.found["neut_abs"]["value"], 3.62)
        self.assertEqual(self.found["wbc"]["value"], 6.2)

    def test_a_number_inside_the_name_is_not_taken_for_the_result(self):
        """«Vitamin D (25-OH)» — the 25 belongs to the name.

        In Russian the digits stand BEFORE the name («25-ОН витамин D») and the
        segment searched for a value starts after it, so this never arose. In
        English the qualifier trails the name: the parser read 25 nmol/L, converted
        it to 10 ng/mL and reported a deficiency for a value that was normal.
        """
        self.assertEqual(self.found["vitamin_d"]["value"], 25.0)

    def test_the_plural_printed_on_the_form_still_matches_the_singular_name(self):
        """«Triglycerides» on the form, `triglyceride` in the dictionary."""
        self.assertIn("triglycerides", self.found)
        self.assertEqual(self.found["triglycerides"]["value"], 2.31)

    def test_the_conversion_still_runs_on_an_english_unit(self):
        """62.5 nmol/L of vitamin D is 25 ng/mL — the gate converts, it does not copy."""
        self.assertEqual(self.found["vitamin_d"]["value"], 25.0)


if __name__ == "__main__":
    unittest.main()
