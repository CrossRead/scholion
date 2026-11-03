/* The same public factory used by the page, with explicit synthetic slots. */
function systemGalleryServices(){
 const empty=()=>'';
 return {t,esc,fmtNum:x=>String(x??'—'),fmtDate:x=>String(x||''),measurementLabel:empty,
  levelChip:x=>`<span class="badge">${esc(x)}</span>`,selected:()=>false,
  flags:{ok:{cls:'b-ok',key:'ok'}},badge:(cls,text)=>`<span class="badge ${esc(cls)}">${esc(text)}</span>`,
  geneticComparisonHTML:empty,genSummaryHtml:empty,geneticCatalogueFold:empty,panelLabsHtml:empty,
  fib4Html:empty,sparkline:empty,bodyMassMetric:()=>false,genTableHtml:empty,systemPolygenicHtml:empty,
  thematicPanelLinks:empty,correctionRoutesHtml:empty,visibleTestProposals:rows=>rows||[],
  testItem:()=>({outerHTML:''}),basketRowHtml:empty,
  systemLinkHtml:(key,label)=>`<a href="#system/${encodeURIComponent(key)}" data-system="${esc(key)}">${esc(label)}</a>`,
  noteHtml:empty,visitReportGenes:empty};
}
function renderSystemGallery(){
 const component=ScholionSystemViews.create(systemGalleryServices());
 return ScholionSystemCases.cases.map(c=>`<section class="${c.id.startsWith('visit-')?'visit-sheet':'today-view syscard'}" data-system-case="${c.id}"><h2>${esc(c.id)}</h2>${component[c.method](...c.args)}</section>`).join('');
}
