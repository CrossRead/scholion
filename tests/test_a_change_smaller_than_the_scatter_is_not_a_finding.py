"""An arrow on a laboratory series says the person moved. Often it says the scatter did.

`↑ 44 % since the previous measurement` is arithmetic on two numbers and it is
true. What it is not is a finding: a series moves for three reasons — the
analyser, the person's own day-to-day biology, and an actual change — and only
the third deserves an arrow read as a finding. Two draws on ONE day were already
excluded from this comparison for exactly that reason; two draws a month apart
that differ by nothing but scatter were not.

The textbook route is the reference change value from published coefficients of
analytical and within-subject variation. Those are not in this build and are not
invented here: typing clinical numbers from memory is the one thing this project
never does. So the scatter is MEASURED instead, from the same marker in the same
person — the history already contains it.

Three properties are load-bearing and are asserted rather than described:

  · the estimate is conservative BY CONSTRUCTION. It contains real change as well
    as scatter, so it is an upper bound: what it calls indistinguishable is, while
    what it calls distinguishable is merely not excluded. The error falls on the
    side of claiming less;
  · it refuses on a history too short to support it — the wearable layer's own
    lesson, applied here before the same mistake is made in the other direction;
  · a rule that suggests a test on a direction no longer fires on a movement the
    series cannot distinguish. A suggested test costs a real draw.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path

from scholion.engine.labs import _trend, change_floor


def series(values, month_start=1, year=2024):
    """One measurement a month, so nothing is excluded as a same-day pair."""
    out = []
    y, m = year, month_start
    for v in values:
        out.append({"date": f"{y}-{m:02d}-01", "value": v})
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


#: A marker that wobbles by a few per cent and goes nowhere.
WOBBLE = [5.0, 5.4, 5.1, 5.5, 5.2, 5.6, 5.3, 5.5, 5.2, 5.4]


class TestTheHistoryIsAllowedToSpeakOnlyWhenItCan(unittest.TestCase):

    def test_a_short_history_says_nothing(self):
        self.assertIsNone(change_floor(series(WOBBLE[:4])))

    def test_a_history_long_enough_gives_a_floor_and_names_its_evidence(self):
        f = change_floor(series(WOBBLE))
        self.assertIsNotNone(f)
        self.assertEqual(f["from"], "own_history")
        self.assertEqual(f["pairs"], len(WOBBLE) - 1)
        self.assertGreater(f["rcv_pct"], 0)

    def test_a_series_that_never_moved_says_nothing(self):
        """No scatter at all is not «infinitely sensitive» — it is a series that
        cannot support the statement."""
        self.assertIsNone(change_floor(series([5.0] * 10)))

    def test_a_value_at_or_below_zero_is_refused_rather_than_divided_by(self):
        self.assertIsNone(change_floor(series([5.0, 5.2, 0.0, 5.1, 5.3, 5.0, 5.2])))

    def test_two_draws_of_one_day_are_not_scatter(self):
        """The same exclusion the trend makes: they differ because of what
        happened between them."""
        same_day = [{"date": "2024-01-01T09:00", "value": 5.0},
                    {"date": "2024-01-01T15:00", "value": 9.0}]
        with_pair = change_floor(same_day + series(WOBBLE, month_start=2))
        without = change_floor(series(WOBBLE))
        # The 80% jump between the two draws of that morning is not in the
        # scatter: the floor stays where the monthly series put it.
        self.assertLess(with_pair["rcv_pct"], without["rcv_pct"] * 1.5)
        self.assertLess(with_pair["rcv_pct"], 30)


class TestAnArrowThatCannotBeToldFromScatter(unittest.TestCase):

    def test_a_small_move_keeps_its_numbers_and_loses_its_claim(self):
        t = _trend(series(WOBBLE))
        self.assertIsNotNone(t["pct"])
        self.assertIn(t["direction"], ("up", "down"))
        self.assertFalse(t["distinguishable"])

    def test_a_large_move_is_still_a_move(self):
        t = _trend(series(WOBBLE + [9.0]))
        self.assertTrue(t["distinguishable"])

    def test_the_floor_travels_with_the_verdict(self):
        """A threshold nobody can see is one nobody can argue with."""
        t = _trend(series(WOBBLE))
        self.assertEqual(t["change_floor"]["from"], "own_history")
        self.assertGreater(t["change_floor"]["rcv_pct"], 0)

    def test_a_series_too_short_gets_no_verdict_either_way(self):
        t = _trend(series([5.0, 7.0, 5.1]))
        self.assertIsNotNone(t)
        self.assertNotIn("distinguishable", t)
        self.assertNotIn("change_floor", t)


class TestTheEstimateIsConservative(unittest.TestCase):

    def test_real_movement_raises_the_floor_rather_than_lowering_it(self):
        """The whole safety argument in one assertion. A series that really
        climbed contains that climb in its own differences, so its floor is
        HIGHER — the method claims less, never more."""
        flat = change_floor(series(WOBBLE))
        climbing = change_floor(series([v + i * 0.8 for i, v in enumerate(WOBBLE)]))
        self.assertGreater(climbing["rcv_pct"], flat["rcv_pct"])


class TestARuleDoesNotFireOnScatter(unittest.TestCase):
    """`test_rules.json` can suggest a test when a marker trends. A test suggested
    because of scatter costs a real draw of blood."""

    def _condition_fires(self, values):
        import json, os, shutil, tempfile
        from pathlib import Path
        from scholion import core
        from scholion.engine import labs as L
        tmp = Path(tempfile.mkdtemp(prefix="rcv-"))
        (tmp / "profile").mkdir()
        old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(tmp / "profile")
        core.reset_cache()
        try:
            (tmp / "profile" / "labs.json").write_text(json.dumps({
                "markers": {"glucose": {"name": "Glucose", "unit": "mmol/L",
                                        "series": series(values)}}}), encoding="utf-8")
            core.reset_cache()
            return L._eval_condition({"trend": {"marker": "glucose", "direction": "up"}})
        finally:
            if old is None:
                os.environ.pop("SCHOLION_PROFILE_DIR", None)
            else:
                os.environ["SCHOLION_PROFILE_DIR"] = old
            core.reset_cache()
            shutil.rmtree(tmp, ignore_errors=True)

    def test_scatter_does_not_suggest_a_test(self):
        self.assertFalse(self._condition_fires(WOBBLE))

    def test_a_real_climb_still_does(self):
        self.assertTrue(self._condition_fires(WOBBLE + [9.0]))


if __name__ == "__main__":
    unittest.main()
