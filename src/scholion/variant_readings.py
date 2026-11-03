"""Canonical literal observations and resolution over existing genotype stores.

A catalogue assertion is not a measurement. File adapters retain every recorded
observation; resolution never overwrites the source files. Legacy flat fields
remain projections for existing consumers, with the complete reading record
beside them. No persistent cache is keyed by rsID alone.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

POSITIVE = frozenset({'called', 'confirmed_ref', 'called_array'})


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), default=str).encode()).hexdigest()


def same_genotype(a: str | None, b: str | None) -> bool:
    """Compare literal allele dosage only; retain phase in the observations."""
    def normalize(value):
        value = str(value or '').strip().upper()
        if re.fullmatch(r'[ACGT]{1,2}', value):
            return tuple(sorted(value))
        if re.fullmatch(r'[ACGT]+[/|][ACGT]+', value):
            return tuple(sorted(re.split(r'[/|]', value)))
        # Numeric GT requires the original REF/ALT array; concatenated indels
        # have lost allele boundaries. Neither establishes literal agreement.
        return None
    return bool(normalize(a)) and normalize(a) == normalize(b)


def observation(rsid: str, value: dict, source: str, selector: str) -> dict:
    """An immutable-by-convention snapshot; never fill unknown source coordinates."""
    identity = deepcopy(value.get('variant_identity') or {})
    if not identity:
        identity = {k: value.get(v) for k, v in (
            ('assembly', 'assembly'), ('chrom', 'chrom'), ('pos', 'read_pos'),
            ('ref', 'ref'), ('alt', 'alt'))}
    quality_keys = ('depth', 'filter', 'qual', 'allele_fraction', 'low_depth',
                    'depth_unverified', 'filtered', 'imputed', 'strand_ambiguous',
                    'needs_confirmation', 'confirmation_reasons', 'unverified_locus')
    result: dict[str, Any] = {'rsid': rsid, 'identity': identity,
            'genotype': value.get('genotype'), 'raw_genotype': value.get('raw_genotype'),
            'raw_recorded_genotype': value.get('raw_recorded_genotype'),
            'phased': value.get('phased'), 'confidence': value.get('confidence'),
            'interpretation_applicable': value.get('interpretation_applicable'),
            'quality': {k: deepcopy(value[k]) for k in quality_keys if k in value},
            'source': {'file': source, 'selector': selector},
            'source_identity': deepcopy(value.get('source_identity')),
            'underlying_observations': deepcopy(value.get('observations') or []),
            'date': value.get('date')}
    # Presentation language and catalogue prose must not change a measurement's
    # identity. Unknown coordinates remain unknown, including in old reports.
    result['source']['record_digest'] = digest(result)
    return result


def recorded_genotypes() -> dict[str, dict]:
    """Lossless adapters for PGx and longevity; no first-row-wins conflict loss."""
    from . import core
    groups: dict[str, list[dict]] = {}

    def add(rsid, raw, source, selector, gene=''):
        rs = str(rsid or '').strip().lower()
        if not rs.startswith('rs') or not str(raw.get('genotype') or '').strip():
            return
        value = deepcopy(raw)
        raw_gt = str(value.get('genotype') or '').strip()
        annotated = re.fullmatch(r'([ACGT](?:[/|]?[ACGT])?)\s*\(DP=(\d+)\)', raw_gt, re.I)
        if annotated:
            value['raw_recorded_genotype'] = raw_gt
            value['genotype'] = annotated[1].upper()
            value.setdefault('depth', int(annotated[2]))
        if not same_genotype(value.get('genotype'), value.get('genotype')):
            value['interpretation_applicable'] = False
        value.setdefault('gene', gene)
        value['source'] = source
        value.setdefault('confidence', 'reported')
        value['observation'] = observation(rs, value, source, selector)
        groups.setdefault(rs, []).append(value)

    for i, value in enumerate(core.pharmacogenomics().get('genotypes') or []):
        if isinstance(value, dict):
            add(value.get('rsid'), value, 'pharmacogenomics.json', f'genotypes/{i}')
    saved = core.read_profile_json(core.profile_dir() / 'longevity_findings.json')
    raw_apoe = saved.get('apoe')
    apoe = raw_apoe if isinstance(raw_apoe, dict) else {}
    for rs in ('rs429358', 'rs7412'):
        add(rs, {'genotype': apoe.get(rs)}, 'longevity_findings.json', 'apoe/' + rs, 'APOE')
    for i, value in enumerate(saved.get('known') or []):
        if isinstance(value, dict):
            add(value.get('rsid'), value, 'longevity_findings.json', f'known/{i}')
    out = {}
    for rs, values in groups.items():
        first = values[0]
        result = {k: deepcopy(v) for k, v in first.items() if k != 'observation'}
        result['gene'] = str(result.get('gene') or '').upper()
        result['rsid'] = rs
        result['observations'] = [v['observation'] for v in values]
        if any(not same_genotype(first.get('genotype'), v.get('genotype')) for v in values[1:]):
            result['conflict'] = {'kind': 'recorded_disagreement',
                                  'values': [v.get('genotype') for v in values], 'resolved_to': None}
            result['interpretation_applicable'] = False
        out[rs] = result
    return out


def resolve(rsid: str, called: dict | None, recorded: dict | None = None) -> dict | None:
    """One source policy for all consumers, keeping literal data and uncertainty.

    A positive current reading outranks a recorded summary for display only.
    Disagreement prohibits automatic interpretation; agreement does not establish
    independent validation, because the summary may derive from the same file.
    An absent row cannot erase a recorded result. All alternatives remain in the
    record, including a current refusal and conflicting historical observations.
    """
    from . import core
    if called is None and recorded is None:
        return None
    current = deepcopy(called or {})
    saved = deepcopy(recorded or {})
    saved_valid = bool(saved.get('genotype') and saved.get('source'))
    positive = current.get('confidence') in POSITIVE and bool(current.get('genotype'))
    if saved_valid and not positive:
        result = {k: deepcopy(v) for k, v in saved.items() if k not in ('observations', 'source')}
        result.update(confidence='reported', source='profile', from_profile=saved.get('source'))
        result['reader_refusal'] = current.get('confidence')
        # Source quality belongs to the report, never to the failed current read.
        selected = 'recorded'
    else:
        result, selected = current, 'current'
    if current.get('interpretation_applicable') is False:
        result['interpretation_applicable'] = False
    if current.get('conflict') or current.get('confidence') == 'conflicting_calls':
        result['conflict'] = deepcopy(current.get('conflict') or {
            'kind': 'conflicting_calls', 'resolved_to': None})
        result['interpretation_applicable'] = False
    observations = deepcopy(saved.get('observations') or [])
    if saved.get('genotype') and not observations:
        observations.append(observation(rsid, saved, saved.get('source') or 'profile', rsid))
    if called:
        observations.insert(0, observation(rsid, called, called.get('source') or 'current', rsid))
    if positive and saved_valid:
        if same_genotype(current.get('genotype'), saved.get('genotype')):
            result.update(confirmed_by='profile', also_reported=saved['genotype'])
        else:
            result['conflict'] = {'reported': saved.get('genotype'), 'called': current.get('genotype'),
                                  'resolved_to': 'called', 'kind': 'source_disagreement'}
            result['interpretation_applicable'] = False
    if saved.get('conflict'):
        result['recorded_conflict'] = saved['conflict']
        result.setdefault('conflict', saved['conflict'])
        result['interpretation_applicable'] = False
    if result.get('conflict'):
        from .i18n import t
        notice = t('genome.source_conflict')
        if notice not in str(result.get('note') or ''):
            result['note'] = ' '.join(filter(None, [result.get('note'), notice]))
    catalogue = (core.loci().get('loci') or {}).get(rsid) or {}
    result['reading_record'] = {'schema': 1, 'rsid': rsid, 'selected': selected,
        'profile_key': digest(str(core.profile_dir().resolve())),
        'observations': observations, 'catalogue_digest': digest(catalogue),
        'source_digest': digest(observations),
        'conflict': deepcopy(result.get('conflict')),
        'interpretation_applicable': result.get('interpretation_applicable')}
    return result


def permits_interpretation(reading: dict) -> bool:
    """Identity/source conflicts are independent of scientific evidence level."""
    return not reading.get('conflict') and reading.get('interpretation_applicable') is not False
