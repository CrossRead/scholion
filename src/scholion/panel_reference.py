"""Reference biology at every evidence level, without analytical permission.

Gene annotation and a variant association are different sources with different
scopes. Neither changes a call, a finding, a clinical basis or a decision route.
Descriptions apply to the literature, including when the position is unread.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import core
from .i18n import CATALOGUES, lang, t


def gene_reference_context(gene: str, assertions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Gene biology and each GenCC assertion; neither supplies a variant effect."""
    book = core._read_knowledge("gencc_reference_context.json")
    genes = book.get("genes") or {}
    entry = genes.get(gene) or genes.get(gene.upper()) or {}
    diseases = entry.get("diseases") or {}
    associations = []
    for assertion in assertions:
        disease = assertion.get("disease") or "—"
        label = (diseases.get(disease) or {}).get("label")
        classification = assertion.get("classification") or "—"
        class_key = "gencc.class." + classification
        moi = str(assertion.get("moi") or "Unknown")
        moi_key = "gencc.moi." + moi
        associations.append({**assertion,
            "disease_label": core._localized(label, lang()) or disease,
            "classification_label": t(class_key) if class_key in CATALOGUES[lang()] else classification,
            "moi_label": t(moi_key) if moi_key in CATALOGUES[lang()] else moi})
    return {"scope": "reference_only", "level": None,
            "gene_function": entry.get("description") or t("reference.gene_unknown"),
            "gene_source": entry.get("source"), "gene_source_scope": "gene_function",
            "retrieved": entry.get("retrieved"),
            "variant_context": t("reference.variant_not_supplied"),
            "variant_source": None, "variant_status": "not_supplied",
            "limitations": entry.get("caveat"),
            "gencc_assertions": associations,
            "gencc_source": "https://thegencc.org/",
            "gencc_version": book.get("_meta", {}).get("gencc_export_version"),
            "notice": t("reference.notice")}


def reference_context(spec: Dict[str, Any], level: Any) -> Dict[str, Any]:
    """A position's reference card; never a genotype-specific conclusion."""
    book = core._read_knowledge("panel_reference_context.json")
    gene = str(spec.get("gene") or "").upper()
    gene_entry = (book.get("genes") or {}).get(gene) or {}
    variant = (book.get("variants") or {}).get(spec.get("rsid")) or {}
    if variant.get("gene") != gene:
        variant = {}
    description = variant.get("description")
    # Structured reference prose also feeds the shared report. Its combined
    # wording is identical to the catalogue description, with a legacy fallback.
    parts = [variant.get("reading"), variant.get("mechanism"),
             variant.get("possible_influence")]
    if all(isinstance(part, str) and part for part in parts):
        description = " ".join(part for part in parts if isinstance(part, str))
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
    lines = [t("reference.gene_level") if context.get("variant_status") == "not_supplied"
             else t("reference.level", level=context.get("level") or "—"),
             t("reference.gene", text=context.get("gene_function")),
             t("reference.variant", text=context.get("variant_context"))]
    if context.get("limitations"):
        lines.append(context["limitations"])
    for assertion in context.get("gencc_assertions") or []:
        lines.append(t("gencc.assertion", disease=assertion["disease_label"],
                       classification=assertion["classification_label"],
                       moi=assertion["moi_label"], submitter=assertion.get("submitter") or "—",
                       date=assertion.get("curated_on") or "—"))
    if context.get("gencc_assertions"):
        lines.append(t("gencc.source", version=context.get("gencc_version") or "—",
                       source=context.get("gencc_source")))
    if context.get("gene_source"):
        lines.append(t("reference.gene_source", source=context["gene_source"]))
    if context.get("variant_source"):
        lines.append(t("reference.variant_source", source=context["variant_source"]))
    return lines
