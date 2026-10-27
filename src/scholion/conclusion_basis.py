"""The structural minimum for a product interpretation, not clinical validation.

A publication identifier or typed source passport must still be checked against
the exact sentence during curation. Database and guideline identities do not
require a PMID; their claim scope and version remain mandatory. This
offline check never claims that an identifier proves an effect or applicability.
Raw bilingual mechanisms must have both languages; already-localised callers
are also supported, with raw catalogue completeness held by regression tests.
"""
from __future__ import annotations

import re
from typing import Any, Dict

from .i18n import lang, t

_PMID = re.compile(r"\bPMID\s*:?\s*([1-9][0-9]{0,8})\b", re.I)
# An offline syntax pattern, not an endpoint contacted by this module.
_PUBMED = re.compile("https://" + re.escape("pubmed.ncbi.nlm.nih.gov") + r"/([1-9][0-9]{0,8})(?:/|\b)", re.I)
_DOI = re.compile(r"\b10\.[1-9][0-9]{3,8}/[^\s<>\"']+", re.I)


def source_has_identifier(source: Any) -> bool:
    """Identifier syntax only; no network lookup and no clinical approval."""
    return isinstance(source, str) and bool(_PMID.search(source) or _PUBMED.search(source) or _DOI.search(source))


def _source_passport(source: Any, claim_type: str) -> bool:
    """Structural source identity and scope, never scientific approval by URL."""
    if not isinstance(source, dict):
        return False
    kind = source.get('source_type')
    scopes = source.get('claim_scopes') or []
    reviewed_on = source.get('reviewed_on')
    if not isinstance(scopes, list) or claim_type not in scopes or not isinstance(reviewed_on, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', reviewed_on):
        return False
    url = source.get('url')
    ident = source.get('identifier')
    if not isinstance(url, str) or not url.startswith('https://') or not isinstance(ident, str) or not ident.strip():
        return False
    if kind == 'publication':
        return source_has_identifier(ident) or bool(ident.startswith('https://') and source.get('title'))
    if not source.get('version'):
        return False
    if kind == 'guideline':
        return bool(source.get('issuer') and source.get('title'))
    if kind == 'database_assertion':
        # A gene-level or classification assertion cannot supply a clinical rule.
        if claim_type not in ('gene_function', 'gene_disease_validity', 'variant_classification', 'sequence_annotation'):
            return False
        patterns = {'ClinVar': r'(?:VCV|RCV|SCV)[0-9]+(?:\.[0-9]+)?',
                    'GenCC': r'SGC-[0-9]+', 'UniProt': r'[A-Z0-9]{6,10}',
                    'GO': r'GO:[0-9]{7}', 'NCBI Gene': r'[0-9]+'}
        pattern = patterns.get(str(source.get('database') or ''))
        return bool(pattern and re.fullmatch(pattern, ident))
    return False


def conclusion_basis(spec: Any, *, claim_type: str = 'personal_inference') -> Dict[str, Any]:
    """A row's own support and named gaps, without mutation or a system fallback."""
    spec = spec if isinstance(spec, dict) else {}
    evidence = spec.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    source = spec.get("source") or evidence.get("source")
    raw = spec.get("mechanism")
    bilingual = isinstance(raw, dict) and all(isinstance(raw.get(k), str) and raw[k].strip()
                                              for k in ("en", "ru"))
    mechanism = raw.get(lang()) if bilingual else raw if isinstance(raw, str) else None
    mechanism = mechanism.strip() if isinstance(mechanism, str) else None
    missing = []
    passport = spec.get('source_passport')
    passport_valid = _source_passport(passport, claim_type)
    if not source_has_identifier(source) and not passport_valid:
        missing.append("source_identifier")
    if not mechanism and claim_type not in ('gene_function', 'gene_disease_validity', 'variant_classification', 'sequence_annotation'):
        missing.append("mechanism")
    return {"status": "incomplete" if missing else "complete", "missing": missing,
            "source": source if isinstance(source, str) else passport.get('url') if passport_valid else None,
            "source_kind": passport.get('source_type') if passport_valid else 'publication_identifier' if source_has_identifier(source) else None,
            "mechanism": mechanism or None,
            "reason": t("conclusion.withheld", missing=", ".join(t("conclusion.missing." + k)
                                                                    for k in missing)) if missing else None}


def guard_position(spec: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the reading and level, withhold an unsupported A/B interpretation.

    This guards curated positions only, not every clinical output in the product.
    Author opinions and local notes retain their own explicit provenance.
    """
    out = guard_subclaims(spec, row)
    if row.get("level") not in ("A", "B"):
        out["conclusion_basis"] = None
        return out
    basis = conclusion_basis(spec)
    out["conclusion_basis"] = basis
    if basis["status"] != "complete":
        out.update(text=None, mechanism=None, effect_size=None, expect_check=None,
                   next_step=None, route=None, under_load=None, findings=0,
                   clinical_carrier=False, pending=True,
                   pending_why=row.get("pending_why") or "conclusion_basis",
                   not_a_finding_why=row.get("not_a_finding_why") or "basis")
    return out


_SUBCLAIMS = {"expect": "expect_check", "route": "route", "under_load": "under_load", "next_step": "next_step"}


def subclaim_bases(spec: Dict[str, Any], level: Any) -> Dict[str, Any]:
    """Each adjacent clinical claim needs its own support, not a parent's loan."""
    out = {}
    parent = conclusion_basis(spec)
    for name in _SUBCLAIMS:
        if spec.get(name) is None:
            continue
        basis = conclusion_basis(spec[name])
        missing = list(basis["missing"])
        if level not in ("A", "B"):
            missing.append("evidence_level")
        if parent["status"] != "complete":
            missing.append("parent_basis")
        out[name] = {**basis, "missing": missing, "status": "incomplete" if missing else "complete",
                     "reason": t("conclusion.withheld", missing=", ".join(t("conclusion.missing." + k)
                                                                           for k in missing)) if missing else None}
    return out


def guard_subclaims(spec: Dict[str, Any], row: Dict[str, Any], *, reference: bool = False) -> Dict[str, Any]:
    """Keep observation/provenance fields; suppress only the unsupported subclaim."""
    out = dict(row)
    bases = subclaim_bases(spec, row.get("level"))
    if bases:
        out["subclaim_basis"] = bases
    for name, basis in bases.items():
        destination = name if reference else _SUBCLAIMS[name]
        if basis["status"] != "complete":
            out[destination] = None
        elif isinstance(out.get(destination), dict):
            out[destination] = {**out[destination], "conclusion_basis": basis}
    return out
