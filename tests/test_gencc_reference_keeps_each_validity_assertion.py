"""Gene biology must retain disagreement and never become variant evidence."""
import re
import shutil
import subprocess
import unittest

import support
from scholion import core, i18n
from scholion.engine import system_panels
from scholion.format_system import _system_gene_row
from scholion.panel_reference import gene_reference_context, reference_lines


class TestGenCCReference(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        i18n.set_lang('en')

    def test_full_existing_gene_set_has_source_bound_biology_without_a_variant_grade(self):
        base = core._read_knowledge_raw('gencc_gene_disease.json')
        book = core._read_knowledge_raw('gencc_reference_context.json')
        genes = {gene for panel in base['systems'].values() for gene in panel['genes']}
        self.assertEqual(1469, len(genes))
        self.assertEqual(genes, set(book['genes']))
        for gene, entry in book['genes'].items():
            self.assertEqual('gene_function', entry['scope'], gene)
            self.assertNotIn('level', entry)
            self.assertNotIn('review', entry)
            self.assertIn('https://www.ncbi.nlm.nih.gov/gene/', entry['source'])
            self.assertEqual({'en', 'ru'}, set(entry['description']))
            self.assertRegex(entry['description']['ru'], r'[\u0400-\u04ff]')
            self.assertRegex(entry['hgnc_id'], r'^HGNC:\d+$')

    def test_disagreeing_assertions_are_retained_with_their_diseases_and_submitters(self):
        raw = core._read_knowledge_raw('gencc_gene_disease.json')['systems']['lipids']['genes']['ABCA1']['submissions']
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            row = next(r for r in system_panels._base_rows('lipids')['rows'] if r['gene'] == 'ABCA1')
            context = row['reference_context']
            self.assertIsNone(context['level'])
            self.assertEqual('not_supplied', context['variant_status'])
            self.assertEqual(len(raw), len(context['gencc_assertions']))
            for original, displayed in zip(raw, context['gencc_assertions']):
                for key in ('disease', 'disease_id', 'classification', 'moi', 'submitter', 'curated_on'):
                    self.assertEqual(original[key], displayed[key])
            labels = {a['classification_label'] for a in context['gencc_assertions']}
            self.assertIn(i18n.t('gencc.class.Definitive'), labels)
            self.assertIn(i18n.t('gencc.class.Limited'), labels)
            rendered = _system_gene_row(row, 'clinician')
            self.assertIn(i18n.t('gencc.class.Limited'), rendered)
            self.assertIn('GenCC', rendered)
            if language == 'ru':
                for assertion in context['gencc_assertions']:
                    self.assertRegex(assertion['disease_label'], r'[\u0400-\u04ff]')

    def test_reference_context_does_not_promote_moderate_identity_conflicts(self):
        i18n.set_lang('ru')
        rows = system_panels._base_rows('immune')['rows']
        for gene, other in [('MST1', 'STK4'), ('CSF3', 'CSF3R')]:
            row = next(r for r in rows if r['gene'] == gene)
            self.assertFalse(row['finding_grade'])
            self.assertEqual(['Moderate'], row['classifications'])
            self.assertIn(other, row['reference_context']['limitations'])
            self.assertIsNone(row['reference_context']['variant_source'])

    def test_missing_reference_remains_an_explicit_gap(self):
        context = gene_reference_context('NOT_A_GENE', [])
        self.assertEqual(i18n.t('reference.gene_unknown'), context['gene_function'])
        self.assertIsNone(context['gene_source'])
        self.assertEqual([], context['gencc_assertions'])
        self.assertIn(i18n.t('reference.gene_level'), reference_lines({'reference_context': context}))
        self.assertEqual([], reference_lines({}))

    def test_patient_reference_retains_each_base_status_without_becoming_a_finding(self):
        row = next(r for r in system_panels._base_rows('lipids')['rows'] if r['gene'] == 'ABCA1')
        row.update(findings=0, carrier=False, pending=False)
        projected = system_panels._project({'rows': [row]}, 'patient')['rows'][0]
        self.assertEqual(row['reference_context'], projected['reference_context'])
        self.assertEqual(row['classifications'], projected['classifications'])
        self.assertEqual(row['moi_codes'], projected['moi_codes'])
        self.assertEqual(0, projected['findings'])
        self.assertFalse(projected['carrier'])
        self.assertFalse(projected['pending'])
        self.assertNotIn('level', row)

    def test_every_stored_status_and_inheritance_has_a_display_label(self):
        base = core._read_knowledge_raw('gencc_gene_disease.json')
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            for panel in base['systems'].values():
                for entry in panel['genes'].values():
                    for assertion in entry['submissions']:
                        for prefix, field in [('gencc.class.', 'classification'), ('gencc.moi.', 'moi')]:
                            key = prefix + assertion[field]
                            self.assertIn(key, i18n.CATALOGUES[language])
                            if language == 'ru':
                                self.assertTrue(re.search(r'[\u0400-\u04ff]', i18n.t(key)))

    @unittest.skipUnless(shutil.which('node'), 'needs node for the page JavaScript')
    def test_unknown_gene_reading_is_never_rendered_as_a_negative_result(self):
        page = (support.ROOT / 'src/scholion/web/index.html').read_text(encoding='utf-8')
        start = page.index('function geneStateBadge(')
        function = page[start:page.index('\n}\n', start) + 2]
        script = """
const assert=require('node:assert/strict');
const t=key=>key, badge=(cls,text)=>({cls,text});
""" + function + """
for(const row of [{},{read:null},{read:false}]){
  const before=JSON.stringify(row);
  assert.equal(geneStateBadge(row).text,'system.gen.state.unread');
  assert.equal(JSON.stringify(row),before);
}
assert.equal(geneStateBadge({read:true}).text,'system.gen.state.clear');
assert.equal(geneStateBadge({findings:1}).text,'system.gen.state.finding');
assert.equal(geneStateBadge({carrier:true}).text,'system.gen.state.carrier');
"""
        result = subprocess.run(['node', '-e', script], capture_output=True,
                                text=True, timeout=20, stdin=subprocess.DEVNULL)
        self.assertEqual(0, result.returncode, result.stderr)
