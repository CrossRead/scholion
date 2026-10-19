"""Join system insights to actual readings, without inferring a cause or treatment.

The panel reader owns genotype quality and interpretation. A sourced, gated
marker expectation can agree with an exact recent lab reading; gene membership,
a cohort direction and a changing time series cannot establish causation.
"""
from __future__ import annotations

from datetime import date

from . import core
from .i18n import t, lang
from .trend_qualification import observation_day, _number


def _panel_rows(system: str, markers: dict) -> list[dict]:
    from .engine import panel_form, system_panels
    domain = system_panels._domain(system)
    spec = (system_panels._curated().get('systems') or {}).get(system)
    if not domain or not domain['genetic_half'] or not spec:
        return []
    scan = panel_form.scan_for(p.get('gene', '') for p in spec.get('positions') or [])
    scan['local_only'] = True
    curated = system_panels._curated_rows(system, spec, domain['markers'], scan, markers, position_only=True)
    excluded = {r['gene'] for r in curated['excluded'] + curated['unreadable']}
    return [r for r in curated['rows'] if r['gene'] not in excluded]


def _genetic_context(row: dict, markers: dict) -> dict | None:
    """A carried, read position is context; an absent allele is not a risk."""
    if row.get('read') is not True or row.get('carrier') is not True or row.get('presumed') or row.get('needs_confirmation'):
        return None
    interpretation = row.get('interpretation') or {}
    reference = row.get('reference_context') or {}
    genotype = row.get('genotype') or {}
    level = row.get('level')
    text = interpretation.get('summary') if level in ('A', 'B', 'C', 'D') else None
    if not isinstance(text, str) or not text:
        text = reference.get('gene_function')
    if not text:
        return None
    result = {k: row.get(k) for k in ('gene', 'rsid', 'state', 'level', 'read_state', 'depth_note', 'passport')}
    result.update(genotype=genotype, interpretation=interpretation, reference_context=reference,
                  summary=text, status='context_only', causal=False,
                  source=interpretation.get('source') or reference.get('gene_source'))
    from .genetic_comparison import compare_all
    comparisons = row.get('comparisons')
    if comparisons is None:
        comparisons = compare_all(row, markers)
    result['comparisons'] = comparisons
    joined = next(iter(comparisons), None)
    if joined:
        result['genetic_lab_comparison'] = joined
        result['level'] = joined['level']
        result['summary'] = joined['summary']
        result['source'] = joined['source']
        result['status'] = joined['status']
        result['comparison'] = joined['comparison']
        if joined['eligible']:
            result.update(marker=joined['marker'], expected_direction=joined['expected_direction'],
                observation=joined['observation']['point'],
                marker_basis={'source': joined['source'], 'mechanism': joined['summary'],
                              'knowledge': joined['knowledge'], 'status': 'complete'})

    return result


def _display_number(value: float) -> str:
    text = f"{value:g}"
    return text.replace('.', ',') if lang() == 'ru' else text


def _lifestyle_context(phenotype: list[dict], wearable: dict, system: str) -> list[dict]:
    """Dated context, not an automatic gene-by-environment interaction claim."""
    rows = []
    catalogue = core.wearable_metrics().get('metrics') or {}
    person_names = {v['person_metric']: v.get('label') for v in catalogue.values() if v.get('person_metric')}
    for row in phenotype:
        for component in row.get('components') or []:
            ref = component.get('ref') or ''
            if not ref.startswith(('metric:', 'life:')):
                continue
            rows.append({**component, 'key': ref, 'label': person_names.get(ref.split(':', 1)[1]) or component.get('label') or row.get('label'),
                         'record': component.get('series_record') or 'metrics.json'})
    for row in wearable.get('metrics') or []:
        if row.get('counts_toward_conclusions') is False:
            continue
        rows.append({**row, 'record': row.get('record') or 'wearable_trends.json',
                     'aggregation': row.get('aggregation') or 'monthly_mean'})
    # Reuse the canonical wearable/person metric mapping; a hand-entered
    # weight and a device weight are one quantity, with the newest reading shown.
    selected: dict[str, dict] = {}
    for row in rows:
        key = str(row.get('key') or '')
        canonical = (catalogue.get(key) or {}).get('person_metric') or key.split(':')[-1]
        current = selected.get(canonical)
        if current is None or str(row.get('date') or '')[:7] > str(current.get('date') or '')[:7]:
            selected[canonical] = row
    result = []
    for row in selected.values():
        day_text = str(row.get('date') or '')
        day = observation_day(day_text + ('-01' if len(day_text) == 7 else ''))
        if not day or not 0 <= (date.today() - day).days <= 365 or not _number(row.get('value')):
            continue
        comparison = row.get('comparison') or {}
        result.append({k: row.get(k) for k in ('key', 'label', 'value', 'unit', 'date', 'source', 'record', 'aggregation')} | {
            'comparison': comparison if comparison.get('eligible') and comparison.get('distinguishable') else None,
            'unit_display': core.unit_label(row.get('unit') or ''),
            'value_display': _display_number(row['value']),
            'source_label': row.get('source') if row.get('source') not in (None, '', 'recorded') else t('web.phenotype.recorded'),
            'scope': 'coexisting_observation', 'causal': False})
    # Free text stays testimony. No diagnosis, diet or direction is extracted
    # from it. Only reports explicitly assigned to this system are associated.
    from .reported_response import events
    for event in events():
        fact = event['facts'][0]
        if fact.get('system') == system:
            result.append({**fact, 'scope': 'patient_report', 'causal': False})
    result.extend(_recorded_notes(system))
    return result


def _recorded_notes(system: str) -> list[dict]:
    from .engine.system_panels import _domain
    from .engine.lifestyle import _brief_resolve, _brief_newest
    domain = _domain(system) or {}
    keys = set((domain.get('markers') or []) + (domain.get('panel_markers') or []))
    notes = []
    for block in core.lifestyle_brief_src().get('blocks') or []:
        watched = {w.get('key') for w in block.get('watch') or [] if w.get('kind') in (None, 'lab')}
        reviewed = observation_day(block.get('reviewed'))
        if not keys.intersection(watched) or not reviewed or not 0 <= (date.today()-reviewed).days <= 365:
            continue
        newest = _brief_newest(block.get('watch') or [])
        # An old interpretation is not silently reused after new data arrived.
        if newest and newest > block['reviewed']:
            continue
        body = block.get('body')
        if isinstance(body, str) and body.strip():
            notes.append({'record': 'lifestyle_brief.json', 'key': block.get('id'),
                'date': block['reviewed'], 'scope': 'recorded_note', 'causal': False,
                'note': _brief_resolve(body)['text']})
    return notes


def prepare_context(items: list[dict], labs: dict, wearable: dict, phenotype: list[dict]) -> dict:
    """One reading per relevant curated panel; no BAM/PGS recalculation."""
    from .engine.insight_events import _event, _fact
    domains = core._read_knowledge('radar_domains.json').get('domains') or []
    membership: dict[str, str] = {}
    all_membership: dict[str, list[str]] = {}
    for domain in domains:
        for marker in (domain.get('markers') or []) + (domain.get('panel_markers') or []):
            membership.setdefault(marker, domain['key'])
            all_membership.setdefault(marker, []).append(domain['key'])
    by_key = {r['key']: r for r in labs.get('markers') or []}
    systems = {system for item in items for f in item['facts']
               if f.get('record') == 'labs.json' for system in all_membership.get(f.get('key'), [])}
    systems.update(f['system'] for item in items for f in item['facts'] if f.get('system'))
    if any(f.get('record') in ('wearable_trends.json', 'metrics.json') for item in items for f in item['facts']):
        systems.add('fitness')
    contexts: dict[str, dict] = {}
    panels = {system: _panel_rows(system, by_key) for system in sorted(systems)}
    for system in sorted(systems):
        genetics = []
        rows = panels[system]
        for row in rows:
            context = _genetic_context(row, by_key)
            if context:
                genetics.append(context)
        from .genetic_comparison import system_comparisons
        contexts[system] = {'comparisons': system_comparisons(rows, by_key, system), 'genetics': genetics, 'lifestyle': _lifestyle_context(phenotype, wearable, system),
                            'scope': 'recorded_context', 'causal': False}
        # A single abnormal reading plus a supported carried variant is useful
        # even without enough observations for a trend. Do not manufacture a trend.
        for context in contexts[system]['comparisons']:
            if not context['eligible'] or context['status'] != 'concordant':
                continue
            marker = by_key[context['marker']]
            item = next((i for i in items if i['id'] == 'lab:' + marker['key']), None)
            if item is None:
                continue
            fact = {'record': 'genotype', 'gene': context['gene'], 'rsid': context['rsid'],
                    'genotype': context.get('display_genotype') or context['genotype'].get('genotype'), 'state': context['state'],
                    'genotype_source': context['genotype'].get('from_profile') or context['genotype'].get('confidence')}
            if context.get('variant_readings'):
                fact['variants'] = context['facts']['variants']
                fact['diplotype'] = context['facts'].get('diplotype')
            event_key = context['association_id'] if context.get('variant_readings') else context['rsid'] + ':' + marker['key']
            event = _event('genetic_phenotype', event_key, marker['name'],
                [_fact(marker['key'], context['observation']['point'], marker), fact],
                rule={'source': context['source'], 'mechanism': context['summary'],
                      'knowledge': context['knowledge'], 'status': 'complete'},
                detail={'why': context['comparison'],
                        'source': context['source'], 'mechanism': context['summary']})
            event['level'] = context['level']
            if not any(e['id'] == event['id'] for e in item['events']):
                item['events'].append(event)
            if fact not in item['facts']:
                item['facts'].append(fact)
    return {'systems': contexts, 'membership': membership, 'all_membership': all_membership}


def attach_context(groups: list[dict], prepared: dict) -> None:
    for group in groups:
        system = group.get('system') or next((prepared['membership'].get(f.get('key'))
                   for f in group['facts'] if f.get('record') == 'labs.json'), None)
        context = prepared['systems'].get(system)
        if context is None:
            continue
        context = dict(context)
        group['context'] = context
        group['related_systems'] = sorted({s for f in group['facts'] for s in prepared.get('all_membership', {}).get(f.get('key'), []) if s != system})
        matches = [g for g in context.get('comparisons', []) if g['eligible'] and g['status'] == 'concordant']
        if matches:
            redundant = {e['title'] for e in group.get('events') or [] if e['kind'] == 'genetic_phenotype'}
            group['summaries'] = [s for s in group.get('summaries') or [] if s not in redundant]
            if not group.get('trajectory') and group.get('priority', 3) > 1:
                group['title'] = t('insight.context.system_match', system=group['name'])
            group['context_summary'] = ' '.join(g['comparison'] for g in matches)
            group.setdefault('questions', []).append(t('insight.context.question', system=group['name']))
        group['context_notice'] = t('insight.context.notice')
        # Independent measurements can coincide in time without proving an
        # interaction. Only already-qualified wearable comparisons are described.
        lab_dates = [str(f['date'])[:7] for f in group['facts']
                     if f.get('record') == 'labs.json' and f.get('date')]
        context['coexisting_changes'] = []
        for row in context['lifestyle']:
            comparison = row.get('comparison') or {}
            before, after = comparison.get('before') or {}, comparison.get('after') or {}
            if not lab_dates or not before.get('date') or not after.get('date'):
                continue
            if not min(lab_dates) <= before['date'] <= after['date'] <= max(lab_dates):
                continue
            context['coexisting_changes'].append(t('insight.context.coincides',
                name=row.get('label') or row.get('key'), before=before.get('value'),
                after=after.get('value'), unit=row.get('unit_display') or row.get('unit') or '',
                start=before['date'], end=after['date']))
        group['context_lifestyle_summary'] = ' '.join(context['coexisting_changes'][:2])


def context_lines(item: dict, clinician: bool = False) -> list[str]:
    context = item.get('context') or {}
    lines = [item['context_summary']] if item.get('context_summary') else []
    lines.extend(context.get('coexisting_changes') or [])
    from .genetic_comparison import lines as comparison_lines, visible
    comparisons = context.get('comparisons')
    if comparisons is None:
        comparisons = [c for row in context.get('genetics') or []
                       for c in (row.get('comparisons') or [row.get('genetic_lab_comparison')]) if c]
    for comparison in comparisons:
        if visible(comparison, clinician):
            lines.extend(comparison_lines(comparison, clinician))
    for row in context.get('genetics') or []:
        if row.get('genetic_lab_comparison'):
            continue
        lines.append(f"{row['gene']} {row['rsid']} · {(row.get('genotype') or {}).get('genotype') or row.get('state')} · Scholion {row['level']}: {row['summary']}")
        if row.get('depth_note'):
            lines.append(row['depth_note'])
        if row.get('comparison') and row['status'] != 'concordant':
            lines.append(row['comparison'])
        if row.get('source'):
            lines.append(str(row['source']))
    for row in context.get('lifestyle') or []:
        if row.get('scope') == 'recorded_note':
            lines.append(t('insight.context.note', date=row['date'], text=row['note']))
            continue
        if row.get('scope') == 'patient_report':
            continue  # Already shown once by the reported-response event.
        lines.append(t('insight.context.lifestyle_value', name=row.get('label') or row.get('key'),
                       value=row.get('value_display') or row.get('value'), unit=core.unit_label(row.get('unit') or ''),
                       date=row.get('date'), source=row.get('source_label') or row.get('source') or row.get('record')))
    if context.get('genetics') or context.get('lifestyle'):
        lines.append(item.get('context_notice') or t('insight.context.notice'))
    return lines
