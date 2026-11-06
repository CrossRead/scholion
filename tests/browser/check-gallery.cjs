/* Run with an installed Playwright; fail explicitly if the browser is absent. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const [gallery,output,baseline]=process.argv.slice(2);
if(!gallery||!output)throw Error('Usage: node check-gallery.cjs gallery/index.html output-directory [baseline-directory]');
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const start=performance.now();
 const browser=await chromium.launch(process.env.SCHOLION_BROWSER_EXECUTABLE?{executablePath:process.env.SCHOLION_BROWSER_EXECUTABLE}:{});
 const context=await browser.newContext({viewport:{width:1280,height:900},locale:'en-GB',timezoneId:'UTC',reducedMotion:'reduce'});
 await context.route(/^https?:/,route=>route.abort());
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const results=[];
 try{
 await page.goto(pathToFileURL(path.resolve(gallery)).href);
 for(const width of [1280,375]) for(const language of ['en','ru']) for(const register of ['patient','clinician']) for(const theme of ['light','dark']){
  await page.setViewportSize({width,height:900});
  await page.evaluate(opts=>renderGallery(opts),{language,register,theme});
  const id=[width,language,register,theme].join('-');
  assert.equal(await page.locator('[data-case]').count(),19);
  const conflict=page.locator('[data-case="reading-conflict"]');
  assert.ok((await conflict.innerText()).includes(await page.evaluate(()=>t('genome.source_conflict'))));
  const saved=page.locator('[data-case="reading-saved"]');
  assert.equal(await saved.locator('.gene-card-genotype').innerText(),'AG');
  assert.ok(!(await saved.innerText()).includes('999'));
  const readingDetails=conflict.locator('[data-reading-details]');
  await readingDetails.locator(':scope > summary').click();
  const observations=conflict.locator('[data-reading-observations]');
  await observations.locator(':scope > summary').click();
  assert.ok((await observations.innerText()).includes('synthetic-history.json'));
  await observations.locator(':scope > summary').click();
  await readingDetails.locator(':scope > summary').click();
  assert.equal(await page.locator('[data-case="escaped"] img').count(),0);
  assert.equal(await page.locator('[data-case="unread"] .gene-card-call').count(),0);
  const state=await page.evaluate(()=>{
   const root=document.querySelector('#cards');
   return {html:root.innerHTML,elements:[...root.querySelectorAll('*')].map(el=>{
    const r=el.getBoundingClientRect(),s=getComputedStyle(el);
    return [el.tagName,r.x,r.y,r.width,r.height,s.fontSize,s.fontWeight,s.color,s.backgroundColor,s.display];
   }),overflow:document.documentElement.scrollWidth>innerWidth+1};
  });
  assert.equal(state.overflow,false,id+' overflow');
  const json=JSON.stringify(state);fs.writeFileSync(path.join(output,id+'.json'),json);
  if(baseline)assert.equal(json,fs.readFileSync(path.join(baseline,id+'.json'),'utf8'),id+' layout/content changed');
  if(await page.locator('[data-measurement]').count()){
    assert.equal(await page.locator('[data-measurement=annual-weight] polyline').count(),1);
    assert.equal(await page.locator('[data-measurement=bounded] polyline').count(),0);
  }
  if(await page.locator('[data-system-case]').count()){
    assert.equal(await page.locator('[data-system-case]').count(),14);
    assert.equal(await page.locator('[data-system-case="escaped"] script').count(),0);
    const attention=page.locator('[data-system-case="attention"] [data-attention-card]');
    await attention.locator(':scope > summary').click();
    assert.equal(await attention.evaluate(el=>el.open),true);
    assert.equal(await attention.locator('[data-system="lipids"]').first().getAttribute('href'),'#system/lipids');
    await attention.locator(':scope > summary').click();
    assert.equal(await attention.evaluate(el=>el.open),false);
  }
  // Actual native disclosure behavior, not a string containing <details>.
  const disclosure=page.locator('[data-case="called"] details').first();
  await disclosure.locator('summary').click();assert.equal(await disclosure.evaluate(el=>el.open),true);
  await disclosure.locator('summary').click();assert.equal(await disclosure.evaluate(el=>el.open),false);
  const link=page.locator('[data-case="called"] .gene-card-name a').first();
  assert.equal(await link.getAttribute('href'),'https://www.ncbi.nlm.nih.gov/gene/?term=SYNTHETIC%5BPREF%5D%20AND%209606%5Btaxid%5D');
  assert.equal(await link.getAttribute('target'),'_blank');
  results.push({id,elements:state.elements.length});
 }
 await page.emulateMedia({media:'print'});
 await page.pdf({path:path.join(output,'gallery.pdf'),format:'A4',printBackground:true});
 await page.emulateMedia({media:'screen'});
 await page.screenshot({path:path.join(output,'gallery.png'),fullPage:true});
 assert.deepEqual(errors,[]);
 const result={browser:browser.version(),seconds:(performance.now()-start)/1000,states:results,errors,baseline_compared:!!baseline};
 fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
