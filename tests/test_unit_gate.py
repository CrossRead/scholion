"""A value enters the profile in a known unit, or it does not enter.

This is the one defect of the release audit that is a safety defect rather than a
correctness one, and its shape is worth stating exactly:

Action thresholds are stored in the canonical unit and do not name it — glucose
≥ 5.6 means mmol/L, uric acid ≥ 360 means µmol/L. `add_lab_point` wrote the unit
as a free string and the value as given. So `add-lab glucose … 95 --unit mg/dL`
put 95 into the series, and the decision layer compared 95 against 5.6 and
reported the threshold crossed by a factor of seventeen. Nothing failed. The
sentence went into the report, and reports are what people take to their doctor.

A wrong unit is not an input error to be tolerated — it is arithmetic belonging to
someone else, presented as the person's own. So the rule is: recognised and
converted, or refused with nothing written. The third option, «store as given and
hope», is the defect.

The refusals are tested as carefully as the conversions. A gate that rejects the
right unit is a gate people route around, and the way around it is `--new`, which
is exactly where a real second series gets born.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support

from scholion import core, store


class _Profile(unittest.TestCase):
    """Each test writes into a fresh profile directory of its own."""

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

    def series(self, key):
        return (core.labs().get("markers", {}).get(key) or {}).get("series", [])


class TestTheValueIsConverted(_Profile):

    def test_glucose_in_mg_per_dl_lands_as_mmol_per_litre(self):
        """The case from the audit, with the number it produced."""
        r = store.add_lab_point("glucose", "2026-08-01", 95, unit="mg/dL")
        self.assertTrue(r.get("ok"), r)
        self.assertAlmostEqual(self.series("glucose")[0]["value"], 5.2734, places=3)
        self.assertEqual(core.labs()["markers"]["glucose"]["unit"], "mmol/L")

    def test_the_series_records_the_canonical_unit_not_the_typed_one(self):
        """Otherwise the next reader has to guess which of the two the number is in."""
        store.add_lab_point("creatinine", "2026-08-01", 1.1, unit="mg/dL")
        self.assertEqual(core.labs()["markers"]["creatinine"]["unit"], "umol/L")
        self.assertAlmostEqual(self.series("creatinine")[0]["value"], 97.24, places=2)

    def test_a_russian_spelling_of_the_same_unit_works(self):
        store.add_lab_point("glucose", "2026-08-01", 95, unit="мг/дл")
        self.assertAlmostEqual(self.series("glucose")[0]["value"], 5.2734, places=3)

    def test_the_canonical_unit_passes_through_unchanged(self):
        store.add_lab_point("glucose", "2026-08-01", 5.4, unit="mmol/L")
        self.assertEqual(self.series("glucose")[0]["value"], 5.4)

    def test_case_and_spacing_do_not_matter(self):
        store.add_lab_point("glucose", "2026-08-01", 95, unit=" MG/DL ")
        self.assertAlmostEqual(self.series("glucose")[0]["value"], 5.2734, places=3)

    def test_testosterone_tells_ng_per_dl_from_ng_per_ml(self):
        """Two spellings a hundredfold apart, both in common use."""
        store.add_lab_point("testosterone", "2026-08-01", 500, unit="ng/dL")
        store.add_lab_point("testosterone", "2026-08-02", 5.0, unit="ng/mL")
        vals = [p["value"] for p in self.series("testosterone")]
        self.assertAlmostEqual(vals[0], 17.335, places=2)
        self.assertAlmostEqual(vals[1], 17.335, places=2)


class TestNothingIsWrittenOnRefusal(_Profile):

    def test_an_unknown_unit_writes_nothing_at_all(self):
        r = store.add_lab_point("glucose", "2026-08-01", 5.4, unit="parsec")
        self.assertFalse(r.get("ok"))
        self.assertEqual(self.series("glucose"), [],
                         "the point was refused and stored anyway — a partial write is worse "
                         "than either outcome, because the refusal says it did not happen")

    def test_the_refusal_names_what_would_be_accepted(self):
        r = store.add_lab_point("glucose", "2026-08-01", 5.4, unit="mmol")
        self.assertIn("mmol/L", r.get("error", ""))
        self.assertIn("mg/dL", r.get("error", ""))

    def test_a_new_series_without_a_unit_is_refused(self):
        r = store.add_lab_point("ldl", "2026-08-01", 3.2)
        self.assertFalse(r.get("ok"))
        self.assertEqual(self.series("ldl"), [])

    def test_an_existing_series_accepts_a_point_without_a_unit(self):
        """The series already declares its unit — the point joins it.

        Without this the web form, which sends no unit for a marker that is already
        in the profile, would refuse every ordinary entry, and the gate would be
        switched off within a day.
        """
        store.add_lab_point("ldl", "2026-08-01", 3.2, unit="mmol/L")
        r = store.add_lab_point("ldl", "2026-09-01", 3.4)
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(len(self.series("ldl")), 2)

    def test_hba1c_in_ifcc_units_is_refused_with_its_reason(self):
        """The conversion is affine, and a multiplier would read 6.5 % as 4.4 %.

        Refused rather than approximated, and the reason is in the message: a
        person told only «unknown unit» about a unit that plainly exists goes
        looking for a typo, finds none, and enters the number bare.
        """
        r = store.add_lab_point("hba1c", "2026-08-01", 48, unit="mmol/mol")
        self.assertFalse(r.get("ok"))
        self.assertEqual(self.series("hba1c"), [])


class TestTheConstantsThemselves(unittest.TestCase):
    """The coefficients, checked against their own stated molar masses.

    A conversion table is the kind of data that is never read again after it is
    written, and a wrong constant is invisible from the outside: the number simply
    comes out plausible and wrong. So each entry is recomputed here from the mass
    named in its own note.
    """

    MARKERS = json.loads((support.ROOT / "src" / "scholion" / "knowledge"
                          / "lab_markers.json").read_text(encoding="utf-8"))["markers"]

    #: marker, surface form, molar mass, the formula that gives the factor
    CASES = [
        ("glucose", "mg/dL", 180.16, lambda m: 10 / m),
        ("cholesterol_total", "mg/dL", 386.65, lambda m: 10 / m),
        ("ldl", "mg/dL", 386.65, lambda m: 10 / m),
        ("triglycerides", "mg/dL", 885.4, lambda m: 10 / m),
        ("creatinine", "mg/dL", 113.12, lambda m: 10000 / m),
        ("urea", "mg/dL", 60.06, lambda m: 10 / m),
        ("urea", "mg/dL (BUN)", 28.014, lambda m: 10 / m),
        ("uric_acid", "mg/dL", 168.11, lambda m: 10000 / m),
        ("bilirubin_total", "mg/dL", 584.66, lambda m: 10000 / m),
        ("iron", "ug/dL", 55.845, lambda m: 10 / m),
        ("phosphorus", "mg/dL", 30.974, lambda m: 10 / m),
        ("homocysteine", "mg/L", 135.18, lambda m: 1000 / m),
        ("testosterone", "ng/dL", 288.42, lambda m: 10 / m),
        ("estradiol", "pg/mL", 272.38, lambda m: 1 / m),
        ("cortisol", "ug/dL", 362.46, lambda m: 10000 / m),
        ("folate", "ng/mL", 441.4, lambda m: 1000 / m),
        ("vitamin_b12", "pmol/L", 1355.4, lambda m: m / 1000),
        ("vitamin_d", "nmol/L", 400.6, lambda m: m / 1000),
    ]

    def test_each_coefficient_matches_its_molar_mass(self):
        for key, surface, mass, formula in self.CASES:
            with self.subTest(marker=key, unit=surface):
                got = (self.MARKERS[key].get("convert") or {}).get(surface)
                self.assertIsNotNone(got, f"{key}: no conversion for {surface}")
                want = formula(mass)
                # Relative, not absolute: these factors span 0.003 to 88, and an
                # absolute tolerance would be meaningless at one end and absurd at
                # the other. 0.1 % lets the conventional rounded constants stand
                # (88.4 rather than 88.4017 — that is what a clinical table
                # prints) while catching everything this test exists for: a factor
                # of ten misplaced, a decimal slipped, or another analyte's
                # constant borrowed.
                self.assertLess(abs(got - want) / want, 1e-3,
                                f"{key}/{surface}: the stored factor {got} does not follow from "
                                f"the molar mass {mass} in its own note (expected ≈{want:.6g})")

    def test_triglycerides_do_not_use_the_cholesterol_constant(self):
        """A substitution that overstates the result 2.3-fold and looks right."""
        tg = self.MARKERS["triglycerides"]["convert"]["mg/dL"]
        chol = self.MARKERS["cholesterol_total"]["convert"]["mg/dL"]
        self.assertNotAlmostEqual(tg, chol, places=4)

    def test_every_conversion_table_carries_its_reasoning(self):
        missing = [k for k, spec in self.MARKERS.items()
                   if spec.get("convert") and not spec.get("convert_note")]
        self.assertEqual(missing, [], "a conversion with no note saying where the constant "
                         "comes from: " + ", ".join(missing))


class TestEveryThresholdHasAScaleToBeOn(unittest.TestCase):
    """An action threshold is a bare number: 5.6, 360, 0.8.

    It means something only because the marker it names has one canonical unit and
    every value stored under that marker is in it. A threshold on a marker with no
    canonical unit is a comparison against nothing in particular — and it does not
    fail, it just answers.
    """

    K = support.ROOT / "src" / "scholion" / "knowledge"

    def setUp(self):
        self.thresholds = json.loads((self.K / "clinical_thresholds.json")
                                     .read_text(encoding="utf-8")).get("markers", {})
        self.markers = json.loads((self.K / "lab_markers.json")
                                  .read_text(encoding="utf-8"))["markers"]

    def test_every_threshold_names_a_marker_that_exists(self):
        missing = sorted(set(self.thresholds) - set(self.markers))
        self.assertEqual(missing, [], "thresholds on markers absent from the dictionary — they "
                         "can never fire: " + ", ".join(missing))

    def test_every_marker_with_a_threshold_has_a_canonical_unit(self):
        bare = sorted(k for k in self.thresholds
                      if k in self.markers and not self.markers[k].get("unit"))
        self.assertEqual(bare, [], "a threshold compared against a value whose unit is "
                         "undefined: " + ", ".join(bare))




class TestTheUnitsAnAmericanPanelIsPrintedIn(unittest.TestCase):
    """A US blood count refuses to load, and the refusal is the whole panel.

    The parsing side was widened in v2.18.0 — `K/µL` is recognised on a form. The
    ENTRY side was not: `scholion add-lab` and the CSV import go through the
    `units` gate, and for the nine markers counted in 10⁹/L that gate accepted
    `10*9/L`, `10⁹/L` and `10⁹/л` and nothing else. Somebody typing what their own
    report prints — `K/uL`, or `10^9/L` with a caret because the superscript is not
    on a keyboard — was told the unit was unrecognised.

    The import is transactional, so one refused row loses the whole panel: a
    twenty-line American report entered nothing at all.

    Every entry added here is a factor of exactly 1 or a decimal power, verified by
    arithmetic and written into `convert_note` beside it:

    * 10³ per microlitre **is** 10⁹ per litre;
    * 10⁶ per microlitre **is** 10¹² per litre;
    * a haematocrit of 0.45 L/L **is** 45 %.

    The two that stay refused are refused on purpose, and each says why in its own
    words — HbA1c because the IFCC scale is affine rather than proportional, Lp(a)
    because mass and molar concentration depend on the person's apo(a) isoform. A
    generic «unrecognised unit» on either of those would invite somebody to find a
    factor on the internet and type the value in anyway.
    """

    @classmethod
    def setUpClass(cls):
        from scholion import core
        cls.core = core
        cls.markers = core.lab_markers().get("markers", {})

    def _resolve(self, key, unit):
        self.assertIn(key, self.markers, f"the base panel has no marker «{key}»")
        return self.core.resolve_unit(self.markers[key], unit)

    def test_every_marker_counted_in_ten_to_the_ninth_takes_the_us_spelling(self):
        keys = [k for k, v in self.markers.items() if v.get("unit") == "10*9/L"]
        self.assertGreaterEqual(len(keys), 5, "the fixture no longer covers the blood count")
        for key in keys:
            for unit in ("K/uL", "K/µL", "10^9/L"):
                with self.subTest(marker=key, unit=unit):
                    r = self._resolve(key, unit)
                    self.assertTrue(r.get("ok"), f"{key} refuses «{unit}»: {r.get('reason')}")
                    self.assertEqual(r["factor"], 1.0,
                                     "10³/µL is 10⁹/L exactly — any other factor is arithmetic "
                                     "somebody invented")

    def test_the_red_cell_count_takes_millions_per_microlitre(self):
        for unit in ("M/uL", "M/µL", "10^12/L"):
            with self.subTest(unit=unit):
                r = self._resolve("rbc", unit)
                self.assertTrue(r.get("ok"), r.get("reason"))
                self.assertEqual(r["factor"], 1.0)

    def test_a_haematocrit_fraction_becomes_a_percentage(self):
        r = self._resolve("hematocrit", "L/L")
        self.assertTrue(r.get("ok"), r.get("reason"))
        self.assertEqual(r["factor"], 100.0, "0.45 L/L is 45 %")

    def test_insulin_accepts_the_spelling_tsh_already_accepted(self):
        """Both are stored in `u[IU]/mL`; only one of them took the ASCII form."""
        self.assertTrue(self._resolve("tsh", "uIU/mL").get("ok"))
        r = self._resolve("insulin", "uIU/mL")
        self.assertTrue(r.get("ok"), "the same unit was accepted for one marker and refused "
                                     "for another")
        self.assertEqual(r["factor"], 1.0)

    def test_the_two_deliberate_refusals_say_why_in_their_own_words(self):
        for key, unit, word in (("hba1c", "mmol/mol", "affine"),
                                ("lpa", "mg/dL", "isoform")):
            with self.subTest(marker=key):
                r = self._resolve(key, unit)
                self.assertFalse(r.get("ok"), f"{key} now converts {unit} by a multiplier")
                self.assertIn(word, (r.get("reason") or ""),
                              "the refusal is generic, so it reads as «we have not got round to "
                              "this unit» rather than «this conversion does not exist»")

    def test_a_unit_that_belongs_to_another_marker_is_still_refused(self):
        """Widening must not turn the gate off."""
        r = self._resolve("wbc", "mmol/L")
        self.assertFalse(r.get("ok"), "the gate accepts a unit from a different quantity")


if __name__ == "__main__":
    unittest.main()
