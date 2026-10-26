"""Sourced LOINC mappings keep specimen, method, date and component identity."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import support
from scholion import core, engine, ingest_fhir, store


def observation(code, value=5.1, unit="mmol/L", **extra):
    return {"resourceType": "Observation", "id": "synthetic-observation",
            "status": "final", "effectiveDateTime": "2024-03-02T10:00:00Z",
            "code": {"coding": [{"system": ingest_fhir.LOINC_SYSTEM, "code": code}]},
            "valueQuantity": {"value": value, "code": unit}, **extra}


class FhirMeasurementIdentity(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="synthetic-fhir-identity-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.addCleanup(support.pin_profile(self.profile))
        self.addCleanup(support.pin_cache(self.root / "cache"))
        core.reset_cache(); self.addCleanup(core.reset_cache)
        self.path = self.root / "synthetic.json"

    def write(self, *rows):
        self.path.write_text(json.dumps({"resourceType": "Bundle", "entry": [
            {"resource": r} for r in rows]}), encoding="utf-8")
        return self.path

    def test_whole_blood_and_serum_glucose_are_not_one_series(self):
        self.write(observation("2339-0", 90, "mg/dL"), observation("2345-7", 100, "mg/dL"))
        result = ingest_fhir.ingest(str(self.path))
        self.assertFalse(result["refused"], result)
        markers = core.labs()["markers"]
        self.assertIn("glucose_blood", markers)
        self.assertIn("glucose", markers)
        self.assertAlmostEqual(90 * 0.05551, markers["glucose_blood"]["series"][0]["value"], places=3)

    def test_method_unspecified_blood_calcium_does_not_replace_icp(self):
        self.assertEqual("mg/L", core.lab_markers()["markers"]["calcium_blood"]["unit"])
        self.assertEqual("icp", core.lab_markers()["markers"]["calcium_blood"]["method"])
        result = ingest_fhir.ingest(str(self.write(observation("49765-1", 9, "mg/dL"))))
        self.assertEqual(["calcium_blood_reported"], result["added"])
        self.assertNotIn("calcium_blood", core.labs()["markers"])
        marker = core.labs()["markers"]["calcium_blood_reported"]
        self.assertEqual("mg/dL", marker["unit"])
        self.assertEqual(9, marker["series"][0]["value"])
        self.assertNotIn("ref_low", marker["series"][0])

    def test_serum_calcium_code_does_not_use_the_elemental_blood_row(self):
        self.assertEqual("calcium_total", core.loinc_index()["17861-6"])
        result = ingest_fhir.ingest(str(self.write(observation("17861-6", 9, "mg/dL"))))
        self.assertEqual(["calcium_total"], result["added"])
        self.assertNotIn("calcium_blood", core.labs()["markers"])
        self.assertAlmostEqual(2.2455, core.labs()["markers"]["calcium_total"]["series"][0]["value"])

    def test_mdrd_is_never_recorded_as_ckdepi(self):
        self.write(observation("33914-3", 85, "mL/min/{1.73_m2}"))
        result = ingest_fhir.ingest(str(self.path))
        self.assertEqual(["egfr_mdrd"], result["added"])
        self.assertNotIn("egfr_ckdepi", core.labs()["markers"])
        self.assertEqual("MDRD", core.labs()["markers"]["egfr_mdrd"]["series"][0]["method"])

    def test_fasting_direct_assay_and_urine_contexts_survive(self):
        self.write(observation("1558-6", 90, "mg/dL"), observation("18262-6", 100, "mg/dL"),
                   observation("14959-1", 10, "mg/g"))
        result = ingest_fhir.ingest(str(self.path))
        self.assertFalse(result["refused"], result)
        markers = core.labs()["markers"]
        self.assertTrue(markers["glucose"]["series"][0]["fasting"])
        self.assertEqual("direct_assay", markers["ldl"]["series"][0]["method"])
        self.assertEqual("urine", markers["microalbumin_creatinine_ratio"]["series"][0]["specimen"])

    def test_parent_pressure_components_keep_their_date_and_identity(self):
        parent = observation("85354-9")
        parent.pop("valueQuantity")
        parent["component"] = [{k: v for k, v in observation(c, value, "mm[Hg]").items()
                                 if k in ("code", "valueQuantity")}
                               for c, value in [("8480-6", 120), ("8462-4", 80)]]
        self.write(parent)
        result = ingest_fhir.ingest(str(self.path))
        self.assertEqual(1, result["observations"])
        self.assertEqual(2, result["measurement_entries"])
        self.assertEqual({"systolic_bp", "diastolic_bp"}, set(result["added_metrics"]))
        metrics = core.metrics_json()["metrics"]
        for index, key in enumerate(["systolic_bp", "diastolic_bp"]):
            point = metrics[key]["series"][0]
            self.assertEqual("2024-03-02T10:00", point["date"])
            self.assertEqual(index, point["source_record"]["component"])
            self.assertEqual(parent["id"], point["source_record"]["resource_id"])

    def test_invalid_or_nonfinite_quantity_is_a_named_refusal(self):
        for value in [True, float("nan"), float("inf"), "not numeric"]:
            with self.subTest(value=value):
                result = ingest_fhir.plan(self.write(observation("2345-7", value)))
                self.assertEqual([], result["points"])
                self.assertEqual("invalid_quantity", result["skipped"][0]["reason"])

    def test_conflicting_lab_codes_are_not_resolved_by_the_first(self):
        row = observation("2345-7")
        row["code"]["coding"].append({"system": ingest_fhir.LOINC_SYSTEM, "code": "2160-0"})
        result = ingest_fhir.plan(self.write(row))
        self.assertEqual("ambiguous_loinc", result["skipped"][0]["reason"])

    def test_invalid_collection_date_writes_nothing(self):
        row = observation("2345-7", effectiveDateTime="2024-02-31")
        result = ingest_fhir.ingest(str(self.write(row)))
        self.assertEqual([], result["added"])
        self.assertFalse((self.profile / "labs.json").exists())
        self.assertEqual("invalid_date", result["skipped"][0]["reason"])

    def test_unlike_reference_units_do_not_stamp_a_wrong_interval(self):
        row = observation("2345-7", referenceRange=[{"low": {"value": 70, "code": "mg/dL"}}])
        result = ingest_fhir.plan(self.write(row))
        self.assertEqual("reference_unit_mismatch", result["skipped"][0]["reason"])

    def test_issue_date_remains_approximate_not_a_collection_date(self):
        row = observation("2345-7", issued="2024-03-03T11:00:00Z")
        row.pop("effectiveDateTime")
        ingest_fhir.ingest(str(self.write(row)))
        point = core.labs()["markers"]["glucose"]["series"][0]
        self.assertEqual("issued", point["date_source"])
        self.assertIn("issued", store.DATE_APPROXIMATE)

    def test_manual_replacement_drops_source_row_identity(self):
        ingest_fhir.ingest(str(self.write(observation("2345-7"))))
        store.add_lab_point("glucose", "2024-03-02T10:00", 5.5, unit="mmol/L",
                            date_source="manual", subject="owner")
        self.assertNotIn("source_record", core.labs()["markers"]["glucose"]["series"][0])

    def test_imported_vital_labels_switch_language_without_reimport(self):
        ingest_fhir.ingest(str(self.write(observation("8867-4", 70, "/min"))))
        from scholion import i18n
        previous = i18n.lang(); self.addCleanup(i18n.set_lang, previous)
        for lang, name in [("en", "Heart rate at measurement"), ("ru", "Пульс во время измерения")]:
            i18n.set_lang(lang)
            result = engine.metrics_summary()
            self.assertIn(name, str(result))

    def test_configured_folder_import_uses_the_same_fhir_core(self):
        from scholion import ingest_labs
        folder = self.root / "inputs"
        folder.mkdir()
        self.path = folder / "synthetic.json"
        self.write(observation("2339-0", 90, "mg/dL"), observation("8480-6", 120, "mm[Hg]"))
        result = ingest_labs.ingest(str(folder))
        self.assertFalse(result.get("errors"), result)
        self.assertEqual(1, result["files_processed"])
        self.assertEqual(1, result["points_added"])
        self.assertEqual(1, result["metrics_added"])
        self.assertEqual("2024-03-02T10:00", core.labs()["markers"]["glucose_blood"]["series"][0]["date"])
        self.assertEqual(120, core.metrics_json()["metrics"]["systolic_bp"]["series"][0]["value"])
        self.assertEqual(1, ingest_labs.ingest(str(folder))["skipped"])

    def test_assistant_folder_import_runs_the_fhir_path(self):
        from scholion import ouroboros_tools
        folder = self.root / "inputs"
        folder.mkdir()
        self.path = folder / "synthetic.json"
        self.write(observation("8480-6", 120, "mm[Hg]"))
        result = ouroboros_tools._h_ingest_labs(None, folder=str(folder))
        self.assertIn("body measurements", result)
        self.assertEqual(120, core.metrics_json()["metrics"]["systolic_bp"]["series"][0]["value"])

    def test_named_external_score_is_not_a_new_scholion_risk(self):
        result = ingest_fhir.plan(self.write(observation("65853-4", 9.4, "%")))
        self.assertEqual([], result["points"])
        self.assertEqual([], result["metrics"])
        self.assertEqual("external_score_not_supported", result["skipped"][0]["reason"])
        self.assertIn("loinc.org", result["skipped"][0]["source"]["url"])
