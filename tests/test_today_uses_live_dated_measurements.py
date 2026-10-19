"""Current measurements, annual history, and external imports share one view."""
from __future__ import annotations
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock
import support
from scholion import core, engine, server, i18n
from scholion.engine.goals import _phenotype_rows
from scholion.panel_reference import genome_context
from scholion.pgs_validation import validate
from pgs_support import calibrated

class LiveMeasurements(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name).resolve();self.addCleanup(support.pin_profile(self.root))
        self.today=date.today();self.month=self.today.isoformat()[:7]
        self.previous=f"{self.today.year-1}-{self.today.month:02d}"
        self.addCleanup(i18n.set_lang, getattr(i18n._state,'current',None))
        self.write('metrics.json',{'profile':{},'metrics':{'weight':{'name':'Weight','unit':'kg','series':[
            {'date':self.today.isoformat(),'value':77.0}]}}})
        self.write('wearable_trends.json',{'sources':{'garmin':{'metrics':{'Weight':{self.previous:85.0,self.month:81.0}}}}})
    def write(self,name,value):
        (self.root/name).write_text(json.dumps(value), encoding="utf-8");core.reset_cache()
    def test_manual_weight_is_not_replaced_by_same_month_device_average(self):
        rows=engine.lifestyle()['metrics'];manual=next(r for r in rows if r['key']=='Weight' and r['source'] is None)
        self.assertEqual(77,manual['value']);self.assertEqual(self.today.isoformat(),manual['date'])
        self.assertIsNone(manual['score']);self.assertIsNone(manual['trend'])
        self.assertEqual(77,engine._brief_life('Weight')['value'])
        self.assertEqual(1, len([r for r in rows if r['key'] == 'Weight']))
        self.assertEqual({'garmin', None}, {o['source'] for o in manual['measurement_series']})
        self.assertEqual(81, next(o for o in manual['measurement_series'] if o['source'] == 'garmin')['series'][-1]['value'])
    def test_phenotype_is_present_without_a_saved_personal_goal(self):
        result=engine.goal_dashboard();self.assertFalse(result['available'])
        self.assertEqual('Weight',result['phenotype'][0]['label'])
        self.assertEqual(77,result['phenotype'][0]['components'][0]['value'])
        self.assertNotIn('2021',json.dumps(result))
    def test_goal_and_measurement_row_do_not_duplicate_the_same_quantity(self):
        r=_phenotype_rows([{'label':'Personal weight goal','source':'wear:Weight','target':'Chosen target'}])
        self.assertEqual(1,len(r));self.assertEqual(77,r[0]['components'][0]['value'])
        self.assertIsNone(r[0]['components'][0]['year_delta'])
        self.assertEqual(3, len(r[0]['components'][0]['series']))
        self.assertNotIn('device_history', r[0]['components'][0])
    def test_device_specific_goal_keeps_its_own_device(self):
        r=_phenotype_rows([{'label':'Device weight','source':'wear:garmin:Weight'}])[0]
        self.assertEqual(81,r['components'][0]['value']);self.assertEqual('garmin',r['components'][0]['source'])
        self.assertEqual(-4,r['components'][0]['year_delta'])
    def test_annual_history_excludes_old_and_future_values_and_keeps_zero(self):
        series=[{'date':f'{self.today.year-2}-01-01','value':100},
                {'date':self.previous,'value':0},{'date':self.month,'value':2},
                {'date':f'{self.today.year+1}-01','value':9}]
        self.write('metrics.json',{'metrics':{'waist':{'name':'Synthetic','unit':'cm','series':series}}})
        component=_phenotype_rows([])[0]['components'][0]
        self.assertEqual(2,component['year_delta']);self.assertEqual(2,len(component['series']))
    def test_focus_raw_value_refreshes_after_data_change(self):
        self.write('focus.json',{'focus':{'title':'Synthetic focus','metric':{'kind':'life','key':'Weight','unit':'kg'}}})
        self.assertEqual(77,engine.focus_dashboard()['metric']['raw'])
        self.write('metrics.json',{'metrics':{'weight':{'name':'Weight','unit':'kg','series':[{'date':self.today.isoformat(),'value':76}]}}})
        self.assertEqual(76,engine.focus_dashboard()['metric']['raw'])
    def test_revision_changes_on_import_but_not_journal_access(self):
        before=server._profile_revision();self.assertEqual(before,server._profile_revision())
        (self.root/'container-journal.jsonl').write_text('synthetic access', encoding='utf-8')
        self.assertEqual(before,server._profile_revision())
        self.write('sleep_nightly.json',{'nights':[]});self.assertNotEqual(before,server._profile_revision())
        (self.root/'sleep_nightly.json').unlink();self.assertEqual(before,server._profile_revision())
    def test_unknown_population_is_missing_not_a_claimed_mismatch(self):
        row=calibrated({'pgs_id':'PGS000001'});row.pop('reference_panel_ancestry')
        reasons=validate(row,expected_ancestry='EUR')['calibration']['reasons']
        self.assertIn('reference_identity_missing',reasons);self.assertNotIn('reference_population_mismatch',reasons)
    def test_context_reuses_confidence_without_reclassifying_external_annotations(self):
        for language in ('en','ru'):
            i18n.set_lang(language)
            context=genome_context('GNMT','rs9296404')
            self.assertEqual('C',context['level']);self.assertTrue(context['reference_context']['gene_source'])
            unknown=genome_context('GNMT','rs999999999')
            self.assertEqual('E',unknown['level']);self.assertEqual('not_curated',unknown['reference_context']['variant_status'])
        self.assertEqual('not_supplied',genome_context('GNMT')['reference_context']['variant_status'])

    def test_gene_lookup_keeps_the_reading_and_exact_variant_confidence(self):
        from scholion import genome
        from scholion.engine import genomics
        data = {"status": "ok", "gene": "GNMT", "loci": [{"gene": "GNMT", "rsid": "rs9296404", "result": {"genotype": "AG", "confidence": "called"}}]}
        with mock.patch.object(genome, "lookup", return_value=data), \
             mock.patch.object(genomics, "gene_coverage", return_value={"state": "unknown"}), \
             mock.patch.object(genomics, "gene_layers", return_value={"status": "unknown"}):
            result = genomics.genome_lookup(gene="GNMT")
        self.assertEqual("C", result["loci"][0]["level"])
        self.assertEqual("AG", result["loci"][0]["result"]["genotype"])
        self.assertTrue(result["reference_context"]["gene_source"])
        self.assertEqual("not_supplied", result["reference_context"]["variant_status"])
    def test_clinvar_classification_does_not_promote_scholion_confidence(self):
        from scholion import genome
        from scholion.engine import genomics
        hit = {"gene": "GNMT|SYN1", "rsid": "rs9296404", "genotype": "0/1", "clnsig": "Pathogenic", "stars": 4}
        with mock.patch.object(genome, "clinvar_hits", return_value={"status": "ok", "hits": [hit]}), \
             mock.patch.object(genome, "clinvar_normalisation", return_value={"left_aligned": True}), \
             mock.patch.object(genomics, "_array_only_input", return_value=None), \
             mock.patch.object(genomics, "_input_boundary", return_value=None):
            result = genomics.clinvar_findings()
        row = result["hits"][0]
        self.assertEqual("Pathogenic", row["clnsig"])
        self.assertEqual("0/1", row["genotype"])
        self.assertEqual(["C", "E"], [c["level"] for c in row["gene_contexts"]])
    def test_significant_longevity_variants_keep_their_reading_beside_context(self):
        from scholion.engine import genomics
        data = {"_meta": {}, "known": [{"gene": "GNMT", "rsid": "rs9296404", "genotype": "AG"}], "significant_by_gene": {"GNMT": [{"rsid": "rs9296404", "genotype": "AG"}]}}
        with mock.patch.object(core, "longevity_data", return_value=data):
            result = genomics.longevity_findings()
        variant = result["significant_genes"][0]["variants"][0]
        self.assertEqual("AG", variant["genotype"])
        self.assertEqual("C", variant["level"])
        self.assertTrue(variant["reference_context"]["variant_source"])

    def test_today_activity_resolves_device_without_manual_entry(self):
        self.write('metrics.json', {'metrics': {'activity_min': {'name': 'Активность', 'unit': 'мин/день', 'series': []}}})
        self.write('wearable_trends.json', {'sources': {'garmin': {'metrics': {'IntensityMinutesDaily': {self.previous: 0, self.month: 25}}}}})
        row = _phenotype_rows([])[0]
        current = row['components'][0]
        self.assertEqual('Intensity minutes', row['label'])
        self.assertEqual(25, current['value'])
        self.assertEqual('garmin', current['source'])
        self.assertEqual(25, current['year_delta'])
        self.assertEqual('min/day', current['unit_display'])
        i18n.set_lang('ru')
        self.assertEqual('мин/день', _phenotype_rows([])[0]['components'][0]['unit_display'])

    def test_one_weight_card_retains_older_manual_series_when_device_is_newer(self):
        self.write('metrics.json', {'metrics': {'weight': {'name': 'Вес', 'unit': 'kg', 'series': [{'date': self.previous + '-15', 'value': 84}]}}})
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            rows = [r for r in engine.lifestyle()['metrics'] if r['key'] == 'Weight']
            self.assertEqual(1, len(rows))
            self.assertEqual(81, rows[0]['value'])
            self.assertEqual('Weight' if language == 'en' else 'Вес', rows[0]['label'])
            self.assertEqual(2, len(rows[0]['measurement_series']))

    def test_factual_fitness_report_does_not_emit_clinical_support_gaps(self):
        from scholion import format as fmt
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            report = fmt.lifestyle_report(engine.lifestyle())
            self.assertNotIn(i18n.t('conclusion.missing.mechanism'), report)
            self.assertNotIn('PMID/DOI', report)
        html = (support.ROOT / 'src/scholion/web/index.html').read_text(encoding='utf-8')
        card = html[html.index('function lifeCard(m)'):html.index('function briefSections(b)')]
        self.assertNotIn('clinicalBasisHTML(m)', card)

    def test_unselected_device_weights_are_one_card_without_a_claimed_current_value(self):
        self.write('metrics.json', {'metrics': {}})
        self.write('wearable_trends.json', {'sources': {
            'garmin': {'metrics': {'Weight': {self.month: 81}}},
            'whoop': {'metrics': {'Weight': {self.month: 82}}}}})
        with mock.patch.object(core, 'wearable_primary', return_value=None):
            rows = [m for m in engine.lifestyle()['metrics'] if m['key'] == 'Weight']
        self.assertEqual(1, len(rows))
        self.assertIsNone(rows[0]['value'])
        self.assertIsNone(rows[0]['score'])
        self.assertFalse(rows[0]['counts_toward_conclusions'])
        self.assertEqual(2, len(rows[0]['measurement_series']))

    def test_partial_pgs_explains_vcf_without_assuming_a_bam(self):
        from scholion.engine import genomics
        from scholion import format as fmt
        row = calibrated({'pgs_id': 'PGS000001', 'label': 'Synthetic trait', 'term': 'synthetic', 'percentile': 95, 'match_rate': 0.8})
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            with mock.patch.object(core, 'prs_results', return_value={'_meta': {'superpopulation': 'EUR'}, 'traits': [row]}), mock.patch.object(genomics, '_array_only_input', return_value=None):
                result = genomics.prs_findings()
            trait = result['categories'][0]['traits'][0]
            self.assertFalse(trait['reliable'])
            self.assertEqual([], result['high'])
            self.assertIn('VCF', trait['reading_note'])
            self.assertIn('BAM', trait['reading_note'])
            self.assertIn(trait['reading_note'], fmt.prs_report(result))
