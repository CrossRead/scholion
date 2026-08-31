"""A month is one number, and one number cannot say whether it is a measurement.

Measured on twelve months of this project's own wearable data: the spread of deep
sleep WITHIN a month is about 20.6 min, while the spread BETWEEN the twelve monthly
means is 4.05 — against 3.90 expected from sampling alone. Some 92% of the visible
movement of that series is the sample rather than the sleeper, and the true
month-to-month movement is on the order of 1.1 min. The application nonetheless
reported a direction for it, in the same words and with the same confidence as a
real fifteen-minute shift.

The fix is not daily data. It is that a point carries what it stands on — how many
days had a reading, how many the month had, the median beside the mean and the
spread — and that the sentence about a shift knows the smallest difference this
sample can distinguish. Below that, no direction is claimed at all.

Two things are load-bearing here and are asserted rather than assumed:

  · the information can only be kept at the moment of the fold. The daily values
    exist in the builder and nowhere afterwards, so a point without its `n` can
    never be given one later;
  · a series that does NOT describe its sample must behave exactly as before —
    an older file, another device's reader — and must not have a spread invented
    for it. Silence is the correct answer, not a guess.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path


def _builder():
    """The Garmin reader lives outside the package, next to the other ingests."""
    p = support.ROOT / "src" / "ingest" / "ingest_garmin.py"
    spec = importlib.util.spec_from_file_location("_g_for_tests", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = _builder()


class TestTheFoldKeepsItsArithmetic(unittest.TestCase):

    def test_a_month_says_how_many_days_carried_a_reading(self):
        st = G._stats([60, 62, 58, 61], "2024-10")
        self.assertEqual(st["n"], 4)
        self.assertEqual(st["days"], 31)

    def test_the_number_of_days_comes_from_a_calendar(self):
        self.assertEqual(G._stats([1], "2024-02")["days"], 29)
        self.assertEqual(G._stats([1], "2023-02")["days"], 28)

    def test_the_median_stands_beside_the_mean(self):
        """Steps are skewed — the mean sat above the median in ten months of
        twelve — so the median has to be there to be chosen later."""
        st = G._stats([10, 10, 10, 10, 1000], "2024-10")
        self.assertEqual(st["median"], 10)

    def test_one_day_has_no_spread_and_does_not_pretend_to(self):
        """`sd: 0.0` would read as «perfectly steady». There is nothing to
        compare, and the absence says so."""
        self.assertNotIn("sd", G._stats([57], "2024-10"))

    def test_a_month_with_no_readings_produces_nothing(self):
        self.assertIsNone(G._stats([], "2024-10"))

    def test_the_months_of_the_stats_are_the_months_of_the_series(self):
        daily = {"2024-09": [1, 2, 3], "2024-10": [], "2024-11": [5, 6]}
        self.assertEqual(sorted(G._monthly_stats(daily)), sorted(G._monthly(daily)))


class TestTheShiftConclusionKnowsWhatIsDistinguishable(unittest.TestCase):
    """`_life_metric` and `_smoothing_error` are closures inside `lifestyle()`, so
    they are exercised through the public answer with a profile built for it."""

    def _run(self, series, stats, direction="higher_better"):
        import os, shutil, tempfile, json
        import importlib
        from scholion import core
        # `scholion.engine` re-exports the FUNCTION under this name, so the
        # module has to be asked for by its full path.
        L = importlib.import_module("scholion.engine.lifestyle")
        tmp = Path(tempfile.mkdtemp(prefix="mdd-"))
        (tmp / "profile").mkdir()
        old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(tmp / "profile")
        core.reset_cache()
        try:
            (tmp / "profile" / "wearable_trends.json").write_text(json.dumps({
                "_meta": {"shape": "x"},
                "sources": {"garmin": {"metrics": {"DeepSleepMin": series},
                                       "stats": {"DeepSleepMin": stats} if stats else {}}},
            }), encoding="utf-8")
            core.reset_cache()
            out = L.lifestyle()
            for m in out.get("metrics") or []:
                if m["key"] == "DeepSleepMin":
                    return m
            return None
        finally:
            if old is None:
                os.environ.pop("SCHOLION_PROFILE_DIR", None)
            else:
                os.environ["SCHOLION_PROFILE_DIR"] = old
            core.reset_cache()
            shutil.rmtree(tmp, ignore_errors=True)

    #: Twelve months of a series that barely moves, with the spread this project
    #: actually measured: SD ≈ 20.6 min on ≈30 nights a month.
    MONTHS = [f"2024-{m:02d}" for m in range(1, 13)]
    #: A real drift of about 1.1 min over the year — the true month-to-month
    #: movement this project measured — which is well under what the sample can
    #: show. The delta must NOT be zero: a flat series gets no verdict for a
    #: different reason, and a test that passes for the wrong reason would keep
    #: passing with the rule removed.
    FLAT = {m: round(60 + i * 0.1 + (i % 3) * 0.05, 2) for i, m in enumerate(MONTHS)}
    NOISY_STATS = {m: {"n": 30, "days": 31, "median": 60, "sd": 20.6} for m in MONTHS}

    def test_a_movement_smaller_than_the_noise_gets_no_verdict(self):
        m = self._run(self.FLAT, self.NOISY_STATS)
        self.assertIsNotNone(m)
        # The premise: there IS a movement, it points somewhere, and it is real
        # arithmetic on the series. What it is not is distinguishable.
        self.assertNotEqual(m["trend"]["delta"], 0)
        self.assertNotEqual(m["trend"]["direction"], "flat")
        self.assertIsNotNone(m["trend"].get("mdd"))
        self.assertFalse(m["trend"]["distinguishable"])
        self.assertIsNone(m["trend_good"])

    def test_the_smallest_visible_difference_matches_the_hand_calculation(self):
        """The same arithmetic the hand calculation used, at the window this
        engine actually smooths over.

        SD 20.6 on 30 nights gives a month a standard error of 20.6/√30 = 3.76.
        The hand calculation that raised this task reported ≈10.8 min for one
        month against one (1.96·√2·3.76 = 10.4) and ≈7.6 for two against two
        (1.96·√2·3.76/√2 = 7.4). This engine smooths over three, so the same
        formula gives 1.96·√2·3.76/√3 = 6.0 — a narrower window is what more
        months buy.

        Pinned because a formula nobody checks against a number computed by hand
        drifts silently, and every conclusion above it drifts with it.
        """
        m = self._run(self.FLAT, self.NOISY_STATS)
        self.assertAlmostEqual(m["trend"]["mdd"], 6.0, delta=0.3)

    def test_a_real_shift_is_still_called_one(self):
        """The gate must not silence everything: a movement well above the noise
        keeps its verdict."""
        big = dict(self.FLAT)
        for m_ in self.MONTHS[-4:]:
            big[m_] = 95.0
        m = self._run(big, self.NOISY_STATS)
        self.assertTrue(m["trend"]["distinguishable"])
        self.assertIs(m["trend_good"], True)

    def test_a_series_without_a_described_sample_behaves_as_before(self):
        """An older file, or a reader that does not describe its months. No
        `mdd`, no silencing, and no invented spread."""
        m = self._run(self.FLAT, None)
        self.assertNotIn("mdd", m["trend"])
        self.assertNotIn("distinguishable", m["trend"])

    def test_a_month_measured_on_part_of_itself_says_so(self):
        stats = dict(self.NOISY_STATS)
        stats[self.MONTHS[-1]] = {"n": 19, "days": 31, "median": 60, "sd": 20.6}
        m = self._run(self.FLAT, stats)
        self.assertEqual(m["coverage"], {"n": 19, "days": 31})

    def test_a_month_measured_in_full_needs_no_note(self):
        m = self._run(self.FLAT, self.NOISY_STATS)
        self.assertEqual(m["coverage"], {"n": 30, "days": 31})


class TestTheSampleTravelsWithTheSeries(unittest.TestCase):
    """Kept at the fold, and then kept all the way to the file — otherwise the
    arithmetic above has nothing to read."""

    def test_the_builder_emits_a_stats_block_beside_the_metrics(self):
        src = G.__dict__
        self.assertIn("_monthly_stats", src)
        self.assertIn("_stats", src)
        text = (support.ROOT / "src" / "ingest" / "ingest_garmin.py").read_text(encoding="utf-8")
        self.assertIn('"stats"', text,
                      "the reader no longer puts the sample beside the series")

    def test_the_merge_carries_the_stats_of_a_month_the_export_lacks(self):
        """The same protection the series has: an export that did not download in
        full cannot erase what an earlier one measured — and it must not leave the
        value of a month behind without its sample, or the two drift apart."""
        from scholion import wearables
        fresh = {"metrics": {"DeepSleepMin": {"2024-12": 61.0}},
                 "stats": {"DeepSleepMin": {"2024-12": {"n": 30, "days": 31, "sd": 20.0}}}}
        previous = {"_meta": {"shape": "x"}, "sources": {"garmin": {
            "metrics": {"DeepSleepMin": {"2024-11": 59.0}},
            "stats": {"DeepSleepMin": {"2024-11": {"n": 28, "days": 30, "sd": 19.0}}}}}}
        kept = wearables._merge(fresh, previous, "garmin")
        self.assertEqual(kept, 1, "the count is of series months, not of both blocks")
        self.assertEqual(sorted(fresh["metrics"]["DeepSleepMin"]), ["2024-11", "2024-12"])
        self.assertEqual(sorted(fresh["stats"]["DeepSleepMin"]), ["2024-11", "2024-12"])

    def test_a_device_that_describes_nothing_grows_no_empty_block(self):
        from scholion import wearables
        fresh = {"metrics": {"X": {"2024-12": 1.0}}}
        wearables._merge(fresh, {}, "whoop")
        self.assertNotIn("stats", fresh)


if __name__ == "__main__":
    unittest.main()
