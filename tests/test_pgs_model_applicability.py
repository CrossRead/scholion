"""Study-population evidence never reinstates or substitutes for calibration."""
import copy
import unittest
from unittest import mock

import support  # noqa: F401
from pgs_support import calibrated
from scholion import core, engine, format as fmt, i18n
from scholion.pgs_applicability import annotate, describe


class ModelApplicability(unittest.TestCase):
    def test_pinned_models_have_sourced_coverage_with_explicit_independence(self):
        pinned = core._read_knowledge_raw("prs_models.json")["models"]
        evidence = core._read_knowledge_raw("pgs_population_evidence.json")["models"]
        self.assertEqual({row["pgs_id"] for row in pinned.values()}, set(evidence))
        for model, record in evidence.items():
            with self.subTest(model=model):
                self.assertEqual(f"https://www.pgscatalog.org/rest/score/{model}", record["source"])
                self.assertRegex(record["source_digest"], r"^[a-f0-9]{64}$")
                report = describe(model, record, "EUR")
                self.assertEqual(len(record["evaluation"]), len(report["evaluations"]))
                for item in report["evaluations"]:
                    self.assertTrue(item["independence_label"])
                    self.assertNotIn("⟦", item["independence_label"])
                    if item["kind"] == "separate_publication":
                        self.assertNotEqual("heldout", item["independence"])

    def test_mixed_and_modified_weights_do_not_count_as_separate_evaluation(self):
        cases = (
            ("PGS005270", "EUR", "limited_evidence"),
            ("PGS000031", "AFR", "limited_evidence"),
            ("PGS000031", "EUR", "evaluation_reported"),
            ("PGS000646", "EAS", "no_matching_evaluation"),
            ("PGS000646", None, "unknown_population"),
            ("PGS999999", "EUR", "not_reviewed"),
        )
        for model, population, expected in cases:
            with self.subTest(model=model, population=population):
                row = {"pgs_id": model}
                annotate([row], population)
                self.assertEqual(expected, row["model_applicability"]["status"])
                self.assertEqual(population, row["model_applicability"]["profile_group"])

    def test_model_evidence_uses_current_profile_group_and_preserves_stored_results(self):
        valid = calibrated({"term": "coronary artery disease", "pgs_id": "PGS000010",
                            "percentile": 90})
        legacy = {"term": "chronic lymphocytic leukemia", "pgs_id": "PGS000646",
                  "percentile": 99.9, "reliable": True}
        profile = {"_meta": {"superpopulation": "EUR"}, "traits": [valid, legacy]}
        original = copy.deepcopy(profile)
        with mock.patch.object(core, "prs_results", return_value=profile), \
             mock.patch.object(core, "ancestry", return_value={"value": None, "source": None}), \
             mock.patch("scholion.prs_recompute.recalculation_status",
                        return_value={"required": False, "reason": None}):
            for language in ("en", "ru"):
                with mock.patch.object(i18n._state, "current", language, create=True):
                    report = engine.prs_findings()
                    rows = {r["pgs_id"]: r for c in report["categories"] for r in c["traits"]}
                    self.assertEqual(90, rows["PGS000010"]["percentile"])
                    self.assertIsNone(rows["PGS000646"]["percentile"])
                    self.assertEqual(99.9, rows["PGS000646"]["saved_result"]["value"])
                    for row in rows.values():
                        self.assertEqual("unknown_population", row["model_applicability"]["status"])
                        self.assertIn(row["model_applicability"]["label"], fmt.prs_report(report))
                    self.assertIn("https://www.pgscatalog.org/rest/performance/PPM001331", fmt.prs_report(report))
        self.assertEqual(original, profile)

    def test_unrecognized_model_ids_do_not_acquire_population_evidence(self):
        rows = [{"pgs_id": value, "percentile": 42} for value in
                (None, 123, "PGS000001-extra", "unknown")]
        before = copy.deepcopy(rows)
        annotate(rows, "EUR")
        self.assertEqual(before, rows)
        self.assertTrue(all("model_applicability" not in row for row in rows))

    def test_malformed_performance_records_cannot_establish_population_support(self):
        evidence = {"gwas": [], "training": [], "evaluation": [
            {"id": "PPM000001", "groups": ["INVALID"], "kind": "reported"},
            {"id": "PPM000002", "groups": ["EUR"], "kind": "unsupported"},
            {"id": "not-a-performance", "groups": ["EUR"], "kind": "reported"},
        ]}
        report = describe("PGS000001", evidence, "EUR")
        self.assertEqual("no_evaluation", report["status"])
        self.assertEqual([], report["evaluations"])
        self.assertTrue(report["gwas_label"])
        self.assertTrue(report["training_label"])

    def test_unknown_evaluation_ancestry_and_independence_stay_explicit(self):
        evidence = {"gwas": [], "training": [], "evaluation": [
            {"id": "PPM000001", "groups": [], "kind": "reported",
             "independence": "unverified-import-value"},
        ]}
        before = copy.deepcopy(evidence)
        for language in ("en", "ru"):
            with mock.patch.object(i18n._state, "current", language, create=True):
                report = describe("PGS000001", evidence, "EUR")
                self.assertEqual("evaluation_ancestry_unknown", report["status"])
                self.assertEqual([], report["evaluations"][0]["groups"])
                self.assertEqual("not_established", report["evaluations"][0]["independence"])
                self.assertNotIn("⟦", report["evaluations"][0]["independence_label"])
        self.assertEqual(before, evidence)
