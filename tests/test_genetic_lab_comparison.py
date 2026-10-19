"""The same personal comparison survives every door without overstating evidence."""
from copy import deepcopy
from datetime import date, timedelta
from unittest import TestCase, mock

import support  # noqa: F401
from scholion import core, genetic_comparison as gc
from scholion.i18n import set_lang
from scholion.insight_context import _genetic_context, prepare_context


class GeneticComparisonTests(TestCase):
    def tearDown(self):
        set_lang(None)

    def row(self, rsid='rs2231142', **changes):
        spec=next(r for r in gc.catalogue()['links'] if r['rsid']==rsid)
        return {'gene':spec['gene'],'rsid':rsid,'level':'B','state':'het','read':True,'carrier':True,
                'mode':spec['evidence_type'], 'risk_allele':spec['catalogue_allele'],'hgvs':spec['catalogue_hgvs'], 'genotype':{'genotype':'GT','confidence':'called','depth':30,
                'source':'synthetic VCF','filter':'PASS'},'interpretation':{'summary':'Synthetic'},**changes}

    def marker(self, value=8, **changes):
        p={'date':date.today().isoformat(),'value':value,'unit':'mg/dL','ref_low':2,'ref_high':6,
           'source':'synthetic form','date_source':'form',**changes}
        return {'key':'uric_acid','name':'Urate',**p,'series':[p]}

    def compare(self,row=None,marker=None):
        return gc.compare(row or self.row(),{'uric_acid':marker or self.marker()})

    def test_normal_high_low_are_observations_not_causes(self):
        for value,status in [(4,'within'),(8,'concordant'),(1,'different_direction')]:
            r=self.compare(marker=self.marker(value))
            self.assertEqual(r['status'],status)
            self.assertFalse(r['causal'])
            self.assertEqual(r['facts']['laboratory']['value'],value)
            self.assertFalse(any(h['eligible'] for h in r['horizons']))
            if status=='within':self.assertIsNone(r['question'])

    def test_legacy_and_context_share_currentness_and_quality(self):
        exp={'marker':'uric_acid','direction':'higher'}
        cases=[{'date':'2000-01-01'}, {'date':(date.today()+timedelta(days=1)).isoformat()},
               {'censored':'<'},{'proposed_rule':True},{'reference_withheld':True},
               {'date_source':'filename'},{'ref_low':20,'ref_high':6}]
        for patch in cases:
            m=self.marker(**patch); markers={'uric_acid':m}
            with self.subTest(patch=patch):
                new=gc.compare(self.row(),markers)
                old=gc.legacy_expectation(exp,markers)
                self.assertFalse(new['eligible'])
                self.assertEqual(old['position'],'unknown')
                self.assertEqual(new['observation']['point']['value'],8)
                self.assertEqual(_genetic_context(self.row(),markers)['status'],new['status'])
        self.assertEqual(gc.compare(self.row(),{})['observation']['status'],'missing')

    def test_low_depth_filters_imputation_and_missing_quality_do_not_confirm(self):
        for patch in ({'depth':2},{'depth':None},{'filter':'LowQual'}, {'imputed':True},
                      {'needs_confirmation':[{'what':'allele_fraction_off_half'}]}, {'unverified_locus':True}):
            row=self.row(); row['genotype'].update(patch)
            r=self.compare(row)
            self.assertFalse(r['eligible'],patch)
            self.assertEqual(r['quality']['status'],'limited')
            self.assertTrue(r['reason_labels'])
        for patch,status in [({'read':False},'unread'),({'state':'absent','carrier':False},'allele_absent')]:
            r=self.compare(self.row(**patch))
            self.assertEqual(r['status'],status)
            self.assertFalse(r['eligible'])

    def test_reference_function_cannot_create_an_association(self):
        row=self.row(); row.update(rsid='rs999',reference_context={'gene_function':'Synthetic'})
        self.assertIsNone(gc.compare(row,{}))

    def test_recessive_and_nonsecretor_claims_do_not_apply_to_one_copy(self):
        for rsid in ('rs601338','rs1801133','rs1800562','rs5742905'):
            row=self.row(rsid)
            r=gc.compare(row,{})
            self.assertFalse(r['applicable'])
            self.assertIn('genotype_scope',r['reasons'])
        r=gc.compare(self.row('rs601338',state='hom'),{'vitamin_b12':self.marker(8)})
        self.assertTrue(r['eligible'])

    def test_hypotheses_are_not_promoted_by_matching_labs(self):
        for rsid in ('rs429358','rs1050828','rs855791'):
            row=self.row(rsid); spec=next(r for r in gc.catalogue()['links'] if r['rsid']==rsid)
            result=gc.compare(row,{spec['marker']:self.marker()})
            self.assertEqual(result['status'],'hypothesis')
            self.assertFalse(result['eligible'])
            self.assertIsNone(result['interpretation'])
            self.assertTrue(result['hypothesis'])
        r=gc.compare(self.row('rs174546'),{'omega3_index':self.marker(1)})
        self.assertEqual(r['status'],'excluded')
        self.assertIsNone(r['hypothesis'])

    def test_unverified_fasting_and_wrong_study_sex_are_named(self):
        r=gc.compare(self.row('rs1260326'),{'glucose':self.marker(1)})
        self.assertFalse(r['eligible'])
        self.assertIn('fasting_unknown',r['reasons'])
        with mock.patch.object(core,'profile_sex',return_value='female'):
            r=gc.compare(self.row('rs6258'),{'testosterone':self.marker(1)})
        self.assertFalse(r['applicable'])
        self.assertIn('sex_scope',r['reasons'])

    def test_three_horizons_are_independent(self):
        m=self.marker()
        m['series']=[self.marker(v,date=(date.today()-timedelta(days=d)).isoformat())['series'][0]
                     for d,v in [(340,2),(240,3),(140,5),(40,8)]]
        m.update(m['series'][-1])
        r=self.compare(marker=m)
        self.assertTrue(r['horizons'][0]['eligible'])
        self.assertFalse(r['horizons'][1]['eligible'])
        self.assertFalse(r['horizons'][2]['eligible'])

    def test_contrary_observations_remain_visible(self):
        m=self.marker(); m['series'].insert(0,self.marker(1,date=(date.today()-timedelta(days=40)).isoformat())['series'][0])
        r=self.compare(marker=m)
        self.assertEqual(r['contrary_observations'][0]['value'],1)
        self.assertIn('Observations in the other direction','\n'.join(gc.lines(r,True)))

    def test_english_and_russian_are_localized_and_facts_identical(self):
        outputs=[]
        for language in ('en','ru'):
            set_lang(language); r=self.compare(); outputs.append(r)
            text='\n'.join(gc.lines(r,True))
            self.assertNotIn('⟦',text)
            self.assertNotIn("{'en':",text)
            if language=='en':self.assertNotRegex(text,'[\u0410-\u044f]')
            else:self.assertIn('\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u0437\u043d\u0430\u043d\u0438\u044f \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d',text)
        self.assertEqual(outputs[0]['facts'],outputs[1]['facts'])
        self.assertEqual(outputs[0]['status'],outputs[1]['status'])
        self.assertNotEqual(outputs[0]['comparison'],outputs[1]['comparison'])

    def test_all_original_links_have_a_named_review_outcome(self):
        from scholion.engine import system_panels
        rows=gc.catalogue()['links']; indexed={(r['rsid'],s):r for r in rows for s in r['systems']}
        expected={(p['rsid'],s) for s,b in system_panels._curated()['systems'].items()
                  for p in b.get('positions',[]) if p.get('expect')}
        self.assertTrue(expected <= set(indexed))
        self.assertEqual(len(expected),31)
        for r in rows:
            self.assertIn(r['status'],('supported','hypothesis','excluded'))
            self.assertTrue(gc.sources(r['source']))
            self.assertTrue(r['limitations'])
            self.assertEqual(r['checked_on'],'2026-10-18')

    def test_shared_marker_produces_one_event_with_system_crosslinks(self):
        marker=self.marker(); items=[{'id':'lab:uric_acid','name':'Urate','events':[],
            'facts':[{'record':'labs.json','key':'uric_acid'}]}]
        with mock.patch('scholion.insight_context._panel_rows',return_value=[self.row()]), \
             mock.patch('scholion.insight_context._lifestyle_context',return_value=[]):
            prepared=prepare_context(items,{'markers':[marker]},{},[])
        self.assertEqual(len(items[0]['events']),1)
        self.assertEqual(set(prepared['systems']),{'renal','amino_acids'})
        a=prepared['systems']['renal']['comparisons'][0]
        b=prepared['systems']['amino_acids']['comparisons'][0]
        self.assertEqual(a,b)

    def test_patient_and_clinician_keep_facts_but_differ_in_density(self):
        r=self.compare()
        self.assertGreater(len(gc.lines(r,True)),len(gc.lines(r,False)))
        original=deepcopy(r)
        gc.lines(r,True)
        self.assertEqual(r,original)

    def test_genotype_reader_keeps_quality_flags(self):
        from scholion.engine.panel_genotype import _genotype
        call={'genotype':'GT','confidence':'called','depth':2,'filter':'LowQual','filtered':'LowQual',
              'source':'vcf','needs_confirmation':[{'what':'low_depth','value':2}]}
        with mock.patch.object(core,'profile_genotypes',return_value={}), \
             mock.patch('scholion.genome.lookup',return_value={'status':'ok','result':call}):
            g=_genotype('rs2231142','','ABCG2','T',{'status':'ok','local_only':True},('G','T'))
        self.assertEqual(g['needs_confirmation'],call['needs_confirmation'])
        self.assertEqual(g['filter'],'LowQual')

    def test_changed_catalogue_identity_cannot_inherit_old_source_support(self):
        for patch in ({'risk_allele':'G'}, {'hgvs':'NC_000004.12:g.1G>T'}):
            result=self.compare(self.row(**patch))
            self.assertFalse(result['eligible'])
            self.assertIn('catalogue_identity',result['reasons'])

    def test_hypothesis_and_excluded_link_have_no_directional_verdict(self):
        for rsid in ('rs429358','rs1800790','rs174546'):
            row=self.row(rsid);spec=next(r for r in gc.catalogue()['links'] if r['rsid']==rsid)
            result=gc.compare(row,{spec['marker']:self.marker()})
            self.assertEqual(result['relation'],'not_comparable')
            self.assertEqual(result['contrary_observations'],[])

    def test_fasting_is_an_explicit_fact_not_a_truthy_string(self):
        for fasting in (False,'false','unknown',None):
            result=gc.compare(self.row('rs1260326'),{'glucose':self.marker(1,fasting=fasting)})
            self.assertFalse(result['eligible'])
        result=gc.compare(self.row('rs1260326'),{'glucose':self.marker(1,fasting=True)})
        self.assertTrue(result['eligible'])

    def test_unconfirmed_recognition_cannot_form_a_trend(self):
        m=self.marker(proposed_rule=True)
        m['series']=[self.marker(v,date=(date.today()-timedelta(days=d)).isoformat())['series'][0]
                     for d,v in [(340,2),(240,3),(140,5),(40,8)]]
        result=self.compare(marker=m)
        self.assertFalse(any(h['eligible'] for h in result['horizons']))

    def test_unread_presumed_reference_is_not_displayed_as_a_called_genotype(self):
        row=self.row(read=False,presumed=True)
        row['genotype'].update(genotype='GG',confidence='assumed_ref')
        result=self.compare(row)
        self.assertIsNone(result['display_genotype'])
        self.assertEqual(result['facts']['genotype']['genotype'],'GG')
        self.assertNotIn('GG','\n'.join(gc.lines(result,True)))

    def test_multiple_markers_keep_stable_identity_and_legacy_projection(self):
        first=next(deepcopy(r) for r in gc.catalogue()['links'] if r['rsid']=='rs2231142')
        second={**first,'association_id':'synthetic:second','marker':'other'}
        row=self.row(); markers={'uric_acid':self.marker(), 'other':self.marker(1)}
        with mock.patch.object(gc,'catalogue',return_value={'links':[first,second]}):
            items=gc.compare_all(row,markers,'renal')
            self.assertEqual(len(items),2)
            self.assertEqual(gc.compare(row,markers),items[0])
            self.assertEqual(len(gc.system_comparisons([row,row],markers,'renal')),2)
            self.assertEqual(len(_genetic_context(row,markers)['comparisons']),2)
            ids={r['association_id'] for r in items}
        with mock.patch.object(gc,'catalogue',return_value={'links':[second,first]}):
            self.assertEqual({r['association_id'] for r in gc.compare_all(row,markers)},ids)

    def test_specimen_is_recorded_for_the_point_not_borrowed_or_guessed(self):
        spec=next(deepcopy(r) for r in gc.catalogue()['links'] if r['rsid']=='rs2231142')
        spec.update(specimens=['plasma'],units=['mg/dL'],methods=['synthetic'])
        with mock.patch.object(gc,'catalogue',return_value={'links':[spec]}):
            for material,reason in [(None,'specimen_unknown'),('urine','specimen_scope'),('blood','specimen_scope')]:
                marker=self.marker(specimen=material,method='synthetic')
                marker['specimen']='plasma'
                r=self.compare(marker=marker)
                self.assertFalse(r['eligible'])
                self.assertIn(reason,r['reasons'])
            marker=self.marker(specimen='plasma',method='synthetic',sample_id='synthetic-draw')
            self.assertTrue(self.compare(marker=marker)['eligible'])
            self.assertEqual(self.compare(marker=marker)['facts']['laboratory']['sample_id'],'synthetic-draw')
            for patch,reason in [({'method':None},'method_scope'),({'unit':'other'},'unit_scope')]:
                r=self.compare(marker=self.marker(specimen='plasma',method='synthetic',**patch)) if 'method' not in patch else self.compare(marker=self.marker(specimen='plasma',**patch))
                self.assertFalse(r['eligible']);self.assertIn(reason,r['reasons'])
            self.assertEqual(gc.collection_reasons(spec,{'point':{'specimen':'плазма','unit':'mg/dL','method':'synthetic'}}),[])

    def test_second_link_creates_its_own_event_without_duplicate_memberships(self):
        first=next(deepcopy(r) for r in gc.catalogue()['links'] if r['rsid']=='rs2231142')
        second={**first,'association_id':'synthetic:second','marker':'valine','systems':['amino_acids']}
        rows=[self.row()]
        items=[{'id':'lab:'+key,'name':key,'events':[], 'facts':[{'record':'labs.json','key':key}]}
               for key in ('uric_acid','valine')]
        with mock.patch.object(gc,'catalogue',return_value={'links':[first,second]}), \
             mock.patch('scholion.insight_context._panel_rows',return_value=rows), \
             mock.patch('scholion.insight_context._lifestyle_context',return_value=[]):
            prepared=prepare_context(items,{'markers':[self.marker(),self.marker(key='valine')]},{},[])
        self.assertEqual([len(i['events']) for i in items],[1,1])
        self.assertEqual(len(prepared['systems']['amino_acids']['comparisons']),2)

    def test_printed_specimen_survives_storage_and_analysis(self):
        from scholion import ingest_labs, store
        from scholion.engine.labs import analyze_labs
        from tempfile import TemporaryDirectory
        from pathlib import Path
        for header,material in [('Specimen: Serum','serum'),('Биоматериал: плазма крови','plasma'),
                                ('Specimen: Whole blood','whole_blood'),('Specimen: blood',None),
                                ('Specimen: serum or plasma',None),('Serum iron',None)]:
            self.assertEqual(ingest_labs._result_specimen(header),material)
        self.assertIsNone(ingest_labs._result_specimen('Specimen: Serum\nSpecimen: urine'))
        text='Collected: '+date.today().isoformat()+'\nSpecimen: Serum\nGlucose 5.2 mmol/L 3.9 - 6.1'
        day,values=ingest_labs.parse_report(text,core.lab_markers()['markers'])
        self.assertEqual(values['glucose']['specimen'],'serum')
        with TemporaryDirectory() as tmp:
            restore=support.pin_profile(Path(tmp).resolve());core.reset_cache()
            try:
                result=store.add_lab_point('glucose',day,5.2,unit='mmol/L',ref_low=3.9,ref_high=6.1,
                                          date_source='form',reference_context=values['glucose'])
                self.assertTrue(result['ok'])
                marker=analyze_labs(['glucose'])['markers'][0]
                self.assertEqual(gc.observation(marker)['point']['specimen'],'serum')
                result=store.add_lab_point('glucose',day,5.3,unit='mmol/L',date_source='form')
                self.assertTrue(result['ok']);core.reset_cache()
                self.assertIsNone(gc.observation(analyze_labs(['glucose'])['markers'][0])['point']['specimen'])
            finally: restore();core.reset_cache()

    def test_new_passports_have_independent_levels_and_strict_endpoints(self):
        added=[s for s in gc.catalogue()['links'] if s.get('independent_claim')]
        self.assertEqual(len(added),11)
        self.assertEqual(sum(s['status']=='supported' for s in added),10)
        for spec in added:
            row=self.row(spec['rsid']); row['genotype']['assembly']='GRCh38'
            row['level']='C' if spec['gene']=='TMPRSS6' else 'B'
            point=self.marker(8,key=spec['marker'],unit=spec['units'][0],specimen=spec['specimens'][0],
                              method=(spec.get('methods') or ['reported'])[0],fasting=True)
            actual=next(r for r in gc.compare_all(row,{spec['marker']:point}) if r['association_id']==spec['association_id'])
            self.assertEqual(actual['eligible'],spec['status']=='supported',spec['association_id'])
            self.assertEqual(actual['variant_level'],row['level'])
            self.assertEqual(actual['association_level'],spec['association_level'])
            row['genotype'].pop('assembly')
            missing=next(r for r in gc.compare_all(row,{spec['marker']:point}) if r['association_id']==spec['association_id'])
            self.assertFalse(missing['eligible']);self.assertIn('assembly_unknown',missing['reasons'])
        self.assertEqual(len({s['association_id'] for s in gc.catalogue()['links']}),len(gc.catalogue()['links']))

    def test_cross_system_adapter_reads_only_explicitly_linked_positions(self):
        from scholion.engine import system_panels, panel_form
        row=self.row('rs58542926');row['genotype']['assembly']='GRCh38'
        calls=[]
        def curated(key,spec,markers,scan,by_key,**kw):
            calls.extend(p['rsid'] for p in spec['positions'])
            return {'rows':[row] if any(p['rsid']==row['rsid'] for p in spec['positions']) else []}
        with mock.patch.object(system_panels,'_curated_rows',side_effect=curated), \
             mock.patch.object(panel_form,'scan_for',return_value={'status':'no_genome'}):
            result=gc.system_comparisons([],{},'lipids')
        self.assertEqual({r['marker'] for r in result if r['gene']=='TM6SF2'},{'ldl','triglycerides'})
        self.assertNotIn('rs715',calls)
        self.assertTrue(all(r['reference_system']=='liver' for r in result if r['gene']=='TM6SF2'))
