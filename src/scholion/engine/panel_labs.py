"""A system's long laboratory panel: shown, not scored (task 200, stage B).

A system's score is built from a few markers that mean something one by one.
Some systems also have a panel whose single values say little on their own —
thirty amino acids are read as a picture and through their ratios — and thirty
corridors inside a score would be noise that looks like knowledge. Such markers
are declared as `panel_markers` beside `markers`, and ratios as `derived`; this
module shows them and never lets them into the score.

A ratio is taken as the laboratory printed it when it did; otherwise it is
computed from its components, and only from components measured on the same
day — a ratio of two values drawn months apart describes no moment. A ratio
with no published range is shown as a value, with no arrow and no colour.
"""
from __future__ import annotations

from typing import Any, Dict, List


def _day(row: Dict[str, Any]) -> str:
    return str(row.get("date") or "")[:10]


def _ratio(key: str, by_key: Dict[str, Any]) -> Dict[str, Any]:
    from .. import provenance
    printed = by_key.get(key)
    spec = provenance.DERIVED.get(key) or {}
    needs = list(spec.get("needs") or [])
    out: Dict[str, Any] = {"key": key, "needs": needs}
    if printed and printed.get("value") is not None:
        return {**out, "origin": "printed", "value": printed.get("value"), "date": printed.get("date"),
                "name": printed.get("name"), "ref_low": printed.get("ref_low"),
                "ref_high": printed.get("ref_high")}
    rows = [by_key.get(n) for n in needs]
    missing = [n for n, r in zip(needs, rows) if not r or r.get("value") is None]
    if missing:
        return {**out, "origin": "missing", "missing": missing}
    # The LAST DRAW THAT HOLDS THEM ALL, not each marker's own last point.
    # Taking the latest of each and then demanding one day threw away a ratio
    # whose components were drawn together, only because one of them was
    # measured again later: on 17.09.2026 that silently killed urea/creatinine
    # — the one ratio of this panel with a published corridor — and
    # methionine/homocysteine, both present in one draw of 22.07.2026.
    at = _common_day(needs, rows)
    if at is None:
        return {**out, "origin": "not_same_day", "days": sorted({_day(r) for r in rows})}
    if at == "not_a_number":
        return {**out, "origin": "not_computable"}
    day, values, stamp = at
    try:
        value = spec["fn"](values)
    except (ZeroDivisionError, KeyError, TypeError, ValueError):
        return {**out, "origin": "not_computable"}
    return {**out, "origin": "computed", "value": round(value, 3), "date": stamp}


def _common_day(needs: List[str], rows: List[Dict[str, Any]]):
    """`(day, {marker: value}, timestamp)` of the latest draw holding every component.

    A marker carries its whole series, so a component measured again later does
    not hide the draw where the pair was taken together. Only a day where ALL of
    them are present is offered — a ratio of two values drawn months apart
    describes no moment, and that rule is what this looks for a day to satisfy.
    """
    by_day: List[Dict[str, Dict[str, Any]]] = []
    seen: Dict[str, Dict[str, Any]] = {}
    for name, row in zip(needs, rows):
        points = list(row.get("series") or [])
        if not points:
            points = [{"date": row.get("date"), "value": row.get("value")}]
        seen[name] = {}
        for p in points:
            if p.get("value") is None:
                continue
            seen[name].setdefault(str(p.get("date") or "")[:10], p)
    days = set.intersection(*[set(v) for v in seen.values()]) if seen else set()
    days.discard("")
    if not days:
        return None
    day = max(days)
    picked = {n: seen[n][day] for n in needs}
    try:
        values = {n: float(picked[n]["value"]) for n in needs}
    except (TypeError, ValueError):
        # The pair WAS drawn together; what is not a number is the value. Saying
        # «not the same day» here would send a reader to look for a draw that
        # exists.
        return "not_a_number"
    stamp = max(str(picked[n].get("date") or "") for n in needs)
    return day, values, stamp


def panel_view(dom: Dict[str, Any], by_key: Dict[str, Any]) -> Dict[str, Any]:
    """The panel markers measured, those not measured, and the ratios — or None."""
    keys: List[str] = list(dom.get("panel_markers") or [])
    derived: List[str] = list(dom.get("derived") or [])
    if not keys and not derived:
        return None
    from .system_panels import _marker_name
    measured = []
    for k in keys:
        r = by_key.get(k)
        if r and r.get("value") is not None:
            measured.append({"key": k, "name": r.get("name") or _marker_name(k), "value": r.get("value"),
                             "unit": r.get("unit"), "date": r.get("date"), "ref_low": r.get("ref_low"),
                             "ref_high": r.get("ref_high"), "flag": r.get("flag")})
    ratios = []
    for k in derived:
        x = _ratio(k, by_key)
        x["name"] = x.get("name") or _marker_name(k)
        if x.get("missing"):
            x["missing_names"] = [_marker_name(m) for m in x["missing"]]
        x["has_range"] = x.get("ref_low") is not None or x.get("ref_high") is not None
        ratios.append(x)
    return {"markers": measured,
            "unmeasured": [_marker_name(k) for k in keys if k not in {m["key"] for m in measured}],
            "total": len(keys), "ratios": ratios, "scored": False}
