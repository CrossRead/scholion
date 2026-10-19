"""Mechanistic hypotheses retain molecular, collection and evidence boundaries."""
from copy import deepcopy
from datetime import date
from unittest import TestCase, mock

import support  # noqa: F401
from scholion import core, genetic_patterns as gp, genetic_comparison as gc
from scholion.i18n import set_lang
from scholion.panel_reference import gene_reference_context, reference_lines


class GeneticPatternTests(TestCase):
    def tearDown(self):
        set_lang(None)

    def spec(self, kind):
        return deepcopy(next(p for p in gp.catalogue() if p['kind'] == kind))

    def rows(self, spec):
        return [{**v, 'read':True, 'state':'het', 'level':'B', 'carrier':True,
                 'genotype':{'genotype':'CT','confidence':'called','depth':30,
                             'source':'synthetic VCF','filter':'PASS','assembly':'GRCh38'}}
                for v in spec['variants']]

    def labs(self, spec):
        result={}
        for key in spec['markers']:
            endpoint=spec.get('endpoint', {}).get(key, {})
            point={'date':date.today().isoformat(),'value':4,'unit':next(iter(endpoint.get('units',[])), 'unit'),
                   'specimen':next(iter(endpoint.get('specimens',[])), 'serum'),
                   'method':next(iter(endpoint.get('methods',[])), 'reported'),
                   'ref_low':1,'ref_high':3,'form_id':'synthetic-form','draw_id':'synthetic-draw','source':'synthetic form'}
            result[key]={'key':key, 'name':key, **point, 'series':[point]}
        return result

    def run_pattern(self, spec, rows=None, labs=None):
        with mock.patch.object(gp,'catalogue',return_value=[spec]):
            return gp.comparisons(self.rows(spec) if rows is None else rows,
                                  self.labs(spec) if labs is None else labs,spec['systems'][0])

    def test_composite_does_not_turn_phase_ambiguity_into_a_diplotype(self):
        spec=self.spec('apoe'); rows=self.rows(spec)
        result=self.run_pattern(spec,rows)[0]
        self.assertEqual(result['facts']['diplotype']['status'],'ambiguous_without_phase')
        self.assertFalse(result['eligible'])
        self.assertIn('diplotype_unconfirmed',result['reasons'])
        rows[0]['genotype']['genotype']='TT'
        rows[0]['state']='absent'
        result=self.run_pattern(spec,rows)[0]
        self.assertEqual(result['display_genotype'],'ε2/ε3')
        self.assertTrue(result['eligible'])
        self.assertEqual(result['expected_direction'],'lower')
        self.assertFalse(result['causal'])
        rows[1]['genotype']['depth']=1
        self.assertFalse(self.run_pattern(spec,rows)[0]['eligible'])

    def test_iron_requires_two_alleles_same_collection_and_context(self):
        spec=self.spec('iron'); rows=self.rows(spec); labs=self.labs(spec)
        with mock.patch.object(core,'profile_sex',return_value='male'):
            self.assertIn('genotype_scope',self.run_pattern(spec,rows,labs)[0]['reasons'])
            rows[0]['state']='hom'
            result=self.run_pattern(spec,rows,labs)[0]
            self.assertEqual(result['status'],'compatible_pattern')
            self.assertFalse(result['eligible'])
            self.assertTrue(result['qualified_context'])
            self.assertIsNone(result['question'])
            labs[spec['markers'][0]]['series'][0]['sample_id']='a'
            labs[spec['markers'][1]]['series'][0]['sample_id']='b'
            result=self.run_pattern(spec,rows,labs)[0]
            self.assertFalse(result['qualified_context'])
            self.assertIn('draw_identity',result['reasons'])

    def test_collection_date_or_document_cannot_override_contradicting_ids(self):
        same={'date':'2026-10-01','form_id':'one'}
        self.assertFalse(gp.same_draw([{'point':same},{'point':same}]))
        self.assertTrue(gp.same_draw([{'point':{**same,'draw_id':'one'}},{'point':{**same,'draw_id':'one'}}]))
        self.assertFalse(gp.same_draw([{'point':{**same,'sample_id':'one'}},
                                      {'point':{**same,'sample_id':'two'}}]))
        self.assertFalse(gp.same_draw([{'point':{'date':'2026-10-01'}},
                                      {'point':{'date':'2026-10-01'}}]))

    def test_ratio_has_no_diagnostic_range_or_radar_flag(self):
        spec=self.spec('ratio'); labs=self.labs(spec)
        labs[spec['markers'][1]]['series'][0]['value']=2
        result=self.run_pattern(spec,labs=labs)[0]
        self.assertEqual(result['derived']['value'],2)
        self.assertIsNone(result['derived']['reference'])
        self.assertIsNone(result['derived']['abnormal'])
        self.assertFalse(result['eligible'])
        labs[spec['markers'][0]]['series'][0]['specimen']='urine'
        self.assertNotIn('derived',self.run_pattern(spec,labs=labs)[0])

    def test_normal_hba1c_can_still_have_a_bias_context_without_correction(self):
        spec=self.spec('bias'); labs=self.labs(spec)
        labs['hba1c']['series'][0]['ref_high']=8
        with mock.patch.object(core,'profile_sex',return_value='male'):
            result=self.run_pattern(spec,labs=labs)[0]
            self.assertEqual(result['status'],'bias_possible')
            self.assertEqual(result['observations'][0]['position'],'within')
            self.assertNotIn('derived',result)
            self.assertFalse(result['eligible'])
            labs['hba1c']['series'][0]['method']=None
            self.assertFalse(self.run_pattern(spec,labs=labs)[0]['qualified_context'])

    def test_gene_membership_and_common_snp_never_create_a_monogenic_finding(self):
        spec=next(p for p in gp.catalogue() if p['association_id']=='pattern:nitrogen_disposal')
        common={'gene':'CPS1','rsid':'rs715','state':'hom','read':True,'carrier':True}
        self.assertEqual(self.run_pattern(spec,[common],{}),[])
        empty={'gene':'CPS1','read':True,'findings':0,'carrier':False}
        self.assertEqual(self.run_pattern(spec,[empty],{}),[])
        hit={**empty,'variant_records':[{'clnsig':'Pathogenic','zygosity':'het'}],
             'assertions':[{'disease':'Synthetic condition','moi_code':'AR','classification':'Definitive'}]}
        result=self.run_pattern(spec,[hit],{})[0]
        self.assertFalse(result['eligible'])
        self.assertFalse(result['qualified_context'])
        self.assertEqual(result['level_scope'],'mechanism_reference_not_personal_variant')
        self.assertEqual(result['facts']['gencc_assertions'],hit['assertions'])

    def test_reference_hypotheses_exist_without_personal_data_and_are_translated(self):
        for language, phrase in [('en','urea'),('ru','мочевины')]:
            set_lang(language)
            context=gene_reference_context('CPS1',[])
            self.assertTrue(context['mechanistic_hypotheses'])
            text='\n'.join(reference_lines({'reference_context':context}))
            self.assertIn(phrase,text)
            self.assertIn('https://',text)

    def test_pattern_ids_markers_sources_and_localization_are_complete(self):
        markers=core._read_knowledge('lab_markers.json')['markers']
        ids=[]
        for p in gp.catalogue():
            ids.append(p['association_id'])
            self.assertTrue(set(p['markers']) <= set(markers),p['association_id'])
            self.assertTrue(p['source'].startswith('https://'))
            self.assertIsInstance(p['summary'],str)
            self.assertIn(p['association_level'],'ABCDE')
        self.assertEqual(len(ids),len(set(ids)))

    def test_clinician_projection_keeps_all_measurements_and_source(self):
        spec=self.spec('ratio');result=self.run_pattern(spec)[0]
        text='\n'.join(gc.lines(result,True))
        self.assertTrue(all(key in text for key in spec['markers']))
        self.assertIn('Observed ratio',text)
        self.assertIn('synthetic form',text)

    def test_ended_treatment_cannot_create_a_current_drug_context(self):
        spec=self.spec('drug_context')
        with mock.patch.object(core,'active_medications',return_value=[]):
            self.assertEqual(self.run_pattern(spec),[])
        with mock.patch.object(core,'active_medications',return_value=[{'name':'synthetic thiopurine'}]), \
             mock.patch.object(core,'classify_drug',return_value=['thiopurine']), \
             mock.patch('scholion.engine.pgx.compute_phenotype',return_value={'certainty':'assumed','basis':{}}):
            result=self.run_pattern(spec)[0]
            self.assertFalse(result['eligible'])
            self.assertIn('diplotype_unconfirmed',result['reasons'])

    def test_excluded_variant_stays_excluded_even_with_high_labs(self):
        result=self.run_pattern(self.spec('excluded'))[0]
        self.assertEqual(result['status'],'excluded')
        self.assertFalse(result['eligible'])

    def test_ratio_uses_exact_measurements_without_inventing_a_reference(self):
        spec=self.spec('ratio'); labs=self.labs(spec)
        for m in labs.values():
            m['series'][0].update(ref_low=None,ref_high=None)
        result=self.run_pattern(spec,labs=labs)[0]
        self.assertTrue(result['qualified_context'])
        self.assertIsNone(result['derived']['reference'])
        labs[spec['markers'][0]]['series'][0]['censored']='<'
        self.assertNotIn('derived',self.run_pattern(spec,labs=labs)[0])

    def test_unresolved_allele_orientation_stays_reference_only(self):
        pending=[p for p in gp.catalogue() if p.get('reference_only')]
        self.assertEqual({p['genes'][0] for p in pending},{'PTPN22','COL1A1','PADI4','PEMT','AOC1'})
        for spec in pending:
            self.assertEqual(self.run_pattern(spec),[])
            self.assertTrue(gp.reference_patterns(spec['genes'][0],spec['variants'][0]['rsid']))

    def test_collection_checks_every_identity_before_accepting_a_match(self):
        common={'date':'2026-10-18','sample_id':'one'}
        self.assertFalse(gp.same_draw([{'point':{**common,'draw_id':'a'}},
                                      {'point':{**common,'draw_id':'b'}}]))
        self.assertFalse(gp.same_draw([]))
        self.assertFalse(gp.same_draw([{'point':{}}]))
        self.assertFalse(gp.same_draw([{'point':common}, {'point':{**common,'date':'2026-10-17'}}]))

    def test_patient_cli_uses_the_same_composites_without_duplicate_legacy_pairs(self):
        from scholion.insight_context import context_lines
        spec=self.spec('ratio'); result=self.run_pattern(spec)[0]
        context={'comparisons':[result], 'genetics':[
            {'genetic_lab_comparison':result, 'comparisons':[result]}]}
        for clinician in (False, True):
            text='\n'.join(context_lines({'context':context},clinician))
            self.assertEqual(text.count(result['summary']),1)
            self.assertIn('DIO1',text)
        result['status']='excluded'
        self.assertNotIn(result['summary'],'\n'.join(context_lines({'context':context})))

    def test_actual_thiopurine_names_reach_the_context(self):
        spec=self.spec('drug_context')
        for name in ('azathioprine','mercaptopurine','thioguanine'):
            self.assertIn('thiopurine',core.classify_drug(name))
            with mock.patch.object(core,'active_medications',return_value=[{'name':name}]), \
                 mock.patch('scholion.engine.pgx.compute_phenotype',return_value={'certainty':'called','basis':{'source':'synthetic'}}):
                result=self.run_pattern(spec)[0]
                self.assertIn('treatment_not_causal',result['reasons'])
                self.assertNotIn('diplotype_unconfirmed',result['reasons'])
                self.assertFalse(result['eligible'])

    def test_missing_inputs_never_supply_a_ratio_or_qualified_context(self):
        spec=self.spec('ratio')
        self.assertFalse(self.run_pattern(spec,labs={})[0]['qualified_context'])
        labs=self.labs(spec);labs[spec['markers'][1]]['series'][0]['value']=0
        result=self.run_pattern(spec,labs=labs)[0]
        self.assertNotIn('derived',result)
        self.assertIn('not_comparable',result['reasons'])
        rows=self.rows(spec);rows[0]['genotype'].pop('assembly')
        self.assertIn('assembly_unknown',self.run_pattern(spec,rows)[0]['reasons'])
        rows[0]['risk_allele']='unverified'
        self.assertIn('catalogue_identity',self.run_pattern(spec,rows)[0]['reasons'])
        rows[0]['state']='absent'
        self.assertEqual(self.run_pattern(spec,rows),[])

    def test_apoe_reference_and_mixed_diplotypes_are_not_a_direction_shortcut(self):
        spec=self.spec('apoe');rows=self.rows(spec)
        rows[0]['genotype']['genotype']='TT';rows[1]['genotype']['genotype']='CC'
        self.assertIn('diplotype_context_only',self.run_pattern(spec,rows)[0]['reasons'])
        mixed=self.spec('apoe_mixed')
        self.assertEqual(self.run_pattern(mixed,rows),[])
        rows[1]['genotype']['genotype']='TT'
        result=self.run_pattern(mixed,rows)[0]
        self.assertFalse(result['eligible'])
        self.assertIn('clinical_context_required',result['reasons'])

    def test_on_demand_reference_context_does_not_become_a_personal_comparison(self):
        from scholion.engine import system_panels
        from scholion.format_system import system_report
        key='folate_histamine_redox_choline'
        spec=next(p for p in gp.catalogue() if p['association_id']=='pattern:pemt_restricted_diet_context')
        with mock.patch.object(system_panels,'_genotype',return_value={
                'state':'het','read':True,'genotype':'CT','confidence':'called','depth':30,'assembly':'GRCh38'}):
            for register in ('patient','clinician'):
                card=system_panels.system(key,register)
                self.assertEqual(card['genetic_lab_comparisons'],[])
                self.assertNotIn('score',card['labs'])
                self.assertIn(spec['summary'],system_report(card))

    def test_low_quality_composite_keeps_a_carried_second_site_visible(self):
        spec=self.spec('apoe');rows=self.rows(spec)
        rows[0]['state']='absent';rows[0]['genotype']['genotype']='TT'
        rows[1]['genotype']['depth']=2
        result=self.run_pattern(spec,rows)[0]
        self.assertFalse(result['eligible'])
        self.assertEqual(result['state'],'het')
        self.assertTrue(gc.visible(result))
        self.assertIn('APOE','\n'.join(gc.lines(result)))

    def test_clinician_text_retains_the_actual_variant_and_gencc_assertion(self):
        spec=next(p for p in gp.catalogue() if p['association_id']=='pattern:nitrogen_disposal')
        row={'gene':'CPS1','read':True,'variant_records':[{
            'chrom':'1','pos':7,'ref':'A','alt':'G','zygosity':'het','clnsig':'Pathogenic'}],
            'assertions':[{'disease':'Synthetic condition','moi_code':'AR','classification':'Definitive'}]}
        result=self.run_pattern(spec,[row],{})[0]
        text='\n'.join(gc.lines(result,True))
        self.assertIn('1:7 A>G',text)
        self.assertIn('GenCC: Synthetic condition · Definitive · AR',text)
        self.assertIn('Mechanism evidence; not the personal variant classification',text)
        self.assertFalse(result['eligible'])

    def test_apoe_event_carries_both_loci_and_the_diplotype(self):
        from scholion.insight_context import prepare_context
        spec=self.spec('apoe');rows=self.rows(spec);labs=self.labs(spec)
        rows[0]['genotype']['genotype']='TT';rows[0]['state']='absent'
        labs['ldl']['series'][0]['value']=0.5
        items=[{'id':'lab:ldl','name':'LDL','events':[],
                'facts':[{'record':'labs.json','key':'ldl'}]}]
        with mock.patch('scholion.insight_context._panel_rows',return_value=rows), \
             mock.patch('scholion.reported_response.events',return_value=[]):
            prepare_context(items,{'markers':list(labs.values())},{},[])
        event=next(e for e in items[0]['events'] if e['kind']=='genetic_phenotype')
        fact=next(f for f in event['facts'] if f['record']=='genotype')
        self.assertEqual(fact['rsid'],'rs429358 / rs7412')
        self.assertEqual(fact['genotype'],'ε2/ε3')
        self.assertEqual(len(fact['variants']),2)
        self.assertEqual(fact['diplotype']['status'],'ok')
        self.assertEqual(event['id'],'genetic_phenotype:'+spec['association_id'])

    def test_result_units_cannot_be_borrowed_from_another_marker_definition(self):
        marker={'unit':'mg/dL','date':date.today().isoformat(),'series':[{'date':date.today().isoformat(),'value':4,
                'unit':'mmol/L','ref_low':1,'ref_high':3}]}
        self.assertIn('unit_conflict',gc.observation(marker)['reasons'])
