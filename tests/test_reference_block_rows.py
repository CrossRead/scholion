"""Choosing the right row of a multi-line reference block.

Tasks 65, 66, 73. A lab prints the corridor as a block under the result —
newborns, children, Tanner stages, women, trimesters, age bands, «by default» —
and the parser used to take the FIRST row that passed a flat filter. That is how
a man of 41 was measured against Tanner stage I (a nineteen-fold false
exceedance on a normal testosterone) and a woman who is not pregnant was measured
against the second-trimester fibrinogen range.

Two rules are held here, and the second matters more than the first:

  · the row that applies is chosen, not the row that comes first;
  · when MORE THAN ONE row applies, the point keeps no corridor at all.

The second is the project's own rule — ambiguity is answered with silence, not
with a plausible pick — and it is the one a test has to hold, because a wrong
corridor looks exactly like a right one on screen.

The fixtures are modelled on real Russian lab layouts (Gemotest, Helix, CMD,
Invitro); no patient's form is reproduced.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest

import support  # noqa: F401
from scholion import core, ingest_labs

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures" / "refblocks"

#: file → (marker, value, expected low, expected high). None/None means «no
#: corridor», which for these forms is the correct answer and not a shortfall.
EXPECTED = {
    "01_tanner_stages.txt":        ("testosterone", 18.5, 8.64, 29.0),
    "02_tanner_bare_roman.txt":    ("testosterone", 18.5, 8.64, 29.0),
    "03_trimester_under_women.txt": ("fibrinogen", 3.1, 2.0, 3.93),
    "04_two_rows_fit.txt":         ("testosterone", 18.5, None, None),
    "05_age_bands.txt":            ("alp", 95.0, 40.0, 129.0),
}


class TestTheApplicableRowIsChosen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = cls.tmp
        (pathlib.Path(cls.tmp) / "metrics.json").write_text(
            json.dumps({"profile": {"sex": "male", "birth_year": 1985}}))
        core.reset_cache()
        cls.markers = core.lab_markers()["markers"]

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        core.reset_cache()

    def test_every_fixture_picks_the_row_that_applies(self):
        for name, (key, value, lo, hi) in EXPECTED.items():
            with self.subTest(form=name):
                text = (FIXTURES / name).read_text(encoding="utf-8")
                _date, found = ingest_labs.parse_report(text, self.markers, source=name)
                self.assertIn(key, found, f"{name}: the marker was not recognised at all")
                got = found[key]
                self.assertEqual(got["value"], value)
                self.assertEqual((got["ref_low"], got["ref_high"]), (lo, hi))

    def test_a_pubertal_stage_is_never_used_for_an_adult(self):
        """The exact shape of task 65: 0.98 is the top of Tanner stage I."""
        for name in ("01_tanner_stages.txt", "02_tanner_bare_roman.txt"):
            with self.subTest(form=name):
                text = (FIXTURES / name).read_text(encoding="utf-8")
                _d, found = ingest_labs.parse_report(text, self.markers, source=name)
                self.assertNotEqual(found["testosterone"]["ref_high"], 0.98)

    def test_a_trimester_row_is_never_used(self):
        """Task 66: no profile carries a pregnancy status, so no trimester row can
        ever be the applicable one — including a row that sits under a «Женщины»
        heading and does not repeat the word itself."""
        text = (FIXTURES / "03_trimester_under_women.txt").read_text(encoding="utf-8")
        _d, found = ingest_labs.parse_report(text, self.markers, source="x")
        self.assertNotIn(found["fibrinogen"]["ref_high"], (5.42, 6.4, 6.9))

    def test_ambiguity_is_answered_with_silence(self):
        text = (FIXTURES / "04_two_rows_fit.txt").read_text(encoding="utf-8")
        _d, found = ingest_labs.parse_report(text, self.markers, source="x")
        self.assertIsNone(found["testosterone"]["ref_low"])
        self.assertIsNone(found["testosterone"]["ref_high"])

    def test_the_library_covers_more_than_one_shape(self):
        """A single easy fixture would pass a change that broke the rest."""
        self.assertGreaterEqual(len(list(FIXTURES.glob("*.txt"))), 5)


class TestAnAgeBandedRowSurvivesAnUnknownAge(unittest.TestCase):
    """GitHub issue #1, filed against 0.4.3: `_row_fits()` compared age to a
    band/over/under bound without checking `age is not None` first, so a
    profile with no birth year on file (an ordinary, supported state — `init`
    itself warns and proceeds) crashed the WHOLE ingest-labs batch on the
    first form carrying an age-banded reference row, not just that one file.

    `_owner()`'s own docstring already promised the right behaviour — "No
    profile / no birth date -> (None, None), the logic is off" — `_row_fits()`
    just did not honour it. Age unknown is not the same claim as age fits:
    an age-banded row can be neither confirmed nor excluded, so — same as a
    row that fits more than one candidate — the project's own rule holds:
    ambiguity is answered with silence, not a crash and not a guess.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = cls.tmp
        # Sex recorded, birth year not — exactly `scholion init` without
        # `--birth-year`, which the CLI allows and warns about rather than
        # refuses (task 72).
        (pathlib.Path(cls.tmp) / "metrics.json").write_text(
            json.dumps({"profile": {"sex": "male"}}))
        core.reset_cache()
        cls.markers = core.lab_markers()["markers"]

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        core.reset_cache()

    def test_an_age_banded_form_does_not_raise(self):
        text = (FIXTURES / "05_age_bands.txt").read_text(encoding="utf-8")
        try:
            _d, found = ingest_labs.parse_report(text, self.markers, source="x")
        except TypeError as e:
            self.fail(f"parse_report raised on an age-banded row with no "
                      f"birth year recorded: {e}")
        self.assertIn("alp", found, "the marker itself must still be read — "
                       "only the AGE-BASED row choice is meant to be off")

    def test_it_does_not_guess_which_band_applies(self):
        """Three rows (children / teens / adults) all count as fitting when age
        logic is off, so — per the block's own ambiguity rule — none is picked."""
        text = (FIXTURES / "05_age_bands.txt").read_text(encoding="utf-8")
        _d, found = ingest_labs.parse_report(text, self.markers, source="x")
        self.assertIsNone(found["alp"]["ref_low"])
        self.assertIsNone(found["alp"]["ref_high"])

    def test_sex_filtering_still_applies_with_age_unknown(self):
        """Age off is not a general bypass — `_row_fits` still enforces sex,
        which does not depend on the owner's age being known."""
        from scholion.ingest_labs import _row_fits
        self.assertFalse(_row_fits("Женщины: 10 - 20", "male", None))
        self.assertTrue(_row_fits("Мужчины: 10 - 20", "male", None))


if __name__ == "__main__":
    unittest.main()
