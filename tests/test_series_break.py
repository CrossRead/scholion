"""A break in the series when the device changes does not turn into a conclusion about deterioration.

A real case: the monthly sleep duration starts in 2017-12 at a value of 8.6 h —
that is the old watch, which counted time in bed as sleep. The current one gives
7.0-7.4. The application compared the last value with the first and confidently
reported "sleep has got worse by 1.6 hours", that is, it compared two devices.
The baseline is obliged to be counted from the month from which the series is
comparable with itself.
"""
import unittest

from scholion import engine


SERIES = {
    "2017-12": 8.6, "2018-06": 8.4, "2019-06": 8.8,          # the old device
    "2022-01": 7.2, "2023-01": 7.4, "2024-01": 7.4,          # the current one
    "2025-01": 7.0, "2026-01": 7.0,
}
INFO = {"label": "Sleep", "unit": "h/night", "direction": "higher_better", "target_low": 7.5}


def _metric(since):
    fn = engine.lifestyle.__globals__.get("_life_metric")
    if fn is None:                       # the function is local — we get at it through the call
        raise unittest.SkipTest("_life_metric is not reachable on its own")
    return fn("SleepHours", INFO, SERIES, since)


class TestComparabilityMark(unittest.TestCase):
    """We check through the public entry point rather than through the internal
    function: what matters is the behaviour of the application, not how it is
    arranged inside."""

    def _lifestyle_with(self, meta):
        data = {"_meta": meta, "metrics": {"SleepHours": SERIES}}
        return data

    def test_without_the_mark_the_baseline_is_the_first_point(self):
        """The previous behaviour is preserved: no key — we count over the whole series."""
        from scholion import core
        real = core.wearable_trends
        core.wearable_trends = lambda: self._lifestyle_with({})
        try:
            m = next(x for x in engine.lifestyle()["metrics"] if x["key"] == "SleepHours")
        finally:
            core.wearable_trends = real
        self.assertEqual(m["first_date"], "2017-12")
        self.assertIsNone(m.get("comparable_from"))

    def test_with_the_mark_the_baseline_is_counted_from_it(self):
        from scholion import core
        real = core.wearable_trends
        core.wearable_trends = lambda: self._lifestyle_with(
            {"comparable_from": {"SleepHours": "2022-01"}})
        try:
            m = next(x for x in engine.lifestyle()["metrics"] if x["key"] == "SleepHours")
        finally:
            core.wearable_trends = real
        self.assertEqual(m["first_date"], "2022-01", "the baseline was taken from the incomparable part of the series")
        self.assertEqual(m["comparable_from"], "2022-01")
        self.assertGreater(m["overall_delta"], -1.0,
                           "the drop is still being counted from another device")

    def test_a_mark_from_the_future_does_not_eat_the_series(self):
        """A cut-off that no point falls under is wrong — then returning to the
        full series is more honest than showing emptiness."""
        from scholion import core
        real = core.wearable_trends
        core.wearable_trends = lambda: self._lifestyle_with(
            {"comparable_from": {"SleepHours": "2099-01"}})
        try:
            m = next(x for x in engine.lifestyle()["metrics"] if x["key"] == "SleepHours")
        finally:
            core.wearable_trends = real
        self.assertEqual(m["first_date"], "2017-12")
        self.assertIsNone(m.get("comparable_from"))


if __name__ == "__main__":
    unittest.main()
