"""A plausible extreme and full coverage cannot stand in for calibration."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import support
from pgs_support import calibrated
from scholion import core, engine, format as fmt, prs
from scholion.pgs_validation import percentile_label, validate


class Calibration(unittest.TestCase):
    def test_display_does_not_round_a_tail_to_p100_or_p0(self):
        for p, expected in ((99.86, "P99.86"), (99.999, "≥P99.99"),
                            (100, "≥P99.99"), (0.001, "≤P0.01"),
                            (0, "≤P0.01"), (None, "—")):
            self.assertEqual(expected, percentile_label(p))

    def test_malformed_build_and_model_metadata_are_withheld_without_crashing(self):
        row = calibrated({"pgs_id": "PGS000001", "percentile": 97.0})
        out = validate(dict(row, detected_genome_build={}, models=["invalid"]))
        self.assertIsNone(out["percentile"])
        self.assertIn("build_unknown", out["build_validation"]["reasons"])

    def test_auroc_p100_is_withdrawn_at_every_coverage(self):
        for coverage in (1.0, 0.95, 0.5):
            row = calibrated({"pgs_id": "PGS000001", "percentile": 100.0,
                              "reliable": True, "match_rate": coverage})
            row["percentile_method"] = "auroc_approx"
            out = validate(row)
            self.assertIsNone(out["percentile"])
            self.assertEqual(100, out["diagnostic_percentile"])
            self.assertFalse(out["reliable"])
            self.assertIn("method_unsupported", out["calibration"]["reasons"])

    def test_theoretical_unknown_or_rejected_reference_cannot_become_a_percentile(self):
        for mode in ("theoretical", "unknown", "rejected", "tampered"):
            row = calibrated({"pgs_id": "PGS000001", "percentile": 99.0})
            if mode == "theoretical":
                row["percentile_method"] = "theoretical"
            elif mode == "unknown":
                row.pop("percentile_method")
            elif mode == "rejected":
                row["reference_validation"]["quality"] = "rejected"
            else:
                row["reference_std"] = 2.0
            self.assertIsNone(validate(row)["percentile"], mode)

    def test_an_extreme_from_a_verified_reference_survives(self):
        for p in (0.0, 15.87, 50.0, 84.13, 100.0):
            row = calibrated({"pgs_id": "PGS000001", "percentile": p})
            out = validate(row)
            self.assertTrue(out["reliable"], out)
            self.assertEqual(p, out["percentile"])

    def test_build_origin_can_differ_but_effective_coordinates_must_match(self):
        row = calibrated({"pgs_id": "PGS000001", "percentile": 97.0})
        self.assertTrue(validate(row)["reliable"])
        for bad in (None, "GRCh37", "T2T-CHM13v2.0"):
            changed = dict(row, detected_genome_build=bad)
            self.assertIsNone(validate(changed)["percentile"])
        self.assertIsNone(validate(dict(row, build_mismatch=True))["percentile"])

    def test_population_and_numerical_consistency_are_checked(self):
        row = calibrated({"pgs_id": "PGS000001", "percentile": 97.0})
        self.assertIsNone(validate(row, expected_ancestry="AFR")["percentile"])
        for key, value in (("score", float("nan")), ("reference_std", 0),
                           ("z_score", 0), ("percentile", 50), ("score", True)):
            self.assertIsNone(validate(dict(row, **{key: value}))["percentile"])

    def test_reading_and_informativeness_do_not_validate_calibration(self):
        row = calibrated({"pgs_id": "PGS000001", "percentile": 97.0,
                          "weight_mass_coverage": 0.5, "auroc_estimate": 0.99})
        got = validate(row)
        self.assertTrue(got["calibration"]["valid"])
        self.assertFalse(got["reading"]["sufficient"])
        self.assertFalse(got["reliable"])
        self.assertFalse(validate(dict(row, weight_mass_coverage=None))["reliable"])

    def test_legacy_note_and_model_spread_remain_diagnostic_only(self):
        got = validate({"pgs_id": "PGS000001", "percentile": 100,
                        "reliable": True, "validity_note": "Old claim about EUR",
                        "models": {"spread_pp": 76, "percentiles": [24, 100]}})
        self.assertIsNone(got["percentile"])
        self.assertNotIn("validity_note", got)
        self.assertEqual("Old claim about EUR", got["diagnostic_validity_note"])
        self.assertIsNone(got["models"]["spread_pp"])
        self.assertEqual(100, validate(got)["diagnostic_percentile"])


class Bridge(unittest.TestCase):
    def test_unknown_build_refuses_before_starting_the_sidecar(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.vcf"
            path.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
            with mock.patch("scholion.genome.assembly_evidence", return_value={"assembly": None}), \
                 mock.patch.object(prs, "_MCP") as sidecar:
                got = prs.report(str(path), traits=[{"term": "t", "label": "T"}])
            self.assertFalse(got["ok"])
            sidecar.assert_not_called()

    def test_build_passes_to_both_calls_and_bad_fallback_cannot_win(self):
        calls = []
        bad = calibrated({"pgs_id": "PGS000001", "percentile": 100.0})
        good = calibrated({"pgs_id": "PGS000002", "percentile": 50.0})

        class Sidecar:
            def call(self, name, args):
                calls.append((name, dict(args)))
                if name == "normalize_vcf":
                    return {"genotypes_path": "synthetic.parquet"}
                if name == "compute_prs_by_trait":
                    return {"genome_build": "GRCh38", "detected_genome_build": "GRCh38",
                            "build_mismatch": False, "rows": [dict(bad), dict(good)]}
                row = bad if args["pgs_id"] == bad["pgs_id"] else good
                return {"method": "auroc_approx" if row is bad else "reference_panel",
                        "reliable": True, **{k: row[k] for k in
                         ("z_score", "reference_mean", "reference_std", "reference_panel", "reference_panel_ancestry")}}
            def close(self):
                pass

        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.vcf"; path.write_text("synthetic", encoding="utf-8")
            with mock.patch.object(prs, "_MCP", Sidecar), \
                 mock.patch("scholion.genome.assembly_evidence", return_value={"assembly": "GRCh38"}), \
                 mock.patch.object(prs, "_model_build", return_value={"model_harmonized_build": "GRCh38", "model_original_build": "GRCh37"}):
                report = prs.report(str(path), traits=[{"term": "t", "label": "T", "efo_id": "EFO_TEST"}], superpopulation="EUR")
        self.assertEqual("PGS000002", report["traits"][0]["chosen"]["pgs_id"])
        self.assertEqual([50.0], report["traits"][0]["models"]["percentiles"])
        for name, args in calls:
            if name in ("normalize_vcf", "compute_prs_by_trait"):
                self.assertEqual("GRCh38", args["genome_build"])

    def test_model_header_selects_harmonized_build_without_copying_weights(self):
        import gzip
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "scores"; p.mkdir()
            with gzip.open(p / "PGS000001_hmPOS_GRCh38.txt.gz", "wt", encoding="utf-8") as handle:
                handle.write("#genome_build=GRCh37\n#HmPOS_build=GRCh38\nchr_name\teffect_weight\n1\t1\n")
            with mock.patch.object(prs, "_cache_root", return_value=Path(temp)):
                got = prs._model_build("PGS000001", "GRCh38")
        self.assertEqual("GRCh37", got["model_original_build"])
        self.assertEqual("GRCh38", got["model_harmonized_build"])
        self.assertNotIn("effect_weight", got)


class StoredResults(unittest.TestCase):
    def test_three_legacy_p100_are_not_high_on_cli_web_or_panels(self):
        rows = [{"term": term, "label": term, "pgs_id": "PGS000001", "percentile": 100,
                 "match_rate": 1.0, "weight_mass_coverage": 1.0, "reliable": True}
                for term in ("chronic lymphocytic leukemia", "systemic lupus erythematosus", "hypothyroidism")]
        rows.append(calibrated({"term": "coronary artery disease", "label": "CAD", "pgs_id": "PGS000002", "percentile": 97.0}))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp); (path / "prs_results.json").write_text(json.dumps({"traits": rows}), encoding="utf-8")
            restore = support.pin_profile(path)
            try:
                core.reset_cache()
                got = engine.prs_findings()
                self.assertEqual(["coronary artery disease"], [r["term"] for r in got["high"]])
                text = fmt.prs_report(got)
                self.assertNotIn("P100", text)
                self.assertIn("Percentile withheld", text)
                self.assertEqual(1, got["stats"]["reliable"])
            finally:
                restore(); core.reset_cache()

    def test_builder_preserves_provenance_and_does_not_keep_an_unverified_old_value(self):
        path = support.ROOT / "src/ingest/prs_results_build.py"
        if not path.exists():
            self.skipTest("ingest scripts are absent")
        spec = importlib.util.spec_from_file_location("pgs_builder_test", path)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        good = calibrated({"pgs_id": "PGS000001", "percentile": 97.0})
        row, usable = mod.build_row({"term": "t", "status": "ok", "chosen": good}, "2026-10-09")
        self.assertTrue(usable)
        self.assertEqual(good["reference_validation"], row["reference_validation"])
        with tempfile.TemporaryDirectory() as temp:
            d = Path(temp); mod.RESULTS = d / "prs_results.json"; mod.REGISTRY = d / "registry.json"
            mod.RESULTS.write_text(json.dumps({"traits": [{"term": "t", "pgs_id": "PGS000001", "percentile": 100, "reliable": True}]}), encoding="utf-8")
            raw = d / "raw.json"; raw.write_text(json.dumps({"traits": [{"term": "t", "status": "ok", "chosen": dict(good, percentile_method="auroc_approx")}]}), encoding="utf-8")
            self.assertEqual(0, mod.main(["build", str(raw)]))
            result = json.loads(mod.RESULTS.read_text(encoding="utf-8"))["traits"][0]
        self.assertIsNone(result["percentile"])
        self.assertFalse(result["reliable"])
        self.assertEqual(100, result["previous_result"]["diagnostic_percentile"])


if __name__ == "__main__":
    unittest.main()
