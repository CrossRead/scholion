"""A polygenic percentile is printed with two quantities beside it — how stable
the number is, and how informative the model is — and an absent one is named.

Task 132. A bare percentile looks equally convincing for coronary artery
disease and for intelligence; for the second, the reference population moves
the number by fifty points while the model's whole range separates the outcome
by a few. «Signal to method» as one ratio is degenerate (the effect size
cancels out), so the two are separate quantities and both are shown.

Task 131b/c. Every model the server scores now comes back (`top_n` equals
`--models`), so the spread across models exists to be shown; and the number of
candidates not scored travels with the rule behind it, which is the client's
own `--models`, rather than as a bare count.
"""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import format as fmt
from scholion import prs
from scholion.engine import prs_quality


def _profile(d: Path, results: dict, sensitivity: dict | None = None) -> None:
    (d / "prs_results.json").write_text(json.dumps(results), encoding="utf-8")
    if sensitivity is not None:
        (d / "prs_ancestry_sensitivity.json").write_text(json.dumps(sensitivity),
                                                        encoding="utf-8")


FULL = {"label": "Coronary artery disease", "category": "Cardiovascular", "term": "cad",
        "pgs_id": "PGS000010", "percentile": 71.0, "reliable": True,
        "match_rate": 0.96, "weight_mass_coverage": 0.93,
        "effect_size": "HR=1.17 [1.13-1.21]", "auroc_estimate": 0.62,
        "models": {"scored": 3, "spread_pp": 17.0, "percentiles": [58.0, 71.0, 75.0],
                   "candidates": 88, "not_scored": 85, "not_scored_rule": "limit"}}
BARE = {"label": "Intelligence", "category": "Cognitive", "term": "iq",
        "pgs_id": "PGS001919", "percentile": 30.0, "reliable": True}
SENS = {"traits": [{"term": "cad", "pgs_id": "PGS000010", "spread": 26.7,
                    "pct_by_pop": {"EUR": 71, "AFR": 55, "AMR": 60, "EAS": 81, "SAS": 66}}]}


class TestTheEffectSizeIsReadAsTheCatalogueWritesIt(unittest.TestCase):

    def test_hazard_odds_and_beta(self):
        self.assertEqual({"kind": "HR", "per_sd": 1.17},
                         prs_quality.effect_size("HR=1.17 [1.13-1.21]"))
        self.assertEqual({"kind": "OR", "per_sd": 1.5}, prs_quality.effect_size("OR=1.50"))
        self.assertEqual({"kind": "Beta", "per_sd": -0.21},
                         prs_quality.effect_size("Beta=-0.21 [-0.23--0.19]"))
        self.assertEqual("Beta", prs_quality.effect_size("β=0.3")["kind"])

    def test_anything_else_is_absent_not_zero(self):
        for junk in (None, "", "n/a", "1.17", {"HR": 1.17}):
            self.assertIsNone(prs_quality.effect_size(junk), repr(junk))


class TestTheTwoQuantitiesAreComputedAndAbsencesAreNamed(unittest.TestCase):

    def test_a_trait_with_everything_and_a_trait_with_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            _profile(Path(d), {"traits": []}, SENS)
            unpin = support.pin_profile(Path(d))
            try:
                full, bare = dict(FULL), dict(BARE)
                prs_quality.annotate_measurement([full, bare])
            finally:
                unpin()
        st, inf = full["stability"], full["informativeness"]
        self.assertEqual(26.7, st["ancestry_spread_pp"])
        self.assertEqual(5, st["populations"])
        self.assertEqual(17.0, st["models_spread_pp"])
        self.assertEqual(3, st["models_scored"])
        self.assertEqual(96.0, st["coverage_pct"])
        self.assertEqual([], st["missing"])
        self.assertEqual("HR", inf["kind"])
        self.assertEqual(0.62, inf["auroc"])
        self.assertAlmostEqual(1.17 ** prs_quality.P90_P10_SD, inf["p90_vs_p10_ratio"], places=2)
        self.assertIsNone(inf["p90_vs_p10_shift"])
        self.assertEqual([], inf["missing"])
        st, inf = bare["stability"], bare["informativeness"]
        self.assertEqual(["ancestry_spread_pp", "models_spread_pp", "coverage_pct"], st["missing"],
                         "an absent figure must be NAMED — a line with one number and a "
                         "line with three look alike only when the missing two are silent")
        self.assertEqual(["auroc", "per_sd"], inf["missing"])

    def test_the_ancestry_figure_is_not_borrowed_from_another_model(self):
        with tempfile.TemporaryDirectory() as d:
            _profile(Path(d), {"traits": []}, SENS)
            unpin = support.pin_profile(Path(d))
            try:
                moved = dict(FULL, pgs_id="PGS999999")
                prs_quality.annotate_measurement([moved])
            finally:
                unpin()
        self.assertIsNone(moved["stability"]["ancestry_spread_pp"],
                          "the spread was measured on another model's sum")

    def test_a_beta_gives_a_shift_not_a_ratio(self):
        with tempfile.TemporaryDirectory() as d:
            _profile(Path(d), {"traits": []})
            unpin = support.pin_profile(Path(d))
            try:
                t = dict(BARE, effect_size="Beta=0.46")
                prs_quality.annotate_measurement([t])
            finally:
                unpin()
        self.assertIsNone(t["informativeness"]["p90_vs_p10_ratio"])
        self.assertAlmostEqual(0.46 * prs_quality.P90_P10_SD, t["informativeness"]["p90_vs_p10_shift"], places=2)


class TestTheReportPrintsBothUnderEveryPercentile(unittest.TestCase):

    def test_numbers_where_they_exist_and_words_where_they_do_not(self):
        with tempfile.TemporaryDirectory() as d:
            _profile(Path(d), {"traits": []}, SENS)
            unpin = support.pin_profile(Path(d))
            try:
                full, bare = dict(FULL), dict(BARE)
                prs_quality.annotate_measurement([full, bare])
            finally:
                unpin()
        text = fmt.prs_report({"available": True, "stats": {"total": 2, "reliable": 2,
                                                             "ancestry_stated": True},
                               "categories": [{"category": "Cardiovascular", "traits": [full]},
                                              {"category": "Cognitive", "traits": [bare]}],
                               "high": [], "disclaimer": "d"})
        self.assertEqual(2, text.count("↳"), text)
        self.assertIn("26.7", text)
        self.assertIn("17.0", text)
        self.assertIn("AUROC 0.62", text)
        self.assertIn("HR P90 vs P10 ×", text)
        self.assertIn("not recorded", text)
        self.assertIn("effect size not stated", text)
        self.assertIn("STABILITY", text, "the legend explains the two quantities once")


class TestEveryScoredModelComesBackAndTheRuleTravels(unittest.TestCase):

    def test_models_summary_names_the_rule_and_the_spread(self):
        rep = {"n_scored": 3, "n_returned": 3, "n_skipped": 85, "n_failed": 0,
               "rows": [{"pgs_id": "PGS1", "percentile": 58.0, "percentile_reliable": True},
                        {"pgs_id": "PGS2", "percentile": 71.0, "percentile_reliable": True},
                        {"pgs_id": "PGS3", "percentile": 99.0, "percentile_reliable": False}]}
        m = prs._models_summary(rep, 3)
        self.assertEqual(88, m["candidates"])
        self.assertEqual(85, m["not_scored"])
        self.assertEqual("limit", m["not_scored_rule"])
        self.assertEqual([58.0, 71.0], m["percentiles"],
                         "a percentile the server itself calls unreliable is not spread over")
        self.assertEqual(13.0, m["spread_pp"])
        self.assertEqual(["PGS1", "PGS2", "PGS3"], m["pgs_ids"])

    def test_one_reliable_row_has_no_spread(self):
        self.assertIsNone(prs._models_summary({"rows": [{"percentile": 5, "percentile_reliable": True}]}, 3)["spread_pp"])

    def test_the_client_asks_for_every_scored_model(self):
        restore = support.pin_profile(support.ROOT / "tests" / "fixtures" / "profile")
        self.addCleanup(restore)
        calls = []

        class FakeMCP:
            def __init__(self, *a, **k):
                pass

            def call(self, name, args):
                calls.append((name, dict(args)))
                return {"n_scored": 2, "n_returned": 2, "n_skipped": 4, "n_failed": 0,
                        "rows": [{"pgs_id": "A", "percentile": 40.0, "percentile_reliable": True},
                                 {"pgs_id": "B", "percentile": 52.0, "percentile_reliable": True}]}

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as d:
            vcf = Path(d) / "g.vcf.gz"
            vcf.write_bytes(b"")
            with mock.patch.object(prs, "_MCP", FakeMCP):
                res = prs.report(str(vcf), traits=[{"label": "T", "term": "t", "efo_id": "EFO_1"}],
                                 normalize=False, models_per_trait=5, superpopulation="EUR")
        compute = [a for n, a in calls if n == "compute_prs_by_trait"][0]
        self.assertEqual(5, compute["limit"])
        self.assertEqual(5, compute["top_n"], "top_n=1 trimmed the answer to the server's "
                                              "favourite: three scored, one seen")
        models = res["traits"][0]["models"]
        self.assertEqual(12.0, models["spread_pp"])
        self.assertEqual(6, models["candidates"])


class TestTheStoredPanelCarriesWhatTheReportLearned(unittest.TestCase):

    def test_build_row_keeps_models_and_auroc(self):
        path = support.ROOT / "src" / "ingest" / "prs_results_build.py"
        if not path.exists():
            self.skipTest("src/ingest is not part of this build")
        spec = importlib.util.spec_from_file_location("prs_results_build", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        t = {"label": "T", "category": "C", "term": "t", "status": "ok",
             "chosen": {"pgs_id": "PGS000010", "percentile": 71.0, "percentile_reliable": True,
                        "match_rate": 0.96, "auroc_estimate": 0.62, "effect_size": "HR=1.17"},
             "models": {"scored": 3, "spread_pp": 17.0, "percentiles": [58.0, 71.0, 75.0],
                        "candidates": 88, "not_scored": 85, "not_scored_rule": "limit",
                        "pgs_ids": ["PGS000010", "PGS2", "PGS3"], "returned": 3}}
        row, usable = mod.build_row(t, "2026-09-08")
        self.assertTrue(usable)
        self.assertEqual(0.62, row["auroc_estimate"])
        self.assertEqual(17.0, row["models"]["spread_pp"])
        self.assertEqual("limit", row["models"]["not_scored_rule"])
        self.assertNotIn("returned", row["models"], "only the named fields travel")


if __name__ == "__main__":
    unittest.main()
