"""Independent interaction statements; a matched class pair is not a conclusion.

Source syntax is a structural gate, not clinical validation. Specific-drug
scope is checked separately and never inferred from class membership.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List

from .conclusion_basis import conclusion_basis
from .i18n import t


def _clinical_scope_gap(rule: Dict[str, Any]) -> Any:
    """Do not let a newer local copy restore a known study-context substitution."""
    source = rule.get("source")
    source = source if isinstance(source, str) else ""
    def names_source(pmid, doi):
        return bool(re.search(r"\b" + pmid + r"\b", source)) or doi.lower() in source.lower()
    pair = {rule.get("a"), rule.get("b")}
    if pair == {"thyroid_hormone", "combined_oral_contraceptive"} and names_source("11396440", "10.1056/NEJM200106073442302"):
        return t("interactions.scope.estrogen_study")
    if pair == {"ppi", "vitamin_b12"} and names_source("24327038", "10.1001/jama.2013.280490"):
        return t("interactions.scope.b12_study")
    if pair == {"thyroid_hormone", "iron_oral"} and names_source("1443969", "10.7326/0003-4819-117-12-1010"):
        if rule.get("study_context") != "simultaneous_ferrous_sulfate_levothyroxine":
            return t("interactions.scope.iron_study")
    applicability = rule.get("applicability")
    if applicability is not None and (not isinstance(applicability, dict) or applicability.get("status") != "held"):
        return t("interactions.scope_unheld")
    return None


def _statement_basis(spec: Any, text: Any) -> Dict[str, Any]:
    basis = conclusion_basis(spec)
    usable = (isinstance(text, str) and bool(text.strip())) or (
        isinstance(text, dict) and all(isinstance(text.get(k), str) and text[k].strip() for k in ("en", "ru")))
    if not usable:
        basis = {**basis, "status": "incomplete", "missing": [*basis["missing"], "claim_text"],
                 "reason": t("drug.guidance.claim_text")}
    return basis


def _guard(rule: Dict[str, Any], applicable: bool) -> Dict[str, Any]:
    basis = _statement_basis(rule, rule.get("effect"))
    scope_gap = _clinical_scope_gap(rule)
    if scope_gap:
        basis = {**basis, "status": "incomplete", "missing": [*basis["missing"], "clinical_scope"], "reason": scope_gap}
    if not applicable:
        basis = {**basis, "status": "incomplete", "missing": [*basis["missing"], "drug_scope"],
                 "reason": t("interactions.scope_unheld")}
    out = {**rule, "conclusion_basis": basis, "catalogue_severity": rule.get("severity"),
           "interpretation_withheld": basis["status"] != "complete",
           "source": basis["source"], "mechanism": basis["mechanism"], "manage": rule.get("manage") or None}
    mb = _statement_basis(rule.get("manage_basis"), rule.get("manage")) if rule.get("manage") else None
    if mb and basis["status"] != "complete":
        mb = {**mb, "status": "incomplete", "missing": [*mb["missing"], "parent_basis"], "reason": basis["reason"]}
    out["management_basis"] = mb
    if basis["status"] != "complete":
        out.update(severity="unknown", effect=basis["reason"], mechanism=None, manage=None)
    elif mb and mb["status"] != "complete":
        out["manage"] = None
    return out


def matched_rows(rule: Dict[str, Any], drug: str, classes: List[str], pair: str,
                 meds: List[str], class_names: Dict[str, Any],
                 matches: Callable[[str, str], bool]) -> List[Dict[str, Any]]:
    """Preserve each observed partner, splitting held/unheld identities if needed."""
    scope = rule.get("drug_scope") or {}
    if rule.get("study_context") == "simultaneous_ferrous_sulfate_levothyroxine":
        scope = {**scope, "thyroid_hormone": {"names": ["levothyroxine", "levothyroxine sodium", "левотироксин"]},
                 "iron_oral": {"names": ["ferrous sulfate", "ferrous sulphate", "сульфат железа", "железа сульфат"]}}

    def held(name, cls):
        exact = (scope.get(cls) or {}).get("names") or []
        if not exact:
            return True
        aliases = (class_names.get(cls) or {}).get("names") or []
        return any(matches(name, n) for n in exact) and not any(
            matches(name, n) for n in aliases if not any(matches(n, x) for x in exact))

    new_held = all(held(drug, cls) for cls in classes if cls in scope)
    groups: Dict[bool, List[str]] = {}
    for name in meds:
        groups.setdefault(new_held and held(name, pair), []).append(name)
    if not groups:
        groups[False if pair in scope else new_held] = []
    return [{**_guard(rule, applies), "with_class": pair, "with_meds": names}
            for applies, names in groups.items()]
