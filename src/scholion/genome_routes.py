"""Three decision-workflow routes, distinct from routes of administration.

These describe data prerequisites, not a prescription or an automatic test
order. A blocked route never licenses a conclusion or declares a marker absent.
"""
from __future__ import annotations

import math
from typing import Any, Dict

from .i18n import t

ROUTES = ('decision_now', 'first_lab', 'no_marker')


def decision_route(row: Dict[str, Any], markers: Dict[str, Any], *, reference: bool = False) -> Dict[str, Any]:
    """Route the gated row, never a raw catalogue claim or an assumed genotype."""
    blocks = []
    if reference:
        blocks.append('reference_only')
    if row.get('level') not in ('A', 'B'):
        blocks.append('evidence_level')
    if (row.get('conclusion_basis') or {}).get('status') != 'complete':
        blocks.append('basis')
    reading = row.get('reading') or row.get('genotype') or {}
    if row.get('read', reading.get('read')) is not True:
        blocks.append('genotype')
    quality = reading.get('quality') or {}
    if row.get('presumed') or row.get('needs_confirmation') or reading.get('depth_unverified') \
            or reading.get('confidence') == 'profile' or any(quality.get(k) for k in
                ('depth_unverified', 'low_depth', 'filtered', 'strand_ambiguous', 'imputed', 'confirmation_reasons')):
        blocks.append('confirmation')
    exp = row.get('expect_check') or row.get('expect')
    own = (row.get('subclaim_basis') or {}).get('expect') or {}
    marker = exp.get('marker') if isinstance(exp, dict) and own.get('status') == 'complete' else None
    kind = 'no_marker'
    observation = None
    if marker:
        m = markers.get(marker) or {}
        value = m.get('value')
        from .store import date_resolution
        exact = not any(p.get('censored') for p in m.get('series', []) if p.get('date') == m.get('date'))
        measured = isinstance(value, (int, float)) and not isinstance(value, bool) \
            and math.isfinite(value) and isinstance(m.get('unit'), str) and bool(m['unit'].strip()) \
            and isinstance(m.get('date'), str) and date_resolution(m['date']) is not None and exact
        kind = 'decision_now' if measured else 'first_lab'
        if measured:
            observation = {k: m.get(k) for k in ('value', 'unit', 'date')}
        else:
            blocks.append('measurement')
    elif own.get('status') == 'incomplete':
        blocks.append('marker_basis')
    return {'kind': kind, 'label': t('genome.route.' + kind), 'ready': not blocks,
            'marker': marker, 'observation': observation, 'blocked_by': blocks,
            'reason': ' · '.join(t('genome.route.block.' + b) for b in blocks)
                      if blocks else t('genome.route.known_marker' if marker else 'genome.route.undeclared_marker'),
            'basis': row.get('conclusion_basis'), 'marker_basis': own or None,
            'notice': t('genome.route.notice')}


def route_text(row: Dict[str, Any]) -> str:
    route = row.get('decision_route')
    return t('genome.route.line', label=route['label'], reason=route['reason']) + ' · ' + route['notice'] if route else ''
