"""Independently checked aggregate calibrations, tied to exact scoring models.

These references establish a score's population scale, never clinical accuracy
or absolute disease probability. No weights, genotypes or network are used here.
"""
from __future__ import annotations

import math

from .pgs_validation import number, scoring_verified


def calibration_for(row: dict, population: str) -> dict | None:
    """Use a curated reference only for a verified score of the identical model.

    An upstream quarantine is not overridden generically. A separately checked
    reference must cover this model, effective coordinate build and population.
    """
    from .core import _read_knowledge
    if not scoring_verified(row) or row.get("build_mismatch"):
        return None
    build = row.get("genome_build")
    if build not in ("GRCh37", "GRCh38") or any(
            row.get(key) != build for key in ("detected_genome_build", "model_harmonized_build")):
        return None
    score = number(row.get("score"))
    if score is None:
        return None
    witness = row["scoring_validation"]
    if witness.get("genome_build") != build:
        return None
    for ref in _read_knowledge("prs_references.json").get("references", []):
        if ref.get("pgs_id") != row.get("pgs_id") or ref.get("population") != population:
            continue
        model_hash = (ref.get("model_sha256_by_build") or {}).get(build)
        mean, sd = number(ref.get("mean")), number(ref.get("std"))
        n, variants = number(ref.get("samples")), number(ref.get("model_variants"))
        if (not model_hash or witness.get("model_sha256") != model_hash
                or row.get("model_original_build") != ref.get("reference_coordinate_build")
                or mean is None or sd is None or sd <= 0 or n is None or n < 100
                or variants is None or variants <= 0
                or ref.get("minimum_called_positions") != variants
                or witness.get("variants_total") != variants
                or ref.get("estimation") != "normal_mean_sd"
                or not ref.get("source") or not ref.get("validation")
                or any(not isinstance(ref.get(key), str) or len(ref[key]) != 64 for key in
                       ("reference_sample_list_sha256", "reference_called_sites_sha256"))):
            continue
        z = (score - mean) / sd
        return {"method": "reference_panel", "percentile": 50 * math.erfc(-z / math.sqrt(2)),
                "z_score": z, "reference_mean": mean, "reference_std": sd,
                "reference_panel": ref["panel"], "reference_panel_ancestry": population,
                "reliable": True, "validation": {
                    "checked": True, "quality": "passed", "source": ref["source"],
                    "kind": "independent_called_reference", "samples": int(n),
                    "variants": int(variants), "model_sha256": model_hash,
                    "reference_coordinate_build": ref["reference_coordinate_build"],
                    "estimation": ref["estimation"], "updated": ref.get("updated"),
                    "sample_list_sha256": ref["reference_sample_list_sha256"],
                    "called_sites_sha256": ref["reference_called_sites_sha256"],
                    "publication": ref.get("source_publication")}}
    return None
