"""Claim-scoped scientific provenance, independent of clinical eligibility.

A database assertion, gene function, variant association and treatment claim
have different sources. Missing project review is never absence of literature.
This module only reports reviewed scope; it never fills a clinical mechanism.
"""
from __future__ import annotations

from typing import Any

from . import core
from .i18n import lang, t
from .knowledge_provenance import _book, record



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
    if gene.upper() in [part.strip().upper() for part in str(entry.get('gene') or '').split(',')]:
        return {'scope': 'study_membership', 'status': 'external_literature_catalogue',
                'label': t('science.scope.variant'), 'summary': t('science.study_membership'),
                'sources': ['https://pubmed.ncbi.nlm.nih.gov/' + str(pmid) + '/' for pmid in entry.get('pmids') or []]}
    return None


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
    if rsid:
        book = _book('variant_scientific_review.json')
        raw = (book.get('variants') or {}).get(gene.upper() + '|' + rsid)
        review = core._localize_tree(raw, lang()) if raw else None
        if review:
            if review.get('database_assertion'):
                from .panel_reference import database_assertion
                review['database_assertion'] = database_assertion(review['database_assertion'])
            witnesses = review.get('source_records') or []
            valid = bool(witnesses) and all(record(w['file'], *w['selector']).get('record_digest') == w['digest']
                                             for w in witnesses)
            if not valid:
                review = {**review, 'status': 'review_stale', 'summary': t('science.review_stale')}
            rows.append({'scope': 'variant', 'label': t('science.scope.variant'), **review})
        else:
            retained = _retained_literature(gene, rsid)
            if retained:
                rows.append(retained)
                return rows
            rows.append({'scope': 'variant', 'status': 'not_reviewed',
                         'label': t('science.scope.variant'),
                         'summary': t('science.variant_not_reviewed'),
                         'sources': [context['variant_source']] if context.get('variant_source') else []})
    return rows
