"""A short visit uses an explicit focus, not a complete catalogue export."""
from __future__ import annotations

import gene_card_support

import importlib
import json
import shutil
import subprocess
from pathlib import Path
from unittest import mock

from scholion import core, engine, i18n, format as fmt, visit_focus
from tests.test_ingest_reads_a_table import TableCase

_LIFESTYLE = importlib.import_module("scholion.engine.lifestyle")


class FocusedVisit(TableCase):
    def setUp(self):
        super().setUp()
        self.topic = {'id': 'panel:lipids', 'system': 'lipids', 'title': 'Synthetic lipid trend',
            'visit_brief': {'conclusions': ['Synthetic dated response'], 'support': [], 'comparisons': []},
            'questions': ['Synthetic visit question']}
        self.data = {'agenda': {'items': [self.topic]}, 'regimen_cautions': [{'severity': 'red_flag'}]}
        self.marker = {'key': 'hdl', 'name': 'HDL', 'value': 1.4, 'unit': 'mmol/L',
                       'date': '2026-10-24', 'ref_low': 1.0, 'ref_high': None}
        self.card = {'label': 'Synthetic lipids', 'labs': {'current_markers': [self.marker]},
                     'medications': {'rows': [{'name': 'Synthetic current prescription'}]}}

    def build(self, systems=None, panels=None, question=''):
        with mock.patch('scholion.engine.system_panels._labs_layer', return_value=self.card['labs']), \
             mock.patch('scholion.engine.system_panels._medications_layer', return_value=self.card['medications']), \
             mock.patch.object(_LIFESTYLE, 'health_radar', return_value={'domains': []}), \
             mock.patch('scholion.engine.labs.analyze_labs', return_value={'markers': [self.marker]}), \
             mock.patch('scholion.insight_context._panel_rows', return_value=[]):
            return visit_focus.build(self.data, systems, panels, question)

    def test_normal_selected_system_and_other_topics_are_not_invented_findings(self):
        self.data['agenda']['items'].append({**self.topic, 'id': 'panel:liver', 'system': 'liver'})
        result = self.build(['lipids'], [], '  Synthetic appointment question  ')
        self.assertEqual(['lipids'], result['selected_systems'])
        self.assertEqual(1, len(result['systems']))
        self.assertEqual(1.4, result['systems'][0]['measurements'][0]['value'])
        self.assertEqual(1, result['other_topic_count'])
        self.assertFalse(result['suggested'])
        self.assertEqual('Synthetic appointment question', result['question'])
        self.assertEqual(self.data['regimen_cautions'], result['safety'])

    def test_suggestion_is_bounded_and_explicit_empty_does_not_select_everything(self):
        result = self.build()
        self.assertTrue(result['suggested'])
        self.assertEqual(['lipids'], result['selected_systems'])
        result = self.build([])
        self.assertFalse(result['systems'])
        self.assertFalse(result['selected_systems'])
        self.assertEqual(1, result['other_topic_count'])

    def test_unknown_and_malformed_selection_is_rejected_instead_of_broadening(self):
        for systems, panels, question in [(['unknown'], [], ''), ('lipids', [], ''),
                ([], ['unknown'], ''), ([], [], 'x'*501), ([], [], None)]:
            with self.subTest(systems=systems, panels=panels), self.assertRaises(ValueError):
                self.build(systems, panels, question)

    def test_counts_and_preview_are_explicit_without_discarding_full_payload(self):
        self.card['labs']['current_markers'] = [{**self.marker, 'key': str(n)} for n in range(7)]
        result = self.build(['lipids', 'lipids'])
        section = result['systems'][0]
        self.assertEqual(5, len(section['measurements']))
        self.assertEqual(7, section['measurement_count'])
        self.assertEqual(2, section['more_measurements'])
        self.assertEqual(1, len(self.data['agenda']['items']))

    def test_gene_row_preserves_quality_and_separate_validity_without_a_personal_effect(self):
        row = {'gene': 'SYNTHETIC', 'rsid': 'rs123', 'level': 'C', 'depth_note': 'Synthetic quality',
            'genotype': {'genotype': 'A/G', 'depth': 23, 'confidence': 'called'},
            'reference_context': {'gene_function': 'Synthetic function',
                'gencc_assertions': [{'classification': 'Limited', 'submitter': 'Synthetic source'}]},
            'interpretation': {'summary': 'Synthetic qualified association', 'source': 'PMID:123'}}
        actual = visit_focus._reading_row(row)
        self.assertEqual(23, actual['quality']['depth'])
        self.assertEqual('C', actual['level'])
        self.assertEqual('Limited', actual['gencc'][0]['classification'])
        self.assertFalse(actual['personal_effect_established'])

    def test_explicit_panel_retains_unread_status_and_does_not_call_the_whole_genome(self):
        panel = {'label': 'Synthetic panel', 'genes': [{'gene': 'SYNTHETIC',
            'reference_context': {'gene_function': 'Synthetic function'}, 'personal_comparison': {},
            'positions': [{'rsid': 'rs123', 'reading': {'read': False}, 'reference_context': {}}]}],
            'regions': [], 'counts': {'genes': 1, 'read': 0}, 'reading_note': 'Synthetic no reading'}
        with mock.patch('scholion.engine.thematic_panels.thematic_readings', return_value=panel) as read:
            result = self.build([], ['methylation'])
        self.assertFalse(result['panels'][0]['readings'])
        self.assertEqual(0, result['panels'][0]['counts']['read'])
        read.assert_called_once_with('methylation', 'clinician')

    def test_real_compact_core_keeps_legacy_fields_and_read_only_profile_in_both_languages(self):
        before = {p.name: p.read_bytes() for p in self.profile.glob('*.json')}
        for language in ('ru', 'en'):
            with mock.patch.object(i18n._state, 'current', language, create=True):
                result = engine.visit_sheet(compact=True, visit_systems=[], visit_panels=[])
                self.assertIn('measurements', result)
                self.assertIn('historical_measurements', result)
                self.assertIn('reference_appendix', result)
                self.assertFalse(result['appointment']['systems'])
                text = fmt.visit_report(result)
                self.assertIn(result['appointment']['scope_note'], text)
                self.assertNotIn('⟦', text)
                self.assertNotIn('scholion system unknown', text)
        core.reset_cache()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.profile.glob('*.json')})

    def test_qualified_carried_context_is_deduplicated_and_keeps_unprinted_count(self):
        rows = [{'gene': 'SYNTHETIC', 'rsid': 'rs'+str(n), 'level': 'C',
                 'genotype': {'genotype': 'A/G', 'depth': 25}, 'reference_context': {},
                 'summary': 'Synthetic context'} for n in range(5)]
        with mock.patch('scholion.engine.system_panels._labs_layer', return_value=self.card['labs']), \
             mock.patch('scholion.engine.system_panels._medications_layer', return_value={'rows': []}), \
             mock.patch.object(_LIFESTYLE, 'health_radar', return_value={'domains': []}), \
             mock.patch('scholion.engine.labs.analyze_labs', return_value={'markers': []}), \
             mock.patch('scholion.insight_context._panel_rows', return_value=rows+[rows[0]]), \
             mock.patch('scholion.insight_context._genetic_context', side_effect=lambda x,m:x):
            result = visit_focus.build(self.data, ['lipids'], [], '')
        section = result['systems'][0]
        self.assertEqual(3, len(section['genetics']))
        self.assertEqual(5, section['genetic_count'])
        self.assertEqual(2, section['more_genetics'])

    def test_compact_cli_and_agent_parameters_reach_shared_core(self):
        from scholion import cli, ouroboros_tools
        args = cli.build_parser().parse_args(['overview', '--visit-sheet', '--compact',
            '--visit-system', 'lipids', '--visit-panel', 'methylation', '--visit-focus', 'Synthetic question'])
        with mock.patch.object(engine, 'visit_sheet', return_value={'kind': 'visit_sheet'}) as read, \
             mock.patch.object(fmt, 'visit_report', return_value='Synthetic compact sheet'):
            cli._cmd_overview(args)
            read.assert_called_with(False, None, compact=True, visit_systems=['lipids'],
                                    visit_panels=['methylation'], visit_focus='Synthetic question')
            ouroboros_tools._h_overview(None, compact=True, visit_systems='lipids',
                                       visit_panels='methylation', visit_focus='Synthetic question')
            read.assert_called_with(False, None, compact=True, visit_systems=['lipids'],
                                    visit_panels=['methylation'], visit_focus='Synthetic question')

    def test_gencc_in_the_short_sheet_uses_existing_system_concepts_not_every_gene_disease(self):
        assertions = [{'disease_id': 'MONDO:synthetic1', 'classification': 'Limited'},
                      {'disease_id': 'MONDO:synthetic2', 'classification': 'Strong'}]
        row = {'gene': 'SYNTHETIC', 'reference_context': {'gencc_assertions': assertions}}
        actual = visit_focus._reading_row(row, {'MONDO:synthetic1'})
        self.assertEqual([assertions[0]], actual['gencc'])
        self.assertEqual(1, actual['other_gencc_count'])
        self.assertEqual(assertions, actual['reference_context']['gencc_assertions'])

    def test_selected_panel_positive_calls_and_the_compact_text_keep_their_qualifications(self):
        position = {'gene': 'SYNTHETIC', 'rsid': 'rs123', 'level': 'C',
            'reference_context': {'gene_function': 'Synthetic function', 'variant_context': 'Synthetic hypothesis',
                'gene_source': 'PMID:123'},
            'reading': {'read': True, 'genotype': 'A/G', 'depth': 22, 'message': 'Synthetic called A/G',
                        'confidence': 'called', 'source': 'Synthetic source'}}
        panel = {'label': 'Synthetic selected panel', 'genes': [{'gene': 'SYNTHETIC',
            'reference_context': position['reference_context'], 'personal_comparison': {},
            'positions': [{**position, 'rsid': 'rs'+str(n)} for n in range(5)]}],
            'regions': [], 'counts': {'genes': 1, 'read': 5}, 'reading_note': 'Synthetic panel scope'}
        with mock.patch('scholion.engine.thematic_panels.thematic_readings', return_value=panel):
            result = self.build([], ['methylation'], 'Synthetic visit focus')
        self.assertEqual(3, len(result['panels'][0]['readings']))
        self.assertEqual(2, result['panels'][0]['more_readings'])
        self.assertEqual('C', result['panels'][0]['readings'][0]['level'])
        result['safety'] = []
        text = fmt.visit_report({'appointment': result, 'title': 'Synthetic handout', 'container': {'id': 'synthetic'},
             'version': '0.7.2', 'as_of': '2026-10-24', 'disclaimer': 'Synthetic disclaimer'})
        for expected in ('Synthetic visit focus', 'Synthetic selected panel', 'Synthetic panel scope',
                         'Synthetic called A/G', 'Synthetic hypothesis', 'PMID:123', 'scholion system methylation'):
            self.assertIn(expected, text)

    def test_short_text_retains_dated_facts_qualified_genetics_and_more_links_without_unrelated_sections(self):
        self.card['labs']['current_markers'] = [{**self.marker, 'key': str(n)} for n in range(7)]
        self.card['medications']['rows'] = [{'name': 'Synthetic medicine '+str(n), 'dose': 'synthetic dose'} for n in range(5)]
        result = self.build(['lipids'], [], 'Synthetic focus question')
        section = result['systems'][0]
        section['insights'][0]['support'] = ['Synthetic reported response, not causation']
        section['insights'][0]['comparisons'] = [{'gene': 'SYNTHETIC', 'rsid': 'rs123', 'level': 'C',
            'status_label': 'Synthetic hypothesis', 'comparison': 'Synthetic comparison', 'summary': 'Synthetic association'}]
        section['genetics'] = [{'gene': 'SYNTHETIC', 'rsid': 'rs123', 'level': 'C', 'genotype': 'A/G',
            'function': 'Synthetic function', 'summary': 'Synthetic qualified association',
            'reading_note': 'Synthetic depth 22', 'source': 'PMID:123',
            'gencc': [{'disease_label': 'Synthetic gene disease', 'classification_label': 'Synthetic limited validity',
                       'moi_label': 'Synthetic inheritance', 'submitter': 'Synthetic laboratory', 'curated_on': '2026-10-01'}]}]
        section['more_genetics'] = 2
        result['safety'] = []
        data = {'appointment': result, 'title': 'Synthetic handout', 'container': {'id': 'synthetic'},
                'version': '0.7.2', 'as_of': '2026-10-24', 'disclaimer': 'Synthetic disclaimer', 'synthetic': True}
        text = fmt.visit_report(data)
        for expected in ('Synthetic focus question', '1.4 mmol/L', '2026-10-24', 'Synthetic reported response',
                         'Synthetic comparison', 'Synthetic limited validity', 'Synthetic laboratory',
                         'Synthetic medicine 0', 'Synthetic depth 22', 'scholion system lipids'):
            self.assertIn(expected, text)
        self.assertNotIn('Synthetic medicine 4', text)
        self.assertNotIn('scholion system liver', text)
        section['measurements'] = []
        section['insights'][0]['comparisons'] = [{'gene': 'SYNTHETIC', 'rsid': 'rs123', 'level': 'C',
            'status_label': 'Synthetic hypothesis', 'comparison': 'Synthetic hypothesis', 'summary': 'Synthetic association'}]
        result['panels'] = [{'key': 'methylation', 'label': 'Synthetic uncalled panel',
                            'readings': [], 'note': 'Synthetic scope', 'more_readings': 0}]
        self.assertIn(i18n.t('visit.focus.no_measurements'), fmt.visit_report(data))
        self.assertIn(i18n.t('visit.focus.no_panel_calls'), fmt.visit_report(data))

    def test_explicit_narrow_focus_does_not_hide_a_recorded_critical_topic(self):
        self.data['safety_topics'] = [{'title': 'Synthetic important recorded control',
            'visit_brief': {'support': ['Synthetic clinician plan'],
                'measurements': [{'name': 'Synthetic marker',
                    'latest': {'value': 9, 'unit': 'u', 'date': '2026-10-24'}}]}}]
        result = self.build([])
        result['safety'] = []
        self.assertEqual(self.data['safety_topics'], result['safety_topics'])
        text = fmt.visit_report({'appointment': result, 'title': 'Synthetic handout', 'container': {'id': 'synthetic'},
                'version': '0.7.2', 'as_of': '2026-10-24', 'disclaimer': 'Synthetic disclaimer'})
        self.assertIn('Synthetic important recorded control', text)
        self.assertIn('Synthetic clinician plan', text)
        self.assertIn('9 u', text)

    def test_recorded_body_measurement_and_only_relevant_computed_estimates_enter_the_short_sheet(self):
        self.topic['visit_brief']['measurements'] = [{'key': 'weight', 'name': 'Synthetic weight',
            'latest': {'record': 'metrics.json', 'value': 78, 'date': '2026-10-24', 'unit': 'kg'}}]
        self.data['clinical_estimates'] = {'estimates': [
            {'key': 'fib4', 'status': 'computed', 'name': 'Synthetic liver index', 'value': 0.5, 'unit': '',
             'date': '2026-10-24', 'source': 'Synthetic published method', 'interpretation': 'Synthetic method scope'},
            {'key': 'phenoage', 'status': 'missing'}]}
        result = self.build(['lipids'])
        self.assertFalse(result['clinical_estimates'])
        self.assertIn('weight', [m['key'] for m in result['systems'][0]['measurements']])
        result = self.build(['liver'])
        self.assertEqual(['fib4'], [r['key'] for r in result['clinical_estimates']])
        result['safety'] = []
        text = fmt.visit_report({'appointment': result, 'title': 'Synthetic handout', 'container': {'id': 'synthetic'},
                'version': '0.7.2', 'as_of': '2026-10-24', 'disclaimer': 'Synthetic disclaimer'})
        self.assertIn('Synthetic liver index', text)
        self.assertIn('Synthetic method scope', text)

    def test_joint_result_replaces_single_positions_and_never_assigns_an_unphased_epsilon_pair(self):
        from scholion.genome import _apoe_from_readings
        calls = [{'gene': 'APOE', 'rsid': rsid, 'read': True, 'level': 'B',
                  'genotype': {'genotype': 'CT', 'confidence': 'called', 'depth': 24}}
                 for rsid in ('rs429358', 'rs7412')]
        joint = {'gene': 'APOE', 'rsid': 'rs429358 / rs7412', 'level': 'B',
            'facts': {'diplotype': _apoe_from_readings(*(r['genotype'] for r in calls))},
            'variant_readings': calls, 'summary': 'Synthetic joint association',
            'source': 'Synthetic joint source', 'association_id': 'synthetic-joint'}
        with mock.patch('scholion.engine.system_panels._labs_layer', return_value=self.card['labs']), \
             mock.patch('scholion.engine.system_panels._medications_layer', return_value={'rows': []}), \
             mock.patch.object(_LIFESTYLE, 'health_radar', return_value={'domains': []}), \
             mock.patch('scholion.engine.labs.analyze_labs', return_value={'markers': []}), \
             mock.patch('scholion.insight_context._panel_rows', return_value=calls), \
             mock.patch('scholion.insight_context._genetic_context', side_effect=lambda x,m:x), \
             mock.patch('scholion.genetic_patterns.comparisons', return_value=[joint]):
            result = visit_focus.build(self.data, ['lipids'], [], '')
            genetics = result['systems'][0]['genetics']
            self.assertEqual(1, len(genetics))
            self.assertEqual('rs429358 / rs7412', genetics[0]['rsid'])
            self.assertIsNone(genetics[0]['genotype'])
            self.assertEqual(joint['facts']['diplotype']['message'], genetics[0]['summary'])
            calls[0]['genotype']['genotype'] = 'TT'
            joint['facts']['diplotype'] = _apoe_from_readings(*(r['genotype'] for r in calls))
            result = visit_focus.build(self.data, ['lipids'], [], '')
            self.assertEqual('\u03b52/\u03b53', result['systems'][0]['genetics'][0]['genotype'])

    def test_cli_invalid_focus_is_an_actionable_refusal_not_a_traceback(self):
        from contextlib import redirect_stderr, redirect_stdout
        import io
        from scholion import cli
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = cli.main(['overview', '--compact', '--visit-system', 'synthetic-unknown'])
        self.assertEqual(2, code)
        self.assertIn(i18n.t('visit.focus.invalid_selection'), errors.getvalue())
        self.assertNotIn('Traceback', errors.getvalue())

    def test_compact_projection_does_not_fetch_linked_gene_regions_for_its_joint_summary(self):
        with mock.patch('scholion.genetic_comparison.linked_rows', side_effect=AssertionError('Unexpected region fetch')):
            result = self.build(['lipids'])
        self.assertEqual(['lipids'], result['selected_systems'])

    def test_non_diplotype_context_and_entirely_unread_pairs_do_not_become_personal_joint_calls(self):
        with mock.patch('scholion.genetic_patterns.comparisons', return_value=[
            {'facts': {}}, {'facts': {'diplotype': {'status': 'no_data'}},
                           'variant_readings': [{'read': False}, {'read': None}]}]):
            result = self.build(['lipids'])
        self.assertFalse(result['systems'][0]['genetics'])
        self.assertEqual(0, result['systems'][0]['genetic_count'])

    def test_short_web_sheet_keeps_a_qualified_rare_finding_outside_the_snp_preview(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('needs node for the actual visit renderer')
        result = self.build(['lipids'])
        comparison = {'gene': 'SYNTHETIC', 'rsid': '', 'level': 'C',
            'comparison': 'Synthetic qualified association', 'status_label': 'Synthetic incomplete support',
            'summary': 'Synthetic mechanism', 'knowledge_status': 'hypothesis',
            'limitations': 'Synthetic uncertainty', 'knowledge': {}, 'reason_labels': [],
            'qualified_context': True, 'pattern_inputs': ['hdl'],
            'variant_readings': [{'gene': 'SYNTHETIC', 'variant_records': [
                {'chrom': '1', 'pos': 123, 'ref': 'A', 'alt': 'G', 'zygosity': 'het',
                 'classification': 'Synthetic classification'}]}]}
        result['systems'][0]['insights'][0]['comparisons'] = [comparison]
        result['safety'] = []
        self.assertFalse(result['systems'][0]['genetics'])
        data = {'appointment': result, 'container': {}, 'version': '0.7.2',
                'as_of': '2026-10-24', 'disclaimer': 'Synthetic disclaimer'}
        data['document'] = visit_focus.document(self.data, result, compact=True)
        page = (Path(__file__).resolve().parents[1] / 'src/scholion/web/index.html').read_text(encoding='utf-8')
        start = page.index('function geneticComparisonHTML(')
        functions = page[start:page.index('\nfunction insightContextHTML(', start)]
        start = page.index('function visitFocusedHTML(')
        functions += page[start:page.index('\nasync function viewVisitSheet(', start)]
        script = """
const assert=require('node:assert/strict');
const esc=x=>String(x??'').replaceAll('<','&lt;'),t=k=>k,fmtDate=String,fmtNum=String;
const systemGeneLink=esc,levelChip=esc,cautionsHtml=()=>'',visitSourceLinks=esc,geneticBriefHtml=()=>'';
""" + functions + '\nconst html=visitDocumentHTML(' + json.dumps(data) + ");\n" + """
for(const text of ['Synthetic qualified association','Synthetic uncertainty','1:123 A&gt;G',
                   'Synthetic classification','Synthetic incomplete support']) assert.ok(html.includes(text),text);
"""
        script = gene_card_support.javascript() + script
        process = subprocess.run([node], input=script, text=True, encoding='utf-8',
                                 capture_output=True, timeout=30)
        self.assertEqual(0, process.returncode, process.stderr)

    def test_document_keeps_dates_units_and_qualifies_the_axis_without_inventing_a_response(self):
        projection = self.build(['lipids'])
        a = {'date': '2026-01-02', 'value': 120, 'unit': 'mg/dL', 'date_source': 'form'}
        with mock.patch.object(i18n._state, 'current', 'ru', create=True):
            recorded_unit = core.unit_label('mmol/L')
        b = {'date': '2026-09-12', 'value': 4, 'unit': recorded_unit, 'date_source': 'form'}
        projection['systems'][0]['histories'] = [{'key': 'ldl', 'name': 'Synthetic LDL', 'series': [a, b]}]
        data = {**self.data, 'medications': [
            {'name': 'Synthetic ended', 'current': False},
            {'name': 'Synthetic future', 'current': True, 'start_date': '2099-01-01'}]}
        with mock.patch('scholion.engine.system_panels.medication_system_context', return_value={
                'systems': ['lipids'], 'system_links': [], 'outside_contexts': []}):
            result = visit_focus.document(data, projection, compact=True)
        chart = result['charts'][0]
        self.assertEqual([a, b], [{k: v for k, v in point.items() if k != 'unit_display'}
                                  for point in chart['series']])
        self.assertEqual('mmol/L', chart['series'][1]['unit_display'])
        self.assertEqual(recorded_unit, b['unit'])
        self.assertNotIn('unit_display', b)
        self.assertFalse(chart['connect'])
        self.assertFalse(chart['numeric_axis'])
        self.assertEqual(['Synthetic future'], [m['name'] for m in result['medications']])
        self.assertFalse(result['medications'][0]['response_assessed'])
        self.assertFalse(result['medications'][0]['response'])
        self.assertFalse(result['controls'])
        self.assertEqual('2099-01-01', result['medications'][0]['start_date'])

    def test_full_projection_retains_unique_rows_beyond_the_short_preview(self):
        self.card['labs']['current_markers'] = [{**self.marker, 'key': str(n)} for n in range(8)]
        with mock.patch('scholion.engine.system_panels._labs_layer', return_value=self.card['labs']), \
             mock.patch('scholion.engine.system_panels._medications_layer', return_value={'rows': []}), \
             mock.patch.object(_LIFESTYLE, 'health_radar', return_value={'domains': []}), \
             mock.patch('scholion.insight_context._panel_rows', return_value=[]), \
             mock.patch('scholion.engine.labs.analyze_labs', side_effect=AssertionError('Duplicate lab analysis')):
            result = visit_focus.build(self.data, ['lipids'], [], '', full=True, lab_markers=[self.marker])
        self.assertEqual(8, len(result['systems'][0]['measurements']))
        self.assertEqual(0, result['systems'][0]['more_measurements'])

    def test_both_document_modes_are_read_only_and_adapt_to_an_empty_profile(self):
        (self.profile / 'labs.json').write_text(json.dumps({'markers': {}}), encoding='utf-8')
        (self.profile / 'metrics.json').write_text(json.dumps({'profile': {}, 'metrics': {}}), encoding='utf-8')
        before = {p.name: p.read_bytes() for p in self.profile.glob('*.json')}
        for lang in ('ru', 'en'):
            with mock.patch.object(i18n._state, 'current', lang, create=True):
                for compact in (False, True):
                    result = engine.visit_sheet(compact=compact, visit_systems=[] if compact else None)
                    document = result['document']
                    self.assertEqual('short' if compact else 'full', document['kind'])
                    self.assertFalse(document['charts'])
                    self.assertFalse(document['controls'])
                    self.assertNotIn('⟦', fmt.visit_report(result))
                    self.assertIn(document['title'], fmt.visit_report(result))
                    self.assertIn('reference_appendix', result)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.profile.glob('*.json')})

    def test_full_report_keeps_a_current_abnormal_system_without_a_trend_insight(self):
        from datetime import date
        from scholion import store
        self.assertTrue(store.add_lab_point('ldl', date.today().isoformat(), 4.1,
            unit='mmol/L', ref_low=0, ref_high=3, date_source='form')['ok'])
        result = engine.visit_sheet()
        section = next(s for s in result['document']['systems'] if s['key'] == 'lipids')
        self.assertIn(4.1, [m['value'] for m in section['measurements']])
        self.assertFalse(any(c.get('connect') for c in section['charts']))
        self.assertIn('reference_appendix', result)

    def test_short_response_preview_keeps_a_temporal_comparison_without_claiming_efficacy(self):
        projection = self.build(['lipids'])
        self.topic['treatment_review'] = [{'drug': 'Synthetic compared', 'current': True,
            'summary': 'Synthetic temporal comparison; causation is not established',
            'comparisons': [{'before': 4, 'after': 3}], 'response_assessed': False}]
        data = {**self.data, 'medications': [{'name': 'Synthetic record '+str(i), 'current': True}
                for i in range(8)]+[{'name': 'Synthetic compared', 'current': True}]}
        with mock.patch('scholion.engine.system_panels.medication_system_context', return_value={
                'systems': ['lipids'], 'system_links': [], 'outside_contexts': []}):
            result = visit_focus.document(data, projection, compact=True)
        row = result['medications'][0]
        self.assertEqual('Synthetic compared', row['name'])
        self.assertTrue(row['has_observed_comparison'])
        self.assertFalse(row['response_assessed'])
        self.assertFalse(row['causal'])
        self.assertIn('causation is not established', row['response'][0])
        self.assertEqual(9, result['medication_count'])

    def test_report_renderers_omit_empty_sections_instead_of_describing_missing_data(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('needs node for the actual visit renderer')
        page = (Path(__file__).resolve().parents[1] / 'src/scholion/web/index.html').read_text(encoding='utf-8')
        start = page.index('function visitFocusedHTML(')
        functions = page[start:page.index('\nasync function viewVisitSheet(', start)]
        for compact in (False, True):
            result = engine.visit_sheet(compact=compact, visit_systems=[] if compact else None)
            text = fmt.visit_report(result)
            self.assertNotIn(i18n.t('visit.empty'), text)
            self.assertNotIn(i18n.t('visit.report.plan'), text)
            self.assertFalse(result['document']['cards'])
            script = """
const assert=require('node:assert/strict');
const esc=x=>String(x??''),t=k=>k,fmtDate=String,fmtNum=String;
const systemGeneLink=esc,levelChip=esc,cautionsHtml=()=>'',visitSourceLinks=esc,controlsHtml=()=>'';
""" + functions + '\nconst html=visitDocumentHTML(' + json.dumps(result) + ");\n" + """
for(const unwanted of ['visit.report.plan','visit.report.response','visit.empty',
                       'visit.report.no_plan','visit.focus.no_measurements']) assert.ok(!html.includes(unwanted),unwanted);
"""
            script = gene_card_support.javascript() + script
            run = subprocess.run([node], input=script, text=True, encoding='utf-8', capture_output=True,
                                 timeout=30)
            self.assertEqual(0, run.returncode, run.stderr)

    def test_visit_body_charts_use_the_shared_manual_and_device_history(self):
        from datetime import date, timedelta
        from scholion.measurements import history, bmi_history
        from scholion.format_visit_focus import document_overview
        today = date.today()
        recent = (today-timedelta(days=50)).strftime('%Y-%m')
        recorded = {'profile': {'height_cm': 200}, 'metrics': {'weight': {
            'unit': 'kg', 'series': [{'date': '2000-01-01', 'value': 110},
                {'date': today.isoformat(), 'value': 96}]}}}
        device = {'sources': {'garmin': {'metrics': {'Weight': {recent: 100}}}}}
        self.topic['system'] = 'fitness'
        self.card['labs']['current_markers'] = []
        with mock.patch.object(core, 'metrics_json', return_value=recorded), \
             mock.patch.object(core, 'wearable_trends', return_value=device):
            projection = self.build(['fitness'], question='Synthetic weight discussion')
            result = visit_focus.document(self.data, projection, compact=True)
            charts = {c['key']: c for c in result['charts']}
            cutoff = (today-timedelta(days=365)).isoformat()[:7]
            for key, expected in [('weight', history('weight')), ('bmi', bmi_history())]:
                self.assertEqual([{**p, 'unit_display': core.unit_label(p['unit'])}
                                  for p in expected['series'] if p['date'][:7] >= cutoff], charts[key]['series'])
                self.assertEqual({'garmin', 'recorded'}, {p['measurement_source'] for p in charts[key]['series']})
                self.assertTrue(charts[key]['display_connect'])
                self.assertEqual(charts[key]['qualification']['eligible'], charts[key]['connect'])
                self.assertEqual(i18n.t('visit.report.body_history'), charts[key]['summary'])
            text = '\n'.join(document_overview({'document': result}))
        self.assertEqual(2, len(result['charts']))
        self.assertEqual(24, charts['bmi']['series'][-1]['value'])
        self.assertIn('Synthetic weight discussion', text)
        self.assertNotIn('2000-01-01', text)

    def test_visit_annual_charts_do_not_duplicate_or_invent_empty_system_cards(self):
        projection = self.build(['lipids', 'liver'])
        projection['systems'][1].update(measurements=[], histories=[])
        points = [{'date': '2026-01-02', 'value': 4, 'unit': 'mmol/L', 'date_source': 'form'},
                  {'date': '2026-09-12', 'value': 3, 'unit': 'mmol/L', 'date_source': 'form'}]
        annual = {'window': 365, 'marker': 'ldl', 'name': 'Synthetic LDL', 'series': points,
                  'summary': 'Synthetic annual direction', 'status': 'toward'}
        self.topic['trajectory'] = {'changes': [
            {**annual, 'window': 30, 'marker': 'short_only'}, annual, dict(annual),
            {**annual, 'marker': 'empty', 'series': []}]}
        result = visit_focus.document(self.data, projection, compact=True)
        self.assertEqual(['ldl'], [c['key'] for c in result['charts']])
        self.assertEqual([{**p, 'unit_display': core.unit_label(p['unit'])} for p in points],
                         result['charts'][0]['series'])
        self.assertEqual(['lipids'], [c['system'] for c in result['cards']])
        self.assertFalse(projection['systems'][1]['charts'])

    def test_visit_keeps_recorded_controls_and_observed_response_in_both_languages(self):
        from scholion.format_visit_focus import document_overview
        self.topic['treatment_review'] = [{'drug': 'Synthetic compared', 'current': True,
            'summary': 'Synthetic observed comparison; causation not established',
            'comparisons': [{'before': 4, 'after': 3}], 'response_assessed': False}]
        medications = [{'name': 'Synthetic compared', 'current': True, 'dose': 'Synthetic dose'}]
        medications += [{'name': 'Synthetic other '+str(n), 'current': True} for n in range(6)]
        medications += [{'name': 'Synthetic outside', 'current': True},
                        {'name': 'Synthetic ended', 'current': False}]
        plan = {'name': 'Synthetic compared', 'current': True, 'status': 'scheduled',
                'marker': 'ldl', 'due': '2026-11-20', 'plan_source': 'Synthetic recorded plan'}
        data = {**self.data, 'medications': medications, 'treatment': {'controls': [plan,
            {**plan, 'name': 'Synthetic outside'}, {**plan, 'current': False},
            {**plan, 'status': 'unstructured'}]}}
        def context(med):
            return {'systems': ['liver' if med['name'] == 'Synthetic outside' else 'lipids'],
                    'system_links': [], 'outside_contexts': []}
        for lang in ('ru', 'en'):
            with mock.patch.object(i18n._state, 'current', lang, create=True), \
                 mock.patch('scholion.engine.system_panels.medication_system_context', side_effect=context):
                result = visit_focus.document(data, self.build(['lipids'], question='Synthetic visit question'), compact=True)
                text = '\n'.join(document_overview({'document': result}))
                self.assertEqual(7, result['medication_count'])
                self.assertEqual(1, result['more_medications'])
                self.assertEqual([plan], result['controls'])
                self.assertEqual([plan], result['medications'][0]['controls'])
                self.assertFalse(result['medications'][0]['causal'])
                self.assertFalse(result['medications'][0]['response_assessed'])
                self.assertIn('Synthetic observed comparison', text)
                self.assertIn('Synthetic recorded plan', text)
                self.assertIn('2026-11-20', text)
                self.assertNotIn('Synthetic outside', text)
                self.assertNotIn('Synthetic ended', text)
                self.assertIn(i18n.t('visit.report.more_rx', n=1), text)

    def test_visit_gene_focus_keeps_each_system_before_additional_rows(self):
        projection = self.build(['lipids', 'glucose'])
        genes = [visit_focus._reading_row({'gene': 'SYNTHETIC'+str(n), 'rsid': 'rs'+str(n),
            'level': 'C', 'genotype': {'genotype': 'A/G', 'depth': 25},
            'reference_context': {'gene_function': 'Synthetic function'},
            'genetic_lab_comparison': {'eligible': True, 'marker': 'hdl', 'summary': 'Synthetic association'}}) for n in range(10)]
        projection['systems'][0].pop('genetic_candidates')
        projection['systems'][1].pop('genetic_candidates')
        projection['systems'][0]['genetics'] = genes[:8]
        projection['systems'][1]['genetics'] = [genes[0], *genes[8:]]
        for compact, expected in [(True, 3), (False, 10)]:
            result = visit_focus.document(self.data, projection, compact=compact)
            self.assertEqual(10, result['genetic_context_count'])
            self.assertEqual(expected, len(result['genetic_focus']))
            self.assertEqual({'lipids', 'glucose'}, {g['system'] for g in result['genetic_focus']})
            self.assertIn('SYNTHETIC8', [g['gene'] for g in result['genetic_focus']])
            self.assertEqual(10-expected, result['more_genetic_focus'])
            self.assertEqual(11, sum(len(s['genetics']) for s in result['systems']))


    def test_exact_marker_links_replace_system_membership_and_keep_every_candidate(self):
        section = self.build(['lipids'])['systems'][0]
        genes = []
        for n, marker in enumerate(('uric_acid', 'hdl', 'hdl', 'hdl', 'hdl')):
            comparison = {'marker': marker, 'eligible': True, 'summary': 'Synthetic association',
                          'comparison': 'Synthetic measured relation', 'source': 'PMID:123'}
            genes.append(visit_focus._reading_row({'gene': 'SYNTHETIC'+str(n), 'rsid': 'rs'+str(n),
                'genotype': {'genotype': 'A/G', 'depth': 25}, 'level': 'B',
                'genetic_lab_comparison': comparison}))
        section['genetics'] = genes[:3]
        section['genetic_candidates'] = genes + [genes[1]]
        section['focus_measurements'] = [self.marker]
        projection = self.build(['lipids'])
        projection['systems'] = [section]
        for compact in (True, False):
            result = visit_focus.document(self.data, projection, compact=compact)
            self.assertEqual(4, result['genetic_context_count'])
            self.assertEqual(5, result['genetic_read_count'])
            self.assertEqual(2 if compact else 4, len(result['genetic_focus']))
            self.assertEqual(2 if compact else 0, result['more_genetic_focus'])
            for gene in result['genetic_focus']:
                self.assertNotEqual('SYNTHETIC0', gene['gene'])
                self.assertEqual('hdl', gene['visit_links'][0]['marker'])
                self.assertIn('HDL', gene['visit_links'][0]['reason'])
            self.assertEqual(3, len(section['genetics']))

    def test_second_association_can_match_and_hypotheses_remain_qualified(self):
        section = self.build(['lipids'])['systems'][0]
        section['focus_measurements'] = [self.marker]
        hypothesis = {'marker': 'hdl', 'status': 'hypothesis', 'applicable': True,
            'quality': {'status': 'usable'}, 'observation': {'current': True},
            'comparison': 'Synthetic hypothesis only', 'limitations': 'Synthetic uncertainty'}
        gene = visit_focus._reading_row({'gene': 'SYNTHETIC', 'rsid': 'rs123', 'level': 'C',
            'comparisons': [{'marker': 'other', 'eligible': True}, hypothesis]})
        section['genetic_candidates'] = [gene]
        rows = visit_focus._discussion_genetics(section, self.data)
        self.assertEqual('C', rows[0]['level'])
        self.assertEqual('hypothesis', rows[0]['visit_links'][0]['kind'])
        self.assertEqual('Synthetic uncertainty', rows[0]['visit_links'][0]['limitations'])
        for changes in ({'applicable': False}, {'quality': {'status': 'limited'}},
                        {'observation': {'current': False}}, {'status': 'context_only'}):
            gene['comparisons'] = [{**hypothesis, **changes}]
            self.assertEqual([], visit_focus._discussion_genetics(section, self.data))

    def test_prescription_requires_an_explicit_verified_variant_drug_relation(self):
        section = self.build(['lipids'])['systems'][0]
        flag = {'gene': 'SYNTHETIC', 'rsid': 'rs123', 'drug': 'Synthetic current prescription',
                'genotype': 'A/G', 'factor': 'Synthetic qualified caution', 'why_it_matters': 'Synthetic mechanism',
                'level': 'B', 'source': 'PMID:123', 'genotype_source': 'Synthetic VCF'}
        data = {**self.data, 'regimen_cautions': [flag]}
        rows = visit_focus._discussion_genetics(section, data)
        self.assertEqual(1, len(rows))
        self.assertEqual('prescription', rows[0]['visit_links'][0]['kind'])
        self.assertIn(flag['drug'], rows[0]['visit_links'][0]['reason'])
        for changes in ({'drug': 'Synthetic unrelated drug'}, {'interpretation_withheld': True}, {'factor': None}, {'genotype': None}, {'level': 'C'}):
            self.assertEqual([], visit_focus._discussion_genetics(section,
                {**data, 'regimen_cautions': [{**flag, **changes}]}))

    def test_default_keeps_attention_systems_after_three_favourable_topics(self):
        self.data['agenda']['items'] = [{**self.topic, 'system': k} for k in
            ('amino_acids', 'inflammation', 'micronutrients', 'fitness')]
        marker = {**self.marker, 'abnormal': True}
        with mock.patch('scholion.engine.system_panels._labs_layer', return_value={'current_markers': [marker]}), \
             mock.patch('scholion.engine.system_panels._medications_layer', return_value={'rows': []}), \
             mock.patch('scholion.insight_context._panel_rows', return_value=[]):
            result = visit_focus.build(self.data, None, [], '', lab_markers=[marker])
        self.assertIn('lipids', result['selected_systems'])
        self.assertEqual(['lipids'], result['selected_systems'])
        self.data['agenda']['items'].append({**self.topic, 'system': 'renal',
            'trajectory': {'changes': [{'window': 365, 'status': 'away'}]}})
        self.assertIn('renal', self.build()['selected_systems'])
        with mock.patch('scholion.insight_context._panel_rows', return_value=[]):
            full = visit_focus.build(self.data, None, [], '', full=True, lab_markers=[marker])
        self.assertIn('fitness', full['selected_systems'])
        # Explicit selection stays explicit, including an empty list.
        self.assertEqual([], self.build([])['selected_systems'])

    def test_metadata_limited_mechanisms_remain_context_but_wrong_alleles_do_not(self):
        section = self.build(['lipids'])['systems'][0]
        comparison = {'marker': 'hdl', 'systems': ['lipids'], 'knowledge_status': 'supported',
            'level': 'B', 'quality': {'status': 'usable'}, 'reasons': ['fasting_unknown'],
            'summary': 'Synthetic known mechanism', 'source': 'PMID:123'}
        gene = visit_focus._reading_row({'gene': 'SYNTHETIC', 'rsid': 'rs123',
            'genetic_lab_comparison': comparison})
        section['genetic_candidates'] = [gene]
        actual = visit_focus._discussion_genetics(section, self.data)
        self.assertEqual('context', actual[0]['visit_links'][0]['kind'])
        self.assertIn(i18n.t('visit.report.variant_context_only'), actual[0]['visit_links'][0]['qualification'])
        for changes in ({'reasons': ['genotype_scope']}, {'reasons': ['catalogue_identity']},
                        {'reasons': ['specimen_scope']}, {'quality': {'status': 'limited'}},
                        {'knowledge_status': 'excluded'}, {'systems': ['liver']}):
            gene['comparison'] = {**comparison, **changes}
            self.assertFalse(visit_focus._discussion_genetics(section, self.data))
        # Cross-system contexts are reused without scanning or moving their observations.
        section['genetic_candidates'] = []
        cross = {**gene, 'comparisons': [{**comparison, 'eligible': True}]}
        data = {**self.data, 'agenda': {'items': [{**self.topic, 'context': {'genetics': [cross]}}]}}
        actual = visit_focus._discussion_genetics(section, data)
        self.assertEqual('SYNTHETIC', actual[0]['gene'])
        self.assertEqual('hdl', actual[0]['visit_links'][0]['marker'])

    def test_both_text_reports_keep_reasons_rare_readings_sources_and_explicit_appendix(self):
        from scholion import format_visit_focus
        projection = self.build(['lipids'])
        section = projection['systems'][0]
        section['histories'] = [{'key': 'hdl', 'name': 'Synthetic HDL', 'series': [
            {**self.marker, 'value': 1.2, 'date': '2026-03-10', 'date_source': 'form'},
            {**self.marker, 'date_source': 'form'}]}]
        comparison = {'gene': 'SYNTHETIC', 'rsid': 'rs123', 'marker': 'hdl', 'eligible': True,
            'summary': 'Synthetic known mechanism', 'comparison': 'Synthetic qualified comparison',
            'limitations': 'Synthetic uncertainty', 'variant_readings': [{'variant_records': [
                {'chrom': '1', 'pos': 123, 'ref': 'A', 'alt': 'G', 'zygosity': 'het', 'classification': 'Synthetic classification'}]}]}
        gene = visit_focus._reading_row({'gene': 'SYNTHETIC', 'rsid': 'rs123', 'level': 'C',
            'genotype': {'genotype': 'AG', 'depth': 25}, 'source': 'PMID:123',
            'summary': 'Synthetic known mechanism',
            'reference_context': {'gene_function': 'Synthetic function', 'gencc_assertions': [
                {'disease_label': 'Synthetic disease', 'classification': 'Limited', 'submitter': 'Synthetic source'}]},
            'genetic_lab_comparison': comparison})
        gene['variant_readings'] = comparison['variant_readings']
        section['genetic_candidates'] = [gene]
        section['insights'][0]['comparisons'] = [comparison]
        projection['clinical_estimates'] = [{'name': 'Synthetic index', 'value': 1, 'unit': '',
            'date': '2026-10-24', 'source': 'Synthetic published method'}]
        projection['safety_topics'] = [{'title': 'Synthetic safety topic', 'visit_brief': {'support': ['Synthetic safety basis']}}]
        projection['panels'] = [{'key': 'methylation', 'label': 'Synthetic panel', 'note': 'Synthetic panel scope',
                                 'readings': [gene]}]
        self.data['regimen_cautions'] = []
        projection['safety'] = []
        for language in ('ru', 'en'):
            with mock.patch.object(i18n._state, 'current', language, create=True):
                for compact in (True, False):
                    doc = visit_focus.document(self.data, projection, compact=compact)
                    doc['systems'][0]['more_discussion_genetics'] = 1
                    data = {'document': doc, 'container': {'id': 'synthetic'}, 'version': '0.7.2',
                        'as_of': '2026-10-24', 'synthetic': True, 'disclaimer': 'Synthetic disclaimer',
                        'reference_appendix': {'included': True, 'panels': [{'label': 'Synthetic appendix',
                            'positions': [{'gene': 'SYNTHETIC', 'rsid': 'rs123',
                                'reference_context': {'gene_function': 'Synthetic appendix function'}, 'interpretation': {}}]}]},
                        'appendix_note': 'Synthetic source qualification'}
                    text = fmt.visit_report(data)
                    for expected in ('Synthetic known mechanism', 'Synthetic uncertainty', '1:123 A>G',
                                     'Synthetic classification', 'Synthetic disease', 'Synthetic source',
                                     'Synthetic index', 'Synthetic panel', 'Synthetic appendix function',
                                     'Synthetic safety basis', '2026-03-10', i18n.t('visit.report.gene_reason')):
                        self.assertIn(expected, text)
                    self.assertIn('Synthetic qualified comparison', text)
                    self.assertIn(doc['scope_note'], text)
                    # A disconnected observation stays disconnected in terminal output.
                    doc['systems'][0]['discussion_charts'][0]['connect'] = False
                    self.assertIn(i18n.t('visit.report.separate'), format_visit_focus.report(data))

    def test_non_diplotype_pattern_stays_an_observation_link_with_an_explicit_passport(self):
        comparison = {'gene': 'SYNTHETIC', 'rsid': 'rs123', 'level': 'D', 'display_genotype': 'AG',
            'pattern_inputs': ['hdl'], 'qualified_context': True, 'summary': 'Synthetic rare mechanism',
            'source': 'PMID:123', 'facts': {}, 'association_id': 'synthetic-compound',
            'variant_readings': [{'read': True, 'genotype': {'genotype': 'AG', 'depth': 25}}]}
        with mock.patch('scholion.genetic_patterns.comparisons', return_value=[comparison]):
            projection = self.build(['lipids'])
        section = projection['systems'][0]
        section['insights'][0]['comparisons'] = [{'summary': 'Synthetic non-variant context'}]
        self.data['regimen_cautions'] = [{'gene': 'OTHER', 'rsid': 'rs456',
            'drug': 'Synthetic current prescription', 'genotype': 'AG', 'factor': 'Synthetic prescription fact', 'level': 'B'}]
        doc = visit_focus.document(self.data, projection, compact=True)
        self.assertEqual({'SYNTHETIC', 'OTHER'}, {g['gene'] for g in doc['genetic_focus']})
        doc['systems'][0]['discussion_charts'] = [{'name': 'Synthetic HDL', 'series': [self.marker],
            'connect': True, 'summary': 'Synthetic trend qualification'}]
        doc['systems'][0]['discussion_genetics'][0]['visit_links'][0]['limitations'] = 'Synthetic limitation'
        data = {'document': doc, 'container': {}, 'version': '0.7.2', 'as_of': '2026-10-24',
            'disclaimer': 'Synthetic disclaimer', 'appendix_note': 'Synthetic reference only',
            'reference_appendix': {'included': True, 'panels': [{'label': 'Synthetic panel', 'positions': [
                {'gene': 'SYNTHETIC', 'rsid': 'rs123', 'passport': {'level': 'D', 'mechanism': 'Synthetic passport mechanism'}}]}]}}
        text = fmt.visit_report(data)
        for expected in ('Synthetic rare mechanism', 'Synthetic trend qualification',
                         'Synthetic limitation', 'Synthetic passport mechanism'):
            self.assertIn(expected, text)
