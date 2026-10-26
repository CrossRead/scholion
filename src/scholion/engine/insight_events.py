"""Identify events from existing calculators; no ranking, persistence or rendering."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from .. import core
from .treatment import _treatment_medications
from ..i18n import t
from ..knowledge_provenance import digest as _digest
from ..trend_qualification import comparable_observations, observation_day
from .labs import _flag_value, _trend
from .corridor import point_corridor


def _fact_identity(fact: dict) -> dict:
    """Translation is presentation, not an observation or a change in evidence."""
    identity = {k: fact.get(k) for k in ("record", "key", "date", "value", "censored", "comparator",
        "source", "date_source", "method", "unit", "stats", "drug", "rsid", "genotype", "state",
        "genotype_source", "gene", "recorded_reference", "ref_low", "ref_high", "ref_origin", "reference_withheld", "marker", "from", "due", "plan_source", "dose", "target",
        "system", "aspect", "change", "note", "during_recorded_course", "pgs_id", "percentile", "reference_panel_ancestry", "computed", "class", "end_date", "current",
        "source_record", "ingest_method", "sample_id", "draw_id", "variants", "diplotype") if k in fact}
    observed_genotype=identity.get("genotype")
    if isinstance(observed_genotype, dict):
        identity["genotype"] = {k: v for k, v in observed_genotype.items()
                                if k not in ("note", "message", "why_label", "source_label", "unit_display")}
    return identity


def _event(kind: str, key: str, name: str, facts: list[dict], *, priority: int = 3,
           destination: str = "labs", rule: Any = None, detail: Any = None) -> dict:
    from ..knowledge_provenance import sources
    return {"id": kind + ":" + key, "kind": kind, "key": key,
            "title": t("insight.kind." + kind, name=name), "name": name,
            "date": max((str(p.get("date") or "") for p in facts), default=""),
            "priority": priority, "destination": destination, "facts": facts,
            "detail": detail, "rule": {"id": kind, "version": "1", "digest": _digest(rule),
                                       "sources": sources(rule)},
            "facts_digest": _digest([_fact_identity(f) for f in facts]), "limitations": [], "level": None}


def _fact(key: str, point: dict, row: dict) -> dict:
    return {"record": "labs.json", "key": key, **{k: point.get(k) for k in (
        "date", "value", "censored", "comparator", "source", "date_source", "method")},
        **{k: point[k] for k in ("source_record", "ingest_method", "sample_id", "draw_id") if k in point},
        "unit": row.get("unit"), "unit_display": row.get("unit_display"),
        "ref_low": point.get("ref_low", row.get("ref_low")),
        "ref_high": point.get("ref_high", row.get("ref_high")),
        "ref_origin": "form" if any(point.get(k) is not None for k in ("ref_low", "ref_high")) else row.get("ref_origin"),
        "reference_withheld": point.get("reference_withheld", row.get("reference_withheld")),
        "recorded_reference": {k: point[k] for k in ("ref_low", "ref_high") if k in point}}


def _current(point: dict, today: date, days: int = 365) -> bool:
    day: date | None
    stamp = point.get("date")
    if isinstance(stamp, str) and len(stamp) == 7:
        try:
            day = date.fromisoformat(stamp + "-01")
        except ValueError:
            return False
    else:
        day = observation_day(stamp)
    return day is not None and 0 <= (today - day).days <= days


def _lab_events(rows: list[dict], today: date) -> list[dict]:
    events = []
    for row in rows:
        key = row["key"]
        points = sorted(row.get("series") or [], key=lambda p: str(p.get("date") or ""))
        if not points or not _current(points[-1], today) or row.get("proposed_rule"):
            continue
        current = points[-1]
        fact = _fact(key, current, row)
        decisions = [d for d in row.get("decisions") or [] if d.get("crossed") is True]
        for d in decisions:
            events.append(_event("clinical_threshold", key + ":" + _digest(d.get("value"))[:8],
                                 row["name"], [fact], priority=0, rule=d, detail=d))
        abnormal = row.get("abnormal") and row.get("flag") in ("high", "low")
        kind, used, detail = "abnormal", [fact], {"flag": row.get("flag"),
            "ref_low": row.get("ref_low"), "ref_high": row.get("ref_high")}
        if len(points) >= 2:
            pair = points[-2:]
            qualifies = comparable_observations(pair)
            if (abnormal and qualifies["eligible"] and _current(pair[0], today)
                    and row.get("flags_comparable") is not False):
                previous = pair[0]
                corridor = point_corridor(key, row, previous)
                previous_flag = _flag_value({**row, **corridor}, previous["value"])
                if previous_flag == row["flag"]:
                    kind = "repeated_abnormal"
                    used = [_fact(key, p, row) for p in pair]
                    detail["comparison"] = qualifies
        if abnormal:
            events.append(_event(kind, key, row["name"], used, priority=2, detail=detail,
                                 rule={k: row.get(k) for k in ("ref_low", "ref_high", "flag")}))
        qualification = comparable_observations(points)
        trend = _trend(points) if qualification["eligible"] else None
        if trend and trend.get("distinguishable") is True:
            e = _event("lab_change", key, row["name"], [_fact(key, p, row) for p in points],
                       detail={"trend": trend, "comparison": qualification}, rule="own-history-change-v1")
            e["limitations"] = ["own_history_variation", "not_clinical_significance"]
            events.append(e)
        target = row.get("clinician_target") or row.get("target")
        if trend and isinstance(target, dict):
            low, high, value = target.get("low"), target.get("high"), target.get("value")
            if any(isinstance(v, (int, float)) for v in (low, high, value)):
                def distance(v):
                    if value is not None:
                        return abs(v - value)
                    return max((low - v) if low is not None else 0,
                               (v - high) if high is not None else 0, 0)
                delta = distance(points[-1]["value"]) - distance(points[-2]["value"])
                if delta and trend.get("distinguishable") is True:
                    target_identity = {k: target.get(k) for k in
                                       ("low", "high", "value", "unit", "set_by", "set_on")}
                    events.append(_event("goal_toward" if delta < 0 else "goal_away", key,
                        row["name"], [_fact(key, p, row) for p in points[-2:]] +
                        [{"record": "clinician_targets.json", "key": key, "target": target_identity}],
                        detail={"target": target, "comparison": trend}, rule="explicit-target-distance-v1"))
    return events


def insight_events(labs: dict, cautions: list[dict], controls: list[dict],
                   wearable: dict, suggestions: list[dict], today: date | None = None) -> list[dict]:
    """Reuse clinical decisions unchanged. New changes remain descriptive facts."""
    now = today or date.today()
    events = _lab_events(labs.get("markers") or [], now)
    caution_rules = core._read_knowledge_raw("class_genotype_cautions.json").get("cautions") or []
    for row in cautions:
        if row.get("interpretation_withheld"):
            continue
        e = _event("prescription_genotype", str(row.get("drug")) + ":" + str(row.get("rsid")),
                   str(row.get("drug") or ""), [{"record": "medications.json",
                       **{k: row.get(k) for k in ("drug", "class", "gene", "rsid", "genotype", "state", "genotype_source")}}],
                   priority=0, destination="medications", rule=[r for r in caution_rules
                       if r.get("class") == row.get("class") and r.get("rsid") == row.get("rsid")], detail=row)
        e["level"] = row.get("level")
        events.append(e)
    for row in controls:
        events.append(_event("overdue_control", str(row.get("name")) + ":" + str(row.get("marker")) + ":" + str(row.get("from")),
            core.marker_name({"key": row.get("marker"), "name": row.get("marker")}),
            [{"record": "medications.json", "date": row.get("due"), **row}],
            priority=1, destination="medications", rule=row.get("plan_source"), detail=row))
    for row in wearable.get("metrics") or []:
        comparison = row.get("comparison") or {}
        if (not row.get("counts_toward_conclusions", True) or not comparison.get("eligible")
                or comparison.get("distinguishable") is not True):
            continue
        try:
            end = date.fromisoformat(str(row["date"]) + "-01")
        except (KeyError, ValueError):
            continue
        if not 0 <= (now - end).days <= 62:
            continue
        e = _event("wearable_change", str(row["source"]) + ":" + row["key"], row["label"],
            [{"record": "wearable_trends.json", "key": row["key"], **comparison[k]}
             for k in ("before", "after")], destination="lifestyle", detail=comparison,
            rule={"policy": comparison.get("policy"), "statistic": comparison.get("statistic")})
        e["limitations"] = comparison.get("limitations", [])
        events.append(e)
    for row in suggestions:
        if (row.get("done_recently") or not row.get("suggest")
                or row.get("proposal_status") != "held" or row.get("error")):
            continue
        rule = next((r for r in core._read_knowledge_raw("test_rules.json").get("rules", [])
                     if r.get("id") == row.get("id")), None)
        events.append(_event("planned_test", str(row.get("id") or _digest(row.get("markers"))[:16]),
            row["suggest"], [{"record": "suggest-tests", "source": row.get("source")}],
            priority=4, destination="second_opinion", rule=rule, detail=row))
    return events


def _annual_events(summary: list[dict], labs: dict, window: int = 365) -> list[dict]:
    """Longitudinal observations for the person's existing phenotype summary."""
    from ..trend_qualification import period_shift
    from ..period_summary import period_summary
    rows = {r["key"]: r for r in labs.get("markers") or []}
    # Phenotype is only a compact display selection, not the scope of analysis.
    supplied = {c.get("ref") for row in summary for c in row.get("components") or []}
    extra = [{"label": r.get("name") or core.marker_name({"key": key}), "components": [{"ref": "lab:" + key,
              "series": r.get("series") or [], "aggregation": "observation"}]}
             for key, r in rows.items() if "lab:" + key not in supplied]
    summary = period_summary(summary + extra, window)
    events = []
    seen = set()
    for row in summary:
        for component in row.get("components") or []:
            ref = component.get("ref") or ""
            if not ref or ref in seen or component.get("missing"):
                continue
            seen.add(ref)
            key = ref.partition(":")[2]
            lab = rows.get(key) if ref.startswith("lab:") else None
            if ref.startswith("lab:") and (not lab or lab.get("proposed_rule")):
                continue
            period = component.get("period") or {}
            points = period.get("series" if lab else "comparison_series") or []
            from ..measurements import streams
            candidates = [(group, period_shift(group, component.get("aggregation") == "monthly_mean" or all(p.get("aggregation") == "monthly_mean" for p in group), window))
                          for group in streams(points)]
            eligible = [(group, result) for group, result in candidates if result["eligible"]]
            if not eligible:
                continue
            points, shift = max(eligible, key=lambda pair: str(pair[1].get("to") or ""))
            shift["measurement_source"] = points[-1].get("measurement_source")
            facts = ([_fact(key, p, lab) for p in points] if lab else
                     [{"record": component.get("series_record") or ("wearable_trends.json" if ref.startswith("wear:") else "metrics.json"),
                       "key": key, "unit": component.get("unit"), "unit_display": component.get("unit_display"), **p,
                       "source": p.get("measurement_source") or p.get("source") or component.get("series_source") or component.get("source")}
                      for p in points])
            name = (lab.get("name") or core.marker_name({"key": key})) if lab else row["label"]
            event = _event("period_shift", ref if window == 365 else ref + ":" + str(window), name, facts, priority=2,
                           destination="labs" if lab else "lifestyle", rule=shift["policy"], detail=shift)
            if lab:
                from ..insight_synthesis import assess_direction
                event["detail"]["assessment"] = assess_direction(shift, lab, points)
                context = _treatment_context(key, shift["from"], shift["to"])
                event["detail"]["treatment_context"] = context
                event["facts"].extend(context)
                event["facts_digest"] = _digest([_fact_identity(f) for f in event["facts"]])
            event["limitations"] = ["descriptive_periods", "not_clinical_significance"]
            events.append(event)
    return events


def _treatment_context(marker: str, start: str, end: str) -> list[dict]:
    """Recorded treatment chronology in the same system, without attribution."""
    domains = core._read_knowledge_raw("radar_domains.json").get("domains") or []
    systems = {d["key"] for d in domains if marker in d.get("markers", [])}
    context = []
    for row in _treatment_medications():
        med = row['medication']
        if not systems.intersection(row['systems']):
            continue
        begin = str(med.get("start_date") or "")
        stop = str(med.get("end_date") or "")
        matched = re.fullmatch(r"(?:stopped|completed|discontinued)_(\d{4}-\d{2}(?:-\d{2})?)", str(med.get("status") or ""))
        if not stop and matched:
            stop = matched.group(1)
        current = core.is_active_medication(med)
        if any(stamp and observation_day(stamp + ("-01" if len(stamp) == 7 else "")) is None
               for stamp in (begin, stop)):
            continue
        if stop and stop < begin[:len(stop)]:
            continue
        if not begin or begin > end or (stop and stop < start[:len(stop)]):
            continue
        if not current and not stop:
            continue
        context.append({"record": "medications.json", "drug": med.get("name"),
                        "date": begin, "end_date": stop or None, "current": current,
                        "state": med.get("status"), "source": "medications.json"})
    return context
