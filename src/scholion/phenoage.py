"""PhenoAge (Levine 2018) — biological age. THE SINGLE source of truth for the formula.

⚠️ THE RULE, wired into the code: compute from ONE panel ONLY.
All 9 markers must come from ONE blood draw (one month in labs.json). Substituting a
value from an earlier panel when the fresh one lacks it is FORBIDDEN: the formula is
sensitive to albumin and creatinine, and a substitution yields a pleasant but wrong
number. A missing marker → the result «cannot be computed» + the list to order next time.
"""
from __future__ import annotations
import datetime
import math
import os
from typing import Any, Dict, List, Optional, Tuple

from . import core
from .i18n import t as _t

REQ = ["albumin", "creatinine", "glucose", "crp", "lymph", "mcv", "rdw", "alp", "wbc"]

# formula key -> possible keys in profile/labs.json (in order of priority)
LABS_KEYS: Dict[str, List[str]] = {
    "albumin": ["albumin"],
    "creatinine": ["creatinine"],
    "glucose": ["glucose"],
    "crp": ["crp_hs", "crp", "crp_ultra"],
    "lymph": ["lymph_pct", "lymph", "lymphocytes_pct"],
    "mcv": ["mcv"],
    "rdw": ["rdw", "rdw_cv"],
    "alp": ["alp", "alkaline_phosphatase"],
    "wbc": ["wbc", "leukocytes"],
}
def marker_name(key: str) -> str:
    """How one of the nine markers is called in the report, in the reader's language."""
    return _t(f"phenoage.marker.{key}")


def unit(key: str) -> str:
    """The unit the formula expects the marker in. Curated by the project, so it is
    spelled out in each language rather than copied off somebody's lab form."""
    return _t(f"phenoage.unit.{key}")


# Canonical-unit plausibility bands for the nine inputs. A value outside means the
# stored number is almost certainly in a different unit than the formula expects —
# refuse rather than compute a confidently wrong age (finding 31: albumin in g/dL
# read as g/L moved PhenoAge by 8.3 years and printed a hypoalbuminaemia
# incompatible with life). Bounds are deliberately wide; they catch unit errors,
# not borderline results.
_PLAUSIBLE = {
    "albumin": (20.0, 60.0),      # g/L
    "creatinine": (20.0, 1500.0), # umol/L
    "glucose": (1.5, 40.0),       # mmol/L
    "crp": (0.0, 500.0),          # mg/L
    "lymph": (1.0, 90.0),         # %
    "mcv": (50.0, 130.0),         # fL
    "rdw": (8.0, 30.0),           # %
    "alp": (10.0, 1500.0),        # U/L
    "wbc": (0.5, 100.0),          # 10^9/L
}


def _implausible(vals: Dict[str, float]) -> List[str]:
    out = []
    for k, (lo, hi) in _PLAUSIBLE.items():
        v = vals.get(k)
        if v is not None and not (lo <= v <= hi):
            out.append(k)
    return out


def formula(v: Dict[str, float]) -> Tuple[float, float]:
    """(PhenoAge, modelled 10-year mortality risk). Units are as in UNITS."""
    crp = max(v["crp"] / 10.0, 0.01)   # mg/L -> mg/dL, then the natural logarithm
    xb = (-19.9067
          - 0.0336 * v["albumin"] + 0.0095 * v["creatinine"] + 0.1953 * v["glucose"]
          + 0.0954 * math.log(crp) - 0.0120 * v["lymph"] + 0.0268 * v["mcv"]
          + 0.3306 * v["rdw"] + 0.00188 * v["alp"] + 0.0554 * v["wbc"] + 0.0804 * v["age"])
    g = 0.0076927
    M = 1 - math.exp(-math.exp(xb) * (math.exp(120 * g) - 1) / g)
    pa = 141.50225 + math.log(-0.00553 * math.log(1 - M)) / 0.090165
    return pa, M


def age_at(panel: str) -> Optional[float]:
    """Age at the middle of the panel's month (birth_date / birth_year from metrics.json)."""
    prof = core.metrics_json().get("profile", {})
    born = None
    bd = prof.get("birth_date")
    if bd:
        try:
            y, m, d = (int(x) for x in str(bd).split("-")[:3])
            born = datetime.date(y, m, d)
        except Exception:
            born = None
    if born is None and prof.get("birth_year"):
        born = datetime.date(int(prof["birth_year"]), 7, 1)
    if born is None:
        return None
    y, m = (int(x) for x in panel.split("-")[:2])
    return (datetime.date(y, m, 15) - born).days / 365.2425


def collect_panel(panel: str) -> Tuple[Dict[str, float], List[str], Dict[str, str]]:
    """Values STRICTLY for the month `panel`. -> (values, missing, used_labs_keys)."""
    markers = core.labs().get("markers", {})
    vals: Dict[str, float] = {}
    used: Dict[str, str] = {}
    missing: List[str] = []
    for m in REQ:
        hit = None
        for k in LABS_KEYS[m]:
            spec = markers.get(k)
            if not spec:
                continue
            for pt in spec.get("series", []):
                if str(pt.get("date", ""))[:7] == panel:
                    hit = (k, float(pt["value"]))
                    break
            if hit:
                break
        if hit:
            used[m], vals[m] = hit[0], hit[1]
        else:
            missing.append(m)
    return vals, missing, used


def panel_months() -> List[str]:
    markers = core.labs().get("markers", {})
    months = set()
    for m in REQ:
        for k in LABS_KEYS[m]:
            for pt in markers.get(k, {}).get("series", []):
                d = str(pt.get("date", ""))[:7]
                if len(d) == 7:
                    months.add(d)
    return sorted(months)


def panels_overview() -> Dict[str, Any]:
    out = []
    for p in panel_months():
        vals, missing, _ = collect_panel(p)
        out.append({"panel": p, "have": 9 - len(missing), "complete": not missing,
                    "missing": missing, "missing_ru": [marker_name(m) for m in missing]})
    return {"panels": out, "complete": [x["panel"] for x in out if x["complete"]],
            "rule": _t("phenoage.rule")}


def compute_panel(panel: str = "latest", track: bool = False,
                  age: Optional[float] = None) -> Dict[str, Any]:
    months = panel_months()
    if not months:
        return {"ok": False, "error": "no_data", "message": _t("phenoage.no_data")}
    if panel in (None, "", "latest"):
        complete = [p for p in months if not collect_panel(p)[1]]
        panel = complete[-1] if complete else months[-1]
    vals, missing, used = collect_panel(panel)
    if missing:
        return {"ok": False, "error": "incomplete_panel", "panel": panel,
                "have": {m: vals[m] for m in REQ if m in vals},
                "missing": missing, "missing_ru": [marker_name(m) for m in missing],
                "request_next_panel": [f"{marker_name(m)} ({unit(m)})" for m in missing],
                "message": _t("phenoage.incomplete", panel=panel, n=len(missing))}
    bad = _implausible(vals)
    if bad:
        return {"ok": False, "error": "implausible_units", "panel": panel,
                "markers": bad, "markers_ru": [marker_name(m) for m in bad],
                "message": _t("phenoage.implausible", markers=", ".join(marker_name(m) for m in bad))}
    a = age if age is not None else age_at(panel)
    if a is None:
        return {"ok": False, "error": "no_age", "panel": panel,
                "message": _t("phenoage.no_age")}
    vals["age"] = a
    try:
        pa, M = formula(vals)
    except (ValueError, OverflowError):
        # The math domain can be left only by an input the plausibility gate should
        # have caught; refusing is the contract, a traceback is not (finding 32).
        return {"ok": False, "error": "compute_failed", "panel": panel,
                "message": _t("phenoage.compute_failed")}
    res = {"ok": True, "panel": panel, "age": round(a, 1), "phenoage": round(pa, 1),
           "delta": round(pa - a, 1), "mortality_10y_pct": round(M * 100, 1),
           "values": {m: vals[m] for m in REQ}, "labs_keys": used, "tracked": False}
    if track:
        res["tracked"] = _track(res)
    return res


def _track(res: Dict[str, Any]) -> bool:
    hist = core.profile_dir() / "biological_age_history.md"
    try:
        txt = hist.read_text(encoding="utf-8") if hist.exists() else ""
        if f"| {res['panel']} |" in txt:
            return False
        with hist.open("a", encoding="utf-8") as f:
            if not txt:
                f.write(_t("phenoage.history_header"))
            f.write(f"| {res['panel']} | {res['age']:.1f} | {res['phenoage']:.1f} | "
                    f"{res['delta']:+.1f} | {res['mortality_10y_pct']:.1f}% |\n")
        return True
    except Exception:
        return False


# ---- rendering ------------------------------------------------------------
def format_panels(r: Dict[str, Any]) -> str:
    lines = [_t("phenoage.panels_title"), "", _t("phenoage.panels_lead"), ""]
    for p in r["panels"]:
        if p["complete"]:
            lines.append(_t("phenoage.panel_complete", panel=p["panel"]))
        else:
            lines.append(_t("phenoage.panel_incomplete", panel=p["panel"], have=p["have"],
                            missing=", ".join(p["missing_ru"])))
    lines += ["", "⚠️ " + r["rule"]]
    return "\n".join(lines)


def format_result(r: Dict[str, Any]) -> str:
    if not r.get("ok"):
        if r.get("error") == "incomplete_panel":
            out = [_t("phenoage.cannot_title", panel=r["panel"]), "",
                   _t("phenoage.cannot_missing", n=len(r["missing"]),
                      missing=", ".join(r["missing_ru"])), ""]
            if r.get("have"):
                out.append(_t("phenoage.have_in_panel",
                              items=", ".join(f"{marker_name(m)} {v:g}"
                                              for m, v in r["have"].items())))
            out += ["", _t("phenoage.request_next")]
            out += [f"- {x}" for x in r["request_next_panel"]]
            out += ["", _t("phenoage.no_substitution")]
            return "\n".join(out)
        return f"⚠️ {r.get('message', r.get('error'))}"
    src = ", ".join(f"{marker_name(m)} {r['values'][m]:g} {unit(m)}" for m in REQ)
    out = [_t("phenoage.title", panel=r["panel"]), "",
           _t("phenoage.chrono_age", value=f"{r['age']:.1f}"),
           _t("phenoage.value", value=f"{r['phenoage']:.1f}", delta=f"{r['delta']:+.1f}"),
           _t("phenoage.mortality", value=f"{r['mortality_10y_pct']:.1f}"), "",
           _t("phenoage.source", items=src), "",
           _t("phenoage.caveat")]
    if r.get("tracked"):
        out += ["", _t("phenoage.tracked")]
    return "\n".join(out)
