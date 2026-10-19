"""Shared, descriptive qualification of observations; no clinical thresholds."""
from __future__ import annotations

import math
from datetime import date
from typing import Any, TypeGuard

# Display policy, not a biological significance threshold. Stored in each result.
POLICY = "observed-change-v1"
MIN_COVERAGE = 0.7
MIN_OBSERVATIONS = 14
MEDIAN_METRICS = {"Steps", "StepsDaily", "IntensityMinutes", "IntensityMinutesDaily", "ActiveMinutes"}


def _number(value: Any) -> TypeGuard[float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def observation_day(value: Any) -> date | None:
    """A month is not a dated draw. Reject malformed and future dates upstream."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def comparable_observations(points: list[dict]) -> dict:
    """Retain every input, but qualify only exact, independent, comparable draws."""
    reasons = []
    days = [observation_day(p.get("date")) for p in points]
    if len(points) < 2:
        reasons.append("too_few_observations")
    if any(d is None for d in days):
        reasons.append("date_unknown")
    from .store import DATE_APPROXIMATE
    approximate_dates = sorted({str(p.get("date") or "") for p in points
                                if p.get("date_source") in DATE_APPROXIMATE})
    if approximate_dates:
        reasons.append("date_approximate")
    if len(set(days)) != len(days):
        reasons.append("same_day_draws")
    if any(p.get("censored") or p.get("comparator") not in (None, "", "=") for p in points):
        reasons.append("reporting_limit")
    if any(not _number(p.get("value")) for p in points):
        reasons.append("value_unknown")
    for key in ("method", "device", "unit"):
        values = {str(p[key]) for p in points if p.get(key)}
        if len(values) > 1:
            reasons.append(key + "_changed")
    return {"eligible": not reasons, "reasons": reasons, "policy": POLICY,
            "method_recorded": bool(points) and all(p.get("method") for p in points),
            "approximate_dates": approximate_dates}


def period_shift(points: list[dict], monthly: bool = False, window: int = 365) -> dict:
    """Describe a long-term direction, not clinical significance or causation.

    Each window needs four draws in two calendar halves, spanning at least
    half the window (15/45/180 days). Short-window changes remain forming.
    These are descriptive display criteria, not validated clinical cutoffs.
    For the annual window, use all dated points across at least six months. Separated half-year ranges
    support a sustained shift; overlapping ranges need concordant pairwise
    directions and a resistant median slope and remain a forming trend. These
    are explicit display criteria, not a significance test. Device monthly means
    never become independent daily observations.
    """
    from statistics import median
    if window not in (30, 90, 365):
        raise ValueError("window must be 30, 90 or 365")
    series = sorted(points, key=lambda p: str(p.get("date") or ""))
    dated = [{**p, "date": str(p.get("date") or "") +
              ("-01" if monthly and len(str(p.get("date") or "")) == 7 else "")}
             for p in series]
    qualification = comparable_observations(dated)
    minimum_span = {30: 15, 90: 45, 365: 180}[window]
    out = {"eligible": False, "comparison": qualification, "window": window,
           "minimum_span": minimum_span}
    if not qualification["eligible"] or len(series) < 4:
        return out
    days = [observation_day(p["date"]) for p in dated]
    if any(d is None for d in days):
        return out
    ordinals = [d.toordinal() for d in days if d is not None]
    if ordinals[-1] - ordinals[0] < minimum_span:
        return out
    midpoint = (ordinals[0] + ordinals[-1]) / 2
    early = [p for p, day in zip(series, ordinals) if day <= midpoint]
    late = [p for p, day in zip(series, ordinals) if day > midpoint]
    if min(len(early), len(late)) < 2:
        return out
    a, b = [p["value"] for p in early], [p["value"] for p in late]
    separated = max(a) < min(b) or max(b) < min(a)
    slopes = [(series[j]["value"] - series[i]["value"]) / (ordinals[j] - ordinals[i])
              for i in range(len(series)) for j in range(i + 1, len(series))]
    concordance = sum(1 if s > 0 else -1 if s < 0 else 0 for s in slopes) / len(slopes)
    slope = median(slopes)
    delta = median(b) - median(a)
    # A selected last extreme cannot supply most of the pairwise directions.
    forming = abs(concordance) >= 2 / 3 and slope * delta > 0
    if not separated and not forming:
        return {**out, "reason": "no_consistent_direction", "concordance": concordance}
    return {**out, "eligible": True, "stage": "sustained" if separated and window == 365 else "forming",
            "concordance": round(concordance, 3), "median_slope_per_year": slope * 365,
            "before": median(a), "after": median(b),
            "direction": "up" if median(b) > median(a) else "down",
            "from": series[0]["date"], "to": series[-1]["date"],
            "before_range": [min(a), max(a)], "after_range": [min(b), max(b)],
            "before_dates": [early[0]["date"], early[-1]["date"]],
            "after_dates": [late[0]["date"], late[-1]["date"]],
            "latest": {"date": series[-1]["date"], "value": series[-1]["value"]},
            "before_n": len(a), "after_n": len(b), "n": len(series),
            "statistic": "monthly_means" if monthly else "observations",
            "policy": "multi-window-direction-v3"}


def wearable_comparison(metric: str, before: dict, after: dict) -> dict:
    """Compare two non-overlapping monthly summaries from the same named source.

    Mean uncertainty uses the recorded sample SD, assuming independent days.
    Median comparisons require recorded order-statistic intervals; the SD of a
    mean is never lent to a median. Legacy summaries keep their numbers.
    """
    statistic = "median" if metric in MEDIAN_METRICS else "mean"
    reasons = []
    out: dict[str, Any] = {"policy": POLICY, "statistic": statistic,
                          "before": before, "after": after,
                          "coverage_min": MIN_COVERAGE, "n_min": MIN_OBSERVATIONS,
                          "eligible": False, "distinguishable": None,
                          "delta": None, "mdd": None,
                          "limitations": ["independent_days_assumed", "not_clinical_significance"]}
    if not before.get("source") or before.get("source") == "unspecified":
        reasons.append("source_unknown")
    if before.get("source") != after.get("source"):
        reasons.append("device_changed")
    if before.get("method") != after.get("method"):
        reasons.append("method_changed")
    try:
        a = date.fromisoformat(str(before["date"]) + "-01")
        b = date.fromisoformat(str(after["date"]) + "-01")
        if a >= b:
            reasons.append("overlapping_periods")
    except (ValueError, KeyError):
        reasons.append("date_unknown")
    vals: list[Any] = []
    for point in (before, after):
        st = point.get("stats") or {}
        n, days = st.get("n"), st.get("days")
        if (not _number(n) or not _number(days) or days <= 0 or n < MIN_OBSERVATIONS
                or n > days or n / days < MIN_COVERAGE):
            reasons.append("insufficient_coverage")
        if st.get("corrected"):
            reasons.append("corrected_summary")
        value = st.get("median") if statistic == "median" else point.get("value")
        vals.append(value)
        if not _number(value):
            reasons.append("value_unknown")
        if not _number(st.get("sd")) or st["sd"] <= 0:
            reasons.append("spread_unknown")
        if statistic == "median":
            ci = st.get("median_interval")
            if (not isinstance(ci, list) or len(ci) != 2 or not all(_number(v) for v in ci)
                    or ci[0] > ci[1] or not _number(value) or not ci[0] <= value <= ci[1]):
                reasons.append("median_uncertainty_unknown")
    if all(_number(v) for v in vals):
        out["delta"] = round(vals[1] - vals[0], 4)
    out["reasons"] = list(dict.fromkeys(reasons))
    if reasons:
        return out
    sa, sb = before["stats"], after["stats"]
    if statistic == "mean":
        floor = 1.96 * math.sqrt(sa["sd"] ** 2 / sa["n"] + sb["sd"] ** 2 / sb["n"])
        out.update(mdd=round(floor, 4), distinguishable=abs(out["delta"]) > floor)
    else:
        ca, cb = sa["median_interval"], sb["median_interval"]
        out["distinguishable"] = ca[1] < cb[0] or cb[1] < ca[0]
        out["limitations"].append("nonoverlapping_median_intervals")
    out["eligible"] = True
    return out


def reading_status(point: dict, today: date | None = None) -> str:
    """A dated, exact reading may be within its bounds without establishing a trend."""
    day = observation_day(point.get("date"))
    now = today or date.today()
    value, low, high = (point.get(k) for k in ("value", "ref_low", "ref_high"))
    if (day is None or not 0 <= (now-day).days <= 365 or not _number(value)
            or point.get("censored") or point.get("comparator") not in (None, "", "=")
            or point.get("reference_withheld") or point.get("proposed_rule")
            or not any(_number(v) for v in (low, high))
            or any(v is not None and not _number(v) for v in (low, high))
            or (low is not None and high is not None and low > high)):
        return "unknown"
    return "within" if (low is None or value >= low) and (high is None or value <= high) else "outside"
