"""Visit-specific projection; source facts and the full handout remain available."""
from __future__ import annotations

from datetime import date, timedelta

from . import core
from .i18n import t


class VisitFocusInvalid(ValueError):
    """A visit selection may be corrected without exposing internal details."""


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _reading_row(row: dict, disease_ids: set[str] | None = None) -> dict:
    from .panel_reference import genome_context
    gene_reference = genome_context(row.get('gene') or '')['reference_context']
    reference = {**gene_reference, **(row.get('reference_context') or {})}
    for key in ('gencc_assertions', 'gencc_version', 'gencc_source', 'gencc_status'):
        if not reference.get(key):
            reference[key] = gene_reference.get(key)
    interpretation = row.get('interpretation') or {}
    genotype = row.get('genotype') or {}
    assertions = reference.get('gencc_assertions') or []
    focused_assertions = assertions if disease_ids is None else [a for a in assertions if a.get('disease_id') in disease_ids]
    return {'gene': row.get('gene'), 'rsid': row.get('rsid'),
            'function': reference.get('gene_function'),
            'genotype': genotype.get('genotype'), 'quality': genotype,
            'reading_note': row.get('depth_note') or row.get('read_why_text') or (t('visit.focus.depth', depth=genotype['depth']) if genotype.get('depth') is not None else t('visit.focus.depth_unknown')),
            'summary': interpretation.get('summary') or row.get('summary') or reference.get('variant_context'),
            'mechanism': row.get('mechanism') or (row.get('passport') or {}).get('mechanism'),
            'level': row.get('level'), 'source': interpretation.get('source') or row.get('source'),
            'gencc': focused_assertions, 'other_gencc_count': len(assertions)-len(focused_assertions),
            'gencc_version': reference.get('gencc_version'),
            'clinvar': row.get('clinvar'), 'reference_context': reference,
            'personal_effect_established': False,
            'comparisons': row.get('comparisons') or [],
            'comparison': row.get('genetic_lab_comparison')}


def _discussion_genetics(section: dict, data: dict) -> list[dict]:
    """Join a visit observation or a verified prescription flag, never gene membership."""
    focus = {m['key']: m for m in section['focus_measurements']}
    candidates = list(section.get('genetic_candidates', section['genetics']))
    # Reuse cross-system readings already composed by the attention engine;
    # generating a handout must not fetch new gene regions.
    for item in data['agenda']['items']:
        for gene in (item.get('context') or {}).get('genetics') or []:
            if any(section['key'] in c.get('systems', []) for c in gene.get('comparisons') or []):
                candidates.append(_reading_row(gene))
    for insight in section['insights']:
        for comparison in insight.get('comparisons') or []:
            if not comparison.get('variant_readings'):
                continue
            candidate = _reading_row({**comparison,
                'genotype': comparison.get('genotype') or {},
                'genetic_lab_comparison': comparison})
            candidate['variant_readings'] = comparison['variant_readings']
            candidates.append(candidate)
    medications = {m['name'] for m in section['medications'] if m.get('current') is not False}
    flags = [c for c in data.get('regimen_cautions') or []
             if c.get('drug') in medications and c.get('gene') and c.get('rsid')
             and c.get('genotype') and c.get('level') in ('A', 'B')
             and not c.get('interpretation_withheld') and c.get('factor')]
    for flag in flags:
        candidates.append(_reading_row({**flag, 'summary': flag['factor'],
            'genotype': {'genotype': flag.get('genotype'), 'source': flag.get('genotype_source')}}))
    result = {}
    for gene in candidates:
        links = []
        comparisons = gene.get('comparisons') or [gene.get('comparison') or {}]
        for comparison in comparisons:
            if comparison.get('systems') and section['key'] not in comparison['systems']:
                continue
            keys = comparison.get('pattern_inputs') or [comparison.get('marker')]
            matched = [focus[k] for k in keys if k in focus]
            hypothesis = (comparison.get('status') == 'hypothesis' and comparison.get('applicable')
                and (comparison.get('quality') or {}).get('status') == 'usable'
                and (comparison.get('observation') or {}).get('current'))
            # Missing collection metadata limits the personal comparison, not
            # the sourced variant mechanism relevant to this measured marker.
            context = (comparison.get('knowledge_status') in ('supported', 'hypothesis')
                and comparison.get('level') in ('A', 'B', 'C', 'D')
                and (comparison.get('quality') or {}).get('status') == 'usable'
                and bool(comparison.get('reasons'))
                and set(comparison['reasons']) <= {'specimen_unknown', 'unit_scope', 'method_scope', 'fasting_unknown'}
                and comparison.get('source') and comparison.get('summary'))
            if not matched or not (comparison.get('eligible') or comparison.get('qualified_context') or hypothesis or context):
                continue
            for marker in matched:
                links.append({'kind': 'context' if context else 'hypothesis' if hypothesis else 'measurement',
                    'level': comparison.get('level'),
                    'marker': marker['key'], 'observation': marker, 'comparison': comparison,
                    'reason': t('visit.report.gene_for_marker', marker=marker['name']),
                    'qualification': (t('visit.report.variant_context_only') if context else
                                      comparison.get('comparison') or comparison.get('summary') or ''),
                    'status_label': comparison.get('status_label') or '',
                    'limitations': comparison.get('limitations') or '',
                    'source': comparison.get('source')})
        for flag in flags:
            if (flag['gene'], flag['rsid']) != (gene['gene'], gene['rsid']):
                continue
            links.append({'kind': 'prescription', 'drug': flag['drug'],
                'level': flag.get('level'),
                'reason': t('visit.report.gene_for_drug', drug=flag['drug']),
                'qualification': flag.get('why_it_matters') or flag['factor'], 'source': flag.get('source')})
        if not links:
            continue
        identity = (gene['gene'], gene['rsid'])
        if identity not in result:
            result[identity] = {**gene, 'system': section['key'], 'visit_links': []}
        saved = result[identity]['visit_links']
        for link in links:
            if link not in saved:
                saved.append(link)
        levels = [level for level in [gene.get('level'), *[link.get('level') for link in saved]]
                  if level in ('A', 'B', 'C', 'D', 'E')]
        if levels:
            result[identity]['level'] = max(levels)
    return sorted(result.values(), key=lambda g: (
        not any(link['kind'] == 'prescription' for link in g['visit_links']),
        not any((link.get('observation') or {}).get('abnormal') or
                (link.get('observation') or {}).get('outside_target') for link in g['visit_links']),
        g.get('level') or 'E', g['gene'], g['rsid']))


def build(data: dict, system_keys: list[str] | None, panel_keys: list[str] | None,
          question: str, *, full: bool = False, lab_markers: list[dict] | None = None) -> dict:
    """Selection is navigation, not a new clinical indication or a gene scan."""
    from .engine.system_panels import domains, _labs_layer, _medications_layer
    from .engine.thematic_panels import thematic_summaries, thematic_readings
    from .engine.labs import analyze_labs
    from .insight_context import _panel_rows, _genetic_context
    known = {d['key']: d for d in domains()}
    topics = {p['key']: p for p in thematic_summaries()}
    if not isinstance(question, str) or len(question) > 500:
        raise VisitFocusInvalid(t('visit.focus.invalid_question'))
    for requested, allowed in ((system_keys, known), (panel_keys, topics)):
        if requested is not None and (not isinstance(requested, list) or
                any(not isinstance(k, str) or k not in allowed for k in requested)):
            raise VisitFocusInvalid(t('visit.focus.invalid_selection'))
    suggested = _unique([i['system'] for i in data['agenda']['items'] if i.get('system') in known])
    panels = _unique(panel_keys or [])
    measured = {m['key']: m for m in (analyze_labs()['markers'] if lab_markers is None else lab_markers)}
    attention = {k for k, m in measured.items() if m.get('display_recency') is not False
                 and (m.get('abnormal') or m.get('outside_target'))}
    abnormal_systems = [key for key, domain in known.items() if attention.intersection(domain['markers'])]
    adverse_systems = [i['system'] for i in data['agenda']['items'] if i.get('system') in known and any(
        c.get('window') == 365 and c.get('status') in ('away', 'mixed')
        for c in (i.get('trajectory') or {}).get('changes') or [])]
    # Do not let three favourable trends displace another system's current deviation.
    priorities = _unique([k for k in suggested if k in abnormal_systems] + abnormal_systems + adverse_systems)
    selected = (_unique(system_keys) if system_keys is not None else
                _unique(priorities+suggested) if full else priorities or suggested)
    base_systems = core._read_knowledge('gencc_gene_disease.json').get('systems') or {}
    sections = []
    for key in selected:
        # Only the existing measurements are used here, not a second radar score.
        labs = _labs_layer(known[key], {}, measured)
        agenda = [i for i in data['agenda']['items'] if i.get('system') == key]
        # The same qualified context as system insights, also for a normal
        # system explicitly selected to discuss a diagnosis or a prescription.
        concepts = {gene.upper(): {a.get('disease_id') for a in entry.get('submissions') or []}
                    for gene, entry in (base_systems.get(key, {}).get('genes') or {}).items()}
        rows = _panel_rows(key, measured)
        genetics = [_reading_row(g, concepts.get(str(g.get('gene') or '').upper(), set())) for row in rows
                    if (g := _genetic_context(row, measured)) is not None]
        from .genetic_patterns import comparisons
        for comparison in comparisons(rows, measured, key):
            diplotype = (comparison.get('facts') or {}).get('diplotype')
            if not diplotype:
                if comparison.get('variant_readings'):
                    candidate = _reading_row({**comparison,
                        'genotype': {'genotype': comparison.get('display_genotype')},
                        'genetic_lab_comparison': comparison})
                    candidate.update(variant_readings=comparison['variant_readings'],
                                     association_id=comparison.get('association_id'))
                    genetics.append(candidate)
                continue
            components = comparison['variant_readings']
            if not any(r.get('read') is True for r in components):
                continue
            identities = {(r.get('gene'), r.get('rsid')) for r in components}
            genetics = [g for g in genetics if (g['gene'], g['rsid']) not in identities]
            genotype = diplotype.get('genotype') if diplotype['status'] == 'ok' else None
            summary = (comparison['summary'] if genotype else
                       diplotype.get('message') or t('genome.apoe_unconfirmed'))
            joint = _reading_row({'gene': comparison['gene'], 'rsid': comparison['rsid'],
                'genotype': {'genotype': genotype}, 'level': comparison['level'],
                'summary': summary, 'source': comparison['source'],
                'depth_note': '; '.join(str(r.get('rsid'))+': '+str((r.get('genotype') or {}).get('genotype') or '—')
                    +' · DP '+str((r.get('genotype') or {}).get('depth') or '—') for r in components)},
                concepts.get(comparison['gene'].upper(), set()))
            joint.update(comparison=comparison, variant_readings=components,
                         association_id=comparison.get('association_id'))
            genetics.append(joint)
        genetics = list({(g['gene'], g['rsid'], g.get('association_id')): g for g in genetics}.values())
        genetics.sort(key=lambda g: (not bool((g.get('comparison') or {}).get('eligible')),
                                      g.get('level') or 'E', g.get('gene') or '', g.get('rsid') or ''))
        markers = list(labs.get('current_markers') or [])
        included = {m['key'] for m in markers}
        for item in agenda:
            for fact in item['visit_brief'].get('measurements') or []:
                if fact['key'] not in included and fact['latest'].get('record') in ('metrics.json', 'wearable_trends.json'):
                    markers.append({**fact['latest'], 'key': fact['key'], 'name': fact['name']})
                    included.add(fact['key'])
        wanted = {f.get('key') for i in agenda for f in i.get('facts') or []}
        markers.sort(key=lambda m: (m['key'] not in wanted, not (m.get('abnormal') or m.get('outside_target')), m['key']))
        medications = _medications_layer(key).get('rows') or []
        cutoff = (date.today() - timedelta(days=365)).isoformat()
        histories = [{'key': m['key'], 'name': m['name'], 'series': [
            {**p, 'unit': p.get('unit') or m.get('unit'), 'record': 'labs.json'}
            for p in m.get('series') or [] if cutoff <= str(p.get('date') or '')[:10] <= date.today().isoformat()]}
            for m in markers if m.get('series')]
        if key == 'fitness':
            from .measurements import history, bmi_history
            metric_catalogue = core.wearable_metrics().get('metrics') or {}
            for metric in (history('weight'), bmi_history()):
                points = [p for p in metric['series'] if cutoff[:7] <= str(p['date'])[:7]]
                if points:
                    histories.append({'key': metric['key'], 'name': (
                        metric_catalogue.get(metric['metric']) or {}).get('label') or metric['metric'], 'series': points})
        focused = [m for m in markers if m['key'] in attention or m['key'] in wanted]
        if system_keys is not None and not focused:
            focused = markers
        focused.sort(key=lambda m: (m['key'] not in attention, m['key'] not in wanted, m['key']))
        sections.append({'key': key, 'label': t('radar.domain.'+key),
            'insights': [{'title': i['title'], **i['visit_brief']} for i in agenda],
            'measurements': [{k: m.get(k) for k in ('key', 'name', 'value', 'unit', 'unit_display',
                'date', 'censored', 'ref_low', 'ref_high', 'abnormal', 'outside_target', 'source', 'flag')}
                for m in (markers if full else markers[:5])],
            'measurement_count': len(markers), 'more_measurements': 0 if full else max(0, len(markers)-5),
            'genetics': genetics if full else genetics[:3], 'genetic_count': len(genetics), 'more_genetics': 0 if full else max(0, len(genetics)-3),
            'genetic_candidates': genetics,
            'focus_measurements': [{k: m.get(k) for k in ('key', 'name', 'value', 'unit', 'unit_display',
                'date', 'censored', 'ref_low', 'ref_high', 'abnormal', 'outside_target', 'source', 'flag')}
                for m in focused],
            'medications': medications, 'medication_preview': medications if full else medications[:3],
            'more_medications': 0 if full else max(0, len(medications)-3),
            'panels': thematic_summaries(key),
            'histories': histories,
            'destination': {'kind': 'system', 'key': key}})
    requested_panels = []
    for key in panels:
        panel = thematic_readings(key, 'clinician')
        rows = []
        for gene in panel['genes'] + panel['regions']:
            for position in gene['positions']:
                reading = position['reading']
                if reading['read']:
                    rows.append({**_reading_row({**position, 'genotype': reading}),
                        'reading': reading, 'personal_comparison': gene['personal_comparison']})
        rows.sort(key=lambda row: (row.get('level') or 'E', row['gene'], row['rsid']))
        requested_panels.append({'key': key, 'label': panel['label'], 'counts': panel['counts'],
            'readings': rows if full else rows[:3], 'more_readings': 0 if full else max(0, len(rows)-3),
            'note': panel['reading_note'], 'destination': {'kind': 'panel', 'key': key}})
    ids = {i['id'] for i in data['agenda']['items'] if i.get('system') in selected}
    questions = _unique([q for i in data['agenda']['items'] if i['id'] in ids for q in i.get('questions') or []])
    estimate_systems = {'fib4': {'liver'}, 'phenoage': set(selected)}
    estimates = [{**e, 'visit_systems': sorted(estimate_systems[e['key']].intersection(selected))} for e in (data.get('clinical_estimates') or {}).get('estimates') or []
                 if e['status'] == 'computed' and estimate_systems.get(e['key'], set()).intersection(selected)]
    return {'question': question.strip(), 'suggested': system_keys is None,
            'selected_systems': selected, 'selected_panels': panels,
            'choices': {'systems': [{'key': k, 'label': t('radar.domain.'+k)} for k in known],
                        'panels': list(topics.values())},
            'systems': sections, 'panels': requested_panels, 'questions': questions,
            'other_topic_count': sum(i['id'] not in ids for i in data['agenda']['items']),
            'safety': data['regimen_cautions'], 'safety_topics': data.get('safety_topics') or [], 'scope_note': t('visit.focus.scope'),
            'period': 365, 'clinical_estimates': estimates}


def document(data: dict, projection: dict, *, compact: bool) -> dict:
    """Presentation of existing conclusions, never a new treatment assessment.

    The source examples define the order, not medical rules or default values.
    Keep every factual date and the engine's existing qualifications. No genome,
    model, network or profile write is requested by this projection.
    """
    from .engine.system_panels import medication_system_context
    from .trend_qualification import comparable_observations
    selected = set(projection['selected_systems'])
    items = [i for i in data['agenda']['items'] if i.get('system') in selected]
    by_system = {key: [i for i in items if i.get('system') == key] for key in selected}
    all_charts = []
    seen = set()
    for section in projection['systems']:
        charts = []
        candidates = []
        for item in by_system[section['key']]:
            for change in (item.get('trajectory') or {}).get('changes') or []:
                if change.get('window') != 365:
                    continue
                candidates.append(change)
        existing = {c.get('marker') for c in candidates}
        candidates.extend({'marker': h['key'], 'name': h['name'], 'series': h['series']}
                          for h in section.get('histories') or [] if h['key'] not in existing)
        # Body mass has a single source-labelled timeline, including manual entries.
        for history in section.get('histories') or []:
            if history['key'] in ('weight', 'bmi'):
                candidates = [c for c in candidates if c.get('marker') != history['key']]
                candidates.insert(0, {'marker': history['key'], 'name': history['name'], 'series': history['series']})
        for change in candidates:
            series = change.get('series') or []
            if not series:
                continue
            identity = (change.get('marker'), tuple((p.get('date'), p.get('value'), p.get('unit')) for p in series))
            if identity in seen:
                continue
            seen.add(identity)
            qualification = comparable_observations(series)
            chart = {'key': change.get('marker'), 'name': change['name'],
                     'system': section['key'], 'system_label': section['label'],
                     'series': [{**p, 'unit_display': core.unit_label(p.get('unit') or '')} for p in series],
                     'summary': change.get('summary') or '',
                     'status': change.get('status'), 'comparison': change.get('comparison'),
                     'connect': qualification['eligible'], 'qualification': qualification,
                     'scope': 'recorded_observations_not_causation'}
            # Different units cannot share even a disconnected numeric axis.
            chart['numeric_axis'] = (len({p.get('unit') for p in series}) == 1
                                     and 'reporting_limit' not in qualification['reasons'])
            chart['display_connect'] = (chart['numeric_axis'] and change.get('marker') in ('weight', 'bmi'))
            if chart['display_connect']:
                chart['summary'] = t('visit.report.body_history')
            charts.append(chart)
            all_charts.append(chart)
        focus_order = {m['key']: n for n, m in enumerate(section.get('focus_measurements') or [])}
        charts.sort(key=lambda c: focus_order.get(c['key'], len(focus_order)))
        section['charts'] = charts
    # One card per selected system before extra charts from any single system.
    first = [s['charts'][0] for s in projection['systems'] if s['charts']]
    ordered = first + [c for c in all_charts if c not in first]
    headline_cards = []
    for section in projection['systems'][:3]:
        card_chart = section['charts'][0] if section['charts'] else None
        point = card_chart['series'][-1] if card_chart else next(iter(section['measurements']), None)
        if point is None:
            continue
        conclusions = [c for i in section['insights'] for c in i['conclusions']]
        headline_cards.append({'system': section['key'], 'label': section['label'],
            'name': card_chart['name'] if card_chart else (point or {}).get('name'),
            'point': point, 'summary': next(iter(conclusions), ''),
            'status': card_chart['status'] if card_chart else None})
    medication_rows = []
    for med in data.get('medications') or []:
        if not med.get('current'):
            continue
        context = medication_system_context(med)
        systems = set(context['systems'])
        if compact and not systems.intersection(selected):
            continue
        reviews = [r for i in items for r in i.get('treatment_review') or []
                   if r.get('drug') == med.get('name') and r.get('current') is not False]
        medication_rows.append({'name': med['name'], 'dose': med.get('dose'),
            'start_date': med.get('start_date'), 'scheme_date': med.get('scheme_date'),
            'start_date_provenance': med.get('start_date_provenance'),
            'systems': sorted(systems), 'system_labels': [t('radar.domain.'+key) for key in sorted(systems)],
            'links': context['system_links'],
            'outside_contexts': context['outside_contexts'],
            'response': list(dict.fromkeys(r['summary'] for r in reviews if r.get('summary') and r.get('comparisons'))),
            'response_assessed': any(r.get('response_assessed') is True for r in reviews),
            'has_observed_comparison': any(r.get('comparisons') for r in reviews),
            'causal': False,
            'controls': [c for c in data.get('treatment', {}).get('controls') or []
                         if c.get('name') == med['name'] and c.get('current') is not False
                         and c.get('status') in ('scheduled', 'overdue', 'recorded')]})
    if compact:
        medication_rows.sort(key=lambda m: not m['has_observed_comparison'])
    controls = [c for c in data.get('treatment', {}).get('controls') or []
                if c.get('current') is not False and (not compact or any(
                    m['name'] == c.get('name') for m in medication_rows))]
    ready_controls = [c for c in controls if c.get('status') in ('scheduled', 'overdue', 'recorded')]
    highlights = list(dict.fromkeys(c for section in projection['systems']
        for insight in section['insights'][:1] for c in insight['conclusions'][:1]))
    statuses = {c['status'] for c in all_charts if c['qualification']['eligible']}
    headline_key = 'mixed' if 'toward' in statuses and statuses.intersection({'away', 'mixed'}) else (
        'toward' if 'toward' in statuses else 'away' if 'away' in statuses else 'headline')
    if any(m.get('abnormal') or m.get('outside_target') for section in projection['systems']
           for m in section.get('focus_measurements') or []):
        headline_key = 'attention'
    questions = projection['questions']
    gene_rows: dict[tuple[str, str], dict] = {}
    shown_genes: dict[tuple[str, str], dict] = {}
    context_seen: set[tuple[str, str]] = set()
    for section in projection['systems']:
        candidates = section.get('genetic_candidates', section['genetics'])
        context_seen.update((g['gene'], g['rsid']) for g in candidates)
        section.setdefault('focus_measurements', section['measurements'])
        genetics = _discussion_genetics(section, data)
        section['discussion_genetics'] = genetics[:2] if compact else genetics
        section['discussion_genetic_count'] = len(genetics)
        section['more_discussion_genetics'] = len(genetics)-len(section['discussion_genetics'])
        for gene in genetics:
            gene_rows.setdefault((gene['gene'], gene['rsid']), gene)
        for gene in section['discussion_genetics']:
            shown_genes.setdefault((gene['gene'], gene['rsid']), gene)
        focus = {m['key'] for m in section['focus_measurements']}
        section['discussion_charts'] = [c for c in section['charts'] if c['key'] in focus and len(c['series']) > 1]
    return {'kind': 'short' if compact else 'full', 'version': 2,
            'title': t('visit.report.short' if compact else 'visit.report.full'),
            'headline': t('visit.report.'+headline_key), 'question': projection['question'],
            'highlights': highlights[:3], 'cards': headline_cards,
            'charts': ordered[:3 if compact else 4], 'all_chart_count': len(ordered),
            'systems': projection['systems'], 'panels': projection['panels'],
            'genetic_focus': list(shown_genes.values()), 'genetic_context_count': len(gene_rows),
            'genetic_read_count': len(context_seen),
            'more_genetic_focus': len(gene_rows.keys()-shown_genes.keys()),
            'medications': medication_rows[:6] if compact else medication_rows,
            'medication_count': len(medication_rows),
            'more_medications': max(0, len(medication_rows)-6) if compact else 0,
            'controls': ready_controls, 'unstructured_controls': len(controls)-len(ready_controls),
            'questions': questions[:4] if compact else questions,
            'more_questions': max(0, len(questions)-4) if compact else 0,
            'clinical_estimates': projection['clinical_estimates'],
            'safety': projection['safety'], 'safety_topics': projection['safety_topics'],
            'scope_note': projection['scope_note'], 'period': 365,
            'chronology_note': t('visit.report.chronology'),
            'response_note': t('visit.report.response_note'),
            'plan_note': t('visit.report.plan_note')}
