"""Actual called alleles, not coordinate joins, determine a PGS sum."""
from __future__ import annotations
import gzip
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import support
from pgs_support import calibrated
from scholion import prs
from scholion.pgs_scoring import ScoringVCF, dosage
from scholion.pgs_validation import validate


class CalledAlleles(unittest.TestCase):
    def test_multiallelic_phase_and_softmask_are_decoded(self):
        for e, other, rec, expected in [
                ("G", "A", ("a", ["c", "g"], [1, 2]), 1),
                ("C", "T", ("c", ["cG"], [0, 1]), 1),
                ("A", "G", ("A", ["G"], [0, 0]), 2),
                ("G", "A", ("A", ["."], [0, 0]), 0),
                ("G", "", ("A", ["C"], [1, 1]), 0)]:
            with self.subTest(rec=rec):
                self.assertEqual(expected, dosage(e, other, [rec])[0])

    def test_flip_requires_a_known_non_palindromic_pair(self):
        rec = ("G", ["A"], [0, 1])
        self.assertEqual((1, "flip"), dosage("T", "C", [rec]))
        self.assertEqual((0, "zero"), dosage("T", "", [rec]))
        self.assertEqual((1, "carried"), dosage("A", "T", [("T", ["A"], [0, 1])]))
        self.assertIsNone(dosage("AC", "GT", [("GT", ["AC"], [])])[0])

    def test_incomplete_symbolic_and_conflicting_calls_are_excluded(self):
        for recs in [[("A", ["G"], [0])], [("A", ["G"], [0, 9])],
                     [("A", ["<DEL>"], [0, 1])],
                     [("A", ["G"], [0, 1]), ("A", ["G"], [1, 1])]]:
            self.assertIsNone(dosage("G", "A", recs)[0])
        self.assertEqual(1, dosage("G", "A", [("A", ["G"], [0, 1])] * 2)[0])
        self.assertIsNone(dosage("AT", "A", [("A", ["ATT"], [0, 1])])[0])


class LocalScoring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.vcf = self.root / "calls.vcf"
        self.vcf.write_text("##fileformat=VCFv4.2\n##reference=GRCh38\n"
                           "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC\n"
                           "1\t1\t.\ta\tc,g\t.\tPASS\t.\tDP:GT\t20:1|2\n"
                           "1\t2\t.\tc\tcG\t.\tPASS\t.\tGT\t0/1\n"
                           "1\t3\t.\tA\tG\t.\tPASS\t.\tGT\t0/.\n"
                           "1\t4\t.\tA\t.\t.\tPASS\t.\tGT\t0/0\n", encoding="utf-8")
        self.model = self.root / "model.txt.gz"
        self.write_model("1\t1\tG\tA\t2\n1\t2\tC\t\t3\n1\t3\tG\tA\t5\n1\t4\tG\tA\t7\n1\t5\tG\tA\t11\n")

    def write_model(self, rows, header="hm_chr\thm_pos\teffect_allele\tother_allele\teffect_weight"):
        with gzip.open(self.model, "wt", encoding="utf-8") as stream:
            stream.write("#HmPOS_build=GRCh38\n#genome_build=GRCh37\n" + header + "\n" + rows)

    def score(self):
        source = ScoringVCF(self.vcf)
        try:
            return source.score(self.model, "GRCh38")
        finally:
            source.close()

    def test_partial_calls_and_absent_positions_do_not_become_reference_calls(self):
        got = self.score()
        self.assertEqual(5, got["score"])
        self.assertEqual(3, got["variants_matched"])
        self.assertEqual(0.6, got["match_rate"])
        self.assertAlmostEqual(12 / 28, got["weight_mass_coverage"])
        counts = got["scoring_validation"]["counts"]
        self.assertEqual(1, counts["no_call"])
        self.assertEqual(1, counts["missing_position"])
        self.assertEqual(0, got["scoring_validation"]["absent_positions_imputed"])

    def test_duplicate_input_rows_count_once_and_invalid_weights_block_validation(self):
        with self.vcf.open("a", encoding="utf-8") as stream:
            stream.write("1\t1\t.\ta\tc,g\t.\tPASS\t.\tGT\t1/2\n")
        self.assertEqual(5, self.score()["score"])
        self.write_model("1\t1\tG\tA\tnan\n")
        self.assertFalse(self.score()["scoring_validation"]["checked"])

    def test_nonlinear_weights_use_the_actual_dosage(self):
        self.write_model("1\t1\tG\tA\t10\t20\t40\n", "hm_chr\thm_pos\teffect_allele\tother_allele\tdosage_0_weight\tdosage_1_weight\tdosage_2_weight")
        self.assertEqual(20, self.score()["score"])

    def test_build_and_sample_refusals_and_input_change_are_explicit(self):
        source = ScoringVCF(self.vcf)
        try:
            with self.assertRaises(ValueError):
                source.score(self.model, "GRCh37")
            with self.vcf.open("a", encoding="utf-8") as stream:
                stream.write("\n")
            with self.assertRaises(ValueError):
                source.score(self.model, "GRCh38")
        finally:
            source.close()
        self.vcf.write_text(self.vcf.read_text(encoding="utf-8").replace("\tSYNTHETIC\n", "\tSYNTHETIC\tSECOND\n"), encoding="utf-8")
        with self.assertRaises(ValueError):
            ScoringVCF(self.vcf)

    def test_recalculation_uses_the_pin_and_calibrates_the_corrected_sum(self):
        self.write_model("1\t1\tG\tA\t2\n")
        cache = self.root / "cache" / "scores"
        cache.mkdir(parents=True)
        (cache / "PGS000001_hmPOS_GRCh38.txt.gz").write_bytes(self.model.read_bytes())
        calls = []
        class Sidecar:
            reference_contract_verified = True
            def call(self, name, args):
                calls.append((name, args))
                if name == "search_traits":
                    return {"traits": []}
                if name == "search_scores":
                    return {"scores": [{"pgs_id": "PGS000001", "variants_number": 1, "trait_reported": "test"}]}
                if name == "compute_prs":
                    return {"pgs_id": "PGS000001", "score": 99, "percentile": 100}
                if name == "percentile":
                    score = args["prs_score"]
                    return {"percentile": 50 * math.erfc(-score / math.sqrt(2)),
                            "method": "reference_panel", "reliable": True,
                            "reference_mean": 0, "reference_std": 1, "z_score": score,
                            "reference_panel": "synthetic", "reference_panel_ancestry": "EUR"}
                raise AssertionError(name)
            def close(self):
                pass
        restore = support.pin_profile(support.ROOT / "tests/fixtures/profile")
        self.addCleanup(restore)
        with mock.patch.object(prs, "_pinned_models", return_value={"test": {"pgs_id": "PGS000001"}}), \
             mock.patch.object(prs, "_MCP", return_value=Sidecar()), \
             mock.patch.dict(os.environ, {"PRS_MCP_CACHE_DIR": str(cache.parent)}):
            result = prs.report(str(self.vcf), traits=[{"term": "test"}], normalize=False, superpopulation="EUR")
        row = result["traits"][0]["chosen"]
        self.assertEqual(2, row["score"])
        self.assertEqual(99, row["sidecar_diagnostic_score"])
        self.assertTrue(row["reliable"], row)
        self.assertEqual("pinned", result["traits"][0]["selection"])
        self.assertFalse(any(n in ("search_traits", "compute_prs_by_trait") for n, _ in calls))
        with mock.patch.object(prs, "_pinned_models", return_value={}), \
             mock.patch.object(prs, "_MCP", return_value=Sidecar()), \
             mock.patch.dict(os.environ, {"PRS_MCP_CACHE_DIR": str(cache.parent)}):
            resolved = prs.report(str(self.vcf), traits=[{"term": "test"}], normalize=False, superpopulation="EUR")
        self.assertEqual("ok_fallback", resolved["traits"][0]["status"])
        self.assertEqual(2, resolved["traits"][0]["fallback"]["result"]["score"])
        invalid = dict(row, scoring_validation=dict(row["scoring_validation"], checked=False))
        self.assertIsNone(validate(invalid)["percentile"])

    def test_null_summary_count_is_resolved_without_accepting_another_endpoint(self):
        search = {"scores": [{"pgs_id": "PGS000001", "variants_number": None, "trait_reported": "test"},
                             {"pgs_id": "PGS000002", "variants_number": 10, "trait_reported": "parental test"}]}
        sidecar = mock.Mock()
        sidecar.call.side_effect = lambda name, args: search if name == "search_scores" else {"pgs_id": args["pgs_id"]}
        good = calibrated({"pgs_id": "PGS000001"})
        with mock.patch("scholion.net.get_json", return_value={"variants_number": 4}), \
             mock.patch.object(prs, "_score_row", return_value=good):
            result, error = prs._search_scores_fallback(sidecar, "test", None, str(self.vcf),
                                                        genome_build="GRCh38", source=mock.Mock())
        self.assertIsNone(error)
        self.assertEqual("PGS000001", result["pgs_id"])
        self.assertEqual(["PGS000001"], result["candidates_checked"])
        computed = [call.args[1]["pgs_id"] for call in sidecar.call.call_args_list if call.args[0] == "compute_prs"]
        self.assertEqual(["PGS000001"], computed)


    def test_vcf_only_scoring_needs_no_bam_and_explicit_reference_calls_count(self):
        self.write_model("1\t4\tG\tA\t7\n")
        got = self.score()
        self.assertEqual(1, got['match_rate'])
        self.assertEqual(1, got['weight_mass_coverage'])
        self.assertEqual(0, got['score'])
        self.assertEqual(0, got['scoring_validation']['absent_positions_imputed'])

class ModelPins(unittest.TestCase):
    def test_an_unusable_or_missing_old_row_does_not_permit_a_model_switch(self):
        path = support.ROOT / "src/ingest/prs_results_build.py"
        if not path.exists():
            self.skipTest("Ingest tools are not in this build")
        spec = importlib.util.spec_from_file_location("pin_builder", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for old in ({}, {"traits": [{"term": "test", "pgs_id": "PGS000001", "reliable": False}]}):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp).resolve()
                mod.RESULTS = root / "prs_results.json"
                mod.REGISTRY = root / "registry.json"
                mod.RESULTS.write_text(json.dumps(old), encoding="utf-8")
                mod.REGISTRY.write_text(json.dumps({"models": {"test": {"pgs_id": "PGS000001"}}}), encoding="utf-8")
                raw = root / "raw.json"
                raw.write_text(json.dumps({"traits": [{"term": "test", "status": "ok", "chosen": calibrated({"pgs_id": "PGS000002"})}]}), encoding="utf-8")
                self.assertEqual(0, mod.main(["build", str(raw)]))
                result = json.loads(mod.RESULTS.read_text(encoding="utf-8"))["traits"][0]
                self.assertEqual("PGS000001", result["pgs_id"])
                self.assertEqual("PGS000002", result["pending_model_candidate"]["pgs_id"])
                self.assertFalse(result["reliable"])


class RecalculationOffer(unittest.TestCase):
    def test_calibration_cannot_certify_a_legacy_allele_calculation(self):
        row = calibrated({"pgs_id": "PGS000001", "percentile": 97.0})
        for witness in (None, {}, dict(row["scoring_validation"], algorithm="previous")):
            old = dict(row, scoring_validation=witness)
            result = validate(old)
            self.assertIsNone(result["percentile"])
            self.assertEqual(97, result["diagnostic_percentile"])
            self.assertIn("scoring_unverified", result["calibration"]["reasons"])
        self.assertTrue(validate(row)["reliable"])

    def test_the_offer_depends_on_the_calculation_not_the_application_version(self):
        from scholion import core, engine, recompute, format as fmt
        from scholion.pgs_validation import recalculation_status
        current = calibrated({"term": "test", "label": "Test", "pgs_id": "PGS000001", "percentile": 97.0})
        old = dict(current)
        old.pop("scoring_validation")
        self.assertFalse(recalculation_status([current])["required"])
        # Missing reference calibration cannot justify repeating BAM genotyping.
        no_reference = dict(current, percentile_method="unavailable")
        self.assertFalse(recalculation_status([no_reference])["required"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "prs_results.json").write_text(json.dumps({"traits": [old]}), encoding="utf-8")
            restore = support.pin_profile(root)
            self.addCleanup(restore)
            core.reset_cache()
            view = engine.prs_findings()
            self.assertTrue(view["recalculation"]["required"])
            self.assertIn(view["recalculation"]["note"], fmt.prs_report(view))
            with mock.patch("scholion.updates.installed", return_value="0.6.7"):
                plan = recompute.plan(since="0.6.7", text="")
            offers = [s for s in plan["steps"] if s.get("attention_key")]
            self.assertEqual(1, len(offers))
            self.assertEqual("by_hand", offers[0]["state"])
            self.assertNotIn("key", offers[0])
            (root / "prs_results.json").write_text(json.dumps({"traits": [current]}), encoding="utf-8")
            core.reset_cache()
            self.assertFalse(engine.prs_findings()["recalculation"]["required"])
            self.assertFalse(any(s.get("attention_key") for s in recompute.plan(since="0.6.7", text="")["steps"]))
            journal = "## v0.6.7 — 10.10.2026\n\n**By hand — if polygenic scores were computed before this release.**\n\nRecompute PGS.\n"
            upgraded = recompute.plan(since="0.6.6", text=journal)
            self.assertFalse(any(s["state"] == "by_hand" for s in upgraded["steps"]))

    def test_partial_recalculation_does_not_relabel_all_rows_with_the_latest_vcf(self):
        path = support.ROOT / "src/ingest/prs_results_build.py"
        if not path.exists():
            self.skipTest("Ingest tools are not in this build")
        spec = importlib.util.spec_from_file_location("partial_pgs_builder", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        old = calibrated({"term": "old", "pgs_id": "PGS000001", "percentile": 50})
        new = calibrated({"pgs_id": "PGS000002", "percentile": 50})
        old["scoring_validation"]["input_vcf"] = "/synthetic/old.vcf"
        new["scoring_validation"]["input_vcf"] = "/synthetic/new.vcf"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            mod.RESULTS = root / "results.json"
            mod.REGISTRY = root / "registry.json"
            mod.RESULTS.write_text(json.dumps({"traits": [old]}), encoding="utf-8")
            mod.REGISTRY.write_text(json.dumps({"models": {}}), encoding="utf-8")
            raw = root / "raw.json"
            raw.write_text(json.dumps({"vcf": "/synthetic/new.vcf", "traits": [
                {"term": "new", "status": "ok", "chosen": new}]}), encoding="utf-8")
            self.assertEqual(0, mod.main(["build", str(raw)]))
            doc = json.loads(mod.RESULTS.read_text(encoding="utf-8"))
            self.assertEqual(2, doc["_meta"]["reliable_count"])
            self.assertIsNone(doc["_meta"]["input_vcf"])
            self.assertEqual(["/synthetic/new.vcf", "/synthetic/old.vcf"], doc["_meta"]["input_vcfs"])
            self.assertEqual("/synthetic/old.vcf", doc["traits"][0]["scoring_validation"]["input_vcf"])


class ActiveProfileBuilder(unittest.TestCase):
    def test_report_builder_targets_the_selected_profile(self):
        from scholion import core
        path = support.ROOT / "src/ingest/prs_results_build.py"
        if not path.exists():
            self.skipTest("Ingest tools are not in this build")
        with tempfile.TemporaryDirectory() as temp:
            chosen = Path(temp).resolve()
            with mock.patch.object(core, "profile_dir", return_value=chosen):
                spec = importlib.util.spec_from_file_location("selected_pgs_profile", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
            self.assertEqual(chosen / "prs_results.json", mod.RESULTS)
