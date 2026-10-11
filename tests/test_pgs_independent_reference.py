"""A separately checked reference must not become a blanket quarantine bypass."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, prs
from scholion.pgs_reference import calibration_for
from scholion.pgs_validation import validate
from pgs_support import calibrated


class IndependentReference(unittest.TestCase):
    def setUp(self):
        self.ref = {"pgs_id": "PGS999999", "population": "EUR", "panel": "synthetic-EUR",
                    "mean": 3.0, "std": 2.0, "samples": 503, "model_variants": 32,
                    "minimum_called_positions": 32, "reference_coordinate_build": "GRCh37",
                    "estimation": "normal_mean_sd", "source": "https://example.org/reference",
                    "validation": "All synthetic positions checked",
                    "reference_sample_list_sha256": "2" * 64,
                    "reference_called_sites_sha256": "3" * 64,
                    "model_sha256_by_build": {"GRCh37": "1" * 64, "GRCh38": "1" * 64}}
        self.row = calibrated({"pgs_id": "PGS999999", "percentile": 50.0})
        self.row["score"] = 7.0
        self.row["scoring_validation"].update(genome_build="GRCh38", variants_total=32)
        self.patch = mock.patch.object(core, "_read_knowledge", return_value={"references": [self.ref]})
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_both_checked_builds_use_same_original_model_scale(self):
        for build in ("GRCh37", "GRCh38"):
            row = copy.deepcopy(self.row)
            row.update(genome_build=build, detected_genome_build=build, model_harmonized_build=build)
            row["scoring_validation"]["genome_build"] = build
            got = calibration_for(row, "EUR")
            self.assertAlmostEqual(97.724986805, got["percentile"], places=8)
            self.assertEqual(2.0, got["z_score"])
            self.assertEqual(503, got["validation"]["samples"])

    def test_unknown_changed_or_wrong_population_models_are_not_promoted(self):
        for key, value in (("pgs_id", "PGS888888"), ("score", float("nan")),
                           ("score", True), ("detected_genome_build", "GRCh37"),
                           ("model_harmonized_build", None), ("model_original_build", "GRCh38"),
                           ("build_mismatch", True)):
            self.assertIsNone(calibration_for(dict(self.row, **{key: value}), "EUR"), key)
        self.assertIsNone(calibration_for(self.row, "AFR"))
        for key, value in (("checked", False), ("algorithm", "old-scorer"),
                           ("model_sha256", "4" * 64), ("variants_total", 31),
                           ("genome_build", None)):
            row = copy.deepcopy(self.row)
            row["scoring_validation"][key] = value
            self.assertIsNone(calibration_for(row, "EUR"), key)

    def test_incomplete_or_malformed_reference_cannot_calibrate(self):
        original = dict(self.ref)
        for key, value in (("std", 0), ("mean", float("inf")), ("samples", 10),
                           ("minimum_called_positions", 31), ("estimation", "auroc_approx"),
                           ("source", None), ("reference_called_sites_sha256", None)):
            self.ref.clear()
            self.ref.update(original, **{key: value})
            self.assertIsNone(calibration_for(self.row, "EUR"), key)

    def test_verified_reference_works_when_sidecar_is_unavailable_and_does_not_clear_manual_withdrawal(self):
        sidecar = mock.Mock()
        sidecar.call.side_effect = RuntimeError("No upstream reference")
        headers = {"model_original_build": "GRCh37", "model_harmonized_build": "GRCh38"}
        with mock.patch.object(prs, "_model_build", return_value=headers):
            got = prs._verify_row(sidecar, self.row, self.row, "GRCh38", "EUR")
            self.assertTrue(got["reliable"], got)
            self.assertTrue(got["calibration"]["valid"])
            self.assertEqual("independent_called_reference", got["reference_validation"]["kind"])
            self.assertFalse(prs._verify_row(sidecar, dict(self.row, reliable=False), self.row,
                                            "GRCh38", "EUR")["reliable"])
        sidecar.call.assert_not_called()

    def test_complete_reference_does_not_replace_missing_person_calls(self):
        with mock.patch.object(prs, "_model_build", return_value={
                "model_original_build": "GRCh37", "model_harmonized_build": "GRCh38"}):
            got = prs._verify_row(mock.Mock(), dict(self.row, match_rate=0.8), self.row,
                                  "GRCh38", "EUR")
        self.assertTrue(got["calibration"]["valid"])
        self.assertFalse(got["reading"]["sufficient"])
        self.assertFalse(got["reliable"])
        self.assertFalse(validate(got)["reliable"])


class BundledReferenceProvenance(unittest.TestCase):
    def test_only_aggregate_statistics_ship_with_sources_and_model_hashes(self):
        data = json.loads((Path(core.__file__).parent / "knowledge/prs_references.json")
                          .read_text(encoding="utf-8"))
        for ref in data["references"]:
            self.assertTrue(ref["source"].startswith("https://"))
            self.assertIn("PMID:", ref["model_publication"])
            self.assertIn("PMID:", ref["source_publication"])
            self.assertEqual(ref["model_variants"], ref["minimum_called_positions"])
            self.assertGreaterEqual(ref["samples"], 100)
            for digest in ref["model_sha256_by_build"].values():
                self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.assertFalse(set(ref) & {"weights", "effect_weight", "genotypes", "scores", "sample_ids"})
