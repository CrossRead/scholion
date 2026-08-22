"""Two devices measured it; nothing here is allowed to pretend one did.

A Garmin and a WHOOP both report resting heart rate, HRV, respiration and sleep,
and they do not measure them the same way. A single series carrying both shows a
step on the month the second export was loaded, and a reader takes that step for
a change in themselves. This file is the reason that cannot happen quietly:

* the series are kept apart, and a merge would be visible here;
* a conclusion is drawn from the device a person named, and from no other;
* where nobody named one, the metric is shown and enters no conclusion at all;
* a file from before any of this is migrated on read, and the device it is filed
  under is read out of what that file says — a file that says nothing is filed
  as `unspecified` rather than guessed into somebody's watch.

The column table is enumerated rather than spot-checked: a header pointing at a
metric that does not exist, or asking for a conversion nobody wrote, fails the
build instead of losing a column in silence at somebody's first run.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

import support

ROOT = support.ROOT
FIXTURE = ROOT / "tests" / "fixtures" / "whoop"


def _reader():
    spec = importlib.util.spec_from_file_location(
        "_t_whoop", ROOT / "src" / "ingest" / "ingest_whoop.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _knowledge():
    return json.loads((ROOT / "src" / "scholion" / "knowledge"
                       / "wearable_metrics.json").read_text(encoding="utf-8"))


class TestTheExportIsRead(unittest.TestCase):

    def setUp(self):
        if not FIXTURE.exists():
            self.skipTest("no WHOOP fixture in this build")
        self.data = _reader().build(str(FIXTURE), _knowledge())

    def test_it_reads_the_measurements(self):
        self.assertTrue(self.data.get("ok"))
        m = self.data["metrics"]
        for key in ("Recovery", "HRV", "RestingHeartRate", "SleepHours", "DayStrain"):
            self.assertIn(key, m, f"«{key}» was in the export and did not arrive")
        self.assertEqual(sorted(m["Recovery"]), ["2026-01", "2026-02"])

    def test_minutes_become_hours_rather_than_staying_minutes(self):
        """391 and 362 minutes is 6.28 h, not 376 of something."""
        self.assertAlmostEqual(self.data["metrics"]["SleepHours"]["2026-01"], 6.28, places=2)

    def test_a_column_nobody_knows_is_named_and_not_read(self):
        meta = self.data["_meta"]
        self.assertIn("Mystery Column", meta["unrecognised_columns"])
        self.assertNotIn("Mystery Column", self.data["metrics"])

    def test_a_timestamp_that_is_not_one_is_counted_and_not_repaired(self):
        """The row with `not-a-date` carries a heart rate. It is not filed anywhere."""
        self.assertGreaterEqual(self.data["_meta"]["rows_without_a_date"], 1)
        self.assertNotIn(60.0, self.data["metrics"]["RestingHeartRate"].values())

    def test_a_nap_does_not_shorten_a_month_of_nights(self):
        """The sleep file holds naps. A forty-minute one averaged into a month of
        nights reports sleep getting shorter, which is a fact about the file.

        January in the fixture is two nights of 391 and 362 minutes — 6.28 h —
        plus a 41-minute nap. If the nap were counted the month would read about
        4.4 h and nothing would say why.
        """
        self.assertAlmostEqual(self.data["metrics"]["SleepHours"]["2026-01"], 6.28, places=2)
        self.assertEqual(self.data["_meta"]["metrics_from"], "physiological_cycles")

    def test_the_night_list_leaves_naps_out_and_the_count_shows_it(self):
        self.assertEqual(len(self.data["nightly_sleep"]), 3)
        self.assertEqual([n["date"] for n in self.data["nightly_sleep"]],
                         ["2026-01-04", "2026-01-05", "2026-02-02"])

    def test_the_measurements_a_real_export_carries_all_arrive(self):
        """Every column of a published member export is either read or named.

        The four below were missing until a real export was compared against the
        table — a synthetic fixture agrees with whoever wrote it.
        """
        for key in ("LightSleepMin", "AwakeMin", "TimeInBedMin", "SleepNeedMin"):
            self.assertIn(key, self.data["metrics"])

    def test_a_known_timestamp_column_is_not_reported_as_unknown(self):
        """Otherwise the list of unknown columns is too long to be worth reading."""
        for noisy in ("Cycle start time", "Cycle timezone", "Wake onset", "Nap",
                      "HR Zone 3 %", "GPS enabled", "Notes"):
            self.assertNotIn(noisy, self.data["_meta"]["unrecognised_columns"])


class TestTheColumnTableIsWholeRatherThanSampled(unittest.TestCase):
    """Enumerated, because the failure of a single wrong line is a silent one."""

    def setUp(self):
        self.k = _knowledge()
        self.mod = _reader()

    def test_every_column_points_at_a_metric_that_exists(self):
        known = set(self.k.get("metrics") or {})
        for header, spec in (self.k["sources"]["whoop"]["columns"]).items():
            with self.subTest(column=header):
                self.assertIn(spec["metric"], known,
                              "the column names a metric the reference does not define, "
                              "so the value would arrive with no label, unit or direction")

    def test_every_conversion_named_is_one_that_exists(self):
        for header, spec in (self.k["sources"]["whoop"]["columns"]).items():
            with self.subTest(column=header):
                self.assertIn(spec.get("read", "number"), self.mod.CONVERTERS)

    def test_every_metric_in_the_table_is_in_the_display_order(self):
        order = set(self.k.get("order") or ())
        for spec in self.k["sources"]["whoop"]["columns"].values():
            with self.subTest(metric=spec["metric"]):
                self.assertIn(spec["metric"], order,
                              "a metric absent from `order` is read and then never shown")


class TestOneFileOneDevice(unittest.TestCase):

    def setUp(self):
        from scholion import wearables
        self.w = wearables

    def test_an_export_is_recognised_by_what_is_inside_it(self):
        if not FIXTURE.exists():
            self.skipTest("no WHOOP fixture in this build")
        self.assertEqual(self.w.detect(FIXTURE), "whoop")

    def test_a_folder_that_merely_contains_an_export_is_not_one(self):
        """`tests/fixtures` holds the WHOOP fixture among many other folders.

        Calling it an export would mean any ancestor of one is an export, and an
        automatic search that accepts an ancestor is a search that reads folders
        nobody offered it.
        """
        self.assertIsNone(self.w.detect(ROOT / "tests" / "fixtures"))

    def test_the_single_folder_a_zip_unpacks_into_is_still_found(self):
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(FIXTURE, Path(tmp) / "my_whoop_data_20260210")
            self.assertEqual(self.w.detect(Path(tmp)), "whoop")

    def test_an_old_file_is_migrated_and_the_device_is_read_not_guessed(self):
        old = {"_meta": {"source": "Garmin Connect (GDPR export)"},
               "metrics": {"HRV": {"2025-01": 40}}, "workouts": {}}
        got = self.w.migrate(old)
        self.assertEqual(list(got["sources"]), ["garmin"])
        self.assertEqual(got["sources"]["garmin"]["metrics"]["HRV"]["2025-01"], 40)

    def test_a_file_that_names_no_device_is_not_assigned_one(self):
        """«Probably Garmin» would put somebody else's watch under a name they
        never chose, and nothing downstream could tell."""
        got = self.w.migrate({"_meta": {"range": "2025-01–2025-06"},
                              "metrics": {"HRV": {"2025-01": 40}}})
        self.assertEqual(list(got["sources"]), ["unspecified"])

    def test_it_does_not_invent_a_second_meaning_for_the_schema_field(self):
        """`_meta.schema` is the PROFILE file format, and the core refuses a file
        whose number is newer than the build. A layout counter of our own under
        that name would make every reader declare this file one from the future."""
        got = self.w.migrate({"_meta": {"source": "Garmin"}, "metrics": {"HRV": {"2025-01": 40}}})
        self.assertNotIn("schema", got["_meta"])

    def test_migration_leaves_an_already_migrated_file_alone(self):
        once = self.w.migrate({"_meta": {"source": "Garmin"}, "metrics": {"HRV": {"2025-01": 40}}})
        self.assertEqual(self.w.migrate(once), once)

    def test_a_metric_both_devices_report_is_named_as_shared(self):
        two = {"_meta": {}, "sources": {
            "garmin": {"metrics": {"HRV": {"2025-01": 40}, "StepsDaily": {"2025-01": 9000}}},
            "whoop": {"metrics": {"HRV": {"2025-01": 70}, "Recovery": {"2025-01": 66}}}}}
        self.assertEqual(self.w.shared_metrics(two), {"HRV": ["garmin", "whoop"]})


class TestTheSeriesAreNotMerged(unittest.TestCase):
    """The gate that would catch a merge, exercised on a profile with two devices."""

    TWO = {"_meta": {}, "sources": {
        "garmin": {"metrics": {"HRV": {"2025-01": 40.0, "2025-02": 41.0}}, "workouts": {}},
        "whoop": {"metrics": {"HRV": {"2025-01": 70.0, "2025-02": 71.0}}, "workouts": {}}}}

    def _lifestyle(self, primary=None):
        import sys
        from scholion import core
        import scholion.engine.lifestyle          # noqa: F401  (the package re-exports the
        mod = sys.modules["scholion.engine.lifestyle"]   # function under the module's name)
        real_trends, real_primary = core.wearable_trends, core.wearable_primary
        core.wearable_trends = lambda: self.TWO
        core.wearable_primary = lambda: primary
        try:
            return mod.lifestyle()
        finally:
            core.wearable_trends, core.wearable_primary = real_trends, real_primary

    def test_both_series_arrive_and_neither_is_the_average(self):
        got = [m for m in self._lifestyle()["metrics"] if m["key"] == "HRV"]
        self.assertEqual(len(got), 2, "two devices measured it and one entry came back")
        self.assertEqual(sorted(m["source"] for m in got), ["garmin", "whoop"])
        values = {m["source"]: m["value"] for m in got}
        self.assertAlmostEqual(values["garmin"], 41.0, places=1)
        self.assertAlmostEqual(values["whoop"], 71.0, places=1)
        # 55.5 is the average of the two devices. Nobody measured it.
        for m in got:
            self.assertNotAlmostEqual(m["value"], 55.5, places=1,
                                      msg="a value nobody measured reached the report")

    def test_with_nobody_named_the_shared_metric_enters_no_conclusion(self):
        r = self._lifestyle()
        self.assertEqual(r["shared_unresolved"], ["HRV"])
        for m in r["metrics"]:
            if m["key"] == "HRV":
                self.assertFalse(m["counts_toward_conclusions"])

    def test_naming_a_device_makes_that_one_answer_and_only_that_one(self):
        r = self._lifestyle(primary="whoop")
        counted = [m for m in r["metrics"] if m["key"] == "HRV" and m["counts_toward_conclusions"]]
        self.assertEqual([m["source"] for m in counted], ["whoop"])
        self.assertEqual(r["shared_unresolved"], [])

    def test_a_metric_only_one_device_reports_is_untouched_by_all_of_this(self):
        """The person with a single device must not pay for the person with two."""
        one = {"_meta": {},
               "sources": {"whoop": {"metrics": {"Recovery": {"2025-01": 66.0}}, "workouts": {}}}}
        import sys
        from scholion import core
        import scholion.engine.lifestyle          # noqa: F401  (the package re-exports the
        mod = sys.modules["scholion.engine.lifestyle"]   # function under the module's name)
        real = core.wearable_trends
        core.wearable_trends = lambda: one
        try:
            got = [m for m in mod.lifestyle()["metrics"] if m["key"] == "Recovery"]
        finally:
            core.wearable_trends = real
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0]["counts_toward_conclusions"])
        self.assertEqual(got[0]["also_measured_by"], [])


class TestTheCommandRefusesRatherThanFilingUnderTheWrongName(unittest.TestCase):

    def test_asking_for_one_device_and_being_handed_another_reads_nothing(self):
        if not FIXTURE.exists():
            self.skipTest("no WHOOP fixture in this build")
        code, stdout, stderr = support.run(
            ["ingest-wearable", str(FIXTURE), "--device", "garmin"])
        self.assertIn("whoop", (stdout + stderr).lower(),
                      "the refusal has to name what the file actually is")
        self.assertNotIn("metric series", stdout)


class TestThePageNamesTheDevice(unittest.TestCase):
    """A number on screen without the device that produced it invites a comparison
    nobody may make. Enumerated over the devices this build can read, so adding a
    third one without giving it a name on screen fails here rather than showing
    a raw internal word to a person."""

    def setUp(self):
        from scholion import wearables
        from scholion.i18n import messages
        self.w = wearables
        self.cat = messages

    def test_every_device_has_a_name_in_every_language(self):
        names = [k["source"] for k in self.w.KINDS] + ["unspecified", "apple_health"]
        for lang in ("en", "ru"):
            for name in names:
                with self.subTest(lang=lang, device=name):
                    key = f"web.life.device.{name}"
                    self.assertIn(key, self.cat(lang),
                                  "the page would print the internal word to a person")

    def test_the_command_actually_records_the_choice(self):
        """The banner offers a button and the command prints «recorded». Neither
        means anything unless the field survives the write — and the writer keeps
        an explicit list of fields, which is exactly where a new one gets lost."""
        import tempfile
        from scholion import core, store
        with tempfile.TemporaryDirectory() as tmp:
            real = core.profile_dir
            core.profile_dir = lambda: Path(tmp)
            try:
                store._path("metrics.json").write_text('{"profile": {}, "metrics": {}}',
                                                       encoding="utf-8")
                r = store.update_metric_profile({"wearable_primary": "whoop"})
                self.assertEqual(r["profile"].get("wearable_primary"), "whoop")
                self.assertEqual(core.wearable_primary(), "whoop")
            finally:
                core.profile_dir = real
                core.reset_cache()

    def test_the_label_helper_never_returns_a_bare_internal_word(self):
        self.assertEqual(self.w.device_label("garmin"), "Garmin")
        self.assertEqual(self.w.device_label("whoop"), "WHOOP")
        self.assertNotEqual(self.w.device_label("unspecified"), "unspecified")

    def test_the_page_asks_for_the_device_of_every_metric_it_draws(self):
        """The card template has to reach for the source, or the whole point of
        storing it per device is lost at the last step."""
        page = (ROOT / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("srcTag(m)", page)
        self.assertIn("also_measured_by", page)
        self.assertIn("shared_unresolved", page)

    def test_the_source_strip_names_devices_rather_than_a_file_path(self):
        from scholion import core
        import sys
        import scholion.engine.sources                     # noqa: F401
        mod = sys.modules["scholion.engine.sources"]
        real = core.wearable_trends
        core.wearable_trends = lambda: {"sources": {
            "garmin": {"metrics": {"HRV": {"2025-01": 40}}},
            "whoop": {"metrics": {"HRV": {"2025-01": 70}}}}}
        try:
            s = mod.provenance()["lifestyle"]
        finally:
            core.wearable_trends = real
        self.assertEqual(s.get("devices"), ["garmin", "whoop"])
        self.assertEqual(s.get("shared_metrics"), ["HRV"])


class TestTheOverlayIsRealRatherThanPromised(unittest.TestCase):
    """The report tells a person to name an unknown column in a file. That file
    has to be read, or the sentence is a complaint dressed as an instruction."""

    def test_a_column_named_in_the_profile_is_read(self):
        import json as _j, tempfile
        from scholion import core, wearables
        with tempfile.TemporaryDirectory() as tmp:
            prof = Path(tmp)
            (prof / wearables.OVERLAY).write_text(_j.dumps(
                {"sources": {"whoop": {"columns": {"Mystery Column": {"metric": "Recovery"}}}}}),
                encoding="utf-8")
            real = core.profile_dir
            core.profile_dir = lambda: prof
            try:
                k = wearables.knowledge()
            finally:
                core.profile_dir = real
        cols = k["sources"]["whoop"]["columns"]
        self.assertIn("Mystery Column", cols)
        self.assertIn("Recovery score %", cols, "an addition must not delete what shipped")


if __name__ == "__main__":
    unittest.main()
