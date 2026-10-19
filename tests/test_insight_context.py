"""A personal association requires a real allele and a supported marker link."""
from datetime import date, timedelta
from importlib import import_module
from unittest import TestCase, mock

import support  # noqa: F401
from scholion.insight_context import _genetic_context, _lifestyle_context, prepare_context, attach_context
from scholion.engine.insights import attention_feed


class ContextTests(TestCase):
    def row(self):
        return {'risk_allele':'T','hgvs':'NC_000004.12:g.88131171G>T','gene':'ABCG2', 'rsid':'rs2231142', 'level':'B', 'mode':'common_variant',
                'state':'het', 'read':True, 'carrier':True, 'genotype':{'genotype':'GT','confidence':'called','depth':30},
                'interpretation':{'summary':'Recorded association', 'source':'PMID:19506252'},
                'decision_route':{'ready':True,'kind':'decision_now'},
                'expect_check':{'marker':'uric_acid','direction':'higher'},
                'subclaim_basis':{'expect':{'source':'PMID:19506252','mechanism':'Urate transport', 'status':'complete'}}}

    def labs(self, value=8):
        point={'date':date.today().isoformat(),'value':value,'unit':'mg/dL','ref_low':2,'ref_high':6}
        return {'uric_acid':{'key':'uric_acid','name':'Urate',**point, 'series':[point]}}

    def test_single_measurement_can_match_without_a_trend(self):
        result=_genetic_context(self.row(),self.labs())
        self.assertEqual(result['status'],'concordant')
        self.assertEqual(result['observation']['value'],8)
        self.assertFalse(result['causal'])

    def test_normal_does_not_refute_predisposition_or_prompt_more_labs(self):
        result=_genetic_context(self.row(),self.labs(4))
        self.assertEqual(result['status'],'within')
        self.assertNotIn('recommendation', result)

    def test_opposite_direction_is_not_explained_by_the_variant(self):
        self.assertEqual(_genetic_context(self.row(),self.labs(1))['status'],'different_direction')

    def test_no_inference_from_missing_or_unconfirmed_reading(self):
        for patch in ({'read':False},{'carrier':False},{'presumed':True},{'needs_confirmation':True}):
            self.assertIsNone(_genetic_context({**self.row(),**patch},self.labs()))

    def test_weak_evidence_and_unsupported_link_remain_context(self):
        for patch in ({'level':'C'}, {'mode':'monogenic'}):
            self.assertEqual(_genetic_context({**self.row(),**patch},self.labs())['status'],'context_only')

    def test_stale_censored_future_or_proposed_result_cannot_confirm(self):
        for patch in ({'date':'2000-01-01'}, {'date':(date.today()+timedelta(days=1)).isoformat()},
                      {'censored':'<'}, {'proposed':True}, {'reference_withheld':True}):
            labs=self.labs(); labs['uric_acid'].update(patch);labs['uric_acid']['series'][0].update(patch)
            self.assertEqual(_genetic_context(self.row(),labs)['status'],'context_only',patch)

    def test_actual_panel_gates_are_used(self):
        from scholion.engine import system_panels
        with mock.patch.object(system_panels,'_genotype',return_value={
            'state':'het','read':True,'genotype':'GT','confidence':'called','depth':30}), \
             mock.patch.object(system_panels.panel_form,'gene_row',side_effect=lambda gene,row,scan:row):
            spec=system_panels._curated()['systems']['renal']
            curated=system_panels._curated_rows('renal',spec,system_panels._domain('renal')['markers'],
                {'status':'not_ready'},self.labs())
        row=next(r for r in curated['rows'] if r['rsid']=='rs2231142')
        self.assertEqual(_genetic_context(row,self.labs())['status'],'concordant')
        # The reviewed association has its own support; it grants no clinical finding.
        row['decision_route']['ready']=False
        self.assertEqual(_genetic_context(row,self.labs())['status'],'concordant')

    def test_one_abnormal_reading_plus_association_becomes_system_insight(self):
        with mock.patch('scholion.insight_context._panel_rows',return_value=[self.row()]), \
             mock.patch('scholion.engine.goals.goal_dashboard',return_value={}), \
             mock.patch('scholion.core.medications_json',return_value={}), \
             mock.patch('scholion.core.focus_log',return_value={}), \
             mock.patch('scholion.engine.insight_links.linked_pgs_events',return_value=[]):
            labs=self.labs();labs['uric_acid'].update(flag='high',abnormal=True)
            feed=attention_feed({'markers':list(labs.values())},[],[],{},[])
        group=next(g for g in feed['highlights'] if g.get('system')=='renal')
        self.assertIn('context_summary',group)
        self.assertNotIn('trajectory',group)
        self.assertTrue(any(e['kind']=='genetic_phenotype' for e in group['events']))
        self.assertEqual(len(group['questions']),1)
        from scholion.format_insights import attention_report
        self.assertIn(group['context_summary'],attention_report(feed))

    def test_lifestyle_keeps_origin_and_does_not_invent_a_diet(self):
        metric={'key':'SleepHours','value':7,'label':'Sleep','unit':'hours','date':date.today().isoformat()[:7],
                'source':'synthetic','counts_toward_conclusions':True,'comparison':{'eligible':False}}
        with mock.patch('scholion.reported_response.events',return_value=[]):
            rows=_lifestyle_context([],{'metrics':[metric]},'renal')
            self.assertEqual(rows[0]['source'],'synthetic')
            self.assertIsNone(rows[0]['comparison'])
            self.assertFalse(rows[0]['causal'])
            self.assertEqual(len(rows),1)
            self.assertEqual(_lifestyle_context([],{'metrics':[{**metric,'counts_toward_conclusions':False}]},'renal'),[])

    def test_urgent_event_is_enriched_without_losing_priority(self):
        labs=self.labs();items=[{'id':'lab:uric_acid','name':'Urate','priority':0,'events':[],
            'facts':[{'record':'labs.json','key':'uric_acid'}]}]
        with mock.patch('scholion.insight_context._panel_rows',return_value=[self.row()]), \
             mock.patch('scholion.reported_response.events',return_value=[]):
            contexts=prepare_context(items,{'markers':list(labs.values())},{},[])
        attach_context(items,contexts)
        self.assertEqual(items[0]['priority'],0)
        self.assertIn('context_summary',items[0])

    def test_context_lookup_never_resolves_an_identifier_on_the_network(self):
        from scholion import genome
        from scholion.engine.panel_genotype import _genotype
        with mock.patch.object(genome, 'lookup', return_value={'status':'no_genome'}) as lookup, \
             mock.patch('scholion.core.profile_genotypes',return_value={}):
            _genotype('rs2231142','','ABCG2','T',{'status':'ok','local_only':True})
        lookup.assert_called_once_with('rs2231142',allow_network=False)
        with mock.patch.object(genome,'available',return_value={'ready':False}), \
             mock.patch.object(genome,'resolve_rsid',return_value=None) as resolve:
            genome.lookup('rs999',allow_network=False)
        resolve.assert_called_once_with('rs999',allow_network=False)

    def test_every_sourced_context_link_is_for_a_marker_in_its_system(self):
        from scholion.engine import system_panels
        found=[]
        for system,spec in system_panels._curated()['systems'].items():
            for row in spec.get('positions') or []:
                exp=row.get('expect') or {}
                if exp.get('context_only'):
                    self.assertIn(exp['marker'],system_panels._domain(system)['markers'])
                    self.assertTrue(exp['source'])
                    self.assertTrue(exp['mechanism'])
                    found.append((system,row['rsid']))
        self.assertIn(('renal','rs2231142'),found)
        self.assertIn(('amino_acids','rs2231142'),found)

    def test_recent_note_is_used_only_with_its_explicit_marker_and_review(self):
        from scholion.insight_context import _recorded_notes
        block={'id':'nutrition','body':'Recorded dietary change','reviewed':date.today().isoformat(),
               'watch':[{'kind':'lab','key':'uric_acid'}]}
        with mock.patch('scholion.core.lifestyle_brief_src',return_value={'blocks':[block]}), \
             mock.patch.object(import_module('scholion.engine.lifestyle'), '_brief_newest',return_value=None):
            self.assertEqual(_recorded_notes('renal')[0]['note'],block['body'])
            self.assertEqual(_recorded_notes('thyroid'),[])
            block['reviewed']='2000-01-01'
            self.assertEqual(_recorded_notes('renal'),[])
        block['reviewed']=(date.today()-timedelta(days=2)).isoformat()
        with mock.patch('scholion.core.lifestyle_brief_src',return_value={'blocks':[block]}), \
             mock.patch.object(import_module('scholion.engine.lifestyle'), '_brief_newest',return_value=date.today().isoformat()):
            self.assertEqual(_recorded_notes('renal'),[])

    def test_coexisting_change_requires_temporal_overlap_and_does_not_share_mutation(self):
        row={'key':'SleepHours','label':'Sleep','unit':'h', 'comparison':{
            'before':{'date':'2026-03','value':6},'after':{'date':'2026-04','value':7}}}
        context={'genetics':[], 'lifestyle':[row]}
        groups=[{'name':'Renal','system':'renal','facts':[{'record':'labs.json','date':d} for d in dates]}
                for dates in [('2026-01-01','2026-05-01'),('2026-06-01','2026-07-01')]]
        attach_context(groups,{'membership':{},'systems':{'renal':context}})
        self.assertTrue(groups[0]['context_lifestyle_summary'])
        self.assertFalse(groups[1]['context_lifestyle_summary'])
        self.assertEqual(len(groups[0]['context']['coexisting_changes']),1)
        self.assertNotIn('coexisting_changes',context)

    def test_drug_matching_cache_does_not_survive_the_reading(self):
        from scholion import core
        with mock.patch.object(core,'med_classes',return_value={'classes':{'a':{'names':['Synthetic']}}}) as book:
            with core.reading_session():
                first=core.classify_drug('Synthetic')
                first.append('mutation')
                self.assertEqual(core.classify_drug('Synthetic'),['a'])
            self.assertEqual(book.call_count,1)
            self.assertEqual(core.classify_drug('Synthetic'),['a'])
            self.assertEqual(book.call_count,2)

    def test_manual_and_device_weight_are_one_context_quantity(self):
        phenotype=[{'label':'Weight','components':[{'ref':'metric:weight','value':81,'unit':'kg',
            'date':date.today().isoformat(),'source':'recorded'}]}]
        wearable={'metrics':[{'key':'Weight','label':'Weight','value':83,'unit':'kg',
            'date':date.today().isoformat()[:7],'source':'synthetic','counts_toward_conclusions':True}]}
        with mock.patch('scholion.reported_response.events',return_value=[]), \
             mock.patch('scholion.core.lifestyle_brief_src',return_value={}):
            rows=_lifestyle_context(phenotype,wearable,'renal')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['value'],81)
        self.assertNotEqual(rows[0]['label'],'weight')
        self.assertNotEqual(rows[0]['source_label'],'recorded')

    def test_context_only_marker_does_not_request_missing_test(self):
        from scholion.engine.system_panels import _questions
        gen={'rows':[{'risk_allele':'T','hgvs':'NC_000004.12:g.88131171G>T','gene':'ABCG2','rsid':'rs2231142','expect_check':{
            'marker':'uric_acid','gap':True,'context_only':True}}]}
        answer=_questions(gen,{}, {}, {})
        self.assertFalse(any(r.get('origin') in ('expect','expect_gap') for r in answer.get('rows') or []))

    def test_unregistered_variant_keeps_reference_and_reading_details_in_both_modes(self):
        from scholion.insight_context import context_lines
        from scholion import i18n
        row = {**self.row(), 'rsid': 'rs999999999', 'depth_note': 'Synthetic depth: 30'}
        context = _genetic_context(row, self.labs())
        self.assertEqual(context['status'], 'context_only')
        self.assertNotIn('genetic_lab_comparison', context)
        context['comparison'] = 'No marker association established'
        item = {'context': {'genetics': [context]}}
        for language in ('en', 'ru'):
            with mock.patch.object(i18n._state, "current", language, create=True):
                for clinician in (False, True):
                    text = '\n'.join(context_lines(item, clinician))
                    for expected in ('rs999999999', 'GT', 'Scholion B', 'Recorded association',
                                     'Synthetic depth: 30', 'PMID:19506252',
                                     'No marker association established'):
                        self.assertIn(expected, text)

    def test_function_only_context_does_not_promote_low_evidence_or_invent_text(self):
        row = {**self.row(), 'rsid': 'rs999999999', 'level': 'E',
               'reference_context': {'gene_function': 'Synthetic transport function',
                                     'gene_source': 'Synthetic source'}}
        context = _genetic_context(row, self.labs())
        self.assertEqual(context['level'], 'E')
        self.assertEqual(context['summary'], 'Synthetic transport function')
        self.assertEqual(context['status'], 'context_only')
        row['reference_context'] = {}
        self.assertIsNone(_genetic_context(row, self.labs()))

    def test_recorded_note_is_printed_but_patient_response_is_not_duplicated(self):
        from scholion.insight_context import context_lines
        item = {'context': {'lifestyle': [
            {'scope': 'recorded_note', 'date': date.today().isoformat(), 'note': 'Synthetic dietary note'},
            {'scope': 'patient_report', 'note': 'Response already printed as an event'},
            {'key': 'SleepHours', 'value': 7, 'unit': 'h', 'date': date.today().isoformat(),
             'source': 'Synthetic device'}]}}
        text = '\n'.join(context_lines(item, True))
        self.assertIn('Synthetic dietary note', text)
        self.assertIn('Synthetic device', text)
        self.assertNotIn('Response already printed as an event', text)

    def test_clinician_sees_comparison_quality_once_when_it_is_also_genetic_context(self):
        from scholion.insight_context import context_lines
        context = _genetic_context(self.row(), self.labs())
        comparison = context['genetic_lab_comparison']
        item = {'context': {'genetics': [context], 'comparisons': [comparison]}}
        clinician = '\n'.join(context_lines(item, True))
        patient = '\n'.join(context_lines(item, False))
        self.assertEqual(clinician.count('DP 30'), 1)
        self.assertIn(comparison['source'], clinician)
        self.assertIn(comparison['comparison'], patient)
        self.assertNotIn('DP 30', patient)
