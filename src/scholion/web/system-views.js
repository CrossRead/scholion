/* Shared system, insight and prescription presentation. No IO or clinical inference. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.ScholionSystemViews=api;
})(typeof globalThis==='undefined'?this:globalThis,function(){
'use strict';
function create(services){
  const {t,esc,fmtNum,fmtDate,measurementLabel,levelChip,geneticComparisonHTML,genSummaryHtml,geneticCatalogueFold,panelLabsHtml,fib4Html,badge,sparkline,bodyMassMetric,genTableHtml,systemPolygenicHtml,thematicPanelLinks,correctionRoutesHtml,visibleTestProposals,testItem,basketRowHtml,systemLinkHtml,noteHtml,visitReportGenes}=services;
  const FLAG=services.flags;
function insightFactHTML(f){
  const target=f.target, bounds=target?(target.value!=null?target.value:(target.low??'—')+'–'+(target.high??'—')):null;
  const value=target?esc(t('insight.target',{value:bounds,unit:target.unit||''})):f.percentile!=null?esc(t('insight.pgs',{model:f.pgs_id,value:f.percentile,population:f.reference_panel_ancestry})):f.genotype?esc((f.gene||'')+' '+(f.rsid||'')+': '+f.genotype):f.value==null?'':`${esc(f.censored||'')}${esc(String(f.value))} ${esc(f.unit_display||f.unit||'')}`;
  const source=typeof f.source==='string'?f.source:(f.source?.path||f.record||'');
  return `<li><time>${esc(f.date||'—')}</time> ${value}<span class="meta"> · ${esc(source)}</span>${f.ref_low!=null||f.ref_high!=null?`<span class="meta"> · ${esc(t('insight.reference',{low:f.ref_low??'—',high:f.ref_high??'—'}))}</span>`:''}</li>`;
}

function comparisonHTML(c){
  if(!c)return '';
  const lines=[];
  if(['mean','median'].includes(c.statistic))lines.push(t('insight.stat.'+c.statistic));
  if(c.delta!=null)lines.push(t('insight.delta')+': '+c.delta);
  if(c.mdd!=null)lines.push(t('insight.mdd',{value:c.mdd}));
  for(const key of ['before','after']){const p=c[key],s=p?.stats;if(s)lines.push(t('insight.coverage',{date:p.date,n:s.n,days:s.days,sd:s.sd}));}
  const pair=(values,valid)=>Array.isArray(values)&&values.length===2&&values.every(valid);
  if([c.before_dates,c.after_dates].every(values=>pair(values,value=>typeof value==='string'&&value.length>0))){
    lines.push(t('insight.period_dates',{a:c.before_dates.map(x=>x.slice(0,10)).join(' — '),b:c.after_dates.map(x=>x.slice(0,10)).join(' — ')}));
  }
  if([c.before_range,c.after_range].every(values=>pair(values,Number.isFinite))
     &&[c.before_n,c.after_n].every(n=>Number.isInteger(n)&&n>0)){
    lines.push(t('insight.period_ranges',{a:c.before_range.join('–'),b:c.after_range.join('–'),na:c.before_n,nb:c.after_n}));
  }
  if(c.method_recorded===false||(c.comparison&&c.comparison.method_recorded===false))lines.push(t('insight.method_unknown'));
  return lines.map(x=>`<p class="meta">${esc(x)}</p>`).join('');
}

function insightChartHTML(change){
  const points=(change.series||[]).map(p=>({x:Date.parse(String(p.date).length===7?p.date+'-01':p.date),y:p.value,date:p.date}))
    .filter(p=>Number.isFinite(p.x)&&typeof p.y==='number'&&Number.isFinite(p.y)).sort((a,b)=>a.x-b.x);
  if(points.length<2)return '';
  const c=change.comparison||{}, b=change.basis||{}, limits=[b.low,b.high].filter(v=>typeof v==='number'&&Number.isFinite(v));
  const min=Math.min(...points.map(p=>p.y),...limits),max=Math.max(...points.map(p=>p.y),...limits),span=max-min||1;
  const x=p=>8+184*(p.x-points[0].x)/(points.at(-1).x-points[0].x||1),y=v=>54-44*(v-min)/span;
  const path=points.map(p=>x(p).toFixed(2)+','+y(p.y).toFixed(2)).join(' ');
  const meaning=t('insight.direction.'+change.status,{basis:t('insight.basis.'+(['target','reference'].includes(b.basis)?b.basis:'unknown'))});
  const label=change.name+' · '+t('insight.window.'+change.window)+' · '+t('insight.arrow.'+c.direction);
  const boundLines=limits.map(v=>`<path d="${esc('M8 '+y(v).toFixed(2)+' H192')}" stroke="currentColor" stroke-dasharray="3 4" opacity=".4"><title>${esc(t('insight.chart.range')+': '+fmtNum(v))}</title></path>`).join('');
  return `<figure class="insight-chart" data-direction="${esc(change.status)}"><figcaption><b>${esc(change.name)}</b> <span>${esc(c.direction==='up'?'↗':'↘')} ${esc(t('insight.arrow.'+c.direction))}</span></figcaption>
    <svg viewBox="0 0 200 64" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>${boundLines}<polyline points="${esc(path)}" fill="none" stroke="currentColor" stroke-width="2"/>${points.map(p=>`<circle cx="${esc(x(p).toFixed(2))}" cy="${esc(y(p.y).toFixed(2))}" r="2.5" fill="currentColor"><title>${esc(p.date+': '+fmtNum(p.y))}</title></circle>`).join('')}</svg>
    <div class="chart-dates"><span><strong>${esc(fmtNum(points[0].y))} ${esc(change.series[0].unit_display||change.series[0].unit||'')}</strong><br>${esc(fmtDate(points[0].date))}</span><span><strong>${esc(fmtNum(points.at(-1).y))} ${esc(change.series[0].unit_display||change.series[0].unit||'')}</strong><br>${esc(fmtDate(points.at(-1).date))}</span></div><p class="chart-meaning">${esc(meaning)}</p>
    ${change.show_latest!==false&&b.latest_outside?`<p class="meta">${esc(t('insight.latest_outside'))}</p>`:''}${change.show_latest!==false&&b.latest_reversal?`<p class="meta">${esc(t('insight.latest_reversal'))}</p>`:''}
    <span class="meta">${change.series[0]?.measurement_source?esc(measurementLabel(change.series[0]))+" · ":""}${esc(t('insight.chart.readings',{n:points.length,unit:change.series[0].unit_display||change.series[0].unit||''}))}</span></figure>`;
}

function insightWindowsHTML(item){
  const changes=item.trajectory?.changes||[];
  return changes.length?`<div class="insight-windows">${[365].map(window=>{
    const rows=changes.filter(c=>c.window===window);if(!rows.length)return '';
    return `<section class="insight-window"><b class="meta">${esc(t('insight.window.'+window))}</b>${rows.slice(0,1).map(c=>insightChartHTML({...c,show_latest:window===365||!changes.some(a=>a.marker===c.marker&&a.window===365)})).join('')}${rows.length>1?`<details class="fold"><summary>${esc(t('insight.more',{n:rows.length-1}))}</summary>${rows.slice(1).map(insightChartHTML).join('')}</details>`:''}</section>`;
  }).join('')}</div>`:'';
}

function insightContextHTML(item){
  const c=item.context||{}, genes=c.genetics||[], life=(c.lifestyle||[]).filter(r=>r.scope!=='patient_report');
  const links=[];
  if(genes.length||(c.comparisons||[]).length)links.push(item.system
    ?`<a class="cr-btn cr-btn--s cr-btn--ghost" href="#system/${encodeURIComponent(item.system)}" data-system="${esc(item.system)}">${esc(t('system.layer.genetics'))}</a>`
    :`<a class="cr-btn cr-btn--s cr-btn--ghost" href="#" data-goto="web.tab.genome">${esc(t('web.tab.genome'))}</a>`);
  if(life.length||c.cgm)links.push(`<a class="cr-btn cr-btn--s cr-btn--ghost" href="#" data-goto="web.tab.lifestyle">${esc(t(c.cgm?'cgm.title':'web.tab.lifestyle'))}</a>`);
  return links.length?`<nav class="toolbar insight-context-links" data-insight-context-links>${links.join('')}</nav>`:'';
}

function insightBasisHTML(item){
  const b=item.provenance?.basis;if(!b)return '';
  const seen=new Set(),rows=[];
  (b.facts||[]).forEach(f=>{const key=JSON.stringify([f.source,f.date]);if(seen.has(key))return;seen.add(key);
    rows.push(`<tr><td>${esc(t('insight.basis.fact'))}</td><td>${esc(f.date||'—')}</td><td>${esc(f.source||t('insight.basis.source_unknown'))}${f.availability==='unavailable'?`<p class="cr-caption">${esc(t('insight.basis.unavailable'))}</p>`:''}</td></tr>`);});
  [...(b.knowledge||[]),...(b.rule_sources||[])].forEach(w=>rows.push(`<tr><td>${esc(t('insight.basis.knowledge'))}</td><td>${esc(w.checked_on||'—')} · ${esc(w.version||'—')}</td><td>${esc(w.source||t('insight.basis.source_unknown'))}</td></tr>`));
  return `<details class="fold" data-insight-basis><summary>${esc(t('insight.basis.title'))}</summary><div class="tblwrap"><table class="cr-table cr-table--compact"><thead><tr><th></th><th>${esc(t('insight.basis.date'))}</th><th>${esc(t('insight.basis.source'))}</th></tr></thead><tbody>${rows.join('')}</tbody></table></div><p class="cr-caption">${esc(t('insight.basis.recorded'))}</p><p class="cr-caption">${esc(t('insight.basis.refresh'))}</p></details>`;
}

function attentionItemHTML(item, select=true){
  const summaries=item.summaries||[], chartSummaries=new Set((item.trajectory?.changes||[]).map(c=>c.summary)), lead=summaries.filter(s=>!chartSummaries.has(s)).slice(0,2);
  const detail=(item.events||[]).filter(e=>e.kind!=='genetic_phenotype').map(e=>{
    const d=e.detail||{};
    const texts=[d.action,d.factor,d.why_it_matters,d.mechanism,d.why,d.source,d.plan_source,d.study_limitations].filter(v=>typeof v==='string'&&v);
    const comparison=d.trend||(d.before_range?d:d.comparison)||(d.statistic?d:null);
    return `<div>${e.title!==item.title?`<p>${esc(e.title)}</p>`:''}${texts.map(v=>`<p>${esc(v)}</p>`).join('')}
      ${comparisonHTML(comparison)}${d.trend&&d.comparison?comparisonHTML(d.comparison):''}
      ${(e.limitations||[]).map(k=>`<p class="meta">${esc(t('insight.limit.'+k))}</p>`).join('')}</div>`;
  }).join('');
  return `<details class="cr-card attention-item" data-attention-card><summary><strong class="insight-title">${esc(item.title)}</strong> ${item.level?levelChip(item.level):''}</summary><div class="attention-body">
    ${insightWindowsHTML(item)}${lead.map(s=>`<p class="small">${esc(s)}</p>`).join('')}
    ${item.summaries?.length?'':`<div class="meta"><time>${esc(item.date||'')}</time>${item.reason?' · '+esc(item.reason):''}</div>`}
    ${insightContextHTML(item)}<details class="fold" data-insight-detail><summary>${esc(t('insight.more_evidence'))}</summary>${summaries.filter(s=>!lead.includes(s)).map(s=>`<p>${esc(s)}</p>`).join('')}${(item.detail_summaries||[]).map(s=>`<p class="meta">${esc(s)}</p>`).join('')}<ul>${(item.facts||[]).filter(f=>f.record!=='genotype').map(insightFactHTML).join('')}</ul>${detail}
      ${insightBasisHTML(item)}${item.system?`<a href="#" data-system="${esc(item.system)}">${esc(t('insight.panel_open'))}</a>`:`<a href="#" data-goto="web.tab.${esc(item.destination)}">${esc(t('insight.open'))}</a>`}
      ${select?`<label class="cr-label"><input type="checkbox" data-visit-item="${esc(item.id)}" ${services.selected(item.id)?'checked':''}> ${esc(t('insight.select'))}</label>`:''}</details></div></details>`;
}

function attentionHTML(feed){
  const items=feed?.highlights??feed?.items??[], followUp=feed?.follow_up||[];
  return `<h2 class="cr-h2">${esc(t('insight.title'))}</h2><p class="meta">${esc(t('web.phenotype.year'))}</p>
    ${items.map(i=>attentionItemHTML(i)).join('')}
    ${followUp.length?`<h3 class="cr-h3">${esc(t('insight.repeated_fold',{n:followUp.length}))}</h3>${followUp.map(i=>attentionItemHTML(i)).join('')}`:''}
    ${!items.length&&!followUp.length?`<p>${esc(feed?.items?.length?t('insight.highlights_empty'):t('insight.empty'))}</p>`:''}`;
}

function visitInsightHTML(item,index){
  const brief=item.visit_brief||{}, conclusions=brief.conclusions||item.summaries||[];
  const point=p=>`${esc(p.censored||'')}${esc(fmtNum(p.value))} ${esc(p.unit_display||p.unit||'')}<br><span class="meta">${esc(fmtDate(p.date))}</span>`;
  const readings=(brief.measurements||[]).map(m=>`<tr><th scope="row">${esc(m.name)}</th><td>${m.count>1?point(m.first):'—'}</td><td>${point(m.latest)}</td></tr>`).join('');
  return `<article class="visit-topic"><header><span class="visit-number">${String(index+1).padStart(2,'0')}</span><span>${esc(item.title)}</span>${item.level?levelChip(item.level):''}</header>
    <div class="visit-topic-body"><div><h3>${esc(t('web.visit.conclusion'))}</h3>${conclusions.map(x=>`<p>${esc(x)}</p>`).join('')}${(brief.support||[]).map(x=>`<p class="small">${esc(x)}</p>`).join('')}</div>
    ${readings?`<div><h3>${esc(t('web.visit.support'))}</h3><table class="cr-table cr-table--compact"><thead><tr><th>${esc(t('web.form.marker'))}</th><th>${esc(t('web.visit.before'))}</th><th>${esc(t('web.visit.latest'))}</th></tr></thead><tbody>${readings}</tbody></table></div>`:''}</div>
    ${brief.comparisons?.length?`<div class="visit-topic-footer">${geneticComparisonHTML(brief.comparisons,true,item.system||'')}</div>`:''}${insightBasisHTML(item)}</article>`;
}

function systemMedicationsHtml(med){
  const head=`<thead><tr><th>${esc(t('web.system.med_name'))}</th><th>${esc(t('web.system.med_dose'))}</th><th>${esc(t('web.system.med_class'))}</th></tr></thead>`;
  const table=rows=>`<div class="cr-table-wrap"><table class="cr-table system-medications-table">${head}<tbody>${rows}</tbody></table></div>`;
  const row=(m,labels,reason='')=>`<tr><td><b>${esc(m.name||'')}</b></td><td>${esc(m.dose||'—')}</td><td>${esc(labels.join(', ')||reason||t((m.system_links||[]).length?'system.meds.named_substance':'prescription.class_undefined'))}${(m.system_links||[]).map(x=>`<p class="cr-caption">${esc(x.relation_label)}${x.note?' · '+esc(x.note):''}</p>`).join('')}${reason&&labels.length?`<div class="cr-caption">${esc(reason)}</div>`:''}</td></tr>`;
  let h=med.rows?.length?table(med.rows.map(m=>row(m,m.via_labels||[])).join('')):'';
  if(med.empty_reason) h+=`<p class="cr-caption">${esc(med.empty_reason)}</p>`;
  const unplaced=(med.unmapped||[]).map(m=>row(m,m.class_labels||[],t('web.system.med_no_map')))
    .concat((med.unclassified||[]).map(m=>row(m,[],t('web.system.med_no_class'))));
  if(unplaced.length) h+=`<details class="fold system-medication-unplaced" data-medications-unplaced><summary>${esc(t('web.system.med_unplaced',{n:unplaced.length}))}</summary>${table(unplaced.join(''))}</details>`;
  return h;
}

function geneticPanelSummary(r){
  const lines=[r.verdict_line,r.unread_line].filter(Boolean);
  return lines.length?`<section class="layer" data-system-genetic-summary><h3 class="cr-h3">${esc(t('web.system.genetic_summary'))}</h3>${lines.map(line=>`<p class="muted">${esc(line)}</p>`).join('')}</section>`:'';
}

function mitochondrialContextHtml(c){
  const group=c.haplogroup?.name||'—';
  const source=s=>/^https:\/\//.test(s)?`<a href="${esc(s)}" target="_blank" rel="noopener noreferrer">${esc(s)}</a>`:'';
  const observations=p=>(p.observations||[]).map(m=>`<div class="row-l"><b>${esc(m.name)}</b>: ${esc(m.censored||'')}${esc(fmtNum(m.value))} ${esc(m.unit_display||m.unit||'')} <span class="meta">${esc(fmtDate(m.date))}</span>${m.series?.length>1?sparkline(m.series):''}</div>`).join('');
  const reports=rows=>(rows||[]).map(e=>`<p>${esc(e.detail?.summary||'')}</p>`).join('');
  return `<p>${esc(c.message)}</p>${c.status==='available'?`<p>${esc(t('mt.system.readings',{n:(c.variants||[]).length,group}))}</p>${!c.current?`<p class="cr-caption">${esc(t('mt.stale'))}</p>`:''}`:''}
    <a class="cr-btn cr-btn--ghost" href="#genome/mito" data-genome-pane="mito">${esc(t('mt.system.open'))}</a>
    ${(c.pathways||[]).map(p=>`<section class="cr-card card mt-2"><h4>${esc(p.title)}</h4><p><b>${esc(p.gene)} m.${esc(p.variant.position)}${esc(p.variant.ref)}&gt;${esc(p.variant.alt)}</b> · ${esc(fmtNum(p.variant.fraction*100))}%</p><p>${esc(p.summary)}</p><p class="cr-caption">${esc(p.status_text)}</p><p>${esc(p.clinical_context_text||'')}</p>${observations(p)}${(p.medications||[]).length?`<p>${esc(t('mt.system.related_treatment'))}: ${p.medications.map(m=>esc(m.name)).join(', ')}</p>`:''}${reports(p.reported_responses)}<details class="fold"><summary>${esc(t('mt.meaning'))}</summary>${levelChip(p.level)} <span>${esc(p.level_scope||'')}</span><p>${p.sources.map(source).join(' · ')}</p></details></section>`).join('')}
    ${(c.lifestyle||[]).length||(c.responses||[]).length?`<details class="fold"><summary>${esc(t('mt.system.context'))}</summary>${reports(c.responses)}${(c.lifestyle||[]).map(l=>`<p>${esc(l.note||[l.label||l.key,l.value_display??l.value,l.unit_display,l.date].filter(x=>x!=null).join(' · '))}</p>`).join('')}</details>`:''}
    <details class="fold"><summary>${esc(t('mt.meaning'))}</summary>${(c.limitations||[]).map(s=>`<p>${esc(s)}</p>`).join('')}</details>`;
}

function systemCardHtml(r){
  const L=[]; const layer=(n,key,body)=>L.push(`<div class="layer"><h3 class="cr-h3">${n}. ${esc(t(key))}</h3>${body}</div>`);
  if(r.on_demand){
    // A panel without a radar domain (task 199 F): no score, no figure, the
    // same rows through the same gate — and the reason at the top. The
    // laboratory layers do not exist for it and are not drawn.
    L.push(`<div class="layer"><h3 class="cr-h3">${esc(t('system.on_demand.head'))}</h3><div class="why">${esc(t('system.on_demand.why',{why:r.why_no_domain||'—'}))}</div></div>`);
    const gen=r.genetics||{};
    let b=genSummaryHtml(gen,r)+geneticCatalogueFold(gen,r);
    L.push(`<div class="layer"><h3 class="cr-h3">${esc(t('system.layer.on_demand_genetics'))}</h3>${b}</div>`);
    return L.join('')+geneticPanelSummary(r);
  }
  const lab=r.labs||{};
  let b='';
  if(lab.status==='context') b=`<p>${esc(t('system.labs.context',{measured:lab.measured||0}))}</p><p class="cr-caption">${esc(lab.score_note||'')}</p>`;
  else if(lab.status==='absent') b=`<div class="row-l">${esc(t('system.labs.absent'))}</div>`;
  else if(lab.status==='nodata') b=`<div class="row-l">${esc(t('system.labs.nodata',{total:lab.total||0}))}</div>`;
  else{
    b=`<div class="row-l">${esc(t('system.labs.line',{score:lab.score,level:t('system.level.'+(lab.level||'nodata')),measured:lab.measured||0,total:lab.total||0}))}</div>`;
  }
  if((lab.missing||[]).length) b+=`<div class="row-l muted">${esc(t('system.labs.missing',{markers:(lab.missing_names||lab.missing).join(', ')}))}</div>`;
  if((lab.stale||[]).length) b+=`<div class="row-l muted">${esc(t('system.labs.stale',{markers:lab.stale.map(s=>s.name||s.key).join(', ')}))}</div>`;
  if(lab.panel_term) b+=`<div class="row-l">${esc(t('system.panel_labs.term',{outside:lab.panel_term.outside,judged:lab.panel_term.judged,score:lab.panel_term.score}))}</div>`;
  b+=panelLabsHtml(lab.panel);
  b+=(r.validated_indices||[]).map(fib4Html).join('');
  const readings=lab.current_markers||[];
  const readingRows=readings.map(m=>`<div class="row-l">${badge((FLAG[m.flag]||FLAG.ok).cls,t((FLAG[m.flag]||FLAG.ok).key))} <b>${esc(m.name)}</b>: ${esc(m.censored||'')}${esc(fmtNum(m.value))} ${esc(m.unit_display??m.unit??'')} <span class="meta">${esc(fmtDate(m.date))}</span>${m.series?.length>1?sparkline(m.series,undefined,null,bodyMassMetric(m.key)):''}</div>`).join('');
  b=`<details class="fold system-current-labs"><summary>${esc(t('web.labs.group_counts',{measured:readings.length,abnormal:readings.filter(m=>m.abnormal).length}))}</summary>${readingRows}<button class="cr-btn cr-btn--ghost" data-lab-system="${esc(r.key)}">${esc(t('web.labs.open_system'))}</button>${b}</details>`;
  if(r.cgm_link)b+=`<a class="cr-btn cr-btn--ghost" href="#lifestyle">${esc(r.cgm_link.label)}</a>`;
  layer(1,'system.layer.labs',b);
  const dyn=r.dynamics||{};
  if(dyn.status==='ok'){
    const d=dyn.delta||0;
    b=`<div class="row-l">${esc(t('system.dynamics.line',{prev:dyn.prev_score,score:dyn.compared_score,delta:(d>0?'+':'')+d,date:fmtDate(dyn.prev_date)||'—',compared:dyn.compared||0}))}</div>`
     +(dyn.moved||[]).map(m=>`<div class="row-l">· ${esc(t('system.dynamics.moved',{name:m.name,from_value:m.from_value,to_value:m.to_value,unit:m.unit_display??m.unit??''}))}</div>`).join('');
  } else b=`<div class="row-l">${esc(t('system.dynamics.'+(dyn.status||'absent')))}</div>`;
  layer(2,'system.layer.dynamics',b);
  const gen=r.genetics||{};
  // The genotype of the system first, in the words a person reads; the list it
  // was composed from, every position's card and the scores fold under it —
  // open in the clinician's register, where they are the point.
  const summary=r.mitochondrial_context?mitochondrialContextHtml(r.mitochondrial_context):genSummaryHtml(gen,r);
  b='';
  if(gen.status==='composed'){
    const base=gen.base||{};
    b=`<div class="row-l">${esc(t('system.genetics.composed',{source:base.source||'—',version:base.version||'—',base_genes:base.genes||0,positions:(gen.curated||{}).positions||0,read_genes:gen.read_genes||0,read_positions:gen.read_positions||0,findings:gen.finding_count||0,carriers:gen.carrier_count||0,pending:gen.pending_count||0}))}</div>`
      +(gen.signature_author_count?`<div class="row-l">${esc(t('system.genetics.signature_author',{n:gen.signature_author_count,date:gen.signature_author_date||'—'}))}</div>`:'')
      +(gen.signature_open_count?`<div class="row-l">${esc(t('system.genetics.signature_open',{n:gen.signature_open_count}))}</div>`:'')
      +(gen.level_counts?`<div class="row-l">${esc(t('system.genetics.levels',{levels:['A','B','C','D','E'].filter(k=>gen.level_counts[k]).map(k=>k+' — '+gen.level_counts[k]).join(', ')||'—',none:gen.level_counts.none||0}))}</div>`:'');
    if(gen.withheld_by_classification) b+=`<div class="row-l muted">${esc(t('system.genetics.withheld',{n:gen.withheld_by_classification}))}</div>`;
    if((gen.excluded||[]).length) b+=`<div class="row-l muted">${esc(t('system.genetics.excluded',{genes:gen.excluded.map(e=>e.gene).join(', ')}))}</div>`;
    if((gen.refused||{}).total) b+=`<div class="row-l muted">${esc(t('system.genetics.refused',{n:gen.refused.total}))}</div>`;
    (gen.unreadable||[]).forEach(u=>{ b+=`<div class="row-l">${esc(t('system.genetics.unreadable',{gene:u.gene,reason:u.reason||'—'}))}</div>`; });
    b+=genTableHtml(gen,r,r.register);
    if(gen.rows_withheld_as_detail) b+=`<div class="row-l muted">${esc(t('system.row.patient_withheld',{n:gen.rows_withheld_as_detail}))}</div>`;
  }
  if(!r.mitochondrial_context&&!(gen.positions||[]).length) b+=systemPolygenicHtml(gen.polygenic, r.register);
  b=summary+thematicPanelLinks(r.thematic_panels)+(b?`<details class="fold" data-genetic-catalogue><summary>${esc(t('web.system.genetics_detail'))}</summary>${b}</details>`:'');
  layer(3,'system.layer.genetics',b);
  b=correctionRoutesHtml(r.correction_routes,r.register);
  // Not a numbered layer: the seven layers are the brief's own frame, and this
  // block answers a decision that is not the product's to make.
  if(b) L.push(`<div class="layer"><h3 class="cr-h3">${esc(t('system.routes.layer'))}</h3>${b}</div>`);
  b=systemMedicationsHtml(r.medications||{});
  layer(4,'system.layer.medications',b);
  const tg=r.target||{};
  b=(tg.rows||[]).map(x=>{
    if(!x.current) return `<div class="row-l">· ${esc(t('system.target.no_value',{name:x.name,spec:x.spec,unit:x.unit||'',set_by:x.set_by||'',set_on:x.set_on||''}))}</div>`;
    const side=x.outside_target?t(x.side==='above'?'target.side_above':'target.side_below'):t('system.target.within');
    return `<div class="row-l">· ${esc(t('system.target.row',{name:x.name,spec:x.spec,unit:x.unit||'',set_by:x.set_by||'',set_on:x.set_on||'',value:x.current.value,date:x.current.date||'—',side:side}))}</div>`;
  }).join('');
  if(tg.empty_reason) b+=`<div class="row-l muted">${esc(tg.empty_reason)}</div>`;
  layer(5,'system.layer.target',b);
  const tests=r.tests||{};
  b=visibleTestProposals(tests.rows).map(s=>testItem(s).outerHTML).join('');
  if(!b) b=`<div class="row-l muted">${esc(t('web.tests.none_supported'))}</div>`;
  layer(6,'system.layer.tests',b);
  const qs=r.questions||{};
  b=(qs.rows||[]).length?`<ol>${qs.rows.map(q=>`<li>${esc(q.text)}</li>`).join('')}</ol>`:'';
  if(qs.empty_why) b+=`<div class="row-l muted">${esc(t('system.why.'+qs.empty_why))}</div>`;
  layer(7,'system.layer.questions',b);
  const nxt=r.next||{};
  b=['lab','genome','ask'].map(k=>{const bk=nxt[k]||{};
    const rows=(bk.rows||[]).map(basketRowHtml).join('');
    const empty=bk.empty_reason||(!rows&&k==='lab'?t('web.tests.none_supported'):'');
    return `<div class="basket"><h4>${esc(t('system.next.'+k))}</h4>${rows}${empty?`<div class="row-l muted"><i>${esc(empty)}</i></div>`:''}${(bk.full_genome&&bk.full_genome.text)?`<div class="row-l">${esc(bk.full_genome.text)}</div>`:''}</div>`;}).join('');
  L.push(`<div class="layer"><h3 class="cr-h3">${esc(t('web.system.next_h'))}</h3>${b}</div>`);
  return L.join('')+geneticPanelSummary(r);
}

function actsOnHtml(m, sys){
  if(m.current===false) return '';
  const p=m.system_context||(sys?.prescriptions||[]).find(x=>x.name===m.name);
  if(!p) return '';
  const contexts=(p.system_links||[]).filter((x,i,all)=>all.findIndex(y=>y.relation===x.relation&&y.note===x.note)===i);
  const support=contexts.length?`<details class="fold"><summary>${esc(t('system.meds.link_basis'))}</summary>${contexts.map(x=>`<p class="cr-caption">${esc(x.relation_label)}${x.note?' · '+esc(x.note):''}</p>`).join('')}</details>`:'';
  if(p.systems&&p.systems.length)
    return `<div class="why">${esc(t('system.acts_on',{systems:''}))}${p.systems.map(k=>systemLinkHtml(k,t('radar.domain.'+k))).join(', ')}</div>`+support;
  if(p.outside_contexts?.length)return p.outside_contexts.map(x=>`<p class="cr-caption" data-medication-outside-system>${esc(x.note)}</p>`).join('');
  return `<div class="why muted">${esc(t('system.acts_on_none',{status:p.map_status}))}</div>`;
}

function medStatusText(s){
  const m=String(s||'').match(/^([a-z_]*?)_?(\d{4}-\d{2}(?:-\d{2})?)?$/);
  if(!m) return String(s||'—');
  const word=m[1]?t('web.meds.status.'+m[1]):'';
  const w=(!word||word.startsWith('⟦'))?String(m[1]||'').replace(/_/g,' '):word;
  return [w,m[2]?fmtDate(m[2]):''].filter(Boolean).join(' ')||'—';
}

function controlsHtml(controls, overdueOnly=false){
  if(!(controls||[]).length)return '';
  return `<section class="cr-card card ${overdueOnly?'warnbox':''}" data-treatment-controls><b>${esc(t(overdueOnly?'treatment.overdue':'treatment.title'))}</b>${controls.map(c=>`<div class="list-item"><div>${esc(t('treatment.control',{name:c.name||'—',marker:c.marker||'—',start:c.from||'—',due:c.due||'—'}))}</div><b>${esc(t('treatment.status.'+c.status))}</b>${c.plan_source?`<div class="meta">${esc(t('treatment.plan_source',{source:c.plan_source}))}</div>`:`<div class="meta">${esc(t('treatment.unresolved'))}</div>`}</div>`).join('')}</section>`;
}

function treatmentHtml(data){
  if(!data)return '';
  return `${controlsHtml(data.current_controls??(data.controls||[]).filter(c=>c.current!==false))}${(data.historical_controls||[]).length?`<details class="fold" data-historical-controls><summary>${esc(t('treatment.history_controls'))}</summary>${controlsHtml(data.historical_controls)}</details>`:''}<details class="fold" data-treatment-timeline><summary>${esc(t('treatment.title'))}</summary><p class="meta">${esc(t('treatment.scope'))}</p><ol>${(data.events||[]).map(e=>`<li><time>${esc(e.date)}</time> · ${e.kind==='prescription_start'?`<b>${esc(t('treatment.start'))}: ${esc(e.name)}</b> ${esc(e.dose||'')}`:`${esc(e.name)}: ${esc(e.comparator||'')}${esc(e.value??'—')} ${esc(e.unit||'')}`}</li>`).join('')}</ol>${(data.undated||[]).map(e=>`<div class="meta">${esc(e.name)} · ${esc(t('treatment.undated'))}</div>`).join('')}</details>`;
}

function medItem(m, sys){
  // `current` is the server's verdict by the one rule in core — the page does not
  // re-decide which words mean «taking it».
  const st=m.current===false?` ${badge('b-unknown',medStatusText(m.status))}`:'';
  return `<div class="list-item"><div class="row"><b>${esc(m.name)}</b> ${m.dose?`<span class="muted">${esc(m.dose)}</span>`:''}${st} <button class="cr-btn cr-btn--ghost cr-btn--s ghost btn-sm ml-auto" data-rm="${esc(m.name)}">${esc(t('web.meds.remove'))}</button></div>${m.scheme_date?`<div class="meta">${esc(t('treatment.scheme_date'))}: ${esc(fmtDate(m.scheme_date))}</div>`:''}<div class="meta">${m.start_date?`${esc(t('treatment.intake_start'))}: ${esc(fmtDate(m.start_date))}`:esc(t('treatment.intake_start_missing'))}</div>${noteHtml(m.note)}${actsOnHtml(m,sys)}</div>`;
}

function visitReportChart(chart){
  const source=chart.series||[], points=source.filter(p=>Number.isFinite(p.value));
  if(!points.length)return '';
  const dated=points.map(p=>({...p,stamp:Date.parse(String(p.date).length===7?p.date+'-01':p.date)})).filter(p=>Number.isFinite(p.stamp));
  if(!dated.length)return '';
  const values=dated.map(p=>p.value),lo=Math.min(...values),hi=Math.max(...values),pad=(hi-lo)*.18||Math.max(Math.abs(hi)*.05,1);
  const start=Math.min(...dated.map(p=>p.stamp)),end=Math.max(...dated.map(p=>p.stamp));
  const xy=p=>[20+(p.stamp-start)/(end-start||1)*280,100-(p.value-(lo-pad))/(hi-lo+2*pad)*65];
  const connected=(chart.connect||chart.display_connect)&&new Set(dated.map(p=>p.unit||'')).size<=1;
  const path=dated.map((p,i)=>`${i?'L':'M'}${xy(p).join(' ')}`).join(' ');
  const selected=new Set([0,dated.length-1]);const middle=Math.floor((dated.length-1)/2);if(xy(dated[middle])[0]-xy(dated[0])[0]>45&&xy(dated.at(-1))[0]-xy(dated[middle])[0]>45)selected.add(middle);
  const svg=chart.numeric_axis===false?'':`<svg viewBox="0 0 320 137" role="img" aria-label="${esc(chart.name)}">${connected&&dated.length>1?`<path d="${path}" class="visit-report-line"/>`:''}${dated.map((p,i)=>{const [x,y]=xy(p);return `<g><title>${esc(fmtDate(p.date))}: ${esc(fmtNum(p.value))} ${esc(p.unit_display||p.unit||'')}</title><circle cx="${x}" cy="${y}" r="3"/>${selected.has(i)?`<text x="${x}" y="${y-9}" text-anchor="${i===0?'start':i===dated.length-1?'end':'middle'}" class="visit-point-value">${esc(p.censored||'')}${esc(fmtNum(p.value))}</text>${i===0||i===dated.length-1?`<text x="${x}" y="126" text-anchor="${i===0?'start':i===dated.length-1?'end':'middle'}">${esc(fmtDate(p.date))}</text>`:''}`:''}</g>`;}).join('')}</svg>`;
  return `<article class="visit-report-chart"><h3>${esc(chart.name)}</h3><p class="cr-caption">${esc(points.at(-1).unit_display||points.at(-1).unit||'')}</p>${svg}${chart.summary?`<p>${esc(chart.summary)}</p>`:''}${(dated.length>1&&!connected||chart.numeric_axis===false)?`<p class="cr-caption">${esc(t('visit.report.separate'))}</p>`:''}<details class="visit-point-details" ${chart.numeric_axis===false?'open':''}><summary>${esc(t('visit.report.points'))}</summary><table class="cr-table cr-table--compact"><tbody>${source.map(p=>`<tr><th>${esc(fmtDate(p.date))}</th><td>${esc(p.censored||'')}${esc(fmtNum(p.value))} ${esc(p.unit_display||p.unit||'')}</td><td>${esc(p.measurement_source||p.source?.path||(typeof p.source==='string'?p.source:'')||p.record||'')}</td></tr>`).join('')}</tbody></table></details></article>`;
}

function visitReportSystem(s,short){
  const measures=s.focus_measurements||[],genes=s.discussion_genetics||[],series=s.discussion_charts||[];
  if(!measures.length&&!s.insights.length&&!genes.length)return '';
  const shown=short?measures.slice(0,3):measures;
  const charts=series;
  const point=m=>`${esc(m.censored||'')}${esc(fmtNum(m.value))} ${esc(m.unit_display||m.unit||'')}`;
  const bounds=m=>m.ref_low!=null&&m.ref_high!=null?fmtNum(m.ref_low)+'–'+fmtNum(m.ref_high):m.ref_low!=null?'≥'+fmtNum(m.ref_low):m.ref_high!=null?'≤'+fmtNum(m.ref_high):'—';
  const conclusions=[...new Set(s.insights.flatMap(i=>i.conclusions||[]))];
  return `<article class="visit-report-system"><h3>${esc(s.label)}</h3>${(short?conclusions.slice(0,2):conclusions).map(c=>`<p>${esc(c)}</p>`).join('')}
    ${shown.length?`<table class="cr-table cr-table--compact"><thead><tr><th>${esc(t('web.form.marker'))}</th><th>${esc(t('web.form.value'))}</th><th>${esc(t('visit.reference_bounds'))}</th></tr></thead><tbody>${shown.map(m=>`<tr><th>${esc(m.name)}</th><td>${point(m)} · ${esc(fmtDate(m.date))}</td><td>${esc(bounds(m))}</td></tr>`).join('')}</tbody></table>`:''}
    ${measures.length>shown.length?`<p class="cr-caption">${esc(t('visit.report.more_markers',{n:measures.length-shown.length}))}</p>`:''}
    ${charts.length?`<div class="visit-report-charts">${charts.map(c=>visitReportChart({...c,summary:conclusions.includes(c.summary)?'':c.summary})).join('')}</div>`:''}
    ${genes.length?`<h4>${esc(t('visit.report.genetics'))}</h4>${visitReportGenes(genes,s.key)}`:''}
    ${s.more_discussion_genetics?`<button class="cr-btn cr-btn--ghost cr-btn--s visit-actions" data-visit-open-system="${esc(s.key)}">${esc(t('visit.report.more_factors',{n:s.more_discussion_genetics}))}</button>`:''}
    </article>`;
}
return Object.freeze({insightFactHTML,comparisonHTML,insightChartHTML,insightWindowsHTML,insightContextHTML,insightBasisHTML,attentionItemHTML,attentionHTML,visitInsightHTML,systemMedicationsHtml,systemCardHtml,actsOnHtml,medStatusText,controlsHtml,treatmentHtml,medItem,visitReportChart,visitReportSystem});
}
return Object.freeze({create});
});
