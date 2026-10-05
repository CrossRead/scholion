"""Recognise the missing public analytes without inventing units or norms.

All numbers and forms below are synthetic parser fixtures. U/mL is deliberately
a test spelling, not an asserted clinical assay unit for every analyte.
"""
from __future__ import annotations

import copy
import json
from unittest import mock

from scholion import core, engine, format as fmt, ingest_labs as il, markers_local, store
from tests.test_ingest_reads_a_table import TableCase

CASES = [
  [
    "ca_15_3",
    "ca 15-3",
    "са 15-3"
  ],
  [
    "ca_19_9",
    "ca 19-9",
    "са 19-9"
  ],
  [
    "ca_125",
    "ca 125",
    "са 125"
  ],
  [
    "ca_72_4",
    "ca 72-4",
    "са 72-4"
  ],
  [
    "ca_242",
    "ca 242",
    "са 242"
  ],
  [
    "he4",
    "he4",
    "he4"
  ],
  [
    "nse",
    "neuron-specific enolase",
    "нейронспецифическая энолаза"
  ],
  [
    "s100",
    "s-100 protein",
    "белок s-100"
  ],
  [
    "tbg",
    "thyroxine-binding globulin",
    "тироксинсвязывающий глобулин"
  ],
  [
    "t4_total",
    "total t4",
    "т4 общий"
  ],
  [
    "t3_reverse",
    "reverse t3",
    "реверсивный т3"
  ],
  [
    "vitamin_a",
    "vitamin a",
    "витамин а"
  ],
  [
    "vitamin_e",
    "vitamin e",
    "витамин е"
  ],
  [
    "vitamin_d2",
    "25-oh vitamin d2",
    "25-он витамин d2"
  ],
  [
    "acid_phosphatase",
    "acid phosphatase",
    "кислая фосфатаза"
  ],
  [
    "bone_alp",
    "bone-specific alkaline phosphatase",
    "костная щелочная фосфатаза"
  ],
  [
    "osteoprotegerin",
    "osteoprotegerin",
    "остеопротегерин"
  ],
  [
    "vegf",
    "vascular endothelial growth factor",
    "фактор роста эндотелия сосудов"
  ],
  [
    "prothrombin_time",
    "prothrombin time",
    "протромбиновое время"
  ],
  [
    "prothrombin_index",
    "prothrombin index",
    "протромбиновый индекс"
  ],
  [
    "inr",
    "international normalized ratio",
    "международное нормализованное отношение"
  ],
  [
    "thrombin_time",
    "thrombin time",
    "тромбиновое время"
  ],
  [
    "antithrombin_iii",
    "antithrombin iii",
    "антитромбин iii"
  ],
  [
    "lupus_anticoagulant",
    "lupus anticoagulant",
    "волчаночный антикоагулянт"
  ],
  [
    "igg_total",
    "total immunoglobulin g",
    "иммуноглобулин g"
  ],
  [
    "igm_total",
    "total immunoglobulin m",
    "иммуноглобулин m"
  ],
  [
    "serotonin",
    "serotonin",
    "серотонин"
  ],
  [
    "il6",
    "interleukin-6",
    "интерлейкин-6"
  ],
  [
    "deoxycortisol_21",
    "21-deoxycortisol",
    "21-дезоксикортизол"
  ],
  [
    "deoxycorticosterone_11",
    "11-deoxycorticosterone",
    "11-дезоксикортикостерон"
  ],
  [
    "vldl",
    "vldl cholesterol",
    "холестерин лпонп"
  ]
]
HEADER = "Дата взятия биоматериала: 01.02.2026 08:30\n"


class TestMissingPublicAnalytes(TableCase):
    def test_all_31_names_are_read_in_both_languages_and_units_come_from_the_form(self):
        markers = core.lab_markers()["markers"]
        self.assertEqual(31, len(CASES))
        for key, en, ru in CASES:
            with self.subTest(marker=key):
                spec = markers[key]
                self.assertEqual("proposed", spec["status"])
                self.assertTrue(spec["unit_from_form"])
                for field in ("unit", "loinc", "ref_low", "ref_high", "convert", "units"):
                    self.assertNotIn(field, spec)
                for label, unit in ((en, "U/mL"), (ru, "Ед/мл")):
                    _, found = il.parse_report(HEADER + label + " 123.45 " + unit + " 1 - 2", markers)
                    self.assertIn(key, found)
                    self.assertEqual(123.45, found[key]["value"])
                    self.assertEqual("U/mL", found[key]["unit"])

    def test_all_values_are_stored_but_unconfirmed_rules_make_no_norm_claim(self):
        text = HEADER + "\n".join(en + " 123.45 U/mL 1 - 2" for key, en, ru in CASES)
        # INR is explicitly dimensionless: no unit is supplied for that row.
        text = text.replace("international normalized ratio 123.45 U/mL", "international normalized ratio 123.45")
        (self.forms / "missing.txt").write_text(text, encoding="utf-8")
        result = self.run_ingest()
        self.assertEqual(31, result["points_added"], result)
        readings = engine.analyze_labs()["markers"]
        self.assertEqual(set(key for key, _, _ in CASES), set(r["key"] for r in readings))
        for row in readings:
            self.assertEqual(123.45, row["value"])
            self.assertEqual("unconfirmed_rule", row["flag"])
            self.assertFalse(row["abnormal"])
        self.assertIn("not yet confirmed", fmt.labs_report(engine.analyze_labs()))
        self.assertNotIn("[normal", fmt.labs_report(engine.analyze_labs()))
        self.assertEqual("", fmt._fmt_ref(readings[0]))

    def test_confirmation_allows_the_own_forms_corridor_not_a_shipped_default(self):
        self.assertTrue(store.add_lab_point("ca_15_3", "2026-02-02", 99, unit="U/mL",
                                          ref_low=1, ref_high=2)["ok"])
        self.assertEqual("unconfirmed_rule", engine.analyze_labs()["markers"][0]["flag"])
        self.assertTrue(markers_local.confirm("ca_15_3")["ok"])
        self.assertEqual("high", engine.analyze_labs()["markers"][0]["flag"])

    def test_the_browser_cannot_default_an_unconfirmed_rule_to_green(self):
        page = (core._PKG_DIR / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("unconfirmed_rule:{cls:'b-unknown', key:'web.flag.unconfirmed'}", page)
        self.assertIn("if(m.proposed_rule) return t('markers.proposed_no_flag'", page)

    def test_a_unit_change_or_missing_unit_is_named_and_cannot_rewrite_the_series(self):
        (self.forms / "first.txt").write_text(HEADER + "CA 15-3 123.45 U/mL 1 - 2", encoding="utf-8")
        self.assertEqual(1, self.run_ingest()["points_added"])
        before = (self.profile / "labs.json").read_bytes()
        for unit in ("mg/L", ""):
            result = store.add_lab_point("ca_15_3", "2026-02-02", 99, unit=unit)
            self.assertFalse(result["ok"])
            self.assertEqual(before, (self.profile / "labs.json").read_bytes())
        (self.forms / "first.txt").write_text(HEADER + "CA 15-3 99 mg/L 1 - 2", encoding="utf-8")
        result = self.run_ingest()
        self.assertTrue(any(r["reason"] == "marker_unit_refused" for r in result["not_ingested"]))
        self.assertEqual(before, (self.profile / "labs.json").read_bytes())

    def test_known_unit_spellings_match_without_conversion_and_tables_share_the_gate(self):
        for unit in ("U/mL", "Ед/мл"):
            self.assertTrue(store.add_lab_point("ca_15_3", "2026-02-02", 99, unit=unit)["ok"])
        (self.forms / "changed.csv").write_text(
            "Date,Test,Result,Units\n2026-02-03,CA 15-3,999,mg/L\n", encoding="utf-8")
        result = self.run_ingest()
        self.assertEqual(0, result["points_added"])
        self.assertEqual("marker_unit_refused", result["not_ingested"][0]["reason"])
        self.assertFalse(store.add_lab_point("inr", "2026-02-02", 1.1, unit="%")["ok"])
        self.assertTrue(store.add_lab_point("inr", "2026-02-02", 1.1)["ok"])

    def test_confirmation_is_profile_local_and_cannot_shadow_or_survive_a_changed_rule(self):
        raw = core._read_knowledge_raw("lab_markers.json")
        self.assertTrue(markers_local.confirm("ca_15_3")["ok"])
        self.assertEqual("confirmed", core.lab_markers()["markers"]["ca_15_3"]["status"])
        overlay = json.loads(core.markers_overlay_path().read_text(encoding="utf-8"))
        overlay["markers"]["ca_15_3"].update({"unit": "mg/L", "ref_high": 999})
        core.markers_overlay_path().write_text(json.dumps(overlay), encoding="utf-8")
        core.reset_cache()
        spec = core.lab_markers()["markers"]["ca_15_3"]
        self.assertNotIn("unit", spec)
        self.assertNotIn("ref_high", spec)
        changed = copy.deepcopy(raw)
        changed["markers"]["ca_15_3"]["labels"]["en"]["names"].append("new spelling")
        original = core._read_knowledge_raw
        with mock.patch.object(core, "_read_knowledge_raw",
                               side_effect=lambda name: changed if name == "lab_markers.json" else original(name)):
            self.assertEqual("proposed", core.lab_markers()["markers"]["ca_15_3"]["status"])
            self.assertEqual("proposed", next(r["status"] for r in markers_local.listing()["entries"]
                                                if r["key"] == "ca_15_3"))
        self.assertTrue(markers_local.drop("ca_15_3")["ok"])
        self.assertEqual("proposed", core.lab_markers()["markers"]["ca_15_3"]["status"])

    def test_short_names_subclasses_and_antibodies_are_not_total_analytes(self):
        markers = core.lab_markers()["markers"]
        for label, keys in (
            ("Antibodies to immunoglobulin G", ("igg_total",)),
            ("Immunoglobulin G subclass 1", ("igg_total",)),
            ("EBV IgG antibodies", ("igg_total",)),
            ("Vitamin D3", ("vitamin_d2",)),
            ("Free T4", ("t4_total",)),
            ("S100A8 protein", ("s100",)),
            ("HE40", ("he4",)),
            ("IL-60", ("il6",)),
            ("CA 1250", ("ca_125",)),
        ):
            with self.subTest(label=label):
                _, found = il.parse_report(HEADER + label + " 123.45 U/mL 1 - 2", markers)
                self.assertTrue(all(key not in found for key in keys))

    def test_a_missing_or_unknown_printed_unit_is_refused_not_guessed(self):
        for unit in ("", "unknownunit"):
            (self.forms / "unit.txt").write_text(HEADER + "CA 15-3 123.45 " + unit + " 1 - 2", encoding="utf-8")
            result = self.run_ingest()
            self.assertEqual(0, result["points_added"])
            self.assertEqual("marker_unit_refused", result["not_ingested"][0]["reason"])
        self.assertEqual("", il._printed_unit(" 1 U/mLword", 2))

    def test_the_proposals_are_visible_in_the_existing_marker_list(self):
        entries = {r["key"]: r for r in markers_local.listing()["entries"]}
        self.assertTrue(all(key in entries for key, _, _ in CASES))
