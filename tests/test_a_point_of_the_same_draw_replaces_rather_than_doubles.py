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

What these tests hold: a point of the same day replaces a point of the same
day, the finer date wins whichever order the two writes came in, what the
earlier point recorded about the draw survives the replacement, and the one
case that cannot be resolved — a bare day against two draws of that day — is
still not guessed at.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import support

STAMPED = """Date,Test,Result,Units,Reference Range
2018-05-22T08:22,Ferritin,31,ng/mL,13-150
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


class TestADayAndItsStampAreOnePoint(_Profile):

    def test_a_bare_day_is_replaced_by_the_stamped_re_import(self):
        """The order the defect was found in: hand entry first, form second."""
        self.assertTrue(self.add("2018-05-22")["ok"])
        (self.forms / "panel.csv").write_text(STAMPED, encoding="utf-8")

        r = self.ingest()

        self.assertEqual(r["points_added"], 1, r)
        self.assertEqual([pt["date"] for pt in self.series()], ["2018-05-22T08:22"],
                         "the same draw stands in the series twice")
        self.assertEqual(self.series()[0]["value"], 31.0)

    def test_a_stamp_survives_a_later_bare_day(self):
        """The reverse order: the form was read first, the hand entry came later.
        The finer date is knowledge, and a coarser write is not a reason to lose it."""
        (self.forms / "panel.csv").write_text(STAMPED, encoding="utf-8")
        self.ingest()

        r = self.add("2018-05-22", value=32.0)

        self.assertTrue(r["ok"], r)
        self.assertEqual([pt["date"] for pt in self.series()], ["2018-05-22T08:22"])
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
        self.add("2018-05-22")
        # Seed the doubled state directly, as the older store left it: going
        # through `add` would already apply the rule under test.
        p = self.profile / "labs.json"
        labs = json.loads(p.read_text(encoding="utf-8"))
        labs["markers"]["ferritin"]["series"] = [
            {"date": "2018-05-22", "value": 31.0}, {"date": "2018-05-22T08:22", "value": 31.0}]
        p.write_text(json.dumps(labs, ensure_ascii=False), encoding="utf-8")
        from scholion import core
        core.reset_cache()

        self.add("2018-05-22", value=31.0)

        self.assertEqual([pt["date"] for pt in self.series()], ["2018-05-22T08:22"])


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

        self.assertEqual([pt["date"] for pt in self.series()],
                         ["2018-05-22", "2018-05-22T08:22", "2018-05-22T16:40"])
        self.assertEqual(r.get("resolution_mixed"), ["2018-05-22T08:22", "2018-05-22T16:40"])
        self.assertNotIn("replaced", r)

    def test_two_stamps_of_one_day_are_two_points(self):
        self.add("2018-05-22T08:22", value=31.0)
        self.add("2018-05-22T16:40", value=29.0)
        self.assertEqual(len(self.series()), 2)

    def test_a_month_and_a_day_of_it_are_still_only_reported(self):
        """A month entered from memory and a dated form may be two draws of that
        month; that pair stays as it was — reported, not replaced."""
        self.add("2018-05")
        r = self.add("2018-05-22")
        self.assertEqual(r.get("resolution_mixed"), ["2018-05"])
        self.assertEqual([pt["date"] for pt in self.series()], ["2018-05", "2018-05-22"])


if __name__ == "__main__":
    unittest.main()
