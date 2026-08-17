"""provenance.py — the REVERSE check: every profile data point → its source report.

Why a separate module. `reconcile` goes one way: «it is in the PDF → is it in the
profile». That direction catches LOSSES. But it is inherently blind to the opposite
class of defects — a point that IS in the profile while no report holds it: a typo
during manual entry, a value from someone else's date, a «derived index» that does not
follow from its own components. The live case the module was written for: a HOMA-IR
index stored for a month where the profile holds insulin but no glucose at all — no
report contains that number, and recomputing it gives a value several times larger.

Verdict classes for each point:
  form        — the value was found in a report from the same month (provenance exists);
  alt_form    — a report for this marker/month exists, but the value comes from a
                DIFFERENT method of the same draw (LC-MS vs CLIA) and the marker has
                prefer_form set — legitimate;
  derived_ok  — the derived index agrees with its components in the profile;
  derived_bad — 🔴 the derived index CONTRADICTS the components — a data defect;
  derived_orphan — 🔴 a derived index that is in no report and cannot be recomputed
                (the components are not in the profile) — the point hangs in the air;
  conflict    — 🔴 a report for this marker/month exists, the value differs, and there
                is no «second method» explanation;
  manual      — there is no report for this marker in this month at all: manual entry, a
                paper conclusion, an external lab. Not an error, but NOT a fact from a report.

Writes nothing to labs.json. Run with:
  python -m scholion provenance [--refresh] [--marker KEY] [--json]
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core
from .i18n import t as _t

# --- derived indices: how they are computed from other points of THE SAME month ---
# `expr` holds a catalogue KEY, not the formula itself: the formula is printed into the
# report next to the numbers, and it names the markers in the reader's language.
# strict=True  → a discrepancy counts as a defect (the index definition is universal);
# strict=False → for reference only (the lab may have used a direct method).
DERIVED: Dict[str, Dict[str, Any]] = {
    "homa_ir": {
        "needs": ["insulin", "glucose"],
        "fn": lambda v: v["insulin"] * v["glucose"] / 22.5,
        "expr": "provenance.expr.homa_ir", "tol": 0.12, "strict": True},
    "atherogenic_index": {
        "needs": ["cholesterol_total", "hdl"],
        "fn": lambda v: (v["cholesterol_total"] - v["hdl"]) / v["hdl"],
        "expr": "provenance.expr.atherogenic_index", "tol": 0.10, "strict": True},
    "free_androgen_index": {
        "needs": ["testosterone", "shbg"],
        "fn": lambda v: v["testosterone"] / v["shbg"] * 100.0,
        "expr": "provenance.expr.free_androgen_index", "tol": 0.10, "strict": True},
    "ag_ratio": {
        "needs": ["albumin", "protein_total"],
        "fn": lambda v: v["albumin"] / (v["protein_total"] - v["albumin"]),
        "expr": "provenance.expr.ag_ratio", "tol": 0.10, "strict": True},
    "non_hdl": {
        "needs": ["cholesterol_total", "hdl"],
        "fn": lambda v: v["cholesterol_total"] - v["hdl"],
        "expr": "provenance.expr.non_hdl", "tol": 0.05, "strict": True},
    "ldl": {
        "needs": ["cholesterol_total", "hdl", "triglycerides"],
        "fn": lambda v: v["cholesterol_total"] - v["hdl"] - v["triglycerides"] / 2.2,
        "expr": "provenance.expr.ldl", "tol": 0.15, "strict": False,
        "skip_if": lambda v: v["triglycerides"] >= 4.5},
    "omega6_omega3_ratio": {
        "needs": ["omega6", "omega3"],
        "fn": lambda v: v["omega6"] / v["omega3"],
        "expr": "provenance.expr.omega6_omega3_ratio", "tol": 0.10, "strict": False},
}


def _close(a: float, b: float, tol: float = 0.02) -> bool:
    return abs(a - b) <= max(0.05, abs(b) * tol)


def _load_coverage(refresh: bool, lab_dir: Optional[str]) -> Dict[str, Any]:
    # Same path as `reconcile` writes — built from the profile, not from the code.
    p = core.profile_dir() / "labs_coverage.json"
    if refresh or not p.exists():
        from . import reconcile as _rec
        _rec.reconcile(lab_dir)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8")).get("coverage", {})


def audit(refresh: bool = False, lab_dir: Optional[str] = None,
          marker: Optional[str] = None) -> Dict[str, Any]:
    labs = core.labs().get("markers", {})
    if not labs:
        return {"ok": False, "error": _t("provenance.no_labs")}
    cov = _load_coverage(refresh, lab_dir)
    if not cov:
        return {"ok": False, "error": _t("provenance.no_coverage")}
    dictionary = core.lab_markers().get("markers", {})

    # the profile as {month: {marker: value}} for the derived indices
    by_month: Dict[str, Dict[str, float]] = {}
    for k, m in labs.items():
        for pt in m.get("series", []):
            if "date" in pt and isinstance(pt.get("value"), (int, float)):
                by_month.setdefault(pt["date"], {})[k] = float(pt["value"])

    points: List[Dict[str, Any]] = []
    for k, m in sorted(labs.items()):
        if marker and k != marker:
            continue
        prefer = [x.lower() for x in core.marker_rules(dictionary.get(k, {}), "prefer_form")]
        for pt in m.get("series", []):
            ym, val = pt.get("date"), pt.get("value")
            if ym is None or not isinstance(val, (int, float)):
                continue
            rec: Dict[str, Any] = {"marker": k, "date": ym, "value": val,
                                   "unit": m.get("unit"), "verdict": "", "detail": ""}
            slot = cov.get(k, {}).get(ym)
            srcs = (slot or {}).get("sources") or ([slot] if slot else [])
            hit = next((s for s in srcs if s.get("value") is not None
                        and _close(float(s["value"]), float(val))), None)
            if hit:
                rec["verdict"] = "form"
                rec["detail"] = hit.get("file", "")
                rec["form"] = hit.get("form", "")
            elif srcs:
                other = ", ".join(f"{s.get('value')} [{s.get('form','—')}]" for s in srcs)
                if prefer:
                    rec["verdict"] = "alt_form"
                    rec["detail"] = _t("provenance.alt_form", values=other,
                                       prefer='/'.join(prefer))
                else:
                    rec["verdict"] = "conflict"
                    rec["detail"] = _t("provenance.conflict", values=other, value=val)
            else:
                rec["verdict"] = "manual"
                rec["detail"] = _t("provenance.no_form")

            # derived indices are checked ALWAYS — even if the value is printed in a report:
            # a printed index is not an independent measurement (see Step 0.6 item 11).
            d = DERIVED.get(k)
            if d:
                have = by_month.get(ym, {})
                comp = {n: have[n] for n in d["needs"] if n in have}
                if len(comp) == len(d["needs"]):
                    if d.get("skip_if") and d["skip_if"](comp):
                        rec["derived"] = _t("provenance.derived_skipped")
                    else:
                        exp = d["fn"](comp)
                        okd = _close(float(val), exp, d["tol"])
                        rec["derived"] = (f"{_t(d['expr'])} = {exp:.2f} "
                                          f"({', '.join(f'{n}={comp[n]}' for n in d['needs'])})")
                        if okd:
                            if rec["verdict"] in ("manual", "form"):
                                rec["verdict"] = "derived_ok"
                        elif d["strict"]:
                            rec["verdict"] = "derived_bad"
                            rec["detail"] = _t("provenance.derived_mismatch", value=val,
                                               expected=f"{exp:.2f}", expr=_t(d["expr"]))
                else:
                    miss = [n for n in d["needs"] if n not in have]
                    rec["derived"] = _t("provenance.derived_nothing", missing=', '.join(miss))
                    # A derived index that is in no report at all and that cannot be
                    # recomputed hangs in the air. This is not «manual entry», it is a
                    # point with no grounds whatsoever: a separate, stricter class.
                    if rec["verdict"] == "manual":
                        rec["verdict"] = "derived_orphan"
                        present = [n for n in d["needs"] if n in have]
                        rec["detail"] = (_t("provenance.derived_orphan", missing=', '.join(miss))
                                         + (_t("provenance.derived_orphan_partial",
                                               present=', '.join(present)) if present else ""))
            points.append(rec)

    order = ["derived_bad", "derived_orphan", "conflict", "manual", "alt_form", "derived_ok", "form"]
    counts = {v: sum(1 for p in points if p["verdict"] == v) for v in order}
    return {"ok": True, "total": len(points), "counts": counts, "points": points,
            "defects": [p for p in points if p["verdict"] in ("derived_bad", "derived_orphan", "conflict")],
            "unverified": [p for p in points if p["verdict"] == "manual"]}


def format_report(res: Dict[str, Any]) -> str:
    if not res.get("ok"):
        return "⚠️ " + str(res.get("error", ""))
    c, t = res["counts"], res["total"]
    out = [_t("provenance.title"),
           _t("provenance.total", n=t),
           "",
           _t("provenance.count_form", n=c["form"]),
           _t("provenance.count_alt_form", n=c["alt_form"]),
           _t("provenance.count_derived_ok", n=c["derived_ok"]),
           _t("provenance.count_manual", n=c["manual"]),
           _t("provenance.count_conflict", n=c["conflict"]),
           _t("provenance.count_derived_bad", n=c["derived_bad"]),
           _t("provenance.count_derived_orphan", n=c["derived_orphan"]),
           ""]
    if res["defects"]:
        out.append(_t("provenance.defects_header"))
        for p in res["defects"]:
            out.append(f"- **{p['marker']} {p['date']} = {p['value']}** — {p['detail']}")
        out.append("")
    if res["unverified"]:
        out.append(_t("provenance.unverified_header", n=len(res["unverified"])))
        by_m: Dict[str, List[str]] = {}
        for p in res["unverified"]:
            by_m.setdefault(p["marker"], []).append(p["date"])
        for k in sorted(by_m):
            out.append(f"- {k}: {', '.join(sorted(by_m[k]))}")
    return "\n".join(out)
