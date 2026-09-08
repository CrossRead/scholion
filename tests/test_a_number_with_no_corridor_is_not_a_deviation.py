"""A number with no corridor beside it is not a deviation of unknown size.

`_marker_health` scored every marker that was not «ok». A marker with no reference
interval is not «ok» — saying so would be a claim about a number nobody has
anything to compare with — so it scored 55 out of 100, the score meaning «there is
a deviation whose size cannot be assessed». There is no deviation. The system lost
45 points to a number that said nothing, and the same marker appeared in that
system's list of deviations while the marker list on the same screen said it was
not one: two layers of the same program disagreeing about the same fact.

This is about the radar only. What a marker without bounds looks like on the
marker list is `test_safety_rules.py`'s subject and has always been right.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

import importlib
lifestyle = importlib.import_module("scholion.engine.lifestyle")


def lab(key, name, flag, value, ref_low=1.0, ref_high=5.0):
    """One row of `analyze_labs`, as the radar reads it."""
    return {"key": key, "name": name, "unit": "U/L", "value": value, "date": "2026-06",
            "flag": flag, "abnormal": flag not in ("ok", "norange", "unconfirmed_rule"),
            "ref_low": ref_low, "ref_high": ref_high, "note": None, "genome_link": None}


def marker(flag, **kw):
    m = {"flag": flag, "value": 10.0, "ref_low": 1.0, "ref_high": 5.0,
         "abnormal": flag not in ("ok", "norange", "unconfirmed_rule")}
    m.update(kw)
    return m


class TestAMarkerWithNothingToCompareAgainstIsNotScored(unittest.TestCase):

    def test_a_marker_without_a_corridor_has_no_score(self):
        self.assertIsNone(lifestyle._marker_health(
            marker("norange", ref_low=None, ref_high=None)))

    def test_a_marker_read_by_an_unconfirmed_rule_has_no_score(self):
        self.assertIsNone(lifestyle._marker_health(marker("unconfirmed_rule")))

    def test_a_marker_inside_its_corridor_still_scores_full(self):
        self.assertEqual(lifestyle._marker_health(marker("ok", value=3.0)), 100)

    def test_a_deviation_is_still_graded_by_its_size(self):
        mild = lifestyle._marker_health(marker("high", value=5.5))
        severe = lifestyle._marker_health(marker("high", value=25.0))
        self.assertGreater(mild, severe)
        self.assertLess(mild, 100)

    def test_a_deviation_whose_size_is_unknown_still_scores_55(self):
        """The 55 was not wrong — it was applied to the wrong thing. A marker that
        IS out of range with an unusable bound keeps it."""
        self.assertEqual(lifestyle._marker_health(
            marker("high", ref_high=None)), 55)


class TestTheRadarAndTheMarkerListAgree(unittest.TestCase):
    """Built rather than found.

    The obvious form of this test — run the radar on the test profile and check
    that nothing it calls a deviation is denied by the marker list — passes
    whether or not the defect is present, because that profile happens to contain
    no marker without a corridor inside a radar panel. A guard that cannot fail is
    worse than no guard: it reports safety it never checked. So the situation is
    constructed, and the marker list is the one the domain is assembled from.
    """

    def radar_with(self, markers):
        with mock.patch.object(lifestyle, "analyze_labs",
                               lambda: {"markers": markers}):
            return {d["key"]: d for d in lifestyle.health_radar()["domains"]}

    def test_a_marker_with_no_corridor_is_not_one_of_the_domains_deviations(self):
        d = self.radar_with([lab("alt", "ALT", "ok", 20),
                             lab("ast", "AST", "norange", 31, ref_low=None, ref_high=None),
                             lab("ggt", "GGT", "high", 90)])["liver"]
        self.assertEqual([a["key"] for a in d["abnormal"]], ["ggt"],
                         "the radar counted a number nobody has anything to compare "
                         "with among this system's deviations")
        self.assertEqual(d["ok"], 1, "«in range» must not include «no range»")

    def test_a_marker_with_no_corridor_does_not_lower_the_score(self):
        two = self.radar_with([lab("alt", "ALT", "ok", 20),
                               lab("ast", "AST", "ok", 25)])["liver"]
        three = self.radar_with([lab("alt", "ALT", "ok", 20),
                                 lab("ast", "AST", "ok", 25),
                                 lab("ggt", "GGT", "norange", 44,
                                     ref_low=None, ref_high=None)])["liver"]
        self.assertEqual(two["score"], 100)
        self.assertEqual(three["score"], 100,
                         "a third number with no corridor took points off a system "
                         "whose two answerable markers were both in range")
        self.assertEqual(three["measured"], 3,
                         "it says nothing, but it was measured and the ring must show it")

    def test_a_system_whose_every_marker_is_silent_has_no_score(self):
        d = self.radar_with([lab("alt", "ALT", "norange", 20, ref_low=None, ref_high=None),
                             lab("ast", "AST", "norange", 25, ref_low=None, ref_high=None)])["liver"]
        self.assertIsNone(d["score"], "three numbers that say nothing do not average "
                                      "into a middling verdict")
        self.assertEqual(d["status"], "nodata")
        self.assertEqual(d["measured"], 2, "«not taken» and «taken and says nothing» are "
                                           "different facts and the ring shows the difference")
        self.assertEqual(d["missing"], ["ggt"])


if __name__ == "__main__":
    unittest.main()
