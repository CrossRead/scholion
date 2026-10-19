"""A visit handout: measured facts and existing checks, with a separate appendix."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

from .. import container, core, store
from ..i18n import t
from .class_genotype import regimen_cautions
from .goals import goal_dashboard
from .labs import analyze_labs
from .treatment import treatment_timeline
from ._helpers import DISCLAIMER, _recent_or_unknown


class VisitSelectionChanged(ValueError):
    """A stale agenda can be recovered by selecting current topics again."""




def visit_topic(item: dict) -> dict:
    """Compact clinical agenda; the original observations remain in the payload."""
    context = item.get("context") or {}
    comparisons = []
    seen = set()
    for row in context.get("comparisons") or []:
        observations = row.get("observations") or [row.get("observation") or {}]
        if row.get("status") in ("excluded", "unread", "allele_absent"):
            continue
        if not any(o.get("point") for o in observations if isinstance(o, dict)):
            continue
        identity = row.get("association_id") or row.get("id")
        if identity not in seen:
            seen.add(identity)
            comparisons.append(row)
    for row in context.get("genetics") or []:
        if row.get("genetic_lab_comparison") or not row.get("comparison") or row.get("status") == "context_only":
            continue
        identity = (row.get("gene"), row.get("rsid"))
        if identity not in seen:
            seen.add(identity)
            comparisons.append({**row, "display_genotype": (row.get("genotype") or {}).get("genotype"),
                                "status_label": row.get("status_label") or t("genlab.no_cause")})
    facts: dict[str, dict[str, dict]] = {}
    for fact in item.get("facts") or []:
        if fact.get("value") is not None and fact.get("key") and fact.get("date"):
            facts.setdefault(fact["key"], {})[fact["date"]] = fact
    measurements = []
    metric_names = {alias: spec.get("label") or name
                    for name, spec in (core.wearable_metrics().get("metrics") or {}).items()
                    for alias in (name, spec.get("person_metric")) if alias}
    for key, dated in facts.items():
        ordered = [dated[k] for k in sorted(dated)]
        measurements.append({"key": key, "name": ordered[-1].get("name") or metric_names.get(key) or core.marker_name({"key": key}),
                             "first": ordered[0], "latest": ordered[-1], "count": len(ordered)})
    comparison_text = {row.get("comparison") for row in comparisons}
    conclusions = [text for text in dict.fromkeys(item.get("summaries") or [])
                   if text not in comparison_text]
    lifestyle = context.get("lifestyle") or []
    if item.get("context_lifestyle_summary") and any((x.get("comparison") or {}).get("eligible") for x in lifestyle):
        conclusions.append(item["context_lifestyle_summary"])
    if not conclusions:
        conclusions = [item.get("title") or ""]
    support = []
    for event in item.get("events") or []:
        detail = event.get("detail") or {}
        for key in ("action", "factor", "why_it_matters", "why", "plan_source"):
            value = detail.get(key)
            if isinstance(value, str) and value and value not in conclusions and value not in support and value not in comparison_text:
                support.append(value)
    return {"conclusions": conclusions, "comparisons": comparisons,
            "measurements": measurements, "support": support}



@core.in_reading
def visit_sheet(include_reference: bool = False, agenda_ids: list[str] | None = None) -> Dict[str, Any]:
    """Do not promote a reference sentence to a personal clinical conclusion."""
    # The package sets its version after importing the engine facade.
    from .. import __version__
    labs = analyze_labs()
    raw = core.labs().get("markers") or {}
    selected: list[Dict[str, Any]] = []
    held: list[Dict[str, Any]] = []
    historical: list[Dict[str, Any]] = []
    goals = goal_dashboard()
    from .insights import attention_feed
    from .lifestyle import lifestyle
    from .labs import suggest_tests
    from ..insight_history import compare_review
    cautions = regimen_cautions()
    treatment = treatment_timeline()
    feed = attention_feed(labs, cautions, treatment["overdue"], lifestyle(), suggest_tests()["suggestions"])
    highlights = feed.get("highlights", feed["items"])
    candidates = highlights + feed.get("follow_up", [])
    all_ids = {i["id"] for i in feed["items"] + candidates}
    if agenda_ids is not None and not set(agenda_ids) <= all_ids:
        raise VisitSelectionChanged(t("visit.selection_changed"))
    agenda = highlights if agenda_ids is None else [i for i in candidates if i["id"] in agenda_ids]
    represented = {mid for i in agenda for mid in i.get("member_ids", [i["id"]])}
    if agenda_ids is not None:
        agenda.extend(i for i in feed["items"] if i["id"] in agenda_ids and i["id"] not in represented)
    agenda_markers = {f.get("key") for i in agenda for f in i["facts"] if f.get("record") == "labs.json"}
    agenda_cautions = {(e["detail"].get("drug"), e["detail"].get("rsid")) for i in agenda
                       for e in i["events"] if e["kind"] == "prescription_genotype"}
    agenda_controls = {(e["detail"].get("name"), e["detail"].get("marker"), e["detail"].get("from"))
                       for i in agenda for e in i["events"] if e["kind"] == "overdue_control"}
    for marker in labs["markers"]:
        row = dict(marker)
        point: Dict[str, Any] = next((p for p in raw.get(row["key"], {}).get("series", [])
                      if p.get("date") == row.get("date")), {})
        row["source"] = point.get("source")
        row["source_record"] = {"file": "labs.json", "marker": row["key"], "date": row.get("date")}
        source = row.get("source")
        row["source_label"] = t("visit.lab_record", marker=row["name"], date=row.get("date") or "—")
        if isinstance(source, str):
            row["source_label"] += " · " + source
        elif isinstance(source, dict):
            row["source_label"] += " · " + str(source.get("path") or "")
            if source.get("pages"):
                row["source_label"] += " · " + t("visit.source_pages", pages=", ".join(map(str, source["pages"])))
        basis = row.get("date_source") or "unrecorded"
        row["date_basis_label"] = t("visit.date_basis." + basis) if basis in (
            "form", "manual", "filename", "ordered", "unrecorded") else t("visit.date_basis.unrecorded")

        relevant = (row.get("abnormal") or row.get("outside_target")
                    or row.get("flag") == "norange" or row.get("reference_withheld"))
        recency = _recent_or_unknown(str(row.get("date") or ""))
        if relevant and row.get("date") and recency is False:
            historical.append(row)
            continue
        if relevant and recency is not True:
            row["recency_note"] = t("visit.date_unverified")
            held.append(row)
            continue
        if row.get("abnormal") or row.get("outside_target"):
            selected.append(row)
        elif row.get("flag") == "norange" or row.get("reference_withheld"):
            held.append(row)
    appendix: Dict[str, Any] = {"included": include_reference, "scope": "reference_only", "panels": []}
    if include_reference:
        # Lazy: preparing the compact sheet does not read the entire genome.
        from .system_panels import systems, system
        for spec in systems()["systems"]:
            if spec["key"] == "author_list":
                continue
            panel = system(spec["key"], "clinician")
            rows = []
            for position in panel.get("genetics", {}).get("positions", []):
                if position.get("level") not in ("C", "D", "E"):
                    continue
                position = dict(position)
                position["reading_label"] = (t("system.state." + position["state"])
                    if position.get("read") and position.get("state") in ("het", "hom", "hemi", "absent")
                    else position.get("read_why_text") or t("common.no_data"))
                rows.append({k: position.get(k) for k in (
                    "gene", "rsid", "level", "reading_label", "read", "read_state", "read_why_text", "state",
                    "reference_context", "interpretation", "passport", "value_only", "genotype", "source", "mechanism")})
            if rows:
                appendix["panels"].append({"key": spec["key"], "label": panel["label"], "positions": rows})
    agenda = [{**item, "visit_brief": visit_topic(item)} for item in agenda]
    from .sources import provenance
    medications = store.list_medications()
    questions = list(dict.fromkeys(q for item in agenda for q in item.get("questions", [])))
    brief = {"period": 365, "questions": questions, "summary": t("visit.summary_counts",
             systems=sum(bool(i.get("system")) for i in agenda),
             medications=sum(m["current"] for m in medications), controls=len(treatment["overdue"]))}
    return {"ok": True, "kind": "visit_sheet", "container": container.named(),
            "version": __version__, "as_of": date.today().isoformat(),
            "synthetic": core.profile_is_synthetic(), "title": t("visit.title"),
            "scope_note": t("visit.scope"), "goals": goals.get("entities", []),
            "agenda": {"items": agenda, "count": len(agenda), "total": len(feed["items"]),
                       "title": t("insight.agenda"), "empty": feed["empty"]},
            "review_changes": compare_review(feed),
            "remaining_measurements": [r for r in selected if r["key"] not in agenda_markers],
            "remaining_cautions": [r for r in cautions if (r.get("drug"), r.get("rsid")) not in agenda_cautions],
            "remaining_controls": [r for r in treatment["controls"]
                if r.get("current") is not False and (r.get("name"), r.get("marker"), r.get("from")) not in agenda_controls],
            "measurements": selected, "held_measurements": held,
            "historical_measurements": historical,
            "measurements_total": labs["count"], "medications": medications, "brief": brief,
            "historical_medications": [m for m in medications if not m["current"]],
            "regimen_cautions": cautions, "treatment": treatment,
            "sources": provenance(), "reference_appendix": appendix,
            "appendix_note": t("visit.appendix_note"), "disclaimer": DISCLAIMER()}
