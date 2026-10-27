"""Reference topics preserve reading limits and the existing system contract."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from unittest import mock

import support
import gene_card_support
from scholion import core, genome, i18n
from scholion.engine import panel_description, system
from scholion.engine import thematic_panels
from scholion.format_genome import panel_report


class TestThematicGenePanels(unittest.TestCase):
    def test_mechanism_context_uses_current_measurements_without_a_variant_effect(self):
        from scholion.engine import labs
        observations={'markers':[{'key':'homocysteine','name':'Homocysteine','value':9.3,'unit':'umol/L',
                                   'date':'2026-10-23','display_recency':True,'source':'synthetic-form'}]}
        with mock.patch.object(labs,'analyze_labs',return_value=observations), \
             mock.patch.object(genome,'available',return_value={'ready':False}), \
             mock.patch.object(core,'profile_genotypes',return_value={}):
            panel=system('methylation')
        gene=next(g for g in panel['genes'] if g['gene']=='MTHFR')
        compared=gene['personal_comparison']
        self.assertFalse(compared['personal_variant_effect_established'])
        self.assertEqual(compared['observations'][0]['value'],9.3)
        self.assertEqual(compared['observations'][0]['source'],'synthetic-form')
        self.assertIn('9.3',panel_report(panel))
        observations['markers'][0]['display_recency']=False
        with mock.patch.object(labs,'analyze_labs',return_value=observations), \
             mock.patch.object(genome,'available',return_value={'ready':False}), \
             mock.patch.object(core,'profile_genotypes',return_value={}):
            old=system('methylation')
        self.assertEqual(next(g for g in old['genes'] if g['gene']=='MTHFR')['personal_comparison']['observations'],[])

    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_reference_works_without_personal_files_and_keeps_gene_and_variant_scopes(self):
        with mock.patch.object(genome, 'available', side_effect=AssertionError('reference reads no genome')), \
             mock.patch.object(core, 'profile_genotypes', side_effect=AssertionError('reference reads no person')):
            book = panel_description('methylation')
        self.assertTrue(book['reference_only'])
        self.assertIn('BHMT', [g['gene'] for g in book['genes']])
        self.assertNotIn('score', book)
        for gene in book['genes']:
            self.assertTrue(gene['reference_context']['gene_source'], gene['gene'])
            self.assertIsNone(gene['level'])
            self.assertNotIn('genotype', gene)
            self.assertEqual(gene['reading_request'], {
                'command': 'genome', 'tool': 'sch_genome_lookup',
                'gene': gene['reference_context']['canonical_symbol'],
                'scope': 'gene_region_on_request'})
            for position in gene['positions']:
                self.assertIn(position['level'], 'ABCDE')
                self.assertNotIn('reading', position)

    def test_every_gene_has_an_explicit_reading_door_but_a_region_is_not_a_gene(self):
        with mock.patch.object(genome, 'available', side_effect=AssertionError('no automatic scan')):
            for key in thematic_panels.thematic_catalogue()['panels']:
                book=panel_description(key)
                for gene in book['genes']:
                    self.assertEqual(gene['reading_request']['gene'],
                                     gene['reference_context']['canonical_symbol'], (key,gene['gene']))
                for region in book['regions']:
                    self.assertNotIn('reading_request',region)
        text=panel_report(panel_description('methylation'))
        self.assertIn('scholion genome --gene AHCY',text)

    def test_neuro_panels_keep_research_and_clinical_assertions_separate(self):
        research = panel_description('neuro_associations')
        clinical = panel_description('neuro_clinical')
        self.assertEqual(research['kind'], 'research_associations')
        self.assertEqual(clinical['kind'], 'clinical_gene_disease_reference')
        self.assertIn('COMT', [r['gene'] for r in research['genes']])
        self.assertNotIn('GBA1', [r['gene'] for r in research['genes']])
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            clinical = panel_description('neuro_clinical')
            gad1 = next(g for g in clinical['genes'] if g['gene'] == 'GAD1')
            context = gad1['reference_context']
            classes = {a['classification'] for a in context['gencc_assertions']}
            self.assertTrue({'Limited', 'Strong', 'Definitive'} <= classes)
            self.assertEqual(context['gencc_version'], '2026-10-14')
            self.assertIsNone(context['level'])
            for a in context['gencc_assertions']:
                self.assertTrue(a['submission_id'])
                self.assertTrue(a['submitter'])
                self.assertTrue(a['curated_on'])
                if language == 'ru':
                    self.assertRegex(a['disease_label'], '[А-Яа-я]')

    def test_only_positive_local_calls_are_rendered_as_genotypes(self):
        with mock.patch.object(genome, 'available', return_value={'ready': True}), \
             mock.patch.object(core, 'profile_genotypes', return_value={}), \
             mock.patch.object(genome, '_gt_at', return_value={'confidence': 'assumed_ref', 'genotype': 'AA'}), \
             mock.patch.object(genome, 'resolve_rsid', return_value={'chrom': '1', 'pos': 1, 'ref': 'A', 'alt': 'G'}):
            saved = system('methylation')
        self.assertTrue(saved['patient_readings'])
        self.assertGreater(saved['counts']['positions'], 0)
        self.assertEqual(saved['counts']['read'], 0)
        for position in saved['positions']:
            self.assertIsNone(position['reading']['genotype'])
            self.assertEqual(position['reading']['reason'], 'not_positively_read')
        with mock.patch.object(genome, 'available', return_value={'ready': True}), \
             mock.patch.object(core, 'profile_genotypes', return_value={}), \
             mock.patch.object(genome, '_gt_at', return_value={'confidence': 'called', 'genotype': 'AG', 'depth': 28, 'source': 'vcf'}), \
             mock.patch.object(genome, 'resolve_rsid', return_value={'chrom': '1', 'pos': 1, 'ref': 'A', 'alt': 'G'}):
            positive = system('methylation', 'clinician')
        self.assertEqual(positive['counts']['read'], positive['counts']['positions'])
        self.assertTrue(all(p['reading']['genotype'] == 'AG' and p['reading']['depth'] == 28
                            for p in positive['positions']))
        self.assertIn('AG', panel_report(positive))
        self.assertEqual(system('methylation', 'unknown')['status'], 'unknown_register')

    def test_gene_counts_are_not_substituted_for_position_counts_or_system_axes(self):
        from scholion.engine.system_panels import domains
        listed = panel_description()['systems']
        themes = [row for row in listed if row.get('thematic')]
        self.assertTrue(themes)
        self.assertTrue(all(r['positions'] is None and r['genes'] > 0 for r in themes))
        self.assertEqual(len(domains()), 16)
        additional = panel_description('additional_genetics')
        self.assertNotIn('HHEX-IDE', [g['gene'] for g in additional['genes']])
        self.assertEqual(additional['regions'], [])
        self.assertEqual([g['gene'] for g in panel_description('metabolic_genetics')['regions']], ['HHEX-IDE'])
        self.assertEqual(additional['counts']['genes'], len(additional['genes']))
        self.assertEqual([r['key'] for r in thematic_panels.thematic_summaries('amino_acids')],
                         ['amino_genetics', 'methylation'])
        report = panel_report({'systems': themes})
        for row in themes:
            self.assertIn(row['label'], report)
            self.assertIn(row['key'], report)

    def test_ambiguous_submitted_label_uses_exact_variant_identity(self):
        from scholion.panel_reference import genome_context
        context = genome_context('CALC','rs1801197')['reference_context']
        self.assertEqual(context['canonical_symbol'],'CALCR')
        self.assertIn('/799', context['gene_source'])
        self.assertNotIn('mitochondrial calcium uptake', context['gene_function'].lower())

    @unittest.skipUnless(shutil.which('node'), 'requires node for actual renderers')
    def test_shared_renderer_keeps_function_first_and_refused_readings_empty(self):
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding="utf-8")
        functions = []
        for name in ('thematicPanelLinks', 'renderThematicPanel'):
            start = page.index('function ' + name + '(')
            functions.append(page[start:page.index('\n}\n', start) + 2])
        script = """
const assert=require('node:assert/strict');
const esc=x=>String(x??''), t=(k,a)=>k+' '+Object.values(a||{}).join(' ');
const pageHead=(h,n,f)=>h+n+f.join(''),factHtml=(v,n)=>v+n,levelChip=String,geneticBriefHtml=()=>'';
const referenceContextHtml=g=>g.reference_context.gene_source;
const genomeGeneTable=rows=>rows.map(row=>JSON.stringify({rsid:row.rsid,genotype:row.genotype,note:row.reading?.note})).join('');
""" + '\n'.join(functions) + """
const gene={gene:'SYNTHETIC',reference_context:{gene_function:'Known function',gene_source:'https://example.org'},
 reading_request:{gene:'CANONICAL'},
 positions:[{rsid:'rsSynthetic',reading:{read:false,genotype:'AA',message:'Not read'}}]};
const html=renderThematicPanel({label:'Topic',counts:{genes:1},genes:[gene]});
assert.ok(html.includes('Known function')&&html.includes('rsSynthetic'));
assert.ok(html.indexOf('gene-card-reading')<html.indexOf('gene-card-description'));
assert.ok(!html.includes('>AA<'));
assert.ok(html.includes('data-thematic-gene="SYNTHETIC"'));
assert.ok(html.includes('data-read-gene="CANONICAL"'));
const links=thematicPanelLinks([{key:'methylation',label:'Methylation',genes:44}]);
assert.ok(links.includes('data-system="methylation"'));
assert.ok(!links.includes('data-panel="methylation"'));
"""
        script = gene_card_support.javascript() + script
        result = gene_card_support.run(script, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
