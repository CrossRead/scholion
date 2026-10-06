"""Regression examples from the public demo, with no real genome or profile."""
from __future__ import annotations

import copy
import unittest
from unittest import mock

import support  # noqa: F401 -- synthetic environment
from scholion import core, i18n
from scholion.clinical_claims import basis_lines, guard_fields
from scholion.engine import panel_form, system_panels as SP
from scholion.format_genome import longevity_report
from scholion.format_system import _system_gene_row


class TestIssue12(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        i18n.set_lang('en')

    def row(self, state='het', *, read=True, presumed=False, supported=False, written=True):
        p = copy.deepcopy(next(p for p in core._read_knowledge('system_gene_panels.json')
                               ['systems']['cardio']['positions'] if p['rsid'] == 'rs6025'))
        if not supported:
            p['source'] = 'unresolved primary reference'
            p['evidence']['source'] = ''
            p.pop('mechanism', None)
        if not written:
            p['text'] = {}
        geno = {'state': state, 'read': read, 'genotype': 'G/A', 'presumed': presumed}
        with mock.patch.object(SP, '_genotype', return_value=geno), \
             mock.patch.object(SP, '_has_alignment', return_value=False):
            return SP._curated_rows('cardio', {'positions': [p]}, [],
                                   {'status': 'ok', 'input_profile': 'whole_genome'}, {})['rows'][0]

    def test_withheld_f5_keeps_allele_presence_without_a_finding_or_recessive_carrier(self):
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            row = self.row()
            self.assertTrue(row['carrier'])
            self.assertFalse(row['clinical_carrier'])
            self.assertEqual(0, row['findings'])
            self.assertIsNone(row['text'])
            self.assertEqual('conclusion_basis', row['pending_why'])
            for register in ('patient', 'clinician'):
                projected = SP._project({'rows': [row]}, register)['rows'][0]
                self.assertTrue(projected['carrier'])
                self.assertFalse(projected['clinical_carrier'])
                text = _system_gene_row(projected, register)
                self.assertIn(i18n.t('system.row.allele_present'), text)
                self.assertIn(i18n.t('system.row.withheld'), text)
                self.assertNotIn(i18n.t('system.row.pending'), text)
            state = SP._position_state(row)
            self.assertTrue(state['carrier'])
            self.assertEqual('conclusion_basis', state['pending_why'])
            verdict = panel_form.verdict([row], {'status': 'ok'})
            self.assertEqual('not_determined', verdict['kind'])
            self.assertFalse(verdict.get('carriers'))
            questions = SP._questions({'rows': [row]}, {}, {}, {})['rows']
            self.assertTrue(any(q['origin'] == 'conclusion_basis' for q in questions))
            self.assertFalse(any(q['origin'] in ('pending', 'moi') for q in questions))

    def test_unknown_or_presumed_is_never_a_negative_allele_result(self):
        for state in ('het', 'hom', 'hemi', 'absent'):
            self.assertEqual(state != 'absent', self.row(state)['carrier'])
            self.assertIsNone(self.row(state, read=False)['carrier'])
            self.assertIsNone(self.row(state, presumed=True)['carrier'])
        self.assertIsNone(self.row('unread', read=False)['carrier'])
        self.assertIsNone(self.row('risk_allele_not_declared')['carrier'])

    def test_genuinely_unwritten_phrase_keeps_its_distinct_reason(self):
        row = self.row(supported=True, written=False)
        self.assertEqual('no_text_for_state', row['pending_why'])
        self.assertIn(i18n.t('system.row.pending'), _system_gene_row(row, 'clinician'))
        self.assertTrue(any(q['origin'] == 'pending' for q in SP._questions({'rows': [row]}, {}, {}, {})['rows']))

    def test_f5_has_own_support_without_restoring_old_treatment_advice(self):
        row = self.row(supported=True)
        self.assertEqual('complete', row['conclusion_basis']['status'])
        self.assertIn('8164741', row['source'])
        self.assertTrue(row['text'])
        self.assertTrue(row['carrier'])
        self.assertFalse(row['clinical_carrier'])
        self.assertEqual(0, row['findings'])
        self.assertNotIn('transdermal', row['text'])
        self.assertNotIn('5-fold', row['text'])

    def test_longevity_missing_claims_are_one_notice_without_losing_field_provenance(self):
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            row = guard_fields({}, {'gene': 'SYN1', 'rsid': 'rs1', 'genotype': 'AG',
                                    'label': 'unsupported', 'action': 'unsupported',
                                    'verdict_label': 'unsupported'}, ('label', 'action', 'verdict_label'))
            before = copy.deepcopy(row)
            lines = basis_lines(row, compact=True)
            self.assertEqual(1, len(lines))
            self.assertIn('label, action, verdict_label', lines[0])
            self.assertEqual(1, lines[0].count(i18n.t('conclusion.missing.mechanism')))
            rendered = longevity_report({'available': True, 'known': [row]})
            self.assertIn('AG', rendered)
            self.assertNotIn('unsupported', rendered)
            self.assertEqual(1, rendered.count(lines[0]))
            self.assertEqual(before, row)
            self.assertEqual(3, len(row['clinical_basis']))

    def test_compact_refusal_does_not_hide_a_supported_independent_field(self):
        row = guard_fields({'label_basis': {'source': 'PMID:1', 'mechanism': 'synthetic'}},
                           {'label': 'supported', 'action': 'unsupported'}, ('label', 'action'))
        self.assertEqual(2, len(basis_lines(row, compact=True)))
        self.assertIn('PMID:1', '\n'.join(basis_lines(row, compact=True)))
        self.assertEqual([], basis_lines({}, compact=True))

    def test_named_guideline_rows_and_lookup_notes_have_independent_sourced_context(self):
        from scholion.conclusion_basis import conclusion_basis
        wanted = {'rs6025', 'rs1799963', 'rs1800562', 'rs1050828', 'rs5030868',
                  'rs1800462', 'rs1142345', 'rs116855232', 'rs4148323', 'rs28929474',
                  'rs5742904', 'rs111033565', 'rs111033566'}
        seen = set()
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            core.reset_cache()
            for spec in core._read_knowledge('system_gene_panels.json')['systems'].values():
                for position in spec.get('positions', []):
                    if position['rsid'] in wanted:
                        seen.add(position['rsid'])
                        self.assertEqual('complete', conclusion_basis(position)['status'])
                        self.assertNotIn('review', position)
            for rsid in wanted:
                note = core.loci()['loci'][rsid]['note']
                self.assertTrue(note)
                self.assertNotIn('TRT', note)
                self.assertNotIn('CPIC guideline for irinotecan', note)
        self.assertEqual(wanted, seen)
