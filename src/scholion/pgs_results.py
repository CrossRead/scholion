"""Validated, flat PGS reports and atomic profile storage; no package writes."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, date

from . import core, store, __version__
from .pgs_validation import validate

KEEP: tuple[str, ...] = ("percentile", "quality_label", "match_rate", "weight_mass_coverage",
        "percentile_reliable", "effect_size",
        # The model's own discrimination, as the server estimates it — the one
        # informativeness figure on a common scale for a disease trait (task 132).
        "auroc_estimate")
KEEP += ("score", "percentile_method", "percentile_caveat", "reference_panel",
         "reference_panel_ancestry", "reference_mean", "reference_std", "z_score",
         "reference_validation", "genome_build", "detected_genome_build", "build_mismatch",
         "model_original_build", "model_harmonized_build", "model_format_version",
         "diagnostic_percentile", "diagnostic_validity_note", "calibration_error",
         "scoring_validation", "sidecar_diagnostic_score", "variants_total", "variants_matched",
         "weight_mass_total", "weight_mass_matched")
#: What travels from the report's per-trait `models` block into the stored row:
#: how many candidates there were, how many were scored and by what rule the
#: rest were not, and the spread of the percentile across the scored models.
#: The spread is the stability figure a bare percentile lacks (tasks 131b, 132).
MODELS_KEEP = ("validated", "candidates", "scored", "not_scored", "not_scored_rule",
               "pgs_ids", "percentiles", "spread_pp")


def _num(x):
    return x if isinstance(x, (int, float)) else None


def _chosen(t):
    ch = t.get("chosen")
    if t.get("status") == "ok_fallback":
        fb = t.get("fallback") or {}
        ch = fb.get("result") or fb.get("chosen")
    return ch or {}


def _pgs_id(row):
    for k in ("pgs_id", "id", "score_id"):
        v = row.get(k)
        if isinstance(v, str) and v.startswith("PGS"):
            return v
    return None


def build_row(t, today):
    ch = _chosen(t)
    row = {"label": t.get("label"), "category": t.get("category"), "term": t.get("term")}
    for k in KEEP:
        if k in ch:
            row[k] = ch[k]
    if isinstance(t.get("models"), dict):
        row["models"] = {k: t["models"].get(k) for k in MODELS_KEEP}
    row["pgs_id"] = _pgs_id(ch)
    p, mr = _num(row.get("percentile")), _num(row.get("match_rate"))
    problems = []
    if t.get("status") not in ("ok", "ok_fallback"):
        problems.append(f"status={t.get('status')}")
    if p is None:
        problems.append("no percentile (the model has no reference distribution)")
    if mr is not None and mr > 1.0001:
        problems.append("coverage >1 — positions double-counted in the input VCF")
    row = validate(row)
    row["reliable"] = not problems and row["reliable"]
    if problems:
        row["integrity_note"] = "; ".join(problems)
    row["source"] = f"rebuild-{today}"
    return row, row["reliable"]



def merge(raw, old, pins):
    """Keep unrequested traits, pin identity and independently checked witnesses."""
    if not isinstance(raw, dict) or raw.get("ok") is not True:
        raise ValueError("PGS calculation did not complete")
    rows = raw.get("traits")
    if not isinstance(rows, list) or not rows:
        raise ValueError("PGS calculation has no traits")
    if not isinstance(old, dict) or not isinstance(old.get("traits", []), list):
        raise ValueError("Invalid existing PGS report; nothing replaced")
    previous = {}
    for row in old.get("traits", []):
        if not isinstance(row, dict) or not isinstance(row.get("term"), str):
            raise ValueError("Invalid existing PGS trait")
        previous[row["term"]] = row
    merged = dict(previous)
    seen = set()
    today = date.today().isoformat()
    for t in rows:
        term = t.get("term") if isinstance(t, dict) else None
        if not isinstance(term, str) or not term or term in seen:
            raise ValueError("Missing or duplicate PGS trait identity")
        seen.add(term)
        row, _ = build_row(t, today)
        pin = pins.get(term) or {}
        if (t.get("status") not in ("ok", "ok_fallback") or not row.get("pgs_id")
                or pin.get("pgs_id") != row["pgs_id"]
                or row.get("scoring_validation", {}).get("checked") is not True):
            raise ValueError("Incomplete or unpinned PGS calculation: " + term)
        if term in previous:
            row["previous_result"] = {k: v for k, v in previous[term].items() if k != "previous_result"}
        merged[term] = row
    meta = dict(old.get("_meta") or {})
    meta.update(engine=__version__, updated=today, built_by="scholion.prs-recalculation",
                superpopulation=raw.get("superpopulation"),
                superpopulation_source=raw.get("superpopulation_source"),
                last_recalculation_input_vcf=raw.get("vcf"),
                total=len(merged), reliable_count=sum(bool(t.get("reliable")) for t in merged.values()))
    inputs = sorted({t["scoring_validation"]["input_vcf"] for t in merged.values()
                     if isinstance(t.get("scoring_validation"), dict)
                     and t["scoring_validation"].get("input_vcf")})
    if raw.get("connected_genome"):
        meta["connected_genome"] = raw["connected_genome"]
    meta["input_vcfs"] = inputs
    meta["input_vcf"] = inputs[0] if len(inputs) == 1 and all(
        (t.get("scoring_validation") or {}).get("input_vcf") == inputs[0]
        for t in merged.values()) else None
    return {"_meta": meta, "traits": list(merged.values())}


def save(raw, pins, stop=None):
    """Serialize the merge, preserve original bytes, then replace one profile file."""
    from . import container
    with container.pinned(), core.profile_write_lock():
        path = core.profile_dir() / "prs_results.json"
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        document = merge(raw, old, pins)
        if stop is not None and stop():
            return {"ok": False, "status": "stopped"}
        backup = None
        if path.exists():
            backup = path.with_name(path.name + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            shutil.copy2(path, backup)
        store._write_json(path, document)
        core.reset_cache()
        return {"ok": True, "status": "written", "path": str(path),
                "backup": str(backup) if backup else None,
                "rows": len(document["traits"]), "reliable": document["_meta"]["reliable_count"]}
