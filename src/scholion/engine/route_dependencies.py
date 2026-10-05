"""Observe existing cross-panel inputs without importing their interpretation."""
from __future__ import annotations

from . import routes


def _observe(key, by_key, rows):
    from . import system_panels as panels
    from .. import core
    wanted_genes, wanted_positions = set(), set()
    meds = [m.lower() for m in core.medication_names()]
    for rule in routes.routes_book().get("rules") or []:
        if rule.get("system") != key:
            continue
        trigger = rule.get("trigger") or {}
        if trigger.get("medications"):
            if not any(q in m for q in trigger["medications"] for m in meds):
                continue
        elif not routes._deviating(trigger, by_key):
            continue
        if routes._genotype_holds(rule.get("depends_on"), rows):
            continue
        missing = routes._unobserved_dependencies(rule.get("depends_on"), rows)
        dep = rule.get("depends_on") or {}
        wanted_genes.update(n for n in dep.get("genes") or [] if n in missing)
        wanted_positions.update(n for n in dep.get("positions") or [] if n in missing)
    out = list(rows)
    if not wanted_genes and not wanted_positions:
        return out
    curated = panels._curated().get("systems") or {}
    for dom in panels.domains():
        if dom["key"] == key:
            continue
        positions = (curated.get(dom["key"]) or {}).get("positions") or []
        genes = {r.get("gene") for r in panels._base_rows(dom["key"])["rows"]}
        if not (genes & wanted_genes or {p.get("rsid") for p in positions} & wanted_positions):
            continue
        for row in panels._genetics_layer(dom, by_key).get("rows") or []:
            if (row.get("unit") == "position" and row.get("rsid") in wanted_positions
                    or row.get("unit") != "position" and row.get("gene") in wanted_genes):
                out.append({k: row[k] for k in ("unit", "gene", "rsid", "state", "carrier", "read", "presumed")
                            if k in row})
    return out
