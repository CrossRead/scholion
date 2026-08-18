"""The marker dictionary keeps the shape its readers expect.

The dictionary is the one file in this project that a person's history is keyed
on. Everything else can be recomputed; a marker key cannot, because behind it sit
points collected over years, and nothing in the output would say that a key
changed — the old series simply stops at the day of the change and a new one
starts beside it under a name that looks the same on screen.

So the rules below are not style. Each is a way that has actually been available
for a dictionary edit to corrupt data silently:

* a key renamed → one series becomes two;
* a recognition rule left at the top level after the move to `labels` → the
  parser stops seeing it, and the marker quietly disappears from every future
  form;
* a `units` map filled in "for completeness" → it is a GATE, and a marker whose
  form does not repeat the unit next to the value stops being read;
* a unit that is not a UCUM code → the label table cannot render it, and the
  number is printed bare or with a code where a unit should be.
"""
from __future__ import annotations

import json
import re
import unittest

import support

from scholion import core

K = support.ROOT / "src" / "scholion" / "knowledge"
DICT = json.loads((K / "lab_markers.json").read_text(encoding="utf-8"))
MARKERS = DICT["markers"]
UNITS = json.loads((K / "units.json").read_text(encoding="utf-8"))["units"]

#: Fields that belong to a language and must not be left at the top level.
LANG_FIELDS = ("names", "exclude", "require", "form_require", "form_exclude",
               "next_require", "next_exclude", "prefer_form", "display_name")

SPECIMENS = {"blood", "serum", "plasma", "urine", "stool", "saliva"}


class TestTheSchemaIsWhatTheReadersAssume(unittest.TestCase):

    def test_the_schema_is_declared(self):
        self.assertEqual(DICT["_meta"].get("schema"), 2)

    def test_no_language_field_was_left_at_the_top_level(self):
        """The migration is complete, or the parser is reading half a dictionary."""
        stray = [f"{k}.{f}" for k, spec in MARKERS.items()
                 for f in LANG_FIELDS if f in spec]
        self.assertEqual(stray, [], "recognition rules outside labels.<lang>: "
                         + ", ".join(stray[:10]))

    def test_every_marker_can_be_recognised_or_says_why_not(self):
        """A marker with no names in any language can never match a form.

        Not fatal on its own — a few keys exist only to be written into by hand —
        but it must be a visible number rather than an accident, so a migration
        that dropped names on the floor shows up as a jump in this count.
        """
        nameless = [k for k, spec in MARKERS.items() if not core.marker_rules(spec, "names")]
        self.assertEqual(nameless, [], "markers with no recognition names at all: "
                         + ", ".join(nameless[:10]))

    def test_specimen_uses_the_controlled_vocabulary(self):
        bad = []
        for k, spec in MARKERS.items():
            sp = spec.get("specimen")
            for v in ([sp] if isinstance(sp, str) else (sp or [])):
                if v not in SPECIMENS:
                    bad.append(f"{k}: {v!r}")
        self.assertEqual(bad, [], "; ".join(bad[:10]))

    def test_every_unit_is_a_code_the_label_table_knows(self):
        """Otherwise the report prints a code, or nothing, where a unit belongs."""
        unknown = sorted({spec["unit"] for spec in MARKERS.values()
                          if spec.get("unit") and spec["unit"] not in UNITS})
        self.assertEqual(unknown, [], "units absent from knowledge/units.json: "
                         + ", ".join(unknown))

    def test_every_label_in_the_unit_table_carries_both_languages(self):
        missing = [c for c, v in UNITS.items()
                   if not (isinstance(v.get("label"), dict)
                           and v["label"].get("en") and v["label"].get("ru"))]
        self.assertEqual(missing, [], "unit labels missing a language: " + ", ".join(missing))

    def test_a_display_label_is_a_string_in_every_language_that_has_one(self):
        bad = []
        for k, spec in MARKERS.items():
            for lang, block in (spec.get("labels") or {}).items():
                d = block.get("display")
                if d is not None and not (isinstance(d, str) and d.strip()):
                    bad.append(f"{k}.labels.{lang}.display")
        self.assertEqual(bad, [], "; ".join(bad[:10]))

    def test_recognition_substrings_are_lower_case(self):
        """`names` are matched against a lower-cased row: an upper-case letter never matches.

        Silent by construction — the marker is simply never found — and easy to
        introduce, because a label and a search substring look alike.
        """
        bad = []
        for k, spec in MARKERS.items():
            for field in ("names", "exclude", "require", "next_require", "next_exclude"):
                for s in core.marker_rules(spec, field):
                    if s != s.lower():
                        bad.append(f"{k}.{field}: {s!r}")
        self.assertEqual(bad, [], "; ".join(bad[:10]))


class TestTheUnitsGateIsNotWidened(unittest.TestCase):
    """`units` is a gate before it is a conversion table.

    `ingest_labs` skips a row when the marker declares `units` and none of them
    occurs in the segment. Filling the field in where no conversion is needed
    therefore does not add information — it removes markers, on any form that
    prints the unit once in a column header instead of beside every value.
    """

    def test_a_units_map_always_contains_its_own_canonical_unit(self):
        """A conversion table that cannot express «already canonical» is a trap.

        The multiplier for the canonical unit is 1.0, and it has to be present:
        without it the marker's own unit is not in the gate, and a form printing
        the canonical unit — the common case — stops being read.
        """
        bad = []
        for k, spec in MARKERS.items():
            units = spec.get("units") or {}
            if not units:
                continue
            if not any(abs(float(v) - 1.0) < 1e-9 for v in units.values()):
                bad.append(f"{k}: {sorted(units)}")
        self.assertEqual(bad, [], "a units map with no 1.0 entry — the canonical unit itself "
                         "would be rejected: " + "; ".join(bad[:10]))

    def test_nothing_declares_a_conversion_for_an_ordinal_scale(self):
        """A coprogram's «умеренно» → 3 is a rank. Multiplying it produces a number
        that looks measured and is not."""
        bad = [k for k, spec in MARKERS.items()
               if spec.get("units") and UNITS.get(spec.get("unit"), {}).get("convertible") is False]
        self.assertEqual(bad, [], "; ".join(bad))


class TestKeysAreFrozen(unittest.TestCase):
    """A key is the primary key of a person's series and is never renamed.

    The list of keys is pinned by count and by a sample of long-lived ones rather
    than in full: the dictionary is meant to grow, and a test that fails whenever
    a marker is added is a test people delete.
    """

    ALWAYS = ("glucose", "hba1c", "cholesterol_total", "ldl", "hdl", "triglycerides",
              "hemoglobin", "ferritin", "vitamin_d", "tsh", "creatinine", "alt", "ast",
              "neut_abs", "neut_pct", "platelets", "wbc")

    def test_the_long_lived_keys_are_all_still_there(self):
        missing = [k for k in self.ALWAYS if k not in MARKERS]
        self.assertEqual(missing, [], "keys that carry years of history are gone: "
                         + ", ".join(missing))

    def test_keys_are_ascii_snake_case(self):
        bad = [k for k in MARKERS if not re.fullmatch(r"[a-z0-9_]+", k)]
        self.assertEqual(bad, [], "; ".join(bad[:10]))

    def test_the_dictionary_did_not_shrink(self):
        self.assertGreaterEqual(len(MARKERS), 408,
                                "the dictionary lost markers — a migration that drops a key "
                                "drops the series behind it")


if __name__ == "__main__":
    unittest.main()


class TestTheUnitsAnAmericanReportArrivesIn(unittest.TestCase):
    """The eight-row US panel, in the units a US lab actually prints.

    This is the last of the sixteen forms task 36 counted, and the one place in
    the whole product where an American user meets it on the first screen: the
    gateway refuses a unit it does not know, the lab import is transactional, and
    a single unknown form drops the whole panel rather than one row.

    Every factor is written down with the molar mass it comes from, so that a
    wrong one can be checked by arithmetic instead of by trusting the person who
    typed it. Sources: Quest Diagnostics SI unit conversion table (free T4, free
    T3, DHT) and iron's molar mass for TIBC. Zinc is a decimal prefix and depends
    on nothing.
    """

    CASES = [
        # marker,     value,   incoming unit, expected in the profile's unit
        ("t4_free",   1.3,     "ng/dL",       16.731),    # ×12.87,  M = 776.87
        ("t3_free",   3.2,     "pg/mL",       4.9158),    # ×1.5362, M = 650.98
        ("tibc",      310.0,   "ug/dL",       55.521),    # ×0.1791, M = 55.845 (iron)
        ("zinc",      85.0,    "ug/dL",       850.0),     # ×10, dL → L
        ("dht",       45.0,    "ng/dL",       1.548),     # ×0.0344, M = 290.44
    ]

    def setUp(self):
        self.markers = json.loads(
            (support.ROOT / "src" / "scholion" / "knowledge" / "lab_markers.json")
            .read_text(encoding="utf-8"))
        self.markers = self.markers.get("markers", self.markers)

    def test_each_us_form_is_accepted_and_converts(self):
        for key, value, unit, expected in self.CASES:
            with self.subTest(marker=key):
                conv = (self.markers[key].get("convert") or {})
                self.assertIn(unit, conv, f"{key} does not accept {unit}")
                got = value * conv[unit]
                self.assertAlmostEqual(
                    got, expected, delta=abs(expected) * 0.005,
                    msg=f"{key}: {value} {unit} → {got}, expected about {expected}")

    def test_every_factor_carries_the_arithmetic_that_produced_it(self):
        """A bare number in a conversion table cannot be checked by reading."""
        for key, _, _, _ in self.CASES:
            with self.subTest(marker=key):
                note = self.markers[key].get("convert_note") or ""
                self.assertTrue(note, f"{key} has a factor and no note saying where it came from")
                self.assertRegex(
                    note, r"(M = [\d.]+|decimal prefix|molar mass)",
                    f"{key}'s note does not say what the factor is derived from")

    def test_free_and_total_hormones_do_not_share_a_form(self):
        """pg/mL belongs to free T3 and ng/dL to total T3.

        The same number under the wrong one is out by a factor of ten, and both
        land inside a plausible range, so nothing downstream would notice.
        """
        free = (self.markers["t3_free"].get("convert") or {})
        self.assertIn("pg/mL", free)
        self.assertNotIn("ng/dL", free,
                         "free T3 accepts the form that belongs to total T3")

    def test_neither_of_the_two_hard_cases_is_given_a_multiplier(self):
        """`hba1c` and `lpa` are not oversights — they are decisions.

        Both were refusals until v0.3.1, and one of them stopped being one. HbA1c
        relates to the IFCC scale by the NGSP master equation — affine, not
        proportional — so it now converts under `convert_affine`, which is a second
        law rather than a fudged factor. Lp(a) mass to molar still depends on the
        size of the person's apo(a) isoform, so no constant of any shape relates
        the two, and it stays refused.

        What must not change for either is the thing this layer exists to prevent:
        a plain multiplier where none exists.
        """
        for key, form in (("hba1c", "mmol/mol"), ("lpa", "mg/dL")):
            with self.subTest(marker=key):
                spec = self.markers[key]
                self.assertNotIn(form, spec.get("convert") or {},
                                 f"{key} was given a multiplier for {form}, which has none")
                self.assertNotIn(form, spec.get("units") or {},
                                 f"{key} was given a multiplier for {form} by the back door")
                recorded = ((form in (spec.get("convert_refused") or {}))
                            or (form in (spec.get("convert_affine") or {})))
                self.assertTrue(recorded,
                                f"{key} no longer records any decision about {form}: it is "
                                f"neither refused nor converted, so the form simply falls "
                                f"through as an unrecognised unit")

    def test_the_affine_rule_is_a_formula_and_says_where_it_came_from(self):
        rule = (self.markers["hba1c"].get("convert_affine") or {}).get("mmol/mol")
        self.assertIsNotNone(rule, "HbA1c cannot read the commonest unit on a "
                                   "European report")
        self.assertIn("k", rule)
        self.assertIn("b", rule)
        self.assertNotEqual(rule["b"], 0,
                            "an offset of zero is a multiplier wearing the other law's "
                            "clothes — if that is right, `convert` is the place for it")
        self.assertTrue(rule.get("source"), "a conversion constant with no citation")
