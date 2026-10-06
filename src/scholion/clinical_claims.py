"""Independent support for remaining catalogue-authored clinical sentences.

This does not guard observations, source classifications or human-entered
records: callers explicitly enumerate clinical fields. A neighbouring citation
never supplies a missing mechanism or validates a different effect or action.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

from .conclusion_basis import conclusion_basis
from .i18n import t


def guard_fields(spec: Dict[str, Any], row: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    """Suppress only named clinical fields; preserve values and each refusal."""
    out = dict(row)
    bases = {}
    declared = spec.get('claim_bases')
    declared = declared if isinstance(declared, dict) else {}
    for name in fields:
        if row.get(name) is None or row.get(name) == '' or row.get(name) == []:
            continue
        basis = conclusion_basis(spec.get(name + '_basis') or declared.get(name))
        bases[name] = basis
        if basis['status'] != 'complete':
            out[name] = [] if isinstance(row[name], list) else None
    out['clinical_basis'] = bases
    out['unresolved_count'] = sum(b['status'] != 'complete' for b in bases.values())
    return out


def basis_lines(row: Dict[str, Any], *, compact: bool = False) -> list[str]:
    bases = row.get('clinical_basis') or {}
    held = {name: b for name, b in bases.items() if b['status'] != 'complete'} if compact else {}
    lines = []
    if held:
        missing = dict.fromkeys(k for b in held.values() for k in b['missing'])
        lines.append(t('clinical.summary', fields=', '.join(held), missing=', '.join(
            t('conclusion.missing.' + k) for k in missing)))
    lines.extend(t('clinical.basis', field=name, detail=b['reason'] if b['status'] != 'complete'
                 else str(b['source']) + ' · ' + str(b['mechanism']))
                 for name, b in bases.items() if name not in held)
    return lines


def guard_dose_context(spec: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
    out = guard_fields(spec, row, ('nutritional_dose', 'pharmacologic_dose', 'forms', 'verdict_rule', 'alternatives', 'note'))
    out['items'] = [guard_fields(raw, item, ('claim', 'dose_dependent', 'effect_size', 'low_dose_note'))
                    for raw, item in zip(spec.get('critical') or [], row.get('items') or [])]
    out['unresolved_count'] += sum(i['unresolved_count'] for i in out['items'])
    if out.get('alternatives'):
        out['alternatives'] = [guard_fields(raw, item, ('name', 'melatonin', 'metabolic', 'caveat'))
                               for raw, item in zip(spec.get('alternatives') or [], out['alternatives'])]
        out['unresolved_count'] += sum(i['unresolved_count'] for i in out['alternatives'])
    return out
