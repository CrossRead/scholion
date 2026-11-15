"""Sequence genotype examples, never a normal range or a personal reading."""
from __future__ import annotations

from itertools import combinations_with_replacement
import re

from . import core
from .i18n import lang, t


def describe(rsid: str, gene: str = '') -> dict:
    """Use retained allele frames only; opening a card performs no lookup."""
    from .genome import _literal_snp_identity, locus_alleles, locus_position
    from .knowledge_provenance import record

    if not re.fullmatch(r'rs\d+', rsid):
        return {}
    locus = (core.loci().get('loci') or {}).get(rsid) or {}
    if not locus:
        return {}
    identity = locus.get('allele_identity') or {}
    frames = []
    for build in ('GRCh38', 'GRCh37'):
        frame = _literal_snp_identity(locus, build)
        if frame:
            ref, alternatives = frame['reference'], frame['alternatives']
            source, checked = frame['source'], frame['checked_on']
        elif identity.get('scope') == 'literal_genotype_only':
            continue  # A damaged verified passport cannot fall back to legacy fields.
        else:
            mapping = (locus.get('assembly_alleles') or {}).get(build) or {}
            mapped = (mapping.get('source') and mapping.get('position') == locus_position(locus, build)
                      and {mapping.get('ref'), mapping.get('alt')} == {locus.get('ref'), locus.get('alt')})
            if not mapped and (build != 'GRCh38' or not locus.get('pos')):
                continue  # Legacy GRCh37 coordinates do not verify allele orientation.
            positioned = locus_alleles(locus, build)
            ref, alt = positioned.get('ref'), positioned.get('alt')
            alternatives = positioned.get('reading_alternatives') or ([alt] if alt else [])
            source = mapping['source'] if mapped else locus.get('coordinate_source')
            checked = mapping.get('checked_on') if mapped else None
        if (ref not in ('A', 'C', 'G', 'T') or not alternatives
                or any(a not in ('A', 'C', 'G', 'T') or a == ref for a in alternatives)
                or len(set(alternatives)) != len(alternatives)):
            continue  # Indels, repeats and diplotypes need their own allele model.
        alleles = [ref, *alternatives]
        rows = []
        for left, right in combinations_with_replacement(alleles, 2):
            kind = ('reference_homozygous' if left == right == ref else
                    'alternative_homozygous' if left == right else 'heterozygous')
            rows.append({'genotype': left + '/' + right, 'kind': kind,
                         'label': t('genotype_reference.' + kind)})
        frames.append({'assembly': build, 'reference': ref, 'alternatives': alternatives,
                       'rows': rows, 'source': source, 'checked_on': checked,
                       'source_label': t('genotype_reference.catalogue'),
                       'verification': t('science.source_checked', date=checked) if checked
                       else t('genotype_reference.check_unknown')})
    if not frames:
        return {}
    if len(frames) == 2 and all(frames[0][key] == frames[1][key]
                                 for key in ('reference', 'alternatives', 'source', 'checked_on')):
        frames[0]['assembly'] = 'GRCh38 / GRCh37'
        frames = frames[:1]
    out: dict = {'scope': 'sequence_reference_not_personal_reading', 'rsid': rsid,
           'title': t('genotype_reference.title'), 'frames': frames,
           'notice': t('genotype_reference.notice'),
           'ploidy_notice': t('genotype_reference.ploidy'),
           'study_examples': [], 'study_sources': [],
           'knowledge': record('loci.json', 'loci', rsid)}
    # Reuse authored comparisons only while their source witnesses still match.
    # These are conditional reference quotations, not findings for this person.
    spec = (core._read_knowledge('research_interpretations.json').get('variants') or {}).get(gene + '|' + rsid) or {}
    witnesses = spec.get('source_records') or []
    from .variant_annotations import needs_source_review
    if (spec.get('allele_frame') == 'forward_genomic' and spec.get('sources') and witnesses
            and not needs_source_review(gene, rsid)
            and all(record(w['file'], *w['selector']).get('record_digest') == w['digest'] for w in witnesses)):
        supported = {''.join(sorted(r['genotype'].replace('/', ''))) for r in frames[0]['rows']}
        out['study_examples'] = [{'genotype': gt, 'summary': core._localized(summary, lang())}
                                 for gt, summary in (spec.get('genotypes') or {}).items()
                                 if gt in supported]
        out['study_sources'] = list(spec['sources'])
        out['study_notice'] = t('genotype_reference.hypothetical')
        out['study_limitations'] = core._localized(spec.get('limitations'), lang())
        out['study_limitations_scope'] = spec.get('limitations_scope')
        out['study_level'] = spec.get('level')
        out['study_checked_on'] = spec.get('checked_on')
    return out


def lines(guide: dict) -> list[str]:
    """The same reference examples remain available in CLI and agent reports."""
    if not guide:
        return []
    out = [guide['title'] + ' · ' + guide['rsid'], guide['notice']]
    for frame in guide['frames']:
        out.append(frame['assembly'] + ': ' + '; '.join(r['genotype'] + ' — ' + r['label'] for r in frame['rows']))
        out.extend([frame['source_label'], frame['verification']])
        if frame['source']:
            out.append(frame['source'])
    out.append(guide['ploidy_notice'])
    if guide['study_examples']:
        out.append(guide['study_notice'] + ' · Scholion ' + str(guide['study_level'] or '—'))
        out.extend(row['genotype'] + ': ' + row['summary'] for row in guide['study_examples'])
        out.extend([guide['study_limitations'], *guide['study_sources']])
    return [line for line in out if line]
