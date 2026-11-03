/* Shared measurement presentation. No IO, clinical inference or source selection. */
(function(root){
  'use strict';
  function create(services){
    const {t,esc,fmtNum,fmtDate,targetSpec,flagOf,trendNote,badge,refText,targetText,ownerNoteHtml,systemLinkHtml,decisionNote,noteHtml,targetAsk,srcTag,comparisonHTML}=services;
    const FLAG=services.flags;
    const gline=(...args)=>services.line(...args);
    const CT=new Proxy({}, {get:(_target,key)=>services.colours()[key]});
// Normalize only presentation fields; medical facts remain in the supplied row.
function project(input, view){
  if(!['lab','metric','lifestyle'].includes(view))throw new Error('Unknown measurement view: '+view);
  const lab=view==='lab';
  return {label:view==='lifestyle'?input.label:input.name,
    value:lab?fmtNum(input.value):input.value==null?'—':input.value,
    qualifier:lab?(input.censored||''):'',unit:lab?(input.unit_display??input.unit):input.unit};
}
function valueHtml(model){
  return `<div class="value">${esc(model.qualifier)}${esc(model.value)} <small>${esc(model.unit)}</small></div>`;
}
function windowSeries(series){
  if(!series||series.length<=3) return series||[];
  const s=series.slice().sort((a,b)=>a.date<b.date?-1:(a.date>b.date?1:0));
  const latest=s[s.length-1].date;
  const cutoff=(parseInt(latest.slice(0,4),10)-3)+latest.slice(4);   // "2026-03" -> "2023-03"
  const within=s.filter(p=>p.date>=cutoff).length;
  return s.slice(-Math.max(3,within));
}

function measurementLabel(p){
  const src=p.measurement_source;
  if(!src)return '';
  return (src==='recorded'?t('web.phenotype.recorded'):t('web.life.device.'+src))+' · '+t(p.aggregation==='monthly_mean'?'web.life.monthly_mean':p.date?.length===7?'web.measurement.month_only':'web.life.dated_readings');
}

function measurementGroups(series){return [...new Set(series.map(p=>measurementLabel(p)))];}

function bodyMassMetric(ref){return ['weight','bmi'].includes(String(ref||'').split(':').at(-1).toLowerCase());}

function measurementDatasets(c,unified=false){
  if(unified)return [{...gline(c.points?.map(p=>p.value)||c.v,CT.series),spanGaps:false}];
  if(!c.points?.some(p=>p.measurement_source))return [gline(c.v,CT.series)];
  return measurementGroups(c.points).map((label,i)=>({...gline(c.points.map(p=>measurementLabel(p)===label?p.value:null),i===0?CT.series:CT.ink2),label,spanGaps:true,borderDash:i?[3,3]:[]}));
}

function sparkline(series,win,marks,unified=false){
  if(win!==false) series=windowSeries(series);
  if(!series||series.length<2) return '';
  // A reporting limit is not an exact point to connect on a trend line.
  if(series.some(p=>p.censored)) return '';
  const w=168,h=40,pad=5;
  const tg=marks&&marks.target;
  const ys=series.map(p=>p.value);
  // the scale stretches to the target so its line is on the chart, never to the
  // corridor — a wide reference range would flatten the series to a stroke
  const tv=tg?[tg.low,tg.high,tg.value].filter(v=>v!=null).map(Number):[];
  const mn=Math.min(...ys,...tv),mx=Math.max(...ys,...tv),rng=(mx-mn)||1;
  const groups=measurementGroups(series), annotated=series.some(p=>p.measurement_source);
  const stamps=series.map(p=>Date.parse(p.date.length===7?p.date+'-01':p.date));
  const X=i=>pad+(w-2*pad)*(annotated&&stamps.at(-1)>stamps[0]?(stamps[i]-stamps[0])/(stamps.at(-1)-stamps[0]):i/(series.length-1));
  const color=p=>groups.indexOf(measurementLabel(p))===0?'var(--accent)':'var(--ink-2)';
  const Y=v=>h-pad-(h-2*pad)*((v-mn)/rng);
  const clampY=v=>Math.max(pad,Math.min(h-pad,Y(v)));
  const lines=unified?`<polyline fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" points="${series.map((p,i)=>`${X(i).toFixed(1)},${Y(p.value).toFixed(1)}`).join(' ')}"/>`:groups.map((group,j)=>`<polyline fill="none" stroke="${j?'var(--ink-2)':'var(--accent)'}" stroke-width="2" ${j?'stroke-dasharray="3 3"':''} stroke-linejoin="round" stroke-linecap="round" points="${series.map((p,i)=>measurementLabel(p)===group?`${X(i).toFixed(1)},${Y(p.value).toFixed(1)}`:null).filter(Boolean).join(' ')}"/>`).join('');
  // points with the date on hover — the date each measurement was taken
  const dots=series.map((p,i)=>`<circle cx="${X(i).toFixed(1)}" cy="${Y(p.value).toFixed(1)}" r="${i===series.length-1?3.2:2.3}" fill="${unified?'var(--accent)':color(p)}"><title>${esc(fmtDate(p.date))}: ${esc(fmtNum(p.value))}${annotated?" · "+esc(measurementLabel(p)):""}</title></circle>`).join('');
  let bands='', legend='';
  if(tg){
    const lo=marks.ref_low!=null?clampY(Number(marks.ref_low)):h-pad, hi=marks.ref_high!=null?clampY(Number(marks.ref_high)):pad;
    if(marks.ref_low!=null||marks.ref_high!=null)
      bands+=`<rect x="${pad}" y="${hi.toFixed(1)}" width="${w-2*pad}" height="${Math.max(0,lo-hi).toFixed(1)}" fill="var(--muted)" opacity=".14"/>`;
    const dash=(v)=>`<line x1="${pad}" x2="${w-pad}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" stroke="var(--warning)" stroke-width="1.4" stroke-dasharray="4 3"/>`;
    if(tg.low!=null&&tg.high!=null)
      bands+=`<rect x="${pad}" y="${Y(Number(tg.high)).toFixed(1)}" width="${w-2*pad}" height="${Math.max(0,Y(Number(tg.low))-Y(Number(tg.high))).toFixed(1)}" fill="var(--warning)" opacity=".16"/>`;
    [tg.low,tg.high,tg.value].filter(v=>v!=null).forEach(v=>bands+=dash(Number(v)));
    legend=`<div class="sparkleg">${(marks.ref_low!=null||marks.ref_high!=null)?`<span class="lg-corr">▮ ${esc(t('web.target.lg_corridor'))}</span>`:''}<span class="lg-tg">╌ ${esc(t('web.target.lg_target'))} ${esc(targetSpec(tg))}</span></div>`;
  }
  const d0=series[0].date, dN=series[series.length-1].date;
  return `<div class="sparkwrap">
    <svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
      ${bands}
      ${lines}
      ${dots}
    </svg>
    <div class="sparkdates"><span>${esc(fmtDate(d0))}</span><span>${esc(fmtDate(dN))}</span></div>
    ${legend}${annotated&&!unified?`<div class="sparkleg">${groups.map((label,i)=>`<span>${i?"╌":"━"} ${esc(label)}</span>`).join("")}</div>`:""}
  </div>`;
}

function markerCard(m){
  const f = flagOf(m);
  const tr=trendNote(m);
  // Structured method and interval qualifications are product output. Legacy
  // free-text drafts remain in the source data, not in the current conclusion.
  const notes=[...(m.method_notes||[]),m.corridor_note].filter(Boolean).join(' · ');
  return (`<div class="cr-card card">
    <div class="label">${esc(m.name)}</div>
    ${valueHtml(project(m,'lab'))}
    <div class="row">${badge(f.cls,t(f.key))}${m.date?`<span class="muted small" title="${esc(m.date)}">${esc(fmtDate(m.date))}</span>`:''}${tr}</div>
    ${m.series&&m.series.length>1?sparkline(m.series,undefined,m.target?{ref_low:m.ref_low,ref_high:m.ref_high,target:m.target}:null):''}
    <div class="meta">${esc(refText(m))}${targetText(m)}${m.genome_link?` · ${ownerNoteHtml(m)}`:''}${m.system?` · ${systemLinkHtml(m.system)}`:''}</div>
    ${decisionNote(m,false)}
    ${m.display_recency===false?`<div class="meta">${esc(t('labs.historical'))}</div>`:m.display_recency===null?`<div class="meta">${esc(t('labs.date_unknown'))}</div>`:''}
    ${noteHtml(notes,'meta')}
    ${targetAsk(m)}
  </div>`);
}

function metricOrigin(m){
  if(!m.origin) return '';
  const dev = m.device&&t('web.life.device.'+m.device.source)||'';
  const head = m.origin==='device'
    ? t('web.metrics.from_device',{device:dev,date:m.device.date})
    : t('web.metrics.from_hand',{date:(m.manual&&m.manual.date)||m.date});
  const other = m.origin==='device'
    ? (m.manual?t('web.metrics.also_hand',{value:m.manual.value,date:m.manual.date}):'')
    : (m.device?t('web.metrics.also_device',{device:dev,value:m.device.value,date:m.device.date}):'');
  return `<div class="meta">${esc(head)}${other?' · '+esc(other):''}</div>`;
}

function metricCard(m){
  const f = FLAG[m.flag]||FLAG.unknown;
  const has = m.value!=null;
  let tr='';
  if(m.trend){const a={up:'↑',down:'↓',flat:'→'}[m.trend.direction];const pct=m.trend.pct!=null?` ${m.trend.pct>0?'+':''}${m.trend.pct}%`:'';tr=`<span class="trend">${a}${pct}</span>`;}
  return (`<div class="cr-card card">
    <div class="label">${esc(m.name)}</div>
    ${valueHtml(project(m,'metric'))}
    <div class="row">${has?badge(f.cls==='b-good'||f.cls==='b-critical'||f.cls==='b-warning'?f.cls:'b-good', t(f.key)):badge('b-unknown',t('web.flag.unknown'))}${tr}</div>
    ${m.series&&m.series.length>1?sparkline(m.series,undefined,null,bodyMassMetric(m.key)):''}
    <div class="meta">${esc(refText(m))}${has&&m.date?` · ${esc(m.date)}`:''}</div>
    ${metricOrigin(m)}
  </div>`);
}

function lifeCard(m){
  const ST={ok:{cls:'b-good',key:'web.life.ok'},warn:{cls:'b-warning',key:'web.life.warn'},
            bad:{cls:'b-critical',key:'web.life.bad'},none:{cls:'b-unknown',key:'web.life.none'}};
  const s=ST[m.status]||ST.none;
  let trendTxt=m.trend?'→ '+t('web.life.stable'):'', tcol='var(--muted)';
  if(m.trend&&m.trend.direction!=='flat'){
    const ar=m.trend.direction==='up'?'↑':'↓';const dl=m.trend.delta;
    trendTxt=m.measurement_kind?t('body.change',{delta:(dl>0?'+':'')+dl,unit:m.delta_unit||m.unit||'',start:fmtDate(m.trend.from),end:fmtDate(m.trend.to)}):`${ar} ${t('web.life.trend_3m',{delta:(dl>0?'+':'')+dl})}`;
    tcol=m.trend_good===true?'var(--good)':(m.trend_good===false?'var(--critical)':'var(--ink-2)');
  }
  const statusBadge=(m.status&&m.status!=='none')?badge(s.cls,m.status_text||t(s.key)):'';
  return (`<div class="cr-card card">
    <div class="label">${esc(m.label)}</div>
    ${m.composition_note?`<div class="cr-caption">${esc(m.composition_note)}</div>`:''}
    ${m.qualified_change_text?`<div class="cr-caption">${esc(m.qualified_change_text)}</div>`:''}
    ${valueHtml(project(m,'lifestyle'))}
    <div class="row">${statusBadge} <span class="trend" style="color:${tcol};font-weight:600">${esc(trendTxt)}</span></div>
    ${m.combined_history?sparkline(m.series,false,null,bodyMassMetric(m.key)):m.measurement_series?m.measurement_series.map(o=>`<div class="srcline">${esc(o.source?t('web.life.measured_by',{device:t('web.life.device.'+o.source)}):t('web.phenotype.recorded'))} · ${esc(o.aggregation==='monthly_mean'?t('web.life.monthly_mean'):t('web.life.dated_readings'))}</div>${o.series.length>1?sparkline(o.series,false):''}`).join(''):(m.series&&m.series.length>1?sparkline(m.series,false):'')}
    ${srcTag(m)}
    ${m.body_quality?.note?`<div class="cr-caption">${esc(m.body_quality.note)}</div>`:''}
    ${m.body_quality?.invalid_note?`<details class="fold"><summary>${esc(t('body.invalid_h'))}</summary><p>${esc(m.body_quality.invalid_note)}</p>${(m.body_invalid_values||[]).map(x=>`<p>${esc(x.date)}: ${esc(x.raw_value)} ${esc(x.raw_unit)}</p>`).join('')}</details>`:''}
    ${m.comparison?`<details class="fold"><summary>${esc(t('insight.details'))}</summary>${comparisonHTML(m.comparison)}${m.comparison.eligible&&m.comparison.distinguishable===true?'':`<p class="meta">${esc(t('insight.no_change_estimate'))}</p>`}${(m.comparison.limitations||[]).map(k=>`<p class="meta">${esc(t('insight.limit.'+k))}</p>`).join('')}</details>`:''}
    <div class="meta">${esc(m.value_smooth==null?fmtDate(m.date):t('web.life.card_meta',{date:fmtDate(m.date),smooth:m.value_smooth,since:fmtDate(m.first_date)}))}${m.why?' · '+esc(m.why):''}</div>
  </div>`);
}
  const source=c=>['lab','recorded','derived'].includes(c.source)?t('web.phenotype.'+c.source):t('web.life.device.'+c.source);
  const current=c=>c.value==null?'<span class="muted">—</span>':`${esc(fmtNum(c.value))} ${esc(c.unit_display??c.unit??'')}<div class="cr-caption">${esc(fmtDate(c.date)||'')} · ${esc(source(c))}</div>`;
  const annualSeries=c=>{if(bodyMassMetric(c.ref)){const series=c.period?.series||c.series||[];if(series.length>1){const first=series[0],last=series.at(-1),unit=c.unit_display??c.unit??'';return sparkline(series,false,null,true)+`<div class="cr-caption">${esc(fmtNum(first.value))} ${esc(unit)} · ${esc(fmtDate(first.date))} → ${esc(fmtNum(last.value))} ${esc(unit)} · ${esc(fmtDate(last.date))}</div>`;}}if(c.period){const p=c.period;return p.delta==null?`${p.series?.length>1?sparkline(p.series,false,null,bodyMassMetric(c.ref)):''}<span class="muted small">${esc(t(p.series?.length>1?'insight.comparison_unavailable':c.reading_status==='within'?'insight.latest_within':p.series?.length?'insight.one_reading':'insight.no_readings'))}</span>`:`${sparkline(p.series,false,null,bodyMassMetric(c.ref))}<div class="cr-caption">${esc(fmtDate(p.from))} → ${esc(fmtDate(p.to))} · ${p.delta>0?'+':''}${esc(fmtNum(p.delta))} ${esc(c.unit_display??c.unit??'')}${p.statistic==='mean'?' · '+esc(t('insight.stat.mean')):''}${p.comparison_source?' · '+esc(p.comparison_source==='recorded'?t('web.phenotype.recorded'):t('web.life.device.'+p.comparison_source)):''}</div>`;}return c.year_delta==null?`<span class="muted small">${esc(t(c.reading_status==='within'?'insight.latest_within':c.value!=null?'insight.one_reading':'insight.no_readings'))}</span>`
    :`${sparkline(c.series,false,null,bodyMassMetric(c.ref))}<div class="cr-caption">${esc(c.year_delta>0?'+':'')}${esc(fmtNum(c.year_delta))} ${esc(c.unit_display??c.unit??'')}</div>`;};
  const annual=c=>{const primary=annualSeries(c);return !bodyMassMetric(c.ref)&&c.device_history?`${primary}<details class="fold"><summary>${esc(t('web.phenotype.device_history',{source:source(c.device_history)}))}</summary>${annualSeries(c.device_history)}</details>`:primary;};

    const render=(input,view)=>{
      const renderer={lab:markerCard,metric:metricCard,lifestyle:lifeCard}[view];
      if(!renderer)throw new Error('Unknown measurement view: '+view);
      return renderer(input);
    };
    return Object.freeze({project,render,current,annual,windowSeries,label:measurementLabel,
      groups:measurementGroups,isBodyMass:bodyMassMetric,datasets:measurementDatasets,sparkline,origin:metricOrigin});
  }
  const api={create};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.ScholionMeasurements=api;
})(typeof globalThis!=='undefined'?globalThis:this);
