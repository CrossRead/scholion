"""A catalogue trigger is not a supported test order or a monitoring schedule.

Support is structural, not clinical certification: each curated sentence still
needs source review. Existing measurements remain observations even when a
proposed test or its timing is withheld. No support is borrowed across claims.
"""
from __future__ import annotations

from typing import Any, Dict

from .conclusion_basis import conclusion_basis
from .i18n import t


def _text_known(text: Any) -> bool:
    return bool(text.strip()) if isinstance(text, str) else (
        isinstance(text, dict) and all(isinstance(text.get(k), str) and text[k].strip() for k in ('en', 'ru')))


def _basis(rule: Dict[str, Any], name: str, text: Any) -> Dict[str, Any]:
    basis = conclusion_basis(rule.get(name + '_basis'))
    missing = list(basis['missing'])
    if not _text_known(text):
        missing.append('claim_text')
    return {**basis, 'status': 'incomplete' if missing else 'complete', 'missing': missing,
            'reason': t('conclusion.withheld', missing=', '.join(t('conclusion.missing.' + k) for k in missing)) if missing else None}


def guard_test_proposal(rule: Dict[str, Any]) -> Dict[str, Any]:
    """Keep a triggered candidate visible; withheld advice is never a low priority."""
    scope = rule.get('applicability')
    scope_held = isinstance(scope, dict) and scope.get('status') == 'held' and _text_known(scope.get('context'))
    bases = {name: _basis(rule, name, rule.get(name)) for name in ('suggest', 'why')}
    condition = conclusion_basis(rule.get('condition_basis'))
    missing = list(condition['missing'])
    if not scope_held:
        missing.append('clinical_scope')
    bases['condition'] = {**condition, 'status': 'incomplete' if missing else 'complete', 'missing': missing,
                          'reason': t('conclusion.withheld', missing=', '.join(t('conclusion.missing.' + k) for k in missing)) if missing else None}
    held = all(b['status'] == 'complete' for b in bases.values())
    out: Dict[str, Any] = {'id': rule.get('id', '?'), 'proposal_status': 'held' if held else 'withheld',
                           'suggest': rule.get('suggest') if held else t('tests.proposal_withheld', id=rule.get('id', '?')),
                           'why': rule.get('why') if held else t('tests.not_an_order'),
                           'priority': None, 'specialist': None,
                           'applicability': scope if isinstance(scope, dict) else None}
    for name in ('priority', 'specialist'):
        text = rule.get(name)
        if text and text != '—':
            bases[name] = _basis(rule, name, text)
            if held and bases[name]['status'] == 'complete':
                out[name] = text
    months = rule.get('recheck_months')
    if months is not None:
        timing = conclusion_basis(rule.get('recheck_basis'))
        valid = isinstance(months, int) and not isinstance(months, bool) and months > 0
        missing = list(timing['missing']) + ([] if valid else ['timing'])
        bases['recheck'] = {**timing, 'status': 'incomplete' if missing else 'complete', 'missing': missing,
                            'reason': t('conclusion.withheld', missing=', '.join(t('conclusion.missing.' + k) for k in missing)) if missing else None}
        if held and not missing:
            out['recheck_months'] = months
    out['proposal_basis'] = bases
    out['proposal_gaps'] = [{'claim': name, **basis} for name, basis in bases.items() if basis['status'] != 'complete']
    return out


def test_basis_text(row: Dict[str, Any]) -> str:
    """The same independent support accompanies standalone and aggregate text."""
    lines = []
    for name, basis in (row.get('proposal_basis') or {}).items():
        detail = (str(basis['source']) + ' · ' + str(basis['mechanism'])
                  if basis['status'] == 'complete' else basis['reason'])
        lines.append(t('tests.basis', claim=t('tests.claim.' + name), detail=detail))
    return '\n'.join(lines)
