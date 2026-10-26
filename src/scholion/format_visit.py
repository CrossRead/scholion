"""A printable visit structure as readable text for the command and tool doors."""
from __future__ import annotations

from typing import Any, Dict

from .i18n import t
from .format_primitives import _n


def visit_report(data: Dict[str, Any]) -> str:
    if "appointment" in data or data.get("document"):
        from .format_visit_focus import report
        return report(data)
    from .format_prescription import caution_lines
    lines = [(data.get("document") or {}).get("title") or data["title"], t("visit.stamp", id=data["container"].get("id") or "—",
                              version=data["version"], date=data["as_of"]), data["scope_note"]]
    from .format_visit_focus import document_overview
    lines.extend(document_overview(data))
    if data["synthetic"]:
        lines.append(t("web.header.demo_banner"))
    brief = data.get("brief") or {}
    if brief and not data.get('document'):
        lines += ["", t("visit.summary_heading"), brief["summary"], t("visit.year")]
    if data.get("agenda"):
        from .genetic_comparison import lines as comparison_lines
        for item in data["agenda"]["items"]:
            brief_item = item.get("visit_brief") or {}
            lines += ["", item["title"], *brief_item.get("conclusions", item.get("summaries") or [])]
            for row in brief_item.get("measurements") or []:
                a, b = row["first"], row["latest"]
                values = ([a, b] if row["count"] > 1 else [b])
                lines.append(row["name"] + ": " + " → ".join(
                    str(p.get("censored") or "") + _n(p["value"]) + " " + str(p.get("unit_display") or p.get("unit") or "")
                    + " (" + p["date"] + ")" for p in values))
                lines.append(str(b.get("source") or b.get("record") or ""))
            lines.extend(brief_item.get("support") or [])
            for comparison in brief_item.get("comparisons") or []:
                lines.extend(comparison_lines(comparison))
            from .format_insights import basis_lines
            lines.extend(basis_lines(item))
    changes = data.get("review_changes") or {}
    estimates=data.get('clinical_estimates') or {}
    computed=[r for r in estimates.get('estimates') or [] if r['status']=='computed']
    if computed:
        lines += ['',estimates['label']]
        for row in computed:
            lines.append(row['name']+': '+str(row['value'])+' '+row['unit']+' · '+str(row['date']))
            lines.append(row['interpretation'] or '')
            lines.append(row['source'])
        lines.append('scholion system clinical_estimates')
    if changes.get("available"):
        lines += ["", t("insight.history")]
        from .format_insights import review_change_lines
        lines.extend(review_change_lines(changes))
    if brief.get("questions"):
        lines += ["", t("visit.questions")] + ["• " + q for q in brief["questions"]]
    if data["goals"] or not data.get('document'):
        lines += ["", t("visit.goals")]
    for goal in data["goals"]:
        lines.append(f"• {goal['title']} · {goal['origin']['label']} · {goal['record']['file']}")
    if not data["goals"] and not data.get('document'):
        lines.append(t("visit.empty"))
    lines += caution_lines(data.get("remaining_cautions", data["regimen_cautions"]))
    if data.get("remaining_measurements", data["measurements"]) or not data.get('document'):
        lines += ["", t("visit.measurements")]
    for row in data.get("remaining_measurements", data["measurements"]):
        lines.append(f"• {row['name']}: {row.get('censored') or ''}{_n(row['value'])} "
                     f"{row.get('unit') or ''} · {row['date']} · "
                     f"{_n(row.get('ref_low'))}–{_n(row.get('ref_high'))}")
        lines.append("  " + t("visit.observation_source", source=row["source_label"],
                               date_source=row["date_basis_label"]))
    if not data.get("remaining_measurements", data["measurements"]) and not data.get('document'):
        lines.append(t("visit.empty"))
    if any(m['current'] for m in data['medications']) or not data.get('document'):
        lines += ["", t("visit.medications")]
    for med in data["medications"]:
        if med["current"]:
            lines.append(f"• {med['name']} · {med.get('dose') or '—'} · "
                         f"{med.get('start_date') or t('treatment.undated')} · medications.json")
    if data.get("historical_medications"):
        lines += ["", t("visit.rx_history")]
        for med in data["historical_medications"]:
            lines.append(f"• {med['name']} · {med.get('end_date') or med.get('status') or '—'}")
    report_controls = data.get("remaining_controls", data["treatment"]["controls"])
    if data.get('document'):
        report_controls = [c for c in report_controls if c['status'] in ('scheduled', 'overdue', 'recorded')]
    if report_controls or not data.get('document'):
        lines += ["", t("treatment.title")]
    for control in report_controls:
        lines.append(t("treatment.control", name=control.get("name") or "—", marker=control.get("marker") or "—",
                       start=control.get("from") or "—", due=control.get("due") or "—")
                     + " · " + t("treatment.status." + control["status"]))
        lines.append(str(control.get("plan_source") or t("treatment.unresolved")))
    if data['held_measurements'] or not data.get('document'):
        lines += ["", t("visit.held", n=len(data["held_measurements"]))]
    lines.extend(f"• {r['name']} · {r.get('date') or '—'} · "
                 + (r.get("recency_note") or r.get("corridor_note") or t("visit.no_corridor")) for r in data["held_measurements"])
    history = data.get("historical_measurements") or []
    if history:
        lines += ["", t("visit.historical", n=len(history))]
        for row in history:
            lines.append(f"• {row['name']}: {row.get('censored') or ''}{_n(row['value'])} "
                         f"{row.get('unit') or ''} · {row.get('date') or '—'}")
            lines.append("  " + row["source_label"])
    if data["reference_appendix"]["included"]:
        lines += ["", t("visit.appendix"), data["appendix_note"]]
        for panel in data["reference_appendix"]["panels"]:
            lines += ["", panel["label"]]
            for row in panel["positions"]:
                from .panel_reference import interpretation_lines, reference_lines
                lines.append(f"• {row['gene']} {row['rsid']} · " + str(row.get("reading_label") or "—"))
                lines.extend(reference_lines(row))
                lines.extend(interpretation_lines(row))
                passport = row.get("passport") or {}
                if passport:
                    lines.append(t("web.hyp.head", level=passport["level"]))
                    lines.append(passport.get("reported") or t("system.hyp.no_sentence"))
                    for field in ("why_this_level", "mechanism", "effect", "population", "study",
                                  "replication", "would_confirm", "would_refute", "source"):
                        if passport.get(field):
                            lines.append(t("system.hyp.part." + field, value=passport[field]))
                    if passport.get("missing"):
                        lines.append(t("system.hyp.missing", parts=", ".join(
                            t("system.hyp.name." + field) for field in passport["missing"])))
    lines += ["", data["disclaimer"]]
    return "\n".join(lines)
