/* Exercise the public component contract with explicit presentation services. */
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let language='en',register='patient';
const t=(key,args={})=>Object.entries(args).reduce((s,[k,v])=>s.replaceAll('{'+k+'}',v),MESSAGES[language][key]||key);
const cards=ScholionGeneCards.create({t,escape:esc,grade:level=>`<span class="badge">${esc(level)}</span>`,formatDate:esc,register:()=>register,
  passport:()=>'',authorNote:()=>'',clinicalBasis:()=>''});
function renderGallery(options={}){
  language=options.language||language;register=options.register||register;
  document.documentElement.lang=language;
  document.documentElement.dataset.theme=options.theme||'light';
  document.querySelector('#language').value=language;document.querySelector('#register').value=register;
  document.querySelector('#theme').value=options.theme||'light';
  document.querySelector('#cards').innerHTML=ScholionGalleryCases.cases.map(c=>`<section data-case="${c.id}"><h2>${esc(c.id)}</h2>${cards.render(c.row,c.options)}</section>`).join('');
  document.querySelector('#systems').innerHTML=typeof ScholionSystemViews==='undefined'?'':renderSystemGallery();
  document.querySelector('#measurements').innerHTML=typeof ScholionMeasurements==='undefined'?'':renderMeasurementGallery();
}
for(const id of ['language','register','theme'])document.querySelector('#'+id).onchange=()=>renderGallery(Object.fromEntries(['language','register','theme'].map(k=>[k,document.querySelector('#'+k).value])));
renderGallery();
