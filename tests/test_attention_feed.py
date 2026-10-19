"""New findings need independent observations; all faces retain their evidence."""
from __future__ import annotations

import copy
import os
from datetime import date, timedelta
import tempfile
from pathlib import Path
from unittest import TestCase, mock

import support  # noqa: F401
from scholion import insight_history
from scholion.engine.insight_events import insight_events
from scholion.engine.insights import attention_feed
from scholion.period_summary import period_summary


class AttentionTests(TestCase):
    def test_unsupported_period_is_rejected_before_analysis(self):
        with self.assertRaisesRegex(ValueError, "30, 90 or 365"):
            attention_feed({}, [], [], {}, [], period=7)

    def test_unmapped_laboratory_change_does_not_invent_a_body_system(self):
        from scholion.engine.insights import _highlights
        item = {"id": "lab:synthetic-unmapped", "priority": 3,
                "facts": [{"record": "labs.json", "key": "synthetic-unmapped"}],
                "events": [{"kind": "period_shift"}]}
        self.assertEqual(_highlights([item]), [])

    def row(self, values=(12, 13)):
        today = date.today()
        points = [{"date": (today - timedelta(days=(len(values) - i - 1) * 10)).isoformat(),
                   "value": v, "unit": "u", "source": "synthetic form", "date_source": "form",
                   "ref_low": 1, "ref_high": 10, "method": "same"} for i, v in enumerate(values)]
        return {"key": "synthetic-marker", "name": "Synthetic marker", "series": points,
                "date": points[-1]["date"], "value": values[-1], "abnormal": True,
                "flag": "high", "ref_low": 1, "ref_high": 10, "flags_comparable": True,
                "display_recency": True, "unit": "u", "decisions": []}

    def events(self, row):
        return insight_events({"markers": [row]}, [], [], {}, [])

    def test_repeated_deviation_needs_separate_days(self):
        row = self.row()
        self.assertIn("repeated_abnormal", [e["kind"] for e in self.events(row)])
        row["series"][0]["date"] = row["series"][1]["date"]
        self.assertNotIn("repeated_abnormal", [e["kind"] for e in self.events(row)])

    def test_changed_method_and_censoring_do_not_establish_repetition(self):
        for key, value in (("method", "different"), ("censored", ">")):
            row = self.row()
            row["series"][0][key] = value
            self.assertNotIn("repeated_abnormal", [e["kind"] for e in self.events(row)])

    def test_stale_future_proposed_and_unknown_dates_do_not_make_current_findings(self):
        for stamp in ("unknown", "2035-01-01", "2020-01-01"):
            row = self.row()
            for p in row["series"]:
                p["date"] = stamp
            self.assertEqual(self.events(row), [])
        row = self.row()
        row["proposed_rule"] = True
        self.assertEqual(self.events(row), [])

    def test_one_marker_has_one_feed_item_with_every_reason(self):
        row = self.row((6, 6.1, 6, 6.1, 6, 6.1, 12, 13))
        with mock.patch("scholion.engine.goals.goal_dashboard", return_value={}):
            feed = attention_feed({"markers": [row]}, [], [], {}, [])
        self.assertEqual(feed["count"], 1)
        self.assertTrue(feed["items"][0]["facts"])
        self.assertIn("repeated_abnormal", [e["kind"] for e in feed["items"][0]["events"]])

    def test_urgent_items_are_not_hidden_after_five(self):
        cautions = [{"drug": "synthetic-" + str(i), "rsid": "rs-test", "level": "A"}
                    for i in range(7)]
        with mock.patch("scholion.engine.goals.goal_dashboard", return_value={}):
            feed = attention_feed({"markers": []}, cautions, [], {}, [])
        self.assertEqual(feed["visible_count"], 7)

    def test_low_coverage_wearable_never_becomes_an_event(self):
        row = {"key": "Sleep", "comparison": {"eligible": False, "distinguishable": True}}
        self.assertEqual(insight_events({}, [], [], {"metrics": [row]}, []), [])

    def test_unknown_variation_does_not_prove_a_change(self):
        self.assertNotIn("lab_change", [e["kind"] for e in self.events(self.row((6, 20)))])

    def test_period_changes_select_observations_without_modifying_annual_history(self):
        points = [{"date": "2026-08-01", "value": 4}, {"date": "2026-09-20", "value": 5},
                  {"date": "2026-10-10", "value": 6}]
        rows = [{"components": [{"series": points}]}]
        month = period_summary(rows, 30, date(2026, 10, 18))[0]["components"][0]
        quarter = period_summary(rows, 90, date(2026, 10, 18))[0]["components"][0]
        self.assertEqual(month["period"]["delta"], 1)
        self.assertEqual(quarter["period"]["delta"], 2)
        self.assertEqual(rows[0]["components"][0]["series"], points)

    def test_review_preview_and_failure_leave_profile_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / "profile"
            root.mkdir()
            feed = {"policy": "test", "as_of": date.today().isoformat(), "items": [], "states": {}}
            with mock.patch.dict(os.environ, support.env(root)), \
                    mock.patch("scholion.engine.overview", return_value={"attention": feed}):
                first = insight_history.review_snapshot()
                self.assertEqual(list(root.iterdir()), [])
                failed = insight_history.review_snapshot("неверное подтверждение")
                self.assertFalse(failed["ok"])
                self.assertFalse((root / insight_history.FILENAME).exists())
                saved = insight_history.review_snapshot(first["confirmation"])
                self.assertTrue(saved["saved"])
                data = (root / insight_history.FILENAME).read_bytes()
                insight_history.review_snapshot()
                self.assertEqual((root / insight_history.FILENAME).read_bytes(), data)

    def test_missing_input_is_not_resolution(self):
        previous = {"container": None, "items": [{"id": "lab:x", "date": "2026-09-01",
                        "kinds": ["abnormal"], "name": "x"}]}
        feed = {"policy": "test", "as_of": "2026-10-18", "items": [], "states": {}}
        with mock.patch("scholion.container.named", return_value={"id": None}):
            result = insight_history.compare_review(feed, previous)
            self.assertEqual(result["items"][0]["status"], "unavailable")
            feed["states"] = {"lab:x": {"flag": "ok", "date": "2026-10-01", "current": True}}
            self.assertEqual(insight_history.compare_review(feed, previous)["items"][0]["status"], "unavailable")
            feed["states"]["lab:x"]["method"] = "same"
            previous["states"] = {"lab:x": {"method": "same"}}
            self.assertEqual(insight_history.compare_review(feed, previous)["items"][0]["status"], "resolved")

    def test_rule_change_is_distinct_from_data_change(self):
        row = self.row()
        with mock.patch("scholion.engine.goals.goal_dashboard", return_value={}):
            feed = attention_feed({"markers": [row]}, [], [], {}, [])
        previous = insight_history._snapshot(feed)
        changed = copy.deepcopy(feed)
        changed["items"][0]["provenance"]["rules_digest"] = "changed"
        result = insight_history.compare_review(changed, previous)
        self.assertEqual(result["items"][0]["reason"], "rules")

    def test_history_save_is_idempotent_and_translation_is_not_a_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / "profile"
            root.mkdir()
            row = self.row()
            with mock.patch('scholion.engine.goals.goal_dashboard', return_value={}):
                feed = attention_feed({'markers':[row]}, [], [], {}, [])
            with mock.patch.dict(os.environ, support.env(root)), \
                    mock.patch('scholion.engine.overview', return_value={'attention':feed}):
                token = insight_history.review_snapshot()['confirmation']
                feed['items'][0]['title'] = 'A different display language'
                feed['items'][0]['name'] = 'Translated label'
                self.assertTrue(insight_history.review_snapshot(token)['saved'])
                original = (root / insight_history.FILENAME).read_bytes()
                self.assertTrue(insight_history.review_snapshot(token)['saved'])
                self.assertEqual(original, (root / insight_history.FILENAME).read_bytes())

    def test_rule_withdrawal_needs_same_input_and_current_data(self):
        with mock.patch('scholion.engine.goals.goal_dashboard', return_value={}):
            feed = attention_feed({'markers':[self.row()]}, [], [], {}, [])
        previous = insight_history._snapshot(feed)
        feed['items'] = []
        state = feed['states']['lab:synthetic-marker']
        state['rules_digest'] = 'new rule'
        diff = insight_history.compare_review(feed, previous)
        item = next(i for i in diff['items'] if i['id']=='lab:synthetic-marker')
        self.assertEqual((item['status'], item['reason']), ('withdrawn','rules'))
        state['current'] = False
        item = next(i for i in insight_history.compare_review(feed, previous)['items'] if i['id']=='lab:synthetic-marker')
        self.assertEqual(item['status'], 'unavailable')

    def test_a_recorded_target_is_not_a_population_reference(self):
        row = self.row((6,6.1,6,6.1,6,6.1,6,9))
        row.update(abnormal=False, flag='ok', target={'low':5,'high':6,'set_on':'2026-01-01','set_by':'synthetic clinician'})
        events = self.events(row)
        self.assertIn('goal_away', [e['kind'] for e in events])
        self.assertIn('lab_change', [e['kind'] for e in events])
        row.pop('target')
        self.assertNotIn('goal_away', [e['kind'] for e in self.events(row)])

    def test_pgs_pair_requires_this_model_phenotype_and_applicable_calibration(self):
        from scholion.engine.insight_links import linked_pgs_events
        row = self.row()
        row['key'] = 'ldl'
        score = {'pgs_id':'PGS000061','percentile':90,'reliable':True,'reference_panel_ancestry':'EUR'}
        pgs = {'stats':{'panel_matches_ancestry':True},'categories':[{'traits':[score]}]}
        self.assertEqual(len(linked_pgs_events({'markers':[row]}, pgs)), 1)
        for change in ({'reliable':False},{'pgs_id':'PGS-other'},{'reference_panel_ancestry':'EAS'},{'percentile':100}):
            bad = copy.deepcopy(pgs)
            bad['categories'][0]['traits'][0].update(change)
            self.assertEqual(linked_pgs_events({'markers':[row]}, bad), [])
        row['key'] = 'unrelated-marker'
        self.assertEqual(linked_pgs_events({'markers':[row]}, pgs), [])

    def test_unknown_and_future_dates_do_not_enter_the_period_summary(self):
        rows = [{'components':[{'series':[{'date':'','value':1}, {'date':'bad','value':2},
                  {'date':'2035-01-01','value':4}, {'date':'2026-10-10','value':3}]}]}]
        got = period_summary(rows, 30, date(2026,10,18))[0]['components'][0]['period']
        self.assertEqual(got['series'], [{'date':'2026-10-10','value':3}])
        self.assertIsNone(got['delta'])

    def test_lazily_named_profile_keeps_review_but_other_patients_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve() / "profile"
            root.mkdir()
            feed = {"policy": "test", "as_of": date.today().isoformat(), "items": [], "states": {}}
            with mock.patch.dict(os.environ, support.env(root)), \
                    mock.patch("scholion.engine.overview", return_value={"attention": feed}):
                token = insight_history.review_snapshot()["confirmation"]
                self.assertTrue(insight_history.review_snapshot(token)["saved"])
                original = (root / insight_history.FILENAME).read_bytes()
                self.assertTrue(insight_history.review_snapshot()["comparison"]["available"])
                self.assertTrue(insight_history.review_snapshot(token)["saved"])
                self.assertEqual(original, (root / insight_history.FILENAME).read_bytes())
                previous = insight_history._snapshot(feed)
                self.assertTrue(previous["container"])
                with mock.patch("scholion.container.named", return_value={"id": "another-patient"}):
                    with self.assertRaises(ValueError):
                        insight_history.compare_review(feed, previous)
                    previous["container"] = None
                    previous["profile_identity"] = "another-profile"
                    with self.assertRaises(ValueError):
                        insight_history.compare_review(feed, previous)

    def test_pgs_association_keeps_its_grade_when_merged_with_lab_deviation(self):
        from scholion.engine.insight_links import linked_pgs_events
        row = self.row()
        row["key"] = "ldl"
        pgs = {"stats": {"panel_matches_ancestry": True}, "categories": [{"traits": [
            {"pgs_id": "PGS000061", "percentile": 90, "reliable": True, "reference_panel_ancestry": "EUR"}]}]}
        event = linked_pgs_events({"markers": [row]}, pgs)[0]
        with mock.patch("scholion.engine.goals.goal_dashboard", return_value={}), \
                mock.patch("scholion.engine.insight_links.linked_pgs_events", return_value=[event]):
            feed = attention_feed({"markers": [row]}, [], [], {}, [])
        self.assertEqual(feed["count"], 1)
        self.assertEqual(feed["items"][0]["level"], "C")
        for comparator in (">", "<", ">="):
            row["series"][-1]["comparator"] = comparator
            self.assertEqual(linked_pgs_events({"markers": [row]}, pgs), [])

    def test_month_only_lab_dates_are_not_means_or_independent_dated_draws(self):
        rows = [{"components": [{"ref": "lab:ldl", "aggregation": "observation", "series": [
            {"date": "2026-08", "value": 3}, {"date": "2026-09", "value": 4}]}]}]
        result = period_summary(rows, 90, date(2026,10,18))[0]["components"][0]["period"]
        self.assertEqual(result["statistic"], "observation")
        self.assertIsNone(result["delta"])
        rows[0]["components"][0]["aggregation"] = "monthly_mean"
        result = period_summary(rows, 90, date(2026,10,18))[0]["components"][0]["period"]
        self.assertEqual(result["statistic"], "mean")
        self.assertEqual(result["delta"], 1)

    def test_unchanged_review_does_not_invent_an_unknown_change_cause(self):
        from scholion.format_insights import review_change_lines
        from scholion.i18n import t
        result = review_change_lines({"available": True, "items": [{"status": "unchanged",
            "label": "Unchanged", "reason_label": "unknown", "current": {"name": "synthetic"}}]})
        self.assertIn(t("insight.no_changes"), result)
        self.assertNotIn("unknown", " ".join(result))

    def test_changed_recorded_reference_is_data_even_when_value_stays_abnormal(self):
        row = self.row()
        with mock.patch("scholion.engine.goals.goal_dashboard", return_value={}):
            feed = attention_feed({"markers": [row]}, [], [], {}, [])
            previous = insight_history._snapshot(feed)
            row["series"][-1]["ref_high"] = 11
            current = attention_feed({"markers": [row]}, [], [], {}, [])
        changed = next(i for i in insight_history.compare_review(current, previous)["items"]
                       if i["id"] == "lab:synthetic-marker")
        self.assertEqual((changed["status"], changed["reason"]), ("changed", "data"))

    def test_named_review_moves_with_container_but_confirmation_does_not(self):
        from scholion import container
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp).resolve() / "original" / "profile"
            old.mkdir(parents=True)
            feed = {"policy": "test", "as_of": date.today().isoformat(), "items": [], "states": {}}
            with mock.patch("scholion.engine.overview", return_value={"attention": feed}):
                with mock.patch.dict(os.environ, support.env(old)):
                    first = insight_history.review_snapshot()
                    self.assertIsNone(container.named()["id"])
                    insight_history.review_snapshot(first["confirmation"])
                    original = (old / insight_history.FILENAME).read_bytes()
                moved = old.parent.with_name("moved")
                old.parent.rename(moved)
                with mock.patch.dict(os.environ, support.env(moved / "profile")):
                    now = insight_history.review_snapshot()
                    self.assertTrue(now["comparison"]["available"])
                    self.assertTrue(all(i["status"] == "unchanged" for i in now["comparison"]["items"]))
                    self.assertFalse(insight_history.review_snapshot(first["confirmation"])["saved"])
                    self.assertEqual(original, (moved / "profile" / insight_history.FILENAME).read_bytes())

    def test_first_review_does_not_claim_a_comparison_exists(self):
        from scholion.format_insights import review_report
        from scholion.i18n import t
        rendered = review_report({"comparison": {"available": False}, "confirmation": "preview"})
        self.assertIn(t("insight.no_history"), rendered)
        self.assertNotIn(t("insight.no_changes"), rendered)


class ReviewReadabilityTests(TestCase):
    def points(self):
        return [{"date": (date.today()-timedelta(days=300-i*60)).isoformat(),
                 "value": v, "method": "same", "unit": "u", "date_source": "form"}
                for i,v in enumerate((1,2,1,4,5,4))]

    def feed(self, points=None, abnormal=True):
        points = points or self.points()
        row = {"key":"ldl", "name":"Synthetic LDL", "series":points,
               "date":points[-1]["date"], "value":points[-1]["value"],
               "flag":"high" if abnormal else "ok", "abnormal":abnormal,
               "ref_low":0, "ref_high":3, "unit":"u"}
        goal = {"phenotype":[{"label":"Synthetic LDL", "components":[{
            "ref":"lab:ldl", "series":points, "unit":"u", "source":"lab"}]}]}
        with mock.patch("scholion.engine.goals.goal_dashboard",return_value=goal), \
             mock.patch("scholion.engine.insights.core.medications_json", return_value={}), \
             mock.patch("scholion.engine.insight_links.linked_pgs_events",return_value=[]):
            return attention_feed({"markers":[row]},[],[],{},[])

    def test_a_single_abnormal_value_remains_accessible_but_is_not_an_insight(self):
        feed=self.feed(self.points()[-1:])
        self.assertEqual(feed['count'],1)
        self.assertEqual(feed['highlights'],[])
        self.assertEqual(feed['observation_count'],1)

    def test_repetition_is_separate_from_annual_analysis(self):
        feed=self.feed(self.points()[-2:])
        self.assertEqual(feed['highlights'],[])
        self.assertEqual(len(feed['follow_up']),1)
        self.assertTrue(feed['follow_up'][0]['summaries'])

    def test_year_is_default_and_within_range_changes_are_visible(self):
        feed=self.feed(abnormal=False)
        self.assertEqual(feed['period'],365)
        self.assertEqual(len(feed['highlights']),1)
        self.assertEqual(feed['highlights'][0]['id'],'panel:lipids')
        event=feed['highlights'][0]['events'][0]
        self.assertEqual(event['kind'],'period_shift')
        self.assertEqual((event['detail']['before'],event['detail']['after']),(1,4))
        self.assertEqual(event['detail']['n'],6)
        self.assertIn('descriptive_periods',event['limitations'])

    def test_current_single_spike_does_not_become_a_year_shift(self):
        points=self.points()
        for p in points: p['value']=2
        points[-1]['value']=20
        self.assertEqual(self.feed(points)['highlights'],[])

    def test_shared_defaults_and_current_controls(self):
        import inspect
        from scholion.engine.profile_view import overview
        from scholion.ouroboros_tools import _overview_data
        self.assertEqual(inspect.signature(overview).parameters['period'].default,365)
        self.assertEqual(inspect.signature(_overview_data).parameters['period'].default,365)

    def test_treatment_context_retains_stop_date_without_current_warning(self):
        from scholion.engine.insight_events import _treatment_context
        med={"name":"Synthetic prior", "start_date":"2026-01", "status":"stopped_2026-09-10"}
        with mock.patch('scholion.core.medications_json',return_value={'medications':[med]}), \
             mock.patch('scholion.core.classify_drug',return_value=['testosterone_replacement']):
            context=_treatment_context('testosterone','2025-12-01','2026-10-13')
        self.assertEqual(context[0]['end_date'],'2026-09-10')
        self.assertFalse(context[0]['current'])

    def test_annual_summary_renders_in_both_languages_with_latest_value(self):
        from scholion.format_insights import attention_report
        for language in ("en", "ru"):
            with mock.patch.dict(os.environ, SCHOLION_LANG=language):
                feed = self.feed(abnormal=False)
                rendered = attention_report(feed)
                self.assertIn(feed["highlights"][0]["summaries"][0], rendered)
                self.assertIn(self.points()[-1]["date"], rendered)
                self.assertNotIn("⟦", rendered)

    def test_treatment_context_rejects_invalid_or_reversed_dates(self):
        from scholion.engine.insight_events import _treatment_context
        for begin, end in (("2026-99", "2026-10"), ("2026-06", "2026-01")):
            med = {"name":"Synthetic prior", "start_date":begin, "end_date":end, "status":"stopped"}
            with mock.patch('scholion.core.medications_json',return_value={'medications':[med]}), \
                 mock.patch('scholion.core.classify_drug',return_value=['testosterone_replacement']):
                self.assertEqual(_treatment_context('testosterone','2025-12-01','2026-10-13'), [])

    def test_current_derived_value_does_not_rename_historical_device_source(self):
        from scholion.engine.insight_events import _annual_events
        component={'ref':'wear:BMI','source':'derived','series_source':'garmin',
                   'aggregation':'monthly_mean','period':{'series':self.points()}}
        events=_annual_events([{'label':'BMI','components':[component]}],{})
        self.assertTrue(events)
        self.assertTrue(all(f['source']=='garmin' for f in events[0]['facts']))


class OverviewReadingSessionTests(TestCase):
    def test_each_overview_uses_one_reading_without_caching_between_answers(self):
        from scholion import core
        from scholion.engine import profile_view
        original=core.knowledge_precedence.__wrapped__
        with mock.patch('scholion.core._knowledge_stamp', wraps=core._knowledge_stamp) as stamp:
            # Compare repeated lookups inside the overview with an uncached lookup.
            with mock.patch.object(profile_view, 'analyze_labs') as labs:
                def stop_after_reading():
                    core.knowledge_precedence('lab_markers.json')
                    core.knowledge_precedence('lab_markers.json')
                    raise RuntimeError('synthetic stop after reference reads')
                labs.side_effect=stop_after_reading
                original('lab_markers.json');expected=stamp.call_count;stamp.reset_mock()
                for _ in range(2):
                    with self.assertRaisesRegex(RuntimeError,'synthetic stop'):
                        profile_view.overview()
                self.assertEqual(stamp.call_count, expected*2)
            self.assertIsNone(getattr(core._READING,'memo',None))
