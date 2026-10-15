"""Summaries cannot turn measurement bounds or unknown dates into exact facts."""
from __future__ import annotations

import datetime
from importlib import import_module
import unittest
import shutil
import subprocess
from unittest import mock

import support  # noqa: F401
from scholion import i18n
from scholion.engine import _helpers, labs, profile_view

radar = import_module("scholion.engine.lifestyle")

brief_review = import_module("scholion.engine.brief_review")


class FrozenDate(datetime.date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 11)


class BoundFacts(unittest.TestCase):
    def test_brief_review_uses_the_laboratory_bound_flag(self):
        for censor, low, high, expected in ((">", None, 5, "high"), ("<", 5, None, "low")):
            point = {"date": "2026-10-01", "value": 5, "censored": censor}
            result = brief_review._point(point, low, high)
            self.assertEqual(expected, result["status"])
            self.assertEqual(labs._flag_value({"ref_low": low, "ref_high": high}, 5, censor), result["status"])
            self.assertEqual(censor, result.get("censored"))

    def test_bound_sign_survives_review_text_in_both_languages(self):
        self.addCleanup(i18n.set_lang, getattr(i18n._state, "current", None))
        for language in ("en", "ru"):
            i18n.set_lang(language)
            after = brief_review._point({"date": "2026-10-01", "value": 5, "censored": ">"}, None, 5)
            text = brief_review._change_line({"name": "Synthetic", "unit": "unit", "before": None, "after": [after]})
            self.assertIn(">5", text)
            self.assertIn(i18n.t("brief.review.status.high"), text)

    def test_bounded_pair_does_not_claim_exact_delta_or_percent(self):
        for censor in ("<", ">", "<=", ">="):
            points = [{"date": "2026-09-01", "value": 10},
                      {"date": "2026-10-01", "value": 5, "censored": censor}]
            self.assertIsNone(labs._trend(points))
            self.assertIsNone(labs._trend(list(reversed(points))))


    def test_radar_does_not_score_either_end_of_a_bounded_comparison(self):
        raw = {"ref_low": 3, "ref_high": 6}
        for sign in ("<", ">", "<=", ">="):
            point = {"date": "2026-10-01", "value": 6, "censored": sign}
            self.assertIsNone(radar._marker_health(dict(raw, value=6, flag="high", censored=sign)))
            with mock.patch.object(radar.core, "labs", return_value={"markers": {"glucose": raw}}):
                self.assertIsNone(radar._marker_health_at("glucose", point))
        self.assertEqual(100, radar._marker_health(dict(raw, value=5, flag="ok")))

    def test_radar_keeps_bounded_deviations_without_a_false_index_or_delta(self):
        marker = {"key": "glucose", "name": "Synthetic", "value": 6, "unit": "mmol/L",
                  "date": "2026-10-01", "censored": ">", "flag": "high", "abnormal": True,
                  "ref_low": 3, "ref_high": 6}
        with mock.patch.object(radar, "analyze_labs", return_value={"markers": [marker]}), \
             mock.patch.object(radar, "_RADAR_DOMAINS", [("glucose", ["glucose"])]), \
             mock.patch.object(radar, "_panel_term", return_value=None), \
             mock.patch.object(radar, "lifestyle", return_value={}):
            result = radar.health_radar()
        domain = result["domains"][0]
        self.assertIsNone(domain["score"])
        self.assertIsNone(domain["delta"])
        self.assertEqual([], domain["moved"])
        self.assertEqual(">", domain["abnormal"][0]["censored"])
        self.assertIsNone(result["overall_delta"])

    def test_exact_pair_still_has_its_actual_change(self):
        result = labs._trend([{"date": "2026-09-01", "value": 10},
                              {"date": "2026-10-01", "value": 5}])
        self.assertEqual(-50, result["pct"])
        self.assertEqual(-5, result["delta"])

    def test_scatter_and_personal_shift_do_not_use_a_bound_as_an_exact_value(self):
        points = [{"date": f"2026-{n:02d}-01", "value": value}
                  for n, value in enumerate((5, 5.1, 5.2, 5.3, 5.2, 10), 1)]
        points[2]["censored"] = "<"
        self.assertIsNone(labs.change_floor(points))
        self.assertIsNone(labs._personal_move(points))

    def test_brief_cannot_assign_a_numeric_direction_to_a_bound(self):
        marker = {"name": "Synthetic", "series": [
            {"date": "2026-09-01", "value": 10},
            {"date": "2026-10-01", "value": 5, "censored": "<"}]}
        with mock.patch.object(brief_review.core, "labs", return_value={"markers": {"synthetic": marker}}):
            result = brief_review._marker_changes("synthetic", "2026-09-15")
        self.assertIsNone(result["direction"])
        self.assertEqual("<", result["after"][0].get("censored"))


    def test_same_day_bounds_do_not_claim_an_exact_difference(self):
        result = labs.same_day_repeats([
            {"date": "2026-10-01T08:00", "value": 10},
            {"date": "2026-10-01T12:00", "value": 5, "censored": "<"}])[0]
        self.assertIsNone(result["delta"])
        self.assertEqual("<", result["points"][1]["censored"])

    def test_review_does_not_borrow_a_withheld_or_proposed_corridor(self):
        for proposed, withheld in ((True, False), (False, True)):
            marker = {"name": "Synthetic", "ref_low": 1, "ref_high": 5,
                      "series": [{"date": "2026-10-01", "value": 10,
                                  "reference_withheld": withheld}]}
            with mock.patch.object(brief_review.core, "labs", return_value={"markers": {"synthetic": marker}}), \
                 mock.patch.object(brief_review.core, "lab_markers", return_value={
                     "markers": {"synthetic": {"status": "proposed" if proposed else "confirmed"}}}):
                result = brief_review._marker_changes("synthetic", "2026-09-15")
            self.assertEqual("unknown", result["after"][0]["status"])


class RecentFacts(unittest.TestCase):
    def setUp(self):
        clock = mock.patch.object(_helpers.datetime, "date", FrozenDate)
        clock.start()
        self.addCleanup(clock.stop)

    def test_invalid_or_future_date_never_establishes_recently_done(self):
        for stamp in ("2099-01-01", "2026-12", "2026-99-01", "2026-02-30", "2026-10-01T99:00", "2026", "n/a"):
            with self.subTest(stamp=stamp):
                self.assertIsNone(_helpers._recent_or_unknown(stamp))

    def test_precision_and_sliding_window_are_preserved(self):
        for stamp in ("2026-10", "2026-10-11", "2026-10-10T12:34:00", "2025-10", "2025-10-11"):
            self.assertIs(True, _helpers._recent_or_unknown(stamp), stamp)
        for stamp in ("2025-09", "2025-10-10", "2024-10-11", ""):
            self.assertIs(False, _helpers._recent_or_unknown(stamp), stamp)
        self.assertIs(False, _helpers._recent_or_unknown("2026-07-10", months=3))
        self.assertIs(True, _helpers._recent_or_unknown("2026-07-11", months=3))

    def test_unknown_date_remains_visible_but_does_not_close_a_monitoring_gap(self):
        self.assertTrue(_helpers._recent("invalid"))
        self.assertIsNone(_helpers._recent_or_unknown("invalid"))
        self.assertFalse(_helpers._recent(""))

    def test_leap_day_cutoff_is_valid(self):
        with mock.patch.object(FrozenDate, "today", return_value=FrozenDate(2024, 2, 29)):
            self.assertTrue(_helpers._recent_or_unknown("2023-02-28"))
            self.assertFalse(_helpers._recent_or_unknown("2023-02-27"))


class OverviewFacts(unittest.TestCase):
    def test_unknown_flags_do_not_increase_the_abnormal_count(self):
        markers = [{"key": flag, "name": flag, "flag": flag, "abnormal": abnormal,
                    "date": "2026-10-01"} for flag, abnormal in (
                        ("high", True), ("low", True), ("unconfirmed_rule", False),
                        ("norange", False), ("ok", False))]
        with mock.patch.object(profile_view, "analyze_labs", return_value={"count": 5, "markers": markers}), \
             mock.patch.object(profile_view, "suggest_tests", return_value={"count": 0, "suggestions": []}), \
             mock.patch.object(profile_view, "_recent", return_value=True):
            result = profile_view.overview()
        self.assertEqual(2, result["abnormal_count"])
        self.assertEqual({"high", "low"}, {m["flag"] for m in result["flagged"]})
        self.assertEqual(0, result["stale_abnormal_count"])

    def test_unknown_historical_flag_is_not_a_stale_abnormality(self):
        markers = [{"key": "synthetic", "flag": "unconfirmed_rule", "abnormal": False, "date": "2020-01-01"}]
        with mock.patch.object(profile_view, "analyze_labs", return_value={"count": 1, "markers": markers}), \
             mock.patch.object(profile_view, "suggest_tests", return_value={"count": 0, "suggestions": []}):
            result = profile_view.overview()
        self.assertEqual(0, result["stale_abnormal_count"])
        self.assertEqual(0, result["abnormal_count"])


@unittest.skipUnless(shutil.which("node"), "needs node for page rendering")
class BoundWebFacts(unittest.TestCase):
    def test_cards_tables_and_trend_graph_keep_limits_distinct(self):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        functions = []
        for name in ("markerCard", "markerTable", "sparkline"):
            start = page.index("function " + name + "(")
            functions.append(page[start:page.index("\n}\n", start) + 2])
        script = r"""
const assert=require('node:assert/strict');
const esc=x=>String(x??''),fmtNum=String,fmtDate=String,t=x=>x,el=x=>x;
const flagOf=()=>({cls:'',key:''}),badge=()=>'',trendNote=()=>'',noteHtml=()=>'';
const decisionNote=()=>'',targetText=()=>'',targetAsk=()=>'',refText=()=>'';
const markerGeneticsRow=()=>'',windowSeries=s=>s;
""" + "\n".join(functions) + r"""
for(const sign of ['<','>']){
 const bounded={name:'Synthetic',value:6.1,censored:sign,unit:'mmol/L',date:'2026-10-15',
   series:[{date:'2026-09-15',value:5},{date:'2026-10-15',value:6.1,censored:sign}]};
 const before=JSON.stringify(bounded);
 for(const html of [markerCard(bounded),markerTable([bounded])]){
  assert.ok(html.includes(sign+'6.1'),html);
  assert.ok(!html.includes('<polyline'),html);
 }
 assert.equal(sparkline(bounded.series,false), '');
 assert.equal(JSON.stringify(bounded),before);
}
const exact=[{date:'2026-09-15',value:5},{date:'2026-10-15',value:6.1}];
assert.ok(sparkline(exact,false).includes('<polyline'));
"""
        result = subprocess.run([shutil.which("node")], input=script, text=True,
                                capture_output=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
