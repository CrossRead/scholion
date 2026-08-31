"""A date entering the series is one of three shapes, and mixing two is said out loud.

Three resolutions stood side by side in one series — `2026-07`, `2023-10-04` and
`2026-08-21T10:58` — and the obvious reading was that the third is sloppiness to
be unified away. It is not. Blood drawn before a procedure and again after it is
TWO measurements on one day, and with a key no finer than the day the second could
only be recorded as a discrepancy with the first. The laboratory loader keeps the
clock time for exactly that reason, and `set_draw_context` finds such a pair by
looking for stamps longer than a day. Removing the third resolution would put back
a defect that was already fixed once.

What was actually missing was a GATE. `add_lab_point` promised two resolutions in
its own docstring while the loader deliberately wrote three, and nothing checked
the string at all: `2026-13-45`, an empty string or «вчера» would have become keys
of a series and been sorted and charted alongside real dates.

And the harm the mixture does is real, but it is not the mixture itself: a month
point and a dated point for the same month are ONE measurement standing twice.
Both can be honest — a month typed in from memory years ago, a form loaded today —
so this is reported rather than refused. A doubling nobody is told about is one
nobody will ever undo.

The last class here is the one that protects the earlier fix from this very task:
two draws on one day must still both exist, and the context must still attach to
the later of them.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path

from scholion import core, store


class _Profile(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="dates-"))
        (self.dir / "profile").mkdir()
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.dir / "profile")
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        core.reset_cache()
        shutil.rmtree(self.dir, ignore_errors=True)

    def add(self, date, value=5.4, marker="glucose", **kw):
        kw.setdefault("unit", "mmol/L")
        kw.setdefault("subject", "owner")
        kw.setdefault("date_source", "form")
        return store.add_lab_point(marker, date, value, **kw)

    def dates(self, marker="glucose"):
        m = core.labs().get("markers", {}).get(marker) or {}
        return [pt["date"] for pt in m.get("series") or []]


class TestTheThreeShapesAreTheContract(unittest.TestCase):

    def test_each_shape_is_recognised_for_what_it_is(self):
        self.assertEqual(store.date_resolution("2026-07"), "month")
        self.assertEqual(store.date_resolution("2023-10-04"), "day")
        self.assertEqual(store.date_resolution("2026-08-21T10:58"), "stamp")

    def test_a_shape_that_is_not_a_date_is_not_one(self):
        for bad in ("", "   ", "вчера", "2026", "26-08-21", "2026-08-21 10:58",
                    "2026/08/21", "yesterday"):
            self.assertIsNone(store.date_resolution(bad), bad)

    def test_a_calendar_decides_and_not_the_shape_alone(self):
        """`2026-13-45` has the shape of a day. Only a calendar can say it is not
        one, so a calendar is asked."""
        self.assertIsNone(store.date_resolution("2026-13-45"))
        self.assertIsNone(store.date_resolution("2026-02-30"))
        self.assertEqual(store.date_resolution("2024-02-29"), "day")

    def test_the_docstring_and_the_list_agree(self):
        """The defect this file is about was a promise in prose that the code did
        not keep. The promise now comes from the same list the gate uses."""
        self.assertIn("DATE_SHAPES", store.add_lab_point.__doc__)
        self.assertEqual(len(store.DATE_SHAPES), 3)


class TestWhatIsNotADateDoesNotEnterTheSeries(_Profile):

    def test_a_string_that_is_not_a_date_is_refused(self):
        r = self.add("вчера")
        self.assertFalse(r["ok"])
        self.assertEqual(self.dates(), [])

    def test_the_refusal_names_every_shape_that_would_work(self):
        r = self.add("2026-13-45")
        for shape in store.DATE_SHAPES:
            self.assertIn(shape, r["error"])

    def test_all_three_shapes_are_accepted(self):
        for d in ("2026-07", "2026-07-04", "2026-07-04T09:15"):
            self.assertTrue(self.add(d).get("ok"), d)


class TestOneMeasurementStandingTwiceIsNamed(_Profile):

    def test_a_month_and_a_day_of_that_month_are_reported(self):
        self.add("2026-07")
        r = self.add("2026-07-04", value=5.6)
        self.assertEqual(r.get("resolution_mixed"), ["2026-07"])

    def test_a_day_and_a_stamp_of_that_day_are_reported(self):
        self.add("2026-08-21")
        r = self.add("2026-08-21T10:58", value=5.9)
        self.assertEqual(r.get("resolution_mixed"), ["2026-08-21"])

    def test_two_days_of_one_month_are_not_a_doubling(self):
        """Same resolution, different days — an ordinary series, not one
        measurement written twice."""
        self.add("2026-07-04")
        r = self.add("2026-07-19", value=5.6)
        self.assertNotIn("resolution_mixed", r)

    def test_two_draws_of_one_day_are_not_a_doubling(self):
        self.add("2026-08-21T09:10")
        r = self.add("2026-08-21T16:40", value=6.2)
        self.assertNotIn("resolution_mixed", r)

    def test_nothing_is_refused_or_deleted_by_the_report(self):
        """Both points may be honest, so the mixture is reported and BOTH stay."""
        self.add("2026-07")
        self.add("2026-07-04", value=5.6)
        self.assertEqual(self.dates(), ["2026-07", "2026-07-04"])


class TestTheEarlierFixIsNotUndoneByThisOne(_Profile):
    """The reason the third resolution exists. If a later pass ever «unifies the
    format», these fail — which is the whole point of writing them down here."""

    def test_two_draws_on_one_day_both_survive(self):
        self.add("2026-08-21T09:10", value=5.1)
        self.add("2026-08-21T16:40", value=6.2)
        self.assertEqual(self.dates(), ["2026-08-21T09:10", "2026-08-21T16:40"])

    def test_the_context_attaches_to_the_later_draw(self):
        self.add("2026-08-21T09:10", value=5.1)
        self.add("2026-08-21T16:40", value=6.2)
        r = store.set_draw_context("2026-08-21", reason="glucose load")
        self.assertTrue(r["ok"], r.get("error"))
        m = core.labs()["markers"]["glucose"]
        by_date = {pt["date"]: pt for pt in m["series"]}
        self.assertIn("draw_context", by_date["2026-08-21T16:40"])
        self.assertNotIn("draw_context", by_date["2026-08-21T09:10"])

    def test_a_day_key_would_have_collapsed_them(self):
        """Stated as an assertion rather than a comment: written at day
        resolution, the second draw REPLACES the first and one of the two
        measurements is gone."""
        self.add("2026-08-21", value=5.1)
        self.add("2026-08-21", value=6.2)
        self.assertEqual(self.dates(), ["2026-08-21"])


if __name__ == "__main__":
    unittest.main()
