"""The bug class the first real user hit in one run: a plausible default,
substituted silently, presented with the confidence of a checked fact.

Four defects came out of one afternoon on real lab forms (backlog 65-73). They
are not four accidents; they are one habit appearing four times. Where a
precondition is missing — the person's sex, the row that applies, the marker's
label — the code filled the hole with something plausible instead of saying the
hole was there.

Tasks closed here: 70 (the loop that renamed every marker), 67 (a genetic claim
made with no genome attached), 71 (the male range lent to whoever asked), 72
(the two questions nobody was asked).
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest

import support  # noqa: F401
from scholion import core, format as fmt, store
from scholion.engine import labs

SEX_SPECIFIC = ("uric_acid", "testosterone", "creatinine", "ferritin",
                "hematocrit", "hemoglobin")


class _Profile(unittest.TestCase):
    def _profile(self, markers, sex=None):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        (pathlib.Path(d) / "labs.json").write_text(json.dumps({"markers": markers},
                                                              ensure_ascii=False))
        if sex:
            (pathlib.Path(d) / "metrics.json").write_text(
                json.dumps({"profile": {"sex": sex, "birth_year": 1985}}))
        core.reset_cache()
        return pathlib.Path(d)

    def tearDown(self):
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        core.reset_cache()


class TestTask70TheMarkerKeepsItsName(_Profile):
    def test_a_point_with_a_unit_does_not_rename_the_marker(self):
        self._profile({})
        r = store.add_lab_point("glucose", "2026-07-01", 5.4, name="Глюкоза",
                                unit="mmol/L", ref_low=4.1, ref_high=5.9)
        self.assertTrue(r.get("ok"), r)
        saved = core.labs()["markers"]["glucose"]
        self.assertEqual(saved["name"], "Глюкоза")
        self.assertNotEqual(saved["name"], "ref_high")


class TestTask71TheMaleRangeIsNotLentOut(_Profile):
    """Testosterone 12.1-34.4 in the wife's report was not a typo: it is the
    dictionary default, which for these six markers IS the male interval."""

    def test_the_six_markers_still_keep_the_male_range_as_their_default(self):
        """If this ever stops being true the fix below is aimed at nothing."""
        kb = core.lab_markers()["markers"]
        for k in SEX_SPECIFIC:
            with self.subTest(marker=k):
                male = (kb[k]["ref_by_sex"]["male"]["ref_low"],
                        kb[k]["ref_by_sex"]["male"]["ref_high"])
                self.assertEqual((kb[k]["ref_low"], kb[k]["ref_high"]), male)

    def test_no_corridor_is_shown_when_the_sex_is_unknown(self):
        self._profile({"testosterone": {"name": "Т", "unit": "nmol/L",
                                        "series": [{"date": "2026-07-01", "value": 1.2}]}})
        m = labs.analyze_labs()["markers"][0]
        self.assertIsNone(m["ref_low"])
        self.assertIsNone(m["ref_high"])
        self.assertFalse(m["abnormal"], "a value was flagged against a corridor "
                                        "that may belong to the other sex")

    def test_the_reason_is_printed_rather_than_left_blank(self):
        """`ref_sex_unknown` was computed for months and rendered nowhere."""
        self._profile({"testosterone": {"name": "Т", "unit": "nmol/L",
                                        "series": [{"date": "2026-07-01", "value": 1.2}]}})
        r = labs.analyze_labs()
        self.assertTrue(r["markers"][0]["ref_sex_unknown"])
        out = fmt.labs_report(r)
        self.assertRegex(out, r"(?i)(differs by sex|зависит от пола)")

    def test_with_the_sex_recorded_the_right_corridor_is_used(self):
        self._profile({"testosterone": {"name": "Т", "unit": "nmol/L",
                                        "series": [{"date": "2026-07-01", "value": 1.2}]}},
                      sex="female")
        m = labs.analyze_labs()["markers"][0]
        kb = core.lab_markers()["markers"]["testosterone"]["ref_by_sex"]["female"]
        self.assertEqual((m["ref_low"], m["ref_high"]), (kb["ref_low"], kb["ref_high"]))
        self.assertFalse(m["abnormal"])


class TestTask67NoGeneticClaimWithoutAGenome(unittest.TestCase):
    def test_the_rule_no_longer_asserts_a_variant_nobody_measured(self):
        rules = core.test_rules()["rules"]
        rf = next(r for r in rules if r.get("id") == "rf_autoimmune")
        self.assertNotIn("PADI4", json.dumps(rf["why"], ensure_ascii=False))

    def test_every_rule_that_names_a_gene_gates_on_the_genome(self):
        """The general form of the defect, not the one instance."""
        offenders = []
        for r in core.test_rules()["rules"]:
            why = json.dumps(r.get("why", ""), ensure_ascii=False)
            trigger = json.dumps(r.get("when", ""), ensure_ascii=False)
            claims_gene = any(g in why for g in ("PADI4", "SLCO1B1", "CYP2C9", "APOE", "MTHFR"))
            if claims_gene and "genome_gap" not in trigger and "genome" not in trigger:
                offenders.append(r.get("id"))
        self.assertEqual(offenders, [],
                         "a rule asserts something genetic about the person while its "
                         "trigger never checks that a genome is attached")


class TestTask72TheTwoQuestionsAreAsked(unittest.TestCase):
    def test_the_profile_command_can_record_them(self):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        try:
            core.reset_cache()
            r = store.update_metric_profile({"sex": "female", "birth_year": 1985})
            self.assertTrue(r.get("ok"), r)
            core.reset_cache()
            self.assertEqual(core.profile_sex(), "female")
        finally:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
            core.reset_cache()


if __name__ == "__main__":
    unittest.main()


class TestTask81ThePopulationIsNotASilentDefault(unittest.TestCase):
    """The same anti-pattern as task 71, one layer up: a percentile is a position
    WITHIN a reference population, and computing it against a default one nobody
    was asked about makes it not the person's position."""

    def test_the_profile_records_a_stated_ancestry(self):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        try:
            core.reset_cache()
            self.assertIsNone(core.profile_ancestry())
            store.update_metric_profile({"ancestry": "EAS"})
            core.reset_cache()
            self.assertEqual(core.profile_ancestry(), "EAS")
        finally:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
            core.reset_cache()

    def test_an_unstated_population_is_declared_in_the_report(self):
        out = fmt.prs_report({"available": True, "stats": {
            "superpopulation": "EUR", "ancestry_stated": False,
            "reliable": 0, "total": 0}, "by_category": {}})
        self.assertRegex(out, r"(?i)(default|дефолт)")

    def test_a_stated_population_carries_no_caveat(self):
        out = fmt.prs_report({"available": True, "stats": {
            "superpopulation": "EAS", "ancestry_stated": True,
            "reliable": 0, "total": 0}, "by_category": {}})
        self.assertNotRegex(out, r"(?i)(nobody asked|вас не спрашивали)")
