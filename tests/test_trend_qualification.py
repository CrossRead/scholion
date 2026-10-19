"""A visible movement is not necessarily a supported change."""
import unittest

import support  # noqa: F401
from scholion.trend_qualification import comparable_observations, wearable_comparison


class QualificationTests(unittest.TestCase):
    def points(self):
        return ({"date": "2026-08", "source": "garmin", "value": 60,
                 "stats": {"n": 28, "days": 31, "sd": 3, "median": 60}},
                {"date": "2026-09", "source": "garmin", "value": 70,
                 "stats": {"n": 28, "days": 30, "sd": 3, "median": 70}})

    def test_supported_mean_change(self):
        r = wearable_comparison("RestingHeartRate", *self.points())
        self.assertTrue(r["eligible"])
        self.assertTrue(r["distinguishable"])
        self.assertGreater(r["mdd"], 0)

    def test_coverage_device_spread_and_overlap_withhold_same_change(self):
        for mutation, reason in (({"source": "whoop"}, "device_changed"),
                                 ({"date": "2026-08"}, "overlapping_periods"),
                                 ({"stats": {"n": 4, "days": 30, "sd": 3}}, "insufficient_coverage"),
                                 ({"stats": {"n": 28, "days": 30}}, "spread_unknown")):
            with self.subTest(reason=reason):
                a, b = self.points()
                b.update(mutation)
                r = wearable_comparison("RestingHeartRate", a, b)
                self.assertFalse(r["eligible"])
                self.assertIsNone(r["distinguishable"])
                self.assertIn(reason, r["reasons"])

    def test_steps_use_median_without_borrowing_mean_error(self):
        a, b = self.points()
        b["value"] = 1000
        b["stats"]["median"] = 60
        r = wearable_comparison("Steps", a, b)
        self.assertEqual(r["statistic"], "median")
        self.assertEqual(r["delta"], 0)
        self.assertIsNone(r["mdd"])
        self.assertFalse(r["eligible"])
        for p in (a, b):
            p["stats"]["median_interval"] = [58, 62]
        self.assertFalse(wearable_comparison("Steps", a, b)["distinguishable"])

    def test_independent_draws_not_duplicate_rows(self):
        a = {"date": "2026-09-01", "value": 4}
        self.assertFalse(comparable_observations([a, a])["eligible"])
        b = {"date": "2026-09-10", "value": 5}
        self.assertTrue(comparable_observations([a, b])["eligible"])
        for field, value in (("censored", "<"), ("value", float("nan"))):
            self.assertFalse(comparable_observations([a, {**b, field: value}])["eligible"])

    def test_method_switch_is_not_a_trend(self):
        self.assertFalse(comparable_observations([
            {"date": "2026-08-01", "value": 4, "method": "a"},
            {"date": "2026-09-01", "value": 6, "method": "b"}])["eligible"])

    def test_ingest_median_interval_is_robust_to_an_isolated_outlier(self):
        from tests.test_a_monthly_point_says_what_it_stands_on import G
        first = [50+i%5 for i in range(30)]
        second = first[:-1] + [10000]
        a, b = self.points()
        a['stats'], b['stats'] = G._stats(first, '2026-08'), G._stats(second, '2026-09')
        a['value'], b['value'] = sum(first)/30, sum(second)/30
        result = wearable_comparison('Steps', a, b)
        self.assertTrue(result['eligible'])
        self.assertFalse(result['distinguishable'])
        self.assertNotEqual(a['value'], b['value'])
        self.assertEqual(result['delta'], 0)
        self.assertEqual(wearable_comparison('IntensityMinutesDaily', a, b)['statistic'], 'median')
        b['stats'] = G._stats([100+i%5 for i in range(30)], '2026-09')
        self.assertTrue(wearable_comparison('Steps', a, b)['distinguishable'])

    def test_installed_reader_does_not_depend_on_a_source_checkout(self):
        from unittest import mock
        from scholion import wearables
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            package = root / "site-packages" / "scholion"
            (package / "readers").mkdir(parents=True)
            module = package / "wearables.py"
            module.write_text("", encoding="utf-8")
            (package / "readers" / "ingest_garmin.py").write_text("MARKER = 'installed-reader'", encoding="utf-8")
            with mock.patch.object(wearables, "__file__", str(module)), \
                    mock.patch.object(wearables.core, "repo_dir", return_value=root / "absent-source"):
                self.assertEqual(wearables._builder("ingest_garmin.py").MARKER, "installed-reader")


class AnnualWindowTests(unittest.TestCase):
    def test_calendar_halves_are_descriptive_and_use_all_readings(self):
        from scholion.trend_qualification import period_shift
        points=[{'date':d,'value':v,'method':'same'} for d,v in zip(
            ['2026-01-01','2026-03-01','2026-07-01','2026-10-01'],[2,3,5,6])]
        result=period_shift(points)
        self.assertTrue(result['eligible'])
        self.assertEqual(result['before_range'],[2,3])
        self.assertEqual(result['after_range'],[5,6])
        for change in ('same_date','method','censored','overlap','short','nonnumeric'):
            sample=[dict(p) for p in points]
            if change=='same_date':sample[1]['date']=sample[0]['date']
            if change=='method':sample[1]['method']='other'
            if change=='censored':sample[1]['censored']='>'
            if change=='overlap':sample[2]['value']=2
            if change=='short':sample=sample[-2:]
            if change=='nonnumeric':sample[0]['value']=float('nan')
            self.assertFalse(period_shift(sample)['eligible'],change)

    def test_monthly_device_means_are_not_exact_lab_draws(self):
        from scholion.trend_qualification import period_shift
        points=[{'date':d,'value':v} for d,v in zip(['2026-01','2026-03','2026-07','2026-10'],[2,3,5,6])]
        self.assertFalse(period_shift(points)['eligible'])
        result=period_shift(points,monthly=True)
        self.assertTrue(result['eligible'])
        self.assertEqual(result['statistic'],'monthly_means')


class FormingAnnualDirection(unittest.TestCase):
    def test_overlapping_ranges_can_form_a_direction(self):
        from scholion.trend_qualification import period_shift
        points = [{"date": f"2026-{i+1:02d}-01", "value": v, "unit": "u", "method": "same"}
                  for i,v in enumerate([10, 12, 11, 14, 13, 13.5, 16, 15, 18])]
        result = period_shift(points)
        self.assertTrue(result['eligible'])
        self.assertEqual(result['stage'], 'forming')
        self.assertGreater(result['median_slope_per_year'], 0)
        self.assertGreaterEqual(result['concordance'], 2/3)

    def test_an_isolated_last_peak_or_random_oscillation_is_not_a_trend(self):
        from scholion.trend_qualification import period_shift
        for values in ([10,10,10,10,10,10,10,10,50], [10,14,9,14,10,14,9,14,10]):
            points = [{"date": f"2026-{i+1:02d}-01", "value": v} for i,v in enumerate(values)]
            self.assertFalse(period_shift(points)['eligible'])


class RecentAndSingleReadings(unittest.TestCase):
    def test_short_windows_require_independent_draws_and_remain_forming(self):
        from datetime import date, timedelta
        from scholion.trend_qualification import period_shift
        for window,span in ((30,21),(90,60)):
            points=[{'date':(date(2026,10,18)-timedelta(days=span-i*span//3)).isoformat(),
                     'value':v} for i,v in enumerate((4,5,6,7))]
            result=period_shift(points,window=window)
            self.assertTrue(result['eligible'])
            self.assertEqual(result['stage'],'forming')
            self.assertFalse(period_shift(points)['eligible'])
            self.assertFalse(period_shift(points[:1],window=window)['eligible'])
            points[1]['method']='a';points[2]['method']='b'
            self.assertFalse(period_shift(points,window=window)['eligible'])
        with self.assertRaises(ValueError):period_shift([],window=7)

    def test_one_normal_measurement_needs_no_trend_to_be_in_range(self):
        from datetime import date
        from scholion.trend_qualification import reading_status
        p={'date':'2026-10-18','value':4,'ref_low':1,'ref_high':5}
        now=date(2026,10,18)
        self.assertEqual(reading_status(p,now),'within')
        self.assertEqual(reading_status({**p,'value':6},now),'outside')
        for update in ({'date':'2020-01-01'}, {'date':'2027-01-01'}, {'censored':'<'},
                       {'reference_withheld':True}, {'ref_low':9}, {'value':float('nan')},
                       {'ref_low':None,'ref_high':None}, {'proposed_rule':True}):
            self.assertEqual(reading_status({**p,**update},now),'unknown')
