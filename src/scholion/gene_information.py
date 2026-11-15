"""Source-backed gene information shared by every reference surface.

Gene function, disease validity and variant effects are different claims. This
module presents source wording, including negative evidence, without deriving a
patient diagnosis, a reference-as-normal rule or a genotype dose response.
"""
from __future__ import annotations

from datetime import date

from . import core
from .scientific_review import source_refresh_status


def _publications(value) -> list[str]:
    found = set()
    def visit(item):
        if isinstance(item, dict):
            if item.get("source") == "PubMed" and str(item.get("id", "")).isdigit():
                found.add("https://pubmed.ncbi.nlm.nih.gov/" + str(item["id"]) + "/")
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    return sorted(found)


def _texts(comment: dict) -> list[str]:
    texts = [row["value"] for row in comment.get("texts") or [] if row.get("value")]
    disease = comment.get("disease") or {}
    if disease:
        texts.insert(0, ": ".join(filter(None, [disease.get("diseaseId"), disease.get("description")])) )
    for row in (comment.get("note") or {}).get("texts") or []:
        if row.get("value"):
            texts.append(row["value"])
    for row in comment.get("subcellularLocations") or []:
        texts.append("; ".join(str(row[key].get("value")) for key in
                               ("location", "topology", "orientation") if row.get(key, {}).get("value")))
    texts = list(dict.fromkeys(text for text in texts if text))
    if texts and comment.get("molecule"):
        texts.insert(0, str(comment["molecule"]) + ":")
    return texts


def reference(data: dict, identifier: str) -> dict:
    """A complete gene-level context; filtering variants never removes it."""
    checks = data.get("source_checks") or {}
    gene = (data.get("genes") or {}).get(identifier) or {}
    identity_check = checks.get("hgnc:" + identifier) or {}
    identity = identity_check.get("data") or {}
    ncbi = checks.get("ncbi_gene:" + str(gene.get("ncbi_id") or "")) or {}
    ncbi_data = ncbi.get("data") or {}
    observations = []
    for accession, protein in (data.get("proteins") or {}).items():
        if identifier not in (protein.get("gene_ids") or []):
            continue
        compared = protein.get("context_compared_on") or (data.get("_meta") or {}).get("updated")
        for comment in [*(protein.get("functions") or []), *(protein.get("contexts") or [])]:
            texts = _texts(comment)
            if not texts:
                continue
            observations.append({"kind": comment.get("commentType"), "text": "\n".join(texts),
                "provider": "UniProt", "record": accession, "release": protein.get("release"),
                "compared_on": compared, "freshness": source_refresh_status(compared, date.today()),
                "url": "https://www.uniprot.org/uniprotkb/" + accession + "/entry",
                "publications": _publications(comment), "source_evidence": comment,
                "scope": "gene_context_not_individual_variant_classification",
                "shared_protein": len(protein.get("gene_ids") or []) > 1})
    if ncbi_data.get("summary"):
        observations.append({"kind": "FUNCTION", "text": ncbi_data["summary"],
            "provider": "NCBI Gene", "record": str(gene.get("ncbi_id")),
            "compared_on": ncbi.get("compared_on"), "status": ncbi.get("status"),
            "freshness": source_refresh_status(ncbi.get("compared_on"), date.today()),
            "url": "https://www.ncbi.nlm.nih.gov/gene/" + str(gene.get("ncbi_id")),
            "scope": "gene_context_not_individual_variant_classification", "publications": []})
    if not any(row["kind"] == "FUNCTION" for row in observations):
        candidates = [(core._read_knowledge(name).get("genes") or {}).get(gene.get("symbol")) or {}
                      for name in ("gene_curation.json", "gene_function_context.json")]
        curated = next((row for row in candidates if row.get("function_status") in
                        ("curated_function", "function_annotation") and isinstance(row.get("description"), str)
                        and row.get("source")), {})
        if curated:
            observations.append({"kind": "FUNCTION", "text": curated["description"],
                "provider": "Scholion curated source summary", "record": identifier,
                "compared_on": curated.get("checked_on"),
                "freshness": source_refresh_status(curated.get("checked_on"), date.today()),
                "url": curated["source"], "publications": curated.get("additional_sources") or [],
                "scope": "curated_gene_function_not_individual_variant_classification"})
    gencc = checks.get("gencc:" + identifier) or {}
    assertions = []
    if isinstance(gencc.get("data"), dict):
        for submission, row in gencc["data"].items():
            assertions.append({"disease": row.get("disease_title") or row.get("disease_curie"),
                "disease_id": row.get("disease_curie"), "validity": row.get("classification_title"),
                "inheritance": row.get("moi_title"), "submitter": row.get("submitter_title"),
                "submission": submission, "submitted_on": row.get("submitted_as_date"),
                "url": row.get("submitted_as_public_report_url"),
                "pmids": row.get("submitted_as_pmids")})
        clinical_source = {key: gencc.get(key) for key in ("provider", "compared_on", "status", "url")}
    else:
        book = core._read_knowledge("gencc_inheritance.json")
        stored = (book.get("genes") or {}).get(gene.get("symbol")) or {}
        if stored.get("hgnc_id") == identifier:
            for row in stored.get("submissions") or []:
                assertions.append({"disease": row.get("disease"), "disease_id": row.get("disease_id"),
                    "validity": row.get("classification"), "inheritance": row.get("moi_code"),
                    "submission": ", ".join(row.get("submission_ids") or [])})
        meta = book.get("_meta") or {}
        clinical_source = {"provider": "GenCC", "compared_on": meta.get("downloaded"),
                           "url": meta.get("source_url"), "status": "retained_snapshot"}
    clinical_source["freshness"] = source_refresh_status(clinical_source.get("compared_on"), date.today())
    return {"schema": 1, "gene_id": identifier, "symbol": gene.get("symbol"),
        "identity": {"name": identity.get("name") or ncbi_data.get("description"),
                     "locus_type": identity.get("locus_type") or ncbi_data.get("gene_type"),
                     "location": identity.get("location"), "ncbi_id": gene.get("ncbi_id"),
                     "compared_on": identity_check.get("compared_on"),
                     "url": "https://www.genenames.org/data/gene-symbol-report/#!/hgnc_id/" + identifier},
        "observations": observations, "clinical_assertions": assertions, "clinical_source": clinical_source,
        "dimensions": {"identity": bool(identity or ncbi_data),
                       "source_function": any(row["kind"] == "FUNCTION" for row in observations),
                       "disease_context": bool(assertions) or any(row["kind"] == "DISEASE" for row in observations),
                       "established_gene_disease": any(row.get("validity") in ("Definitive", "Strong", "Moderate") for row in assertions)},
        "normality_from_reference": False, "human_genotype_inferred": False}


def lines(data: dict) -> list[str]:
    from .i18n import t
    if not data:
        return []
    identity = data.get("identity") or {}
    output = [t("gene_information.title"), " · ".join(str(identity[key]) for key in
              ("name", "locus_type", "location") if identity.get(key))]
    for row in data.get("observations") or []:
        output.extend([t("gene_information.kind." + row["kind"]) + ": " + row["text"],
                       " · ".join(str(row.get(key) or "—") for key in ("provider", "record", "release", "compared_on")),
                       row["url"], *row.get("publications", [])])
        if row.get("shared_protein"):
            output.append(t("variant_knowledge.shared_protein"))
    if data.get("clinical_assertions"):
        output.append(t("gene_information.clinical_scope"))
        for row in data["clinical_assertions"]:
            output.append(" · ".join(str(row.get(key) or "—") for key in
                          ("disease", "inheritance", "validity", "submitter", "submission", "submitted_on", "pmids", "url")))
        output.append(str(data["clinical_source"].get("url") or ""))
    return output
