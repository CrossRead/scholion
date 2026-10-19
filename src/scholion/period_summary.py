"""Select dated observations for one shared summary without inventing daily data."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta

from .trend_qualification import comparable_observations, observation_day, _number


def period_summary(rows: list[dict], days: int, today: date | None = None) -> list[dict]:
    now = today or date.today()
    start = (now - timedelta(days=days)).isoformat()
    result = deepcopy(rows)
    for row in result:
        for original in row.get("components") or []:
            for c in (original, original.get("device_history")):
                if not c:
                    continue
                series = c.get("series") or (c.get("period") or {}).get("series") or []
                selected = [p for p in series if (observation_day(str(p.get("date") or "") + ("-01" if len(str(p.get("date") or "")) == 7 else "")) is not None)
                            and _number(p.get("value")) and str(p.get("date") or "") >= start[:len(str(p.get("date") or ""))]
                            and str(p.get("date") or "") <= now.isoformat()]
                selected.sort(key=lambda p: p["date"])
                from .measurements import streams, current
                groups = streams(selected)
                latest = current(selected)
                # Arithmetic follows the current source and aggregation; all
                # observations remain on the common display timeline.
                compared = next((g for g in groups if latest in g), [])
                monthly = bool(compared) and (c.get("aggregation") == "monthly_mean" or all(p.get("aggregation") == "monthly_mean" for p in compared)) and all(len(str(p.get("date") or "")) == 7 for p in compared)
                comparison = comparable_observations(compared) if not monthly else {
                    "eligible": False, "reasons": ["period_means_not_individual_measurements"]}
                delta = None
                if len(compared) > 1 and (monthly or comparison["eligible"]):
                    if not any(p.get("censored") for p in compared):
                        delta = round(compared[-1]["value"] - compared[0]["value"], 3)
                c["period"] = {"days": days, "series": selected, "delta": delta,
                    "from": compared[0]["date"] if compared else None,
                    "to": compared[-1]["date"] if compared else None,
                    "comparison_series": compared, "comparison_source": latest.get("measurement_source") if latest else None,
                    "statistic": "mean" if monthly else "observation", "comparison": comparison}
    return result
