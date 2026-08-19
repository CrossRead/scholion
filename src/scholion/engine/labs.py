"""Laboratory series: flags, trends, decision limits, suggested tests.

The empty state distinguishes "measured and clean" from "nothing measured";
a reference bound travels through the same unit gateway as the value it bounds.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from .. import core
from ..i18n import t as _t
from ._helpers import _OPS, _recent, _active_names_by_class, DISCLAIMER


# ==========================================================================
# 2. Analysis of the lab results: flags + trends
# ==========================================================================
def _latest(series: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return sorted(series, key=lambda p: p["date"])[-1] if series else None


def _flag_value(m: Dict[str, Any], value: float, censored: Optional[str] = None) -> str:
    """Flag of a marker relative to the reference interval.

    censored — the sign from the lab form when a bound is printed instead of a number ("<" / ">").
    The value is stored at the bound, so an ordinary comparison lies exactly at the edge: a result of
    "less than 10^5" with a lower bound of 10^5 is strictly BELOW the reference, although
    value == ref_low. Likewise "more than 10^8" with an upper bound of 10^8 is strictly above.
    """
    lo, hi = m.get("ref_low"), m.get("ref_high")
    if censored == "<" and lo is not None and value <= lo:
        return "low"
    if censored == ">" and hi is not None and value >= hi:
        return "high"
    if hi is not None and value > hi:
        return "high"
    if lo is not None and value < lo:
        return "low"
    if lo is None and hi is None:
        # No corridor at all — and «ok» here would be a claim, not an absence of
        # one. A green tick beside a number nobody has anything to compare with
        # reads as «this is fine», which is exactly what cannot be said; the very
        # first marker a new user enters by hand has no bounds, so this is the
        # first screen of every person who starts without a lab form.
        return "norange"
    return "ok"


MOVE_MIN_PCT = 10.0          # below this, a shift from the personal baseline is treated as noise


MOVE_MIN_SD = 1.5            # or this many personal standard deviations


def _personal_move(series: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Shift of the last point relative to the marker's OWN history.

    Why: the position inside the reference corridor is nearly uninterpretable for an individual
    person. The corridor is the central 95 % of a healthy population, so any healthy person lands
    in the outer 10–13 % of its width in about 5 % of cases at each edge by construction alone.
    For most analytes the index of individuality is below 0.6, that is, the population interval
    senses the changes of a particular person poorly, and what has to be watched is the deviation
    from that person's own level.

    A shift counts as significant when it exceeds BOTH 10 % of the personal baseline AND one and
    a half personal standard deviations (when there is enough history to estimate the scatter)."""
    if not series or len(series) < 2:
        return None
    s = sorted(series, key=lambda p: p["date"])
    prior = [p["value"] for p in s[:-1] if isinstance(p.get("value"), (int, float))]
    v = s[-1].get("value")
    if not prior or not isinstance(v, (int, float)):
        return None
    prior_sorted = sorted(prior)
    n = len(prior_sorted)
    base = (prior_sorted[n // 2] if n % 2 else (prior_sorted[n // 2 - 1] + prior_sorted[n // 2]) / 2)
    if base == 0:
        return None
    delta_pct = (v - base) / abs(base) * 100
    sd = None
    if n >= 3:
        mean = sum(prior) / n
        sd = (sum((x - mean) ** 2 for x in prior) / (n - 1)) ** 0.5
    sig = abs(delta_pct) >= MOVE_MIN_PCT
    if sd is not None and sd > 0:
        sig = sig and abs(v - base) >= MOVE_MIN_SD * sd
    return {"baseline": round(base, 4), "points": n, "delta_pct": round(delta_pct, 1),
            "significant": bool(sig), "direction": "up" if v > base else ("down" if v < base else "flat")}


def _decision_limits(key: str, value: float, active_classes: Optional[set] = None) -> List[Dict[str, Any]]:
    """Clinical action thresholds for a marker: which are crossed and which are not.

    This is a DIFFERENT object from the reference interval: a threshold is derived from
    outcomes, not from the distribution of the healthy. It can lie inside the lab corridor
    (prediabetes at HbA1c 5.7 with a reference up to 6.0) or far outside it (haematocrit 54 %
    on testosterone therapy with a lab ceiling of 49.0)."""
    out = []
    for t in core.clinical_thresholds().get("markers", {}).get(key, []):
        need = t.get("applies_when_class")
        if need and (active_classes is None or need not in active_classes):
            continue
        try:
            crossed = value >= t["value"] if t.get("side") == "high" else value <= t["value"]
        except Exception:
            continue
        out.append({**t, "crossed": bool(crossed),
                    "distance_pct": round((value - t["value"]) / abs(t["value"]) * 100, 1) if t["value"] else None})
    # order: the crossed ones first; among those not crossed — the ones tied to an active
    # drug class (for haematocrit on testosterone therapy the relevant threshold is 54, not
    # the general therapy-start threshold of 50), then the nearest by value
    out.sort(key=lambda x: (not x["crossed"], not x.get("applies_when_class"), x.get("value", 0)))
    return out


NEAR_LIMIT_FRACTION = 0.10   # "at the edge" = the last 10 % before the corridor bound


def _near_limit(m: Dict[str, Any], value: float, flag: str,
                censored: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """A marker formally within range, but pressed against the edge of the corridor.

    The threshold is 10 % of the bound value (21.8 against a ceiling of 22.0 → 99 % of the corridor
    and "at the edge"; 98.3 against a ceiling of 106 → 93 % and also "at the edge"). For NARROW
    corridors, where 10 % of the bound would cover half the reference range or more (sodium 130–140,
    say), the zone narrows to half the corridor width — otherwise the whole range would be "at the edge".

    The second condition, when the corridor is two-sided: the value has to lie in the outer quarter of
    the corridor. Without it, "at the edge" would be given to, for instance, HbA1c 5.4 with a reference
    of 4.0–6.0 — that is 10 % off the ceiling, but only 70 % of the corridor width, the middle of the
    range and not its edge.

    Returns None if the marker is already out of range (the ordinary flag works there), if the bound is
    absent or non-positive, and for CENSORED results ("< 1:10", "less than 10^4"): there the value is
    stored at the bound itself, and "0 % to the bound" means a negative result, not an approach to it.

    A value that EXACTLY coincides with the bound does not count as "at the edge" either: almost always it
    is the limit of detection of the method (a hormone at 0.09 with a lower bound of 0.09; lithium at 0.001
    with a bound of 0.001) or a step of a coarse scale (log10 CFU with a corridor of 7.0–8.0, stool-analysis
    scores), and not a marker pressed against the ceiling by the measurement."""
    if flag not in ("ok", "norange") or value is None or censored:
        return None
    lo, hi = m.get("ref_low"), m.get("ref_high")
    width = (hi - lo) if (lo is not None and hi is not None and hi > lo) else None
    outer = 0.25   # what share of the corridor at the edge counts as "the edge"
    try:
        if hi is not None and hi > 0:
            thr = hi * (1 - NEAR_LIMIT_FRACTION)
            if width is not None:
                thr = max(thr, hi - width / 2, hi - width * outer)
            if value >= thr and value < hi:
                return {"side": "high", "bound": hi,
                        "margin_pct": round((hi - value) / hi * 100, 1),
                        "corridor_pct": round((value - lo) / width * 100, 1) if width else None}
        if lo is not None and lo > 0:
            thr = lo * (1 + NEAR_LIMIT_FRACTION)
            if width is not None:
                thr = min(thr, lo + width / 2, lo + width * outer)
            if value <= thr and value > lo:
                return {"side": "low", "bound": lo,
                        "margin_pct": round((value - lo) / lo * 100, 1),
                        "corridor_pct": round((value - lo) / width * 100, 1) if width else None}
    except Exception:
        return None
    return None


def _trend(series: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if len(series) < 2:
        return None
    s = sorted(series, key=lambda p: p["date"])
    prev, last = s[-2], s[-1]
    delta = round(last["value"] - prev["value"], 3)
    direction = "up" if delta > 0 else ("down" if delta < 0 else "flat")
    pct = round(100.0 * delta / prev["value"], 1) if prev["value"] else None
    return {"from_date": prev["date"], "to_date": last["date"], "delta": delta,
            "direction": direction, "pct": pct}


def analyze_labs(markers: Optional[List[str]] = None) -> Dict[str, Any]:
    data = core.labs().get("markers", {})
    keys = markers or list(data.keys())
    try:
        active_classes = set(_active_names_by_class().keys())
    except Exception:
        active_classes = set()
    results = []
    for k in keys:
        m = data.get(k)
        if not m or not m.get("series"):
            continue
        latest = _latest(m["series"])
        flag = _flag_value(m, latest["value"], latest.get("censored"))
        # for "higher_better" (HDL, testosterone, vitamin D, omega-3) the low flag = worse
        direction_pref = m.get("direction")
        # «norange» is not an abnormality — it is the absence of anything to
        # compare against. Counting it as one turns a first screen with two
        # hand-entered numbers into «2 values out of range», which is alarming and
        # false, and the person has no way to tell which of the two it means.
        abnormal = flag not in ("ok", "norange")
        results.append({
            "key": k, "name": m["name"], "unit": m.get("unit", ""),
            "value": latest["value"], "date": latest["date"],
            "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high"),
            "flag": flag, "abnormal": abnormal, "direction_pref": direction_pref,
            "near_limit": None,   # set below, after the personal shift has been assessed
            "personal_move": None,
            "decisions": _decision_limits(k, latest["value"], active_classes),
            "trend": _trend(m["series"]),
            "series": sorted(m["series"], key=lambda p: p["date"]),
            "genome_link": m.get("genome_link"), "note": m.get("note"),
        })
    # "At the edge" is set only if the marker is MOVING towards that bound relative to its
    # own history. Otherwise the flag catches markers that have stood there all their life:
    # without this condition it fired on markers that were flat or even moving away from the
    # bound — attention without information.
    for r in results:
        raw = data.get(r["key"], {})
        latest_v, cens = r["value"], None
        for p in raw.get("series", []):
            if p.get("date") == r["date"]:
                cens = p.get("censored")
        nl = _near_limit(raw, latest_v, r["flag"], cens)
        if not nl:
            continue
        mv = _personal_move(raw.get("series", []))
        r["personal_move"] = mv
        if mv is None:                       # no history — nothing to judge by, it is kept
            nl["movement"] = _t("near.no_history")
        elif mv["significant"] and ((nl["side"] == "high" and mv["direction"] == "up") or
                                    (nl["side"] == "low" and mv["direction"] == "down")):
            nl["movement"] = _t("near.moved_from_baseline", delta=f"{mv['delta_pct']:+g}",
                                baseline=f"{mv['baseline']:g}")
        else:
            continue                         # stands at the edge but goes nowhere — not flagged
        r["near_limit"] = nl

    # sorting: the abnormal first, then by name
    results.sort(key=lambda r: (not r["abnormal"], r["name"]))
    abnormal = [r for r in results if r["abnormal"]]
    near = [r for r in results if r.get("near_limit")]
    crossed = [r for r in results if any(d["crossed"] for d in r.get("decisions", []))]
    return {"status": "ok", "count": len(results), "abnormal_count": len(abnormal),
            "near_limit_count": len(near), "decision_crossed_count": len(crossed),
            "markers": results, "disclaimer": DISCLAIMER()}


# ==========================================================================
# 3. Suggestion of additional lab tests (rules)
# ==========================================================================
def _latest_value(marker_key: str) -> Optional[float]:
    m = core.labs().get("markers", {}).get(marker_key)
    if not m or not m.get("series"):
        return None
    return _latest(m["series"])["value"]


def _eval_condition(cond: Dict[str, Any]) -> bool:
    if "all" in cond:
        return all(_eval_condition(c) for c in cond["all"])
    if "any" in cond:
        return any(_eval_condition(c) for c in cond["any"])
    if "marker" in cond and "op" in cond:
        val = _latest_value(cond["marker"])
        if val is None:
            return False
        return _OPS[cond["op"]](val, cond["value"])
    if "trend" in cond:
        m = core.labs().get("markers", {}).get(cond["trend"]["marker"])
        t = _trend(m["series"]) if m and m.get("series") else None
        return bool(t and t["direction"] == cond["trend"]["direction"])
    if "med_contains" in cond:
        q = cond["med_contains"].lower()
        return any(q in mn for mn in core.medication_names())
    if "med_class" in cond:
        return cond["med_class"] in core.active_med_classes()
    if "genome_gap" in cond:
        return cond["genome_gap"] in core.genome_gaps()
    return False


_PRIORITY_ORDER = {"high": 0, "moderate": 1, "low": 2}


def _marker_last_date(keys) -> Optional[str]:
    """The most recent measurement date among the given markers (or None)."""
    mk = core.labs().get("markers", {})
    ds = []
    for k in keys or []:
        m = mk.get(k)
        if m and m.get("series"):
            try:
                ds.append(max(p["date"] for p in m["series"] if p.get("date")))
            except Exception:
                pass
    return max(ds) if ds else None


def suggest_tests() -> Dict[str, Any]:
    """What else to take. A rule with a ``covers`` field (the markers it monitors) is marked
    ``done_recently`` if all of them were measured within the last ``recheck_months``
    (3 by default) — then it is not an extra order but routine monitoring: it goes down the list."""
    triggered = []
    for rule in core.test_rules().get("rules", []):
        try:
            if _eval_condition(rule["when"]):
                item = {k: rule[k] for k in ("id", "suggest", "why", "priority", "specialist") if k in rule}
                covers = rule.get("covers")
                if covers:
                    ld = _marker_last_date(covers)
                    if ld and _recent(ld, rule.get("recheck_months", 3)):
                        item["done_recently"] = True
                        item["last_measured"] = ld
                        item["recheck_months"] = rule.get("recheck_months", 3)
                triggered.append(item)
        except Exception as e:  # a rule must not take the whole tool down
            triggered.append({"id": rule.get("id", "?"), "error": str(e)})
    # recently done monitoring goes to the end; inside the groups — by priority
    triggered.sort(key=lambda r: (bool(r.get("done_recently")),
                                  _PRIORITY_ORDER.get(r.get("priority", "low"), 3)))
    pending = [r for r in triggered if not r.get("done_recently")]
    return {"status": "ok", "count": len(pending), "total": len(triggered),
            "suggestions": triggered, "disclaimer": DISCLAIMER()}
