"""A number observed, catalogued or entered is not an automatic treatment goal.

Structured guideline citations are retained; they do not lend support to an
unreviewed sentence, quote or choice of population. Historical extrema and
laboratory bounds remain observations, not clinical recommendations.
"""
from __future__ import annotations

import math
from typing import Any, Dict

from .conclusion_basis import conclusion_basis
from .i18n import t


def guard_goal_candidate(spec: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    """Require the proposed target's own support and known applicability."""
    basis = conclusion_basis(spec.get('target_basis'))
    scope = spec.get('applicability')
    context = scope.get('context') if isinstance(scope, dict) else None
    text_known = bool(context.strip()) if isinstance(context, str) else (
        isinstance(context, dict) and all(isinstance(context.get(k), str) and context[k].strip() for k in ('en', 'ru')))
    missing = list(basis['missing'])
    if not isinstance(scope, dict) or scope.get('status') != 'held' or not text_known:
        missing.append('clinical_scope')
    # Neither an assumed risk category nor an unconfirmed diagnosis selects a
    # population. Merely printing that assumption does not make it applicable.
    if row.get('assumed') or row.get('applies_when'):
        missing.append('individual_applicability')
    if row.get('unit') != row.get('observation_unit'):
        missing.append('unit_match')
    value = row.get('value')
    if not row.get('no_target') and (isinstance(value, bool) or not isinstance(value, (int, float))
                                   or not math.isfinite(value) or row.get('comparator') not in ('<', '<=', '>', '>=')):
        missing.append('target_value')
    basis = {**basis, 'status': 'incomplete' if missing else 'complete', 'missing': missing,
             'reason': t('conclusion.withheld', missing=', '.join(t('conclusion.missing.' + k) for k in missing)) if missing else None}
    out = {**row, 'proposal_status': 'held' if not missing else 'withheld', 'target_basis': basis,
           'applicability': scope if isinstance(scope, dict) else None}
    for name in ('quote', 'note', 'still_matters_when'):
        if row.get(name):
            own = conclusion_basis(spec.get(name + '_basis'))
            out[name + '_basis'] = own
            if own['status'] != 'complete':
                out[name] = None
    if missing:
        out['catalogue_comparison'] = {k: row[k] for k in ('value', 'comparator', 'no_target') if k in row}
        out.update(value=None, comparator=None, no_target=False, why=basis['reason'], alternatives=[],
                   assumed=None, cannot_be_decided_here=None)
    return out


def goal_basis_text(row: Dict[str, Any]) -> str:
    """Visible support or refusal alongside the candidate, including aggregates."""
    basis = row.get('target_basis')
    if not basis:
        return t('goalgen.observation_only') if row.get('proposal_status') == 'observation' else ''
    detail = basis['reason'] if basis['status'] != 'complete' else str(basis['source']) + ' · ' + str(basis['mechanism'])
    return t('goalgen.basis', detail=detail)
