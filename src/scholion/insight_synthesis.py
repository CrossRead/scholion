"""System-level descriptions of recorded changes, targets and treatment timing."""
from __future__ import annotations

from datetime import date, timedelta
from statistics import median

from . import core
from .i18n import t, lang
from .trend_qualification import comparable_observations, observation_day, _number


def _num(value: float) -> str:
    text = f"{value:.3g}"
    return text.replace(".", ",") if lang() == "ru" else text


def assess_direction(change: dict, row: dict, points: list[dict]) -> dict:
    """Closer to a recorded target/range is not a finding of clinical benefit."""
    target = row.get("clinician_target") or row.get("target") or {}
    basis = "target"
    if isinstance(target, dict) and any(_number(target.get(k)) for k in ("low", "high", "value")):
        if target.get("unit") and target["unit"] != row.get("unit"):
            return {"status": "unclassified", "basis": "unit_conflict"}
        low, high = target.get("low"), target.get("high")
        if _number(target.get("value")):
            low = high = target["value"]
    else:
        basis = "reference"
        bounds = {(p.get("ref_low", row.get("ref_low")), p.get("ref_high", row.get("ref_high"))) for p in points}
        if len(bounds) != 1 or row.get("reference_withheld"):
            return {"status": "unclassified", "basis": "reference_changed"}
        low, high = next(iter(bounds))
    if not any(_number(x) for x in (low, high)):
        return {"status": "unclassified", "basis": "no_target"}
    if (low is not None and not _number(low)) or (high is not None and not _number(high)) or (
            low is not None and high is not None and low > high):
        return {"status": "unclassified", "basis": "invalid_bounds"}
    def distance(value):
        return max(low - value if low is not None else 0, value - high if high is not None else 0, 0)
    a, b = distance(change["before"]), distance(change["after"])
    status = "toward" if b < a else "away" if b > a else "within" if b == 0 else "unchanged"
    latest = change.get("latest", {}).get("value")
    return {"status": status, "basis": basis, "low": low, "high": high,
            "latest_outside": _number(latest) and distance(latest) > 0,
            "latest_reversal": _number(latest) and status == "toward" and distance(latest) > b}


def _responses(system: str, events: list[dict]) -> list[dict]:
    """An explicit monitored marker can support a temporal comparison, not causation."""
    from .engine.system_panels import medication_system_context
    # Reuse the year's exact observations already present in the feed.
    series: dict[str, dict[str, dict]] = {}
    for e in events:
        for f in e["facts"]:
            if f.get("record") == "labs.json":
                series.setdefault(f["key"], {})[f["date"]] = f
    results = []
    mapped = [m for m in core.medications_json().get("medications") or []
              if core.is_active_medication(m) and system in medication_system_context(m)["systems"]]
    for med in mapped:
        start = observation_day(med.get("start_date"))
        plans = med.get("monitoring_schedule") or []
        keys: list[str] = [p["marker"] for p in plans if isinstance(p, dict) and isinstance(p.get("marker"), str)] if isinstance(plans, list) else []
        explicit = bool(keys)
        # An unambiguous system association is chronology, not a monitoring plan.
        if not explicit and len(mapped) == 1:
            domains = core._read_knowledge_raw("radar_domains.json").get("domains") or []
            keys = [key for d in domains if d["key"] == system for key in d.get("markers", []) if key in series]
        result = {"drug": med.get("name"), "start": med.get("start_date"), "current": True,
                  "status": "not_assessable", "comparisons": [], "causal": False,
                  "selection": "recorded_monitoring" if explicit else "system_context", "response_assessed": False,
                  "system_links": [x for x in medication_system_context(med)["system_links"] if x["system"] == system]}
        reason = "no_baseline" if keys else "no_marker"
        if not start:
            reason = "no_start"
        if start and start <= date.today():
            for key in keys:
                points = sorted(series.get(key, {}).values(), key=lambda p: p["date"])
                dated = [(p, observation_day(p["date"])) for p in points]
                before = [p for p, day in dated if day is not None and start - timedelta(days=365) <= day < start]
                after = [p for p, day in dated if day is not None and start < day <= date.today()]
                combined = before + after
                qualification = comparable_observations(combined)
                if "date_approximate" in qualification["reasons"]:
                    reason = "date_uncertain"
                if min(len(before), len(after)) < 2 or not qualification["eligible"]:
                    continue
                a, b = [p["value"] for p in before], [p["value"] for p in after]
                separated = max(a) < min(b) or max(b) < min(a)
                result["comparisons"].append({"marker": key, "before": median(a), "after": median(b),
                    "before_n": len(a), "after_n": len(b), "separated": separated,
                    "from": before[0]["date"], "to": after[-1]["date"], "facts": combined})
            if result["comparisons"]:
                result["status"] = "temporal_comparison"
                reason = "temporal_only" if explicit else "system_temporal_only"
        result["summary"] = t("insight.rx." + reason, drug=result["drug"])
        for comparison in result["comparisons"]:
            key = comparison["marker"]
            event = next((e for e in events if e["kind"] == "period_shift" and e["facts"][0].get("key") == key), None)
            assessment = ((event or {}).get("detail") or {}).get("assessment") or {}
            target = {"low": assessment.get("low"), "high": assessment.get("high")}
            row = {**comparison["facts"][0]}
            if assessment.get("basis") == "target":
                row["target"] = target
            direction = assess_direction(comparison, row, comparison["facts"])
            if not comparison["separated"]:
                direction = {"status": "unclassified", "basis": "overlapping_ranges"}
            comparison["assessment"] = direction
            comparison["summary"] = t("insight.rx_pair", name=(event or {}).get("name") or key,
                before=_num(comparison["before"]), after=_num(comparison["after"]),
                unit=row.get("unit_display") or row.get("unit") or "",
                meaning=t("insight.direction." + direction["status"], basis=t("insight.basis." + (
                    direction["basis"] if direction["basis"] in ("target", "reference") else "unknown"))))
            annual = (event or {}).get("detail") or {}
            if (annual.get("before"), annual.get("after")) != (comparison["before"], comparison["after"]):
                result["summary"] += " " + comparison["summary"]
        results.append(result)
    return results


def enrich_system(group: dict) -> None:
    """One conclusion and compact supporting findings, shared by all entry points."""
    changes = []
    for event in group["events"]:
        if event["kind"] != "period_shift":
            continue
        d = event["detail"]
        a = d.get("assessment") or {"status": "unclassified", "basis": "no_target"}
        basis = t("insight.basis." + (a["basis"] if a["basis"] in ("target", "reference") else "unknown"))
        status = a["status"]
        unit = event["facts"][0].get("unit_display") or event["facts"][0].get("unit") or ""
        line = t("insight.change_line", name=event["name"], before=_num(d["before"]),
                 after=_num(d["after"]), unit=unit, direction=t("insight.window_direction", window=t("insight.window." + str(d.get("window", 365))), direction=t("insight.arrow." + d["direction"])), meaning=t("insight.direction." + status, basis=basis))
        if status == "unclassified":
            line = t("insight.change_neutral", name=event["name"], before=_num(d["before"]),
                     after=_num(d["after"]), unit=unit, direction=t("insight.window_direction", window=t("insight.window." + str(d.get("window", 365))), direction=t("insight.arrow." + d["direction"]))).replace(" .", ".")
        if d.get("stage") == "forming":
            line = t("insight.forming_short" if d.get("window", 365) < 365 else "insight.forming") + " " + line
        if a.get("latest_outside"):
            line += " " + t("insight.latest_outside")
        if a.get("latest_reversal"):
            line += " " + t("insight.latest_reversal")
        changes.append({"marker": event["facts"][0]["key"], "name": event["name"], "status": status,
                        "basis": a, "summary": line, "comparison": d, "window": d.get("window", 365),
                        "series": [f for f in event["facts"] if f.get("value") is not None]})
    reported = sorted([e for e in group["events"] if e["kind"] == "reported_response"],
                      key=lambda e: e["date"], reverse=True)
    if not changes and not reported:
        return
    kinds = {c["status"] for c in changes}
    status = "mixed" if {"toward", "away"} <= kinds else "away" if "away" in kinds else "toward" if "toward" in kinds else "observed"
    if not changes:
        status = "reported"
    group["trajectory"] = {"status": status, "period": 365, "changes": changes,
                           "windows": [365, 90, 30], "reported_observations": [e["facts"][0] for e in reported]}
    group["title"] = group["name"] + ": " + t("insight.system." + status)
    group["detail_summaries"] = group["summaries"]
    changes.sort(key=lambda c: (-c["window"], c["status"] != "away", c["status"] != "toward", c["name"]))
    group["summaries"] = ([reported[0]["detail"]["summary"]] if reported else []) + [c["summary"] for c in changes]
    group["summaries"].extend(e["detail"]["summary"] for e in reported[1:])
    if reported and changes:
        reported_kinds = {e["detail"]["change"] for e in reported}
        if ("better" in reported_kinds and "away" in kinds) or ("worse" in reported_kinds and "toward" in kinds):
            group["summaries"].insert(0, t("response.divergent"))
    if status in ("toward", "away", "mixed"):
        group["priority"] = min(group["priority"], 2)
    else:
        group["priority"] = max(group["priority"], 3)
    responses = _responses(group["system"], group["events"]) if group.get("system") else []
    group["treatment_review"] = responses
    group["summaries"].extend(r["summary"] for r in responses if r["comparisons"])
    group["detail_summaries"].extend(r["summary"] for r in responses if not r["comparisons"])
    group["questions"] = ([t("insight.question." + status, system=group["name"])]
        if status in ("away", "mixed") or any(r["comparisons"] for r in responses) else [])
    if reported:
        group["questions"].insert(0, t("response.question", system=group["name"]))
