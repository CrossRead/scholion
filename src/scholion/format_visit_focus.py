"""Compact visit rendering from the shared appointment projection."""
from __future__ import annotations

from .i18n import t
from .format_primitives import _n


def report(data: dict) -> str:
    if data.get('document'):
        return _document_report(data)
    from .format_prescription import caution_lines
    from .genetic_comparison import lines as comparison_lines
    visit = data['appointment']
    lines = [(data.get('document') or {}).get('title') or data['title'], t('visit.stamp', id=data['container'].get('id') or '—',
             version=data['version'], date=data['as_of']), visit['scope_note']]
    lines.extend(document_overview(data))
    if data.get('synthetic'):
        lines.append(t('web.header.demo_banner'))
    if visit['question']:
        lines += ['', t('visit.focus.question'), visit['question']]
    lines.extend(caution_lines(visit['safety']))
    for topic in visit.get('safety_topics') or []:
        lines.append(topic['title'])
        lines.extend(topic['visit_brief']['support'])
        for measured in topic['visit_brief']['measurements']:
            point = measured['latest']
            lines.append(measured['name']+': '+_n(point['value'])+' '+str(point.get('unit') or '')+' · '+point['date'])
    for estimate in visit.get('clinical_estimates') or []:
        lines.append(estimate['name']+': '+str(estimate['value'])+' '+estimate['unit']+' · '+str(estimate['date']))
        lines.extend([estimate.get('interpretation') or '', estimate['source']])
    for section in visit['systems']:
        lines += ['', section['label']]
        for insight in section['insights']:
            lines.extend(insight['conclusions'])
            lines.extend(insight['support'])
            for comparison in insight['comparisons']:
                lines.extend(comparison_lines(comparison))
        for row in section['measurements']:
            bounds = (' · ' + t('visit.reference_bounds') + ': ' + _n(row['ref_low']) + '–' + _n(row['ref_high'])
                      if row['ref_low'] is not None or row['ref_high'] is not None else '')
            lines.append(f"• {row['name']}: {row.get('censored') or ''}{_n(row['value'])} "
                         f"{row.get('unit_display') or row.get('unit') or ''} · {row['date']}" + bounds)
        if not section['measurements'] and not data.get('document'):
            lines.append(t('visit.focus.no_measurements'))
        if section['more_measurements']:
            lines.append(t('visit.focus.more_measurements', n=section['more_measurements']))
        if section['medications']:
            lines.append(t('visit.medications') + ': ' + '; '.join(
                m['name'] + (' · '+str(m['dose']) if m.get('dose') else '') for m in section['medication_preview']))
        if section['more_medications']:
            lines.append(t('visit.focus.more_medications', n=section['more_medications']))
        for row in section['genetics']:
            lines.append(f"• {row['gene']} {row['rsid']}: {row.get('genotype') or '—'} · "
                         + t('visit.focus.level', level=row.get('level') or '—'))
            lines.extend(str(row[k]) for k in ('function', 'summary', 'reading_note', 'source') if row.get(k))
            for assertion in row['gencc']:
                lines.append(t('gencc.assertion', disease=assertion.get('disease_label') or assertion.get('disease') or '—',
                    classification=assertion.get('classification_label') or assertion.get('classification') or '—', moi=assertion.get('moi_label') or assertion.get('moi') or '—',
                    submitter=assertion.get('submitter') or '—', date=assertion.get('curated_on') or '—'))
        if section['more_genetics']:
            lines.append(t('visit.focus.more_genetics', n=section['more_genetics']))
        lines.append('scholion system '+section['key']+' --register clinician')
    for panel in visit['panels']:
        lines += ['', panel['label'], panel['note']]
        for row in panel['readings']:
            lines.append(f"• {row['gene']} {row['rsid']}: {row['reading']['message']}")
            reference = row['reference_context']
            lines.extend(str(reference[k]) for k in ('gene_function', 'variant_context', 'gene_source', 'variant_source')
                         if reference.get(k))
        if not panel['readings'] and not data.get('document'):
            lines.append(t('visit.focus.no_panel_calls'))
        if panel['more_readings']:
            lines.append(t('visit.focus.more_genetics', n=panel['more_readings']))
        lines.append('scholion system '+panel['key']+' --register clinician')
    if visit['questions']:
        lines += ['', t('visit.questions'), *['• '+q for q in visit['questions']]]
    if visit['other_topic_count']:
        lines += ['', t('visit.focus.other', n=visit['other_topic_count'])]
    return '\n'.join(lines+['', data['disclaimer']])


def _document_report(data: dict) -> str:
    """System-first handout shared by terminal, MCP and plugin readers."""
    from .format_prescription import caution_lines
    doc = data['document']
    lines = [doc['title'], t('visit.stamp', id=data['container'].get('id') or '—',
             version=data['version'], date=data['as_of']), doc['scope_note']]
    if data.get('synthetic'):
        lines.append(t('web.header.demo_banner'))
    lines.extend(document_overview(data, include_charts=False))
    lines.extend(caution_lines(doc['safety']))
    for topic in doc['safety_topics']:
        lines.extend([topic['title'], *topic['visit_brief']['support']])
    for section in doc['systems']:
        lines += ['', section['label']]
        lines.extend(dict.fromkeys(c for i in section['insights'] for c in i['conclusions']))
        for marker in section['focus_measurements']:
            lines.append(marker['name']+': '+str(marker.get('censored') or '')+_n(marker['value'])+' '
                +str(marker.get('unit_display') or marker.get('unit') or '')+' · '+str(marker['date']))
            if marker.get('source'):
                lines.append(str(marker['source']))
        for chart in section['discussion_charts']:
            lines.append(chart['name']+': '+(' → ' if chart['connect'] else '; ').join(
                _n(p.get('value'))+' '+str(p.get('unit_display') or p.get('unit') or '')
                +' ('+str(p.get('date') or '—')+')' for p in chart['series']))
            if chart['summary']:
                lines.append(chart['summary'])
            if not chart['connect']:
                lines.append(t('visit.report.separate'))
        for gene in section['discussion_genetics']:
            lines += [f"{gene['gene']} {gene['rsid']}: {gene.get('genotype') or '—'} · Scholion {gene.get('level') or '—'}"]
            lines.extend(str(gene[k]) for k in ('function', 'summary', 'reading_note', 'source') if gene.get(k))
            for link in gene['visit_links']:
                lines.extend([t('visit.report.gene_reason')+': '+link['reason'], link['qualification']])
                if link.get('source'):
                    lines.append(link['source'])
                if link.get('limitations'):
                    lines.append(link['limitations'])
            for reading in gene.get('variant_readings') or []:
                for variant in reading.get('variant_records') or []:
                    lines.append(f"{variant.get('chrom')}:{variant.get('pos')} {variant.get('ref')}>{variant.get('alt')}"
                        + ' · '+str(variant.get('zygosity') or '')+' · ClinVar '+str(variant.get('classification') or ''))
            for assertion in gene.get('gencc') or []:
                lines.append(t('gencc.assertion', disease=assertion.get('disease_label') or assertion.get('disease') or '—',
                    classification=assertion.get('classification_label') or assertion.get('classification') or '—',
                    moi=assertion.get('moi_label') or assertion.get('moi') or '—',
                    submitter=assertion.get('submitter') or '—', date=assertion.get('curated_on') or '—'))
        if section['more_discussion_genetics']:
            lines.append(t('visit.report.more_factors', n=section['more_discussion_genetics']))
        lines.append('scholion system '+section['key']+' --register clinician')
    if doc['genetic_context_count']:
        lines.extend([t('visit.report.genetic_count', total=doc['genetic_context_count'], shown=len(doc['genetic_focus'])),
                      t('visit.focus.separate_scales')])
    for panel in doc['panels']:
        if panel['readings']:
            lines.extend(['', panel['label'], panel['note']])
        for gene in panel['readings']:
            lines.append(f"{gene['gene']} {gene['rsid']}: {gene.get('genotype') or '—'} · Scholion {gene.get('level') or '—'}")
            lines.extend(str(gene[k]) for k in ('function', 'summary', 'reading_note', 'source') if gene.get(k))
    for estimate in doc['clinical_estimates']:
        lines.extend([estimate['name']+': '+str(estimate['value'])+' '+estimate['unit']+' · '+str(estimate['date']),
                      estimate.get('interpretation') or '', estimate['source']])
    if doc['questions']:
        lines.extend(['', t('visit.questions'), *doc['questions']])
    if doc['kind'] == 'full':
        for key, heading in (('held_measurements', 'visit.held'), ('historical_measurements', 'visit.historical')):
            rows = data.get(key) or []
            if rows:
                lines.extend(['', t(heading, n=len(rows))])
            for row in rows:
                lines.append(row['name']+': '+str(row.get('censored') or '')+_n(row.get('value'))
                    +' '+str(row.get('unit') or '')+' · '+str(row.get('date') or '—'))
                lines.extend(str(row[k]) for k in ('source_label', 'recency_note') if row.get(k))
    appendix = data.get('reference_appendix') or {}
    if appendix.get('included'):
        from .panel_reference import interpretation_lines, reference_lines
        lines.extend(['', t('visit.appendix'), data['appendix_note']])
        for panel in appendix['panels']:
            lines.append(panel['label'])
            for row in panel['positions']:
                lines.append(f"{row.get('gene')} {row.get('rsid') or ''} · "+str(row.get('reading_label') or '—'))
                lines.extend(reference_lines(row))
                lines.extend(interpretation_lines(row))
                passport = row.get('passport') or {}
                if passport:
                    lines.append(t('web.hyp.head', level=passport['level']))
                    lines.append(passport.get('reported') or t('system.hyp.no_sentence'))
                    for field in ('why_this_level', 'mechanism', 'effect', 'population', 'study',
                                  'replication', 'would_confirm', 'would_refute', 'source'):
                        if passport.get(field):
                            lines.append(t('system.hyp.part.'+field, value=passport[field]))
                    if passport.get('missing'):
                        lines.append(t('system.hyp.missing', parts=', '.join(
                            t('system.hyp.name.'+field) for field in passport['missing'])))
    return '\n'.join(lines+['', data['disclaimer']])


def document_overview(data: dict, *, include_charts: bool = True) -> list[str]:
    """The same source-backed overview for terminal and assistant readers."""
    doc = data.get('document')
    if not doc:
        return []
    result = ['', doc['headline']]
    result.extend('• '+line for line in doc['highlights'])
    if doc['question']:
        result.extend([t('visit.focus.question'), doc['question']])
    for chart in doc['charts'] if include_charts else []:
        result.append(chart['name']+': '+(' → ' if chart['connect'] else '; ').join(
            str(p.get('censored') or '')+_n(p.get('value'))+' '+str(p.get('unit_display') or p.get('unit') or '')
            +' ('+str(p.get('date') or '—')+')' for p in chart['series']))
        if chart['summary']:
            result.append(chart['summary'])
        if not chart['connect']:
            result.append(t('visit.report.separate'))
    result.append(doc['chronology_note'])
    report_medications = ([m for m in doc['medications'] if m['has_observed_comparison']]
                          if doc['kind'] == 'short' else doc['medications'])
    if report_medications:
        result.extend(['', t('visit.report.response')])
        for med in report_medications:
            result.append(med['name']+' · '+str(med.get('dose') or '—')+' · '
                          +str(med.get('start_date') or ''))
            if med['has_observed_comparison']:
                result.extend(med['response'])
        if doc['more_medications']:
            result.append(t('visit.report.more_rx', n=doc['more_medications']))
        result.append(doc['response_note'])
    if doc['controls']:
        result.extend(['', t('visit.report.plan')])
    for control in doc['controls']:
        result.append(str(control.get('name') or '')+' · '+str(control.get('marker') or '')
                      +' · '+str(control.get('due') or '—')+' · '+str(control.get('plan_source') or ''))
    return result
