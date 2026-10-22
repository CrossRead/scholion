"""Body-composition observations retain their model, units and event pairing.

Fat, water, skeletal muscle and the manufacturer's bone estimate are overlapping
quantities, not a partition of total mass. There is no sum-to-one correction.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date

BODY = frozenset(('Weight', 'BMI', 'BodyFat', 'BodyWater', 'MuscleMass', 'BoneMass'))
ESTIMATES = BODY - {'Weight', 'BMI'}
DEFINITION_SOURCE = 'https://www8.garmin.com/manuals/webhelp/GUID-0BADEBCF-960D-4961-856C-86B9204BC169/EN-US/GUID-CB348359-1E39-491B-86B5-79CB12FB6A8C.html'
# The supported userBioMetrics schema uses grams for masses and percentages
# for bodyFat/bodyWater. Explicit incompatible units are refused, not guessed.
GARMIN_FIELDS = {'Weight': ('weight', 'g', 'kg'), 'BMI': ('bmi', '', ''),
                 'BodyFat': ('bodyFat', '%', '%'), 'BodyWater': ('bodyWater', '%', '%'),
                 'MuscleMass': ('muscleMass', 'g', 'kg'), 'BoneMass': ('boneMass', 'g', 'kg')}


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def field_value(value, unit, expected, output):
    reason = None
    if not number(value):
        reason = 'not_a_finite_number'
    elif unit not in (expected, output):
        reason = 'unit_unverified'
    normalised = value / 1000 if reason is None and unit == 'g' else value
    if reason is None:
        if output == '%' and not 0 <= normalised <= 100:
            reason = 'percentage_out_of_range'
        elif output != '%' and normalised < 0:
            reason = 'negative_value'
        elif normalised == 0:
            # The export does not document a universal zero sentinel. Retain it
            # as an uninterpreted source value rather than absence or a result.
            reason = 'zero_unverified'
    raw = value if not isinstance(value, float) or math.isfinite(value) else str(value)
    return {'raw_value': raw, 'raw_unit': unit, 'value': normalised if reason is None else None,
            'unit': output, 'status': 'usable' if reason is None else 'unverified', 'reason': reason}


def garmin_event(record: dict) -> dict:
    """One exported weight object is the pairing boundary, never a monthly mean."""
    meta = record.get('metaData') or {}
    body = record.get('weight')
    if not isinstance(body, dict):
        body = {}
    raw_stamp = body.get('timestamp') or body.get('measurementTime')
    stamp = raw_stamp if isinstance(raw_stamp, str) and len(raw_stamp) >= 10 and raw_stamp[4:5] == '-' else str(meta.get('calendarDate') or '')
    try:
        day = date.fromisoformat(stamp[:10])
        date_valid = day <= date.today()
    except ValueError:
        date_valid = False
    raw = json.dumps(record, sort_keys=True, default=str, ensure_ascii=False)
    event: dict = {'event_id': hashlib.sha256(raw.encode()).hexdigest(), 'date': stamp,
             'date_valid': date_valid, 'source_timestamp': raw_stamp, 'pairing': 'single_exported_record', 'source': 'garmin',
             'method': body.get('method'), 'device': body.get('deviceModel'),
             'algorithm_version': body.get('algorithmVersion'), 'calibration': body.get('calibration'),
             'definition_source': DEFINITION_SOURCE, 'fields': {}, 'derived': {}}
    for metric, (key, default_unit, output_unit) in GARMIN_FIELDS.items():
        if key not in body or body[key] is None:
            continue
        unit = body.get(key + 'Unit', default_unit)
        field = field_value(body[key], unit, default_unit, output_unit)
        field.update(raw_key=key, measurement_kind='reported_weight' if metric == 'Weight' else
                     'derived_index' if metric == 'BMI' else 'manufacturer_estimate')
        if not date_valid:
            field.update(value=None, status='unverified', reason='date_unverified')
        event['fields'][metric] = field
    weight = event['fields'].get('Weight', {}).get('value')
    if number(weight):
        for metric in ('MuscleMass', 'BoneMass'):
            field = event['fields'].get(metric)
            if field and number(field['value']) and field['value'] > weight:
                field.update(value=None, status='unverified', reason='mass_exceeds_paired_weight')
        fat = event['fields'].get('BodyFat', {}).get('value')
        if number(fat):
            event['derived'] = {
                'FatMass': {'value': round(weight * fat / 100, 5), 'unit': 'kg',
                            'measurement_kind': 'derived_estimate', 'inputs': ['Weight', 'BodyFat']},
                'FatFreeMass': {'value': round(weight * (1-fat/100), 5), 'unit': 'kg',
                                'measurement_kind': 'derived_estimate', 'inputs': ['Weight', 'BodyFat']}}
    return event


def event_points(block: dict, metric: str) -> list[dict]:
    """Read paired observations, keeping local monthly corrections authoritative."""
    composition = block.get('body_composition') or {}
    corrected = {(c.get('metric'), c.get('month')) for c in composition.get('corrections') or []}
    points = []
    for event in composition.get('events') or []:
        stamp = str(event.get('date') or '')
        field = (event.get('fields') or {}).get(metric) or {}
        if ((metric, stamp[:7]) in corrected or field.get('status') != 'usable'
                or not event.get('date_valid') or not number(field.get('value'))):
            continue
        points.append({'date': stamp, 'value': field['value'], 'unit': field['unit'],
                       'event_id': event['event_id'], 'source': event.get('source'),
                       'method': event.get('method'), 'device': event.get('device'),
                       'algorithm_version': event.get('algorithm_version'),
                       'calibration': event.get('calibration'),
                       'measurement_kind': field.get('measurement_kind'),
                       'aggregation': 'observation', 'record': 'wearable_trends.json'})
    return sorted(points, key=lambda p: (p['date'], p['event_id']))


def applicable_goal(metric: str, unit: str) -> dict | None:
    """A held, sourced personal goal; never infer a goal from sex or a trend."""
    from . import core
    from .conclusion_basis import conclusion_basis
    for goal in core.health_goals().get('targets') or []:
        ref = str(goal.get('source') or '').split(':')[-1]
        aliases = {'Weight': 'weight', 'BMI': 'bmi'}
        if ref not in (metric, aliases.get(metric)) or not number(goal.get('target')):
            continue
        if core.unit_label(goal.get('unit') or '') != core.unit_label(unit) or goal.get('dir') not in ('lower', 'higher'):
            continue
        basis = conclusion_basis(goal.get('target_basis'))
        scope = goal.get('applicability') or {}
        explicit = goal.get('target_confirmed') is True and bool(goal.get('target_source'))
        if (basis['status'] == 'complete' or explicit) and scope.get('status') == 'held' and scope.get('context'):
            return {**goal, 'basis': basis, 'comparison_kind': 'recorded_goal'}
    return None


def qualify(row: dict, block: dict | None = None) -> dict:
    """One status and interpretation qualification consumed by every surface."""
    if row.get('key') not in BODY:
        return row
    from .i18n import t
    block = block or {}
    metric = row['key']
    synthetic = bool((block.get('_meta') or {}).get('synthetic'))
    points = event_points(block, metric)
    kind = 'reported_weight' if metric == 'Weight' else 'derived_index' if metric == 'BMI' else 'manufacturer_estimate'
    result = {**row, 'measurement_kind': kind, 'synthetic': synthetic,
              'source_kind': 'synthetic' if synthetic else 'reported',
              'status': 'none', 'score': None, 'trend_good': None, 'improving': None,
              'direction': None, 'target_low': None, 'target_high': None,
              'counts_toward_conclusions': False,
              'composition_note': t('body.kind.'+kind),
              'delta_unit': t('body.percentage_points') if metric in ('BodyFat', 'BodyWater') else row.get('unit'),
              'body_quality': {'event_pairing': bool(points), 'legacy_summary': not bool(points),
                               'method_known': bool(points and points[-1].get('method'))},
              'why': t('body.estimate_notice') if metric in ESTIMATES else '',
              'clinical_basis': {}, 'unresolved_count': 0,
              'output_kind': 'recorded_measurement' if metric == 'Weight' else 'derived_measurement'}
    if metric == 'MuscleMass' and row.get('source') == 'garmin':
        result['label'] = t('body.garmin_muscle')
    if synthetic:
        result['composition_note'] = t('body.synthetic')+' · '+result['composition_note']
    # The shared current observation is authoritative, including a manual weight.
    current = row.get('current_observation')
    if points and not row.get('combined_history'):
        current = points[-1]
        months = {p['date'][:7] for p in points}
        legacy = [{**p, 'aggregation': 'monthly_mean'} for p in row.get('series') or []
                  if str(p.get('date'))[:7] not in months]
        combined = sorted(legacy+points, key=lambda p: str(p['date']))
        result.update(value=current['value'], date=current['date'], aggregation='observation',
                      current_observation=current, record=current['record'], value_smooth=None,
                      series=combined, smooth=[])
        result['body_quality']['legacy_summary'] = bool(legacy)
        if legacy:
            result['body_quality']['note'] = t('body.legacy_partial')
    if not current:
        result['aggregation'] = 'monthly_mean'
        result['body_quality']['note'] = t('body.legacy')
    if current and current.get('synthetic'):
        result['synthetic'] = True
        result['source_kind'] = 'synthetic'
        result['composition_note'] = t('body.synthetic')+' · '+t('body.kind.'+kind)
    result['body_quality']['event_pairing'] = bool(current and current.get('event_id'))
    if row.get('body_invalid_values'):
        result['body_quality']['invalid_note'] = t('body.invalid')
    comparison = dict(result.get('comparison') or {})
    for side in ('before', 'after'):
        period = dict(comparison.get(side) or {})
        events = [p for p in points if p['date'][:7] == str(period.get('date'))[:7]]
        if events:
            for key in ('method', 'device', 'algorithm_version', 'calibration'):
                value = events[0].get(key)
                if value is not None and all(p.get(key) == value for p in events):
                    period[key] = value
        if period:
            comparison[side] = period
    if metric in ESTIMATES:
        comparison['limitations'] = list(dict.fromkeys((comparison.get('limitations') or []) + ['body_estimate_accuracy_unknown']))
    result['comparison'] = comparison
    goal = applicable_goal(metric, row.get('unit') or '')
    result['body_goal'] = goal
    if goal and number(result.get('value')):
        value, target = result['value'], goal['target']
        reached = value <= target if goal['dir'] == 'lower' else value >= target
        result.update(status='ok' if reached else 'warn',
                      status_text=t('body.goal_reached' if reached else 'body.goal_above' if goal['dir']=='lower' else 'body.goal_below'),
                      counts_toward_conclusions=False)
        comparison = result.get('comparison') or {}
        if comparison.get('eligible') and comparison.get('distinguishable') is True:
            before, after = comparison.get('before') or {}, comparison.get('after') or {}
            conditions = ('method', 'device', 'algorithm_version', 'calibration')
            comparable = all(before.get(k) is not None and before.get(k) == after.get(k) for k in conditions)
            if comparable and number(before.get('value')) and number(after.get('value')):
                toward = abs(after['value']-target) < abs(before['value']-target)
                result.update(trend_good=toward, improving=toward, counts_toward_conclusions=True,
                              qualified_change_text=t('body.toward_goal' if toward else 'body.away_goal'))
                result['trend'] = {'from': before['date'], 'to': after['date'], 'delta': comparison['delta'],
                                   'direction': 'up' if comparison['delta']>0 else 'down',
                                   'distinguishable': True, 'mdd': comparison.get('mdd')}
    return result


def monthly_values(metric: str, series: dict) -> tuple[dict, list[dict]]:
    clean, invalid = {}, []
    output = '%' if metric in ('BodyFat', 'BodyWater') else '' if metric == 'BMI' else 'kg'
    for stamp, raw in series.items():
        field = field_value(raw, output, output, output)
        if field['status'] == 'usable':
            clean[stamp] = field['value']
        else:
            invalid.append({'date': stamp, **field})
    return clean, invalid


def invalid_values(block: dict, metric: str) -> list[dict]:
    return [{'date': event.get('date'), **field}
            for event in (block.get('body_composition') or {}).get('events') or []
            for key, field in (event.get('fields') or {}).items()
            if key == metric and field.get('status') != 'usable']
