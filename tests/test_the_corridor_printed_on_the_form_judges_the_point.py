"""The corridor printed on the form is the one the point is judged by — and when
the corridor changed between draws, the flags say they are not comparable.

Task 142. The rule «the range on the person's own form wins» held on the write
path only at the level of the marker, which keeps the first range it met and
is not rewritten by later forms; no point carried its own. An ionised calcium
of 1.09 was then judged against a range recorded months earlier (1.16–1.32)
and read as deeply low, while the form that carried it printed 1.10–1.35 and called it a
hair under. The corridor now travels with the point, the verdict stands on it,
the report says whose corridor it stands on, and a series whose corridor moved
says that its flags did not all measure with one ruler.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, store
from scholion import format as fmt
from scholion.engine import labs


def _one(key, series, marker_ref=None, sex="male"):
    marker = {"name": key.upper(), "unit": "mmol/L", "series": series}
    if marker_ref:
        marker.update(marker_ref)
    with mock.patch.object(core, "labs", lambda: {"markers": {key: marker}}), \
         mock.patch.object(core, "profile_sex", lambda: sex), \
         mock.patch.object(core, "profile_age", lambda: 45):
        for m in labs.analyze_labs()["markers"]:
            if m["key"] == key:
                return m
    raise AssertionError(f"{key} did not reach the marker list")


class TestTheStoreKeepsTheCorridorWithThePoint(unittest.TestCase):

    def test_a_point_carries_the_range_its_form_printed(self):
        with tempfile.TemporaryDirectory() as d:
            unpin = support.pin_profile(Path(d))
            core.reset_cache()
            try:
                r1 = store.add_lab_point("ferritin", "2025-12-10", 120.0, ref_low=30.0, ref_high=400.0,
                                         unit="ug/L", date_source="form", subject="owner")
                r2 = store.add_lab_point("ferritin", "2026-09-03T08:22", 109.0, ref_low=20.0, ref_high=250.0,
                                         unit="ug/L", date_source="form", subject="owner")
                self.assertTrue(r1.get("ok") and r2.get("ok"), (r1, r2))
                data = json.loads((Path(d) / "labs.json").read_text(encoding="utf-8"))
            finally:
                unpin()
                core.reset_cache()
        pts = {p["date"]: p for p in data["markers"]["ferritin"]["series"]}
        self.assertEqual((30.0, 400.0), (pts["2025-12-10"]["ref_low"], pts["2025-12-10"]["ref_high"]))
        self.assertEqual((20.0, 250.0), (pts["2026-09-03T08:22"]["ref_low"], pts["2026-09-03T08:22"]["ref_high"]))
        # The marker-level range keeps the FIRST form it met and is not rewritten
        # by later ones — which is exactly why a point needs its own.
        self.assertEqual(30.0, data["markers"]["ferritin"]["ref_low"])

    def test_a_reimport_that_printed_no_range_is_not_lent_the_old_forms(self):
        with tempfile.TemporaryDirectory() as d:
            unpin = support.pin_profile(Path(d))
            core.reset_cache()
            try:
                r1 = store.add_lab_point("ferritin", "2026-09-03", 120.0, ref_low=30.0, ref_high=400.0,
                                         unit="ug/L", date_source="form", subject="owner")
                r2 = store.add_lab_point("ferritin", "2026-09-03T08:22", 120.0,
                                         unit="ug/L", date_source="form", subject="owner")
                self.assertTrue(r1.get("ok") and r2.get("ok"), (r1, r2))
                data = json.loads((Path(d) / "labs.json").read_text(encoding="utf-8"))
            finally:
                unpin()
                core.reset_cache()
        (pt,) = data["markers"]["ferritin"]["series"]
        self.assertEqual("2026-09-03T08:22", pt["date"])
        self.assertNotIn("ref_low", pt, "a form that printed no range was shown as having printed the previous one")


class TestTheVerdictStandsOnTheDrawsOwnCorridor(unittest.TestCase):

    def test_the_forms_range_beats_the_markers_recorded_one(self):
        m = _one("calcium_ionized",
                 [{"date": "2026-09-03", "value": 1.12, "ref_low": 1.10, "ref_high": 1.35}],
                 marker_ref={"ref_low": 1.16, "ref_high": 1.32})
        self.assertEqual("ok", m["flag"], "judged against a range this draw's form did not print")
        self.assertEqual((1.10, 1.35), (m["ref_low"], m["ref_high"]))
        self.assertEqual("form", m["ref_origin"])

    def test_without_its_own_range_the_markers_recorded_one_answers_and_says_so(self):
        m = _one("calcium_ionized", [{"date": "2026-09-03", "value": 1.12}],
                 marker_ref={"ref_low": 1.16, "ref_high": 1.32})
        self.assertEqual("low", m["flag"])
        self.assertEqual("profile", m["ref_origin"])

    def test_the_reference_base_is_named_as_the_weakest_ruler(self):
        m = _one("alp", [{"date": "2026-09-03", "value": 258.0}])
        self.assertTrue(m["ref_reference_base"])
        self.assertEqual("reference_base", m["ref_origin"])


class TestASeriesWhoseCorridorMovedSaysSo(unittest.TestCase):

    def test_two_corridors_make_the_flags_incomparable_and_the_note_names_both(self):
        m = _one("calcium_ionized",
                 [{"date": "2025-12-10", "value": 1.20, "ref_low": 1.16, "ref_high": 1.32},
                  {"date": "2026-09-03", "value": 1.12, "ref_low": 1.10, "ref_high": 1.35}])
        self.assertFalse(m["flags_comparable"])
        self.assertIn("1.16", m["corridor_note"])
        self.assertIn("1.35", m["corridor_note"])

    def test_one_corridor_is_comparable_and_carries_no_note(self):
        m = _one("calcium_ionized",
                 [{"date": "2025-12-10", "value": 1.20, "ref_low": 1.10, "ref_high": 1.35},
                  {"date": "2026-09-03", "value": 1.12, "ref_low": 1.10, "ref_high": 1.35}])
        self.assertTrue(m["flags_comparable"])
        self.assertIsNone(m["corridor_note"])


class TestTheReportSaysWhoseCorridorItPrints(unittest.TestCase):

    def test_a_recorded_range_is_marked_and_a_forms_range_is_not(self):
        own = fmt._fmt_ref({"ref_low": 1.10, "ref_high": 1.35, "ref_origin": "form"})
        recorded = fmt._fmt_ref({"ref_low": 1.16, "ref_high": 1.32, "ref_origin": "profile"})
        self.assertIn("1.1", own)
        self.assertNotIn("recorded", own)
        self.assertIn("recorded", recorded)

    def test_the_labs_report_prints_the_comparability_note(self):
        m = _one("calcium_ionized",
                 [{"date": "2025-12-10", "value": 1.20, "ref_low": 1.16, "ref_high": 1.32},
                  {"date": "2026-09-03", "value": 1.12, "ref_low": 1.10, "ref_high": 1.35}])
        with mock.patch.object(core, "labs", lambda: {"markers": {"calcium_ionized": {
                "name": "CA", "unit": "mmol/L",
                "series": [{"date": "2025-12-10", "value": 1.20, "ref_low": 1.16, "ref_high": 1.32},
                           {"date": "2026-09-03", "value": 1.12, "ref_low": 1.10, "ref_high": 1.35}]}}}), \
             mock.patch.object(core, "profile_sex", lambda: "male"), \
             mock.patch.object(core, "profile_age", lambda: 45):
            text = fmt.labs_report(labs.analyze_labs())
        self.assertIn(m["corridor_note"], text)


if __name__ == "__main__":
    unittest.main()
