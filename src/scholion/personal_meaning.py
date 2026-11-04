"""Source-bound research meaning beside a literal call, separate from action.

This layer never changes clinical eligibility, finding counts or stored calls.
An authored genotype comparison is applied only to the exact, usable reading;
other evidence remains study context rather than an invented personal effect.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any

from . import core
from .i18n import lang, t
from .knowledge_provenance import record


def reading_of(row: dict) -> dict:
    """Normalize producer envelopes without selecting a different observation."""
    value = row.get('reading')
    if not isinstance(value, dict):
        value = row.get('result')
    if not isinstance(value, dict):
        value = row.get('genotype')
    if not isinstance(value, dict):
        value = row
    out = {**(value.get('quality') or {}), **value}
    held = out.get('reading_record') or row.get('reading_record')
    if held is not None:
        if not isinstance(held, dict):
            return {**out, 'reading_contract_invalid': True, 'interpretation_applicable': False}
        selected = next((r for r in held.get('observations') or []
                         if isinstance(r, dict) and held.get('selected_observation')
                         and (r.get('source') or {}).get('record_digest') == held['selected_observation']), None)
        if (held.get('schema') != 1 or held.get('conflict')
                or held.get('selected_observation') is not None and selected is None
                or selected and any(isinstance(r.get('genotype'), str) and r['genotype'] != selected.get('genotype')
                                    for r in (row, out))):
            out['interpretation_applicable'] = False
            out['reading_contract_invalid'] = True
        if selected:
            from .variant_readings import identity_mismatches
            identity = selected.get('identity') or {}
            if identity_mismatches(out.get('variant_identity') or {}, identity):
                out['reading_contract_invalid'] = True
            out.update(selected.get('quality') or {})
            out.setdefault('variant_identity', identity)
            for key, source in (('assembly', 'assembly'), ('read_pos', 'pos'), ('ref', 'ref')):
                out.setdefault(key, identity.get(source))
    return out


def _literal_study_identity(rsid: str, reading: dict) -> bool:
    """Only the reader's explicit catalogue restriction admits a study binding."""
    from .genome import _literal_snp_identity
    if (reading.get('interpretation_restriction') != 'literal_catalogue_only'
            or reading.get('source') != 'vcf' or reading.get('conflict') or reading.get('reading_contract_invalid')):
        return False
    locus = (core.loci().get('loci') or {}).get(rsid) or {}
    identity = _literal_snp_identity(locus, reading.get('assembly'))
    actual = reading.get('variant_identity') or {}
    return bool(identity and actual.get('assembly') == reading.get('assembly')
                and actual.get('pos') == identity['position'] == reading.get('read_pos')
                and str(actual.get('chrom')) == str(identity['chrom'])
                and actual.get('ref') == identity['reference'] == reading.get('ref'))


def _genotype(value: Any) -> str | None:
    # Numeric GT requires REF/ALT decoding by the reader, never by this layer.
    if not isinstance(value, str):
        return None
    value = value.upper()
    if not re.fullmatch(r'[ACGT](?:[/|]?[ACGT])', value):
        return None
    return ''.join(sorted(value.replace('/', '').replace('|', '')))


def _study_identity(rsid: str, reading: dict) -> bool:
    """Bind an observed forward-strand SNP to this catalogue position."""
    from .genome import locus_alleles, locus_position
    from .linear import norm_chrom
    locus = (core.loci().get('loci') or {}).get(rsid) or {}
    identity = reading.get('variant_identity') or {}
    assembly = reading.get('assembly')
    if assembly not in ('GRCh37', 'GRCh38') or identity.get('assembly') != assembly:
        return False
    expected = locus_alleles(locus, assembly)
    position = locus_position(locus, assembly)
    if (not isinstance(position, int) or identity.get('pos') != position
            or reading.get('read_pos') not in (None, position)
            or norm_chrom(identity.get('chrom')) != norm_chrom(locus.get('chrom'))
            or not expected.get('ref') or identity.get('ref') != expected['ref']
            or reading.get('ref') not in (None, expected['ref'])):
        return False
    # A stored positive call may include several ALT alleles. Only the exact
    # studied SNP letters can enter these diploid comparisons.
    genotype = _genotype(reading.get('genotype'))
    return bool(genotype and expected.get('alt') and not set(genotype) - {expected['ref'], expected['alt']})


def _linked_claims(gene: str, rsid: str, genotype: str | None) -> list[dict]:
    """Reuse independently sourced quantitative associations, not gene function.

    Joint haplotypes, monogenic inheritance and unsupported allele orientations
    keep their own readers. Lack of the studied allele is not a protective score.
    """
    if not genotype or (gene == 'APOE' and rsid in ('rs429358', 'rs7412')):
        return []
    locus = (core.loci().get('loci') or {}).get(rsid) or {}
    claims = []
    for spec in core._read_knowledge('genetic_lab_links.json').get('links') or []:
        if (spec.get('gene') != gene or spec.get('rsid') != rsid
                or spec.get('status') not in ('supported', 'hypothesis')
                or spec.get('evidence_type') != 'common_variant'):
            continue
        match = re.fullmatch(r'NC_\d+\.\d+:g\.(\d+)([ACGT])>([ACGT])', spec.get('catalogue_hgvs') or '')
        if not match:
            continue
        position, ref, alt = match.groups()
        if (int(position) != locus.get('pos') or ref != locus.get('ref') or alt != locus.get('alt')
                or set(genotype) - {ref, alt} or spec['catalogue_allele'] not in (ref, alt)):
            continue
        copies = genotype.count(spec['catalogue_allele'])
        state = ('absent', 'het', 'hom')[copies]
        if state not in spec['states'] and state != 'absent':
            continue
        claims.append({**spec, 'state': state, 'copies': copies})
    return claims


def _linked_meaning(claims: list[dict], genotype: str) -> dict:
    summaries, limits, sources = [], [], []
    for claim in claims:
        summaries.append(t('meaning.absent' if claim['state'] == 'absent' else 'meaning.association',
                           genotype=genotype, allele=claim['catalogue_allele'], summary=claim['summary']))
        limits.append(claim['limitations'])
        from .genetic_comparison import sources as source_links
        sources.extend(source_links(claim['source']))
    return {'scope': 'genotype_hypothesis', 'status': 'genotype_hypothesis',
            'summary': ' '.join(dict.fromkeys(summaries)),
            'limitations': ' '.join(dict.fromkeys(limits)), 'sources': list(dict.fromkeys(sources)),
            'checked_on': min(c['checked_on'] for c in claims) if all(c.get('checked_on') for c in claims) else None,
            'level': max(claim['association_level'] for claim in claims),
            'associations': [{k: claim.get(k) for k in ('association_id', 'marker', 'direction', 'state',
                             'copies', 'checked_on', 'catalogue_allele', 'states')} for claim in claims],
            'knowledge': [record('genetic_lab_links.json', 'links', c['association_id']) for c in claims]}


def describe(row: dict) -> dict:
    from .genetic_comparison import genotype_quality
    from .variant_readings import permits_interpretation

    gene, rsid = str(row.get('gene') or '').upper(), str(row.get('rsid') or '')
    reference = row.get('reference_context') or {}
    reading = reading_of(row)
    positive = reading.get('confidence') in ('called', 'confirmed_ref', 'called_array', 'reported', 'profile')
    quality = genotype_quality({'read': positive and bool(reading.get('genotype')), 'genotype': reading})
    usable = (quality['status'] == 'usable' and not reading.get('reading_contract_invalid')
              and ((permits_interpretation(reading) and _study_identity(rsid, reading))
                   or _literal_study_identity(rsid, reading))
              and not reading.get('strand_ambiguous') and not reading.get('imputed')
              and isinstance(reading.get('depth'), (int, float)) and reading['depth'] >= quality['minimum_depth'])
    genotype = _genotype(reading.get('genotype')) if usable else None
    clinical_context = row.get('mode') in ('pgx', 'monogenic')
    spec = None if clinical_context else (core._read_knowledge('research_interpretations.json').get('variants') or {}).get(gene + '|' + rsid)
    out: dict[str, Any] = {'scope': 'research_context', 'status': 'reference_only',
        'summary': None, 'mechanism': None, 'comparator': None, 'direction': None,
        'context': [], 'level': row.get('level') or reference.get('level'),
        'limitations': None, 'sources': [], 'reading_quality': quality,
        'reading_binding': {'status': 'verified' if usable else 'unverified', 'genotype': reading.get('genotype')},
        'clinical_eligibility_upgrade': False, 'action': {'status': 'separate_assessment'}}
    if spec:
        localized = {key: core._localized(value, lang()) for key, value in spec.items()}
        localized['genotypes'] = {key: core._localized(value, lang())
                                  for key, value in (spec.get('genotypes') or {}).items()}
        witnesses = spec.get('source_records') or []
        current = bool(witnesses) and all(record(w['file'], *w['selector']).get('record_digest') == w['digest']
                                         for w in witnesses)
        if current:
            out.update({k: localized.get(k) for k in ('mechanism', 'comparator', 'direction',
                         'limitations', 'sources', 'level', 'checked_on', 'study_scope')})
            if localized.get('limitations_scope') == 'genome':
                out['limitations_scope'] = 'genome'
            statement = (localized.get('genotypes') or {}).get(genotype)
            out.update(summary=statement or localized.get('study_summary'),
                       status='genotype_hypothesis' if statement else 'reference_only',
                       scope='genotype_hypothesis' if statement else 'research_context',
                       knowledge=record('research_interpretations.json', 'variants', gene + '|' + rsid))
            if not statement:
                out['reason'] = 'reading_unverified' if not usable else 'genotype_not_studied'
        else:
            out.update(status='review_stale', reason='source_changed')
    if not clinical_context and not spec and (claims := _linked_claims(gene, rsid, genotype)):
        out.update(_linked_meaning(claims, genotype or ''))
    if not out['summary'] and not spec:
        # A verified authored sentence is more specific than study membership.
        # Keep the caller's clinical gates; this layer cannot revive a held one.
        interpretation = row.get('interpretation') or {}
        text = interpretation.get('summary')
        if usable and isinstance(text, str) and interpretation.get('personalized') is not False:
            out.update(summary=text, status='catalogue_interpretation',
                       scope='catalogue_interpretation', mechanism=interpretation.get('mechanism'),
                       sources=[interpretation['source']] if interpretation.get('source') else [],
                       limitations=interpretation.get('notice'))
    if not out['summary'] and clinical_context and reference.get('variant_status') == 'described':
        from .genetic_comparison import sources as source_links
        out.update(summary=reference.get('variant_context'), limitations=reference.get('notice'),
                   sources=source_links(reference.get('variant_source') or ''))
    if not out['summary']:
        review: dict[str, Any] = next((r for r in reference.get('scientific_review') or []
                       if r.get('scope') in ('variant', 'study_membership')
                       and r.get('status') != 'review_stale' and r.get('patient_summary')), {})
        out.update(summary=review.get('patient_summary'), limitations=review.get('limitations'),
                   sources=review.get('sources') or [], checked_on=review.get('reviewed_on'))
    # Only an existing exact-variant/marker comparison can qualify this claim.
    # General lifestyle facts and unrelated normal labs are not confirmation.
    for comparison in row.get('comparisons') or []:
        if usable and comparison.get('eligible') and comparison.get('rsid') == rsid and comparison.get('gene') == gene:
            out['context'].append({k: comparison.get(k) for k in
                ('association_id', 'marker', 'relation', 'comparison', 'observation',
                 'contrary_observations', 'source', 'causal')})
    from .scientific_review import _review_sources
    out['source_details'] = _review_sources(out['sources'], out.get('checked_on'), date.today())
    return out


def attach(row: dict, markers: dict | None = None) -> dict:
    """One projection shared by web, CLI and agent entry points."""
    if row.get('rsid'):
        if markers is not None and 'comparisons' not in row:
            from .genetic_comparison import compare_all
            reading = reading_of(row)
            claims = _linked_claims(str(row.get('gene') or '').upper(), row['rsid'], _genotype(reading.get('genotype')))
            comparisons: list[dict] = []
            for claim in claims:
                normalized = {**row, 'read': True, 'genotype': reading, 'state': claim['state'],
                              'risk_allele': claim['catalogue_allele'], 'hgvs': claim['catalogue_hgvs'],
                              'mode': claim['evidence_type']}
                comparisons.extend(c for c in compare_all(normalized, markers)
                                   if c['association_id'] == claim['association_id'])
            row['comparisons'] = comparisons
        row['personal_meaning'] = describe(row)
    return row


def lines(row: dict, *, include_level: bool = True) -> list[str]:
    meaning = row.get('personal_meaning') or {}
    if not meaning.get('summary'):
        return []
    title = 'meaning.personal' if meaning.get('scope') != 'research_context' else 'meaning.study'
    result = [t(title) + ': ' + meaning['summary']]
    if meaning.get('mechanism'):
        result.append(meaning['mechanism'])
    result.extend(c['comparison'] for c in meaning.get('context') or [] if c.get('comparison'))
    if meaning.get('limitations'):
        result.append(meaning['limitations'])
    if include_level:
        result.append(t('reference.level', level=meaning.get('level') or '—'))
    result.extend(meaning.get('sources') or [])
    return list(dict.fromkeys(result))
