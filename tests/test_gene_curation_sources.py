"""Gene-level reference text and source verification must remain separately scoped."""
from datetime import date
import json
import shutil
import unittest

import gene_card_support

import support  # noqa: F401
from scholion import core, i18n
from scholion.panel_reference import genome_context, reference_lines
from scholion.scientific_review import context_review, source_refresh_status


class TestGeneCurationSources(unittest.TestCase):
    def test_month_boundary_uses_calendar_dates_including_month_end(self):
        self.assertEqual(source_refresh_status('2026-11-04', date(2027, 2, 4)), 'current')
        self.assertEqual(source_refresh_status('2026-11-04', date(2027, 2, 5)), 'due')
        self.assertEqual(source_refresh_status('2026-11-30', date(2027, 2, 28)), 'current')
        self.assertEqual(source_refresh_status('2026-11-30', date(2027, 3, 1)), 'due')
        for invalid in (None, 'bad date', '2026-02-29', '2099-01-01'):
            self.assertEqual(source_refresh_status(invalid, date(2026, 11, 4)), 'date_unknown')

    def test_source_names_preserve_scope_without_using_import_date(self):
        result = context_review('SYNTHETIC', '', {
            'gene_source': 'https://www.uniprot.org/uniprotkb/P02458/entry',
            'gene_checked_on': '2000-01-01',
            'gene_additional_sources': ['https://www.ncbi.nlm.nih.gov/gene/1280'],
            'gencc_assertions': [{'disease': 'Synthetic condition'}],
            'gencc_source': 'https://thegencc.org/',
            'gencc_version': '2026-10-01',
        })
        function, disease = result
        self.assertEqual(function['scope'], 'gene_function')
        self.assertEqual([s['name'] for s in function['source_details']],
                         ['UniProtKB / Swiss-Prot', 'NCBI Gene / RefSeq'])
        self.assertEqual([s['refresh_status'] for s in function['source_details']],
                         ['due', 'date_unknown'])
        self.assertEqual(disease['scope'], 'gene_disease')
        self.assertEqual(disease['source_details'][0]['refresh_status'], 'date_unknown')

    def test_catalogue_supplies_every_registered_entry_in_both_languages(self):
        book = core._read_knowledge_raw('gene_curation.json')
        genes = book['genes']
        self.assertEqual(len(genes), book['_meta']['catalogue_entries'])
        self.assertGreaterEqual(len(genes), 4295)
        for symbol, entry in genes.items():
            self.assertIn(entry['curation_status'], ('source_derived', 'reviewed_text', 'identity_only'), symbol)
            for key in ('description', 'patient_summary'):
                self.assertEqual(set(entry[key]), {'en', 'ru'}, symbol)
                self.assertTrue(all(isinstance(value, str) and value.strip()
                                    for value in entry[key].values()), symbol)
            self.assertTrue(entry['source'].startswith('https://'), symbol)
            self.assertNotIn('clinical_eligibility', entry, symbol)

    def test_exact_historical_label_retains_its_locus_mapping(self):
        self.assertEqual(genome_context('LRP', 'rs3736228')['reference_context']['canonical_symbol'], 'LRP5')
        unassigned = genome_context('LRP', 'rs999999999')['reference_context']
        self.assertEqual(unassigned['canonical_symbol'], 'LRP')
        self.assertEqual(unassigned['function_status'], 'identity_only')

    def test_catalogue_links_and_explanations_reach_agent_and_cli(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            answer = genome_context('COL2A1')
            context = answer['reference_context']
            self.assertTrue(context['gene_role'])
            self.assertTrue(context['gene_function'])
            self.assertIn('UniProtKB / Swiss-Prot', '\n'.join(reference_lines(answer)))
            self.assertNotIn('⟦', '\n'.join(reference_lines(answer)))
            self.assertEqual(context['variant_status'], 'not_supplied')

    def test_catalogue_membership_keeps_conflicting_study_results_separate_from_effect(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        i18n.set_lang('en')
        context = genome_context('GSR', 'rs1002149')['reference_context']
        study = next(item for item in context['scientific_review'] if item['scope'] == 'study_membership')
        self.assertIn('different results', study['patient_summary'])
        self.assertIn('no estimate for your allele', study['patient_summary'])
        self.assertTrue(all(item['name'] == 'PubMed' for item in study['source_details']))

    @unittest.skipUnless(shutil.which('node'), 'requires the actual card renderer')
    def test_card_discloses_named_record_and_refresh_steps(self):
        reviews = context_review('SYNTHETIC', '', {
            'gene_source': 'https://www.uniprot.org/uniprotkb/P02458/entry',
            'gene_checked_on': '2000-01-01',
        })
        script = gene_card_support.javascript() + r"""
const assert=require('node:assert/strict');
const reviews=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const escape=x=>String(x??'').replaceAll('<','&lt;').replaceAll('"','&quot;');
const t=(key,args={})=>key+JSON.stringify(args);
const html=ScholionGeneCards.render({gene:'SYNTHETIC',reference_context:{scientific_review:reviews}},
                                   {t,escape,grade:escape});
assert.ok(html.includes('UniProtKB / Swiss-Prot'));
assert.ok(html.includes('href="https://www.uniprot.org/uniprotkb/P02458/entry"'));
assert.ok(html.includes('2000-01-01'));
assert.ok(html.includes('data-source-refresh'));
assert.ok(html.includes('science.source_due'));
assert.ok(html.includes('science.source_refresh_steps'));
"""
        result = gene_card_support.run(script, input=json.dumps(reviews), text=True,
                                       capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
