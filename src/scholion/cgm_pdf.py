"""Read the verified Lumiflex application PDF without inventing sensor samples.

Printed statistics, dated user events and approximate vector-chart readings
remain separate. Unknown layouts, icons, time zones and coverage stay unknown.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
import hashlib
import io
import math
from pathlib import Path
import re
from typing import Callable

VERSION='lumiflex-app-pdf-v1'
PERIOD=re.compile(r'(?:Период\s+мониторинга|Monitoring\s+period)\s*:\s*(\d{4}/\d{2}/\d{2})\s*-\s*(\d{4}/\d{2}/\d{2})',re.I)
CLOCK=re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')
NUMBER=re.compile(r'^-?\d+(?:[.,]\d+)?$')
# Recognition digests of the report's generic event icons, not copied artwork.
ICONS={
 'b4fe079f165d0ee59c9d8da22c546f99b27cdf47f12e006fe342674273b835c9':'meal',
 'b0ef3aecaa3f51bcb9d21a518f4c8acf542f0dadf25f845919b3805df59a7c98':'activity',
}
METRICS=[
 ('sample_count','Количество контролируемых','count'),
 ('reported_mean_ambiguous','Среднее стандартное отклонение','mmol/L'),
 ('sd','Стандартное отклонение','mmol/L'),('cv','GV (CV%)','%'),
 ('maximum','Максимальный уровень глюкозы','mmol/L'),('minimum','Минимальный уровень глюкозы','mmol/L'),
 ('lage','Максимальная амплитуда','mmol/L'),('mage','Средняя амплитуда','mmol/L'),
 ('fraction_ge_13_9','% значения глюкозы ≥13.9','%'),('fraction_ge_10','% значения глюкозы ≥10.0','%'),
 ('fraction_ge_7_8','% значения глюкозы ≥7.8','%'),('fraction_le_3_9','% значения глюкозы ≤3.9','%'),
 ('fraction_le_2_8','% значения глюкозы ≤2.8','%'),('fraction_reported_3_9_to_10','% значения глюкозы между 3.9','%'),
]


def recognizes(text: str) -> bool:
    return bool(PERIOD.search(text) and 'непрерывного мониторинга глюкозы' in text.casefold()
                and ('GV (CV%)' in text or 'GV(CV%)' in text))


def _lines(words: list[dict]) -> list[list[dict]]:
    rows: list[list[dict]]=[]
    for word in sorted(words,key=lambda w:(w['top'],w['x0'])):
        if not rows or abs(word['top']-rows[-1][0]['top'])>2:
            rows.append([word])
        else:
            rows[-1].append(word)
    return [sorted(row,key=lambda w:w['x0']) for row in rows]


def _number(text: str) -> float:
    value=float(text.replace(',','.'))
    if not math.isfinite(value):raise ValueError('non-finite printed statistic')
    return value


def daily_table(words: list[dict], start: date, end: date, page: int) -> list[dict]:
    rows=_lines(words)
    header=next((r for r in rows if any(w['text']=='Позиция' for w in r)
                 and sum(bool(re.fullmatch(r'\d{2}/\d{2}',w['text'])) for w in r)>=1),None)
    if not header:return []
    columns=[w for w in header if re.fullmatch(r'\d{2}/\d{2}',w['text'])]
    days=[start+timedelta(days=i) for i in range((end-start).days+1)]
    if [w['text'] for w in columns]!=[d.strftime('%m/%d') for d in days]:
        raise ValueError('daily columns do not match the recorded period')
    centres=[(w['x0']+w['x1'])/2 for w in columns]
    left_edge=centres[0]-(centres[1]-centres[0])/2 if len(centres)>1 else columns[0]['x0']-5
    labels=[]
    for row in rows:
        if row[0]['top'] <= header[0]['top']:
            continue
        label=' '.join(w['text'] for w in row if w['x1']<left_edge)
        for key,fragment,unit in METRICS:
            if label.startswith(fragment):labels.append((row[0]['top'],key,unit,label))
    if len({key for _,key,_,_ in labels})!=len(labels):raise ValueError('ambiguous daily statistic labels')
    if {key for _,key,_,_ in labels}!={key for key,_,_ in METRICS}:
        raise ValueError('daily statistic labels are incomplete or unsupported')
    labels.sort()
    output: list[dict]=[{'date':d.isoformat(),'source_page':page,'statistics':{}} for d in days]
    for n,(top,key,unit,label) in enumerate(labels):
        bottom=labels[n+1][0]-1 if n+1<len(labels) else top+45
        cells: list[list[float]]=[[] for _ in days]
        for w in words:
            if top-1<=w['top']<bottom and w['x0']>=left_edge and NUMBER.fullmatch(w['text']):
                x=(w['x0']+w['x1'])/2;column=min(range(len(centres)),key=lambda i:abs(x-centres[i]))
                if len(centres)>1 and abs(x-centres[column])>(centres[1]-centres[0])*.45:continue
                cells[column].append(_number(w['text']))
        for out,values in zip(output,cells):
            if len(values)>1:raise ValueError('multiple values in a daily statistic cell')
            out['statistics'][key]={'value':values[0] if values else None,'unit':unit,
                'label_as_printed':label,'kind':'printed_statistic','definition_status':'ambiguous' if key=='reported_mean_ambiguous' else 'as_printed'}
    return output


def _simplify(points: list[tuple[float,float]], tolerance: float=.15) -> list[tuple[float,float]]:
    """Bound vertical approximation error; never resample into a minute series."""
    if len(points)<3:return points
    kept={0,len(points)-1};stack=[(0,len(points)-1)]
    while stack:
        a,b=stack.pop();x0,y0=points[a];x1,y1=points[b]
        if b-a<2:continue
        errors=[(abs(y-(y0+(y1-y0)*(x-x0)/(x1-x0))) if x1!=x0 else abs(y-y0),i)
                for i,(x,y) in enumerate(points[a+1:b],a+1)]
        error,i=max(errors)
        if error>tolerance:kept.add(i);stack.extend([(a,i),(i,b)])
    return [points[i] for i in sorted(kept)]


def _cubic_points(a: tuple, b: tuple, c: tuple, d: tuple, tolerance: float) -> list[tuple]:
    """Adaptive De Casteljau subdivision of the actual drawn Bezier curve."""
    output=[];stack=[(a,b,c,d,0)]
    def mid(x,y):return ((x[0]+y[0])/2,(x[1]+y[1])/2)
    while stack:
        p0,p1,p2,p3,depth=stack.pop()
        dx,dy=p3[0]-p0[0],p3[1]-p0[1]
        error=max(abs(p[1]-(p0[1]+dy*(p[0]-p0[0])/dx)) if abs(dx)>1e-9 else math.dist(p,p0) for p in (p1,p2))
        if error<=tolerance or depth>=12:
            output.append(p3);continue
        ab,bc,cd=mid(p0,p1),mid(p1,p2),mid(p2,p3)
        abc,bcd=mid(ab,bc),mid(bc,cd);centre=mid(abc,bcd)
        stack.append((centre,bcd,cd,p3,depth+1));stack.append((p0,ab,abc,centre,depth+1))
    return output


def charts(words: list[dict], curves: list[dict], images: list[dict], page: int) -> list[dict]:
    result=[]
    axis_rows=[r for r in _lines(words) if sum(w['text']=='00:00' for w in r)==2]
    for axis in axis_rows:
        clocks=[w for w in axis if CLOCK.fullmatch(w['text'])]
        if [w['text'] for w in clocks]!=[f'{h:02d}:00' for h in range(0,24,2)]+['00:00']:continue
        left=(clocks[0]['x0']+clocks[0]['x1'])/2;right=(clocks[-1]['x0']+clocks[-1]['x1'])/2
        top=axis[0]['top']
        grid=[c for c in curves if c.get('fill') and not c.get('stroke')
              and c.get('stroking_color') in ([.8667,.8667,.8667],(.8667,.8667,.8667))
              and c['width']<4 and 0<c['height']<1 and left-1<=c['x0']<=right+1 and top-110<c['top']<top]
        counts=Counter(round((c['top']+c['bottom'])/2,2) for c in grid)
        grid_y=sorted(y for y,count in counts.items() if count>=20)
        labels=[w for w in words if w['x0']>right and w['text'] in ('0','5','10','15','20','25') and top-110<w['top']<top]
        matched={}
        for w in labels:
            if not grid_y:continue
            centre=(w['top']+w['bottom'])/2;y=min(grid_y,key=lambda g:abs(g-centre))
            if abs(y-centre)<5:matched[int(w['text'])]=y
        if set(matched)!={0,5,10,15,20,25} or len(set(matched.values()))!=6:continue
        y0,y25=matched[0],matched[25]
        if y0<=y25 or any(abs(y-(y0-(y0-y25)*v/25))>.2 for v,y in matched.items()):continue
        day_labels=[w for w in words if w['x1']<left-5 and w['x0']>left-35 and w['text'].isdigit()
                    and y25<=w['top']<=y0 and 1<=int(w['text'])<=31]
        if len(day_labels)!=1:continue
        segments=[]
        for c in curves:
            if not c.get('stroke') or c.get('fill') or len(c.get('pts') or [])<3:continue
            points=c['pts']
            if not all(left-.5<=x<=right+.5 and y25-.5<=y<=y0+.5 for x,y in points):continue
            # Multiple move-to instructions are explicit gaps, not one joined line.
            paths=c.get('path') or []
            groups=[];current: list[tuple[float,float]]=[]
            for command in paths:
                kind=command[0]
                if kind=='m':
                    if current:groups.append(current)
                    current=[command[1]]
                elif kind=='l' and current:current.append(command[1])
                elif kind in ('c','v','y') and current:
                    controls = (command[1],command[2],command[3]) if kind=='c' else (current[-1],command[1],command[2]) if kind=='v' else (command[1],command[2],command[2])
                    current.extend(_cubic_points(current[-1],controls[0],controls[1],controls[2],(y0-y25)*.05/25))
                else:
                    current=[];groups=[];break
            if current:groups.append(current)
            if not paths:groups=[points]
            for group in groups:
                if len(group)<2 or any(group[i+1][0]<group[i][0] for i in range(len(group)-1)):continue
                projected=[((x-left)*1440/(right-left),(y0-y)*25/(y0-y25)) for x,y in group]
                segments.append([[round(x,2),round(y,2)] for x,y in _simplify(projected)])
        events=[]
        event_words=[w for w in words if CLOCK.fullmatch(w['text']) and top+8<w['top']<top+38]
        for time_word in event_words:
            neighbours=[w for w in event_words if abs(w['top']-time_word['top'])<3 and w['x0']>time_word['x0']]
            limit=min((w['x0']-12 for w in neighbours),default=right+20)
            label=' '.join(w['text'] for w in sorted(words,key=lambda w:w['x0']) if abs(w['top']-time_word['top'])<3 and w['x0']>time_word['x1']+1 and w['x1']<limit)
            icon=next((i for i in images if abs(i['top']-time_word['top'])<5 and 0<time_word['x0']-i['x1']<8),None)
            kind=ICONS.get(str((icon or {}).get('digest') or ''),'unknown')
            events.append({'local_time_as_printed':time_word['text'],'timezone':None,'type':kind,
                'type_evidence':'recognized_report_icon' if kind!='unknown' else 'icon_not_recognized',
                'label_as_printed':label,'description_truncated':bool(re.search(r'…|\.\.\.',label)),
                'source_page':page,'kind':'user_event','quantity':None,'duration':None})
        result.append({'day_as_printed':int(day_labels[0]['text']),'source_page':page,
            'axis':{'x0':left,'x24':right,'y0':y0,'y25':y25,'unit':'mmol/L','method':'six_numeric_labels_matched_to_vector_grid'},
            'segments':segments,'events':events,'kind':'approximate_chart_reading',
            'representation_error_bound_mmol_L':.25,'time_reading_uncertainty_minutes':2,'sampling':'simplified_visible_vector_polyline_not_sensor_observations'})
    return result


def extract(path: Path, checkpoint: Callable[[],None] | None=None) -> dict:
    import pdfplumber
    raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        if len(pdf.pages)>32:raise ValueError("unsupported CGM PDF page count")
        pages: list[dict]=[]
        for n,pdf_page in enumerate(pdf.pages,1):
            if checkpoint:checkpoint()
            pages.append({'text':pdf_page.extract_text() or '', 'words':pdf_page.extract_words(), 'curves':pdf_page.curves,
                'images':[{'top':i['top'],'x0':i['x0'],'x1':i['x1'],'digest':hashlib.sha256(i['stream'].get_data()).hexdigest()} for i in pdf_page.images], 'number':n})
    text='\n'.join(p['text'] for p in pages)
    if not recognizes(text):raise ValueError('unsupported CGM PDF layout')
    period=PERIOD.search(text);assert period is not None
    start,end=(date.fromisoformat(v.replace('/','-')) for v in period.groups())
    if end<start or (end-start).days>92:raise ValueError('invalid CGM reporting period')
    summary={}
    for key,pattern,unit in [('mean',r'\bMBG\s+ммоль/л\s+([\d.,]+)','mmol/L'),('gmi',r'\bGMI\s+%\s+([\d.,]+)','%'),('cv',r'GV\s*\(CV%\)\s+%\s+([\d.,]+)','%'),('reported_coverage',r'непрерывного\s+%\s+([\d.,]+)','%')]:
        m=re.search(pattern,pages[0]['text'])
        if m:summary[key]={'value':_number(m[1]),'unit':unit,'kind':'printed_statistic','source_page':1}
    tir=re.search(r'ННооррммааллььнныыйй,,\s*([\d.,]+)%%',pages[0]['text'])
    if tir:
        value=tir[1]
        if len(value)%2==0 and all(value[i]==value[i+1] for i in range(0,len(value),2)):
            summary['tir']={'value':_number(value[::2]),'unit':'%','kind':'printed_statistic','source_page':1,'range_as_printed':'3.9-10.0 mmol/L','boundary_precision':'printed_label'}
    daily=[];plots=[]
    for p in pages:
        daily.extend(daily_table(p['words'],start,end,p['number']))
        if 'Суточная кривая глюкозы' in p['text'] or p['number'] in (3,4):plots.extend(charts(p['words'],p['curves'],p['images'],p['number']))
    if len(daily)!=(end-start).days+1:raise ValueError('daily CGM table is incomplete or unsupported')
    coverage_ok=len(plots)==len(daily) and all(plot['day_as_printed']==date.fromisoformat(day['date']).day for plot,day in zip(plots,daily))
    events: list[dict]=[]
    if coverage_ok:
        for plot,day in zip(plots,daily):
            plot['date']=day['date'];events.extend({**e,'date':day['date']} for e in plot.pop('events'))
    else:
        plots=[]
    for row in daily:
        count=(row['statistics'].get('sample_count') or {}).get('value')
        row['coverage']={'reported_samples':count,'complete_1440_sample_day':count==1440,'timezone':None}
    serial=re.search(r'Серийный номер:\s*(\S+)',text)
    sensor_digest=hashlib.sha256(serial[1].encode()).hexdigest() if serial else 'unknown'
    return {'format':VERSION,'period':{'start':start.isoformat(),'end':end.isoformat()},
        'source':{'path':str(path.resolve()),'sha256':digest,'pages':len(pages)},
        'sensor_identity':sensor_digest,'summary':summary,'daily':daily,'events':events,
        'chart_segments':plots,'timezone':None,
        'quality':{'exact_sensor_series':False,'graphical_reading':('available' if all(p['segments'] for p in plots) else 'partial_curves') if coverage_ok else 'unsupported_axes_or_date_order',
                   'daily_mean_definition':'ambiguous_printed_label','gmi_is_lab_hba1c':False,
                   'threshold_boundaries':'retained_per_printed_definition','causation_established':False}}
