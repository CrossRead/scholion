"""Validate a population percentile independently of the scoring sidecar.

Coverage, calibration and model informativeness are separate facts. A sidecar
reliability flag cannot establish the scale of a raw score or its coordinates.
This module reads no genome, cache or profile and uses only the standard library.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any


def number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) else None
    return None


def reference_snapshot(row: dict) -> str:
    """Identity of the reference parameters used, not a hash of a whole dataset."""
    fields = ("pgs_id", "reference_panel", "reference_panel_ancestry",
              "reference_mean", "reference_std")
    raw = json.dumps({k: row.get(k) for k in fields}, sort_keys=True,
                     separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def percentile_label(value: Any) -> str:
    """A percentile label, never a percentage probability or rounded P100."""
    p = number(value)
    if p is None:
        return "—"
    if round(p, 2) >= 100:
        return "≥P99.99"
    if round(p, 2) <= 0:
        return "≤P0.01"
    return "P" + f"{p:.2f}".rstrip("0").rstrip(".")


def validate(row: dict, *, expected_build: str | None = None,
             expected_ancestry: str | None = None) -> dict:
    """Return a copy; withdraw unverified percentiles without erasing their history.

    Only empirical reference calibration with recorded, checked parameters is
    admitted. Theoretical and AUROC fallbacks remain diagnostic until a separate
    validated policy exists. Unknown provenance is an unknown result, not zero.
    """
    out = dict(row)
    reasons = []
    method = row.get("percentile_method")
    if method != "reference_panel":
        reasons.append("method_unknown" if not method else "method_unsupported")
    p = number(row.get("percentile"))
    score, mean, sd, z = (number(row.get(k)) for k in
                          ("score", "reference_mean", "reference_std", "z_score"))
    if p is None or not 0 <= p <= 100:
        reasons.append("percentile_missing")
    if score is None or mean is None or sd is None or sd <= 0 or z is None:
        reasons.append("reference_parameters_missing")
    elif p is not None:
        expected_z = (score - mean) / sd
        expected_p = 50 * math.erfc(-expected_z / math.sqrt(2))
        if not math.isclose(z, expected_z, rel_tol=1e-6, abs_tol=1e-6) or abs(p - expected_p) > 0.011:
            reasons.append("calibration_inconsistent")
    if not row.get("reference_panel") or not row.get("reference_panel_ancestry"):
        reasons.append("reference_identity_missing")
    if expected_ancestry and row.get("reference_panel_ancestry") != expected_ancestry:
        reasons.append("reference_population_mismatch")
    witness = row.get("reference_validation") or {}
    if not isinstance(witness, dict) or witness.get("checked") is not True:
        reasons.append("reference_not_checked")
    else:
        try:
            matches = witness.get("snapshot_sha256") == reference_snapshot(row)
        except (TypeError, ValueError):
            matches = False
        if not matches or witness.get("quality") != "passed" or not witness.get("source"):
            reasons.append("reference_not_checked")

    selected = row.get("genome_build")
    detected = row.get("detected_genome_build")
    harmonized = row.get("model_harmonized_build")
    builds = {v if isinstance(v, str) else None for v in (selected, detected, harmonized)}
    if expected_build:
        builds.add(expected_build)
    build_reasons = []
    if None in builds or not builds <= {"GRCh37", "GRCh38"}:
        build_reasons.append("build_unknown")
    if row.get("build_mismatch") is True or len(builds - {None}) > 1:
        build_reasons.append("build_mismatch")
    reasons += build_reasons

    mr, wm = number(row.get("match_rate")), number(row.get("weight_mass_coverage"))
    reading = {"match_rate": mr, "weight_mass_coverage": wm,
               "sufficient": mr is not None and wm is not None
               and 0.9 <= mr <= 1.0001 and 0.9 <= wm <= 1.0001}
    out["reading"] = reading
    out["build_validation"] = {"valid": not build_reasons, "reasons": build_reasons}
    out["calibration"] = {"valid": not reasons, "method": method, "reasons": reasons}
    upstream = row.get("percentile_reliable") is True
    manually_withdrawn = row.get("reliable") is False
    out["reliable"] = not reasons and reading["sufficient"] and upstream and not manually_withdrawn
    if reasons:
        if row.get("percentile") is not None:
            out.setdefault("diagnostic_percentile", row["percentile"])
        if row.get("validity_note"):
            out.setdefault("diagnostic_validity_note", row["validity_note"])
            out.pop("validity_note", None)
        out["percentile"] = None
        out["percentile_reliable"] = False
        models = dict(out["models"]) if isinstance(out.get("models"), dict) else {}
        if models:
            models.setdefault("diagnostic_percentiles", models.get("percentiles"))
            models["percentiles"] = []
            models["spread_pp"] = None
            out["models"] = models
    return out
