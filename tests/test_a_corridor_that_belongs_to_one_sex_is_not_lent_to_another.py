"""A corridor that belongs to one sex is not lent to another.

Six markers in the dictionary carry both corridors under `ref_by_sex`, and the
code has always refused to lend one of those when the profile records no sex. The
commoner case had no name at all: a marker with ONE corridor, transcribed from
the forms of one person, lent to anybody whose own laboratory printed no range.
HDL's floor of 1.0 mmol/L is a man's; so are AST's ceiling of 40, GGT's of 60,
and the intervals for DHEA-S, DHT and estradiol. Lent to a woman, none of them
fails — each produces a verdict, and the wrong one, with a tick beside it.

The defect was invisible because it was spelled as the ABSENCE of a field. So
absence is no longer allowed: every marker a radar domain scores says whether its
corridor depends on sex, and the suite refuses one that does not.
"""
from __future__ import annotations

import json
import re
import unittest
from unittest import mock
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core

import importlib
lifestyle = importlib.import_module("scholion.engine.lifestyle")
labs = importlib.import_module("scholion.engine.labs")

# `unreviewed` joined the vocabulary on 08.09.2026, when the gate widened from
# the scored markers to the whole dictionary: a corridor that could not be
# checked against a form or a standard interval says so in a word and is lent to
# nobody, rather than claiming `any` in bulk. The count of that word may only
# shrink — `test_a_corridor_is_not_lent_outside_its_age_band.py` freezes it.
ALLOWED = ("any", "male", "female", "unreviewed")


def panel_markers():
    """Every marker any radar domain scores — read off the source, not off a run."""
    src = Path(lifestyle.__file__).read_text(encoding="utf-8")
    block = src[src.index("_RADAR_DOMAINS = ["):]
    block = block[:block.index(chr(10) + "]")]
    out = []
    for _key, body in re.findall(r'\(\s*"([a-z_]+)"\s*,\s*\[([^\]]*)\]', block):
        out += re.findall(r'"([a-z0-9_]+)"', body)
    return sorted(set(out))


class TestEveryScoredMarkerSaysWhoseCorridorItHolds(unittest.TestCase):

    def setUp(self):
        self.cat = json.loads(
            core.knowledge_path("lab_markers.json").read_text(encoding="utf-8"))["markers"]

    def test_a_marker_in_a_panel_declares_its_sex_dependence(self):
        silent = []
        for k in panel_markers():
            e = self.cat.get(k)
            self.assertIsNotNone(e, f"{k} is scored by the radar and is not in the dictionary")
            if not e.get("ref_by_sex") and not e.get("ref_sex"):
                silent.append(k)
        self.assertEqual(silent, [],
                         "these markers are scored, hold one corridor, and do not say whose: "
                         + ", ".join(silent))

    def test_the_declaration_is_one_of_three_words(self):
        for k, e in self.cat.items():
            if "ref_sex" in e:
                with self.subTest(marker=k):
                    self.assertIn(e["ref_sex"], ALLOWED)

    def test_a_marker_that_holds_both_corridors_does_not_also_declare_one(self):
        """`ref_by_sex` has already answered. A second answer beside it is a place
        for the two to disagree."""
        for k, e in self.cat.items():
            if e.get("ref_by_sex"):
                with self.subTest(marker=k):
                    self.assertNotIn("ref_sex", e)


class TestTheCorridorIsNotLentAcrossThatBoundary(unittest.TestCase):
    """Built rather than found: the test profile prints its own ranges, as a real
    laboratory form does, and a borrow never happens on it."""

    def one(self, key, sex, value=45.0):
        with mock.patch.object(core, "labs", lambda: {"markers": {key: {
                "name": key.upper(), "unit": "U/L",
                "series": [{"date": "2026-06", "value": value}]}}}), \
             mock.patch.object(core, "profile_sex", lambda: sex):
            for m in labs.analyze_labs()["markers"]:
                if m["key"] == key:
                    return m
        self.fail(f"{key} did not reach the marker list at all")

    def test_a_womans_ggt_is_not_judged_against_a_mans_ceiling(self):
        m = self.one("ggt", "female")
        self.assertIsNone(m["ref_high"], "a man's ceiling was lent to a woman")
        self.assertEqual(m["flag"], "norange")
        self.assertFalse(m["abnormal"])
        self.assertTrue(m["ref_sex_other"], "the reason must be printable, not merely absent")

    def test_a_mans_ggt_still_gets_the_corridor_that_is_his(self):
        m = self.one("ggt", "male")
        self.assertEqual(m["ref_high"], 60)
        self.assertFalse(m.get("ref_sex_other"))

    def test_a_profile_with_no_sex_is_refused_the_same_way(self):
        m = self.one("ggt", None)
        self.assertIsNone(m["ref_high"])

    def test_a_sex_neutral_corridor_is_lent_to_everybody(self):
        """The refusal must not spread: most corridors do not depend on sex, and
        withholding those would cost every reader a verdict they are owed."""
        for sex in ("male", "female", None):
            with self.subTest(sex=sex):
                m = self.one("tsh", sex, value=2.0)
                self.assertEqual(m["ref_high"], 4.2)
                self.assertEqual(m["flag"], "ok")


if __name__ == "__main__":
    unittest.main()
