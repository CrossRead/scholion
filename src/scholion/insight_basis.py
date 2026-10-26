"""Source witnesses of displayed insights, without a second fact database."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .knowledge_provenance import digest


def fact_source(fact: dict[str, Any]) -> dict[str, Any]:
    """A recorded hash is not a claim that a source was rehashed on this read."""
    witness = fact.get('source_record') or {}
    source = witness.get('path') or fact.get('source') or fact.get('genotype_source')
    availability = 'not_checked' if source else 'not_recorded'
    path = witness.get('path')
    if path and Path(str(path)).is_absolute():
        try:
            availability = 'available' if Path(path).is_file() else 'unavailable'
        except OSError:
            availability = 'unavailable'
    result = {'record': fact.get('record'), 'key': fact.get('key') or fact.get('rsid'),
            'date': fact.get('date'), 'date_source': fact.get('date_source'),
            'method': fact.get('method'),
            'source': source, 'availability': availability,
            'recorded_sha256': witness.get('source_sha256'),
            'source_identity': {k: witness.get(k) for k in ('format', 'resource_id', 'component', 'matched_loinc')
                                if k in witness},
            'section': (fact.get('ingest_method') or {}).get('section'),
            'sample_id': fact.get('sample_id'), 'draw_id': fact.get('draw_id'),
            'verification': 'recorded_witness_not_current_content_verification'}
    result['id'] = digest({k: result[k] for k in ('record', 'key', 'date', 'method', 'source',
                                               'source_identity', 'section', 'sample_id', 'draw_id')})
    return result


def _context_facts(context: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    for row in context.get('genetics') or []:
        facts.append({'record': 'genotype', 'gene': row.get('gene'), 'rsid': row.get('rsid'),
                      'genotype': row.get('genotype'), 'state': row.get('state')})
    for row in context.get('comparisons') or []:
        facts.append({'record': 'genetic_comparison', 'key': row.get('association_id'),
                      'genotype': row.get('genotype'), 'variants': (row.get('facts') or {}).get('variants'),
                      'diplotype': (row.get('facts') or {}).get('diplotype'),
                      'observation': {k: v for k, v in ((row.get('facts') or {}).get('laboratory') or {}).items()
                                      if k not in ('unit_display', 'name', 'label')}})
    facts.extend(context.get('lifestyle') or [])
    if context.get('cgm'):
        facts.append(context['cgm'])
    return facts


def bind(item: dict[str, Any], preserve_existing: bool = False) -> None:
    """Bind every member of a system insight, not just its first laboratory row."""
    from .engine.insight_events import _fact_identity

    context = item.get('context') or {}
    facts = item.get('facts') or []
    used = {}
    for row in (context.get('genetics') or []) + (context.get('comparisons') or []):
        reference = row.get('reference_context') or {}
        for witness in ((row.get('knowledge') or {}).get('record'), reference.get('gene_knowledge')):
            if witness:
                used[witness['id']] = witness
    # A genetic comparison is also present on a raw observation before grouping.
    for event in item.get('events') or []:
        for witness in event.get('knowledge_records') or []:
            used[witness['id']] = witness
    knowledge = [used[key] for key in sorted(used)]
    rules = [event['rule'] for event in item.get('events') or []]
    rule_sources = {digest(source): source for rule in rules for source in rule.get('sources') or []}
    source_facts = [_fact_identity(fact) for fact in facts]
    # Context observations contain a nested laboratory reading, not a second
    # scalar. Preserve its identity rather than dropping the whole relation.
    context_facts = [_fact_identity(fact) | ({'observation': fact['observation']}
                     if fact.get('observation') is not None else {}) for fact in _context_facts(context)]
    previous = item.get('provenance') or {}
    facts_digest = digest(source_facts + context_facts)
    rules_digest = digest({'rules': [{k: rule.get(k) for k in ('id', 'version', 'digest')} for rule in rules],
                           'knowledge': [(w['id'], w.get('record_digest')) for w in knowledge]})
    witnesses = [fact_source(fact) | {'fact_digest': digest(_fact_identity(fact))} for fact in facts]
    item['provenance'] = {
        **previous,
        'schema': 'insight-basis-v1',
        'facts_digest': previous.get('facts_digest', facts_digest) if preserve_existing else facts_digest,
        'rules_digest': previous.get('rules_digest', rules_digest) if preserve_existing else rules_digest,
        'rules': rules,
        'basis': {'facts': witnesses, 'knowledge': knowledge, 'rule_sources': list(rule_sources.values()),
                  'facts_digest': facts_digest, 'rules_digest': rules_digest,
                  'context_facts_digest': digest(context_facts),
                  'unknown_knowledge': [w['id'] for w in knowledge if w.get('status') != 'recorded'],
                  'refresh': {'kind': 'computed_on_read', 'command': 'scholion overview --json',
                              'writes_profile': False, 'requires_genome_preparation': False,
                              'requires_pgs_calculation': False}}}
