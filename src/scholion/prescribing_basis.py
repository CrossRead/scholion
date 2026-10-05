"""Own support for prescribing prose and quotations, not for raw observations.

This is the prescribing part of C17, not its all-output acceptance. Identifier
syntax cannot establish clinical relevance, drug identity or indication. Those
remain separate applicability checks and source-based editorial work.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

from .conclusion_basis import conclusion_basis
from .i18n import t


def _quote_digest(quote: Dict[str, Any]) -> str:
    """Bind support to the actual quote, not to a mutable imported slot."""
    text = {k: quote.get(k) for k in ("phenotype", "recommendation", "implication", "classification")}
    return hashlib.sha256(json.dumps(text, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _guard_guidance(row: Dict[str, Any]) -> Dict[str, Any]:
    """A row's note and quote cannot borrow support from each other or a drug."""
    basis = conclusion_basis(row)
    note = row.get("note")
    has_text = (isinstance(note, str) and bool(note.strip())) or (
        isinstance(note, dict) and all(isinstance(note.get(k), str) and note[k].strip() for k in ("en", "ru")))
    if not has_text:
        basis = {**basis, "status": "incomplete", "missing": [*basis["missing"], "claim_text"],
                 "reason": t("drug.guidance.claim_text")}
    out = {**row, "conclusion_basis": basis,
           "interpretation_withheld": basis["status"] != "complete",
           "source": basis["source"], "mechanism": basis["mechanism"]}
    out["catalogue_level"] = row.get("level")
    cp = row.get("cpic")
    out["cpic"] = cp if isinstance(cp, dict) else None
    quote_basis = conclusion_basis(cp) if isinstance(cp, dict) else None
    if isinstance(cp, dict) and (cp.get("basis_quote_sha256") != _quote_digest(cp)
                                or not isinstance(cp.get("recommendation"), str)
                                or not cp["recommendation"].strip()):
        quote_basis = {**(quote_basis or {}), "status": "incomplete",
                       "missing": [*(quote_basis or {}).get("missing", []), "quote_identity"],
                       "reason": t("drug.guidance.quote_identity")}
    out["cpic_basis"] = quote_basis
    if isinstance(cp, dict) and quote_basis and quote_basis["status"] != "complete":
        out["cpic"] = None
    if basis["status"] != "complete":
        out.update(level="unknown", note=basis["reason"], mechanism=None,
                   gap_reason=basis["reason"])
    return out


def _guard_gene_role(entry: Dict[str, Any]) -> Dict[str, Any]:
    """A generic gene-role explanation has its own support, not the table's."""
    spec = entry.get("gene_role_basis")
    row = _guard_guidance({**(spec if isinstance(spec, dict) else {}), "note": entry.get("why")})
    return {"basis": row["conclusion_basis"], "text": row["note"]}
