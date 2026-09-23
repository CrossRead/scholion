"""A drug answer is never reassuring because something was not read.

Four shapes of one defect, found by the 0.5.7 review:

* an unread second gene of a two-gene drug (NUDT15 beside TPMT for azathioprine)
  counted as severity zero and vanished from the answer;
* a called phenotype the engine had no code for (a caller's «Indeterminate»,
  SLCO1B1's «Poor Function») became «reported» and was answered out of the
  catalogue default, «nothing notable in the markers»;
* a drug name was matched by plain containment, so «nystatin» got the statin
  guideline and «heparin» the omega-3 dose evidence;
* a non-normal phenotype of a gene with no table for this drug was answered «low».
"""
from __future__ import annotations

import json
import pathlib
import tempfile
import unittest

import support
from scholion import core
from scholion.engine import pgx


class _Profile(unittest.TestCase):

    def with_pgx(self, profile):
        d = tempfile.mkdtemp()
        self._unpin = support.pin_profile(d)
        self.addCleanup(self._cleanup)
        (pathlib.Path(d) / "pharmacogenomics.json").write_text(json.dumps(profile),
                                                              encoding="utf-8")
        core.reset_cache()

    def _cleanup(self):
        self._unpin()
        core.reset_cache()


class TestAnUnreadCoGeneIsNamed(_Profile):

    def test_normal_tpmt_with_unread_nudt15_is_not_low(self):
        self.with_pgx({"star_alleles": {
            "TPMT": {"diplotype": "*1/*1", "phenotype": "Normal Metabolizer",
                     "source": "pypgx"}}, "genotypes": []})
        r = pgx.check_drug_gene("azathioprine")
        self.assertEqual("NM", r["phenotype"])
        self.assertIn("NUDT15", r["unresolved_genes"])
        self.assertNotEqual("low", r["level"], r["recommendation"])
        self.assertIn("NUDT15", r["recommendation"])


class TestACalledPhraseWithoutACodeIsNotNormal(_Profile):

    def test_indeterminate_is_unknown(self):
        self.with_pgx({"star_alleles": {"CYP2C19": {
            "diplotype": "*1/*?", "phenotype": "Indeterminate", "source": "pypgx"}},
            "genotypes": []})
        r = pgx.compute_phenotype("CYP2C19")
        self.assertEqual("unknown", r["phenotype"])
        self.assertNotEqual("low", pgx.check_drug_gene("clopidogrel")["level"])

    def test_slco1b1_function_words_reach_the_statin_table(self):
        self.with_pgx({"star_alleles": {"SLCO1B1": {
            "diplotype": "*5/*5", "phenotype": "Poor Function", "source": "pypgx"}},
            "genotypes": []})
        self.assertEqual("low_function", pgx.compute_phenotype("SLCO1B1")["phenotype"])

    def test_a_phrase_nobody_maps_is_not_answered_from_default(self):
        self.with_pgx({"star_alleles": {"SLCO1B1": {
            "diplotype": "*1/*99", "phenotype": "Increased Function", "source": "lab"}},
            "genotypes": []})
        r = pgx.check_drug_gene("simvastatin")
        self.assertEqual("reported", r["phenotype"])
        self.assertNotEqual("low", r["level"])
        self.assertIn("SLCO1B1", r["unresolved_genes"])


class TestADrugNameIsAWholeWord(unittest.TestCase):

    def test_containment_inside_another_word_does_not_match(self):
        for query, name in (("nystatin", "statin"), ("нистатин", "статин"),
                            ("антигриппин", "ипп"), ("heparin", "epa"),
                            ("эзомепразол", "омепразол"), ("и", "ипп")):
            with self.subTest(query=query):
                self.assertFalse(pgx.name_matches(query, name))

    def test_a_dose_a_brand_or_a_case_ending_still_matches(self):
        for query, name in (("аторвастатин 20 мг", "аторвастатин"),
                            ("clopidogrel bisulfate", "clopidogrel"),
                            ("цинка пиколинат", "цинк"), ("статины", "статин"),
                            ("omega-3", "omega")):
            with self.subTest(query=query):
                self.assertTrue(pgx.name_matches(query, name))

    def test_nystatin_gets_no_statin_guideline(self):
        r = pgx.check_drug_gene("nystatin")
        self.assertNotEqual("SLCO1B1", r.get("gene"))


class TestTheEdgesOfTheAnswer(_Profile):

    def test_an_empty_name_matches_nothing(self):
        self.assertFalse(pgx.name_matches("", "statin"))
        self.assertIsNone(pgx._copies_at_locus({"genotype": ""}, "T"))

    def test_a_genotype_of_another_allele_leaves_the_marker_unread(self):
        from unittest import mock
        self.with_pgx({"genotypes": []})
        st = {"genotype": "AG", "ref": "A", "confidence": "called", "source": "vcf"}
        with mock.patch.object(core, "genotype_status", lambda rs: st if rs == "rs4244285" else None):
            r = pgx.compute_phenotype("CYP2C19")
        self.assertIn("rs4244285", r["basis"].get("not_called", []))

    def test_an_online_drug_with_a_non_normal_phenotype_is_not_low(self):
        from unittest import mock
        from scholion import drugsource
        info = {"name": "pantoprazole", "internal_class": "ppi", "atc": [], "rxcui": None}
        with mock.patch.object(drugsource, "resolve_drug", return_value=info), \
                mock.patch.object(drugsource, "class_gene", return_value=("CYP2C19", "why")), \
                mock.patch.object(pgx, "compute_phenotype",
                                  return_value={"phenotype": "PM", "label": "poor", "found": []}), \
                mock.patch.object(pgx, "_guidance_for", return_value={}):
            r = pgx._check_drug_online("pantoprazole-x")
        self.assertEqual("unknown", r["level"])

    def test_the_prescription_verdict_hears_every_gene(self):
        from unittest import mock
        self.with_pgx({"star_alleles": {"TPMT": {"diplotype": "*1/*1",
                                                 "phenotype": "Normal Metabolizer",
                                                 "source": "pypgx"}}, "genotypes": []})
        genes = {"genes": [
            {"gene": "TPMT", "actionable": True, "computable": True, "phenotype": "NM"},
            {"gene": "NUDT15", "actionable": True, "computable": True, "phenotype": "unknown"},
            {"gene": "CYP2C9", "actionable": True, "computable": True, "phenotype": "PM"},
            {"gene": "HLA-B", "actionable": True, "computable": False, "phenotype": "pending"},
            {"gene": "ABCB1", "actionable": False, "computable": False, "phenotype": "pending"}],
            "genome_ready": False, "has_pgx": True, "cpic": {"asked": True}}
        with mock.patch.object(pgx, "_genome_for_drug", return_value=genes):
            r = pgx.check_new_prescription("azathioprine")
        named = {u.get("gene") for u in r["unresolved"]}
        self.assertTrue({"NUDT15", "CYP2C9", "HLA-B"} <= named, named)
        self.assertNotIn("ABCB1", named)
        self.assertNotEqual("low", r["overall"])

    def test_the_second_gene_is_in_the_genome_section(self):
        self.with_pgx({"genotypes": []})
        genes = {g["gene"] for g in pgx._genome_for_drug("azathioprine", None)["genes"]}
        self.assertIn("NUDT15", genes)


class TestARegionOnAMissingContig(unittest.TestCase):

    def test_it_is_refused_with_the_reason(self):
        from unittest import mock
        from scholion import gene_region, genes, genome
        loc = {"gene": "TESTGENE", "chrom": "Y", "start": 10, "end": 90, "cds": []}

        def missing(*a, **k):
            raise genome.ContigNotInFile("Y")
        with mock.patch.object(genes, "resolve", lambda g, allow_network=True: loc), \
                mock.patch.object(genome, "available", lambda: {"ready": True}), \
                mock.patch.object(genome, "vcf_path", lambda: pathlib.Path("/nonexistent.vcf.gz")), \
                mock.patch.object(genome, "_query_region_range", missing):
            r = gene_region.report("TESTGENE", allow_network=False)
        self.assertEqual("contig_not_in_file", r["status"])


if __name__ == "__main__":
    unittest.main()
