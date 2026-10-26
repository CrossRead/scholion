"""Repeated system joins share work, never another answer or a mutable result."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import core, i18n, panel_reference
from scholion.engine import genomics, system_panels
from scholion.engine.insight_events import _treatment_context


class TestSharedInsightReading(unittest.TestCase):
    def test_clinical_index_is_read_once_and_copies_do_not_modify_other_systems(self):
        hit = {'gene': 'GENE', 'tier': 'pathogenic', 'genotype': '0/1',
               'personal_context': {'status': 'carrier_context'}}
        with patch.object(genomics, 'clinvar_findings', return_value={'status': 'ok', 'hits': [hit]}) as read:
            with core.reading_session():
                first = system_panels._clinvar_by_gene({'status': 'ok'})
                first['by_gene']['GENE'][0]['personal_context']['status'] = 'changed'
                second = system_panels._clinvar_by_gene({'status': 'ok'})
                self.assertEqual('carrier_context', second['by_gene']['GENE'][0]['personal_context']['status'])
                self.assertEqual(1, read.call_count)
                refused = system_panels._clinvar_by_gene({'status': 'no_genome', 'reason': 'Synthetic absent input'})
                self.assertEqual({}, refused['by_gene'])
                self.assertEqual('no_genome', refused['status'])
                self.assertEqual(1, read.call_count)
            read.return_value = {'status': 'ok', 'hits': []}
            with core.reading_session():
                self.assertEqual({}, system_panels._clinvar_by_gene({'status': 'ok'})['by_gene'])
            self.assertEqual(2, read.call_count)

    def test_acmg_fallback_is_shared_without_turning_its_scope_into_full_clinvar(self):
        answer = {'status': 'ok', 'hits': [{'gene': 'GENE', 'clnsig': 'Pathogenic', 'reportable': 'carrier_only'}]}
        with patch.object(genomics, 'clinvar_findings', return_value={'status': 'not_run'}), \
                patch.object(genomics, 'acmg_findings', return_value=answer) as read:
            with core.reading_session():
                a = system_panels._clinvar_by_gene({'status': 'ok'})
                b = system_panels._clinvar_by_gene({'status': 'ok'})
            self.assertEqual(a, b)
            self.assertEqual('acmg_scan', a['status'])
            self.assertIn('GENE', a['by_gene'])
            self.assertEqual(1, read.call_count)

    def test_gene_biology_is_cached_per_language_and_only_inside_one_answer(self):
        old = i18n.lang()
        self.addCleanup(i18n.set_lang, old)
        with patch.object(panel_reference, '_gene_entry', wraps=panel_reference._gene_entry) as lookup:
            with core.reading_session():
                i18n.set_lang('en')
                first = panel_reference.gene_function_entry('SNUPN')
                count = lookup.call_count
                original = first['description']
                first['knowledge']['id'] = 'changed'
                again = panel_reference.gene_function_entry('SNUPN')
                self.assertEqual(count, lookup.call_count)
                self.assertNotEqual('changed', again['knowledge']['id'])
                i18n.set_lang('ru')
                russian = panel_reference.gene_function_entry('SNUPN')
                self.assertGreater(lookup.call_count, count)
                self.assertNotEqual(original, russian['description'])
            count = lookup.call_count
            with core.reading_session():
                self.assertEqual(russian, panel_reference.gene_function_entry('SNUPN'))
            self.assertGreater(lookup.call_count, count)

    def test_treatment_windows_keep_completed_courses_and_classify_each_record_once(self):
        medications = [{'name': 'Synthetic A', 'status': 'completed_2026-02-01', 'start_date': '2025-01-01'},
                       {'name': 'Synthetic B', 'status': 'active', 'start_date': '2026-03-01'}]
        domains = {'domains': [{'key': 'lipids', 'markers': ['ldl']}, {'key': 'liver', 'markers': ['ast']}]}
        classify = lambda med: {'systems': ['lipids'] if med['name'] == 'Synthetic A' else ['lipids', 'liver']}
        with patch.object(core, 'medications_json', return_value={'medications': medications}), \
                patch.object(core, '_read_knowledge_raw', return_value=domains), \
                patch.object(system_panels, 'medication_system_context', side_effect=classify) as read:
            with core.reading_session():
                broad = _treatment_context('ldl', '2026-01-01', '2026-04-01')
                liver = _treatment_context('ast', '2026-01-01', '2026-04-01')
                recent = _treatment_context('ldl', '2026-03-01', '2026-04-01')
                self.assertEqual(['Synthetic A', 'Synthetic B'], [r['drug'] for r in broad])
                self.assertFalse(broad[0]['current'])
                self.assertTrue(broad[1]['current'])
                self.assertEqual(['Synthetic B'], [r['drug'] for r in liver])
                self.assertEqual(['Synthetic B'], [r['drug'] for r in recent])
                self.assertEqual(2, read.call_count)
            medications.append({'name': 'Synthetic C', 'status': 'active', 'start_date': '2026-03-15'})
            with core.reading_session():
                newest = _treatment_context('ast', '2026-03-01', '2026-04-01')
            self.assertEqual(['Synthetic B', 'Synthetic C'], [r['drug'] for r in newest])
            self.assertEqual(5, read.call_count)
