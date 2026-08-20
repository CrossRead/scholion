"""The activity-score phenotype model, from CPIC verbatim (findings 33, 34, 47).

The count-by-function rules this replaces read CYP2C9 *2/*3 as intermediate;
CPIC's activity score (0.5 + 0.0 = 0.5) calls it a POOR metaboliser, which for
warfarin and phenytoin is the difference that matters. The activity values are
derived from the function label the markers carry (no-function 0.0, decreased
0.5, normal 1.0 — verbatim from api.cpicpgx.org/v1/allele) and the
score->phenotype bands are carried per gene (verbatim from /v1/diplotype,
fetched 2026-08-19).
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest

import support  # noqa: F401
from scholion import core
from scholion.engine import pgx


def _phenotype(gene, genos):
    d = tempfile.mkdtemp()
    os.environ["SCHOLION_PROFILE_DIR"] = d
    (pathlib.Path(d) / "pharmacogenomics.json").write_text(json.dumps({"genotypes": genos}))
    core.reset_cache()
    r = pgx.compute_phenotype(gene)
    os.environ.pop("SCHOLION_PROFILE_DIR", None)
    core.reset_cache()
    return r


class TestCyp2c9ActivityScore(unittest.TestCase):
    def test_star2_star3_is_a_poor_metaboliser_not_intermediate(self):
        r = _phenotype("CYP2C9", [
            {"rsid": "rs1799853", "genotype": "CT", "confidence": "called"},   # *2 het
            {"rsid": "rs1057910", "genotype": "AC", "confidence": "called"}])  # *3 het
        self.assertEqual(r["phenotype"], "PM")
        self.assertEqual(r["activity_score"], 0.5)

    def test_star2_heterozygote_is_intermediate(self):
        r = _phenotype("CYP2C9", [
            {"rsid": "rs1799853", "genotype": "CT", "confidence": "called"},
            {"rsid": "rs1057910", "genotype": "AA", "confidence": "called"}])
        self.assertEqual(r["phenotype"], "IM")
        self.assertEqual(r["activity_score"], 1.5)

    def test_reference_is_normal(self):
        r = _phenotype("CYP2C9", [
            {"rsid": "rs1799853", "genotype": "CC", "confidence": "called"},
            {"rsid": "rs1057910", "genotype": "AA", "confidence": "called"}])
        self.assertEqual(r["phenotype"], "NM")
        self.assertEqual(r["activity_score"], 2.0)


class TestDpydActivityScore(unittest.TestCase):
    def test_star2a_heterozygote_is_intermediate_not_total_deficiency(self):
        r = _phenotype("DPYD", [{"rsid": "rs3918290", "genotype": "CT", "confidence": "called"}])
        self.assertEqual(r["phenotype"], "IM")
        self.assertEqual(r["activity_score"], 1.0)

    def test_hapb3_heterozygote_is_intermediate(self):
        # HapB3 is one allele tagged by two rsids that travel together
        r = _phenotype("DPYD", [
            {"rsid": "rs75017182", "genotype": "GC", "confidence": "called"},
            {"rsid": "rs56038477", "genotype": "CT", "confidence": "called"}])
        self.assertEqual(r["phenotype"], "IM")
        self.assertEqual(r["activity_score"], 1.5)

    def test_star2a_homozygote_is_poor(self):
        r = _phenotype("DPYD", [{"rsid": "rs3918290", "genotype": "TT", "confidence": "called"}])
        self.assertEqual(r["phenotype"], "PM")
        self.assertEqual(r["activity_score"], 0.0)


class TestMthfrIsNotACpicDrugPair(unittest.TestCase):
    """Finding 47: MTHFR/methotrexate is not a CPIC guideline; ACMG advises
    against testing MTHFR C677T/A1298C. It must not be presented as a
    pharmacogenetic dosing pair."""

    def test_methotrexate_no_longer_resolves_to_an_mthfr_recommendation(self):
        kb = core.cpic_kb()
        mthfr_drugs = [e for e in kb.get("drugs", []) if e.get("gene") == "MTHFR"]
        self.assertEqual(mthfr_drugs, [], "MTHFR is still paired to a drug")

    def test_mthfr_gene_is_kept_but_flagged_non_pharmacogenetic(self):
        kb = core.cpic_kb()
        self.assertIn("MTHFR", kb.get("genes", {}))
        self.assertIn("not_a_cpic_drug_pair", kb["genes"]["MTHFR"])
        self.assertNotIn("MTHFR", kb.get("genes_of_interest", []))


class TestTheActivityGenesAreLabelledVerbatim(unittest.TestCase):
    def test_cyp2c9_and_dpyd_declare_the_activity_model_with_bands(self):
        kb = core.cpic_kb()
        for g in ("CYP2C9", "DPYD"):
            gdef = kb["genes"][g]
            self.assertEqual(gdef.get("model"), "activity_score")
            bands = gdef.get("activity_bands")
            self.assertTrue(bands and len(bands) == 3)
            self.assertIn("activity_source", gdef)


if __name__ == "__main__":
    unittest.main()


class TestThiopurinesConsiderNudt15(unittest.TestCase):
    """Finding 48: CPIC dosing for thiopurines follows TPMT AND NUDT15. A person
    normal on TPMT but a NUDT15 intermediate metaboliser was missed entirely."""

    def _aza(self, genos):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        (pathlib.Path(d) / "pharmacogenomics.json").write_text(json.dumps({"genotypes": genos}))
        core.reset_cache()
        r = pgx.check_drug_gene("azathioprine")
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        core.reset_cache()
        return r

    def test_nudt15_intermediate_raises_the_caution_even_when_tpmt_is_normal(self):
        r = self._aza([
            {"rsid": "rs1800462", "genotype": "CC", "confidence": "called"},   # TPMT *2 ref
            {"rsid": "rs1142345", "genotype": "TT", "confidence": "called"},   # TPMT *3C ref
            {"rsid": "rs116855232", "genotype": "CT", "confidence": "called"}])  # NUDT15 *3 het
        self.assertNotEqual(r["level"], "low")
        self.assertEqual(r["driving_gene"], "NUDT15")
        self.assertIn(("NUDT15", "IM"), [(c["gene"], c["phenotype"]) for c in r["co_genes"]])

    def test_both_normal_is_low(self):
        r = self._aza([
            {"rsid": "rs1800462", "genotype": "CC", "confidence": "called"},
            {"rsid": "rs1142345", "genotype": "TT", "confidence": "called"},
            {"rsid": "rs116855232", "genotype": "CC", "confidence": "called"}])
        self.assertEqual(r["level"], "low")

    def test_nudt15_is_a_gene_of_interest_with_its_tag_snp(self):
        kb = core.cpic_kb()
        self.assertIn("NUDT15", kb["genes"])
        self.assertIn("NUDT15", kb["genes_of_interest"])
        rsids = [m["rsid"] for m in kb["genes"]["NUDT15"]["markers"]]
        self.assertIn("rs116855232", rsids)


class TestCalledDiplotypesAreRead(unittest.TestCase):
    """Findings 35/51: PyPGx/PharmCAT wrote star-allele diplotypes into the
    profile and the engine never read them. A called diplotype resolved copy
    number and phase; it outranks the tag-SNP estimate."""

    def _pheno(self, gene, profile):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        (pathlib.Path(d) / "pharmacogenomics.json").write_text(json.dumps(profile))
        core.reset_cache()
        r = pgx.compute_phenotype(gene)
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        core.reset_cache()
        return r

    def test_cyp2d6_gets_a_phenotype_from_a_called_diplotype(self):
        # CYP2D6 cannot be resolved by tag SNPs at all — without reading the call
        # it had no phenotype
        r = self._pheno("CYP2D6", {"star_alleles": {
            "CYP2D6": {"diplotype": "*4/*4", "phenotype": "Poor Metabolizer", "source": "pypgx"}},
            "genotypes": []})
        self.assertEqual(r["phenotype"], "PM")
        self.assertEqual(r["certainty"], "called")
        self.assertEqual(r["diplotype"], "*4/*4")

    def test_a_call_outranks_a_conflicting_tag_snp(self):
        r = self._pheno("CYP2C9", {
            "star_alleles": {"CYP2C9": {"diplotype": "*1/*1",
                                        "phenotype": "Normal Metabolizer", "source": "pharmcat"}},
            "genotypes": [{"rsid": "rs1799853", "genotype": "CT", "confidence": "called"}]})
        self.assertEqual(r["phenotype"], "NM")
        self.assertEqual(r["certainty"], "called")


class TestVerbatimRecommendationsReachTheReport(unittest.TestCase):
    """Finding 57: CPIC's own wording, quoted and attributed, must actually reach
    the person — a verbatim base that nothing prints is a base nobody can check."""

    def _report(self, drug, genos):
        d = tempfile.mkdtemp()
        os.environ["SCHOLION_PROFILE_DIR"] = d
        (pathlib.Path(d) / "pharmacogenomics.json").write_text(json.dumps({"genotypes": genos}))
        core.reset_cache()
        from scholion import format as fmt
        r = pgx.check_drug_gene(drug)
        out = fmt.drug_check(r)
        os.environ.pop("SCHOLION_PROFILE_DIR", None)
        core.reset_cache()
        return r, out

    def test_the_quote_is_printed_and_attributed(self):
        r, out = self._report("azathioprine", [
            {"rsid": "rs1800462", "genotype": "CC", "confidence": "called"},
            {"rsid": "rs1142345", "genotype": "TT", "confidence": "called"},
            {"rsid": "rs116855232", "genotype": "CT", "confidence": "called"}])
        self.assertIn("CPIC", out)
        self.assertIn("reduced starting doses (30-80%", out)
        self.assertEqual(r["cpic"]["classification"], "Strong")

    def test_codeine_has_real_phenotype_guidance_now_that_diplotypes_are_read(self):
        """Before findings 35/57 codeine could only say «the diplotype is unknown»:
        the gene had no phenotype and the table had no phenotype keys."""
        kb = core.cpic_kb()
        cod = next(x for x in kb["drugs"] if "codeine" in x["names"])
        for key in ("UM", "PM", "IM", "NM"):
            self.assertIn(key, cod["guidance"], f"codeine still has no {key} guidance")
        self.assertIn("diminished analgesia", cod["guidance"]["PM"]["cpic"]["recommendation"])

    def test_the_quote_is_not_our_paraphrase(self):
        kb = core.cpic_kb()
        clop = next(x for x in kb["drugs"] if "clopidogrel" in x["names"])
        pm = clop["guidance"]["PM"]
        self.assertIn("prasugrel or ticagrelor", pm["cpic"]["recommendation"])
        self.assertNotEqual(pm["cpic"]["recommendation"], pm["note"])
