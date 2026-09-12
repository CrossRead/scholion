"""The target a clinician set, beside the corridor (task 170).

Moved out of `labs.py` on 12.09.2026 the way the corridor rule was (143): a
domain of its own — what a treatment is aiming at is a different question from
what a laboratory calls normal, and the two answers must never read alike. This
module reads the profile through `core` and imports `analyze_labs` lazily, so
`labs` may import it at the top without a cycle.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .. import core
from ..i18n import lang as _lang, t as _t


# ---- the target a clinician set (task 170) --------------------------------
# Three things are deliberately NOT here. No figure is proposed: the target
# arrives from the person's word and is stored with who said it and when. No
# tolerance is assumed: a bare figure («free T3 5.0») is compared strictly, and
# «near enough» is the clinician's to state as bounds. And no flag is raised:
# `outside_target` is a fact placed beside the corridor, never folded into
# `flag` or `abnormal` — the corridor says whether a value is abnormal, the
# target says whether it is where the treatment is aiming, and the two must not
# read alike.

def outside_target(target: Optional[Dict[str, Any]], value: Any) -> Optional[bool]:
    """Whether the latest value stands outside the clinician's target.

    `None` when there is nothing to compare — no target, no value, or a target
    that names no figure at all. Bounds decide when they exist; a single figure
    decides by strict comparison, for the reason given above.
    """
    if not target or value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    lo, hi, one = target.get("low"), target.get("high"), target.get("value")
    if lo is not None or hi is not None:
        return (lo is not None and v < float(lo)) or (hi is not None and v > float(hi))
    if one is not None:
        return v != float(one)
    return None


def target_side(target: Optional[Dict[str, Any]], value: Any) -> Optional[str]:
    """`above`, `below`, `within` — or None when nothing can be said."""
    out = outside_target(target, value)
    if out is None:
        return None
    if not out:
        return "within"
    v = float(value)
    lo, hi, one = target.get("low"), target.get("high"), target.get("value")
    if hi is not None and v > float(hi):
        return "above"
    if lo is not None and v < float(lo):
        return "below"
    return "above" if one is not None and v > float(one) else "below"


def target_view(target: Dict[str, Any], value: Any = None) -> Dict[str, Any]:
    """The target as the renderers read it: the figures, the provenance, the side."""
    return {"low": target.get("low"), "high": target.get("high"),
            "value": target.get("value"), "unit": target.get("unit", ""),
            "set_by": target.get("set_by", ""), "set_on": target.get("set_on", ""),
            "note": target.get("note"), "side": target_side(target, value)}


def clinician_targets_view() -> Dict[str, Any]:
    """Every target a clinician set, each beside the marker's current value.

    The one place that OWNS the list «inside the corridor, outside the target»:
    the labs report and the page both read it from here rather than each
    filtering the analysis on its own, so that the question is asked in one
    wording and counted once. A marker with a target and no measurement yet is
    listed too — a target with nothing to compare against is still a fact about
    the treatment.
    """
    targets = core.clinician_targets_by_marker()
    if not targets:
        return {"status": "ok", "count": 0, "outside_count": 0, "to_discuss": [],
                "targets": []}
    from .labs import analyze_labs                  # lazy: labs imports this module
    analysed = {m["key"]: m for m in analyze_labs(list(targets)).get("markers", [])}
    known = core.lab_markers().get("markers", {})
    from ..i18n import lang as _lang
    rows = []
    for key, tg in sorted(targets.items()):
        m = analysed.get(key)
        stored = core.labs().get("markers", {}).get(key) or {}
        name = (core.marker_display(known.get(key) or {}, _lang())
                or stored.get("name") or key)
        current = None
        if m:
            current = {"value": m["value"], "date": m["date"], "flag": m["flag"],
                       "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high")}
        rows.append({"marker": key, "name": name,
                     **target_view(tg, m["value"] if m else None),
                     "current": current,
                     "outside_target": outside_target(tg, m["value"]) if m else None,
                     # The question this whole layer exists to ask: inside the
                     # laboratory corridor, outside the frame of treatment.
                     "in_corridor": (m["flag"] == "ok") if m else None})
    to_discuss = [r for r in rows if r["outside_target"] and r["in_corridor"]]
    return {"status": "ok", "count": len(rows),
            "outside_count": sum(1 for r in rows if r["outside_target"]),
            "to_discuss": [r["marker"] for r in to_discuss],
            "targets": rows}
