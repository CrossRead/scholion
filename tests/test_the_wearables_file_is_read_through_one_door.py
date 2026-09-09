"""The wearables file is read through one door, and a goal row that says
nothing says why.

Two watches do not measure resting heart rate the same way, so the file keeps
one block per device: `sources.<device>.metrics`. It has not always had that
shape, and `wearables.series` exists to hide the difference — it migrates an
older file on read and hands back the same thing either way.

`goals._goal_series` did not use it. It knew the shape the file used to be in,
looked for a `metrics` key that had moved a level down, found nothing, and
returned an empty series. Seven of the thirteen rows of the goal table — weight,
BMI, body fat, muscle mass, VO₂max, resting heart rate, steps — printed «—» for
a month, and so did five charts. Nothing raised, nothing logged: a dash is what
this table prints for «no data», and there was plenty of data.

Two rules come out of it, and both are tested here rather than remembered:

* a module that reads the wearables file goes through the accessor;
* a row with no number names the reason, because «—» meant three different
  things and a reader could not tell which.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

import scholion
from scholion.engine import goals


SRC = Path(scholion.__file__).parent


#: The functions that know the file's shape and hide it. `series` hands back one
#: block per device, `migrate` brings an older file to the current shape, and
#: `shared_metrics` names what more than one device reports. Anything reached
#: through one of them may be indexed freely — that is what they are for.
ACCESSORS = {"series", "migrate", "shared_metrics"}


def _name(func):
    return func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)


def violations(source: str):
    """Places that take the wearables file and read into it themselves.

    Not «did this module call the accessor» — two modules that read the file
    correctly do not call `series` at all — but the narrower thing that actually
    breaks: a value that came straight out of `wearable_trends()` and is then
    indexed by whoever received it. Asking whether the file is empty is not that,
    and neither is handing it to an accessor and indexing what comes back.
    """
    tree = ast.parse(source)
    parents = {}
    for node in ast.walk(tree):
        for kid in ast.iter_child_nodes(node):
            parents[kid] = node

    def guarded(call):
        """Is this `wearable_trends()` inside an accessor's argument list?"""
        node = parents.get(call)
        while node is not None:
            if isinstance(node, ast.Call) and _name(node.func) in ACCESSORS:
                return True
            node = parents.get(node)
        return False

    raw = set()          # names bound to an unguarded wearables file
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _name(node.func) == "wearable_trends" \
                and not guarded(node):
            stmt = parents.get(node)
            while stmt is not None and not isinstance(stmt, ast.stmt):
                stmt = parents.get(stmt)
            if isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        raw.add(tgt.id)

    handed_over = {a.id for node in ast.walk(tree)
                   if isinstance(node, ast.Call) and _name(node.func) in ACCESSORS
                   for a in node.args if isinstance(a, ast.Name)}

    bad = []
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.Subscript):
            target = node.value
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr in ("get", "keys", "values", "items"):
            target = node.func.value
        if isinstance(target, ast.Name) and target.id in raw \
                and target.id not in handed_over:
            bad.append((target.id, node.lineno))
    return bad


def readers():
    """Modules that ask for the wearables file, other than the two that own it."""
    found = []
    for p in sorted(SRC.rglob("*.py")):
        if p.name in ("wearables.py", "core.py"):
            continue
        text = p.read_text(encoding="utf-8")
        if "wearable_trends" not in text:
            continue
        try:
            found.append((p.relative_to(SRC).as_posix(), violations(text)))
        except SyntaxError:                                      # noqa: PERF203
            continue
    return found


#: The defect as it stood, in five lines, so the checker above is measured
#: against a case known to be wrong rather than against the repaired tree —
#: which passes whether the checker works or not.
THE_DEFECT = """
def _goal_series(ref):
    data = core.wearable_trends()
    msrc = data.get("metrics") if isinstance(data.get("metrics"), dict) else data
    return (msrc or {}).get(ref)
"""

#: And the two shapes of correct use that the first version of this check
#: called wrong: reaching the contents through an accessor, and not reaching
#: them at all.
THROUGH_THE_ACCESSOR = """
def strip():
    data = _wear.migrate(core.wearable_trends() or {})
    return sorted(data.get("sources") or {}), sorted(_wear.shared_metrics(data))
"""

ONLY_WHETHER_IT_EXISTS = """
def limits():
    return ("wearables", bool(core.wearable_trends()), "limits.no_wearables")
"""


def wear_file(shape, months):
    """`months` = {metric: {YYYY-MM: value}} in the old flat shape or the new one."""
    if shape == "old":
        return {"_meta": {"source": "Garmin"}, "metrics": months}
    return {"_meta": {"shape": "one block per device"},
            "sources": {"garmin": {"_meta": {}, "metrics": months, "workouts": {}}}}


GOALS = {"title": "T", "targets": [
    {"label": "Weight", "source": "wear:Weight"},
    {"label": "Steps", "source": "wear:StepsDaily"},
]}


class TestNothingElseKnowsTheShape(unittest.TestCase):

    def test_the_check_catches_the_defect_it_was_written_for(self):
        """Run against the repaired tree, this check passes whether it works or
        not. Run against the five lines that were wrong, it has to speak."""
        self.assertTrue(violations(THE_DEFECT),
                        "the check would not have caught the month-long defect")

    def test_reaching_the_contents_through_an_accessor_is_fine(self):
        self.assertEqual([], violations(THROUGH_THE_ACCESSOR))

    def test_asking_only_whether_the_file_exists_is_fine(self):
        """No change of shape can make `bool(...)` wrong."""
        self.assertEqual([], violations(ONLY_WHETHER_IT_EXISTS))

    def test_the_scan_finds_readers_at_all(self):
        """A scan that matched nothing would pass the next assertion for ever."""
        names = [n for n, _ in readers()]
        self.assertGreaterEqual(len(names), 2, names)
        self.assertIn("engine/goals.py", names)
        self.assertIn("engine/lifestyle.py", names)

    def test_no_module_reads_into_the_file_itself(self):
        for name, bad in readers():
            with self.subTest(module=name):
                self.assertEqual([], bad,
                                 f"{name} indexes the wearables file directly — it will "
                                 "keep working until the shape moves again, and then "
                                 "return nothing without failing")


class TestTheGoalTableReadsBothShapes(unittest.TestCase):

    MONTHS = {"Weight": {"2026-06": 100.5, "2026-07": 99.0},
              "StepsDaily": {"2026-07": 8356}}

    def _now(self, data):
        with mock.patch.object(goals.core, "health_goals", return_value=GOALS), \
             mock.patch.object(goals.core, "labs", return_value={"markers": {}}), \
             mock.patch.object(goals.core, "wearable_trends", return_value=data):
            return {t["label"]: t for t in goals.goal_dashboard()["targets"]}

    def test_the_current_shape_is_read(self):
        rows = self._now(wear_file("new", self.MONTHS))
        self.assertEqual(rows["Weight"]["now"], "99")
        self.assertEqual(rows["Weight"]["now_date"], "2026-07")
        self.assertEqual(rows["Weight"]["now_device"], "garmin")
        self.assertIsNone(rows["Weight"]["now_missing"])

    def test_a_file_from_an_older_version_gives_the_same_answer(self):
        """The accessor migrates it; nothing above the accessor needs to know."""
        old = self._now(wear_file("old", self.MONTHS))
        new = self._now(wear_file("new", self.MONTHS))
        self.assertEqual(old["Weight"]["now"], new["Weight"]["now"])
        self.assertEqual(old["Steps"]["now"], new["Steps"]["now"])

    def test_the_series_behind_the_chart_is_the_whole_series(self):
        with mock.patch.object(goals.core, "wearable_trends",
                               return_value=wear_file("new", self.MONTHS)):
            pts, dev, why = goals._goal_resolve("wear:Weight")
        self.assertEqual([p["date"] for p in pts], ["2026-06", "2026-07"])
        self.assertEqual(dev, "garmin")
        self.assertIsNone(why)


class TestTwoWatchesAreNotOneSeries(unittest.TestCase):

    TWO = {"_meta": {"shape": "x"}, "sources": {
        "garmin": {"metrics": {"RestingHeartRate": {"2026-07": 64}}},
        "whoop": {"metrics": {"RestingHeartRate": {"2026-07": 58}}}}}

    def test_a_metric_two_devices_report_resolves_to_nothing(self):
        with mock.patch.object(goals.core, "wearable_trends", return_value=self.TWO):
            pts, dev, why = goals._goal_resolve("wear:RestingHeartRate")
        self.assertEqual(pts, [], "the two series were merged or one was picked")
        self.assertEqual(why, "several_devices")

    def test_naming_the_device_answers_it(self):
        with mock.patch.object(goals.core, "wearable_trends", return_value=self.TWO):
            a, dev_a, _ = goals._goal_resolve("wear:garmin:RestingHeartRate")
            b, dev_b, _ = goals._goal_resolve("wear:whoop:RestingHeartRate")
        self.assertEqual((a[-1]["value"], dev_a), (64.0, "garmin"))
        self.assertEqual((b[-1]["value"], dev_b), (58.0, "whoop"))

    def test_a_device_that_does_not_carry_it_is_not_answered_from_another(self):
        with mock.patch.object(goals.core, "wearable_trends", return_value=self.TWO):
            pts, _, why = goals._goal_resolve("wear:polar:RestingHeartRate")
        self.assertEqual((pts, why), ([], "unknown_metric"))


class TestADashAlwaysHasAReason(unittest.TestCase):

    G = {"title": "T", "targets": [
        {"label": "nothing carries it", "source": "wear:Nonexistent"},
        {"label": "no lab points", "source": "lab:empty_one"},
        {"label": "no such marker", "source": "lab:not_a_marker"},
        {"label": "two watches", "source": "wear:RestingHeartRate"},
    ]}

    def rows(self):
        with mock.patch.object(goals.core, "health_goals", return_value=self.G), \
             mock.patch.object(goals.core, "labs",
                               return_value={"markers": {"empty_one": {"series": []}}}), \
             mock.patch.object(goals.core, "wearable_trends",
                               return_value=TestTwoWatchesAreNotOneSeries.TWO):
            return goals.goal_dashboard()["targets"]

    def test_every_row_of_this_table_is_a_dash(self):
        """Otherwise the assertions below are about rows that do not exist."""
        self.assertEqual({r["now"] for r in self.rows()}, {"—"})

    def test_each_dash_names_which_of_the_three_things_went_wrong(self):
        for r in self.rows():
            with self.subTest(row=r["label"]):
                self.assertIn(r["now_missing"],
                              ("unknown_metric", "several_devices", "empty_series"))

    def test_the_reason_reaches_the_reader_as_a_sentence(self):
        for r in self.rows():
            with self.subTest(row=r["label"]):
                txt = r["now_missing_text"]
                self.assertTrue(txt and not txt.startswith("\u27e6"),
                                f"{r['now_missing']} printed as a message key")

    def test_the_heading_date_is_not_older_than_the_board(self):
        """It was the timestamp of one of the files behind the table, while half
        the rows come from another — so a board carrying a draw from the 3rd was
        headed «data as of» the 23rd of the month before."""
        with mock.patch.object(goals.core, "health_goals", return_value={
                "title": "T", "targets": [
                    {"label": "lab", "source": "lab:x"},
                    {"label": "watch", "source": "wear:Weight"}]}), \
             mock.patch.object(goals.core, "labs", return_value={"markers": {
                 "x": {"series": [{"date": "2026-09-03T08:22", "value": 3.4}]}}}), \
             mock.patch.object(goals.core, "wearable_trends",
                               return_value=wear_file("new", {"Weight": {"2026-07": 99.0}})):
            d = goals.goal_dashboard()
        self.assertEqual(d["as_of"], "2026-09-03")

    def test_a_row_with_a_number_carries_no_reason(self):
        with mock.patch.object(goals.core, "health_goals", return_value=GOALS), \
             mock.patch.object(goals.core, "labs", return_value={"markers": {}}), \
             mock.patch.object(goals.core, "wearable_trends", return_value=wear_file(
                 "new", {"Weight": {"2026-07": 99.0}, "StepsDaily": {"2026-07": 8000}})):
            for r in goals.goal_dashboard()["targets"]:
                self.assertIsNone(r["now_missing"], r["label"])
                self.assertIsNone(r["now_missing_text"], r["label"])


if __name__ == "__main__":
    unittest.main()
