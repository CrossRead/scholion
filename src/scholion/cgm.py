"""One versioned CGM report layer over studies, not a laboratory glucose series."""
from __future__ import annotations

from datetime import date,datetime,timezone
import math

from typing import Any

from . import core
from .i18n import t


def merge(by_id: dict, report: dict, filename: str) -> tuple[str,str]:
    """Stage a source revision; no write until the surrounding import commits."""
    for sid,existing in by_id.items():
        for version in (existing.get('cgm') or {}).get('versions') or []:
            if version['source']['sha256'] != report['source']['sha256']:
                continue
            source=version['source'];aliases=source.get('aliases') or []
            path=report['source']['path']
            if path != source['path'] and path not in aliases:
                aliases.append(path)
                source['aliases']=aliases
                return sid,'updated'
            return sid,'unchanged'
    identity=report['sensor_identity']
    if identity=='unknown':identity=report['source']['sha256']
    sid='cgm-'+identity[:12]+'-'+report['period']['start']+'-'+report['period']['end']
    old=by_id.get(sid) or {}
    versions=list((old.get('cgm') or {}).get('versions') or [])
    versions.append({**report,'imported_at':datetime.now(timezone.utc).isoformat()})
    by_id[sid]={**old,'id':sid,'kind':'cgm','date':report['period']['end'],'source':filename,
                'source_path':report['source']['path'],'conclusion':'',
                'cgm':{'current_version':report['source']['sha256'],'versions':versions}}
    return sid,'updated' if old else 'added'


def _absolute(day: str, minute: float) -> float:
    return date.fromisoformat(day).toordinal()*1440+minute


def _segments(report: dict) -> list[list[list[float]]]:
    pieces=sorted([[[ _absolute(plot['date'],x), y] for x,y in segment]
            for plot in report.get('chart_segments') or [] for segment in plot['segments'] if len(segment)>=2],key=lambda s:s[0][0])
    out: list[list[list[float]]]=[]
    for piece in pieces:
        if out and abs(out[-1][-1][0]-piece[0][0])<1e-7 and abs(out[-1][-1][1]-piece[0][1])<=.5:
            out[-1].extend(piece)
        else:out.append(piece)
    return out


def _window(segments: list, start: float, end: float) -> list[list[float]] | None:
    """Require continuous visible support; never bridge a sensor/chart gap."""
    for points in segments:
        if points[0][0]>start or points[-1][0]<end:continue
        result=[]
        for edge in (start,end):
            for a,b in zip(points,points[1:]):
                if a[0]<=edge<=b[0] and b[0]>a[0]:
                    result.append([edge,a[1]+(b[1]-a[1])*(edge-a[0])/(b[0]-a[0])]);break
        if len(result)!=2:return None
        return [result[0]]+[p for p in points if start<p[0]<end]+[result[-1]]
    return None


def responses(report: dict) -> list[dict]:
    """Within-report wall-clock alignment only; every numeric result approximate."""
    segments=_segments(report);events=report.get('events') or [];out=[]
    for event in events:
        if event['type'] not in ('meal','activity'):continue
        h,m=map(int,event['local_time_as_printed'].split(':'));stamp=_absolute(event['date'],h*60+m)
        base=_window(segments,stamp-30,stamp);after=_window(segments,stamp,stamp+120)
        confounders=[e['type'] for e in events if e is not event and e['type'] in ('meal','activity')
                     and stamp-30<=_absolute(e['date'],int(e['local_time_as_printed'][:2])*60+int(e['local_time_as_printed'][3:]))<=stamp+120]
        r={'event':event,'status':'incomplete_chart_window','kind':'approximate_chart_response',
           'window_minutes':{'baseline':[-30,0],'response':[0,120]},'confounders':sorted(set(confounders)),
           'timezone':report.get('timezone'),'time_basis':'same_report_local_wall_clock',
           'limitation':t('cgm.approximate'),'causation_established':False}
        if base and after:
            baseline=sum((b[0]-a[0])*(a[1]+b[1])/2 for a,b in zip(base,base[1:]))/30
            peak=max(after,key=lambda p:p[1])
            # Integrate the positive part of each linear segment exactly,
            # including a crossing of the baseline between its endpoints.
            area=0.0
            for a,b in zip(after,after[1:]):
                ya,yb=a[1]-baseline,b[1]-baseline;span=b[0]-a[0]
                if min(ya,yb)>=0:area+=span*(ya+yb)/2
                elif max(ya,yb)>0:area+=span*max(ya,yb)**2/(2*abs(yb-ya))
            r.update(status='estimated',baseline_mean_estimate=round(baseline,1),peak_estimate=round(peak[1],1),
                peak_delta_estimate=round(peak[1]-baseline,1),time_to_peak_minutes_estimate=round((peak[0]-stamp)/5)*5,
                minimum_estimate=round(min(p[1] for p in after),1),end_estimate=round(after[-1][1],1),
                end_delta_estimate=round(after[-1][1]-baseline,1),
                area_above_baseline_estimate=round(area,1),unit='mmol/L',area_unit='mmol*min/L',
                return_toward_baseline_observed=abs(after[-1][1]-baseline)<=.25)
        out.append(r)
    return out


def _sleep_points() -> list[dict]:
    """Read existing per-night files and the common recorded metric, by source."""
    points=list(core.metrics_json().get('metrics',{}).get('sleep',{}).get('series') or [])
    for name in ('sleep_nightly.json','sleep_nightly.whoop.json'):
        path=core.profile_dir()/name
        if path.is_file():
            block=core.read_profile_json(path)
            points.extend({**p,'source':p.get('source') or block.get('_meta',{}).get('source'),
                           'source_record':name} for p in block.get('nights') or [])
    return points


def _curve_stats(window: list) -> dict:
    span=window[-1][0]-window[0][0]
    mean=sum((b[0]-a[0])*(a[1]+b[1])/2 for a,b in zip(window,window[1:]))/span
    second=sum((b[0]-a[0])*(a[1]**2+a[1]*b[1]+b[1]**2)/3 for a,b in zip(window,window[1:]))/span
    return {'mean_estimate':round(mean,1),'minimum_estimate':round(min(p[1] for p in window),1),
            'maximum_estimate':round(max(p[1] for p in window),1),
            'sd_estimate':round(math.sqrt(max(0,second-mean**2)),1)}


def _night_associations(rows: list[dict]) -> list[dict]:
    """Exploratory within-device descriptions; no independence or causal claim."""
    out=[]
    for source in sorted({r['source'] for r in rows}):
        group=[r for r in rows if r['source']==source and r['status']=='estimated'
               and r.get('sleep_kind')=='main_sleep']
        for key in ('duration_hours','last_recorded_meal_gap_hours','score'):
            pairs=[(r[key],r['mean_estimate']) for r in group if isinstance(r.get(key),(float,int))
                   and math.isfinite(r[key]) and math.isfinite(r['mean_estimate'])]
            item={'source':source,'x':key,'y':'mean_estimate','included':len(pairs),
                  'excluded':len([r for r in rows if r['source']==source])-len(pairs),
                  'status':'descriptive','causation_established':False,'minimum_pairs':8,
                  'method':'Pearson r; leave-one-night-out sensitivity; exploratory minimum8, not a clinical threshold'}
            def correlation(values: list) -> float | None:
                mx=sum(x for x,y in values)/len(values);my=sum(y for x,y in values)/len(values)
                den=math.sqrt(sum((x-mx)**2 for x,y in values)*sum((y-my)**2 for x,y in values))
                return sum((x-mx)*(y-my) for x,y in values)/den if den else None
            if len(pairs)>=8:
                value=correlation(pairs)
                if value is not None:
                    sensitivity=[correlation(pairs[:n]+pairs[n+1:]) for n in range(len(pairs))]
                    supported=[v for v in sensitivity if v is not None]
                    item.update(status='exploratory',r=round(value,2),
                                leave_one_out_range=[round(min(supported),2),round(max(supported),2)] if supported else None)
            out.append(item)
    return out


def _night_alignment(report: dict) -> dict:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    zone=report.get('timezone');points=_sleep_points();results=[];excluded=[];seen=set()
    if not zone:
        return {'status':'not_established','reason':'timezone_unknown','message':t('cgm.sleep_unknown'),
                'daily_extrema_used_as_night':False,'intervals':[],'excluded':[], 'associations':[]}
    try:tz=ZoneInfo(zone)
    except (ValueError,ZoneInfoNotFoundError):
        return {'status':'not_established','reason':'timezone_unavailable','message':t('cgm.timezone_invalid'),
                'daily_extrema_used_as_night':False,'intervals':[],'excluded':[],'associations':[]}
    segments=_segments(report)
    for point in points:
        recorded_day=str(point.get('date') or '')[:10]
        if recorded_day:
            try:
                day=date.fromisoformat(recorded_day).toordinal()
                if day+1<date.fromisoformat(report['period']['start']).toordinal() or recorded_day>report['period']['end']:continue
            except ValueError:pass
        source=point.get('source');a,b=point.get('started_at'),point.get('ended_at')
        reason=None
        try:
            begin=datetime.fromisoformat(str(a).replace('Z','+00:00'));end=datetime.fromisoformat(str(b).replace('Z','+00:00'))
            if not begin.tzinfo or not end.tzinfo or end<=begin or not source:reason='interval_or_source_unverified'
        except (TypeError,ValueError,AttributeError):reason='interval_or_source_unverified'
        if reason:
            excluded.append({'date':point.get('date'),'source':source,'reason':reason});continue
        local_a,local_b=begin.astimezone(tz),end.astimezone(tz)
        if local_b.date().isoformat()<report['period']['start'] or local_a.date().isoformat()>report['period']['end']:continue
        identity=(source,begin.astimezone(timezone.utc).isoformat(),end.astimezone(timezone.utc).isoformat())
        if identity in seen:continue
        seen.add(identity)
        if local_a.utcoffset()!=local_b.utcoffset():
            excluded.append({'date':local_a.date().isoformat(),'source':source,'reason':'dst_transition'});continue
        if point.get('is_nap') or point.get('sleep_kind')=='nap':
            excluded.append({'date':local_a.date().isoformat(),'source':source,'reason':'nap_not_night'});continue
        start=_absolute(local_a.date().isoformat(),local_a.hour*60+local_a.minute+local_a.second/60)
        finish=_absolute(local_b.date().isoformat(),local_b.hour*60+local_b.minute+local_b.second/60)
        if finish<=start:continue
        window=_window(segments,start,finish)
        row={'sleep_start':begin.isoformat(),'sleep_end':end.isoformat(),'source':source,
             'report_local_start':local_a.isoformat(),'report_local_end':local_b.isoformat(),
             'source_record':point.get('source_record'),'sleep_kind':point.get('sleep_kind','recorded_sleep'),
             'status':'estimated' if window else 'incomplete_chart_window',
             'duration_hours':round((end-begin).total_seconds()/3600,2),
             'minimum_estimate':None,'kind':'approximate_chart_sleep_alignment','causation_established':False}
        for key in ('score','awake_count','awake_min','deep_min','rem_min','light_min','total_min','respiration','hrv','resting_heart_rate'):
            if point.get(key) is not None:row[key]=point[key]
        for old,new in (('SleepPerformance','score'),('DeepSleepMin','deep_min'),('RemSleepMin','rem_min'),('LightSleepMin','light_min'),('AwakeMin','awake_min')):
            if old in point and new not in row:row[new]=point[old]
        if window:
            row.update(_curve_stats(window),curve=[[round(p[0]-start,2),p[1]] for p in window])
        before=[];during=[]
        for event in report.get('events') or []:
            if event['type'] not in ('meal','activity'):continue
            h,m=map(int,event['local_time_as_printed'].split(':'));stamp=_absolute(event['date'],h*60+m)
            if event['type']=='meal' and start-1440<=stamp<=start:before.append((stamp,event))
            if start<=stamp<=finish:during.append({**event,'minutes_from_sleep_start':round(stamp-start,2)})
        if before:
            stamp,event=max(before,key=lambda p:p[0]);row.update(last_recorded_meal=event,
                last_recorded_meal_gap_hours=round((start-stamp)/60,2))
        row['events_during_sleep']=during
        results.append(row)
    reason=None if results else 'sleep_intervals_not_recorded' if not seen else 'no_supported_intervals'
    return {'status':'estimated' if any(r['status']=='estimated' for r in results) else 'incomplete_chart_window' if results else 'not_established',
            'reason':reason,'message':t('cgm.sleep_context') if results else t('cgm.sleep_unknown'),'daily_extrema_used_as_night':False,
            'intervals':results,'excluded':excluded,'associations':_night_associations(results),
            'sleep_period_rule':'Explicit sourced interval; only marked main_sleep contributes to night associations',
            'last_meal_rule':'Last recorded meal within24h; absence is not fasting',
            'association_uncertainty':'Leave-one-night-out range is sensitivity, not a confidence interval; no independent-night assumption'}


def laboratory_context(report: dict | None, markers: dict) -> dict | None:
    """Only a dated overlap with an existing glucose-system observation.

    Sensor mean and GMI are different measurements from fasting glucose and
    laboratory HbA1c. Coexistence never becomes agreement, conflict or causation.
    """
    if not report or not report.get('summary',{}).get('mean'):
        return None
    period=report['period']
    matched=[m for key,m in markers.items() if key in ('glucose','hba1c') and m.get('date')
             and period['start'] <= m['date'][:10] <= period['end'] and m.get('value') is not None]
    if not matched:return None
    mean=report['summary']['mean']
    return {'record':'studies.json','key':'cgm_report','date':period['end'],
            'value':mean['value'],'unit':mean['unit'],'source':report['source']['path'],
            'source_record':{'path':report['source']['path'],'source_sha256':report['source']['sha256'],
                             'format':report['format']},'method':'printed_sensor_summary',
            'matched_laboratory_keys':[m['key'] for m in matched],
            'causation_established':False,'individual_variant_effect_established':False,
            'message':t('cgm.laboratory_context',start=period['start'],end=period['end'],
                        mean=mean['value'],unit=mean['unit'])}


@core.in_reading
def summary(report_sha: str = '') -> dict[str,Any]:
    reports: list[dict]=[];versions: list[dict]=[]
    for item in core.studies().get('studies') or []:
        block=item.get('cgm') or {}
        selected=next((v for v in block.get('versions') or [] if v['source']['sha256']==block.get('current_version')),None)
        if selected:
            reports.append({**selected,'id':item['id'],'versions_count':len(block['versions'])})
        versions.extend({**v,'id':item['id'],'versions_count':len(block['versions']),
                         'is_current_revision':v['source']['sha256']==block.get('current_version')}
                        for v in block.get('versions') or [])
    reports.sort(key=lambda r:(r['period']['end'],r['period']['start'],r.get('imported_at') or ''))
    current=next((v for v in versions if v['source']['sha256']==report_sha),None) if report_sha else reports[-1] if reports else None
    if current:
        zones=(core.metrics_json().get('profile') or {}).get('cgm_timezones') or {}
        current={**current,'timezone':zones.get(current['source']['sha256']),
                 'timezone_source':'explicit_user_report_context' if zones.get(current['source']['sha256']) else None}
        current={**current,'responses':responses(current),'night_alignment':_night_alignment(current)}
    return {'available':bool(current),'label':t('cgm.title'),'current':current,
            'requested_report':report_sha or None,'selection_found':bool(current) if report_sha else None,
            'reports':[{'id':r['id'],'period':r['period'],'source':r['source'],'versions_count':r['versions_count']} for r in reports],
            'versions':[{'id':v['id'],'period':v['period'],'source':v['source'],
                         'is_current_revision':v['is_current_revision'],'imported_at':v.get('imported_at')}
                        for v in sorted(versions,key=lambda v:(v['period']['end'],v.get('imported_at') or ''),reverse=True)],
            'notice':t('cgm.notice'),'history_preserved':True,'laboratory_series_created':False}
