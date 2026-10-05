"""Monitoring proposals cannot borrow support from observations or a class book."""
from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from scholion import cli, core, engine, format as fmt, i18n, mcp_server, ouroboros_tools
from scholion.engine import pgx
from scholion.monitoring_basis import monitoring_for
from tests.test_a_genotype_in_the_profile_is_never_shown_as_unread import _Demo


def supported():
    return {"labs": ["creatinine", "uric_acid"], "why": {"en": "SYNTHETIC_REASON", "ru": "SYNTHETIC_REASON"},
            "why_basis": {"source": "Synthetic PMID:2", "mechanism": {"en": "REASON_MECHANISM", "ru": "REASON_MECHANISM"}},
            "lab_basis": {k: {"source": "Synthetic PMID:3", "mechanism": {"en": "SELECTION_MECHANISM", "ru": "SELECTION_MECHANISM"}}
                          for k in ("creatinine", "uric_acid")}}


OBS = {"key": "creatinine", "name": "Creatinine", "value": 120, "unit": "umol/L", "flag": "high",
       "date": "2026-01-01", "date_source": "form", "source": "Synthetic form", "ref_high": 100,
       "decisions": [{"crossed": None}], "near_limit": {"why": "Synthetic interval"},
       "personal_move": {"delta": 2}}


class TestIndependentMonitoring(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def run_map(self, spec, classes=None):
        return monitoring_for(classes or ["X"], {"X": spec}, [OBS], core.marker_name)

    def test_reason_and_marker_selection_have_independent_support(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            out = self.run_map(supported())
            self.assertEqual("SYNTHETIC_REASON", out["reason"])
            self.assertFalse(out["gaps"])
            for change in ({"why_basis": None}, {"lab_basis": {}}, {"source": "Synthetic PMID:4", "why_basis": None}):
                spec = {**supported(), **change}
                before = copy.deepcopy(spec)
                out = self.run_map(spec)
                self.assertTrue(out["gaps"])
                self.assertEqual(before, spec)
                self.assertEqual("" if "why_basis" in change else "SYNTHETIC_REASON", out["reason"])
                self.assertEqual(OBS["value"], out["markers"][0]["value"])
                self.assertEqual(["X"], out["basis"]["with_rules"])

    def test_malformed_or_one_language_prose_is_not_supported_after_localisation(self):
        for text in (None, [], 1, " ", {"en": "ONLY_EN"}):
            for language in ("en", "ru"):
                i18n.set_lang(language)
                spec = {**supported(), "why": text}
                for candidate in (spec, core._localize_tree(spec, language)):
                    out = self.run_map(candidate)
                    self.assertEqual("", out["reason"])
                    self.assertIn("claim_text", out["proposals"][0]["conclusion_basis"]["missing"])
        for change in ({"source": "PMID:TBD"}, {"mechanism": None}, {"mechanism": {"en": "ONLY_EN"}}):
            spec = supported()
            spec["why_basis"].update(change)
            self.assertEqual("", self.run_map(spec)["reason"])

    def test_observations_keep_dates_units_flags_and_unresolved_thresholds(self):
        before = copy.deepcopy(OBS)
        out = self.run_map({"labs": ["creatinine", "uric_acid"], "why": "UNHELD_TIMING"})
        row = out["markers"][0]
        for key in OBS:
            self.assertEqual(OBS[key], row[key])
        self.assertEqual(before, OBS)
        self.assertEqual([row], out["watch"])
        self.assertEqual([row], out["near"])
        self.assertEqual([row], out["unresolved"])
        self.assertFalse(out["crossed"])
        self.assertFalse(out["markers"][1]["present"])
        self.assertIsNone(out["markers"][1]["value"])
        self.assertNotEqual("uric_acid", out["markers"][1]["name"])
        self.assertNotIn("UNHELD_TIMING", out["reason"])

    def test_multiple_classes_share_the_observation_not_their_support(self):
        other = {"labs": ["creatinine"], "why": "OTHER_UNHELD_REASON"}
        out = monitoring_for(["X", "Y", "Z"], {"X": supported(), "Y": other}, [OBS], core.marker_name)
        self.assertEqual(2, len(out["markers"]))
        self.assertEqual(2, len(out["markers"][0]["monitoring_basis"]))
        self.assertEqual(["X", "Y"], out["basis"]["with_rules"])
        self.assertTrue(all(g["class"] == "Y" for g in out["gaps"]))
        out = monitoring_for(["X"], {}, [], core.marker_name)
        self.assertFalse(out["basis"]["with_rules"])
        self.assertFalse(out["markers"])
        out = self.run_map({"labs": [], "why": None})
        self.assertTrue(out["gaps"])
        self.assertNotIn(i18n.t("prescription.no_lab_control"), fmt.prescription_check({"status": "ok", "labs": out}))

    def test_crossed_observation_is_retained_without_borrowing_monitoring_support(self):
        observed = {**OBS, "decisions": [{"crossed": True}]}
        out = monitoring_for(["X"], {"X": {"labs": ["creatinine"]}}, [observed], core.marker_name)
        self.assertEqual(out["markers"], out["crossed"])
        self.assertFalse(out["unresolved"])


class TestMonitoringOutputs(_Demo):
    def setUp(self):
        super().setUp()
        self.addCleanup(i18n.set_lang, i18n.lang())
        ouroboros_tools.unpin_session()
        self.addCleanup(ouroboros_tools.unpin_session)

    def test_unsupported_proposal_is_named_in_all_existing_prescription_doors(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            rx = engine.check_new_prescription("ibuprofen")
            self.assertNotEqual("low", rx["overall"])
            self.assertTrue(any(u["what"] == "monitoring_basis" for u in rx["unresolved"]))
            lb = rx["labs"]
            self.assertEqual("", lb["reason"])
            self.assertTrue(lb["markers"])
            text = fmt.prescription_check(rx)
            self.assertIn(i18n.t("monitoring.observations"), text)
            for gap in lb["gaps"]:
                self.assertIn(gap["detail"], text)
            self.assertNotIn(i18n.t("prescription.no_lab_control"), text)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(0, cli.main(["prescription", "ibuprofen", "--json"]))
            self.assertTrue(json.loads(output.getvalue())["labs"]["gaps"])
            ouroboros_tools.unpin_session()
            answer = mcp_server.call_tool("sch_check_prescription", {"drug": "ibuprofen"})
            self.assertFalse(answer.get("isError"), answer)
            self.assertIn(lb["gaps"][0]["detail"], "\n".join(c.get("text", "") for c in answer["content"]))

    def test_supported_reason_and_selection_print_their_own_mechanisms_and_sources(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            spec = core._localize_tree(supported(), language)
            with mock.patch.object(core, "drug_lab_monitoring", return_value={"classes": {"nsaid": spec}}):
                lb = pgx._labs_for_drug(["nsaid"])
            self.assertEqual("SYNTHETIC_REASON", lb["reason"])
            text = fmt.prescription_check({"status": "ok", "labs": lb})
            for phrase in ("SYNTHETIC_REASON", "REASON_MECHANISM", "Synthetic PMID:2", "SELECTION_MECHANISM", "Synthetic PMID:3"):
                self.assertIn(phrase, text)
            self.assertFalse(lb["gaps"])

    def test_missing_record_caption_does_not_assert_a_test_was_never_done(self):
        for language in ("en", "ru"):
            i18n.set_lang(language)
            with mock.patch.object(pgx, "analyze_labs", return_value={"markers": []}):
                lb = pgx._labs_for_drug(["nsaid"])
            self.assertTrue(all(not m["present"] for m in lb["markers"]))
            text = fmt.prescription_check({"status": "ok", "labs": lb})
            self.assertIn(i18n.t("prescription.not_tested"), text)
            self.assertEqual(i18n.t("prescription.not_tested"), i18n.t("web.rx.not_taken_yet"))
            self.assertTrue(all(m["name"] != m["key"] for m in lb["markers"]))


if __name__ == "__main__":
    unittest.main()
