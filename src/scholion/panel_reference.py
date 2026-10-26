"""Reference biology at every evidence level, without analytical permission.

Gene annotation and a variant association are different sources with different
scopes. Neither changes a call, a finding, a clinical basis or a decision route.
Descriptions apply to the literature, including when the position is unread.
"""
from __future__ import annotations

from typing import Any, Dict, List

from . import core
from .i18n import CATALOGUES, lang, t
from .genetic_patterns import reference_patterns


def _gene_entry(genes: Dict[str, Any], symbol: str) -> tuple[str, Dict[str, Any]]:
    """Resolve casing of an exact symbol, without guessing an alias or neighbour."""
    key = symbol if symbol in genes else next((k for k in genes if k.upper() == symbol.upper()), symbol)
    return key, genes.get(key) or {}


def gene_function_entry(gene: str) -> Dict[str, Any]:
    """Prefer existing curated biology, then sourced human function annotations.

    The added registry describes genes, never a variant's effect or evidence
    grade. Catalogue aliases retain their original label and resolved identity.
    """
    return _gene_function_entry(gene, lang())


@core.memo_in_reading
def _gene_function_entry(gene: str, _language: str) -> Dict[str, Any]:
    """Resolve once per gene and language in an answer; return independent copies."""
    registry = core._read_knowledge("gene_function_context.json")
    alias = (registry.get("_meta", {}).get("identity_aliases") or {}).get(gene.upper()) or {}
    canonical = alias.get("canonical_symbol") or gene
    for name in ("panel_reference_context.json", "gencc_reference_context.json",
                 "gene_function_context.json"):
        genes = core._read_knowledge(name).get("genes") or {}
        resolved, entry = _gene_entry(genes, str(canonical))
        if entry.get("description") and entry.get("source"):
            # Retain the submitted label on the row; the biology is one shared
            # canonical record, even for an official previous symbol.
            from .knowledge_provenance import record
            return {**entry, "canonical_symbol": entry.get("canonical_symbol") or resolved,
                    "knowledge": record(name, "genes", resolved),
                    **({"identity_source": alias.get("source")} if alias else {})}
    return {}


def _function_fields(gene: str, rsid: str = "") -> Dict[str, Any]:
    resolutions = core._read_knowledge("panel_reference_context.json").get("_meta", {}).get("position_label_resolutions") or {}
    position_label = (resolutions.get(rsid) or {}).get(gene) or {}
    canonical = position_label.get("canonical_symbol") or gene
    entry = gene_function_entry(canonical)
    if not entry and rsid:
        # Some intake labels are historical abbreviations or misspellings.
        # Resolve biology only through this exact curated locus, never fuzzy
        # name matching; retain the source's label and variant evidence level.
        locus = ((core.loci().get("loci") or {}).get(rsid) or {})
        resolved = locus.get("gene")
        if resolved:
            canonical = str(resolved)
            entry = gene_function_entry(canonical)
        if not entry and locus.get("gene_assignment") == "no_gene_annotation":
            from .knowledge_provenance import record
            entry = {"description": t("reference.intergenic"), "source": locus.get("coordinate_source"),
                     "scope": "genomic_annotation", "function_status": "intergenic_region",
                     "retrieved": (locus.get("allele_identity") or {}).get("checked_on"),
                     "knowledge": record("loci.json", "loci", rsid)}
    return {"gene_function": entry.get("description") or t("reference.gene_unknown"),
            "gene_source": entry.get("source"),
            "gene_source_scope": "genomic_annotation" if entry.get("scope") == "genomic_annotation" else "gene_function",
            "retrieved": entry.get("retrieved"), "limitations": entry.get("caveat"),
            "canonical_symbol": entry.get("canonical_symbol") or canonical,
            "function_status": (entry.get("function_status") or "curated") if entry else "not_curated",
            "function_support": entry.get("function_support") or [],
            "gene_knowledge": entry.get("knowledge"),
            "disease_context": core._read_knowledge("gene_function_context.json").get("disease_contexts", {}).get(str(entry.get("canonical_symbol") or canonical)),
            "gene_additional_sources": entry.get("additional_sources") or []}


def gene_reference_context(gene: str, assertions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Gene biology and each GenCC assertion; neither supplies a variant effect."""
    book = core._read_knowledge("gencc_reference_context.json")
    genes = book.get("genes") or {}
    canonical = str(gene_function_entry(gene).get("canonical_symbol") or gene)
    _, entry = _gene_entry(genes, canonical)
    additional = core._read_knowledge("gencc_panel_assertions.json")
    supplement = (additional.get("genes") or {}).get(canonical.upper()) or {}
    # These reference assertions do not enter a clinical finding or a score.
    # Keep every submitter and every class, including disagreement.
    if supplement:
        assertions = supplement.get("submissions") or []
    diseases = {**(entry.get("diseases") or {}), **(supplement.get("diseases") or {})}
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
            "mechanistic_hypotheses": reference_patterns(gene),
            **_function_fields(gene),
            "variant_context": t("reference.variant_not_supplied"),
            "variant_source": None, "variant_status": "not_supplied",
            "gencc_assertions": associations,
            "gencc_status": supplement.get("snapshot_status") or ("assertions_recorded" if associations else "not_available"),
            "gencc_source": "https://thegencc.org/",
            "gencc_version": (additional.get("_meta", {}).get("export_last_modified")
                              if supplement else book.get("_meta", {}).get("gencc_export_version")),
            "notice": t("reference.notice")}


def reference_context(spec: Dict[str, Any], level: Any) -> Dict[str, Any]:
    """A position's reference card; never a genotype-specific conclusion."""
    book = core._read_knowledge("panel_reference_context.json")
    gene = str(spec.get("gene") or "").upper()
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
    return {"scope": "reference_only", "level": level,
            "allele_note": core._localized(spec.get("allele_note"), lang()),
            "mechanistic_hypotheses": reference_patterns(gene, spec.get("rsid")),
            **_function_fields(gene, spec.get("rsid") or ""),
            "variant_context": description or t("reference.variant_unknown"),
            "variant_source": source, "variant_status": "described" if description else "not_curated",
            "notice": t("reference.notice")}


def reference_lines(row: Dict[str, Any]) -> List[str]:
    """Shared CLI/report wording; factual readings remain beside this block."""
    context = row.get("reference_context")
    if not isinstance(context, dict):
        return []
    description_key = "reference.region" if context.get("gene_source_scope") == "genomic_annotation" else "reference.gene"
    lines = [t(description_key, text=context.get("gene_function")),
             t("reference.variant", text=context.get("variant_context"))]
    disease = context.get("disease_context")
    if disease:
        lines.extend([disease["label"] + ": " + disease["name"],
                      disease["limitations"], disease["source"]])
    if context.get('reference_identity'):
        identity=context['reference_identity']
        lines.append(context['reading_limit'])
        for build,value in identity['builds'].items():
            lines.append(t('reference.spdi',build=build,accession=value['accession'],
                           start=value['position_zero_based'],ref=value['reference'],alt='/'.join(value['alternatives'])))
        lines.append(identity['source'])
    canonical = context.get("canonical_symbol")
    if canonical and row.get("gene") and canonical.upper() != str(row["gene"]).upper():
        lines.append(t("reference.resolved_gene", gene=canonical))
    assertion = (row.get("interpretation") or {}).get("database_assertion")
    if assertion:
        lines.append(assertion["description"])
    if row.get("transcript"):
        lines.append(str(row["transcript"]) + " · " + str(row.get("hgvs") or ""))
    for hypothesis in context.get("mechanistic_hypotheses") or []:
        lines.append(t("genlab.reference_patterns") + " · Scholion " + hypothesis["association_level"])
        if hypothesis.get("level_scope") == "mechanism_reference_not_personal_variant":
            lines.append(t("genlab.mechanism_level"))
        lines.extend([hypothesis["summary"], hypothesis["limitations"], hypothesis["source"]])
    if context.get("limitations"):
        lines.append(context["limitations"])
    if context.get('clinical_review'):
        lines.append(context['clinical_review']['limitations'])
    if context.get("allele_note"):
        lines.append(context["allele_note"])
    for assertion in context.get("gencc_assertions") or []:
        lines.append(t("gencc.assertion", disease=assertion["disease_label"],
                       classification=assertion["classification_label"],
                       moi=assertion["moi_label"], submitter=assertion.get("submitter") or "—",
                       date=assertion.get("curated_on") or "—"))
    if context.get("gencc_status") == "no_assertions_in_snapshot":
        lines.append(t("reference.gencc_not_in_snapshot", version=context.get("gencc_version") or "—"))
    if context.get("gencc_assertions"):
        lines.append(t("gencc.source", version=context.get("gencc_version") or "—",
                       source=context.get("gencc_source")))
    if context.get("gene_source"):
        lines.append(t("reference.gene_source", source=context["gene_source"]))
    for source in context.get("gene_additional_sources") or []:
        lines.append(t("reference.gene_source", source=source))
    if context.get("variant_source"):
        lines.append(t("reference.variant_source", source=context["variant_source"]))
    lines.append(t("reference.gene_level") if context.get("variant_status") == "not_supplied"
                 else t("reference.level", level=context.get("level") or "—"))
    if context.get("scope") == "catalogue_gene_set":
        for gene in row.get("gene_contexts") or []:
            lines.append("\n**" + str(gene["gene"]) + "**")
            lines.extend(reference_lines(gene))
    return lines


def database_assertion(assertion: Any) -> Any:
    if not isinstance(assertion, dict):
        return None
    out = dict(assertion)
    for field in ("classification", "review_status"):
        value = str(out.get(field) or "unknown")
        key = "insight.database." + (value.replace(",", "").replace(" ", "_") if field == "review_status" else value)
        out[field + "_label"] = t(key) if key in CATALOGUES[lang()] else str(out.get(field) or "—")
    out["description"] = t("insight.database", classification=out["classification_label"],
        review=out["review_status_label"], accession=out.get("accession") or "—",
        date=out.get("retrieved") or out.get("checked_on") or "—")
    return out


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
            "notice": t("interpretation.notice"), "database_assertion": database_assertion(spec.get("database_assertion"))}


def interpretation_lines(row: Dict[str, Any]) -> List[str]:
    """The same interpretation and confidence through CLI and agent reports."""
    context = row.get("interpretation") or {}
    summary = context.get("summary")
    if not isinstance(summary, str) or not summary:
        return []
    lines = [summary, context.get("notice") or t("interpretation.notice")]
    if context.get("source"):
        lines.append(t("decision.source", source=context["source"]))
    for field in ("evidence_reason", "population", "study_effect", "reading_note"):
        if context.get(field):
            lines.append(str(context[field]))
    if context.get("missing"):
        lines.append(t("interpretation.gaps", missing=", ".join(t("conclusion.missing." + k)
                                                               for k in context["missing"])))
    lines.append(t("reference.level", level=context.get("level") or "—"))
    return lines


def longevity_interpretation(row: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the shared catalogue presentation, with a separately verified call."""
    if not spec.get("level"):
        return row
    from .engine.panel_gate import copies
    reading = core.genotype_status(row["rsid"]) or {}
    locus = (core.loci().get("loci") or {}).get(row["rsid"]) or {}
    alleles = (str(locus["ref"]), str(locus["alt"])) if locus.get("ref") and locus.get("alt") else None
    from .genetic_comparison import genotype_quality
    positive = reading.get("confidence") in ("called", "confirmed_ref", "reported", "called_array") and bool(reading.get("genotype"))
    quality = genotype_quality({"read": bool(positive), "genotype": reading})
    count = copies(reading.get("genotype") or "", spec["favorable"], alleles) if alleles and spec.get("favorable") else None
    verified = (quality["status"] == "usable" and not reading.get("conflict")
                and reading.get("interpretation_applicable") is not False
                and spec.get("personal_effect_permitted", True) and count in (0, 1, 2))
    state = ("absent", "het", "hom")[count] if verified and count is not None else None
    summary = (spec.get("text") or {}).get(state) if state else spec.get("label")
    context = interpretation_context(spec, spec["level"], summary)
    context.update(personalized=verified, reading_note=None if verified else t("longevity.reference_only") if positive else t("insight.reading_unverified"),
                   evidence_reason=spec.get("evidence_reason"),
                   population=spec.get("population_caveat"),
                   study_effect=(spec.get("study") or {}).get("effect"),
                   notice=spec.get("action"), source_passport=spec.get("source_passport"))
    return {**row, "level": spec["level"], "reading": reading, "read": bool(positive),
            "reading_quality": quality, "carries_named_allele": None,
            "source_passport": spec.get("source_passport"), "ld_group": spec.get("ld_group"),
            "joint_interpretation_pointer": "apoe" if row['rsid'] in ('rs429358','rs7412') else None,
            "interpretation": context,
            "verdict_token": "see_apoe" if row["rsid"] in ("rs429358", "rs7412") else None,
            "verdict_label": t("longevity.verdict.see_apoe") if row["rsid"] in ("rs429358", "rs7412") else None,
            "genotype": reading.get("genotype") if positive else row.get("genotype"),
            "stored_genotype": row.get("genotype")}


def attach_finding_biology(rows: List[Dict[str, Any]]) -> None:
    """Give every finding surface the same biology, including rows without rsIDs."""
    loci = core.loci().get("loci") or {}
    for row in rows:
        raw = str(row.get("rsid") or "")
        rsid = raw if raw.startswith("rs") and raw[2:].isdigit() else ""
        genes = list(dict.fromkeys(part.strip() for part in
                    str(row.get("gene") or (loci.get(rsid) or {}).get("gene") or "").replace(",", "|").split("|")
                    if part.strip() not in ("", ".", "—")))
        contexts = []
        for gene in genes:
            item = genome_context(gene, rsid)
            if not rsid:
                # A named clinical-table position is still a variant, even when
                # it has no rsID. Do not invent one or downgrade it to gene-only.
                item["reference_context"].update(variant_status="not_curated",
                                                 variant_context=t("reference.variant_unknown"))
            item.update({key: row.get(key) for key in ("genotype", "chrom", "pos", "ref", "alt")})
            contexts.append(item)
        row["gene_contexts"] = contexts


def genome_context(gene: str, rsid: str = "") -> Dict[str, Any]:
    """Reuse system-panel knowledge, without turning an annotation into an effect.

    Scholion confidence belongs to our interpretation, not ClinVar's stars or
    GenCC's disease validity. An uncurated variant has E context even when an
    external database has classified it; that classification remains separate.
    """
    context: Dict[str, Any]
    members = list(dict.fromkeys(part.strip() for part in gene.split(",") if part.strip()))
    if len(members) > 1:
        # LongevityMap sometimes records a study's gene set. It is not a
        # functional assignment of every listed variant to every listed gene.
        context = {"scope": "catalogue_gene_set", "level": "E",
                   "gene_function": t("reference.gene_set", count=len(members)),
                   "gene_source": "https://genomics.senescence.info/longevity/",
                   "gene_source_scope": "study_gene_set",
                   "variant_context": t("reference.gene_set_variant"),
                   "variant_status": "not_curated" if rsid else "not_supplied",
                   "limitations": t("reference.gene_set_variant")}
        return {"gene": gene, "rsid": rsid, "level": "E", "reference_context": context,
                "catalogue_genes": members,
                "gene_contexts": [genome_context(member) for member in members] if not rsid else []}
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
        curated = (core._read_knowledge("longevity_directions.json").get("directions") or {}).get(rsid) or {}
        if curated.get("gene") == gene and curated.get("level"):
            return {"gene": gene, "rsid": rsid, "level": curated["level"],
                    "reference_context": reference_context({**curated, "rsid": rsid}, curated["level"])}
        assertions = []
        canonical = str(gene_function_entry(gene).get("canonical_symbol") or gene)
        for panel in (core._read_knowledge("gencc_gene_disease.json").get("systems") or {}).values():
            _, entry = _gene_entry(panel.get("genes") or {}, canonical)
            for item in entry.get("submissions") or []:
                if item not in assertions:
                    assertions.append(item)
        context = gene_reference_context(gene, assertions)
        position_labels = core._read_knowledge("panel_reference_context.json").get("_meta", {}).get("position_label_resolutions") or {}
        if not context.get("gene_source") or gene in (position_labels.get(rsid) or {}):
            fallback = reference_context({"gene": gene, "rsid": rsid}, "E")
            if fallback.get("gene_source"):
                context.update({k: fallback[k] for k in ("gene_function", "gene_source", "retrieved",
                    "canonical_symbol", "function_status", "function_support", "limitations",
                    "gene_additional_sources", "gene_knowledge", "gene_source_scope", "disease_context")})
        context["level"] = "E"
        if rsid:
            context["variant_status"] = "not_curated"
            context["variant_context"] = t("reference.variant_unknown")
        # E concerns missing variant interpretation; GenCC status is its own field.
    identity=(core._read_knowledge('variant_reference_identity.json').get('variants') or {}).get(rsid)
    if identity and identity.get('gene') == gene:
        context.update(reference_identity=identity,reading_limit=t('reference.specialized_reading'))
    review=(core._read_knowledge('clinical_reference_review.json').get('positions') or {}).get(gene+'|'+rsid)
    if review and review.get('outcome') != 'existing_supported_basis':
        context['clinical_review']={k:review[k] for k in ('reviewed_on','outcome','limitations','subclaims')}
    return {"gene": gene, "rsid": rsid, "level": context["level"], "reference_context": context}
