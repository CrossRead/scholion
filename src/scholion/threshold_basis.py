"""Separate a numerical catalogue comparison from a supported clinical threshold.

Identifier syntax is not clinical validation. The curated rule must also name
its applicability; an action never borrows the threshold's support. Unsupported
interpretation is withheld, not converted into a negative safety finding.
"""
from __future__ import annotations

from typing import Any, Dict
import math

from .conclusion_basis import conclusion_basis
from .i18n import t


def upper_bound_known(value: Any) -> bool:
    """An applicable upper bound must be a positive finite number, not a flag."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def compare_threshold(value: Any, rule: Dict[str, Any], *, censored: Any = None) -> Dict[str, Any]:
    """Pure numerical diagnostic; no clinical meaning or therapy advice."""
    limit = rule.get('value')
    side, comparison = rule.get('side'), rule.get('comparison')
    try:
        if censored or side not in ('high', 'low') or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError('not an uncensored finite value')
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit):
            raise ValueError('no finite boundary')
        if comparison not in (None, 'gt', 'lt') or (comparison == 'gt' and side != 'high') or (comparison == 'lt' and side != 'low'):
            raise ValueError('invalid boundary direction')
        crossed = value > limit if comparison == 'gt' else value < limit if comparison == 'lt' else value >= limit if side == 'high' else value <= limit
        distance = round((value - limit) / abs(limit) * 100, 1) if limit else None
    except (TypeError, ValueError):
        return {'crossed': None, 'why': 'censored' if censored else 'not_comparable', 'distance_pct': None}
    return {'crossed': bool(crossed), 'distance_pct': distance}


def guard_threshold(rule: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    """Keep arithmetic diagnostics, but expose only the independently held claim."""
    basis = conclusion_basis(rule.get('threshold_basis'))
    missing = list(basis['missing'])
    scope = rule.get('applicability')
    context = scope.get('context') if isinstance(scope, dict) else None
    context_held = bool(context.strip()) if isinstance(context, str) else (
        isinstance(context, dict) and all(isinstance(context.get(k), str) and context[k].strip() for k in ('en', 'ru')))
    if not isinstance(scope, dict) or scope.get('status') != 'held' or not context_held:
        missing.append('clinical_scope')
    if rule.get('multiple_of_ref_high') and not row.get('reference_high_known'):
        missing.append('reference_high')
    if missing:
        basis = {**basis, 'status': 'incomplete', 'missing': missing,
                 'reason': t('decision.basis_gap', parts=', '.join(t('conclusion.missing.' + k) for k in missing))}
    action = rule.get('action')
    action_basis = conclusion_basis(rule.get('action_basis')) if action else None
    out = {**row, 'threshold_basis': basis, 'action_basis': action_basis,
           'applicability': scope if isinstance(scope, dict) else None}
    if basis['status'] != 'complete':
        out.update(crossed=None, distance_pct=None, why='threshold_basis', label=None,
                   source=None, action=None)
    else:
        out['source'] = basis['source']
        out['action'] = action if action_basis and action_basis['status'] == 'complete' and row['crossed'] is True else None
    return out
