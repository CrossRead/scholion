"""One draw, one point — whatever resolution each of its two writes carried.

Task 128, reproduced on a real profile on 05.09.2026. A panel was entered by
hand as `2026-09-03`, then re-imported with `ingest-labs`, which reads the draw
hour off the form and writes `2026-09-03T08:22`. The store replaced a point only
on an exact match of the string, so the second write joined the series beside
the first: 54 markers with two points of one draw, values identical. Nothing
failed. The series grew, and the engine's «previous point» became the same draw —
every trend read as flat where it should have read as a step.

The mixed-resolution report did notice it. It was a report and not a rule, and
the report is capped at ten lines, so on a folder of thirteen files it looked
like one file being refused and twelve going through.

Task 144, reproduced on 08.09.2026 on 251 markers. The rule written for 128
compared DAYS, and the shape older imports wrote is a month: `2025-12` against
the form's `2025-12-20T07:30` fell back to the exact-string rule, and one
re-imported folder added 254 points where it should have replaced them. The
guard here covered only the day, which is exactly why 128 closed green — so the
month case now comes first in this file.

What these tests hold: a point of the same period replaces a point of the same
period at every resolution — month, day, day with the clock time — the finer
date wins whichever order the two writes came in, what the earlier point
recorded about the draw survives the replacement, the rule is the store's and
so holds on every path that writes a point, and the case that cannot be
resolved — a bare day or month against two draws inside it — is still not
guessed at.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import support

STAMPED = """Date,Test,Result,Units,Reference Range
2018-05-22T08:22,Ferritin,31,ng/mL,13-150
"""

# The shape of the December folder that reproduced task 144: the form prints
# the draw with its clock time, the profile held the month.
STAMPED_DECEMBER = """Date,Test,Result,Units,Reference Range
2025-12-20T07:30,Ferritin,31,ng/mL,13-150
"""


class _Profile(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.forms = self.root / "forms"
        self.forms.mkdir()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self._restore = support.pin_profile(self.profile)
        # The cache too: the loader's list of already-read files lives beside
        # the profile now, and an old list found in the cache is carried over.
        self._restore_cache = support.pin_cache(self.root / "cache")
        from scholion import core
        core.reset_cache()

    def tearDown(self):
        self._restore()
        self._restore_cache()
        from scholion import core
        core.reset_cache()
        self.tmp.cleanup()

    def add(self, date, value=31.0, **kw):
        from scholion import store
        kw.setdefault("unit", "ng/mL")
        kw.setdefault("subject", "owner")
        kw.setdefault("date_source", "manual")
        return store.add_lab_point("ferritin", date, value, **kw)

    def series(self):
        labs = json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))
        return labs["markers"]["ferritin"]["series"]

    def dates(self):
        return [pt["date"] for pt in self.series()]

    def seed(self, *dates, value=31.0):
        """Write points directly, as an older store left them: going through
        `add` would already apply the rule under test."""
        self.add(dates[0], value=value)
        p = self.profile / "labs.json"
        labs = json.loads(p.read_text(encoding="utf-8"))
        labs["markers"]["ferritin"]["series"] = [{"date": d, "value": value} for d in dates]
        p.write_text(json.dumps(labs, ensure_ascii=False), encoding="utf-8")
        from scholion import core
        core.reset_cache()

    def annotate(self, **fields):
        """Write provenance onto the only point, the way older profiles carry it."""
        p = self.profile / "labs.json"
        labs = json.loads(p.read_text(encoding="utf-8"))
        labs["markers"]["ferritin"]["series"][0].update(fields)
        p.write_text(json.dumps(labs, ensure_ascii=False), encoding="utf-8")
        from scholion import core
        core.reset_cache()

    def ingest(self):
        from scholion import ingest_labs
        return ingest_labs.ingest(str(self.forms), force=True)


class TestAMonthAndItsTimedDrawAreOnePoint(_Profile):
    """Task 144. The pair the guard below did not cover, and the profile paid for."""

    def test_a_monthly_point_is_replaced_by_the_stamped_re_import(self):
        """The order the defect was found in: monthly points from an older
        import, the same folder re-imported with the draw hour on the form."""
        self.assertTrue(self.add("2025-12")["ok"])
        (self.forms / "december.csv").write_text(STAMPED_DECEMBER, encoding="utf-8")

        r = self.ingest()

        self.assertEqual(r["points_added"], 1, r)
        self.assertEqual(self.dates(), ["2025-12-20T07:30"],
                         "the same draw stands in the series twice")
        self.assertEqual(self.series()[0]["value"], 31.0)
        rep = [x for x in r.get("same_day_replaced") or [] if x["marker"] == "ferritin"]
        self.assertEqual(len(rep), 1, "the monthly point was swallowed and nobody was told")
        self.assertEqual(rep[0]["replaced"], ["2025-12"])
        self.assertEqual([], r.get("resolution_mixed") or [],
                         "resolved and still reported as a doubling")

    def test_a_stamp_survives_a_later_bare_month(self):
        """The reverse order. The finer date is knowledge, and a coarser write
        is not a reason to lose it — the month never overwrites the stamp."""
        (self.forms / "december.csv").write_text(STAMPED_DECEMBER, encoding="utf-8")
        self.ingest()

        r = self.add("2025-12", value=32.0)

        self.assertTrue(r["ok"], r)
        self.assertEqual(self.dates(), ["2025-12-20T07:30"])
        self.assertEqual(self.series()[0]["value"], 32.0, "the later write is the write")
        self.assertEqual(r.get("replaced"), ["2025-12"],
                         "the caller was not told its own date was not the one kept")
        self.assertEqual(r.get("date"), "2025-12-20T07:30")
        self.assertEqual(self.series()[0].get("date_source"), "form",
                         "the stamp was kept but its origin was rewritten as the hand entry's")

    def test_a_month_and_the_one_day_in_it_are_one_point(self):
        """Used to be reported and left standing — «a month entered from memory
        and a dated form may be two draws». With one day in the month there is
        one draw to be, and the day is its finer date."""
        self.add("2018-05")

        r = self.add("2018-05-22")

        self.assertEqual(self.dates(), ["2018-05-22"])
        self.assertEqual(r.get("replaced"), ["2018-05"])
        self.assertNotIn("resolution_mixed", r)

    def test_a_month_that_already_stands_beside_its_day_and_stamp_is_collapsed(self):
        """The state a profile was left in by the older stores: a month, its day
        AND its stamp — three points of one draw. The next write of any shape,
        the coarsest included, leaves one point: the three are a chain, so
        they are one draw and the month names it."""
        self.seed("2025-12", "2025-12-20", "2025-12-20T07:30")

        r = self.add("2025-12", value=31.0)

        self.assertEqual(self.dates(), ["2025-12-20T07:30"])
        self.assertEqual(r.get("replaced"), ["2025-12", "2025-12-20"])

    def test_what_the_monthly_point_recorded_travels_to_the_stamp(self):
        """What somebody wrote about the draw once is not a fresh dict's problem —
        the 251 pairs were collapsed by hand precisely to keep this."""
        self.add("2025-12")
        self.annotate(context="fasting", source="hand, from the December paper form")
        (self.forms / "december.csv").write_text(STAMPED_DECEMBER, encoding="utf-8")

        self.ingest()

        pt = self.series()[0]
        self.assertEqual(pt["date"], "2025-12-20T07:30")
        self.assertEqual(pt.get("context"), "fasting")
        self.assertEqual(pt.get("source"), "hand, from the December paper form")
        self.assertEqual(pt.get("date_source"), "form", "the stamp came off the form")

    def test_two_monthly_points_of_one_month_are_one(self):
        self.add("2025-12", value=30.0)
        self.add("2025-12", value=31.0)
        self.assertEqual(self.dates(), ["2025-12"])
        self.assertEqual(self.series()[0]["value"], 31.0)

    def test_a_leap_day_belongs_to_its_month(self):
        """The edge of the calendar the period comparison must not trip on: the
        29th of a leap February is a day of that month like any other."""
        self.add("2024-02")
        r = self.add("2024-02-29T08:00")
        self.assertEqual(self.dates(), ["2024-02-29T08:00"])
        self.assertEqual(r.get("replaced"), ["2024-02"])

    def test_the_rule_holds_for_a_point_entered_by_hand_on_the_command_line(self):
        """The rule is the store's, so `add-lab` cannot carry a different one.
        Through the real command, in a subprocess, against the same profile."""
        first = support.run_json(["add-lab", "ferritin", "2025-12", "30", "--unit", "ng/mL"],
                                 profile_dir=self.profile)
        self.assertTrue(first.get("ok"), first)

        r = support.run_json(["add-lab", "ferritin", "2025-12-20T07:30", "31", "--unit", "ng/mL"],
                             profile_dir=self.profile)

        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r.get("replaced"), ["2025-12"])
        self.assertEqual(r.get("points"), 1)
        self.assertEqual(self.dates(), ["2025-12-20T07:30"])


class TestADayAndItsStampAreOnePoint(_Profile):

    def test_a_bare_day_is_replaced_by_the_stamped_re_import(self):
        """The order the defect was found in: hand entry first, form second."""
        self.assertTrue(self.add("2018-05-22")["ok"])
        (self.forms / "panel.csv").write_text(STAMPED, encoding="utf-8")

        r = self.ingest()

        self.assertEqual(r["points_added"], 1, r)
        self.assertEqual(self.dates(), ["2018-05-22T08:22"],
                         "the same draw stands in the series twice")
        self.assertEqual(self.series()[0]["value"], 31.0)

    def test_a_stamp_survives_a_later_bare_day(self):
        """The reverse order: the form was read first, the hand entry came later.
        The finer date is knowledge, and a coarser write is not a reason to lose it."""
        (self.forms / "panel.csv").write_text(STAMPED, encoding="utf-8")
        self.ingest()

        r = self.add("2018-05-22", value=32.0)

        self.assertTrue(r["ok"], r)
        self.assertEqual(self.dates(), ["2018-05-22T08:22"])
        self.assertEqual(self.series()[0]["value"], 32.0, "the later write is the write")
        self.assertEqual(r.get("replaced"), ["2018-05-22"],
                         "the caller was not told its own date was not the one kept")
        self.assertEqual(r.get("date"), "2018-05-22T08:22")

    def test_the_replacement_is_named_in_the_importer_report(self):
        self.add("2018-05-22")
        (self.forms / "panel.csv").write_text(STAMPED, encoding="utf-8")

        r = self.ingest()

        rep = [x for x in r.get("same_day_replaced") or [] if x["marker"] == "ferritin"]
        self.assertEqual(len(rep), 1, "a hand entry was swallowed and nobody was told")
        self.assertEqual(rep[0]["replaced"], ["2018-05-22"])
        self.assertEqual([], r.get("resolution_mixed") or [],
                         "resolved and still reported as a doubling")
        from scholion import format as fmt
        self.assertIn("2018-05-22T08:22", fmt.ingest_labs_report(r))

    def test_a_day_that_already_stands_twice_is_collapsed_by_the_next_write(self):
        """The state the real profile was left in: a day AND its stamp. The next
        write of either shape leaves one point, not two or three."""
        self.seed("2018-05-22", "2018-05-22T08:22")

        self.add("2018-05-22", value=31.0)

        self.assertEqual(self.dates(), ["2018-05-22T08:22"])


class TestProvenanceSurvivesTheReplacement(_Profile):

    def test_context_and_source_travel_to_the_new_point(self):
        """What somebody wrote about the draw once is not a fresh dict's problem."""
        self.add("2018-05-22")
        self.annotate(context="fasting, before the infusion", source="hand, from the paper form")
        (self.forms / "panel.csv").write_text(STAMPED, encoding="utf-8")

        self.ingest()

        pt = self.series()[0]
        self.assertEqual(pt["date"], "2018-05-22T08:22")
        self.assertEqual(pt.get("context"), "fasting, before the infusion")
        self.assertEqual(pt.get("source"), "hand, from the paper form")
        self.assertEqual(pt.get("date_source"), "form", "the stamp came off the form")

    def test_the_date_source_follows_the_date_that_was_kept(self):
        (self.forms / "panel.csv").write_text(STAMPED, encoding="utf-8")
        self.ingest()

        self.add("2018-05-22", date_source="manual")

        pt = self.series()[0]
        self.assertEqual(pt["date"], "2018-05-22T08:22")
        self.assertEqual(pt.get("date_source"), "form",
                         "the stamp was kept but its origin was rewritten as the hand entry's")

    def test_an_exact_re_import_keeps_the_draw_context(self):
        """The same stamp written twice — the ordinary re-import — used to lose
        `draw_context` too, because a replacement was a fresh dict."""
        self.add("2018-05-22T08:22")
        self.annotate(draw_context="before the dose")

        self.add("2018-05-22T08:22", value=33.0)

        self.assertEqual(self.series()[0].get("draw_context"), "before the dose")
        self.assertEqual(self.series()[0]["value"], 33.0)


class TestWhatIsNotOneDrawIsNotCollapsed(_Profile):

    def test_a_bare_day_against_two_draws_of_that_day_guesses_nothing(self):
        """Blood before a procedure and after it: two draws, both kept. A bare
        day cannot say which of them it is, so it replaces neither and the
        mixture is reported for the person to settle."""
        self.add("2018-05-22T08:22", value=31.0)
        self.add("2018-05-22T16:40", value=29.0)

        r = self.add("2018-05-22", value=30.0)

        self.assertEqual(self.dates(), ["2018-05-22", "2018-05-22T08:22", "2018-05-22T16:40"])
        self.assertEqual(r.get("resolution_mixed"), ["2018-05-22T08:22", "2018-05-22T16:40"])
        self.assertNotIn("replaced", r)

    def test_a_bare_month_against_two_days_of_that_month_guesses_nothing(self):
        """The same shape one resolution up: two days in the month are two
        draws, and a month names neither."""
        self.add("2025-12-05", value=31.0)
        self.add("2025-12-20", value=29.0)

        r = self.add("2025-12", value=30.0)

        self.assertEqual(self.dates(), ["2025-12", "2025-12-05", "2025-12-20"])
        self.assertEqual(r.get("resolution_mixed"), ["2025-12-05", "2025-12-20"])
        self.assertNotIn("replaced", r)

    def test_a_bare_month_against_a_day_and_a_draw_of_another_day_guesses_nothing(self):
        """Two draws at two resolutions inside the month. They are not a chain —
        the draw of the 20th does not hold the 5th — so they are two, and the
        month is not folded into either."""
        self.add("2025-12-05", value=31.0)
        self.add("2025-12-20T07:30", value=29.0)

        r = self.add("2025-12", value=30.0)

        self.assertEqual(self.dates(), ["2025-12", "2025-12-05", "2025-12-20T07:30"])
        self.assertEqual(r.get("resolution_mixed"), ["2025-12-05", "2025-12-20T07:30"])
        self.assertNotIn("replaced", r)

    def test_two_stamps_of_one_day_are_two_points(self):
        self.add("2018-05-22T08:22", value=31.0)
        self.add("2018-05-22T16:40", value=29.0)
        self.assertEqual(len(self.series()), 2)

    def test_two_days_of_one_month_are_two_points(self):
        self.add("2025-12-05", value=31.0)
        r = self.add("2025-12-20", value=29.0)
        self.assertEqual(self.dates(), ["2025-12-05", "2025-12-20"])
        self.assertNotIn("resolution_mixed", r)
        self.assertNotIn("replaced", r)

    def test_a_day_of_another_month_is_not_the_month(self):
        """The period comparison is on the calendar, not on the first characters
        that happen to agree: `2025-1` is a prefix of both `2025-11` and
        `2025-12`, and neither holds the other."""
        self.add("2025-11")
        r = self.add("2025-12-20T07:30")
        self.assertEqual(self.dates(), ["2025-11", "2025-12-20T07:30"])
        self.assertNotIn("replaced", r)
        self.assertNotIn("resolution_mixed", r)


class TestWhatIsNotADateHoldsNothing(unittest.TestCase):
    """The one comparison refuses before it compares: a string the date gate
    would not let through holds no period and is held by none. Without this the
    prefix rule would make «2025» hold every point of 2025 — or an empty string
    hold everything."""

    def test_a_non_date_holds_nothing_and_is_held_by_nothing(self):
        from scholion import store
        for bad in ("", "2025", "not-a-date", "2025-12-2"):
            with self.subTest(bad=bad):
                self.assertFalse(store._holds(bad, "2025-12-20"))
                self.assertFalse(store._holds("2025-12", bad))
        self.assertTrue(store._holds("2025-12", "2025-12-20T07:30"))


if __name__ == "__main__":
    unittest.main()
