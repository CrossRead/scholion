"""Reading and inheritance context, kept separate from variant classification.

This layer neither diagnoses a person nor reclassifies a variant. It describes
what a saved call can mean under a sourced inheritance model. It runs before
pagination: a second recorded allele must not disappear behind a display limit.
"""
from __future__ import annotations

import re
from typing import Any

from . import core
from .i18n import CATALOGUES, lang, t


def _reading(row: dict[str, Any]) -> dict[str, Any]:
    raw = str(row.get('genotype') or '')
    saved = {'het': ('heterozygous', 1), 'hom': ('homozygous', 2),
             'hemi': ('haploid', 1)}.get(str(row.get('zygosity') or '')) if not raw else None
    if saved and ',' not in str(row.get('alt') or ''):
        return {'genotype': '', 'zygosity': saved[0],
                'zygosity_label': t('finding.zygosity.' + saved[0]),
                'allele_identity_supported': True, 'alternative_copies': saved[1],
                'phased_call': False, 'reading_source': 'recorded_zygosity'}
    parts = re.split(r'[/|]', raw)
    valid = len(parts) in (1, 2) and all(p.isdigit() for p in parts)
    alleles = [int(p) for p in parts] if valid else []
    if not alleles:
        state = 'unknown'
    elif not any(alleles):
        state = 'reference'
    elif len(alleles) == 1:
        state = 'haploid'
    elif alleles[0] == alleles[1]:
        state = 'homozygous'
    else:
        state = 'heterozygous'
    # A split multiallelic row can retain its old GT indices. Without an allele
    # mapping, 0/2 cannot establish carriage of the ALT printed beside it.
    identified = bool(alleles and set(alleles) <= {0, 1}
                      and ',' not in str(row.get('alt') or ''))
    return {'genotype': raw, 'zygosity': state,
            'zygosity_label': t('finding.zygosity.' + state),
            'allele_identity_supported': identified,
            'alternative_copies': sum(a == 1 for a in alleles) if identified else None,
            'phased_call': '|' in raw}


def _normal(value: Any) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).strip()


def _reference() -> dict[str, list[dict[str, Any]]]:
    by_gene: dict[str, list[dict[str, Any]]] = {
        gene.upper(): entry.get('submissions') or [] for gene, entry in
        (core._read_knowledge('gencc_inheritance.json').get('genes') or {}).items()}
    for panel in (core._read_knowledge('gencc_gene_disease.json').get('systems') or {}).values():
        for gene, entry in (panel.get('genes') or {}).items():
            if gene.upper() not in by_gene:
                by_gene[gene.upper()] = entry.get('submissions') or []
    for gene, entry in (core._read_knowledge('gencc_panel_assertions.json').get('genes') or {}).items():
        if gene.upper() not in by_gene:
            by_gene[gene.upper()] = entry.get('submissions') or []
    return by_gene


def _inheritance(row: dict[str, Any], book: dict[str, list[dict[str, Any]]],
                 catalogue: dict[str, Any] | None) -> dict[str, Any]:
    genes = [g.strip().upper() for g in str(row.get('gene') or '').split('|') if g.strip()]
    if len(genes) != 1:
        return {'modes': [], 'scope': 'unknown', 'assertions': []}
    gene = genes[0]
    if catalogue is not None:
        entry = (catalogue.get('genes') or {}).get(gene) or {}
        mode = entry.get('inheritance')
        return {'modes': [mode] if mode else [], 'scope': 'acmg_panel',
                'snapshot': (catalogue.get('_meta') or {}).get('version'),
                'assertions': [{'disease': entry.get('phenotype'), 'mode': mode,
                                'source': (catalogue.get('_meta') or {}).get('published')}],
                'source': 'https://pubmed.ncbi.nlm.nih.gov/40568962/'}
    assertions = book.get(gene) or []
    names = {_normal(x) for x in str(row.get('clndn') or '').split('|')}
    matched = [a for a in assertions if _normal(a.get('disease')) in names]
    selected = matched or assertions
    supported = [a for a in selected if a.get('classification') in
                 ('Definitive', 'Strong', 'Moderate')]
    # An unsupported or contradictory assertion remains visible, but cannot
    # supply an inheritance model for a personal summary.
    modes = sorted({str(a.get('moi_code') or 'unknown') for a in selected
                    if not str(a.get('classification') or '').startswith(
                        ('Disputed', 'Refuted', 'No Known'))})
    return {'modes': modes if supported else [], 'scope': 'condition' if matched else 'gene_reference',
            'source': 'https://thegencc.org/',
            'snapshot': core._read_knowledge('gencc_inheritance.json').get('_meta', {}).get('snapshot'),
            'assertions': [{'disease': a.get('disease'), 'disease_id': a.get('disease_id'),
                            'mode': a.get('moi_code'), 'classification': a.get('classification'),
                            'source': a.get('public_report') or 'https://thegencc.org/',
                            'date': a.get('curated_on'),
                            'submission_ids': a.get('submission_ids')} for a in selected]}


def attach(rows: list[dict[str, Any]], catalogue: dict[str, Any] | None = None) -> dict[str, int]:
    """Add per-row context in place; return full-list counts, never diagnoses."""
    book = _reference() if catalogue is None else {}
    pathogenic: dict[str, set[tuple[str, ...]]] = {}
    for row in rows:
        sig = str(row.get('clnsig') or '').lower()
        if 'pathogenic' not in sig or 'conflict' in sig or row.get('reportable') == 'filtered':
            continue
        if row.get('filter') not in (None, '', '.', 'PASS'):
            continue
        reading = _reading(row)
        if not reading['alternative_copies']:
            continue
        for gene in str(row.get('gene') or '').split('|'):
            identity = (str(row.get('chrom') or '').lower().removeprefix('chr'),
                        *(str(row.get(k) or '') for k in ('pos', 'ref', 'alt')))
            pathogenic.setdefault(gene.upper(), set()).add(identity)
    counts: dict[str, int] = {}
    for row in rows:
        reading = _reading(row)
        inheritance = _inheritance(row, book, catalogue)
        modes = inheritance['modes']
        sig = str(row.get('clnsig') or '').lower()
        state = 'classification_only'
        if 'pathogenic' in sig and 'conflict' not in sig:
            state = 'inheritance_unknown'
            if not reading['allele_identity_supported'] or reading['zygosity'] == 'reference':
                state = 'reading_unresolved'
            elif row.get('reportable') == 'filtered' or row.get('filter') not in (None, '', '.', 'PASS'):
                state = 'reading_unresolved'
            elif len(modes) > 1:
                state = 'inheritance_mixed'
            elif modes == ['AR']:
                if reading['zygosity'] == 'heterozygous':
                    state = ('phase_unresolved' if len(pathogenic.get(str(row.get('gene') or '').upper(), set())) > 1
                             else 'carrier_context')
                elif reading['zygosity'] == 'homozygous':
                    state = 'recessive_review'
                else:
                    state = 'reading_unresolved'
            elif modes in (['AD'], ['SD']):
                state = 'dominant_review'
            elif modes and modes[0] in ('XL', 'XLR', 'XLD', 'X-linked', 'X-linked recessive', 'X-linked dominant'):
                state = 'x_linked_review'
            elif modes and modes != ['Unknown']:
                state = 'inheritance_review'
        if row.get('reportable') in ('needs_phase', 'needs_variant_class'):
            state = 'phase_unresolved' if row['reportable'] == 'needs_phase' else 'variant_class_review'
        labels = []
        for mode in modes:
            key = 'finding.mode.' + mode if mode in ('AR', 'AD', 'SD', 'XL', 'XLR', 'XLD') else 'gencc.moi.' + mode
            labels.append(t(key) if key in CATALOGUES[lang()] else t('finding.mode.unknown'))
        modes_label = ', '.join(labels) or t('finding.mode.unknown')
        category = ('pathogenic' if 'pathogenic' in sig and 'conflict' not in sig
                    else str(row.get('tier') or 'uncertain'))
        if category not in ('pathogenic', 'drug', 'risk', 'protective', 'association', 'uncertain'):
            category = 'uncertain'
        row['personal_context'] = {**reading, 'inheritance': inheritance,
            'inheritance_label': modes_label, 'status': state,
            'label': t('finding.status.' + state), 'summary': t('finding.meaning.' + state),
            'inclusion_reason': t('finding.reason.acmg' if catalogue is not None else
                                  'finding.reason.' + category),
            'scope_note': t('finding.scope.' + inheritance['scope']),
            'limitations': t('finding.limitations'), 'diagnosis_established': False}
        counts[state] = counts.get(state, 0) + 1
    return counts


def lines(row: dict[str, Any]) -> list[str]:
    """The same facts for text surfaces; the web uses these structured fields."""
    context = row.get('personal_context') or {}
    if not context:
        return []
    if context['status'] == 'classification_only':
        return [str(context.get('inclusion_reason') or ''),
                t('finding.reading_only', genotype=context.get('genotype') or '—',
                  zygosity=context['zygosity_label'])]
    return [str(context.get('inclusion_reason') or ''), str(context['label']),
            t('finding.reading_line', genotype=context.get('genotype') or '—',
              zygosity=context['zygosity_label'], inheritance=context['inheritance_label']),
            str(context['summary']), str(context['scope_note']),
            t('finding.source', source=context['inheritance'].get('source') or '—',
              version=context['inheritance'].get('snapshot') or '—'),
            str(context['limitations'])]
