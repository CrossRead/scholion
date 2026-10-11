"""Patient-readable context preserves calls, uncertainty and source-language input."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import support
from scholion import core, i18n
from scholion.format_genome import longevity_report
from scholion.engine import genomics, goals, panel_form


class DisplayContext(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.addCleanup(support.pin_profile(self.root))
        self.addCleanup(i18n.set_lang, getattr(i18n._state, "current", None))
        i18n.set_lang("en")

    def test_historical_unit_labels_resolve_without_converting_values(self):
        for code, expected in (("\u043c\u043c\u043e\u043b\u044c/\u043b", "mmol/L"), ("\u0433/\u043b", "g/L"),
                               ("\u043c\u043c\u043e\u043b\u044c/\u043c\u043e\u043b\u044c \u043a\u0440\u0435\u0430\u0442.", "mmol/mol creat."),
                               ("\u0438\u043d\u0434\u0435\u043a\u0441 \u043f\u043e\u0437\u0438\u0442\u0438\u0432\u043d\u043e\u0441\u0442\u0438", "index"), ("\u043c\u0438\u043d/\u043d\u043e\u0447\u044c", "min/night")):
            self.assertEqual(expected, core.unit_label(code))
        self.assertEqual("10\u00b9\u00b2/L", core.unit_label("10^12/\u043b"))
        self.assertEqual("10\u2079/L", core.unit_label("10^9/\u043b"))
        self.assertEqual("mL/min/1.73 m\u00b2", core.unit_label("\u043c\u043b/\u043c\u0438\u043d/1.73 \u043c\u00b2"))
        self.assertEqual("mm/h", core.unit_label("\u043c\u043c/\u0447\u0430\u0441"))
        self.assertEqual("unknown unit", core.unit_label("unknown unit"))
        i18n.set_lang("ru")
        self.assertEqual("\u043c\u043c\u043e\u043b\u044c/\u043b", core.unit_label("mmol/L"))

    def test_bilingual_personal_goal_does_not_change_observations_or_target(self):
        data = {"title": {"en": "Synthetic goal", "ru": "\u0421\u0438\u043d\u0442\u0435\u0442\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u0446\u0435\u043b\u044c"},
                "targets": [{"label": {"en": "Weight", "ru": "\u0412\u0435\u0441"},
                             "source": "wear:Weight", "target": {"en": "At most 80 kg", "ru": "RU target"},
                             "best": {"en": "78 kg", "ru": "RU best"}}],
                "headline": {"en": "Synthetic headline", "ru": "RU headline"},
                "charts": {"weight": {"cap": {"en": "Synthetic caption", "ru": "RU caption"}}}}
        (self.root / "health_goals.json").write_text(json.dumps(data), encoding="utf-8")
        (self.root / "metrics.json").write_text(json.dumps({"metrics": {"weight": {
            "name": "Weight", "unit": "\u043a\u0433", "series": [{"date": "2026-01-01", "value": 81}]}}}), encoding="utf-8")
        row = goals.goal_dashboard()["phenotype"][0]
        self.assertEqual("Weight", row["label"])
        self.assertEqual("At most 80 kg", row["target"])
        self.assertEqual("78 kg", row["best"])
        self.assertEqual("Synthetic headline", core.health_goals()["headline"])
        self.assertEqual("Synthetic caption", core.health_goals()["charts"]["weight"]["cap"])
        self.assertEqual("\u043a\u0433", row["components"][0]["unit"])
        self.assertEqual("kg", row["components"][0]["unit_display"])
        self.assertEqual(81, row["components"][0]["value"])
        self.assertEqual(data, json.loads((self.root / "health_goals.json").read_text(encoding="utf-8")))
        i18n.set_lang("ru")
        self.assertEqual("\u0412\u0435\u0441", goals.goal_dashboard()["phenotype"][0]["label"])
        self.assertEqual("RU target", goals.goal_dashboard()["phenotype"][0]["target"])

    def longevity(self, reading):
        stored = {"known": [{"gene": "UNKNOWN", "rsid": "rs999999", "genotype": "AA"}],
                  "apoe": {"genotype": "ε2/ε3"}, "_meta": {"genotyped": 30}}
        with patch.object(core, "longevity_data", return_value=stored), patch.object(genomics, "apoe", return_value=reading):
            return genomics.longevity_findings()

    def test_apoe_explains_confirmed_diplotype_with_its_own_sources(self):
        result = self.longevity({"status": "ok", "genotype": "ε2/ε3"})
        row = result["apoe"]
        self.assertEqual("B", row["level"])
        self.assertIn("no ε4", row["interpretation"]["summary"])
        self.assertIn("cannot predict", row["interpretation"]["summary"])
        self.assertIn("31356640", row["interpretation"]["source"])
        self.assertNotIn("31954858", row["interpretation"]["source"])
        for language in ("en", "ru"):
            i18n.set_lang(language)
            localized = self.longevity({"status": "ok", "genotype": "ε2/ε3"})
            for field in ("summary", "mechanism", "source", "limitations", "evidence_reason", "notice"):
                self.assertIsInstance(localized["apoe"]["interpretation"][field], str, field)
            self.assertIn("ε2/ε3", longevity_report(localized))
        self.assertIn("30", result["count_note"])
        self.assertIn("not a count of genes", result["count_note"])

    def test_ambiguous_phase_never_selects_a_diplotype_interpretation(self):
        row = self.longevity({"status": "ambiguous_without_phase", "candidates": ["ε2/ε4", "ε1/ε3"]})["apoe"]
        self.assertNotIn("interpretation", row)
        self.assertEqual(["ε2/ε4", "ε1/ε3"], row["candidates"])
        self.assertNotIn("interpretation", self.longevity({"status": "no_genome"})["apoe"])

    def test_all_four_pcsk9_readings_keep_unresolved_direction_separate(self):
        with patch.object(core, "genotype_status", return_value={"genotype": "GG", "confidence": "called", "source": "synthetic VCF"}), patch.object(genomics, "prs_findings", return_value={}):
            rows = {x["rsid"]: x for x in genomics.lipid_genetics()["pcsk9"]}
        self.assertEqual({"rs11591147", "rs28362286", "rs28362263", "rs72646508"}, set(rows))
        for rsid in ("rs28362263", "rs72646508"):
            self.assertEqual("GG", rows[rsid]["genotype"])
            self.assertEqual("read", rows[rsid]["status"])
            self.assertIsNone(rows[rsid]["carrier"])
            self.assertIsNone(rows[rsid]["copies"])
            self.assertIn("variant_note", rows[rsid])

    def test_lipid_measurement_unit_is_localized_without_changing_the_reading(self):
        from scholion.engine import labs
        from scholion.format_genome import lipid_genetics_report
        for language, unit in (("en", "nmol/L"), ("ru", "\u043d\u043c\u043e\u043b\u044c/\u043b")):
            i18n.set_lang(language)
            marker = {"value": 12.5, "unit": "\u043d\u043c\u043e\u043b\u044c/\u043b", "unit_display": unit,
                      "date": "2026-01-01", "flag": "ok", "series": [{"value": 12.5}]}
            with patch.object(labs, "analyze_labs", return_value={"markers": [marker]}), patch.object(genomics, "prs_findings", return_value={}):
                result = genomics.lipid_genetics()
            self.assertEqual(12.5, result["lpa"]["measured"]["value"])
            self.assertEqual(marker["unit"], result["lpa"]["measured"]["unit"])
            self.assertIn("12.5 " + unit, lipid_genetics_report(result))

    def test_cli_does_not_call_unresolved_pcsk9_direction_absent(self):
        from scholion.format_genome import lipid_genetics_report
        for language in ("en", "ru"):
            i18n.set_lang(language)
            row = {"status": "read", "rsid": "rs28362263", "gene": "PCSK9", "genotype": "GG", "carrier": None}
            text = lipid_genetics_report({"pcsk9": [row]})
            self.assertIn(i18n.t("lipidgen.direction_unknown"), text)
            self.assertNotIn(i18n.t("lipidgen.not_carrier"), text)

    def test_screen_provenance_refusals_are_sentences_in_each_language(self):
        for lang in ("en", "ru"):
            i18n.set_lang(lang)
            text = panel_form.verdict_line({"kind": "not_determined", "why": "metadata_unverified"})
            self.assertNotIn("⟦", text)
            self.assertNotIn("metadata_unverified", text)


class LipidPercentileValidity(unittest.TestCase):
    def test_unverified_percentiles_are_not_promoted_by_the_lipid_card(self):
        from scholion.format_genome import lipid_genetics_report
        for reliable, percentile in ((True, 99.9999), (False, 99.0), (False, None)):
            row = {"pgs_id": "PGS002101", "label": "Synthetic Lp(a)", "percentile": percentile,
                   "reliable": reliable, "calibration_note": None if reliable else "Synthetic calibration gap",
                   "reading_note": None if reliable else "Synthetic VCF help"}
            with patch.object(genomics, "prs_findings", return_value={"categories": [{"traits": [row]}]}):
                result = genomics.lipid_genetics()
            estimate = result["lpa"]["estimate"]
            self.assertEqual(reliable, estimate["reliable"])
            self.assertEqual(percentile if reliable else None, estimate["percentile"])
            rendered = lipid_genetics_report(result)
            if reliable:
                self.assertIn("≥P99.99", rendered)
                self.assertNotIn("P100", rendered)
            else:
                self.assertIn("Synthetic calibration gap", rendered)
                self.assertNotIn("Synthetic Lp(a): 99", rendered)
