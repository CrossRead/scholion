"""Only explicit, sourced model-to-phenotype joins, after ordinary PGS validation."""
from __future__ import annotations

from datetime import date

from .. import core
from .insight_events import _current, _event, _fact


def linked_pgs_events(labs: dict, pgs: dict | None = None) -> list[dict]:
    links = core._read_knowledge("insight_links.json").get("links") or []
    rows = {r["key"]: r for r in labs.get("markers") or [] if not r.get("proposed_rule")}
    relevant = [s for s in links if rows.get(s["marker"], {}).get("flag") == s["flag"]]
    if not relevant:
        return []
    if pgs is None:
        from .genomics import prs_findings
        pgs = prs_findings()
    stats = pgs.get("stats") or {}
    if not stats.get("panel_matches_ancestry") or (pgs.get("recalculation") or {}).get("reason") in {
            "input_changed", "population_changed", "model_changed"}:
        return []
    models = {t.get("pgs_id"): t for cat in pgs.get("categories") or [] for t in cat["traits"]}
    events = []
    for spec in relevant:
        row, score = rows[spec["marker"]], models.get(spec["pgs_id"]) or {}
        percentile = score.get("percentile")
        if (score.get("reliable") is not True or not isinstance(percentile, (int, float))
                or not spec["percentile_min"] <= percentile < 100
                or score.get("reference_panel_ancestry") != spec["reference_population"]):
            continue
        points = sorted(row.get("series") or [], key=lambda p: str(p.get("date") or ""))
        if not points or not _current(points[-1], date.today()) or points[-1].get("censored") or points[-1].get("comparator") not in (None, "", "="):
            continue
        fact = {"record": "prs_results.json", "pgs_id": spec["pgs_id"], "percentile": percentile,
                "reference_panel_ancestry": score["reference_panel_ancestry"],
                "computed": (pgs.get("provenance") or {}).get("computed")}
        event = _event("pgs_phenotype", spec["id"], row["name"],
                       [_fact(row["key"], points[-1], row), fact], priority=3,
                       destination="genome", rule=spec["source"],
                       detail={"why": spec["summary"], "source": spec["source"],
                               "study_limitations": spec["limitations"]})
        event["level"] = spec["level"]
        events.append(event)
    return events
