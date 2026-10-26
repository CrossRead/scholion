"""Readable clinical estimates from the same structures as the web interface."""
from __future__ import annotations

import json
from .i18n import t


def report(data: dict) -> str:
    lines=[data['label'],data['as_of'],data['context_note']]
    for row in data['estimates']:
        value='—' if row['value'] is None else str(row['value'])+' '+row['unit']
        lines += ['',row['name']+': '+value,t('clinical.status.'+row['status']),
                  str(row.get('date') or '—'),row['endpoint'],row['horizon'],row['population']]
        if row.get('interpretation'):
            lines.append(row['interpretation'])
        if row['missing']:
            lines.append(t('clinical.missing',fields=', '.join(t('clinical.field.'+k) for k in row['missing'])))
        lines += row['issues']
        for item in row['inputs']:
            lines.append(str(item.get('key') or '')+': '+str(item.get('value'))+' '+str(item.get('unit') or '')+
                         ' · '+str(item.get('date') or '—')+' · '+json.dumps(item.get('source') or item.get('record') or '—',ensure_ascii=False))
        lines += [row['source'],row['version']]
    lines.append(data['disclaimer'])
    return '\n'.join(lines)
