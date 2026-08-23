"""Goal dashboards and proposed targets.

Reads the person's health_goals.json and the observation series behind each
goal; proposes targets from three sources (own best sustained period, clinical
guideline candidates, the person's explicit choice) and never writes any of
them -- a goal is accepted by the person or it does not exist.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from .. import core
from ..i18n import lang as _lang, plural as _plural, t as _t
from ._helpers import DISCLAIMER


def _goal_series(ref: str) -> List[Dict[str, Any]]:
    """Resolve a source of the SINGLE data model into a sorted series [{date,value}].

    ref of the form 'lab:<marker>' (labs.json markers[key].series) or
    'wear:<Metric>' (wearable_trends.json metrics[Metric] = {YYYY-MM: value}).
    That way the goal chart feeds on the project's LIVE data and not on a copy of its own.
    """
    if not ref:
        return []
    kind, _, key = ref.partition(":")
    pts: List[Dict[str, Any]] = []
    if kind == "lab":
        m = core.labs().get("markers", {}).get(key) or {}
        for p in m.get("series", []) or []:
            if p.get("value") is not None and p.get("date"):
                pts.append({"date": str(p["date"]), "value": float(p["value"])})
    elif kind == "wear":
        data = core.wearable_trends()
        msrc = data.get("metrics") if isinstance(data.get("metrics"), dict) else data
        sd = (msrc or {}).get(key)
        if isinstance(sd, dict):
            for y, v in sd.items():
                if isinstance(v, (int, float)):
                    pts.append({"date": str(y), "value": float(v)})
    return sorted(pts, key=lambda p: p["date"])


def _goal_lv(ref: str) -> Dict[str, Any]:
    """Series → {l:[dates], v:[values]} for Chart.js."""
    s = _goal_series(ref)
    return {"l": [p["date"] for p in s], "v": [p["value"] for p in s]}


def _goal_merge(ref_a: str, ref_b: str) -> Dict[str, Any]:
    """Two series on a common sorted date axis (gaps = null, spanGaps on the client)."""
    a, b = _goal_series(ref_a), _goal_series(ref_b)
    da = {p["date"]: p["value"] for p in a}
    db = {p["date"]: p["value"] for p in b}
    labels = sorted(set(da) | set(db))
    return {"l": labels,
            "a": [da.get(x) for x in labels],
            "b": [db.get(x) for x in labels]}


def _goal_num(v: Optional[float]) -> str:
    """Number → a string, with the decimal separator the OUTPUT LANGUAGE uses.

    The comma was hard-coded. On the English page it put «TSH 6,4» in the goal
    table three centimetres above a card reading «6.42» — the same value in two
    notations, which reads as two measurements. The interface has a rule for this
    already (a comma in Russian, a point in English); this function was outside it.
    """
    if v is None:
        return "—"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    out = f"{v:.1f}"
    return out.replace(".", ",") if _lang() == "ru" else out


def _goal_now(source: str) -> str:
    """Current value(s) for the source(s). 'lab:a|lab:b' → 'a_last / b_last'."""
    parts = []
    for ref in source.split("|"):
        s = _goal_series(ref.strip())
        parts.append(_goal_num(s[-1]["value"]) if s else "—")
    return " / ".join(parts)


def goal_dashboard() -> Dict[str, Any]:
    """Dashboard of the GOAL ("get the 2021–2022 shape back") on the project's SINGLE data model.

    The curated part (the wording, the anchor points, the reference values, the chart parameters)
    comes from profile/health_goals.json. The current values and all the series are LIVE from
    labs.json and wearable_trends.json (the same sources the rest of the application sees).
    """
    g = core.health_goals()
    if not g or not g.get("targets"):
        return {"available": False, "disclaimer": DISCLAIMER(),
                "message": _t("goal.not_set")}

    targets = [{"label": t["label"], "now": _goal_now(t.get("source", "")),
                "best": t.get("best", ""), "target": t.get("target", "")}
               for t in g.get("targets", [])]

    ch = g.get("charts", {}) or {}
    charts: Dict[str, Any] = {}

    if "weight" in ch:
        c = ch["weight"]
        charts["weight"] = {**{k: c[k] for k in ("title", "cap", "band", "targets", "min", "max") if k in c},
                            **_goal_lv(c.get("source", ""))}
    if "bodycomp" in ch:
        c = ch["bodycomp"]
        m = _goal_merge(c.get("fat", ""), c.get("mus", ""))
        charts["bodycomp"] = {**{k: c[k] for k in ("title", "cap", "targets", "ymin", "ymax", "y2min", "y2max") if k in c},
                              "l": m["l"], "fat": m["a"], "mus": m["b"]}
    if "minis" in ch:
        minis = []
        for c in ch["minis"]:
            minis.append({**{k: c[k] for k in ("id", "title", "cap", "color", "tgt", "tlabel", "min", "max") if k in c},
                          **_goal_lv(c.get("source", ""))})
        charts["minis"] = minis
    for dual in ("fit", "la"):
        if dual in ch:
            c = ch[dual]
            m = _goal_merge(c.get("a", ""), c.get("b", ""))
            charts[dual] = {**{k: c[k] for k in ("title", "cap", "band", "targets", "ymin", "ymax",
                                                 "y2min", "y2max", "a_label", "b_label", "a_color", "b_color") if k in c},
                            "l": m["l"], "a": m["a"], "b": m["b"]}

    return {
        "available": True,
        "title": g.get("title") or _t("goal.title_default"),
        "headline": g.get("headline", ""),
        "as_of": core.file_date(core.profile_dir() / "wearable_trends.json") or g.get("_meta", {}).get("updated"),
        "peaks": g.get("peaks", []),
        "targets": targets,
        "charts": charts,
        "disclaimer": DISCLAIMER(),
    }


# ======================= proposing a goal, rather than shipping one ==========
# A goal used to arrive with the product: `health_goals.json` carried one
# person's targets, and every new profile opened under them. The mechanism was
# always general — a target, a reference point, a line on a chart — but the
# numbers in it belonged to whoever wrote the file.
#
# What replaces it is a PROPOSAL, and the whole design is in where a proposal may
# come from. There are exactly three honest sources and they are not
# interchangeable:
#
#   guideline      A clinical association published a target for this marker, for
#                  a named population, and it is quoted with its citation. The
#                  strongest source and the rarest: most markers have no such
#                  target, and for at least one — 25(OH)D — a society looked and
#                  withdrew the one it had.
#   personal_best  The best value this person has actually reached, taken from
#                  their own series. Not a recommendation from anybody; a
#                  statement that they have been there before, with the date and
#                  the number of readings behind it.
#   reference      The wall of the laboratory corridor. Weakest of the three and
#                  offered last, because «inside the range» is where most people
#                  already are and is not an aim.
#
# The rule the rest of the project runs on applies here too: a value is
# inseparable from its evidential status. So every candidate carries where it
# came from, and the proposal says which one it chose and what it assumed.

_GOAL_MIN_POINTS = 3          # fewer than three readings is not a trend


_GOAL_MIN_SPAN_MONTHS = 6     # nor is three readings inside one week


_GOAL_MIN_GAIN = 0.05         # a «best» within 5 % of now is not a goal, it is noise


def _months_between(a: str, b: str) -> int:
    """Whole months between two 'YYYY-MM…' stamps. Dates here are never times."""
    try:
        ya, ma = int(a[:4]), int(a[5:7] or 1)
        yb, mb = int(b[:4]), int(b[5:7] or 1)
        return abs((yb - ya) * 12 + (mb - ma))
    except Exception:                                        # noqa: BLE001
        return 0


def _marker_direction(spec: Dict[str, Any], now: Optional[Dict[str, Any]]) -> str:
    """Which way is better — for THIS marker and THIS person, right now.

    The first version asked only the catalogue and answered «unknown» for every
    marker with two bounds, which is most of them: ferritin, B12, glucose,
    creatinine. Those are exactly the markers a goal is worth setting for, so the
    proposer skipped the interesting half of the profile.

    The mistake was treating direction as a property of the marker in the
    abstract. Ferritin has no direction in the abstract — it can be too low and
    too high. It has a very definite one for somebody sitting at 13 against a
    floor of 20, and that is not a guess, it is where they are.

    So: the catalogue wins where it states a direction, a single bound implies
    one, and otherwise the person's own position against their corridor decides.
    Inside the corridor there is genuinely no direction, and the answer is
    «inside» — not «unknown», because those call for different sentences.
    """
    d = (spec or {}).get("direction")
    if d in ("higher_better", "lower_better"):
        return d
    lo, hi = (spec or {}).get("ref_low"), (spec or {}).get("ref_high")
    if hi is not None and lo is None:
        return "lower_better"
    if lo is not None and hi is None:
        return "higher_better"
    if lo is not None and hi is not None and now is not None:
        if now["value"] < lo:
            return "higher_better"
        if now["value"] > hi:
            return "lower_better"
        return "inside"
    return "unknown"


def _meets(value: float, comparator: str, target: float) -> bool:
    return {"<": value < target, "<=": value <= target,
            ">": value > target, ">=": value >= target}.get(comparator, False)


def _best_of(series: List[Dict[str, Any]], direction: str) -> Optional[Dict[str, Any]]:
    if not series or direction not in ("higher_better", "lower_better"):
        return None
    pick = max if direction == "higher_better" else min
    return pick(series, key=lambda p: p["value"])


def _guideline_candidate(key: str, unit: str) -> Optional[Dict[str, Any]]:
    """The published target for this marker, or the published refusal to set one."""
    entry = (core.goal_targets().get("targets") or {}).get(key)
    if not entry:
        return None
    src = entry.get("source") or {}
    base = {"source": "guideline", "unit": entry.get("unit"),
            "citation": {k: src.get(k) for k in ("body", "document", "year", "url") if src.get(k)},
            "quote": src.get("quote"), "note": entry.get("note")}
    # A society that looked and declined. Carried as a candidate with no number,
    # because the absence is the finding and hiding it would let the personal-best
    # route quietly invent the target the society refused to write.
    if entry.get("no_target"):
        return {**base, "no_target": True,
                "why": _t("goalgen.why.no_target", body=src.get("body", "")),
                "still_matters_when": entry.get("still_matters_when")}
    # Risk-stratified targets: the category is a clinical judgement this program
    # does not make. One is offered, the assumption is stated, the rest are listed.
    if entry.get("by_category"):
        cats = entry["by_category"]
        default = entry.get("default_category")
        chosen = next((c for c in cats if c["category"] == default), cats[0])
        return {**base, "comparator": chosen["comparator"], "value": chosen["value"],
                "assumed": {"field": entry.get("depends_on"), "value": chosen["category"],
                            "note": entry.get("default_note")},
                "alternatives": [{"category": c["category"], "comparator": c["comparator"],
                                  "value": c["value"], "and_also": c.get("and_also")} for c in cats],
                "cannot_be_decided_here": entry.get("cannot_be_decided_here"),
                "why": _t("goalgen.why.guideline", body=src.get("body", ""),
                          year=src.get("year", ""))}
    if entry.get("value") is None:
        return None
    out = {**base, "comparator": entry.get("comparator", "<"), "value": entry["value"],
           "why": _t("goalgen.why.guideline", body=src.get("body", ""), year=src.get("year", ""))}
    # A target written for people with a condition is not a target for people
    # without it. Where the profile cannot confirm the condition, the candidate is
    # still offered — but marked, so it is never chosen silently.
    aw = entry.get("applies_when") or {}
    if aw.get("has_condition"):
        out["applies_when"] = aw["has_condition"]
        out["why"] = _t("goalgen.why.guideline_conditional", body=src.get("body", ""),
                        year=src.get("year", ""), condition=aw["has_condition"])
    return out


def suggest_goal_targets(marker_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Propose a target for each marker there is enough evidence to propose one for.

    Returns proposals, and — as importantly — the markers it declined to propose
    for and the reason. A list of five suggestions with no account of the forty it
    passed over reads as «these are the five that matter», which is a different
    and false claim.
    """
    labs = core.labs().get("markers", {}) or {}
    cat = {m["key"]: m for m in core.marker_catalog()}
    known = core.lab_markers().get("markers", {}) or {}
    keys = marker_keys or sorted(labs.keys())
    proposals, skipped, already_met = [], [], []

    for key in keys:
        m = labs.get(key) or {}
        # The catalogue for the label and the corridor, the dictionary for the
        # direction — the profile does not record which way is better.
        spec = {**(known.get(key) or {}), **(cat.get(key) or {}),
                **{k: m[k] for k in ("unit", "ref_low", "ref_high", "direction") if k in m}}
        name = m.get("name") or (cat.get(key) or {}).get("name") or key
        unit = m.get("unit") or (cat.get(key) or {}).get("unit") or ""
        series = sorted([{"date": str(p["date"]), "value": float(p["value"])}
                         for p in (m.get("series") or []) if p.get("value") is not None
                         and p.get("date")], key=lambda p: p["date"])
        now = series[-1] if series else None
        direction = _marker_direction(spec, now)

        candidates = []
        g = _guideline_candidate(key, unit)
        if g:
            candidates.append(g)

        # --- the person's own best -------------------------------------------
        span = _months_between(series[0]["date"], series[-1]["date"]) if len(series) > 1 else 0
        best = _best_of(series, direction)
        if best is None:
            pb_reason = ("no_direction" if direction == "unknown" else "no_series")
        elif len(series) < _GOAL_MIN_POINTS:
            pb_reason = "too_few_points"
        elif span < _GOAL_MIN_SPAN_MONTHS:
            pb_reason = "too_short_a_window"
        elif now and now["value"] and abs(best["value"] - now["value"]) / abs(now["value"]) < _GOAL_MIN_GAIN:
            pb_reason = "already_there"
        else:
            pb_reason = None
        if pb_reason is None and best is not None:
            candidates.append({
                "source": "personal_best",
                "comparator": ">=" if direction == "higher_better" else "<=",
                "value": best["value"], "unit": unit,
                "observed": {"date": best["date"], "n": len(series),
                             "from": series[0]["date"], "to": series[-1]["date"],
                             "span_months": span},
                # Deliberately not «what you should reach» — «where you have been».
                # Nobody recommended this number; the person's own body produced it.
                "why": _t("goalgen.why.personal_best", date=best["date"],
                          readings=_plural(len(series), "count.readings"),
                          months=span),
            })

        # --- the wall of the corridor ----------------------------------------
        lo, hi = spec.get("ref_low"), spec.get("ref_high")
        if direction == "lower_better" and hi is not None:
            candidates.append({"source": "reference", "comparator": "<", "value": hi,
                               "unit": unit, "why": _t("goalgen.why.reference")})
        elif direction == "higher_better" and lo is not None:
            candidates.append({"source": "reference", "comparator": ">=", "value": lo,
                               "unit": unit, "why": _t("goalgen.why.reference")})

        usable = [c for c in candidates if not c.get("no_target") and c.get("value") is not None]
        # A target the person already meets is not a goal. Saying «aim for ALT
        # under 33» to somebody at 19 spends their attention on a problem they do
        # not have, and a screen of such lines makes the two that matter invisible.
        # They are not thrown away — they go to `already_met`, which is a different
        # and true statement: there is nothing to reach here, only to hold.
        reachable = [c for c in usable
                     if not (now and _meets(now["value"], c["comparator"], c["value"]))]
        # A target written for people with a condition is not chosen on a condition
        # nobody confirmed. It stays visible as an alternative, and is offered as
        # THE proposal only where the profile can say the condition applies.
        auto = [c for c in reachable if not c.get("applies_when")]

        if not usable:
            skipped.append({"key": key, "name": name,
                            "reason": ("society_withdrew_the_target"
                                       if any(c.get("no_target") for c in candidates)
                                       else ("inside_the_corridor" if direction == "inside"
                                             else (pb_reason or "nothing_to_go_on"))),
                            "candidates": candidates})
            continue
        if not auto:
            already_met.append({"key": key, "name": name, "unit": unit, "now": now,
                                "met": [{"source": c["source"], "comparator": c["comparator"],
                                         "value": c["value"], "why": c.get("why")}
                                        for c in usable
                                        if now and _meets(now["value"], c["comparator"], c["value"])],
                                "candidates": candidates})
            continue

        order = {"guideline": 0, "personal_best": 1, "reference": 2}
        auto.sort(key=lambda c: order.get(c["source"], 9))
        chosen = auto[0]
        # Where a society looked at this marker and declined to set a target, that
        # refusal travels with whatever else is proposed. Otherwise the corridor
        # quietly supplies the number the society refused to write, and the reader
        # cannot tell the two apart.
        withdrawn = next((c for c in candidates if c.get("no_target")), None)
        proposals.append({
            "key": key, "name": name, "unit": unit, "direction": direction,
            "caveat": (" ".join(x for x in (withdrawn.get("why"), withdrawn.get("note")) if x)
                       if withdrawn else None),
            "now": now, "proposed": chosen["source"],
            "target": {"comparator": chosen["comparator"], "value": chosen["value"]},
            "candidates": candidates,
            "reached_before": bool(best and now and (
                best["value"] >= chosen["value"] if direction == "higher_better"
                else best["value"] <= chosen["value"])),
        })

    return {"status": "ok", "proposals": proposals, "skipped": skipped,
            "already_met": already_met, "count": len(proposals),
            "how_to_read": _t("goalgen.how_to_read"),
            "disclaimer": DISCLAIMER()}
