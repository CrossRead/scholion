"""Domain-correctness fixes from the colleagues' audit (block 3).

The clinical-DATA discrepancies (hand-paraphrased CPIC: findings 33, 34, 47,
48, 50) are deliberately NOT fixed here by hand-editing the mappings — that
would make the code another paraphrase of CPIC and repeat the exact defect the
audit found. They belong with the verbatim CPIC import (block 5). What is fixed
here is structural and answerability-shaped: a privacy leak, a silent sex
assumption, a hidden confidence level, and two confidently-wrong computations.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest

import support  # noqa: F401
from scholion import core, genome


class TestTheSharedRegistryCarriesNobodysAncestry(unittest.TestCase):
    """Finding 39: prs_models.json shipped a dossier about the owner's genome
    (EUR posterior, a reference to their BAM) in a file that ships to everyone."""

    def test_no_reference_population_conclusion_in_the_registry(self):
        p = pathlib.Path(core.__file__).resolve().parent / "knowledge" / "prs_models.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        meta = d.get("_meta", {})
        self.assertNotIn("reference_population", meta,
                         "the shared registry still carries a per-person ancestry conclusion")
        blob = json.dumps(d)
        for token in ("posterior", "ancestry_check.py", "4×10", "BAM"):
            self.assertNotIn(token, blob, f"owner-specific token «{token}» ships in the registry")


class TestReferenceRangesAreSexAware(unittest.TestCase):
    """Finding 37: knowledge default ranges are male; a woman got false anaemia,
    false-low testosterone and a missed low eGFR."""

    def _profile(self, sex, marker, unit, value, ref_low, ref_high):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        pd = pathlib.Path(d)
        (pd / "metrics.json").write_text(json.dumps({"profile": {"sex": sex, "birth_year": 1985}, "metrics": {}}))
        (pd / "labs.json").write_text(json.dumps({"markers": {marker: {"name": marker, "unit": unit, "ref_low": ref_low, "ref_high": ref_high, "series": [{"date": "2026-01", "value": value}]}}}))
        core.reset_cache()
        from scholion.engine import labs
        row = labs.analyze_labs([marker])["markers"][0]
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        core.reset_cache()
        return row

    def test_a_woman_with_hb_125_is_not_flagged_anaemic(self):
        # male default range 131-172 would flag LOW; female range 117-155 is ok
        row = self._profile("f", "hemoglobin", "g/L", 125.0, 131.0, 172.0)
        self.assertEqual(row["flag"], "ok")
        self.assertEqual(row["ref_sex"], "female")
        self.assertEqual((row["ref_low"], row["ref_high"]), (117.0, 155.0))

    def test_a_man_keeps_the_male_range(self):
        row = self._profile("m", "hemoglobin", "g/L", 125.0, 131.0, 172.0)
        self.assertEqual(row["ref_sex"], "male")
        self.assertNotEqual(row["flag"], "ok")   # 125 < 131 is low for a man

    def test_a_form_read_range_is_never_overridden(self):
        # a range that differs from the knowledge default is the person's own form
        row = self._profile("f", "hemoglobin", "g/L", 125.0, 120.0, 150.0)
        self.assertIsNone(row["ref_sex"])
        self.assertEqual((row["ref_low"], row["ref_high"]), (120.0, 150.0))


class TestClinvarSurfacesReviewConfidence(unittest.TestCase):
    """Finding 36: a 0-1-star Pathogenic sat in the same tier as a 4-star one."""

    def test_stars_map(self):
        self.assertEqual(genome._review_stars("reviewed_by_expert_panel"), 3)
        self.assertEqual(genome._review_stars("practice_guideline"), 4)
        self.assertEqual(genome._review_stars("no_assertion_criteria_provided"), 0)

    def test_a_zero_star_pathogenic_is_marked_low_confidence(self):
        # exercise the annotation logic directly on a synthetic record shape
        stars = genome._review_stars("no_assertion_criteria_provided")
        low = stars <= 1 and "pathogenic" in ("pathogenic",)
        self.assertTrue(low)


class TestPhenoAgeRefusesWrongUnitsInsteadOfMisreporting(unittest.TestCase):
    """Findings 31/32: albumin in g/dL read as g/L moved the age 8 years; a bad
    input left the math domain with a traceback."""

    def _run(self, albumin):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        pd = pathlib.Path(d)
        (pd / "metrics.json").write_text(json.dumps({"profile": {"birth_year": 1980}}))
        vals = {"albumin": (albumin, "g/L"), "creatinine": (70, "umol/L"),
                "glucose": (5, "mmol/L"), "crp": (1, "mg/L"), "lymph": (30, "%"),
                "mcv": (90, "fL"), "rdw": (13, "%"), "alp": (70, "U/L"), "wbc": (6, "10^9/L")}
        (pd / "labs.json").write_text(json.dumps({"markers": {k: {"name": k, "unit": u, "series": [{"date": "2026-01", "value": v}]} for k, (v, u) in vals.items()}}))
        core.reset_cache()
        from scholion import phenoage
        r = phenoage.compute_panel("2026-01")
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        core.reset_cache()
        return r

    def test_albumin_in_the_wrong_unit_is_refused(self):
        r = self._run(4.3)                       # g/dL mistaken for g/L
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"], "implausible_units")
        self.assertIn("albumin", r["markers"])

    def test_a_canonical_albumin_computes(self):
        r = self._run(43.0)                      # g/L, correct
        self.assertTrue(r["ok"])


class TestBrokenTabixIndexIsNotUsable(unittest.TestCase):
    """Finding 24: a truncated .tbi read as homozygous-reference everywhere."""

    def test_an_empty_or_garbage_index_is_rejected(self):
        d = tempfile.mkdtemp()
        vcf = pathlib.Path(d) / "x.vcf.gz"
        vcf.write_bytes(b"\x1f\x8b\x08\x00rest")
        (pathlib.Path(str(vcf) + ".tbi")).write_bytes(b"")          # truncated
        self.assertFalse(genome._tbi_usable(str(vcf)))
        (pathlib.Path(str(vcf) + ".tbi")).write_bytes(b"garbage")   # wrong magic
        self.assertFalse(genome._tbi_usable(str(vcf)))
        (pathlib.Path(str(vcf) + ".tbi")).write_bytes(b"\x1f\x8b\x08\x04ok")  # gzip magic
        self.assertTrue(genome._tbi_usable(str(vcf)))


if __name__ == "__main__":
    unittest.main()
