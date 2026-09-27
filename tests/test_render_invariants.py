"""Two rules of the rendering layer that live in comments — held by a test.

An external review of `format.py` (25.09.2026) pointed out that the most
valuable decisions in the file are written down only as comments beside the
code, and that a module split — which is coming — is exactly when a comment
gets left behind and the behaviour «fixed» into its opposite:

1. A value with no corridor gets a neutral mark, never a colour. Every colour on
   the scale is a verdict; a green tick beside a number that has nothing to be
   judged against reads as «this is fine», a sentence about a person made from
   the absence of data.
2. What the interaction comparison left out is printed whether or not anything
   was found. A warning that vanished because a drug was stopped and a warning
   nobody computed look the same on the page, and only one is good news.

The tests go through the public rendering functions, so they survive the move
of the helpers into other modules.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  (puts src/ on the path)
from scholion import format as fmt

VERDICT_COLOURS = {"🔴", "🟠", "🟢", "🟡"}


class TestNoCorridorIsNoVerdict(unittest.TestCase):

    def test_a_value_with_no_corridor_is_not_coloured(self):
        for flag in ("norange", "unconfirmed_rule"):
            with self.subTest(flag=flag):
                icon = fmt._mark_icon({"flag": flag})
                self.assertNotIn(icon, VERDICT_COLOURS)

    def test_even_near_an_edge_that_does_not_exist(self):
        """`near_limit` without a corridor cannot turn into the yellow mark."""
        self.assertNotIn(fmt._mark_icon({"flag": "norange", "near_limit": True}), VERDICT_COLOURS)

    def test_an_unknown_flag_is_not_coloured_either(self):
        self.assertNotIn(fmt._mark_icon({"flag": "something_new"}), VERDICT_COLOURS)

    def test_the_neutral_mark_is_not_one_of_the_verdicts(self):
        self.assertNotIn(fmt._NORANGE_ICON, VERDICT_COLOURS)
        self.assertNotIn(fmt._NORANGE_ICON, set(fmt._FLAG_ICON.values()))


class TestWhatWasLeftOutIsAlwaysSaid(unittest.TestCase):

    def _card(self, interactions):
        return fmt.prescription_check({"status": "ok", "drug": "X", "overall": "low",
                                       "interactions": interactions})

    def test_a_stopped_drug_is_named_when_nothing_was_found(self):
        text = self._card({"status": "ok", "interactions": [],
                           "baseline": {"excluded": [{"name": "Omeprazole", "status": "stopped"}]}})
        self.assertIn("Omeprazole (stopped)", text)

    def test_a_stopped_drug_is_named_when_something_was_found_too(self):
        text = self._card({"status": "ok",
                           "interactions": [{"severity": "moderate", "with_meds": ["Warfarin"],
                                             "effect": "e", "mechanism": "m", "manage": "x"}],
                           "baseline": {"excluded": [{"name": "Omeprazole", "status": "stopped"}]}})
        self.assertIn("Omeprazole (stopped)", text)

    def test_a_drug_with_no_status_is_named(self):
        text = self._card({"status": "ok", "interactions": [],
                           "baseline": {"status_not_recorded": ["Aspirin"]}})
        self.assertIn("Aspirin", text)


if __name__ == "__main__":
    unittest.main()
