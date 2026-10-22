"""One read-only history for recorded and wearable measurements.

A common timeline retains the source and aggregation of every observation.
Current values prefer a dated reading over a mean from the same month. Trend
qualification uses homogeneous streams, never a mixture of means and readings.
"""
from __future__ import annotations

from datetime import date
from math import isfinite
from . import core, wearables


def _valid(point: dict) -> bool:
    stamp, value = str(point.get('date') or ''), point.get('value')
    try:
        day = date.fromisoformat(stamp + '-01' if len(stamp) == 7 else stamp[:10])
    except ValueError:
        return False
    return day <= date.today() and isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def streams(points: list[dict]) -> list[list[dict]]:
    """Keep measurement conditions separate for arithmetic and inference."""
    grouped: dict[tuple, list[dict]] = {}
    for p in points:
        key = tuple(p.get(k) for k in ('measurement_source', 'aggregation', 'unit', 'method', 'device'))
        grouped.setdefault(key, []).append(p)
    return list(grouped.values())


def history(key: str, device: str | None = None) -> dict:
    """Resolve a person-metric key, or an exact wearable catalogue key.

    Explicit device references remain explicitly scoped. Unselected conflicting
    devices keep their histories, but cannot silently choose a current value.
    """
    catalogue = core.wearable_metrics().get('metrics') or {}
    name = 'BMI' if key == 'bmi' else next((n for n, s in catalogue.items() if s.get('person_metric') == key), key)
    person_key = 'bmi' if name == 'BMI' else (catalogue.get(name) or {}).get('person_metric') or key
    spec = catalogue.get(name) or {}
    data = core.metrics_json()
    manual = (data.get('metrics') or {}).get(person_key) or {}
    raw_unit = (core._read_knowledge_raw('wearable_metrics.json').get('metrics', {}).get(name) or {}).get('unit')
    unit = manual.get('unit') or (raw_unit.get('en', '') if isinstance(raw_unit, dict) else raw_unit) or ''
    # Recognized unit labels denote the same quantity; never join different units.
    same_unit = not manual.get('unit') or not spec.get('unit') or core.unit_label(manual['unit']) == core.unit_label(spec['unit'])
    points = []
    rejected = []
    from .body_composition import BODY, monthly_values
    def usable(value, stamp):
        if name not in BODY:
            return True
        clean, bad = monthly_values(name, {str(stamp): value})
        rejected.extend(bad)
        return bool(clean)
    if not device:
        for p in manual.get('series') or []:
            if usable(p.get('value'), p.get('date')) and _valid(p) and (not p.get('unit') or core.unit_label(p['unit']) == core.unit_label(unit)):
                points.append({**p, 'unit': unit, 'measurement_source': 'recorded',
                    'aggregation': p.get('aggregation') or 'observation',
                    'record': 'metrics.json', 'synthetic': bool((data.get('_meta') or {}).get('synthetic'))})
    for src, block in wearables.series(core.wearable_trends()):
        if device and src != device:
            continue
        if not same_unit:
            continue
        from .body_composition import event_points
        events = event_points(block, name)
        event_months = {p['date'][:7] for p in events}
        for event in events:
            point = {**event, 'measurement_source': src, 'source': src,
                     'unit': unit, 'synthetic': bool((block.get('_meta') or {}).get('synthetic'))}
            if _valid(point):
                points.append(point)
        for month, value in ((block.get('metrics') or {}).get(name) or {}).items():
            if str(month)[:7] in event_months:
                continue
            p = {'date': str(month), 'value': value, 'unit': unit,
                 'measurement_source': src, 'source': src, 'device': src,
                 'aggregation': 'monthly_mean', 'record': 'wearable_trends.json',
                 'stats': ((block.get('stats') or {}).get(name) or {}).get(month) or {}}
            if usable(value, month) and _valid(p):
                points.append(p)
    points.sort(key=lambda p: (str(p['date']), p['measurement_source']))
    latest = current(points, device)
    return {'key': person_key, 'metric': name, 'unit': unit, 'series': points,
            'latest': latest, 'invalid_values': rejected, 'missing': 'several_devices' if points and not latest else 'empty_series' if not points else None}


def current(points: list[dict], device: str | None = None) -> dict | None:
    """Select the current reading once, for all screens and calculations."""
    if not points:
        return None
    if not any(p.get('measurement_source') for p in points):
        return max(points, key=lambda p: str(p.get('date') or ''))
    device_sources = {p['measurement_source'] for p in points} - {'recorded'}
    primary = device or core.wearable_primary()
    candidates = [p for p in points if p['measurement_source'] == 'recorded' or
                  len(device_sources) <= 1 or p['measurement_source'] == primary]
    latest = max(candidates, key=lambda p: (str(p['date'])[:7], p['measurement_source'] == 'recorded', str(p['date'])), default=None)
    if latest and latest['measurement_source'] == 'recorded' and len(device_sources) > 1 and primary not in device_sources:
        if any(str(p['date'])[:7] > str(latest['date'])[:7] for p in points):
            latest = None
    return latest


def bmi_history() -> dict:
    """Derive every BMI point from the same weight history and recorded height."""
    weights = history('weight')
    raw = (core.metrics_json().get('profile') or {}).get('height_cm')
    try:
        height = float(raw) if raw is not None and not isinstance(raw, bool) else 0.0
    except (TypeError, ValueError):
        height = 0.0
    if not isfinite(height) or height <= 0 or core.unit_label(weights['unit']) != core.unit_label('kg') or not weights['series']:
        return history('BMI')
    def derive(p):
        return {**p, 'value': round(p['value'] / (height / 100) ** 2, 1), 'unit': 'kg/m²',
                'weight_kg': p['value'], 'height_cm': height, 'method': 'weight_kg / height_m^2',
                'height_record': 'metrics.json:profile.height_cm'}
    return {**weights, 'key': 'bmi', 'metric': 'BMI', 'unit': 'kg/m²',
            'series': [derive(p) for p in weights['series']],
            'latest': derive(weights['latest']) if weights['latest'] else None,
            'derived': True, 'height_cm': height}
