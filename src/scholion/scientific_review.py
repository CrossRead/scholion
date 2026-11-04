"""Claim-scoped scientific provenance, independent of clinical eligibility.

A database assertion, gene function, variant association and treatment claim
have different sources. Missing project review is never absence of literature.
This module only reports reviewed scope; it never fills a clinical mechanism.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
import re
from typing import Any
from urllib.parse import urlsplit

from . import core
from .i18n import lang, t
from .knowledge_provenance import _book, record



def source_refresh_status(value: Any, today: date) -> str:
    """Three calendar months after an exact check, clamped at month end."""
    try:
        checked = date.fromisoformat(value)
    except (TypeError, ValueError):
        return 'date_unknown'
    if checked > today:
        return 'date_unknown'
    year, month = divmod(checked.year * 12 + checked.month + 2, 12)
    due = date(year, month + 1, min(checked.day, monthrange(year, month + 1)[1]))
    return 'due' if today > due else 'current'


def _database_name(url: str) -> str:
    target = urlsplit(url)
    host = (target.hostname or '').removeprefix('www.')
    path = target.path
    if host == 'ncbi.nlm.nih.gov' or host.endswith('.ncbi.nlm.nih.gov'):
        if host.startswith(('pubmed.', 'pmc.')):
            return 'PubMed' if host.startswith('pubmed.') else 'PubMed Central'
        if path.startswith(('/snp/', '/variation/')):
            return 'dbSNP / RefSNP'
        if path.startswith('/clinvar/'):
            return 'ClinVar'
        if path.startswith('/refseq/MANE'):
            return 'MANE'
        if path.startswith(('/gene', '/datasets/gene', '/refseq')):
            return 'NCBI Gene / RefSeq'
        return 'NCBI'
    databases = (('genenames.org', 'HGNC'), ('uniprot.org', 'UniProtKB / Swiss-Prot'),
                 ('geneontology.org', 'Gene Ontology'), ('thegencc.org', 'GenCC'),
                 ('clinicalgenome.org', 'ClinGen'), ('ensembl.org', 'Ensembl'),
                 ('cpicpgx.org', 'CPIC'), ('europepmc.org', 'Europe PMC'),
                 ('senescence.info', 'LongevityMap'))
    return next((name for domain, name in databases
                 if host == domain or host.endswith('.' + domain)), t('science.publication'))


def _review_sources(values: list[Any], checked: Any, today: date) -> list[dict[str, Any]]:
    links: dict[str, dict[str, Any]] = {}
    for value in values:
        if not isinstance(value, str):
            continue
        urls = re.findall(r"https://[^\s;,<>]+", value)
        if not any('pubmed.ncbi.nlm.nih.gov/' in url for url in urls):
            urls.extend('https://pubmed.ncbi.nlm.nih.gov/' + pmid + '/'
                        for pmid in re.findall(r'\bPMID\s*:?\s*(\d+)', value, re.IGNORECASE))
        for url in urls:
            url = url.rstrip(').')
            try:
                hostname = urlsplit(url).hostname
            except ValueError:
                continue
            if hostname:
                links[url] = {'name': _database_name(url), 'url': url}
        if not urls and value.strip():
            links[value] = {'name': t('science.record_unlinked'), 'citation': value}
    state = source_refresh_status(checked, today)
    for item in links.values():
        item.update(checked_on=checked if state != 'date_unknown' else None, refresh_status=state)
    return list(links.values())


def _decorate_sources(rows: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    today = date.today()
    for row in rows:
        checked = row.get('reviewed_on') if row['status'] != 'review_stale' else None
        if row['scope'] in ('gene_function', 'gene_identity'):
            checked = context.get('gene_checked_on') or checked
            if context.get('gene_curation_status') == 'source_derived':
                row['curation_notice'] = t('science.source_derived')
            row['version'] = context.get('gene_source_version')
        values = row.get('sources') or []
        row['source_details'] = _review_sources(values, checked, today)
        if row['scope'] == 'gene_function':
            extra = _review_sources(context.get('gene_additional_sources') or [], None, today)
            known = {link.get('url') or link.get('citation') for link in row['source_details']}
            row['source_details'].extend(link for link in extra
                                         if (link.get('url') or link.get('citation')) not in known)
    return rows


def _retained_literature(gene: str, rsid: str) -> dict[str, Any] | None:
    """A held curation passport or study index is not a new clinical review."""
    direction = (_book('longevity_directions.json').get('directions') or {}).get(rsid) or {}
    if str(direction.get('gene') or '').upper() == gene.upper():
        passport = direction.get('source_passport') or {}
        return {'scope': 'literature_direction', 'status': 'retained_curated_literature',
                'label': t('science.scope.variant'), 'summary': t('science.retained_curation'),
                'limitations': core._localized(direction.get('population_caveat'), lang()),
                'sources': passport.get('sources') or [direction.get('source')],
                'version': passport.get('version') or direction.get('curated_on')}
    entry = (_book('longevitymap.json').get('variants') or {}).get(rsid) or {}
    members = {part.strip().upper() for part in str(entry.get('gene') or '').split(',') if part.strip()}
    requested = {part.strip().upper() for part in gene.split(',') if part.strip()}
    if requested and requested.issubset(members):
        outcomes = set(entry.get('associations') or [])
        result_key = {frozenset({'significant'}): 'significant', frozenset({'non-significant'}): 'not_significant',
                      frozenset({'significant', 'non-significant'}): 'mixed'}.get(frozenset(outcomes), 'listed')
        return {'scope': 'study_membership', 'status': 'external_literature_catalogue',
                'label': t('science.scope.variant'), 'summary': t('science.study_membership'),
                'patient_summary': t('science.study_result.' + result_key, rsid=rsid),
                'sources': ['https://pubmed.ncbi.nlm.nih.gov/' + str(pmid) + '/' for pmid in entry.get('pmids') or []]}
    return None


def _current_witnesses(review: dict[str, Any]) -> bool:
    witnesses = review.get('source_records') or []
    return bool(witnesses) and all(record(w['file'], *w['selector']).get('record_digest') == w['digest']
                                   for w in witnesses)


def physical_position_genes() -> dict[str, str]:
    """Use current reviewed physical assignments for their exact catalogue loci."""
    loci = core.loci().get('loci') or {}
    return {review['rsid']: review['physical_gene']
            for review in (_book('variant_scientific_review.json').get('variants') or {}).values()
            if review.get('physical_gene') and review.get('status') != 'review_stale'
            and (loci.get(review['rsid']) or {}).get('gene') == review.get('gene')
            and _current_witnesses(review)}


def context_review(gene: str, rsid: str, context: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe the exact available source roles, including unresolved reviews."""
    rows: list[dict[str, Any]] = []
    source_review = (_book('gene_source_review.json').get('genes') or {}).get(gene.upper())
    function = context.get('gene_source')
    identity_only = context.get('gene_source_scope') == 'study_gene_set' or context.get('function_status') in ('identity_only', 'pseudogene_identity', 'noncoding_identity', 'regulatory_region', 'withdrawn_model', 'catalogue_gene_set')
    rows.append({'scope': 'gene_identity' if identity_only else 'gene_function',
                 'status': 'withdrawn_model' if context.get('function_status') == 'withdrawn_model' else 'source_recorded' if function else 'metadata_incomplete',
                 'label': t('science.scope.gene_identity' if identity_only else 'science.scope.gene_function'),
                 'summary': t('science.withdrawn_model' if context.get('function_status') == 'withdrawn_model' else 'science.identity_only' if identity_only else 'science.function_recorded' if function else 'science.function_missing'),
                 'sources': [function] if function else []})
    assertions = context.get('gencc_assertions') or []
    if assertions:
        rows.append({'scope': 'gene_disease', 'status': 'external_assertions',
                     'label': t('science.scope.gene_disease'),
                     'summary': t('science.gene_disease'),
                     'sources': [context.get('gencc_source')],
                     'version': context.get('gencc_version')})
    if source_review:
        witnesses = source_review.get('source_records') or []
        valid = bool(witnesses) and all(record(w['file'], *w['selector']).get('record_digest') == w['digest'] for w in witnesses)
        rows[0]['source_check'] = {key: source_review[key] for key in ('status', 'reviewed_on', 'scope')}
        rows[0]['source_check']['current_source_matches_review'] = valid
        gene_record = context.get('gene_knowledge') or {}
        if valid and any(w['file'] == gene_record.get('catalogue') and
                         list(w['selector']) == gene_record.get('selector') and
                         w['digest'] == gene_record.get('record_digest') for w in witnesses):
            rows[0]['reviewed_on'] = source_review['reviewed_on']
    if rsid:
        book = _book('variant_scientific_review.json')
        catalogue_gene = context.get('variant_catalogue_gene') or gene
        raw = (book.get('variants') or {}).get(catalogue_gene.upper() + '|' + rsid)
        review = core._localize_tree(raw, lang()) if raw else None
        if review:
            if review.get('database_assertion'):
                from .panel_reference import database_assertion
                review['database_assertion'] = database_assertion(review['database_assertion'])
            if not _current_witnesses(review):
                for field in ('patient_summary', 'physical_gene'):
                    review.pop(field, None)
                review = {**review, 'status': 'review_stale', 'summary': t('science.review_stale')}
            rows.append({'scope': 'variant', 'label': t('science.scope.variant'), **review})
        else:
            retained = _retained_literature(gene, rsid)
            if retained:
                rows.append(retained)
                return _decorate_sources(rows, context)
            rows.append({'scope': 'variant', 'status': 'not_reviewed',
                         'label': t('science.scope.variant'),
                         'summary': t('science.variant_not_reviewed'),
                         'sources': [context['variant_source']] if context.get('variant_source') else []})
    return _decorate_sources(rows, context)
