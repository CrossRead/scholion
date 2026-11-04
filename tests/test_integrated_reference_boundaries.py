"""The assembled candidate retains source scope, draw identity and region evidence."""
from __future__ import annotations

import copy
from datetime import date
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, gene_region, genome, panel_reference, phenoage, scientific_review
from scholion.engine import labs, thematic_panels


class TestIntegratedReferenceBoundaries(unittest.TestCase):
    def test_source_citations_survive_without_links_and_malformed_links_are_not_published(self):
        rows = scientific_review._review_sources([
            "https://www.ncbi.nlm.nih.gov/refseq/MANE/", "Synthetic printed reference",
            "https://[broken", None], "2026-01-01", date(2026, 11, 4))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "MANE")
        self.assertEqual(rows[1]["citation"], "Synthetic printed reference")
        self.assertTrue(all(r["refresh_status"] == "due" for r in rows))

    def test_reference_export_keeps_scope_and_source_derived_notice(self):
        row = {"gene": "SYNTHETIC", "reference_context": {
            "gene_function": "Synthetic function", "variant_context": "Reference association",
            "allele_note": "Only the selected allele is described",
            "disease_context": {"label": "Reference", "name": "Synthetic condition",
                                "limitations": "Not an individual diagnosis", "source": "https://example.org/disease"},
            "reading_limit": "Exact reference only", "reference_identity": {
                "builds": {"GRCh38": {"accession": "NC_000001.11", "position_zero_based": 99,
                                      "reference": "A", "alternatives": ["G"]}},
                "source": "https://example.org/allele"},
            "scientific_review": [{"label": "Gene-level reference", "summary": "Known function",
                                   "curation_notice": "Source-derived description"}]}}
        text = "\n".join(panel_reference.reference_lines(row))
        for expected in ("Not an individual diagnosis", "Source-derived description", "Exact reference only",
                         "https://example.org/allele", "NC_000001.11", "Only the selected allele is described"):
            self.assertIn(expected, text)
        self.assertEqual(panel_reference._catalogue_reference_lines({}), [])

    def test_exact_phenotype_source_fills_a_missing_function_but_not_a_neighbouring_allele(self):
        phenotype = {"ref": "A", "alt": "G", "gene": "SYNTHETIC", "phenotype": "Synthetic trait",
                     "description": "Exact allele association", "source": "https://example.org/record",
                     "study": "https://example.org/study", "gene_function": "Synthetic sourced function"}
        rows = [{"rsid": "rs123", "ref": "A", "alt": "G", "genotype": "AG"},
                {"rsid": "rs123", "ref": "A", "alt": "T", "genotype": "AT"}]
        def context(gene, rsid):
            return {"gene": gene, "reference_context": {"function_status": "not_curated"}}
        with mock.patch.object(core, "loci", return_value={"loci": {}}), \
             mock.patch.object(core, "_read_knowledge", return_value={"clinvar_phenotypes": {"rs123": phenotype}}), \
             mock.patch.object(panel_reference, "genome_context", side_effect=context), \
             mock.patch.object(panel_reference, "_scientific_context", side_effect=lambda gene, rsid, value: value):
            panel_reference.attach_finding_biology(rows, "GRCh38")
        reference = rows[0]["gene_contexts"][0]["reference_context"]
        self.assertEqual(reference["gene_function"], phenotype["gene_function"])
        self.assertEqual(reference["gene_source"], phenotype["study"])
        self.assertEqual(reference["variant_context"], phenotype["description"])
        self.assertEqual(rows[1]["gene_contexts"], [])
        self.assertNotIn("clinvar_phenotype", rows[1])
        self.assertFalse(panel_reference._matches_catalogue_allele(
            {"chrom": "2", "pos": 100, "ref": "A", "alt": "G"},
            {"chrom": "1", "pos38": 100, "ref": "A", "alt": "G"}, "GRCh38"))

    def test_invalid_or_inferred_draw_points_cannot_complete_an_age_panel(self):
        key = phenoage.LABS_KEYS["albumin"][0]
        points = [{"date": "2026-10-01", "value": value} for value in (True, None, "bad", float("nan"))]
        points += [{"date": "2026-10-99", "value": 40},
                   {"date": "2026-10-01", "value": 41, "date_source": "filename"},
                   {"date": "2026-10-01", "value": 42, "date_source": "ordered"},
                   {"date": "2026-10-01", "value": 43, "censored": "<"},
                   {"date": "2026-09-01", "value": 44},
                   {"date": "2026-10-02T08:00:00", "value": 45},
                   {"date": "2026-10-02T17:00:00", "value": 46}]
        with mock.patch.object(core, "labs", return_value={"markers": {key: {"series": points}}}):
            draws = phenoage._draws("2026-10")
            self.assertEqual(set(draws), {"2026-10-02T08:00:00", "2026-10-02T17:00:00"})
            self.assertEqual(draws["2026-10-02T08:00:00"]["albumin"][1], 45)
            self.assertEqual(phenoage._selected_draw("2026-09-30"), "2026-09-30")
        with mock.patch.object(core, "metrics_json", return_value={"profile": {"birth_date": "invalid"}}):
            self.assertIsNone(phenoage.age_at("2026-10-02"))
        with mock.patch.object(core, "metrics_json", return_value={"profile": {"birth_year": 1980}}):
            self.assertAlmostEqual(phenoage.age_at("2026-10-02"), (date(2026, 10, 2)-date(1980, 7, 1)).days/365.2425)

    def test_whole_genome_empty_region_receives_verification_not_an_inferred_reference(self):
        book = {"positions": [], "genes": [{"gene": "SYNTHETIC", "positions": [],
                 "reference_context": {}, "reading_request": {"gene": "SYNTHETIC"}}], "regions": [], "counts": {}}
        verified = {"status": "ok", "quality": {"state": "partial_coverage"}}
        with mock.patch.object(thematic_panels, "thematic_reference", side_effect=lambda _: copy.deepcopy(book)), \
             mock.patch.object(genome, "available", return_value={"ready": True, "input_profile": "whole_genome"}), \
             mock.patch.object(core, "profile_genotypes", return_value={}), \
             mock.patch.object(gene_region, "bam_path", return_value=None), \
             mock.patch.object(gene_region, "preview", return_value={"status": "ok", "variants": []}) as preview, \
             mock.patch.object(gene_region, "verify_empty_preview", return_value=verified) as verify, \
             mock.patch.object(labs, "analyze_labs", return_value={"markers": []}):
            result = thematic_panels.thematic_readings("synthetic", "patient")
        preview.assert_called_once_with("SYNTHETIC")
        verify.assert_called_once()
        self.assertEqual(result["genes"][0]["region_reading"], verified)
        self.assertNotIn("genotype", result["genes"][0])
