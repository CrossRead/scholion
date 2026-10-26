"""System navigation preserves measured facts and qualified medication context."""
import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import core, i18n
from scholion.engine.labs import analyze_labs
from scholion.engine.system_panels import medication_system_context, prescriptions, _labs_layer


class SystemContextReviewTests(unittest.TestCase):
    def test_reported_ingredients_are_used_but_notes_are_not(self):
        med = {"name": "Synthetic product", "note": "niacin", "composition_as_reported": {
            "ingredients": ["monacolin K", "berberine", None], "amount": "unverified"}}
        classes = core.medication_classes(med)
        self.assertIn("red_yeast_rice", classes)
        self.assertIn("berberine", classes)
        self.assertNotIn("niacin", classes)
        context = medication_system_context(med)
        self.assertIn("lipids", context["systems"])
        self.assertIn("glucose", context["systems"])
        self.assertTrue(any(x["relation"] == "possible_effect" for x in context["system_links"]))
        self.assertNotIn("amount", context)
        for invalid in [None, "berberine", {"ingredients": "berberine"}, {"ingredients": [None, {}]}]:
            self.assertEqual(core.medication_classes({"name": "Synthetic product", "composition_as_reported": invalid}), [])

    def test_combination_ingredients_reach_genotype_cautions(self):
        from scholion.engine.class_genotype import regimen_cautions
        med = {"name":"Synthetic combination", "composition_as_reported":{"ingredients":["azathioprine"]}}
        with patch.object(core,"active_medications",return_value=[med]), \
             patch("scholion.engine.class_genotype.cautions",return_value=[]) as check:
            regimen_cautions()
        self.assertEqual(check.call_args.args[0], core.medication_classes(med))
        self.assertIn("thiopurine",check.call_args.args[0])

    def test_named_ingredient_context_is_not_a_class_wide_claim(self):
        tirzepatide = medication_system_context({"name": "tirzepatide"})
        self.assertIn("lipids", tirzepatide["systems"])
        self.assertIn("fitness", tirzepatide["systems"])
        self.assertNotIn("lipids", medication_system_context({"name": "liraglutide"})["systems"])

    def test_monitoring_is_distinct_and_completed_courses_are_excluded(self):
        current = {"name": "niacin", "status": "active"}
        with patch.object(core, "active_medications", return_value=[current]):
            row = prescriptions()[0]
        self.assertIn("lipids", row["systems"])
        self.assertIn("renal", row["systems"])
        self.assertEqual({x["relation"] for x in row["system_links"] if x["system"] == "renal"}, {"monitoring"})
        with patch.object(core, "medications_json", return_value={"medications": [
            current, {"name": "statin", "status": "completed", "end_date": "2020-01-01"}]}):
            self.assertEqual([r["name"] for r in prescriptions()], ["niacin"])

    def test_groups_cover_every_current_marker_and_keep_shared_membership(self):
        data = analyze_labs()
        current = {m["key"]: m for m in data["markers"] if m["display_recency"] is not False}
        groups = data["system_groups"]
        self.assertEqual({k for g in groups for k in g["markers"]}, set(current))
        for g in groups:
            self.assertEqual(g["measured"], len(g["markers"]))
            self.assertEqual(g["abnormal"], sum(current[k]["abnormal"] for k in g["markers"]))
        fake = {"new": {"key": "new", "display_recency": True, "value": 3, "series": [{"date":"2026-10-01", "value":3}]},
                "old": {"key": "old", "display_recency": False}}
        with patch('scholion.engine.system_panels.panel_labs.panel_view', return_value={}):
            lab = _labs_layer({"source":"labs", "markers":["new","old"]}, {"score":0}, fake)
        self.assertEqual(lab["current_markers"], [fake["new"]])

    def test_relation_labels_are_localized(self):
        before = i18n.lang()
        self.addCleanup(i18n.set_lang, before)
        for lang in ("en", "ru"):
            i18n.set_lang(lang)
            for link in medication_system_context({"name":"niacin"})["system_links"]:
                self.assertNotIn("system.meds.relation", link["relation_label"])

    def test_visit_measurement_names_follow_the_display_language(self):
        from scholion.engine.visit import visit_topic
        before=i18n.lang()
        self.addCleanup(i18n.set_lang,before)
        for language in ("en","ru"):
            i18n.set_lang(language)
            brief=visit_topic({"facts":[{"key":"weight","date":"2026-10-01","value":80}],"events":[]})
            expected=core.wearable_metrics()["metrics"]["Weight"]["label"]
            self.assertEqual(brief["measurements"][0]["name"],expected)

    def test_method_qualifications_use_the_selected_language(self):
        from scholion.engine.labs import _method_notes
        before=i18n.lang()
        self.addCleanup(i18n.set_lang,before)
        with patch.object(core,"lab_test_meta",return_value={"tests":{"synthetic":{"loinc_note":{"en":"Method EN","ru":"Method RU"}}}}):
            for language in ("en","ru"):
                i18n.set_lang(language)
                result=_method_notes("synthetic",{"units_note":{"en":"Units EN","ru":"Units RU"}})
                self.assertEqual(result,["Units "+language.upper(),"Method "+language.upper()])

    def test_visit_brief_is_a_summary_not_a_duplicate_fact_dump(self):
        from scholion.engine.visit import visit_topic
        from scholion.format_visit import visit_report
        from scholion.engine.visit import visit_sheet
        fact = {"key":"ldl", "value":4, "unit":"mmol/L", "date":"2026-10-01", "record":"labs.json"}
        gene = {"gene":"SYN", "rsid":"rsSynthetic", "state":"het", "level":"C", "status":"hypothesis",
                "status_label":"Hypothesis", "comparison":"Possible relation", "summary":"Mechanism",
                "observation":{"point":fact}, "association_id":"synthetic"}
        item = {"title":"Lipids", "facts":[{**fact,"date":"2026-01-01","value":5},fact,fact],
                "summaries":["Lipids moved downward", "Lipids moved downward"],
                "events":[{"detail":{"why":"Possible relation"}}],
                "context":{"comparisons":[gene,gene,{**gene,"status":"unread","association_id":"other"}],
                           "lifestyle":[{"key":"sleep","value":8}]},
                "context_lifestyle_summary":"Raw sleep list"}
        brief = visit_topic(item)
        self.assertEqual(len(brief["measurements"]),1)
        self.assertEqual(brief["measurements"][0]["count"],2)
        self.assertEqual(brief["conclusions"],["Lipids moved downward"])
        self.assertEqual(brief["comparisons"],[gene])
        self.assertNotIn("Possible relation",brief["support"])
        data = visit_sheet(agenda_ids=[])
        data["agenda"]["items"] = [{**item,"visit_brief":brief}]
        # Exercise the retained pre-document JSON shape, not a stale projection.
        data.pop("document", None)
        rendered = visit_report(data)
        self.assertIn("5 mmol/L",rendered)
        self.assertIn("4 mmol/L",rendered)
        self.assertIn("Possible relation",rendered)
        self.assertNotIn("Raw sleep list",rendered)

    def test_visit_reference_without_a_personal_result_does_not_become_a_comparison(self):
        from scholion.engine.visit import visit_topic
        brief = visit_topic({"title": "Synthetic system", "context": {
            "comparisons": [{"id": "reference-only", "summary": "Known mechanism"}],
            "genetics": [{"gene": "SYN", "comparison": "Reference context", "status": "context_only"},
                         {"gene": "OTHER", "summary": "Gene function"}]}})
        self.assertEqual(brief["comparisons"], [])
        self.assertEqual(brief["conclusions"], ["Synthetic system"])

    def test_visit_keeps_one_legacy_hypothesis_with_its_actual_reading(self):
        from scholion.engine.visit import visit_topic
        hypothesis = {"gene": "SYN", "rsid": "rsSynthetic", "comparison": "Qualified hypothesis",
                      "status": "hypothesis", "genotype": {"genotype": "AG"}}
        brief = visit_topic({"context": {"genetics": [hypothesis, hypothesis]}})
        self.assertEqual(len(brief["comparisons"]), 1)
        row = brief["comparisons"][0]
        self.assertEqual(row["comparison"], "Qualified hypothesis")
        self.assertEqual(row["display_genotype"], "AG")
        self.assertTrue(row["status_label"])

    def test_visit_uses_qualified_lifestyle_conclusion_and_deduplicates_support(self):
        from scholion.engine.visit import visit_topic
        item = {"summaries": ["System trend"], "context_lifestyle_summary": "Dated activity comparison",
                "context": {"lifestyle": [{"comparison": {"eligible": True}}]},
                "events": [{"detail": {"why": "Recorded context", "action": "Recorded context"}},
                           {"detail": {"why": "System trend", "factor": None}}]}
        brief = visit_topic(item)
        self.assertEqual(brief["conclusions"], ["System trend", "Dated activity comparison"])
        self.assertEqual(brief["support"], ["Recorded context"])
        item["context"]["lifestyle"][0]["comparison"]["eligible"] = False
        self.assertEqual(visit_topic(item)["conclusions"], ["System trend"])
