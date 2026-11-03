/* Synthetic presentation states only; not medical examples or profile data. */
(function(root){
  const base={gene:'SYNTHETIC',rsid:'rs123',read:true,genotype:'AG',state:'het',level:'B',depth:32,
    reference_context:{gene_function:'Synthetic supplied gene function.',variant_context:'Synthetic supplied variant context.',gene_source:'https://example.org/reference'}};
  const cases=[
    {id:'called',row:base},
    ...['A','B','C','D','E'].map(level=>({id:'level-'+level,row:{...base,level}})),
    {id:'unread',row:{...base,read:false}},
    {id:'assumed',row:{...base,reading:{confidence:'assumed_ref'}}},
    {id:'reference',row:{...base,genotype:'AA',state:'absent'}},
    {id:'gene-only',row:{gene:'SYNTHETIC',reference_context:base.reference_context}},
    {id:'compound',row:{...base,diplotype:'*1/*2'}},
    {id:'carrier',row:{...base,clnsig:'Pathogenic',personal_context:{status:'carrier_context',label:'Synthetic carrier context',summary:'Supplied personal meaning.',zygosity:'heterozygous',alternative_copies:1,inheritance_label:'Autosomal recessive'}}},
    {id:'screen',row:{gene:'SYNTHETIC'},options:{geneScreen:{read:false,scanStatus:'ok',findings:0,why:'Synthetic unavailable region'}}},
    {id:'region',row:{gene:'SYNTHETIC'},options:{geneRegion:{status:'ok',variants:{total:1,reference_calls:[]},message:'Synthetic interval'}}},
    {id:'long',row:{...base,gene:'SYNTHETIC_LONG_GENE_NAME',reference_context:{...base.reference_context,gene_function:'Synthetic supplied function. '.repeat(12)}}},
    {id:'escaped',row:{...base,gene:'<img src=x onerror=alert(1)>',summary:'<script>unsafe</script>'}},
    {id:'context',row:base,options:{contextHtml:'<p data-synthetic-context>Supplied measurement context.</p>'}},
    {id:'reading-conflict',row:{...base,conflict:{kind:'source_disagreement'},interpretation_applicable:false,
      reading_record:{schema:1,selected:'current',observations:[
        {genotype:'AG',quality:{depth:32},source:{file:'synthetic.vcf'}},
        {genotype:'AA',quality:{depth:21},source:{file:'synthetic-history.json'}}]}}},
    {id:'reading-saved',row:{...base,genotype:'TT',depth:999,reading:{genotype:'AG',confidence:'reported',
      from_profile:'synthetic-history.json',reading_record:{schema:1,selected:'recorded',observations:[
        {genotype:'AG',source:{file:'synthetic-history.json'}}]}}}},
  ];
  const api={cases};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  root.ScholionGalleryCases=api;
})(globalThis);
