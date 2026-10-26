"""CGM readings retain their original and approximate measurement kinds."""
from __future__ import annotations

from .i18n import t


def sleep_lines(data: dict) -> list[str]:
    out=[t('cgm.sleep'),data['message']]
    for row in data.get('intervals') or []:
        out.append(row['sleep_start']+' – '+row['sleep_end']+' · '+str(row['source']))
        out.append(t('cgm.duration')+': '+str(row['duration_hours']))
        if row['status']=='estimated':
            out.append(t('cgm.sleep_values')+': '+ ' / '.join(str(row[k]) for k in
                       ('mean_estimate','minimum_estimate','maximum_estimate','sd_estimate')))
        else:out.append(t('cgm.incomplete'))
        out.append(t('cgm.last_meal')+': '+str(row.get('last_recorded_meal_gap_hours',t('cgm.not_recorded'))))
        for key in ('score','deep_min','rem_min','light_min','awake_min','awake_count'):
            if key in row:out.append(t('cgm.sleep_score' if key=='score' else 'cgm.'+key)+': '+str(row[key]))
    if data.get('associations'):
        out.append(t('cgm.association_limit'))
    for item in data.get('associations') or []:
        out.append(str(item['source'])+' · '+t('cgm.'+item['x'])+' · '+t('cgm.association_rows',**{k:item[k] for k in ('included','excluded')}))
        out.append('r ≈'+str(item['r'])+' · '+t('cgm.sensitivity')+': '+str(item['leave_one_out_range'])
                   if item['status']=='exploratory' else t('cgm.descriptive'))
    for row in data.get('excluded') or []:
        out.append(t('cgm.excluded')+': '+str(row.get('date') or '')+' · '+t('cgm.reason.'+row['reason']))
    return out


def lines(data: dict) -> list[str]:
    if not data.get('available'):
        return [t('cgm.report_not_found')] if data.get('requested_report') else []
    r=data['current'];out=[data['label'],r['period']['start']+' – '+r['period']['end'],data['notice']]
    for key,value in r['summary'].items():
        out.append(t('cgm.'+key)+': '+str(value['value'])+' '+value['unit'])
    out.append(t('cgm.approximate'))
    for response in r['responses']:
        event=response['event'];label=event['date']+' '+event['local_time_as_printed']+' · '+t('cgm.'+event['type'])+' · '+event.get('label_as_printed','')
        if response['status']=='estimated':
            label+=' · ≈'+str(response['baseline_mean_estimate'])+' → '+str(response['peak_estimate'])+' mmol/L'
            label+=' · '+t('cgm.minimum')+': ≈'+str(response['minimum_estimate'])+' · '+t('cgm.end_value')+': ≈'+str(response['end_estimate'])
            label+=' · '+t('cgm.area')+': ≈'+str(response['area_above_baseline_estimate'])+' mmol*min/L'
            label+=' · '+t('cgm.return_baseline')+': '+t('cgm.return_yes' if response['return_toward_baseline_observed'] else 'cgm.return_no')
        else:label+=' · '+t('cgm.incomplete')
        out.append(label)
        if response['confounders']:out.append(t('cgm.overlap',events=', '.join(t('cgm.'+k) for k in response['confounders'])))
    out += sleep_lines(r['night_alignment'])+[r['source']['path'],r['source']['sha256'],r['format']]
    return out
