"""Exact public-record checks for the sources behind retained reference models.

These adapters compare database assertions, identity and publication records.
They do not translate an rsID into an effect allele or renew a primary study
interpretation. Every failed or unsupported check keeps its previous witness.
"""
from __future__ import annotations

import csv
from datetime import date
import html
import io
import json
import re
import time
import unicodedata
from typing import Any
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

from . import net, variant_annotations as variant_data

HGNC_URL = "https://storage.googleapis.com/public-download-files/hgnc/json/json/hgnc_complete_set.json"
GENCC_URL = "https://thegencc.org/download/action/submissions-export-tsv?format=new"


def _text(value) -> str | None:
    if value is None:
        return None
    value = re.sub(r"<[^>]+>", " ", html.unescape(str(value)))
    return " ".join(unicodedata.normalize("NFC", value).split())


def _stable_list(value) -> list:
    if isinstance(value, dict):
        value = value.get("pubType") or value.get("commentCorrection") or [value]
    return sorted(value or [], key=lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False))


def publication(record: dict) -> dict:
    identifier = str(record.get("pmid") or record.get("id") or "")
    if record.get("source") != "MED" or not identifier.isdigit():
        raise ValueError("The publication response is not the requested MED record")
    selected = {"pmid": identifier, "title": _text(record.get("title")), "doi": record.get("doi"),
                "abstract_sha256": variant_data.digest(_text(record.get("abstractText"))),
                "abstract_present": "abstractText" in record,
                "retraction_flag_supplied": "isRetracted" in record,
                "is_retracted": record.get("isRetracted"),
                "publication_types": _stable_list(record.get("pubTypeList")),
                "corrections": _stable_list(record.get("commentCorrectionList"))}
    return selected


def hgnc_record(record: dict) -> dict:
    if not re.fullmatch(r"HGNC:\d+", str(record.get("hgnc_id", ""))):
        raise ValueError("Missing exact HGNC identity")
    return {key: record.get(key) for key in ("hgnc_id", "symbol", "name", "locus_type", "location", "status", "entrez_id",
                                            "uniprot_ids", "refseq_accession", "mane_select",
                                            "ensembl_gene_id", "alias_symbol", "prev_symbol")}


def ncbi_gene(record: dict, expected_hgnc: str = "") -> dict:
    identifier = str(record.get("gene_id") or record.get("uid") or "")
    taxon = str(record.get("tax_id") or (record.get("organism") or {}).get("taxid") or "")
    if not identifier.isdigit() or taxon != "9606":
        raise ValueError("NCBI Gene identity/taxon was not verified")
    authority = record.get("nomenclature_authority") or {}
    hgnc = authority.get("identifier")
    if expected_hgnc and hgnc and hgnc != expected_hgnc:
        raise ValueError("NCBI Gene and HGNC identify different genes")
    summary = record.get("summary")
    if isinstance(summary, list):
        summary = "\n".join(row.get("description", "") for row in summary)
    return {"gene_id": identifier, "symbol": record.get("symbol") or record.get("name"),
            "tax_id": taxon, "summary": _text(summary),
            "description": record.get("description"), "gene_type": record.get("type"),
            "chromosomes": record.get("chromosomes") or [],
            "reference_standards": record.get("reference_standards") or []}


def refsnp(record: dict, identifier: str) -> dict:
    number = str(identifier).removeprefix("rs")
    if str(record.get("refsnp_id")) != number:
        raise ValueError("The RefSNP response identifies another rsID")
    state = next((key for key in ("primary_snapshot_data", "merged_snapshot_data",
                                  "withdrawn_snapshot_data", "unsupported_snapshot_data")
                  if key in record), None)
    if not state:
        raise ValueError("Unknown RefSNP record state")
    selected = {"rsid": "rs" + number, "state": state,
                "last_update_build_id": record.get("last_update_build_id"),
                "last_update_date": record.get("last_update_date")}
    if state == "primary_snapshot_data":
        placements = []
        for row in record[state].get("placements_with_allele") or []:
            context = row.get("placement_annot") or {}
            placements.append({"reference": row.get("seq_id"),
                               "assemblies": context.get("seq_id_traits_by_assembly") or [],
                               "opposite_orientation": context.get("is_aln_opposite_orientation"),
                               "mismatch": context.get("is_mismatch"),
                               "alleles": [a.get("allele") for a in row.get("alleles") or []],
                               "hgvs": [a.get("hgvs") for a in row.get("alleles") or []]})
        selected["placements"] = placements
    else:
        selected["state_data"] = record[state]
    return selected


def _xml(value: str) -> ET.Element:
    root = ET.fromstring(value)
    if root.tag.startswith("{"):
        raise ValueError("Unknown XML namespace; the exact source schema needs review")
    return root


def _classification(element: ET.Element | None) -> dict:
    if element is None:
        return {}
    description = element.find("Description")
    return {"description": element.findtext("Description"), "review_status": element.findtext("ReviewStatus"),
            "evaluated_on": description.get("DateLastEvaluated") if description is not None else None}


def clinvar(value: str, identifier: str) -> dict:
    root = _xml(value)
    if root.tag != "ClinVarResult-Set":
        raise ValueError("Unknown ClinVar response schema")
    identifier = identifier.split(".")[0]
    if identifier.startswith("VCV"):
        matches = [row for row in root.findall("VariationArchive") if row.get("Accession") == identifier]
        if len(matches) != 1:
            raise ValueError("The exact VCV accession is absent or ambiguous")
        record = matches[0]
        allele = record.find("ClassifiedRecord/SimpleAllele")
        if allele is None:
            raise ValueError("ClinVar haplotype/genotype requires its own allele model")
        conditions = []
        for row in record.findall("ClassifiedRecord/RCVList/RCVAccession"):
            conditions.append({"accession": row.get("Accession"), "version": row.get("Version"),
                               "conditions": [{"database": c.get("DB"), "id": c.get("ID"), "name": c.text}
                                              for c in row.findall("ClassifiedConditionList/ClassifiedCondition")],
                               "germline": _classification(row.find("RCVClassifications/GermlineClassification"))})
        locations = [dict(row.attrib) for row in allele.findall("Location/SequenceLocation")]
        return {"accession": identifier, "version": record.get("Version"),
                "variation_id": record.get("VariationID"), "record_status": record.findtext("RecordStatus"),
                "genes": [dict(row.attrib) for row in allele.findall("GeneList/Gene")],
                "allele_locations": locations,
                "germline_aggregate": _classification(record.find("ClassifiedRecord/Classifications/GermlineClassification")),
                "condition_assertions": conditions}
    matches = [row for row in root.findall("ClinVarSet/ReferenceClinVarAssertion")
               if any(a.get("Acc") == identifier for a in row.findall("ClinVarAccession"))]
    if len(matches) != 1:
        raise ValueError("The exact RCV accession is absent or ambiguous")
    record = matches[0]
    accession = next(a for a in record.findall("ClinVarAccession") if a.get("Acc") == identifier)
    measures = record.findall("MeasureSet/Measure")
    if not measures:
        raise ValueError("The exact RCV allele is absent")
    conditions = [dict(row.attrib) for row in record.findall("TraitSet/Trait/XRef")]
    return {"accession": identifier, "version": accession.get("Version"),
            "conditions": conditions,
            "condition_names": [row.text for row in record.findall('TraitSet/Trait/Name/ElementValue[@Type="Preferred"]')],
            "germline": _classification(record.find("Classifications/GermlineClassification")),
            "alleles": [{"type": row.get("Type"), "id": row.get("ID"),
                         "canonical_spdi": row.findtext("CanonicalSPDI"),
                         "locations": [dict(location.attrib) for location in row.findall("SequenceLocation")]}
                        for row in measures]}


def refseq(value: str, identifier: str) -> dict:
    if not re.fullmatch(r"N[MR]_\d+\.\d+", identifier):
        raise ValueError("Only exact curated transcript references can be checked")
    root = _xml(value)
    matches = [row for row in root.findall("GBSeq") if row.findtext("GBSeq_accession-version") == identifier]
    if len(matches) != 1 or matches[0].findtext("GBSeq_organism") != "Homo sapiens":
        raise ValueError("The transcript identity or organism was not verified")
    record = matches[0]
    features = []
    for row in record.findall("GBSeq_feature-table/GBFeature"):
        if row.findtext("GBFeature_key") not in ("gene", "CDS"):
            continue
        features.append({"type": row.findtext("GBFeature_key"), "location": row.findtext("GBFeature_location"),
                         "qualifiers": sorted([(q.findtext("GBQualifier_name"), q.findtext("GBQualifier_value"))
                                               for q in row.findall("GBFeature_quals/GBQualifier")])})
    return {"accession_version": identifier, "updated_on": record.findtext("GBSeq_update-date"),
            "length": record.findtext("GBSeq_length"), "features": features}


def gencc(value: str, target_ids: set[str]) -> dict:
    rows = csv.DictReader(io.StringIO(value.lstrip("\ufeff")), delimiter="\t")
    names = set(rows.fieldnames or [])
    if "gene_curie" not in names or not ({"sgc_id", "uuid"} & names):
        raise ValueError("The GenCC response is not the supported assertion export")
    fields = ("gene_curie", "disease_curie", "disease_title", "classification_curie", "classification_title",
              "moi_curie", "moi_title", "submitter_curie", "submitter_title",
              "submitted_as_date", "submitted_as_public_report_url", "submitted_as_pmids",
              "submitted_as_assertion_criteria_url", "submitted_as_submission_id")
    output: dict[str, dict] = {}
    for row in rows:
        if row.get("gene_curie") not in target_ids:
            continue
        identifier = row.get("sgc_id") or row.get("uuid")
        if not identifier:
            raise ValueError("A GenCC assertion has no submission identity")
        selected = {key: row.get(key) for key in fields}
        selected["version"] = row.get("version_number") or row.get("version") or None
        selected["notes_sha256"] = variant_data.digest(row.get("submitted_as_notes"))
        if identifier in output and output[identifier] != selected:
            raise ValueError("Conflicting GenCC submission identities in one export")
        output[identifier] = selected
    return output


def cpic(rows, gene: str, kind: str) -> dict:
    if not isinstance(rows, list):
        raise ValueError("CPIC did not return the expected table")
    fields = (("name", "id", "version", "functionalstatus", "clinicalfunctionalstatus",
               "clinicalfunctionalsubstrate", "activityvalue", "definitionid", "citations",
               "strength", "functioncomments", "findings") if kind == "allele" else
              ("diplotype", "diplotypekey", "function1", "function2", "activityvalue1",
               "activityvalue2", "totalactivityscore", "description", "generesult", "lookupkey"))
    selected = {}
    for row in rows:
        if row.get("genesymbol") != gene:
            raise ValueError("CPIC returned another gene")
        key = row.get("name") if kind == "allele" else json.dumps(row.get("diplotypekey"), sort_keys=True)
        if not key or key == "null":
            raise ValueError("CPIC table identity is missing")
        if key in selected:
            raise ValueError("CPIC returned repeated table identities; the ambiguous view requires review")
        selected[key] = {field: row.get(field) for field in fields}
    if not selected:
        raise ValueError("CPIC returned no matching allele/diplotype records")
    return selected


def cpic_table(url: str, fetch=None, progress=None) -> list:
    """Read an entire public PostgREST view, proving the declared row count."""
    fetch = fetch or net.get_json_response
    output, offset, total = [], 0, None
    url += "&order=" + ("diplotypekey.asc" if "/diplotype?" in url else "name.asc")
    while offset < 100000:
        if progress:
            progress(provider="CPIC", table_rows=offset)
        response = fetch(url + "&limit=1000&offset=" + str(offset),
                         request_headers={"Prefer": "count=exact"})
        if not isinstance(response, dict) or not isinstance(response.get("data"), list):
            raise ValueError("CPIC did not return a versioned table response")
        headers = {key.lower(): value for key, value in (response.get("headers") or {}).items()}
        extent = re.fullmatch(r"(?:(\d+)-(\d+)|\*)/(\d+)", headers.get("content-range", ""))
        if not extent:
            raise ValueError("CPIC did not prove the complete table extent")
        current_total = int(extent[3])
        if total is not None and total != current_total:
            raise ValueError("CPIC table size changed during pagination")
        total = current_total
        rows = response["data"]
        if not total and not rows:
            return []
        if (not rows or extent[1] is None or int(extent[1]) != offset
                or int(extent[2]) - offset + 1 != len(rows)):
            raise ValueError("CPIC table pagination is incomplete")
        output.extend(rows)
        offset += len(rows)
        if offset == total:
            return output
        if offset > total:
            raise ValueError("CPIC returned more rows than its declared extent")
    raise ValueError("CPIC table exceeded the bounded download")


def source_requests(data: dict) -> dict:
    models = data.get("models") or []
    output: dict[str, Any] = {"pmids": set(), "clinvar": set(), "refsnp": set(), "refseq": set(),
              "cpic_genes": set(), "gene_ids": {}, "model_bindings": {}}
    for hgnc_id, gene in (data.get("genes") or {}).items():
        if str(gene.get("ncbi_id") or "").isdigit():
            output["gene_ids"][str(gene["ncbi_id"])] = hgnc_id
    output["cpic_genes"].update((data.get("_meta") or {}).get("reference_cpic_genes") or [])
    for model in models:
        identifier = model["model_id"]
        refs = {value for value in model.get("variant_ids") or [] if re.fullmatch(r"rs\d+", value)}
        output["refsnp"].update(refs)
        keys = {"refsnp:" + value for value in refs}
        for source in model.get("sources") or []:
            if not isinstance(source, dict):
                source = {"url": source}
            url, version = str(source.get("url") or ""), str(source.get("version") or "")
            pmids = {str(source["pmid"])} if str(source.get("pmid") or "").isdigit() else set()
            pmids.update(re.findall(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", url))
            output["pmids"].update(pmids)
            keys.update("pubmed:" + value for value in pmids)
            clinical = set(re.findall(r"\b[VR]CV\d+", url + " " + version))
            match = re.search(r"ncbi\.nlm\.nih\.gov/clinvar/variation/(\d+)", url)
            if match:
                clinical.add("VCV" + match.group(1).zfill(9))
            output["clinvar"].update(clinical)
            keys.update("clinvar:" + value for value in clinical)
            transcripts = set(re.findall(r"\bN[MR]_\d+\.\d+", url + " " + version))
            output["refseq"].update(transcripts)
            keys.update("refseq:" + value for value in transcripts)
            if "cpicpgx.org" in url and model.get("gene"):
                output["cpic_genes"].add(model["gene"])
                keys.update("cpic:" + model["gene"] + ":" + kind for kind in ("allele", "diplotype"))
            if "gencc.org" in url and model.get("hgnc_id"):
                keys.add("gencc:" + model["hgnc_id"])
        if model.get("hgnc_id"):
            keys.add("hgnc:" + model["hgnc_id"])
            keys.update("ncbi_gene:" + gene_id for gene_id, hgnc_id in output["gene_ids"].items()
                        if hgnc_id == model["hgnc_id"])
        output["model_bindings"][identifier] = sorted(keys)
    return output


def refresh(data: dict, *, fetch_json=None, fetch_text=None, progress=None) -> dict:
    """Check exact referenced records; retain old witnesses when a source fails."""
    requests = source_requests(data)
    previous = data.get("source_checks") or {}
    records, events, failures = dict(previous), [], []
    json_fetch, text_fetch = fetch_json or net.get_json, fetch_text or net.get_text
    checked = date.today().isoformat()
    rate_limit = fetch_json is None and fetch_text is None
    failures_by_provider: dict[str, int] = {}
    total = 2 + (len(requests["gene_ids"]) + 99) // 100 + (len(requests["pmids"]) + 49) // 50
    total += len(requests["clinvar"]) + len(requests["refsnp"]) + len(requests["refseq"]) + 2 * len(requests["cpic_genes"])
    completed = 0

    def remember(key, provider, selected, url, scope, version=None):
        fingerprint = variant_data.digest(selected)
        old = previous.get(key) or {}
        records[key] = {"provider": provider, "scope": scope, "url": url, "data": selected,
                        "fingerprint": fingerprint, "compared_on": checked, "status": "current",
                        "version": version, "primary_semantic_review_renewed": False}
        if old.get("fingerprint") and old["fingerprint"] != fingerprint:
            events.append({"key": key, "provider": provider, "kind": "source_record_changed",
                           "before": old.get("data"), "after": selected})

    def fail(key, provider, error):
        old = previous.get(key) or {}
        records[key] = {**old, "provider": provider, "status": "unavailable",
                        "attempted_on": checked, "error": net.reference_error(error)}
        failures.append({"key": key, "provider": provider, "reason": net.reference_error(error)})

    def run(key, provider, url, parser, *, text=False, fetcher=None):
        nonlocal completed
        if progress:
            progress(provider=provider, reference_done=completed, reference_total=total)
        try:
            if failures_by_provider.get(provider, 0) >= 3:
                raise RuntimeError("Provider failure budget reached; previous witnesses retained")
            if rate_limit:
                time.sleep(0.34)
            value = (fetcher or (text_fetch if text else json_fetch))(url)
            if value is None:
                raise RuntimeError("The reference source is unavailable")
            parser(value)
            failures_by_provider[provider] = 0
        except Exception as exc:
            failures_by_provider[provider] = failures_by_provider.get(provider, 0) + 1
            fail(key, provider, exc)
        completed += 1

    target = set(data.get("genes") or {})
    def save_hgnc(value):
        body = value.get("response") or {}
        documents = body.get("docs")
        if not isinstance(documents, list) or int(body.get("numFound") or 0) != len(documents):
            raise ValueError("Incomplete HGNC identity snapshot")
        selected = {row["hgnc_id"]: row for row in documents if row.get("hgnc_id") in target}
        for identifier in target:
            if identifier not in selected:
                fail("hgnc:" + identifier, "HGNC", "Gene absent from the complete identity snapshot")
                continue
            row = hgnc_record(selected[identifier])
            remember("hgnc:" + identifier, "HGNC", row, HGNC_URL, "gene_identity")
            if row["status"] != "Approved":
                events.append({"key": "hgnc:" + identifier, "provider": "HGNC", "kind": "gene_identity_not_approved"})
    run("hgnc:catalogue", "HGNC", HGNC_URL, save_hgnc)

    ids = sorted(requests["gene_ids"])
    for offset in range(0, len(ids), 100):
        batch = ids[offset:offset + 100]
        url = "https://api.ncbi.nlm.nih.gov/datasets/v2/gene/id/" + ",".join(batch) + "/dataset_report?page_size=1000"
        def save_gene(value, batch=batch, url=url):
            if value.get("next_page_token"):
                raise ValueError("NCBI Gene batch is incomplete")
            by_id = {str(row["gene"]["gene_id"]): row["gene"] for row in value.get("reports") or [] if row.get("gene")}
            for identifier in batch:
                if identifier not in by_id:
                    fail("ncbi_gene:" + identifier, "NCBI Gene", "Requested gene record is absent")
                    continue
                selected = ncbi_gene(by_id[identifier], requests["gene_ids"][identifier])
                remember("ncbi_gene:" + identifier, "NCBI Gene", selected, url, "gene_identity_and_function")
        run("ncbi_gene:batch:" + str(offset), "NCBI Gene", url, save_gene)

    pmids = sorted(requests["pmids"])
    for offset in range(0, len(pmids), 50):
        batch = pmids[offset:offset + 50]
        query = "SRC:MED AND (" + " OR ".join("EXT_ID:" + value for value in batch) + ")"
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + urlencode(
            {"query": query, "format": "json", "resultType": "core", "pageSize": 1000})
        def save_publications(value, batch=batch, url=url):
            by_id = {str(row.get("pmid") or row.get("id")): row for row in
                     (value.get("resultList") or {}).get("result") or [] if row.get("source") == "MED"}
            for identifier in batch:
                if identifier not in by_id:
                    fail("pubmed:" + identifier, "Europe PMC", "Requested publication record is absent")
                    continue
                selected = publication(by_id[identifier])
                remember("pubmed:" + identifier, "Europe PMC", selected, url,
                         "bibliography_abstract_and_correction_status_not_fulltext_review")
        run("pubmed:batch:" + str(offset), "Europe PMC", url, save_publications)

    for identifier in sorted(requests["clinvar"]):
        rettype = "vcv" if identifier.startswith("VCV") else "clinvarset"
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urlencode(
            {"db": "clinvar", "rettype": rettype, "id": identifier, "retmode": "xml"})
        run("clinvar:" + identifier, "ClinVar", url, lambda value, identifier=identifier, url=url:
            remember("clinvar:" + identifier, "ClinVar", clinvar(value, identifier), url,
                     "exact_allele_and_condition_classification_not_personal_disease"), text=True)

    for identifier in sorted(requests["refsnp"]):
        url = "https://api.ncbi.nlm.nih.gov/variation/v0/refsnp/" + identifier[2:]
        run("refsnp:" + identifier, "RefSNP", url, lambda value, identifier=identifier, url=url:
            remember("refsnp:" + identifier, "RefSNP", refsnp(value, identifier), url,
                     "rs_record_placements_not_allele_effect"))

    for identifier in sorted(requests["refseq"]):
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urlencode(
            {"db": "nuccore", "id": identifier, "rettype": "gb", "retmode": "xml"})
        run("refseq:" + identifier, "RefSeq", url, lambda value, identifier=identifier, url=url:
            remember("refseq:" + identifier, "RefSeq", refseq(value, identifier), url,
                     "exact_transcript_reference_and_features"), text=True)

    for gene in sorted(requests["cpic_genes"]):
        for kind in ("allele", "diplotype"):
            key = "cpic:" + gene + ":" + kind
            url = "https://api.cpicpgx.org/v1/" + kind + "?" + urlencode({"genesymbol": "eq." + gene})
            run(key, "CPIC", url, lambda value, key=key, gene=gene, kind=kind, url=url:
                remember(key, "CPIC", cpic(value, gene, kind), url,
                         "allele_function" if kind == "allele" else "complete_diplotype_function"),
                fetcher=(lambda url: cpic_table(url, progress=progress)) if fetch_json is None else None)

    def save_gencc(value):
        selected = gencc(value, target)
        grouped = {identifier: {} for identifier in target}
        for key, row in selected.items():
            grouped[row["gene_curie"]][key] = row
        for identifier, assertions in grouped.items():
            remember("gencc:" + identifier, "GenCC", assertions, GENCC_URL,
                     "gene_disease_validity_and_inheritance_not_variant_effect")
    run("gencc:catalogue", "GenCC", GENCC_URL, save_gencc, text=True)
    affected = {row["key"] for row in events}
    review = sorted(identifier for identifier, keys in requests["model_bindings"].items()
                    if affected.intersection(keys))
    return {"records": records, "events": events, "failures": failures,
            "models_requiring_review": review, "requests_completed": completed,
            "all_supported_checks_attempted": True, "primary_semantic_review_renewed": False}
