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
from ._helpers import DISCLAIMER


@core.in_reading
def visit_sheet(include_reference: bool = False) -> Dict[str, Any]:
    """Do not promote a reference sentence to a personal clinical conclusion."""
    # The package sets its version after importing the engine facade.
    from .. import __version__
    labs = analyze_labs()
    raw = core.labs().get("markers") or {}
    selected: list[Dict[str, Any]] = []
    held: list[Dict[str, Any]] = []
    goals = goal_dashboard()
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
                    "reference_context", "passport", "value_only", "genotype", "source", "mechanism")})
            if rows:
                appendix["panels"].append({"key": spec["key"], "label": panel["label"], "positions": rows})
    from .sources import provenance
    return {"ok": True, "kind": "visit_sheet", "container": container.named(),
            "version": __version__, "as_of": date.today().isoformat(),
            "synthetic": core.profile_is_synthetic(), "title": t("visit.title"),
            "scope_note": t("visit.scope"), "goals": goals.get("entities", []),
            "measurements": selected, "held_measurements": held,
            "measurements_total": labs["count"], "medications": store.list_medications(),
            "regimen_cautions": regimen_cautions(), "treatment": treatment_timeline(),
            "sources": provenance(), "reference_appendix": appendix,
            "appendix_note": t("visit.appendix_note"), "disclaimer": DISCLAIMER()}
