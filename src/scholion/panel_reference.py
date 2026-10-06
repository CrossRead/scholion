"""Reference biology at every evidence level, without analytical permission.

Gene annotation and a variant association are different sources with different
scopes. Neither changes a call, a finding, a clinical basis or a decision route.
Descriptions apply to the literature, including when the position is unread.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import core
from .i18n import lang, t


def reference_context(spec: Dict[str, Any], level: Any) -> Dict[str, Any]:
    """A position's reference card; never a genotype-specific conclusion."""
    book = core._read_knowledge("panel_reference_context.json")
    gene = str(spec.get("gene") or "").upper()
    gene_entry = (book.get("genes") or {}).get(gene) or {}
    variant = (book.get("variants") or {}).get(spec.get("rsid")) or {}
    if variant.get("gene") != gene:
        variant = {}
    description = variant.get("description")
    source = variant.get("source")
    # An explicitly held molecular mechanism may be shared as reference
    # context, even when the personalised sentence fails its clinical guard.
    if not description and level != "E":
        description = core._localized(spec.get("mechanism"), lang())
        source = spec.get("source") or (spec.get("evidence") or {}).get("source")
    if not isinstance(description, str) or not isinstance(source, str) or level == "E":
        description, source = None, None
    function = gene_entry.get("description") if gene_entry.get("scope") == "gene_function" else None
    return {"scope": "reference_only", "level": level,
            "gene_function": function or t("reference.gene_unknown"),
            "gene_source": gene_entry.get("source") if function else None,
            "gene_source_scope": "gene_function", "retrieved": gene_entry.get("retrieved"),
            "variant_context": description or t("reference.variant_unknown"),
            "variant_source": source, "variant_status": "described" if description else "not_curated",
            "notice": t("reference.notice")}


def reference_lines(row: Dict[str, Any]) -> List[str]:
    """Shared CLI/report wording; factual readings remain beside this block."""
    context = row.get("reference_context")
    if not isinstance(context, dict):
        return []
    lines = [t("reference.level", level=context.get("level") or "—"),
             t("reference.gene", text=context.get("gene_function")),
             t("reference.variant", text=context.get("variant_context"))]
    if context.get("gene_source"):
        lines.append(t("reference.gene_source", source=context["gene_source"]))
    if context.get("variant_source"):
        lines.append(t("reference.variant_source", source=context["variant_source"]))
    return lines
