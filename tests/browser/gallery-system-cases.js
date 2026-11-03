/* Synthetic presentation states, not medical rules. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ScholionSystemCases=api;})(globalThis,function(){
const points=[{date:'2025-11-03',value:5.5,unit:'mmol/L'},{date:'2026-05-03',value:4.9,unit:'mmol/L'},{date:'2026-10-23',value:4.4,unit:'mmol/L'}];
const medication={name:'Synthetic <medicine>',dose:'Recorded regimen',current:true,system_context:{systems:['lipids'],system_links:[{relation:'monitoring',relation_label:'Recorded relation',note:'Synthetic source'}]}};
const insight={id:'system:lipids',system:'lipids',title:'Synthetic system trend',level:'B',summaries:['Recorded observation'],facts:[{...points[2],source:'synthetic.json'}],events:[],context:{genetics:[{gene:'SYN'}],lifestyle:[{key:'weight',value:90}]},trajectory:{changes:[{name:'Synthetic measurement',marker:'synthetic',window:365,status:'toward',series:points,comparison:{direction:'down'},basis:{low:3,high:5,latest_reversal:true}}]},provenance:{basis:{facts:[{source:'synthetic.json',date:'2026-10-23'}],knowledge:[{source:'Synthetic reference',version:'fixture',checked_on:'2026-10-23'}]}}};
const system={key:'lipids',register:'patient',labs:{status:'ok',score:60,level:'watch',measured:1,total:1,current_markers:[{name:'Synthetic measurement',key:'synthetic',...points[2],flag:'ok',series:points}]},genetics:{status:'absent'},dynamics:{status:'absent'},medications:{rows:[medication]},questions:{rows:[]},tests:{rows:[]},next:{}};
const cases=[
{id:'attention',method:'attentionItemHTML',args:[insight]},
{id:'attention-empty',method:'attentionHTML',args:[{}]},
{id:'attention-follow-up',method:'attentionHTML',args:[{highlights:[insight],follow_up:[{...insight,id:'follow-up'}]}]},
{id:'visit-insight',method:'visitInsightHTML',args:[{...insight,visit_brief:{conclusions:['Synthetic conclusion'],support:['Supplied context'],measurements:[{name:'Synthetic measurement',count:3,first:points[0],latest:points[2]}]}},0]},
{id:'system',method:'systemCardHtml',args:[system]},
{id:'system-empty',method:'systemCardHtml',args:[{...system,labs:{status:'nodata'},medications:{}}]},
{id:'medications',method:'systemMedicationsHtml',args:[{rows:[{...medication,via_labels:['Readable class']}],unmapped:[{name:'Synthetic unmapped',class_labels:['Readable class']}],unclassified:[{name:'Synthetic unclassified'}]}]},
{id:'medicine-current',method:'medItem',args:[medication,{}]},
{id:'medicine-stopped',method:'medItem',args:[{...medication,current:false,status:'stopped_2026-10-23'},{}]},
{id:'controls',method:'controlsHtml',args:[[{name:'Synthetic',marker:'Synthetic marker',current:true,status:'pending',from:'2026-01-01',due:'2026-10-23',plan_source:'Synthetic plan'}]]},
{id:'history',method:'treatmentHtml',args:[{current_controls:[],historical_controls:[{name:'Synthetic',marker:'Synthetic marker',current:false,status:'done'}],events:[{date:'2026-01-01',kind:'prescription_start',name:'Synthetic',dose:'Recorded regimen'}]}]},
{id:'visit-chart',method:'visitReportChart',args:[{name:'Synthetic measurement',series:points,connect:true}]},
{id:'visit-system',method:'visitReportSystem',args:[{key:'lipids',label:'Synthetic system',focus_measurements:[{name:'Synthetic measurement',...points[2]}],discussion_charts:[{name:'Synthetic measurement',series:points,connect:true}],insights:[{conclusions:['Synthetic conclusion']}],discussion_genetics:[]},true]},
{id:'escaped',method:'attentionItemHTML',args:[{...insight,title:'<script>unsafe</script>',summaries:['<img onerror=unsafe>']}]}
];
return {cases,insight,system,medication};
});
