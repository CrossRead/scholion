"""Only explicit, sourced model-to-phenotype joins, after ordinary PGS validation."""
from __future__ import annotations

from datetime import date

from .. import core, knowledge_provenance
from ..pgs_validation import validate
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
    models: dict[str, list[dict]] = {}
    for category in pgs.get("categories") or []:
        for trait in category.get("traits") or []:
            model = trait.get("pgs_id")
            if isinstance(model, str):
                models.setdefault(model, []).append(trait)
    events = []
    for spec in relevant:
        row = rows[spec["marker"]]
        candidates = models.get(spec["pgs_id"], [])
        if len(candidates) != 1:
            continue
        score = validate(candidates[0], expected_ancestry=spec["reference_population"])
        percentile = score.get("percentile")
        if (score.get("reliable") is not True or not isinstance(percentile, (int, float))
                or not spec["percentile_min"] <= percentile < 100
                or score.get("reference_panel_ancestry") != spec["reference_population"]):
            continue
        points = sorted(row.get("series") or [], key=lambda p: str(p.get("date") or ""))
        if not points or not _current(points[-1], date.today()) or points[-1].get("censored") or points[-1].get("comparator") not in (None, "", "="):
            continue
        scoring = score["scoring_validation"]
        reference = score["reference_validation"]
        fact = {"record": "prs_results.json", "pgs_id": spec["pgs_id"], "percentile": percentile,
                "reference_panel_ancestry": score["reference_panel_ancestry"],
                "computed": (pgs.get("provenance") or {}).get("computed"),
                "scoring_trace": {"term": score.get("term"), "score": score.get("score"),
                                "assembly": score["genome_build"], "reading": score["reading"],
                                "algorithm": scoring["algorithm"], "input_sha256": scoring["input_sha256"],
                                "model_sha256": scoring["model_sha256"],
                                "reference_panel": score["reference_panel"],
                                "reference_snapshot": reference["snapshot_sha256"]}}
        rule = knowledge_provenance.record("insight_links.json", "links", spec["id"])
        event = _event("pgs_phenotype", spec["id"], row["name"],
                       [_fact(row["key"], points[-1], row), fact], priority=3,
                       destination="genome", rule=rule,
                       detail={"why": spec["summary"], "source": spec["source"],
                               "study_limitations": spec["limitations"]})
        event["inputs"] = {"schema": 1, "fact_indices": {"phenotype": [0], "score": [1]}}
        event["knowledge_records"] = [rule]
        event["level"] = spec["level"]
        events.append(event)
    return events
