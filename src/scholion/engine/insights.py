"""One attention feed: shared event identities, reasons and navigation."""
from __future__ import annotations

from datetime import date
from typing import Any

from .. import core
from ..i18n import t, lang
from .insight_events import insight_events, _annual_events, _digest, _fact_identity, _fact


@core.in_reading
def attention_feed(labs: dict, cautions: list[dict], controls: list[dict],
                   wearable: dict, suggestions: list[dict], period: int = 365) -> dict:
    """Collapse only events about the same lab observation; retain all reasons."""
    if period not in (30, 90, 365):
        raise ValueError("period must be 30, 90 or 365")
    from .goals import goal_dashboard
    from ..period_summary import period_summary
    phenotype = goal_dashboard().get("phenotype") or []
    summary = period_summary(phenotype, period)
    annual = summary if period == 365 else period_summary(phenotype, 365)
    events = insight_events(labs, cautions, controls, wearable, suggestions)
    for window in (365, 90, 30):
        events.extend(_annual_events(annual, labs, window))
    from .insight_links import linked_pgs_events
    events.extend(linked_pgs_events(labs))
    from ..reported_response import events as reported_events
    events.extend(reported_events())
    groups: dict[str, dict[str, Any]] = {}
    for event in events:
        lab = event["kind"] in ("clinical_threshold", "abnormal", "repeated_abnormal", "lab_change",
                                "goal_toward", "goal_away", "pgs_phenotype") or (
                                    event["kind"] == "period_shift" and event["facts"][0]["record"] == "labs.json")
        identity = "lab:" + event["facts"][0]["key"] if lab else event["id"]
        if identity not in groups:
            groups[identity] = {"id": identity, "name": event["name"], "events": [], "facts": [],
                                "priority": event["priority"], "destination": event["destination"],
                                "date": event["date"], "level": event["level"]}
        group = groups[identity]
        group["events"].append(event)
        group["priority"] = min(group["priority"], event["priority"])
        group["date"] = max(group["date"], event["date"])
        for fact in event["facts"]:
            if fact not in group["facts"]:
                group["facts"].append(fact)
    items = list(groups.values())
    marker_rules = core._read_knowledge_raw("lab_markers.json").get("markers") or {}
    thresholds = core._read_knowledge_raw("clinical_thresholds.json").get("markers") or {}
    links = core._read_knowledge_raw("insight_links.json").get("links") or []
    from ..insight_context import prepare_context, attach_context
    context = prepare_context(items, labs, wearable, phenotype)
    for item in items:
        item["events"].sort(key=lambda e: (e["priority"], e["kind"] in ("abnormal", "repeated_abnormal"), e["id"]))
        item["title"] = item["events"][0]["title"]
        item["reason"] = t("insight.priority." + str(item["priority"]))
        # A merged laboratory card retains the confidence of its genetic reason.
        levels = sorted({e["level"] for e in item["events"] if e.get("level")})
        item["levels"] = levels
        item["level"] = levels[-1] if levels else None
        rule_identity = [e["rule"] for e in item["events"]]
        if item["id"].startswith("lab:"):
            key = item["id"][4:]
            rule_identity = ["lab-attention-v5", marker_rules.get(key), thresholds.get(key),
                             [link for link in links if link.get("marker") == key],
                             [e["rule"] for e in item["events"] if e["kind"] == "genetic_phenotype"]]
        item["provenance"] = {"facts_digest": _digest([_fact_identity(f) for f in item["facts"]]),
                              "rules_digest": _digest(rule_identity),
                              "rules": [e["rule"] for e in item["events"]]}
    items.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    items.sort(key=lambda r: r["priority"])
    visible = max(5, sum(i["priority"] == 0 for i in items))
    states = {"lab:" + r["key"]: {"flag": r.get("flag"), "date": r.get("date"),
              "current": r.get("display_recency"), "proposed": r.get("proposed_rule"),
              "unit": r.get("unit"), "ref_low": r.get("ref_low"), "ref_high": r.get("ref_high"),
              "method": (sorted(r.get("series") or [], key=lambda p: str(p.get("date") or ""))[-1:]
                         or [{}])[0].get("method"),
              "data_digest": _digest([_fact_identity(_fact(r["key"], p, r)) for p in r.get("series") or []]),
              "rules_digest": _digest([marker_rules.get(r["key"]), thresholds.get(r["key"])]),
              "value": r.get("value")} for r in labs.get("markers") or []}
    synthesized = _highlights(items)
    attach_context(synthesized, context)
    highlights = [i for i in synthesized if any(e["kind"] != "repeated_abnormal" for e in i["events"])]
    follow_up = [i for i in synthesized if all(e["kind"] == "repeated_abnormal" for e in i["events"])]
    return {"items": items, "count": len(items), "visible_count": min(visible, len(items)),
            "highlights": highlights, "highlight_count": len(highlights),
            "follow_up": follow_up,
            "observation_count": sum(all(e["kind"] == "abnormal" for e in i["events"]) for i in items),
            "period": period, "summary": summary, "as_of": date.today().isoformat(), "states": states,
            "title": t("insight.title"), "empty": t("insight.empty"),
            "policy": "attention-v5", "profile": core.profile_is_synthetic()}


def _highlights(items: list[dict]) -> list[dict]:
    """Synthesize related longitudinal evidence; keep raw readings in items."""
    domains = core._read_knowledge_raw("radar_domains.json").get("domains") or []
    membership: dict[str, str] = {}
    for domain in domains:
        for key in (domain.get("markers") or []) + (domain.get("panel_markers") or []):
            membership.setdefault(key, domain["key"])
    groups: dict[str, dict[str, Any]] = {}
    def number(value):
        text = f"{value:.3g}"
        return text.replace(".", ",") if lang() == "ru" else text
    highlights = []
    for item in items:
        # Safety and explicit controls are never hidden by the editorial limit.
        if item["priority"] <= 1:
            highlights.append({**item, "member_ids": [item["id"]], "summaries": []})
            continue
        analytic = [e for e in item["events"] if e["kind"] not in ("abnormal", "planned_test")]
        if not analytic:
            continue
        first = item["facts"][0]
        domain = (first.get("system") if first.get("record") == "focus_log.json" else
                  membership.get(first.get("key")) if first.get("record") == "labs.json" else "fitness")
        if domain is None and first.get("record") == "labs.json" and any(e["kind"] == "period_shift" for e in analytic):
            continue  # Retained in raw items; no invented system assignment.
        identity = "panel:" + domain if domain else item["id"]
        if identity not in groups:
            groups[identity] = {**item, "id": identity, "events": [], "facts": [],
                "member_ids": [], "summaries": [], "system": domain,
                "name": t("radar.domain." + domain) if domain else item["name"]}
        group = groups[identity]
        group["member_ids"].append(item["id"])
        group["events"].extend(analytic)
        group["facts"].extend(f for f in item["facts"] if f not in group["facts"])
        group["date"] = max(group["date"], item["date"])
        group["priority"] = min(group["priority"], item["priority"])
        for event in analytic:
            detail = event.get("detail") or {}
            if event["kind"] == "period_shift":
                group["summaries"].append(t("insight.period_shift_summary_means" if detail["statistic"] == "monthly_means" else "insight.period_shift_summary", name=event["name"],
                    before=number(detail["before"]), after=number(detail["after"]),
                    unit=first.get("unit_display") or first.get("unit") or "",
                    start=detail["from"][:10], end=detail["to"][:10], n=detail["n"]))
                group["summaries"].append(t("insight.latest_observation",
                    value=number(detail["latest"]["value"]),
                    unit=first.get("unit_display") or first.get("unit") or "",
                    date=detail["latest"]["date"][:10]))
                for context in detail.get("treatment_context") or []:
                    group["summaries"].append(t("insight.treatment_context" if context["current"] else "insight.treatment_context_ended", name=context["drug"],
                        start=context["date"], end=context["end_date"] or t("insight.ongoing")))
            elif event["kind"] == "repeated_abnormal":
                group["summaries"].append(t("insight.repeated_summary", name=event["name"],
                    start=event["facts"][0]["date"][:10], end=event["facts"][-1]["date"][:10]))
            else:
                group["summaries"].append(event["title"])
    for group in groups.values():
        kinds = {e["kind"] for e in group["events"]}
        group["title"] = t("insight.panel_changes" if kinds - {"repeated_abnormal"}
                           else "insight.panel_repeated", name=group["name"])
        group["reason"] = ""
        group["levels"] = sorted({e["level"] for e in group["events"] if e.get("level")})
        group["level"] = group["levels"][-1] if group["levels"] else None
        from ..insight_synthesis import enrich_system
        enrich_system(group)
        highlights.append(group)
    return sorted(highlights, key=lambda i: (i["priority"], all(e["kind"] == "repeated_abnormal" for e in i["events"]), -len(i["member_ids"]), i["id"]))
