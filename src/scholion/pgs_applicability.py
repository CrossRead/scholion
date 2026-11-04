"""Project sourced model-population evidence alongside the saved PGS result."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from . import core
from .i18n import t

_ID = re.compile(r"PGS[0-9]{6}")
_PERFORMANCE_ID = re.compile(r"PPM[0-9]{6}")
_GROUPS = frozenset({"EUR", "AFR", "EAS", "SAS", "AMR", "GME", "MAE", "MAO", "ASN", "NR", "OTH"})
_LIMITED = frozenset({"mixed", "different_weights", "overlap", "ancestry_incomplete"})
_KINDS = frozenset({"reported", "holdout", "separate_publication"}) | _LIMITED
_INDEPENDENCE = frozenset({"reported_independent", "heldout", "overlap_possible", "not_established"})


def annotate(traits: list[Dict[str, Any]], population: Optional[str]) -> None:
    """Compare broad groups using the profile assignment, never the scoring panel."""
    registry = core._read_knowledge("pgs_population_evidence.json").get("models") or {}
    for trait in traits:
        model_id = trait.get("pgs_id")
        if not isinstance(model_id, str) or not _ID.fullmatch(model_id):
            continue
        trait["model_applicability"] = describe(model_id, registry.get(model_id), population)


def _group_labels(groups: list[str]) -> str:
    return ", ".join(t("prs.applicability.group." + group) for group in groups)


def describe(model_id: str, evidence: Optional[Dict[str, Any]],
             population: Optional[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "model_id": model_id, "profile_group": population,
        "status": "not_reviewed", "gwas_groups": [], "training_groups": [], "evaluations": [],
    }
    if evidence:
        result.update(gwas_groups=evidence["gwas"], training_groups=evidence["training"],
                      source=f"https://www.pgscatalog.org/score/{model_id}/#performances_table",
                      checked_on=evidence.get("checked_on"), publication=evidence.get("publication"),
                      review_status=evidence.get("review_status", "curated"),
                      status="no_evaluation")
        direct, limited = set[str](), set[str]()
        for row in evidence["evaluation"]:
            groups, kind, identifier = row["groups"], row["kind"], row["id"]
            if (not set(groups) <= _GROUPS or kind not in _KINDS
                    or not _PERFORMANCE_ID.fullmatch(identifier)):
                continue
            target = limited if kind in _LIMITED else direct
            target.update(groups)
            independence = row.get("independence", "heldout" if kind == "holdout" else "not_established")
            if independence not in _INDEPENDENCE:
                independence = "not_established"
            result["evaluations"].append({
                "id": identifier, "groups": groups, "kind": kind,
                "label": t("prs.applicability.eval." + kind, groups=_group_labels(groups) or t("prs.applicability.not_reported")),
                "independence": independence,
                "independence_label": t("prs.applicability.independence." + independence),
                "source": f"https://www.pgscatalog.org/rest/performance/{identifier}",
                **{key: row[key] for key in ("limitations", "publication", "sample_set", "sample_size", "metrics") if key in row},
            })
        if population not in core.ANCESTRIES:
            result["status"] = "unknown_population"
        elif population in direct:
            result["status"] = "evaluation_reported"
        elif population in limited:
            result["status"] = "limited_evidence"
        elif direct or limited:
            result["status"] = "no_matching_evaluation"
        elif result["evaluations"]:
            result["status"] = "evaluation_ancestry_unknown"
        for key in ("gwas", "training"):
            groups = result[f"{key}_groups"]
            result[f"{key}_label"] = t(
                f"prs.applicability.{key}",
                groups=_group_labels(groups) if groups else t("prs.applicability.not_reported"),
            )
    result["label"] = t("prs.applicability." + result["status"], population=population)
    return result
