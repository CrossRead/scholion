"""Two quantities beside a polygenic percentile: how stable the number is, and
how informative the model is (task 132).

Split out of `genomics.py` on 08.09.2026 along the line the capability drew
itself: everything here is about the QUALITY of a stored score — what the
number would do under another reference population or another model, and how
much the model can tell at all — and nothing here computes a score or reads a
genome. `genomics.prs_findings` calls in once per report.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .. import core

#: The 90th percentile of a standard normal minus the 10th: 2 × 1.2816. The
#: distance, in standard deviations of the score, between a person at P10 and
#: one at P90 — the span every «per SD» effect size below is stretched over.
P90_P10_SD = 2.5631


def effect_size(text: Any) -> Optional[Dict[str, Any]]:
    """`HR=1.17 [1.13-1.21]` → {"kind": "HR", "per_sd": 1.17}.

    The scoring server quotes the model's effect size as the catalogue prints
    it — a hazard ratio, an odds ratio or a beta, per standard deviation of the
    score. That per-SD reading is the only one made here, and the report says
    so in its legend; a beta's unit is the study's own and is not known here.
    """
    m = re.match(r"\s*(HR|OR|Beta|beta|β)\s*=\s*(-?\d+(?:\.\d+)?)", str(text or ""))
    if not m:
        return None
    kind = {"beta": "Beta", "β": "Beta"}.get(m.group(1), m.group(1))
    return {"kind": kind, "per_sd": float(m.group(2))}


def annotate_measurement(traits: List[Dict[str, Any]]) -> None:
    """Two quantities beside every percentile: how STABLE the number is, and how
    INFORMATIVE the model is (task 132).

    A bare percentile looks equally convincing for coronary artery disease and
    for intelligence, and it is not: for the second, the choice of reference
    population moves the number by fifty points while the model's whole range
    separates the outcome by a few. «Signal to method» as one ratio was tried
    and is degenerate — the effect size cancels out of it — so the two are kept
    apart and both printed. Stability is a property of the MEASUREMENT: the
    spread across the five reference populations, the spread across the models
    the server scored for the trait, the share of the model actually covered.
    Informativeness is a property of the MODEL: its discrimination (AUROC) and
    what its full range does to the outcome. Where a figure is not on the
    machine the report says so by name: «not recorded» is a different statement
    from a small number.
    """
    sens = core.prs_ancestry_sensitivity()
    by_id: Dict[str, Dict[str, Any]] = {}
    by_term: Dict[str, Dict[str, Any]] = {}
    for s in (sens.get("traits") or []) if isinstance(sens, dict) else []:
        if s.get("pgs_id"):
            by_id[str(s["pgs_id"])] = s
        if s.get("term"):
            by_term[str(s["term"]).lower()] = s

    def _num(x):
        return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None

    for t in traits:
        s = by_id.get(str(t.get("pgs_id"))) or by_term.get(str(t.get("term", "")).lower())
        # The ancestry file answers about a MODEL; if the stored score moved to
        # another model since, the file's number is about a different sum.
        if s and t.get("pgs_id") and s.get("pgs_id") and s["pgs_id"] != t["pgs_id"]:
            s = None
        models = t.get("models") if isinstance(t.get("models"), dict) else {}
        mr, wm = _num(t.get("match_rate")), _num(t.get("weight_mass_coverage"))
        stab: Dict[str, Any] = {
            "ancestry_spread_pp": _num(s.get("spread")) if s else None,
            "populations": len(s.get("pct_by_pop") or {}) if s else 0,
            "models_spread_pp": _num(models.get("spread_pp")),
            "models_scored": models.get("scored") if isinstance(models.get("scored"), int) else None,
            "coverage_pct": round(mr * 100, 1) if mr is not None else None,
            "weight_pct": round(wm * 100, 1) if wm is not None else None,
        }
        stab["missing"] = [k for k in ("ancestry_spread_pp", "models_spread_pp", "coverage_pct")
                           if stab[k] is None]
        t["stability"] = stab
        es = effect_size(t.get("effect_size"))
        auroc = _num(t.get("auroc_estimate"))
        info: Dict[str, Any] = {"kind": es["kind"] if es else None,
                                "per_sd": es["per_sd"] if es else None,
                                "auroc": round(auroc, 3) if auroc is not None else None,
                                "p90_vs_p10_ratio": None, "p90_vs_p10_shift": None}
        if es and es["kind"] in ("HR", "OR") and es["per_sd"] > 0:
            info["p90_vs_p10_ratio"] = round(es["per_sd"] ** P90_P10_SD, 2)
        elif es:
            info["p90_vs_p10_shift"] = round(es["per_sd"] * P90_P10_SD, 2)
        info["missing"] = [k for k in ("auroc", "per_sd") if info[k] is None]
        t["informativeness"] = info
