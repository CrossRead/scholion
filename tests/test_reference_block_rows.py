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


if __name__ == "__main__":
    unittest.main()
