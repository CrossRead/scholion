"""A number the watch already has is not a number the person failed to enter.

Some of these quantities are kept twice: metrics.json is what somebody typed in,
and the wearables file is what a device recorded every day. Only the first was
read. On the owner's profile that produced three statements about him that were
false in the ordinary sense — «steps 6000, below the target» from one point
entered in July, while the device series held 8356 for August; «sleep —», while
the same file carried seventy-five months of it; a resting heart rate from
December standing as current in September.

The join is a pairing that has to be asserted, not inferred: `person_metric` in
the shipped wearable catalogue names the row of metrics.json measuring THE SAME
quantity. Where two things are merely similar the field is absent and the row
keeps saying it has nothing behind it — Garmin's intensity minutes are not
«minutes of activity», and a pairing that is nearly true prints a number nobody
can act on.
"""
from __future__ import annotations

import copy
import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import core
from scholion.engine import profile_view as pv


CAT = {"metrics": {
    "Weight": {"label": "Weight", "unit": "kg", "person_metric": "weight"},
    "StepsDaily": {"label": "Steps", "unit": "steps", "person_metric": "steps"},
    "Stress": {"label": "Stress", "unit": ""},
}}


def wear(months, device="garmin"):
    return {"_meta": {"shape": "x"},
            "sources": {device: {"_meta": {}, "metrics": months, "workouts": {}}}}


def person(series_by_key):
    return {"profile": {"sex": "male", "birth_year": 1980, "height_cm": 180},
            "metrics": {k: {"name": k, "unit": "u", "ref_low": 8000 if k == "steps" else None,
                            "series": v}
                        for k, v in series_by_key.items()}}


def rows(metrics_json, trends):
    with mock.patch.object(pv.core, "metrics_json", return_value=metrics_json), \
         mock.patch.object(pv.core, "wearable_metrics", return_value=CAT), \
         mock.patch.object(pv.core, "wearable_trends", return_value=trends):
        return {r["key"]: r for r in pv.metrics_summary()["metrics"]}


class TestTheDeviceFillsWhatNobodyTypedIn(unittest.TestCase):

    def test_a_metric_with_no_hand_entered_points_shows_the_device(self):
        r = rows(person({"steps": []}), wear({"StepsDaily": {"2026-08": 8356}}))["steps"]
        self.assertEqual((r["value"], r["date"], r["origin"]), (8356.0, "2026-08", "device"))
        self.assertEqual(r["device"]["source"], "garmin")

    def test_the_flag_is_judged_on_the_number_that_is_shown(self):
        """The defect in one line: 6000 entered in July was «below the target»
        while the device had 8356 for August."""
        old = rows(person({"steps": [{"date": "2026-07-11", "value": 6000}]}), {})["steps"]
        new = rows(person({"steps": [{"date": "2026-07-11", "value": 6000}]}),
                   wear({"StepsDaily": {"2026-08": 8356}}))["steps"]
        self.assertEqual(old["flag"], "low")
        self.assertEqual(new["flag"], "ok")

    def test_the_series_under_the_number_is_the_series_it_came_from(self):
        """A card showing the device's August above a sparkline of hand-entered
        points would draw one line and label it with another."""
        r = rows(person({"steps": [{"date": "2026-07-11", "value": 6000}]}),
                 wear({"StepsDaily": {"2026-07": 8000, "2026-08": 8356}}))["steps"]
        self.assertEqual([p["date"] for p in r["series"]], ["2026-07", "2026-08"])

    def test_a_newer_hand_entered_reading_wins(self):
        r = rows(person({"weight": [{"date": "2026-08-25", "value": 99.8}]}),
                 wear({"Weight": {"2026-07": 100.5}}))["weight"]
        self.assertEqual((r["value"], r["origin"]), (99.8, "manual"))

    def test_the_same_month_goes_to_the_person(self):
        """A monthly mean and a reading taken on a day are not the same statement,
        and the person made the second on purpose."""
        r = rows(person({"weight": [{"date": "2026-07-30", "value": 99.8}]}),
                 wear({"Weight": {"2026-07": 100.5}}))["weight"]
        self.assertEqual((r["value"], r["origin"]), (99.8, "manual"))

    def test_the_other_store_is_kept_beside_the_number_either_way(self):
        r = rows(person({"weight": [{"date": "2026-08-25", "value": 99.8}]}),
                 wear({"Weight": {"2026-07": 100.5}}))["weight"]
        self.assertEqual(r["device"]["value"], 100.5)
        self.assertEqual(r["manual"]["value"], 99.8)

    def test_an_unpaired_metric_is_left_alone(self):
        """`Stress` declares no person metric, so nothing of it reaches a row."""
        r = rows(person({"steps": [], "waist_cm": []}),
                 wear({"Stress": {"2026-08": 30}}))["waist_cm"]
        self.assertIsNone(r["value"])
        self.assertIsNone(r["device"])
        self.assertEqual(r["flag"], "unknown")

    def test_two_watches_are_not_joined(self):
        two = {"_meta": {}, "sources": {
            "garmin": {"metrics": {"StepsDaily": {"2026-08": 8356}}},
            "whoop": {"metrics": {"StepsDaily": {"2026-08": 9100}}}}}
        r = rows(person({"steps": []}), two)["steps"]
        self.assertIsNone(r["device"], "one of the two devices was picked silently")
        self.assertIsNone(r["value"])

    def test_the_body_mass_index_follows_the_weight_that_is_shown(self):
        with mock.patch.object(pv.core, "metrics_json", return_value=person({"weight": []})), \
             mock.patch.object(pv.core, "wearable_metrics", return_value=CAT), \
             mock.patch.object(pv.core, "wearable_trends",
                               return_value=wear({"Weight": {"2026-08": 97.2}})):
            bmi = pv.metrics_summary()["bmi"]
        self.assertEqual(bmi["value"], 30.0)   # 97.2 / 1.80²

    def test_neither_file_is_written(self):
        """This is a view. The person's file is theirs, and a rebuild of the export
        overwrites the other one."""
        pj = person({"steps": []})
        before = copy.deepcopy(pj)
        rows(pj, wear({"StepsDaily": {"2026-08": 8356}}))
        self.assertEqual(pj, before)


class TestThePairingIsCurated(unittest.TestCase):

    def cat(self):
        return (core.wearable_metrics().get("metrics") or {})

    def test_the_catalogue_declares_some_pairings_at_all(self):
        pairs = {k: v.get("person_metric") for k, v in self.cat().items()
                 if (v or {}).get("person_metric")}
        self.assertGreaterEqual(len(pairs), 3, pairs)

    def test_no_person_metric_is_claimed_by_two_devices_metrics(self):
        seen = {}
        for name, spec in self.cat().items():
            key = (spec or {}).get("person_metric")
            if key:
                seen.setdefault(key, []).append(name)
        doubled = {k: v for k, v in seen.items() if len(v) > 1}
        self.assertEqual({}, doubled, "two device metrics claim to be the same quantity")

    def test_a_pairing_names_a_metric_the_catalogue_carries(self):
        for name, spec in self.cat().items():
            if (spec or {}).get("person_metric"):
                with self.subTest(metric=name):
                    self.assertIn("unit", spec, f"{name} is paired but not described")


if __name__ == "__main__":
    unittest.main()
