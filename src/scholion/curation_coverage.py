"""Explicit gene-to-variant effect links, separate from gene-function coverage.

Only registered, source-bound effect descriptions count. Coordinate proximity,
study membership and database classifications do not create effect links.
"""
from __future__ import annotations

from . import core
from .i18n import t


@core.memo_in_reading
def describe(gene: str, function_recorded: bool) -> dict:
    """Describe the registered coverage, never the absence of published effects."""
    from .genotype_reference import describe as genotype_reference

    links = []
    for key, spec in (core._read_knowledge('research_interpretations.json').get('variants') or {}).items():
        symbol, separator, rsid = key.partition('|')
        if not separator or symbol.upper() != gene.upper():
            continue
        if not all(spec.get(field) for field in ('direction', 'study_scope', 'study_summary', 'sources', 'checked_on', 'limitations')):
            continue
        guide = genotype_reference(rsid, symbol)
        if not guide.get('study_examples'):
            continue  # Reject stale source witnesses or unresolved allele models.
        links.append({'gene': gene, 'rsid': rsid, 'effect': spec['study_summary'],
                      'direction': spec['direction'], 'study_scope': spec['study_scope'],
                      'sources': list(spec['sources']), 'checked_on': spec['checked_on'],
                      'level': spec.get('level'), 'limitations': spec['limitations'],
                      'genotypes': guide['study_examples'],
                      'clinical_eligibility_upgrade': False})
    from .variant_annotations import statistics
    retained = statistics(gene)
    return {'scope': 'registered_source_bound_variant_effects',
            'reference_knowledge': retained,
            'variant_reference_available': bool(retained['source_annotation_count'] or retained['recorded_model_count']),
            'recorded_variant_meaning_available': bool(retained['variant_meaning_model_count']),
            'function_recorded': function_recorded,
            'variant_effect_curated': bool(links), 'links': links,
            'link_count': len(links), 'rsid_count': len({r['rsid'] for r in links}),
            'summary': t('curation.coverage_references', function=t('curation.function_yes') if function_recorded else t('curation.function_no'),
                         models=retained['recorded_model_count'], annotations=retained['natural_annotation_count'],
                         links=retained['fully_described_link_count']),
            'notice': t('curation.coverage_notice')}
