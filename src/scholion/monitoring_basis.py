"""Recorded laboratory values are not a product monitoring recommendation.

Each reason and marker selection requires independent support. This checks
structure only, not clinical validity or individual applicability of a guideline.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from .conclusion_basis import conclusion_basis
from .i18n import t


def _reason_basis(spec: Dict[str, Any]) -> Dict[str, Any]:
    basis = conclusion_basis(spec.get("why_basis"))
    text = spec.get("why")
    usable = (isinstance(text, str) and bool(text.strip())) or (
        isinstance(text, dict) and all(isinstance(text.get(k), str) and text[k].strip() for k in ("en", "ru")))
    if not usable:
        basis = {**basis, "status": "incomplete", "missing": [*basis["missing"], "claim_text"],
                 "reason": t("drug.guidance.claim_text")}
    return basis


def monitoring_for(classes: List[str], catalogue: Dict[str, Any], observations: List[Dict[str, Any]],
                   display: Callable[[Dict[str, Any]], str]) -> Dict[str, Any]:
    """Keep catalogue-selected observations while qualifying every proposed use."""
    by = {m["key"]: m for m in observations}
    rows: Dict[str, Dict[str, Any]] = {}
    whys, proposals, gaps = [], [], []
    for cls in classes:
        spec = catalogue.get(cls)
        if spec is None:
            continue
        basis = _reason_basis(spec)
        reason = spec.get("why") if basis["status"] == "complete" else None
        if isinstance(reason, dict):
            from .i18n import lang
            reason = reason[lang()]
        if reason:
            whys.append(reason)
        else:
            gaps.append({"class": cls, "claim": "reason", "conclusion_basis": basis,
                         "detail": t("monitoring.withheld", cls=cls, reason=basis["reason"])})
        selections = []
        for key in spec.get("labs", []):
            sb = conclusion_basis((spec.get("lab_basis") or {}).get(key))
            selection = {"class": cls, "key": key, "conclusion_basis": sb}
            selections.append(selection)
            if sb["status"] != "complete":
                gaps.append({**selection, "claim": "marker_selection",
                             "detail": t("monitoring.selection_withheld", name=display({"key": key}), reason=sb["reason"])})
            if key not in rows:
                m = by.get(key)
                rows[key] = {"key": key, "present": m is not None,
                             "name": m["name"] if m else display({"key": key}),
                             "value": m["value"] if m else None, "unit": m["unit"] if m else "",
                             "flag": m["flag"] if m else "nodata",
                             **{k: m.get(k) if m else None for k in
                                ("date", "date_source", "source", "near_limit", "personal_move", "ref_low", "ref_high")},
                             "decisions": m.get("decisions") or [] if m else [], "monitoring_basis": []}
            rows[key]["monitoring_basis"].append(selection)
        proposals.append({"class": cls, "reason": reason, "conclusion_basis": basis, "selections": selections})
    values = list(rows.values())
    return {"reason": "; ".join(dict.fromkeys(whys)), "markers": values,
            "basis": {"classes": list(classes), "with_rules": [c for c in classes if c in catalogue]},
            "proposals": proposals, "gaps": gaps,
            "watch": [r for r in values if r["flag"] in ("high", "low")],
            "near": [r for r in values if r.get("near_limit")],
            "crossed": [r for r in values if any(d["crossed"] for d in r["decisions"])],
            "unresolved": [r for r in values if any(d.get("crossed") is None for d in r["decisions"])]}
