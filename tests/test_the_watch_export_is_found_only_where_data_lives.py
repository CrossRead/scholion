"""Where a wearable export may be looked for, and what a rebuild must not erase.

Two properties, and this project has been wrong about both. They are tested here
against `wearables`, which is the code that runs.

That last clause is the point of this file's history. Both rules were arrived at
in the Garmin path, and both moved to `wearables` when a second device arrived —
but the superseded copy stayed in `garmin.py` for a release, and it collected the
attention meant for the original: a first version of this file measured its
coverage, and `test_lab_dir_boundary` checked the search rule on it. Twenty-one
green tests over a hundred and forty-three lines the application never executed,
while `wearables._merge` — the same rule, in the module that runs — had none at
all. A duplicate that outlives its purpose is not inert.

WHERE IT LOOKS. The search once walked the repository directory, its parent AND
its grandparent. From a delivered package that is the folder somebody unpacked it
into and the folder above that — a documents directory, by construction. It was
verified from a built package: the search resolved to a real `garmin_export` two
directories away, and the ingest would have written that person's sleep and heart
rate into the package's own profile. Years of somebody's nights are not less
private than a lab form, so the rule is the same one: automatic discovery looks
where the data layout says data lives and nowhere else. `nearby_candidate` exists
to say a sentence about anything further away without ever opening it.

WHAT A REBUILD KEEPS. The ingest rebuilds from the export rather than appending,
which is what makes it safe to run after every download — and what makes an
INCOMPLETE export dangerous: one that stopped halfway would rewrite the file with
less history than it had. It has happened. `_merge` is the answer, and with two
devices it carries a second obligation the Garmin version never had: an export
from one watch may not touch another watch's series at all.

Recognising an export by its contents is tested in
`test_two_devices_never_become_one_series` and is not repeated here.
"""
from __future__ import annotations

import ast
import csv
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, garmin, wearables


@contextmanager
def data_root():
    """A temporary tree standing in for the whole data directory.

    The readers live in `src/ingest/` and are loaded from `repo_dir()`, so they
    are copied in: without them `detect` cannot ask a WHOOP export what it is and
    would answer «not one» for a reason that has nothing to do with the test.
    """
    # Two levels of our OWN below the temporary root, because the search reaches
    # `base.parent` and `base.parent.parent` and the test has to be able to put
    # something there. On this machine `mkdtemp` lands deep enough that writing
    # above it happens to work; on a Linux runner it lands in `/tmp`, and the
    # grandparent is `/` — the test then failed for want of permission on the
    # root of the filesystem rather than for anything it was about.
    outer = Path(tempfile.mkdtemp(prefix="wearables-")).resolve()
    tmp = outer / "above" / "data"
    tmp.mkdir(parents=True)
    (tmp / "profile").mkdir()
    real_ingest = support.ROOT / "src" / "ingest"
    if real_ingest.is_dir():
        (tmp / "src").mkdir()
        shutil.copytree(real_ingest, tmp / "src" / "ingest")
    old = {k: os.environ.get(k) for k in ("SCHOLION_REPO_DIR", "SCHOLION_PROFILE_DIR")}
    os.environ["SCHOLION_REPO_DIR"] = str(tmp)
    os.environ["SCHOLION_PROFILE_DIR"] = str(tmp / "profile")
    core.reset_cache()
    try:
        yield tmp
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        core.reset_cache()
        shutil.rmtree(outer, ignore_errors=True)


def make_garmin(path: Path) -> Path:
    """The shape of a Garmin GDPR export, and nothing inside it."""
    (path / "DI_CONNECT").mkdir(parents=True, exist_ok=True)
    return path


WHOOP_ROWS = [{"Cycle start time": "2025-01-01 00:00:00", "Recovery score %": "70"}]


def _csv_text() -> str:
    import io
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(WHOOP_ROWS[0]))
    writer.writeheader()
    writer.writerows(WHOOP_ROWS)
    return buf.getvalue()


def make_whoop(path: Path) -> Path:
    """Two of the three measurement files is what makes it one."""
    path.mkdir(parents=True, exist_ok=True)
    for name in ("physiological_cycles.csv", "sleeps.csv"):
        (path / name).write_text(_csv_text(), encoding="utf-8")
    return path


def make_whoop_zip(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        for name in ("physiological_cycles.csv", "sleeps.csv"):
            z.writestr(name, _csv_text())
    return path


class TestWhereAnExportMayBeLookedFor(unittest.TestCase):

    def test_the_persons_own_setting_wins_and_is_per_device(self):
        with data_root() as root:
            chosen = make_garmin(root / "elsewhere" / "my-watch")
            (root / "profile" / "sources.json").write_text(
                json.dumps({"folders": {"garmin": str(chosen)}}), encoding="utf-8")
            core.reset_cache()
            self.assertEqual((chosen, "garmin"), wearables.find_export())

    def test_the_declared_slot_is_searched(self):
        with data_root() as root:
            chosen = make_garmin(root / "raw" / "wearables" / "garmin_export")
            self.assertEqual((chosen, "garmin"), wearables.find_export())

    def test_a_folder_by_a_known_name_in_the_data_directory_is_searched(self):
        with data_root() as root:
            chosen = make_garmin(root / "garmin_export")
            self.assertEqual((chosen, "garmin"), wearables.find_export())

    def test_an_archive_sitting_in_the_slot_is_found(self):
        with data_root() as root:
            z = make_whoop_zip(root / "raw" / "wearables" / "my_whoop_data.zip")
            found = wearables.find_export()
            self.assertIsNotNone(found, "a zip in the declared slot was not looked into")
            self.assertEqual((z, "whoop"), found)

    def test_nothing_anywhere_is_answered_with_nothing(self):
        with data_root():
            self.assertIsNone(wearables.find_export())

    def test_an_export_above_the_data_directory_is_never_returned(self):
        """The defect, stated as a test. A real export one and two directories up
        is exactly what a delivered package sits next to."""
        with data_root() as root:
            above = [root.parent / "garmin_export", root.parent.parent / "garmin_export"]
            for d in above:
                make_garmin(d)
            try:
                self.assertIsNone(wearables.find_export(),
                                  "the search walked out of the data directory and found "
                                  "somebody's export")
            finally:
                for d in above:
                    shutil.rmtree(d, ignore_errors=True)

    def test_asking_for_one_watch_does_not_hand_over_the_other(self):
        with data_root() as root:
            make_garmin(root / "garmin_export")
            self.assertIsNone(wearables.find_export(source="whoop"),
                              "a Garmin export was offered to a request for a WHOOP one")
            self.assertEqual("garmin", wearables.find_export(source="garmin")[1])

    def test_the_device_travels_with_the_path_so_nobody_has_to_assume(self):
        with data_root() as root:
            make_whoop(root / "whoop_export")
            path, source = wearables.find_export()
            self.assertEqual("whoop", source)
            self.assertTrue(str(path).startswith(str(root)))


class TestWhatIsVisibleNearbyIsNamedRatherThanOpened(unittest.TestCase):

    def test_an_export_next_door_is_named_but_not_read(self):
        with data_root() as root:
            outside = make_garmin(root.parent / "garmin_export")
            try:
                self.assertEqual((outside, "garmin"), wearables.nearby_candidate())
                self.assertIsNone(wearables.find_export(),
                                  "what may only be mentioned was opened")
            finally:
                shutil.rmtree(outside, ignore_errors=True)

    def test_nothing_nearby_is_also_an_answer(self):
        with data_root():
            got = wearables.nearby_candidate()
            self.assertTrue(got is None or isinstance(got, tuple))


class TestARebuildDoesNotLoseHistory(unittest.TestCase):
    """`_merge(fresh, previous, source)` — the fresh build wins per month, and
    months it does not carry survive."""

    @staticmethod
    def previous(**by_source):
        return {"sources": {k: {"metrics": v} for k, v in by_source.items()}}

    def test_a_month_the_export_no_longer_mentions_survives(self):
        """The case that has actually happened: a download that did not complete
        would otherwise rewrite the file with less history than it had."""
        fresh = {"metrics": {"sleep": {"2025-02": 7.5}}}
        kept = wearables._merge(fresh, self.previous(
            garmin={"sleep": {"2025-01": 7.0, "2025-02": 7.2}}), "garmin")
        self.assertEqual(1, kept)
        self.assertEqual({"2025-01": 7.0, "2025-02": 7.5}, fresh["metrics"]["sleep"],
                         "the fresh build must win where it speaks and keep quiet where "
                         "it does not")

    def test_a_whole_metric_the_export_dropped_survives(self):
        fresh = {"metrics": {"sleep": {"2025-01": 7.1}}}
        kept = wearables._merge(fresh, self.previous(
            garmin={"sleep": {"2025-01": 7.0}, "hrv": {"2025-01": 40}}), "garmin")
        self.assertEqual(1, kept)
        self.assertIn("hrv", fresh["metrics"])

    def test_one_watch_cannot_touch_the_others_series(self):
        """The obligation the single-device version never had. A Garmin rebuild
        that pulled WHOOP's months into its own block would put one device's
        numbers under another's name — which is the defect this whole layer was
        reshaped to prevent, arriving through the back door."""
        fresh = {"metrics": {"sleep": {"2025-02": 7.5}}}
        kept = wearables._merge(fresh, self.previous(
            garmin={"sleep": {"2025-01": 7.0}},
            whoop={"sleep": {"2024-12": 6.0}, "strain": {"2024-12": 11.0}}), "garmin")
        self.assertEqual(1, kept)
        self.assertNotIn("strain", fresh["metrics"], "a WHOOP metric arrived in the Garmin block")
        self.assertNotIn("2024-12", fresh["metrics"]["sleep"],
                         "a WHOOP month arrived in the Garmin series")

    def test_the_months_come_back_in_order(self):
        fresh = {"metrics": {"sleep": {"2025-01": 6.5}}}
        wearables._merge(fresh, self.previous(
            garmin={"sleep": {"2024-11": 6.0, "2025-03": 7.0}}), "garmin")
        self.assertEqual(["2024-11", "2025-01", "2025-03"], list(fresh["metrics"]["sleep"]))

    def test_a_first_ever_build_has_nothing_to_preserve(self):
        fresh = {"metrics": {"sleep": {"2025-01": 7.0}}}
        self.assertEqual(0, wearables._merge(fresh, {}, "garmin"))
        self.assertEqual({"sleep": {"2025-01": 7.0}}, fresh["metrics"])

    def test_a_file_from_before_devices_were_recorded_is_migrated_before_merging(self):
        """An older file has no `sources` block at all. Merging against it
        directly would find nothing to preserve and erase the history in the one
        situation where the person has the most of it."""
        old_shape = {"_meta": {"source": "Garmin Connect export"},
                     "metrics": {"sleep": {"2024-05": 7.4}}}
        fresh = {"metrics": {"sleep": {"2025-01": 7.0}}}
        kept = wearables._merge(fresh, old_shape, "garmin")
        self.assertEqual(1, kept, "history in the pre-device file shape was dropped")
        self.assertEqual({"2024-05": 7.4, "2025-01": 7.0}, fresh["metrics"]["sleep"])


class TestTheOldCommandStillAsksForOneWatch(unittest.TestCase):

    def test_ingest_garmin_names_the_device_it_wants(self):
        """`ingest-garmin` is in the public contract and cannot be withdrawn. It
        must not be able to file a WHOOP export under the wrong watch."""
        with mock.patch.object(wearables, "reingest", return_value={"ok": True}) as m:
            garmin.reingest("/some/path")
        self.assertEqual(("/some/path",), m.call_args.args)
        self.assertEqual("garmin", m.call_args.kwargs.get("source"))

    def test_the_superseded_implementation_is_not_back(self):
        """A structural check, because this exact duplicate sat unused for a
        release and drew two separate suites onto itself. The module is a name
        kept for the contract; anything else in it is a second implementation."""
        tree = ast.parse(Path(garmin.__file__).read_text(encoding="utf-8"))
        defined = sorted(n.name for n in tree.body
                         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
        self.assertEqual(["reingest"], defined,
                         "garmin.py carries functions again — the work belongs in "
                         "wearables.py, where it is the one copy that runs")


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
