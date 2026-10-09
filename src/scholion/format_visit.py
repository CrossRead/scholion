"""A printable visit structure as readable text for the command and tool doors."""
from __future__ import annotations

from typing import Any, Dict

from .i18n import t
from .format_primitives import _n


def visit_report(data: Dict[str, Any]) -> str:
    from .format_prescription import caution_lines
    lines = [data["title"], t("visit.stamp", id=data["container"].get("id") or "—",
                              version=data["version"], date=data["as_of"]), data["scope_note"]]
    if data["synthetic"]:
        lines.append(t("web.header.demo_banner"))
    lines += ["", t("visit.goals")]
    for goal in data["goals"]:
        lines.append(f"• {goal['title']} · {goal['origin']['label']} · {goal['record']['file']}")
    if not data["goals"]:
        lines.append(t("visit.empty"))
    lines += caution_lines(data["regimen_cautions"])
    lines += ["", t("visit.measurements")]
    for row in data["measurements"]:
        lines.append(f"• {row['name']}: {row.get('censored') or ''}{_n(row['value'])} "
                     f"{row.get('unit') or ''} · {row['date']} · "
                     f"{_n(row.get('ref_low'))}–{_n(row.get('ref_high'))}")
        lines.append("  " + t("visit.observation_source", source=row["source_label"],
                               date_source=row["date_basis_label"]))
    if not data["measurements"]:
        lines.append(t("visit.empty"))
    lines += ["", t("visit.medications")]
    for med in data["medications"]:
        if med["current"]:
            lines.append(f"• {med['name']} · {med.get('dose') or '—'} · "
                         f"{med.get('start_date') or t('treatment.undated')} · medications.json")
    lines += ["", t("treatment.title")]
    for control in data["treatment"]["controls"]:
        lines.append(t("treatment.control", name=control.get("name") or "—", marker=control.get("marker") or "—",
                       start=control.get("from") or "—", due=control.get("due") or "—")
                     + " · " + t("treatment.status." + control["status"]))
        lines.append(str(control.get("plan_source") or t("treatment.unresolved")))
    lines += ["", t("visit.held", n=len(data["held_measurements"]))]
    lines.extend(f"• {r['name']} · {r.get('date') or '—'} · "
                 + (r.get("corridor_note") or t("visit.no_corridor")) for r in data["held_measurements"])
    if data["reference_appendix"]["included"]:
        lines += ["", t("visit.appendix"), data["appendix_note"]]
        for panel in data["reference_appendix"]["panels"]:
            lines += ["", panel["label"]]
            for row in panel["positions"]:
                context = row.get("reference_context") or {}
                lines.append(f"• {row['gene']} {row['rsid']} · {row['level']} · "
                             + str(row.get("reading_label") or "—"))
                for field in ("gene_function", "variant_context", "gene_source", "variant_source"):
                    if context.get(field):
                        lines.append(str(context[field]))
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
