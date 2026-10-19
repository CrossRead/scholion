"""One sourced genotype/laboratory comparison for every system and entry point.

Associations and hypotheses never change the clinical finding gate. Genotype
quality, observation quality, association evidence and personal applicability
are separate axes; a normal observation does not disprove a predisposition.
"""
from __future__ import annotations

from datetime import date
import re

from . import core
from .i18n import lang, t
from .trend_qualification import _number, observation_day, reading_status, period_shift


def catalogue() -> dict:
    return core._read_knowledge('genetic_lab_links.json')


def sources(text: str) -> list[str]:
    """Only explicit public source URLs; no network operation."""
    return re.findall(r'https://[^\s;<>]+', text or '')


def genotype_quality(row: dict) -> dict:
    from .genome import _MIN_DEPTH
    g = row.get('genotype') or {}
    reasons = []
    if row.get('read') is not True:
        reasons.append('unread')
    if row.get('presumed') or g.get('confidence') in ('assumed_ref', 'presumed_ref'):
        reasons.append('presumed')
    if row.get('needs_confirmation') or g.get('needs_confirmation'):
        reasons.append('confirmation')
    if g.get('low_depth') or (_number(g.get('depth')) and g['depth'] < _MIN_DEPTH):
        reasons.append('low_depth')
    if g.get('filtered') or g.get('filter') not in (None, '', '.', 'PASS'):
        reasons.append('filtered')
    if g.get('imputed'):
        reasons.append('imputed')
    if g.get('unverified_locus'):
        reasons.append('locus')
    if g.get('depth_unverified') or not _number(g.get('depth')):
        reasons.append('quality_unknown')
    status = 'unread' if 'unread' in reasons else 'limited' if reasons else 'usable'
    return {'status': status, 'reasons': reasons, 'labels': [t('genlab.quality.' + r) for r in reasons],
            'depth': g.get('depth'), 'minimum_depth': _MIN_DEPTH,
            'source': g.get('from_profile') or g.get('source'),
            'date': g.get('date'), 'assembly': g.get('assembly'),
            'position': g.get('read_pos'), 'filter': g.get('filter'),
            'confirmation_reasons': g.get('needs_confirmation') or []}


def observation(marker: dict | None) -> dict:
    """Keep the last recorded bytes as history even when not usable as current."""
    if not marker:
        return {'status': 'missing', 'position': 'unknown', 'current': False, 'point': None,
                'reasons': ['missing']}
    points = marker.get('series') or []
    point: dict = next((p for p in reversed(points) if p.get('date') == marker.get('date')), {})
    m = {**marker, **point}
    reasons = []
    day = observation_day(m.get('date'))
    if day is None or day > date.today():
        reasons.append('date_unknown')
    elif (date.today()-day).days > 365:
        reasons.append('stale')
    if m.get('date_source') in ('filename', 'ordered'):
        reasons.append('date_uncertain')
    if m.get('proposed') or m.get('proposed_rule'):
        reasons.append('proposed')
    if point.get('unit') and point['unit'] != marker.get('unit'):
        reasons.append('unit_conflict')
    exact = reading_status(m)
    if exact == 'unknown' and not reasons:
        reasons.append('not_comparable')
    position = 'unknown'
    if not reasons:
        position = 'within' if exact == 'within' else 'above' if (
            _number(m.get('ref_high')) and m['value'] > m['ref_high']) else 'below'
    keys = ('key', 'name', 'value', 'unit', 'date', 'date_source', 'ref_low', 'ref_high',
            'reference_withheld', 'ref_origin', 'censored', 'comparator', 'source', 'method',
            'specimen', 'biomaterial', 'specimen_source', 'sample_id', 'draw_id', 'form_id', 'fasting')
    # Collection metadata belongs to this result, never to another point or a
    # catalogue's description of a planned test.
    recorded = point if points else marker
    for key in ('specimen', 'biomaterial', 'specimen_source', 'sample_id', 'draw_id', 'form_id', 'method', 'fasting'):
        m[key] = recorded.get(key)
    return {'status': 'current' if not reasons else reasons[0], 'position': position,
            'current': not reasons, 'reasons': reasons,
            'point': {**{k: m.get(k) for k in keys}, 'unit_display': core.unit_label(m.get('unit') or '')}}


def legacy_expectation(exp: dict, markers: dict) -> dict:
    """Compatibility projection; the shared policy owns recency and quality."""
    m = markers.get(exp.get('marker'))
    obs = observation(m)
    note = exp.get('note')
    out = {'marker': exp.get('marker'), 'direction': exp.get('direction'),
           'context_only': bool(exp.get('context_only')), 'note': note.get(lang()) if isinstance(note, dict) else note,
           'gap': m is None, 'position': obs['position'], 'observation_status': obs['status'],
           'current': obs['current'], 'from_value': None, 'from_date': None}
    if obs['point']:
        out.update(obs['point'])
    return out


def association_id(spec: dict) -> str:
    """Stable across catalogue order, translation and repeated system membership."""
    return spec.get('association_id') or ':'.join((spec['gene'], spec['rsid'], spec['marker'],
                                                  spec.get('relation_type', 'quantitative')))


def compare_all(row: dict, markers: dict, system: str | None = None) -> list[dict]:
    return [_compare_spec(row, markers, spec) for spec in catalogue().get('links', [])
            if spec['rsid'] == row.get('rsid') and spec['gene'] == row.get('gene')
            and (system is None or system in spec['systems'])]


def compare(row: dict, markers: dict, system: str | None = None) -> dict | None:
    """Legacy first-item projection; new consumers use the complete list."""
    items = compare_all(row, markers, system)
    return items[0] if items else None


def specimen_label(point: dict) -> str:
    material = point.get('specimen') or point.get('biomaterial')
    return t('genlab.specimen.' + (material if material in
             ('plasma', 'serum', 'whole_blood', 'urine', 'blood', 'edta_plasma', 'packed_red_blood_cells') else 'unknown'))


def collection_reasons(spec: dict, obs: dict) -> list[str]:
    """Match explicit result metadata, never infer a specimen from units."""
    point = obs.get('point') or {}
    reasons = []
    aliases = {'плазма': 'plasma', 'сыворотка': 'serum', 'моча': 'urine',
               'цельная кровь': 'whole_blood', 'whole blood': 'whole_blood'}
    raw = str(point.get('specimen') or point.get('biomaterial') or '').strip().lower()
    material = aliases.get(raw, raw)
    if spec.get('specimens') and material not in spec['specimens']:
        reasons.append('specimen_unknown' if not material else 'specimen_scope')
    if spec.get('units') and point.get('unit') not in spec['units']:
        reasons.append('unit_scope')
    if spec.get('methods') and point.get('method') not in spec['methods']:
        reasons.append('method_scope')
    if spec.get('requires_fasting') and point.get('fasting') is not True:
        reasons.append('fasting_unknown')
    return reasons


def _compare_spec(row: dict, markers: dict, spec: dict) -> dict:
    marker = markers.get(spec['marker'])
    obs = observation(marker)
    quality = genotype_quality(row)
    state = row.get('state')
    collection = collection_reasons(spec, obs)
    reasons = list(quality['reasons']) + list(obs['reasons']) + collection
    applicable = state in spec['states']
    if not applicable:
        reasons.append('allele_absent' if state == 'absent' else 'genotype_scope')
    if spec.get('sex') and core.profile_sex() != spec['sex']:
        applicable = False
        reasons.append('sex_scope')
    if collection:
        applicable = False
    if spec.get('requires_verified_assembly') and (row.get('genotype') or {}).get('assembly') not in ('GRCh37', 'GRCh38'):
        applicable = False
        reasons.append('assembly_unknown')
    if row.get('risk_allele') != spec['catalogue_allele'] or row.get('hgvs') != spec['catalogue_hgvs']:
        applicable = False
        reasons.append('catalogue_identity')
    position = obs['position']
    relation = ('within' if position == 'within' else 'concordant' if
        (position == 'above' and spec['direction'] == 'higher') or
        (position == 'below' and spec['direction'] == 'lower') else
        'different_direction' if position in ('above', 'below') else 'not_comparable')
    level = (spec['association_level'] if spec.get('independent_claim') else
             max(spec['association_level'], row.get('level') or 'E'))
    supported = (spec['status'] == 'supported' and level in ('A', 'B')
                 and row.get('mode') == spec['evidence_type'])
    if not supported and spec['status'] == 'supported':
        reasons.append('evidence_scope')
    eligible = supported and applicable and quality['status'] == 'usable' and obs['current']
    status = relation if eligible else 'excluded' if spec['status'] == 'excluded' else (
        'unread' if quality['status'] == 'unread' else 'allele_absent' if state == 'absent'
        else 'hypothesis' if spec['status'] == 'hypothesis' and applicable and quality['status'] == 'usable'
        else 'context_only')
    point = obs['point'] or {}
    value = point.get('value')
    value_text = f'{value:g}' if _number(value) else '—'
    if lang() == 'ru':
        value_text = value_text.replace('.', ',')
    comparison = t('genlab.status.' + status)
    if eligible:
        comparison = t('insight.context.' + relation, gene=row['gene'], rsid=row['rsid'],
            level=level, marker=(marker or {}).get('name') or spec['marker'],
            value=value_text, unit=core.unit_label(point.get('unit') or ''), date=point.get('date'))
    history = []
    for p in (marker or {}).get('series') or []:
        judged = observation({**(marker or {}), **p, 'series': [p]})
        if eligible and not collection_reasons(spec, judged) and judged['position'] in ('above', 'below') and (
                (judged['position'] == 'above') != (spec['direction'] == 'higher')):
            history.append(judged['point'])
    # The same qualified horizon calculator as the attention feed. A static
    # genotype never supplies a missing baseline or establishes a trend's cause.
    horizons = []
    if marker:
        points = [{**p, 'unit': p.get('unit') or marker.get('unit')} for p in marker.get('series') or []]
        for window in (365, 90, 30):
            selected = []
            for p in points:
                day = observation_day(p.get('date'))
                if day is not None and 0 <= (date.today() - day).days <= window:
                    judged = observation({**marker, **p, 'series': [p]})
                    if not collection_reasons(spec, judged):
                        selected.append(p)
            shift = period_shift(selected, window=window)
            if marker.get('proposed_rule') or any(p.get('proposed_rule') for p in selected):
                shift = {**shift, 'eligible': False, 'reason': 'proposed_rule'}
            horizons.append({'window': window, **shift})
    check = t('genlab.check_quality') if quality['status'] != 'usable' else t('genlab.check_context')
    return {'id': spec['rsid'] + ':' + spec['marker'], 'association_id': association_id(spec),
        'relation_type': spec.get('relation_type', 'quantitative'), 'association_level': spec['association_level'], 'gene': row['gene'], 'rsid': row['rsid'],
        'systems': spec['systems'], 'reference_system': spec.get('reference_system'), 'level': level, 'variant_level': row.get('level'),
        'evidence_type': spec['evidence_type'], 'evidence_label': t('genlab.type.' + spec['evidence_type']),
        'knowledge_status': spec['status'], 'status': status, 'status_label': t('genlab.status.' + status),
        'genotype': row.get('genotype') or {},
        'display_genotype': (row.get('genotype') or {}).get('genotype') if quality['status'] != 'unread' and 'presumed' not in quality['reasons'] else None,
        'state': state, 'quality': quality,
        'marker': spec['marker'], 'expected_direction': spec['direction'],
        'observation': obs, 'relation': relation if eligible else 'not_comparable',
        'eligible': eligible, 'causal': False, 'summary': spec['summary'], 'comparison': comparison,
        'source': spec['source'], 'source_links': sources(spec['source']),
        'knowledge': {'version': catalogue().get('_meta', {}).get('version'),
                      'checked_on': spec['checked_on'], 'review_kind': spec['review_kind'],
                      'clinical_review': None},
        'limitations': spec['limitations'], 'reasons': list(dict.fromkeys(reasons)),
        'reason_labels': [t('genlab.quality.' + r) for r in dict.fromkeys(reasons)],
        'applicable': applicable, 'horizons': horizons, 'contrary_observations': history,
        'what_to_check': check, 'question': t('genlab.question', gene=row['gene'],
            marker=(marker or {}).get('name') or spec['marker']) if eligible and relation != 'within' else None,
        'facts': {'genotype': row.get('genotype') or {}, 'laboratory': {k:v for k,v in point.items() if k != 'unit_display'}},
        'interpretation': comparison if eligible else None,
        'hypothesis': spec['summary'] if status == 'hypothesis' else None}


def linked_rows(rows: list[dict], markers: dict, system: str) -> list[dict]:
    """Read only explicitly reviewed cross-system positions, never all genes."""
    have = {(r.get('gene'), r.get('rsid')) for r in rows}
    needed = {(s['gene'], s['rsid']) for s in catalogue().get('links', [])
              if system in s['systems']} - have
    from . import genetic_patterns
    patterns = [p for p in genetic_patterns.catalogue() if system in p['systems'] and not p.get('reference_only')]
    needed |= {(v['gene'], v['rsid']) for p in patterns for v in p['variants']} - have
    needed_genes = {g for p in patterns if not p['variants'] for g in p['genes']} - {g for g, r in have if not r}
    if not needed and not needed_genes:
        return []
    from .engine import system_panels, panel_form
    extra = []
    books = {**system_panels._curated().get('systems', {}), **system_panels._on_demand().get('panels', {})}
    for key, spec in books.items():
        positions = [p for p in spec.get('positions', []) if (p['gene'], p['rsid']) in needed]
        if not positions:
            continue
        scan = panel_form.scan_for(p['gene'] for p in positions)
        scan['local_only'] = True
        domain = system_panels._domain(key) or {'markers': []}
        result = system_panels._curated_rows(key, {**spec, 'positions': positions},
                    domain['markers'], scan, markers, position_only=True)
        for row in result['rows']:
            row['comparisons'] = compare_all(row, markers, system)
            extra.append(row)
            needed.discard((row['gene'], row['rsid']))
    if needed_genes:
        scan = panel_form.scan_for(needed_genes)
        scan['local_only'] = True
        clinvar = system_panels._clinvar_by_gene(scan)
        for key in system_panels._base().get('systems', {}):
            for row in system_panels._base_rows(key, needed_genes)['rows']:
                if row['gene'] in needed_genes:
                    row = system_panels._finish_base_row(row, scan, clinvar)
                    row['reference_system'] = key
                    extra.append(row)
                    needed_genes.discard(row['gene'])
            if not needed_genes:
                break
    return extra


def system_comparisons(rows: list[dict], markers: dict, system: str) -> list[dict]:
    result = []
    seen = set()
    all_rows = [*rows, *linked_rows(rows, markers, system)]
    for row in all_rows:
        items = row.get('comparisons')
        if items is None:
            items = compare_all(row, markers, system)
        for item in items:
            identity = item.get('association_id') or item['id']
            if system in item['systems'] and identity not in seen:
                result.append(item)
                seen.add(identity)
    from .genetic_patterns import comparisons
    patterns = comparisons(all_rows, markers, system)
    # Composite contexts supersede only their explicitly listed single-site
    # presentation; the original per-row projection remains available.
    replaced = {key for item in patterns for key in item.get('replaces', [])}
    return [item for item in result if item['association_id'] not in replaced] + patterns


def visible(item: dict, clinician: bool = False) -> bool:
    """The same compact inclusion rule as the web table."""
    return bool(clinician or item['eligible'] or (
        item['status'] not in ('excluded', 'unread', 'allele_absent')
        and item.get('state') and item['state'] != 'absent'))


def lines(item: dict, clinician: bool = False) -> list[str]:
    """Shared copy; renderers choose density, never recalculate a relation."""
    result = [f"{item['gene']} {item['rsid']} · Scholion {item['level']} · {item['status_label']}"]
    if item.get('level_scope') == 'mechanism_reference_not_personal_variant':
        result.append(t('genlab.mechanism_level'))
    if item['comparison'] != item['status_label']:
        result.append(item['comparison'])
    if not clinician:
        if item['comparison'] == item['status_label']:
            result.append(item['summary'])
        return result
    result += [t('genlab.facts') + ': ' + str(item.get('display_genotype') or '—'),
               item['evidence_label'],
               t('genlab.hypothesis' if item['knowledge_status'] == 'hypothesis' else 'genlab.reference') + ': ' + item['summary']]
    q = item['quality']
    result.append(t('genlab.genotype_source') + ': ' + str(q.get('source') or t('common.no_data'))
                  + f" · DP {q.get('depth') if q.get('depth') is not None else '—'} · {q.get('date') or '—'}")
    observations = item.get('observations') or [item['observation']]
    for observation in observations:
        p = observation.get('point') or {}
        if p:
            result.append(f"{p.get('name') or observation.get('marker') or item['marker']}: {p.get('value')} {core.unit_label(p.get('unit') or '')} · {p.get('date') or '—'}")
            result.append(t('genlab.lab_source') + ': ' + str(p.get('source') or t('common.no_data')))
            result.append(t('genlab.specimen') + ': ' + specimen_label(p))
    if item.get('derived'):
        result.append(t('genlab.observed_ratio') + f": {item['derived']['value']:.3g}")
    for row in item.get('variant_readings') or []:
        g = row.get('genotype') or {}
        result.append(f"{row.get('gene', '')} {row.get('rsid', '')}: {g.get('genotype') or '—'}")
        for variant in row.get('variant_records') or []:
            result.append(f"{variant.get('chrom') or ''}:{variant.get('pos') or ''} {variant.get('ref') or ''}>{variant.get('alt') or ''} · {variant.get('zygosity') or '—'} · {variant.get('clnsig') or variant.get('classification') or '—'}")
        for assertion in row.get('assertions') or []:
            result.append(f"GenCC: {assertion.get('disease_label') or assertion.get('disease') or '—'} · {assertion.get('classification_label') or assertion.get('classification') or '—'} · {assertion.get('moi_label') or assertion.get('moi') or assertion.get('moi_code') or '—'}")
    result.extend(item['reason_labels'])
    result += [item['limitations'], t('genlab.checked', date=item['knowledge']['checked_on']),
               item['source'], item['what_to_check']]
    if item['contrary_observations']:
        result.append(t('genlab.contrary') + ': ' + '; '.join(
            f"{p.get('date')}: {p.get('value')} {core.unit_label(p.get('unit') or '')}" for p in item['contrary_observations']))
    if item.get('question'):
        result.append(item['question'])
    return result
