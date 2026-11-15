"""Reference annotations remain available without inventing a genotype effect."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import variant_annotations as annotations


def source_entry(shared=False):
    return {"primaryAccession": "P00001", "uniProtKBCrossReferences": [
        {"database": "HGNC", "id": "HGNC:1"},
        *([{"database": "HGNC", "id": "HGNC:2"}] if shared else [])]}


def source_feature():
    return {"type": "Natural variant", "featureId": "VAR_TEST",
            "location": {"start": {"value": 2, "modifier": "EXACT"},
                         "end": {"value": 2, "modifier": "EXACT"}},
            "alternativeSequence": {"originalSequence": "A", "alternativeSequences": ["G"]},
            "description": "Loss of activity; increased degradation.",
            "featureCrossReferences": [{"database": "dbSNP", "id": "rs100"}],
            "evidences": [{"source": "PubMed", "id": "100", "evidenceCode": "ECO:0000269"}]}


class SourceAnnotationBoundary(unittest.TestCase):
    def test_mixed_source_effect_is_not_reduced_to_an_arrow_or_dosage(self):
        record = annotations.uniprot_record(source_entry(), source_feature(), "2026_04", "2026-11-14", {"HGNC:1"})
        self.assertEqual(record["description"], "Loss of activity; increased degradation.")
        self.assertNotIn("direction", record)
        self.assertFalse(record["human_genotype_dose_model"])
        self.assertEqual(record["genomic_mapping"], "not_verified")
        self.assertEqual(record["protein_changes"], ["p.Ala2Gly"])

    def test_shared_protein_does_not_become_a_gene_specific_effect(self):
        record = annotations.uniprot_record(source_entry(True), source_feature(), "2026_04", "2026-11-14", {"HGNC:1"})
        self.assertEqual(record["gene_mapping"], "shared_protein")
        self.assertEqual(record["protein_gene_ids"], ["HGNC:1", "HGNC:2"])

    def test_experimental_replacement_keeps_its_type(self):
        feature = {**source_feature(), "type": "Mutagenesis"}
        record = annotations.uniprot_record(source_entry(), feature, "2026_04", "2026-11-14", {"HGNC:1"})
        self.assertEqual(record["type"], "Mutagenesis")

    def test_uncertain_source_position_does_not_get_hgvs(self):
        feature = source_feature()
        feature["location"]["start"]["modifier"] = "UNKNOWN"
        self.assertEqual(annotations.protein_changes(feature), [])

    def test_unnamed_experiments_at_same_position_retain_distinct_conditions(self):
        feature = {**source_feature(), "featureId": None, "type": "Mutagenesis"}
        first = annotations.uniprot_record(source_entry(), feature, "2026_04", "2026-11-14", {"HGNC:1"})
        second = annotations.uniprot_record(source_entry(), {**feature, "description": "Activity retained in another assay."}, "2026_04", "2026-11-14", {"HGNC:1"})
        self.assertNotEqual(first["id"], second["id"])


class ReferenceRetrieval(unittest.TestCase):
    def test_encoded_catalogue_retains_full_source_and_all_pages(self):
        record = annotations.uniprot_record(source_entry(), source_feature(), "2026_04", "2026-11-14", {"HGNC:1"})
        second = {**record, "id": "P00001:VAR_SECOND", "feature_id": "VAR_SECOND"}
        data = {"_meta": {"updated": "2026-11-14", "release": "2026_04"},
                "genes": {"HGNC:1": {"symbol": "SYNTH", "aliases": ["SYNTH_OLD"]}},
                "proteins": {"P00001": {"entry_version": 3}},
                "record_fields": annotations.RECORD_FIELDS,
                "records": [[row.get(field) for field in annotations.RECORD_FIELDS] for row in [record, second]]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "reference.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with patch.object(annotations.core, "knowledge_path", return_value=path):
                result = annotations.reference("SYNTH_OLD", limit=1)
                self.assertEqual(result["gene_id"], "HGNC:1")
                self.assertEqual(result["total"], 2)
                self.assertEqual(result["next_offset"], 1)
                self.assertEqual(result["records"][0]["description"], record["description"])
                self.assertFalse(result["clinical_eligibility_upgrade"])
                self.assertEqual(annotations.reference("SYNTH", "rs100")["total"], 2)
                self.assertEqual(annotations.reference("SYNTH", kind="experimental")["total"], 0)
                self.assertEqual(annotations.reference("UNKNOWN")["status"], "gene_not_in_reference_catalogue")


class CompleteRetainedModelAccess(unittest.TestCase):
    def test_every_retained_model_remains_reachable_without_inventing_gene_assignment(self):
        data = annotations.catalogue()
        available = set()
        for model in data.get('models') or []:
            result = annotations.reference(model.get('gene') or 'UNASSIGNED', (model.get('variant_ids') or [''])[0], limit=1)
            available.update(row['id'] for row in result['models'])
        self.assertEqual({model['model_id'] for model in data['models']} - available, set())
        unresolved = annotations.reference('UNASSIGNED', 'rs210332')
        self.assertEqual(unresolved['status'], 'gene_identity_unresolved')
        self.assertTrue(unresolved['models'])
        self.assertTrue(all(row['gene_assignment_unresolved'] for row in unresolved['models']))
        queried = annotations.reference('BRCA1', 'rs210332')
        self.assertTrue(queried['models'])
        self.assertTrue(all(not row['related_locus'] for row in queried['models']))
        self.assertFalse(queried['clinical_eligibility_upgrade'])


class IndependentScientificReview(unittest.TestCase):
    def test_retained_gene_identifiers_agree_with_catalogue_identity(self):
        data = annotations.catalogue()
        symbols = {row['symbol']: key for key, row in data['genes'].items()}
        for collection in ('models', 'supported_contexts'):
            for model in data[collection]:
                if model.get('gene') in symbols and model.get('hgnc_id'):
                    self.assertEqual(model['hgnc_id'], symbols[model['gene']], model)

    def test_cell_constructs_are_not_diploid_patient_genotypes(self):
        model = next(m for m in annotations.reference('HFE', 'rs1800562')['models']
                     if m['id'] == 'gm:ffb65c27d85ba968f9a1e444')
        self.assertEqual(model['kind'], 'experimental_protein_effect')
        self.assertTrue(all('/' not in g['genotype'] for g in model['genotypes']))
        self.assertTrue(all(not g['observed_genotype_effect'] for g in model['genotypes']))

    def test_missing_comparison_is_explicit_in_shared_report(self):
        data = annotations.reference('APOE')
        retained = next(m for m in data['models'] if m['kind'] == 'retained_variant_context')
        self.assertTrue(retained['knowledge_gaps'])
        for gap in retained['knowledge_gaps']:
            self.assertIn(gap, annotations.report(data))
