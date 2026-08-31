"""A decision a person made about a series survives the next rebuild.

`ingest-garmin` and `ingest-wearable` rebuild a device's block from the export.
The merge underneath them protects history the export does not carry — an
incomplete download cannot erase months. What nothing protected was the opposite
case: a month the export DOES carry, about which a person had already decided
something.

The case that produced this was a weight point removed by hand because it was
physically impossible between the two months around it. The next export still
carried that month, so the rebuild put it back, and it was removed a second time.
An edit that cannot survive a rebuild is lost at every refresh, and no journal
replaces it — the file being edited is the one the build overwrites.

So the decision moves out of the artefact and into `wearable_corrections.local.json`
beside it, the same shape of overlay the metric dictionary already uses. What is
asserted here is the whole of that contract: a correction is applied, it survives,
it must give a reason to be accepted at all, it is reported when it stops matching
anything, and it never reaches another device's block.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, format as fmt, wearables

#: The shape the reader hands back: months against values, per metric. The point
#: at the centre of this is `weight_kg 2024-10` — the impossible one.
FRESH = {
    "ok": True,
    "_meta": {"range": "2024-08–2024-12"},
    "metrics": {
        "weight_kg": {"2024-08": 91.7, "2024-09": 92.4, "2024-10": 72.2,
                      "2024-11": 95.3, "2024-12": 94.8},
        "resting_hr": {"2024-10": 58, "2024-11": 57},
    },
}


@contextmanager
def profile_and_export():
    """A temporary profile, and a folder the detector accepts as a Garmin export."""
    tmp = Path(tempfile.mkdtemp(prefix="wear-corr-")).resolve()
    (tmp / "profile").mkdir()
    (tmp / "export" / "DI_CONNECT").mkdir(parents=True)
    old = {k: os.environ.get(k) for k in
           ("SCHOLION_PROFILE_DIR", "SCHOLION_CACHE_DIR", "SCHOLION_REPO_DIR")}
    os.environ["SCHOLION_PROFILE_DIR"] = str(tmp / "profile")
    os.environ["SCHOLION_CACHE_DIR"] = str(tmp / "cache")
    os.environ["SCHOLION_REPO_DIR"] = str(tmp)
    core.reset_cache()

    def build(path):
        return json.loads(json.dumps(FRESH))

    with mock.patch.object(wearables, "_builder",
                           return_value=SimpleNamespace(build=build)):
        try:
            yield tmp
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            core.reset_cache()
            shutil.rmtree(tmp, ignore_errors=True)


def write_corrections(tmp, items):
    (tmp / "profile" / wearables.CORRECTIONS).write_text(
        json.dumps({"corrections": items}, ensure_ascii=False), encoding="utf-8")


def rebuild(tmp):
    return wearables.reingest(str(tmp / "export"), source="garmin")


def series_of(tmp, metric="weight_kg"):
    data = json.loads((tmp / "profile" / "wearable_trends.json").read_text(encoding="utf-8"))
    return ((data.get("sources") or {}).get("garmin") or {}).get("metrics", {}).get(metric, {})


class TestTheRebuildWouldOtherwiseBringItBack(unittest.TestCase):

    def test_without_a_correction_the_point_is_there(self):
        """The premise of everything below. If the fresh build did not carry the
        month, the corrections layer would be protecting nothing and every test
        here would pass for the wrong reason."""
        with profile_and_export() as tmp:
            r = rebuild(tmp)
            self.assertTrue(r["ok"], r.get("error"))
            self.assertEqual(series_of(tmp).get("2024-10"), 72.2)

    def test_a_removal_survives_the_rebuild(self):
        with profile_and_export() as tmp:
            rebuild(tmp)
            write_corrections(tmp, [
                {"device": "garmin", "metric": "weight_kg", "month": "2024-10",
                 "action": "remove", "why": "impossible between 91.7 and 95.3",
                 "on": "2026-08-22"}])
            r = rebuild(tmp)
            self.assertNotIn("2024-10", series_of(tmp))
            self.assertEqual(len(r["corrections_applied"]), 1)

    def test_it_survives_a_second_rebuild_too(self):
        """Once is luck. The point of a layer is that it holds every time."""
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "garmin", "metric": "weight_kg", "month": "2024-10",
                 "action": "remove", "why": "impossible"}])
            rebuild(tmp)
            rebuild(tmp)
            self.assertNotIn("2024-10", series_of(tmp))

    def test_a_replacement_survives_the_rebuild(self):
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "garmin", "metric": "weight_kg", "month": "2024-10",
                 "action": "replace", "value": 93.1, "why": "read off the scale photo"}])
            rebuild(tmp)
            self.assertEqual(series_of(tmp)["2024-10"], 93.1)

    def test_the_months_around_it_are_untouched(self):
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "garmin", "metric": "weight_kg", "month": "2024-10",
                 "action": "remove", "why": "impossible"}])
            rebuild(tmp)
            s = series_of(tmp)
            self.assertEqual(s["2024-09"], 92.4)
            self.assertEqual(s["2024-11"], 95.3)
            self.assertEqual(series_of(tmp, "resting_hr")["2024-10"], 58)


class TestACorrectionAnswersForItself(unittest.TestCase):

    def test_a_correction_without_a_reason_is_refused_and_changes_nothing(self):
        """The rule the project applies to every other change to a record: a
        change nobody can account for is one nobody can review later."""
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "garmin", "metric": "weight_kg", "month": "2024-10",
                 "action": "remove"}])
            r = rebuild(tmp)
            self.assertEqual(series_of(tmp)["2024-10"], 72.2)
            self.assertEqual([c["refused"] for c in r["corrections_refused"]],
                             ["no_reason_given"])

    def test_an_unknown_verb_is_refused_by_name(self):
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "garmin", "metric": "weight_kg", "month": "2024-10",
                 "action": "adjust", "why": "because"}])
            r = rebuild(tmp)
            self.assertEqual(series_of(tmp)["2024-10"], 72.2)
            self.assertEqual([c["refused"] for c in r["corrections_refused"]],
                             ["unknown_action"])

    def test_a_replacement_without_a_value_is_refused(self):
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "garmin", "metric": "weight_kg", "month": "2024-10",
                 "action": "replace", "why": "wrong"}])
            r = rebuild(tmp)
            self.assertEqual(series_of(tmp)["2024-10"], 72.2)
            self.assertEqual([c["refused"] for c in r["corrections_refused"]],
                             ["no_value_to_replace_with"])

    def test_a_correction_that_matches_nothing_is_named_not_ignored(self):
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "garmin", "metric": "weight_kg", "month": "2019-01",
                 "action": "remove", "why": "an old decision the export no longer carries"}])
            r = rebuild(tmp)
            self.assertEqual(len(r["corrections_stale"]), 1)
            self.assertEqual(r["corrections_stale"][0]["month"], "2019-01")

    def test_a_correction_for_another_device_is_left_alone(self):
        """This rebuild rebuilt one block. A decision about the other one is
        neither applied nor invalidated by it — reporting it as stale here would
        invite deleting a correction that is perfectly good."""
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "whoop", "metric": "weight_kg", "month": "2024-10",
                 "action": "remove", "why": "belongs to the other watch"}])
            r = rebuild(tmp)
            self.assertEqual(series_of(tmp)["2024-10"], 72.2)
            self.assertEqual(r["corrections_applied"], [])
            self.assertEqual(r["corrections_stale"], [])
            self.assertEqual(r["corrections_refused"], [])


class TestTheReportSaysSo(unittest.TestCase):

    def test_what_was_applied_refused_and_stale_all_reach_the_reader(self):
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "garmin", "metric": "weight_kg", "month": "2024-10",
                 "action": "remove", "why": "impossible between 91.7 and 95.3"},
                {"device": "garmin", "metric": "resting_hr", "month": "2019-01",
                 "action": "remove", "why": "long gone"},
                {"device": "garmin", "metric": "resting_hr", "month": "2024-11",
                 "action": "remove"},
            ])
            out = fmt.wearable_ingest_report(rebuild(tmp))
        self.assertIn("2024-10", out)
        self.assertIn("impossible between 91.7 and 95.3", out)
        self.assertIn("2019-01", out)
        self.assertIn("no_reason_given", out)


class TestAnEmptySeriesDoesNotSurviveAsAnEmptyOne(unittest.TestCase):

    def test_removing_the_only_point_removes_the_metric(self):
        with profile_and_export() as tmp:
            write_corrections(tmp, [
                {"device": "garmin", "metric": "resting_hr", "month": "2024-10",
                 "action": "remove", "why": "a"},
                {"device": "garmin", "metric": "resting_hr", "month": "2024-11",
                 "action": "remove", "why": "b"},
            ])
            rebuild(tmp)
            data = json.loads((tmp / "profile" / "wearable_trends.json").read_text(encoding="utf-8"))
            self.assertNotIn("resting_hr", data["sources"]["garmin"]["metrics"])


if __name__ == "__main__":
    unittest.main()
