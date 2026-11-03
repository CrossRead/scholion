/* Shared measurement component, fixed observations; no profile or clock. */
const measurementPoints=[{date:'2025-11-03',value:101,measurement_source:'garmin',aggregation:'monthly_mean'},
 {date:'2026-04-02',value:99,measurement_source:'recorded'},
 {date:'2026-10-27',value:96,measurement_source:'recorded'}];
function renderMeasurementGallery(){
 const component=ScholionMeasurements.create({t,esc,fmtNum:x=>language==='ru'?String(x).replace('.',','):String(x),fmtDate:esc,
  targetSpec:()=>'',flagOf:()=>({cls:'b-good',key:'web.flag.ok'}),trendNote:()=>'',badge:()=>'',refText:()=>'',
  targetText:()=>'',ownerNoteHtml:()=>'',systemLinkHtml:()=>'',decisionNote:()=>'',noteHtml:()=>'',targetAsk:()=>'',srcTag:()=>'',comparisonHTML:()=>'',flags:{unknown:{cls:'b-unknown',key:'web.flag.unknown'}}});
 const current={ref:'metric:weight',value:96,unit:'kg',date:'2026-10-27',source:'recorded',series:measurementPoints};
 const rows=[{id:'annual-weight',html:component.current(current)+component.annual(current)},
  {id:'annual-single',html:component.annual({...current,series:[],value:96,reading_status:'within'})},
  {id:'bounded',html:component.render({name:'Synthetic bound',value:5,censored:'<',unit:'unit',series:[measurementPoints[0],{...measurementPoints[1],censored:'<'}]},'lab')},
  {id:'metric',html:component.render({name:'Synthetic weight',key:'weight',value:96,unit:'kg',series:measurementPoints},'metric')},
  {id:'fitness',html:component.render({label:'Synthetic weight',key:'Weight',value:96,unit:'kg',combined_history:true,series:measurementPoints},'lifestyle')}];
 return rows.map(r=>`<section data-measurement="${r.id}"><h2>${r.id}</h2>${r.html}</section>`).join('');
}
