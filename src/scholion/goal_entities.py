"""One read model for recorded goals, without moving or inventing their records.

Origin is the stated reason for a goal, not the location of its measurements.
Legacy records without that reason stay explicitly unresolved. The same IDs
and provenance reach the dashboard, focus, CLI and agent transports.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterator, Tuple

from . import core
from .i18n import t

ORIGINS = ('complaint', 'lab', 'genome', 'history', 'clinician', 'prevention')


def records() -> Iterator[Tuple[str, Tuple[Any, ...], Dict[str, Any]]]:
    """Only established container files; never an arbitrary path from a client."""
    for filename, field in (('health_goals.json', 'targets'), ('clinician_targets.json', 'targets'),
                            ('focus.json', 'tracks')):
        path = core.profile_dir() / filename
        data = core.read_profile_json(path) if path.exists() else {}
        for index, row in enumerate(data.get(field) or []):
            if isinstance(row, dict):
                yield filename, (field, index), row
        if filename == 'focus.json' and isinstance(data.get('focus'), dict) and data['focus']:
            yield filename, ('focus',), data['focus']


def entity_id(filename: str, pointer: Tuple[Any, ...], row: Dict[str, Any]) -> str:
    """Bind an edit to this record, not another record reordered into its slot."""
    identity = {k: v for k, v in row.items() if k != 'origin'}
    payload = json.dumps([filename, pointer, identity], sort_keys=True, ensure_ascii=False)
    return 'goal-' + hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]


def origin_view(row: Dict[str, Any], filename: str) -> Dict[str, Any]:
    origin = row.get('origin')
    if origin is None and filename == 'clinician_targets.json':
        # This file explicitly records the clinician's instruction. A lab
        # source in a personal target does NOT similarly establish its origin.
        origin = {'kind': 'clinician', 'reason': row.get('source'), 'on': row.get('set_on')}
    origin = origin if isinstance(origin, dict) else {}
    valid = origin.get('kind') in ORIGINS \
        and isinstance(origin.get('reason'), str) and bool(origin['reason'].strip())
    return {'status': 'recorded' if valid else 'unspecified',
            'kind': origin['kind'] if valid else None,
            'label': t('goal.origin.' + origin['kind']) if valid else t('goal.origin.unspecified'),
            'reason': origin['reason'] if valid else None,
            'on': origin.get('on') if valid else None}


def goal_entities() -> list[Dict[str, Any]]:
    out = []
    for filename, pointer, row in records():
        metric = row.get('metric')
        metric = metric if isinstance(metric, dict) else {}
        target = {k: row[k] for k in ('low', 'high', 'value', 'unit') if k in row} \
            if filename == 'clinician_targets.json' else row.get('target', metric.get('target'))
        out.append({'id': entity_id(filename, pointer, row),
                    'kind': 'focus' if pointer == ('focus',) else 'track' if pointer[0] == 'tracks' else 'target',
                    'title': row.get('label') or row.get('title') or row.get('marker') or row.get('id') or t('goal.title_default'),
                    'origin': origin_view(row, filename), 'target': target,
                    'measurement_source': row.get('source') if filename == 'health_goals.json' else row.get('marker') or metric.get('key'),
                    'record': {'file': filename, 'pointer': list(pointer)},
                    'provenance': row.get('_from') or {'source': filename, 'on': row.get('set_on') or row.get('started')}})
    return out


def origin_edit(goal_id: str, kind: str, reason: str) -> Dict[str, Any]:
    """Validate and prepare a human's metadata edit; no write or clinical choice."""
    if kind not in ORIGINS or not isinstance(reason, str) or not reason.strip():
        return {'ok': False, 'error': t('goal.origin.invalid')}
    for filename, pointer, row in records():
        if entity_id(filename, pointer, row) == goal_id:
            return {'ok': True, 'file': filename, 'pointer': pointer,
                    'origin': {'kind': kind, 'reason': reason.strip()}}
    return {'ok': False, 'error': t('goal.origin.stale')}
