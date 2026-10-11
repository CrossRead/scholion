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


def interpretation_context(spec: Dict[str, Any], level: Any, summary: Any = None) -> Dict[str, Any]:
    """Retain authored interpretation at every level, with its own support gaps.

    The caller supplies only a sentence for a verified reading, or a dictionary
    of catalogue sentences on the reference page. This never promotes a finding,
    supplies a missing effect, or changes clinical decision eligibility.
    """
    from .conclusion_basis import conclusion_basis
    basis = conclusion_basis(spec)
    # Remove only the retired display-policy suffix, never a biological caveat.
    def recorded(text: Any) -> Any:
        if not isinstance(text, str):
            return text
        for suffix in ("; no verdict.", "; no conclusion.", "; no conclusion follows.", "; "+"\u0432\u044b\u0432\u043e\u0434\u0430 \u043d\u0435\u0442."):
            if text.endswith(suffix):
                return text[:-len(suffix)] + "."
        return text
    summary = {key: recorded(value) for key, value in summary.items()} if isinstance(summary, dict) else recorded(summary)
    return {"scope": "catalogue_interpretation", "level": level,
            "summary": summary, "mechanism": core._localized(spec.get("mechanism"), lang()) or None,
            "source": basis.get("source"), "missing": basis["missing"],
            "notice": t("interpretation.notice")}


def interpretation_lines(row: Dict[str, Any]) -> List[str]:
    """The same interpretation and confidence through CLI and agent reports."""
    context = row.get("interpretation") or {}
    summary = context.get("summary")
    if not isinstance(summary, str) or not summary:
        return []
    lines = [t("interpretation.summary", level=context.get("level") or "—", text=summary),
             context.get("notice") or t("interpretation.notice")]
    if context.get("source"):
        lines.append(t("decision.source", source=context["source"]))
    if context.get("missing"):
        lines.append(t("interpretation.gaps", missing=", ".join(t("conclusion.missing." + k)
                                                               for k in context["missing"])))
    return lines


def genome_context(gene: str, rsid: str = "") -> Dict[str, Any]:
    """Reuse system-panel knowledge, without turning an annotation into an effect.

    Scholion confidence belongs to our interpretation, not ClinVar's stars or
    GenCC's disease validity. An uncurated variant has E context even when an
    external database has classified it; that classification remains separate.
    """
    spec = None
    for name, field in (("system_gene_panels.json", "systems"), ("on_demand_panels.json", "panels")):
        for panel in (core._read_knowledge(name).get(field) or {}).values():
            for entry in panel.get("positions") or []:
                if entry.get("rsid") == rsid and str(entry.get("gene") or "").upper() == gene.upper():
                    spec = entry
                    break
            if spec:
                break
        if spec:
            break
    if spec:
        from .engine.panel_gate import level_of, legend
        level = level_of(spec, {r["level"]: r for r in legend()["levels"]}).get("level") or "E"
        context = reference_context(spec, level)
    else:
        assertions = []
        for panel in (core._read_knowledge("gencc_gene_disease.json").get("systems") or {}).values():
            for item in ((panel.get("genes") or {}).get(gene.upper()) or {}).get("submissions") or []:
                if item not in assertions:
                    assertions.append(item)
        context = gene_reference_context(gene, assertions)
        if not context.get("gene_source"):
            fallback = reference_context({"gene": gene}, "E")
            if fallback.get("gene_source"):
                context.update({k: fallback[k] for k in ("gene_function", "gene_source", "retrieved")})
        context["level"] = "E"
        if rsid:
            context["variant_status"] = "not_curated"
            context["variant_context"] = t("reference.variant_unknown")
        # E concerns missing variant interpretation; GenCC status is its own field.
    return {"gene": gene, "rsid": rsid, "level": context["level"], "reference_context": context}
