"""Source-bound clinical estimates; shared by overview, system, CLI and tools.

These methods have different endpoints and units. Missing answers never become
negative answers, and a formula result never supplies a diagnosis or treatment.
"""
from __future__ import annotations

from datetime import date

from . import core, store
from .i18n import t

def _base(key: str, source: str, version: str, unit: str = '') -> dict:
    return {'key': key, 'name': t('clinical.'+key+'.name'), 'value': None,
            'status': 'missing', 'unit': unit, 'date': None, 'inputs': [],
            'missing': [], 'issues': [], 'source': source, 'version': version,
            'endpoint': t('clinical.'+key+'.endpoint'), 'horizon': t('clinical.'+key+'.horizon'),
            'population': t('clinical.'+key+'.population'), 'interpretation': None}


def _recent(point: dict, today: date) -> bool:
    try:
        stamp = point.get('date') or ''
        return (store.date_resolution(stamp) in ('day', 'stamp')
                and 0 <= (today-date.fromisoformat(stamp[:10])).days <= 365)
    except (TypeError, ValueError):
        return False


@core.in_reading
def panel() -> dict:
    """No network, writes, genome preparation or implicit questionnaire answers."""
    from .engine.validated import fib4
    from . import phenoage
    today=date.today()
    f=fib4()
    fr=_base('fib4',f['sources'][0]['url'],'FIB-4, Sterling 2006')
    fr.update({k:f[k] for k in ('value','status','date','inputs','missing','issues','population','endpoint','horizon')})
    fr['issues'] = list(f['issues'])
    fr['interpretation']=f['interpretation']['reason']
    pa=phenoage.compute_panel('latest', track=False)
    pr=_base('phenoage','https://doi.org/10.18632/aging.101414','Levine 2018',t('clinical.years'))
    pr.update(status='computed' if pa.get('ok') else 'missing',
              value=pa.get('phenoage') if pa.get('ok') else None,
              date=pa.get('draw') or pa.get('panel'),inputs=pa.get('provenance',{}).get('inputs',[]),
              interpretation=t('clinical.phenoage.interpretation'))
    if pa.get('ok'):
        pr['inputs'] = [{'key':key, 'name':phenoage.marker_name(key), 'value':value,
                         'unit':phenoage.unit(key), 'date':pa['draw'],
                         'source':{'profile_marker':pa['labs_keys'][key], 'record':'labs.json'}}
                        for key,value in pa['values'].items()]
    else:
        pr['missing'] = pa.get('missing') or []
        pr['status'] = 'invalid' if pa.get('error') in ('implausible_units','compute_failed','draw_unknown') else 'missing'
        pr['issues']=[pa.get('message') or t('clinical.status.missing')]
    for row in (fr,pr):
        if row['status']=='computed' and not _recent(row,today):
            row.update(status='invalid',value=None)
            row['issues'].append(t('clinical.stale'))
    return {'status':'ok','key':'clinical_estimates','clinical_estimates':True,
            'label':t('clinical.title'),'as_of':today.isoformat(),
            'context':{},'context_fields':[],'context_errors':[],
            'context_note':t('clinical.context_note'),
            'estimates':[fr,pr],
            'policy':{'measurement_age_limit_days':365,'age_limit_kind':'Scholion display policy, not a recommendation to test'},
            'disclaimer':t('clinical.panel_limit')}
