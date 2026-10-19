"""Dated patient testimony, kept separate from measured or causal findings."""
from __future__ import annotations

from datetime import date
from . import core
from .i18n import t
from .trend_qualification import observation_day

ASPECTS = ("symptom", "function", "tolerability")
CHANGES = ("better", "worse", "unchanged", "mixed")


def validate(stamp: str, response: object, note: str) -> bool:
    systems = {d['key'] for d in core._read_knowledge_raw('radar_domains.json').get('domains', [])}
    day = observation_day(stamp)
    return (isinstance(response, dict) and set(response) <= {'system', 'medication', 'aspect', 'change'}
            and len(stamp) == 10 and day is not None and day <= date.today()
            and all(isinstance(v, str) for v in response.values())
            and response.get('system') in systems and response.get('aspect') in ASPECTS
            and response.get('change') in CHANGES and isinstance(note, str) and bool(note.strip()))


def events() -> list[dict]:
    from .engine.insight_events import _event
    out = []
    meds = core.medications_json().get('medications') or []
    for r in core.focus_log().get('responses') or []:
        if not isinstance(r, dict) or not validate(str(r.get('date') or ''), r.get('response'), str(r.get('note') or '')):
            continue
        day = observation_day(r['date'])
        if day is None or (date.today() - day).days > 365:
            continue
        response = r['response']
        drug = response.get('medication') or ''
        candidates = [m for m in meds if (m.get('name') or '').casefold() == drug.casefold()]
        med = candidates[0] if len(candidates) == 1 else {}
        start, end = observation_day(med.get('start_date')), observation_day(med.get('end_date'))
        during = bool(start and start <= day and (end is None or day <= end)
                      and (core.is_active_medication(med) or end is not None))
        fact = {'record': 'focus_log.json', 'key': response['system'], 'date': r['date'],
                'source': 'patient_report', 'note': r['note'], **response,
                'drug': drug, 'during_recorded_course': during}
        detail = {'reported': True, 'causal': False, 'change': response['change'],
                  'summary': t('response.report', date=r['date'],
                      aspect=t('response.aspect.' + response['aspect']),
                      change=t('response.change.' + response['change']), note=r['note'])}
        if drug:
            detail['summary'] += ' ' + t('response.during' if during else 'response.linked', drug=drug)
        key = ':'.join((r['date'], response['system'], drug, response['aspect']))
        event = _event('reported_response', key, t('radar.domain.' + response['system']), [fact],
                       detail=detail, destination='overview', rule='dated-patient-report-v1')
        out.append(event)
    return out
