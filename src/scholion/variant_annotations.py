"""Portable reference annotations, distinct from personal genotype interpretation.

The catalogue retains exact source text. A navigation category is not a clinical
classification, an inferred direction or an assertion about allele dosage.
"""
from __future__ import annotations

from functools import lru_cache
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from . import core

ANNOTATIONS = "variant_source_records.json"
MODELS = ANNOTATIONS
RECORD_FIELDS = ("id", "gene_ids", "protein_gene_ids", "protein", "feature_id", "type",
                 "location", "alternative", "rsids", "description", "pmids", "evidence", "source_digest")
_AMINO = dict(zip("ACDEFGHIKLMNPQRSTVWY",
                 "Ala Cys Asp Glu Phe Gly His Ile Lys Leu Met Asn Pro Gln Arg Ser Thr Val Trp Tyr".split()))
CONTEXT_TYPES = ("FUNCTION", "DISEASE", "PATHWAY", "TISSUE SPECIFICITY", "SUBCELLULAR LOCATION")


def uniprot_context(entry: dict, release: str, checked_on: str) -> dict:
    """Keep complete reviewed gene context, including its evidence qualifiers."""
    audit = entry.get("entryAudit") or {}
    comments = entry.get("comments") or []
    return {"entry_version": audit.get("entryVersion"),
            "sequence_version": audit.get("sequenceVersion"),
            "modified_on": audit.get("lastAnnotationUpdateDate"),
            "gene_ids": sorted({row["id"] for row in entry.get("uniProtKBCrossReferences") or []
                                if row.get("database") == "HGNC" and row.get("id")}),
            "release": release, "context_compared_on": checked_on,
            "protein_name": ((entry.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName", {}).get("value"),
            "functions": [row for row in comments if row.get("commentType") == "FUNCTION"],
            "contexts": [row for row in comments if row.get("commentType") in CONTEXT_TYPES[1:]]}


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def protein_changes(feature: dict) -> list[str]:
    """Describe exact single-residue source changes, without genomic conversion."""
    location = feature.get("location") or {}
    start, end = location.get("start") or {}, location.get("end") or {}
    alternative = feature.get("alternativeSequence") or {}
    original = alternative.get("originalSequence", "")
    if (start.get("modifier") != "EXACT" or end.get("modifier") != "EXACT"
            or start.get("value") != end.get("value") or original not in _AMINO):
        return []
    return ["p." + _AMINO[original] + str(start["value"]) + _AMINO[changed]
            for changed in alternative.get("alternativeSequences") or [] if changed in _AMINO]


def navigation_category(description: str) -> str:
    """A retrieval aid only: callers always retain the complete source wording."""
    text = description.lower()
    if re.search(r"\b(activity|binding|affinity|expression|stability|secretion|locali[sz]ation|"
                 r"transport|catalytic|kinetic|phosphorylation|degrad|traffick|splicing|"
                 r"channel|current|conductance|protein level|mrna|enzyme|folding|signall?ing|"
                 r"plasma level|serum level|glycosylation|aggregation|cleavage|uptake|"
                 r"function|transcription|translation)", text):
        return "functional_text_candidate"
    if re.search(r"associat|susceptibil|risk|protect|correlat", text):
        return "association_text"
    return "other_source_annotation"


def uniprot_record(entry: dict, feature: dict, release: str, checked_on: str,
                   target_ids: set[str]) -> dict | None:
    """Normalize one reviewed source feature; no patient data is accepted."""
    kind = feature.get("type")
    if kind not in ("Natural variant", "Mutagenesis"):
        return None
    all_ids = sorted({row["id"] for row in entry.get("uniProtKBCrossReferences") or []
                      if row.get("database") == "HGNC" and row.get("id")})
    genes = sorted(set(all_ids) & target_ids)
    if not genes:
        return None
    accession = entry.get("primaryAccession")
    if not accession:
        raise ValueError("UniProt feature has no reference accession")
    identity = {"protein": accession, "type": kind, "location": feature.get("location"),
                "alternative": feature.get("alternativeSequence"),
                "description": feature.get("description"), "evidence": feature.get("evidences")}
    feature_id = feature.get("featureId")
    identifier = accession + ":" + (feature_id or digest(identity)[:24])
    description = str(feature.get("description") or "")
    pmids = sorted({str(row["id"]) for row in feature.get("evidences") or []
                    if row.get("source") == "PubMed" and row.get("id")})
    rsids = sorted({row["id"] for row in feature.get("featureCrossReferences") or []
                    if row.get("database") == "dbSNP" and re.fullmatch(r"rs\d+", str(row.get("id", "")))}
                   | set(re.findall(r"\brs\d+", description)))
    record = {"id": identifier, "gene_ids": genes, "protein_gene_ids": all_ids,
              "protein": accession, "feature_id": feature_id, "type": kind,
              "location": feature.get("location") or {},
              "alternative": feature.get("alternativeSequence") or {},
              "protein_changes": protein_changes(feature), "rsids": rsids,
              "description": description, "pmids": pmids,
              "evidence": feature.get("evidences") or [],
              "category": navigation_category(description),
              "gene_mapping": "single_gene" if len(all_ids) == 1 else "shared_protein",
              "genomic_mapping": "not_verified", "human_genotype_dose_model": False,
              "source_release": release, "source_compared_on": checked_on,
              "primary_study_checked_on": None}
    record["source_digest"] = digest({key: value for key, value in record.items()
                                      if key not in ("source_release", "source_compared_on",
                                                     "primary_study_checked_on", "category")})
    return record


@lru_cache(maxsize=6)
def _load(path: str, modified: int, size: int) -> dict:
    del modified, size  # The cache key includes both; content is resolved only once.
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def catalogue(name: str = ANNOTATIONS) -> dict:
    """Use the existing local/bundled precedence without localizing the whole base."""
    path = core.knowledge_path(name)
    try:
        stat = path.stat()
    except OSError:
        return {}
    value = _load(str(path), stat.st_mtime_ns, stat.st_size)
    bundled = core._KNOWLEDGE_DIR / name
    if name == ANNOTATIONS and path != bundled:
        try:
            bundled_stat = bundled.stat()
            metadata = _metadata(str(bundled), bundled_stat.st_mtime_ns)
            revision = metadata.get("authored_revision")
            if revision and revision != (value.get("_meta") or {}).get("authored_revision"):
                authored = _load(str(bundled), bundled_stat.st_mtime_ns, bundled_stat.st_size)
                value = _merge_authored(value, authored)
        except OSError:
            pass
    return value


def _merge_authored(local: dict, bundled: dict) -> dict:
    """A newer product model must not disappear behind a later source import."""
    flags = ("review_required", "review_reason", "interpretation_blocked")
    previous = {row["model_id"]: row for row in local.get("models") or []}
    models = []
    for model in bundled.get("models") or []:
        old = previous.get(model["model_id"]) or {}
        retained = {key: old[key] for key in flags if key in old}
        models.append({**model, **retained})
    previous_contexts = {row["context_id"]: row for row in local.get("supported_contexts") or []}
    contexts = [{**row, **({"review_required": True} if previous_contexts.get(row["context_id"], {}).get("review_required") else {})}
                for row in bundled.get("supported_contexts") or []]
    return {**local, "genes": {**(local.get("genes") or {}), **(bundled.get("genes") or {})},
            "models": models, "supported_contexts": contexts,
            "_meta": {**(local.get("_meta") or {}),
                      "authored_revision": bundled["_meta"]["authored_revision"],
                      "has_interpretation_blocks": any(row.get("interpretation_blocked") for row in models)}}


@lru_cache(maxsize=6)
def _metadata(path: str, modified: int) -> dict:
    del modified
    try:
        return core.knowledge_metadata(Path(path))
    except (OSError, ValueError):
        return {}


def catalogue_metadata() -> dict:
    path = core.knowledge_path(ANNOTATIONS)
    try:
        return _metadata(str(path), path.stat().st_mtime_ns)
    except OSError:
        return {}


@lru_cache(maxsize=12)
def _file_hash(path: str, modified: int, size: int) -> str:
    del modified, size
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def cpic_override(name: str) -> dict | None:
    """An accepted snapshot can carry the existing CPIC import atomically."""
    if not catalogue_metadata().get("has_cpic_overlay"):
        return None
    overlay = catalogue().get("cpic_overlay") or {}
    path = core.knowledge_path(name)
    try:
        stat = path.stat()
        expected = (overlay.get("base_hashes") or {}).get(name)
        if not expected or _file_hash(str(path), stat.st_mtime_ns, stat.st_size) != expected:
            return None  # A subsequent standalone CPIC refresh takes precedence.
    except OSError:
        return None
    return overlay.get("data" if name == "cpic_drug_gene.json" else "pairs")


def needs_source_review(gene: str, variant: str) -> bool:
    """Withhold a dependent personal conclusion, retaining source knowledge."""
    if not catalogue_metadata().get("has_interpretation_blocks"):
        return False
    identifier = gene_id(gene)
    return any(row.get("interpretation_blocked") and variant in (row.get("variant_ids") or [])
               and (row.get("hgnc_id") == identifier if identifier else row.get("gene") == gene)
               for row in catalogue().get("models") or [])


def records(data: dict):
    """Expand the tabular on-disk encoding without changing the public API."""
    fields = data.get("record_fields")
    meta = data.get("_meta") or {}
    for raw in data.get("records") or []:
        row = dict(zip(fields, raw)) if fields else dict(raw)
        row.setdefault("protein_changes", protein_changes({"location": row.get("location"),
                                                          "alternativeSequence": row.get("alternative")}))
        row.setdefault("category", navigation_category(row.get("description", "")))
        row.setdefault("gene_mapping", "single_gene" if len(row.get("protein_gene_ids") or []) == 1 else "shared_protein")
        row.setdefault("genomic_mapping", "not_verified")
        row.setdefault("human_genotype_dose_model", False)
        row.setdefault("source_release", meta.get("release"))
        row.setdefault("source_compared_on", meta.get("updated"))
        row.setdefault("primary_study_checked_on", None)
        yield row


@lru_cache(maxsize=3)
def _indices(path: str, modified: int, size: int, authored_stamp: int = 0) -> tuple[dict, dict, dict]:
    del authored_stamp
    data = catalogue()
    aliases: dict[str, str] = {}
    genes: dict[str, list[dict]] = {}
    variants: dict[str, set[str]] = {}
    for gene_id, gene in (data.get("genes") or {}).items():
        aliases[gene_id.upper()] = gene_id
        for label in [gene.get("symbol"), *(gene.get("aliases") or [])]:
            if label:
                previous = aliases.get(str(label).upper())
                aliases[str(label).upper()] = gene_id if previous in (None, gene_id) else ""
    for record in records(data):
        for gene_id in record.get("gene_ids") or []:
            genes.setdefault(gene_id, []).append(record)
        for identifier in [record.get("id"), record.get("feature_id"),
                           *(record.get("rsids") or []), *(record.get("protein_changes") or [])]:
            if identifier:
                variants.setdefault(str(identifier).casefold(), set()).add(record["id"])
    return aliases, genes, variants


def index() -> tuple[dict, dict, dict]:
    path = core.knowledge_path(ANNOTATIONS)
    try:
        stat = path.stat()
    except OSError:
        return {}, {}, {}
    bundled = core._KNOWLEDGE_DIR / ANNOTATIONS
    authored_stamp = bundled.stat().st_mtime_ns if bundled.is_file() else 0
    return _indices(str(path), stat.st_mtime_ns, stat.st_size, authored_stamp)


def gene_id(label: str) -> str:
    return index()[0].get(str(label).strip().upper(), "")


def local_text(value: Any) -> str:
    from .i18n import lang
    if isinstance(value, dict):
        return local_text(value.get(lang()) or value.get("en") or value.get("ru")
                          or value.get("label") or value.get("summary") or "")
    if isinstance(value, list):
        return "\n".join(local_text(row) for row in value if row)
    return str(value or "")


def model_references(gene: str, variant: str = "") -> list[dict]:
    """Retain authored meanings, including incomplete passports and related loci."""
    identifier = gene_id(gene)
    data = catalogue()
    aliases = index()[0]
    symbol = str((data.get("genes", {}).get(identifier) or {}).get("symbol") or gene).upper()
    from .i18n import t
    output = []
    for model in catalogue(MODELS).get("models") or []:
        variants = model.get("variant_ids") or []
        if variant and variant not in variants and variant != model.get("model_id"):
            continue
        locus = str(model.get("gene") or "").upper()
        target = str(model.get("studied_target_gene") or "").upper()
        related = bool(target and target == symbol)
        model_gene_id = model.get("hgnc_id") or aliases.get(locus)
        unresolved = not (model_gene_id and model_gene_id in (data.get("genes") or {}))
        same_gene = bool(locus and locus == symbol) or bool(identifier and model_gene_id == identifier)
        unassigned = not locus or locus in ("UNASSIGNED", "GENE NOT ASSIGNED")
        explicit_unassigned = symbol in ("UNASSIGNED", "GENE NOT ASSIGNED") and unassigned
        if not same_gene and not related and not explicit_unassigned and not (variant and unresolved):
            continue
        genotypes = []
        for row in model.get("genotypes") or []:
            meaning = row.get("meaning") or {"en": row.get("meaning_en"), "ru": row.get("meaning_ru")}
            direction = row.get("direction_text") or row.get("direction") or {"en": row.get("direction_en"), "ru": row.get("direction_ru")}
            genotypes.append({"genotype": local_text(row.get("genotype_label") or {"en": row.get("genotype"), "ru": row.get("genotype_ru") or row.get("genotype")}), "meaning": local_text(meaning),
                              "direction": local_text(direction),
                              "normality_note": local_text(row.get("normality_note")),
                              "normality_basis": row.get("normality_basis") or model.get("normality_basis"),
                              "classification": row.get("genotype_classification"),
                              "observed_genotype_effect": row.get("observed_genotype_effect", False)})
        frame = local_text(model.get("source_allele_frame") or model.get("allele_frame"))
        frame_label = t("variant_knowledge.frame." + frame) if frame in (
            "protein_genotype", "retained_variant_context_no_genomic_conversion",
            "study_not_automatically_mapped_to_personal_forward_reading", "study_notation",
            "study_notation_NCBI_Build36_not_mapped_to_GRCh38", "forward_genomic_GRCh38_exact_ClinVar_allele",
            "forward_genomic_GRCh38", "unresolved", "study_notation_not_mapped_to_GRCh38",
            "source_study_notation_not_automatically_genomic_REF", "combined_diplotype_required",
            "study_minor_allele_not_resolved", "study_promoter_notation",
            "protein_allele_construct_not_observed_diploid_genotype") else frame
        checked = model.get("checked_on") or model.get("source_checked_on")
        from .scientific_review import source_refresh_status
        output.append({"id": model.get("model_id"), "gene": model.get("gene"),
                       "variant_ids": variants, "kind": model.get("model_kind"),
                       "related_locus": related and not same_gene,
                       "gene_assignment_unresolved": unresolved,
                       "studied_target_gene": model.get("studied_target_gene"),
                       "gene_mapping_note": local_text(model.get("gene_mapping_note")),
                       "allele_frame": frame, "allele_frame_label": frame_label,
                       "recorded_effect": local_text(model.get("effect") or model.get("outcome_label") or model.get("endpoint")),
                       "effect": t("variant_knowledge.sequence_frame") if model.get("model_kind") == "unresolved_reference"
                       else local_text(model.get("effect") or model.get("outcome_label") or model.get("endpoint")),
                       "direction": local_text(model.get("direction_text") or model.get("direction")),
                       "comparator": local_text(model.get("comparator")),
                       "normality_basis": model.get("normality_basis"),
                       "applicability": local_text(model.get("applicability_note") or model.get("applicability") or model.get("applicable_context")),
                       "limitations": local_text(model.get("limitations") or model.get("limits")),
                       "comparison_design": local_text(model.get("comparison_design")),
                       "knowledge_gaps": [t("variant_knowledge.missing_" + key) for key, present in (
                           ("direction", model.get("direction_text") or model.get("direction")),
                           ("comparator", model.get("comparator")),
                           ("allele_frame", frame), ("sources", model.get("sources"))) if not present],
                       "genotypes": genotypes, "sources": model.get("sources") or [],
                       "checked_on": checked,
                       "freshness": source_refresh_status(checked, date.today()),
                       "level": model.get("retained_evidence_level") or model.get("level"),
                       "review_required": bool(model.get("review_required")),
                       "review_reason": model.get("review_reason"),
                       "status": model.get("status"),
                       "scope": "conditional_reference_not_personal_interpretation",
                       "clinical_eligibility_upgrade": False})
    priority = {"validated_full_diplotype": 0, "primary_genotype_effect": 1,
                "joint_haplotype_effect": 2, "source_scoped_association": 3,
                "conditional_pgx_marker": 4, "retained_variant_context": 5,
                "clinical_inheritance_context": 6, "clinical_classification_context": 7,
                "primary_knowledge_boundary": 8, "unresolved_reference": 9}
    output.sort(key=lambda row: (row["related_locus"], priority.get(str(row.get("kind") or ""), 5), row["id"] or ""))
    return output


def statistics(gene: str) -> dict:
    identifier = gene_id(gene)
    rows = index()[1].get(identifier) or []
    models = model_references(gene)
    full = [row for row in catalogue().get("supported_contexts") or []
            if row.get("hgnc_id") == identifier and not row.get("review_required")
            and (row.get("outcome_label") or row.get("endpoint"))
            and (row.get("applicability_note") or row.get("applicability"))
            and all(row.get(key) for key in ("variant_identifier", "comparator", "sources", "checked_on"))]
    return {"gene_id": identifier, "source_annotation_count": len(rows),
            "natural_annotation_count": sum(row["type"] == "Natural variant" for row in rows),
            "experimental_annotation_count": sum(row["type"] == "Mutagenesis" for row in rows),
            "recorded_model_count": len(models),
            "fully_described_link_count": len(full),
            "variant_meaning_model_count": sum(row.get("kind") in (
                "primary_genotype_effect", "validated_full_diplotype", "conditional_pgx_marker",
                "joint_haplotype_effect", "source_scoped_association", "retained_variant_context") for row in models),
            "genotype_meaning_count": sum(len(row["genotypes"]) for row in models),
            "source_annotations_are_genotype_interpretations": False}


def reference(gene: str, variant: str = "", *, offset: int = 0, limit: int = 10,
              kind: str = "natural", query: str = "") -> dict:
    """Return paged source knowledge; never infer the active person's phenotype."""
    if kind not in ("natural", "experimental", "all"):
        raise ValueError("Unknown source annotation kind")
    identifier = gene_id(gene)
    data = catalogue()
    models = model_references(gene, variant)
    needle = query.strip().casefold()
    if needle:
        models = [model for model in models if needle in " ".join(
            [model["effect"], *model["variant_ids"]]).casefold()]
    if not identifier or not data:
        return {"schema": 1, "gene": gene, "gene_id": None, "variant": variant,
                "records": [], "models": models, "total": 0, "offset": 0,
                "kind": kind, "query": query,
                "limit": max(1, min(int(limit), 100)), "next_offset": None,
                "status": "gene_identity_unresolved" if models else "gene_not_in_reference_catalogue",
                "source_release": (data.get("_meta") or {}).get("release"),
                "source_compared_on": (data.get("_meta") or {}).get("updated"),
                "clinical_eligibility_upgrade": False}
    aliases, by_gene, by_variant = index()
    del aliases
    records = list(by_gene.get(identifier) or [])
    if variant:
        matching = by_variant.get(variant.casefold(), set())
        records = [row for row in records if row["id"] in matching]
    if kind in ("natural", "experimental"):
        wanted = "Natural variant" if kind == "natural" else "Mutagenesis"
        records = [row for row in records if row["type"] == wanted]
    needle = query.strip().casefold()
    if needle:
        records = [row for row in records if needle in " ".join(
            [row["id"], row["description"], *row["rsids"], *row["protein_changes"]]).casefold()]
    records.sort(key=lambda row: (row.get("category") != "functional_text_candidate", row["id"]))
    offset, limit = max(0, int(offset)), max(1, min(int(limit), 100))
    selected = records[offset:offset + limit]
    from .scientific_review import source_refresh_status
    from .i18n import t
    rows = []
    for record in selected:
        protein = (data.get("proteins") or {}).get(record["protein"]) or {}
        rows.append({**record, "source": {**{key: protein.get(key) for key in
                     ("entry_version", "sequence_version", "modified_on", "gene_ids", "release")},
                     "url": "https://www.uniprot.org/uniprotkb/" + record["protein"] + "/entry",
                     "publications": ["https://pubmed.ncbi.nlm.nih.gov/" + pmid + "/" for pmid in record["pmids"]]},
                     "freshness": source_refresh_status(record.get("source_compared_on"), date.today()),
                     "scope": "source_annotation_not_personal_genotype_interpretation"})
    checks = data.get("source_checks") or {}
    ncbi_id = str((data["genes"][identifier] or {}).get("ncbi_id") or "")
    keys = {"hgnc:" + identifier, "gencc:" + identifier, "ncbi_gene:" + ncbi_id}
    for model in models:
        keys.update("refsnp:" + value for value in model["variant_ids"] if re.fullmatch(r"rs\d+", value))
        keys.update("pubmed:" + str(source["pmid"]) for source in model["sources"]
                    if isinstance(source, dict) and source.get("pmid"))
    source_checks = [{"key": key, **{field: checks[key].get(field) for field in
                     ("provider", "scope", "url", "version", "compared_on", "attempted_on", "status", "error")}}
                     for key in sorted(keys) if key in checks]
    for check in source_checks:
        if check.get("scope"):
            check["scope_label"] = t("variant_knowledge.check_scope." + check["scope"])
        if check.get("status"):
            check["status_label"] = t("variant_knowledge.check_status." + check["status"])
    functions = []
    for accession, protein in (data.get("proteins") or {}).items():
        if identifier not in (protein.get("gene_ids") or []):
            continue
        for comment in protein.get("functions") or []:
            for value in comment.get("texts") or []:
                if value.get("value"):
                    functions.append({"text": (str(comment["molecule"]) + ": " if comment.get("molecule") else "") + value["value"],
                                      "molecule": comment.get("molecule"),
                                      "shared_protein": len(protein.get("gene_ids") or []) > 1,
                                      "provider": "UniProt", "protein": accession,
                                      "scope": "gene_function_not_variant_effect", "release": protein.get("release"),
                                      "compared_on": protein.get("context_compared_on") or (data.get("_meta") or {}).get("updated"),
                                      "url": "https://www.uniprot.org/uniprotkb/" + accession + "/entry"})
    gene_check = checks.get("ncbi_gene:" + ncbi_id) or {}
    summary = (gene_check.get("data") or {}).get("summary")
    if summary:
        functions.append({"text": summary, "provider": "NCBI Gene", "compared_on": gene_check.get("compared_on"),
                          "scope": "gene_function_not_variant_effect", "url": "https://www.ncbi.nlm.nih.gov/gene/" + ncbi_id})
    from . import gene_information
    return {"schema": 1, "gene": (data["genes"][identifier] or {}).get("symbol") or gene,
            "gene_id": identifier, "variant": variant, "kind": kind, "query": query,
            "records": rows, "models": models, "functions": functions, "source_checks": source_checks,
            "gene_information": gene_information.reference(data, identifier),
            "total": len(records), "offset": offset, "limit": limit,
            "next_offset": offset + limit if offset + limit < len(records) else None,
            "source_release": (data.get("_meta") or {}).get("release"),
            "source_compared_on": (data.get("_meta") or {}).get("updated"),
            "clinical_eligibility_upgrade": False}


def lines(data: dict) -> list[str]:
    """CLI, reports and agent responses carry the same self-contained meanings."""
    from .i18n import t
    if not data:
        return []
    output = [t("variant_knowledge.title") + " · " + data.get("gene", "")]
    from . import gene_information
    if data.get("gene_information"):
        output.extend(gene_information.lines(data["gene_information"]))
    else:
        for function in data.get("functions") or []:
            output.extend([t("reference_updates.function") + ": " + function["text"], function["url"]])
    for check in data.get("source_checks") or []:
        output.append(" · ".join(str(check.get(key) or "—") for key in
                               ("provider", "scope", "status", "compared_on", "url")))
    for model in data.get("models") or []:
        output.append(" · ".join(model["variant_ids"]))
        for key in ("effect", "direction", "comparator", "allele_frame", "applicability"):
            if model.get(key):
                value = str(model.get("allele_frame_label") if key == "allele_frame" else model[key])
                output.extend(t("variant_knowledge." + key) + ": " + line for line in value.splitlines())
        output.append(t("variant_knowledge.normality." + (model.get("normality_basis") or "not_established")))
        if model.get("gene_assignment_unresolved"):
            output.append(t("variant_knowledge.unresolved_gene_assignment"))
        output.extend(model.get("knowledge_gaps") or [])
        if model.get("review_required"):
            output.append(t("variant_knowledge.review_source_missing") if model.get("review_reason") == "source_missing"
                          else t("variant_knowledge.review_required"))
        level = model.get("level")
        output.append(t("variant_knowledge.level", level=" / ".join(map(str, level)) if isinstance(level, list) else str(level))
                      if level else t("variant_knowledge.level_unassigned"))
        output.append(t("variant_knowledge.checked") + ": " + str(model.get("checked_on") or "—"))
        for genotype in model.get("genotypes") or []:
            output.append(str(genotype["genotype"]) + ": " + genotype["meaning"])
            if genotype.get("direction"):
                output.append(t("variant_knowledge.direction") + ": " + genotype["direction"])
        output.extend(value for value in (model.get("gene_mapping_note"), model.get("comparison_design"), model.get("limitations")) if value)
        for source in model.get("sources") or []:
            url = source if isinstance(source, str) else source.get("url")
            if url:
                output.append(url)
    output.append(t("variant_knowledge.page", shown=len(data.get("records") or []),
                    total=data.get("total", 0), offset=data.get("offset", 0) + 1 if data.get("records") else 0))
    for row in data.get("records") or []:
        output.append(" · ".join([row["id"], *row.get("protein_changes", []), *row.get("rsids", [])]))
        output.extend([t("variant_knowledge.source_scope"), row["description"],
                       t("variant_knowledge.protein_not_genotype"), t("variant_knowledge.level_unassigned"),
                       t("variant_knowledge.retrieved") + ": " + str(row.get("source_compared_on") or "—"),
                       t("variant_knowledge.version") + ": " + str(row.get("source_release") or "—")])
        if row["gene_mapping"] == "shared_protein":
            output.append(t("variant_knowledge.shared_protein"))
        source = row.get("source") or {}
        output.extend(value for value in [source.get("url"), *source.get("publications", [])] if value)
    if not data.get("models") and not data.get("records"):
        output.append(t("variant_knowledge.no_matching_knowledge"))
    return output


def report(data: dict) -> str:
    return "\n".join(lines(data))
