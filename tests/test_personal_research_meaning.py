"""A molecular hypothesis is useful without borrowing a clinical action rule."""
from __future__ import annotations

from copy import deepcopy
import json
import shutil
import unittest
from unittest import mock

import gene_card_support
import support
from scholion import core, i18n
from scholion.panel_reference import genome_context, reference_lines
from scholion.personal_meaning import attach, describe


class ResearchMeaning(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        i18n.set_lang('en')

    def row(self, gene='FOXO3', rsid='rs13217795', genotype='TT', **flags):
        locus = core.loci()['loci'][rsid]
        return {**genome_context(gene, rsid), 'reading': {
            'confidence': 'called', 'genotype': genotype, 'depth': 23,
            'assembly': 'GRCh38', 'read_pos': locus['pos'], 'ref': locus['ref'],
            'variant_identity': {'assembly': 'GRCh38', 'chrom': str(locus['chrom']),
                                 'pos': locus['pos'], 'ref': locus['ref']},
            **({'source': 'vcf', 'interpretation_restriction': 'literal_catalogue_only'}
               if locus.get('allele_identity', {}).get('scope') == 'literal_genotype_only' else {}),
            **flags}}

    def test_both_sides_of_the_comparison_are_meaningful_without_an_action(self):
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            rows = [attach(self.row(genotype=gt)) for gt in ('TT', 'CT', 'CC')]
            self.assertEqual(3, len({r['personal_meaning']['summary'] for r in rows}))
            for row in rows:
                meaning = row['personal_meaning']
                self.assertEqual('genotype_hypothesis', meaning['status'])
                self.assertEqual('separate_assessment', meaning['action']['status'])
                self.assertFalse(meaning['clinical_eligibility_upgrade'])
                self.assertIn(meaning['summary'], '\n'.join(reference_lines(row)))
                self.assertIn('34436732', str(meaning['sources']))
                self.assertNotIn('⟦', str(meaning))
            self.assertIn('TT', rows[0]['personal_meaning']['limitations'])

    def test_missing_or_unsafe_reading_keeps_the_study_not_a_personal_conclusion(self):
        for flags in ({'confidence': 'assumed_ref'}, {'depth': 7}, {'depth': None},
                      {'filtered': True}, {'conflict': {'kind': 'source_disagreement'}},
                      {'interpretation_applicable': False, 'interpretation_restriction': 'unknown'},
                      {'strand_ambiguous': True}, {'assembly': 'unknown'}, {'variant_identity': {}}):
            row = self.row(**flags)
            result = describe(row)
            self.assertEqual('reference_only', result['status'], flags)
            self.assertEqual('research_context', result['scope'])
            self.assertNotIn('you may', result['summary'])
        for genotype in ('GG', '0/1', 'T', './.', 'TCG'):
            result = describe(self.row(genotype=genotype))
            self.assertEqual('reference_only', result['status'], genotype)
        self.assertEqual(describe(self.row(genotype='C|T'))['summary'],
                         describe(self.row(genotype='TC'))['summary'])

    def test_prescribing_and_inheritance_contexts_keep_their_own_question(self):
        for mode in ('pgx', 'monogenic'):
            row = self.row('ABCG2', 'rs2231142', 'GT')
            row['mode'] = mode
            row['interpretation'] = {'summary': 'Synthetic verified drug-specific meaning.',
                                     'source': 'PMID:35152405', 'personalized': True}
            row['reference_context'].update(variant_status='described',
                variant_context='Synthetic drug disposition mechanism.', variant_source='PMID:35152405')
            meaning = describe(row)
            self.assertEqual('catalogue_interpretation', meaning['status'])
            self.assertEqual(row['interpretation']['summary'], meaning['summary'])
            self.assertNotIn('gout', meaning['summary'])
            row['reading']['depth'] = 3
            meaning = describe(row)
            self.assertEqual('research_context', meaning['scope'])
            self.assertEqual(row['reference_context']['variant_context'], meaning['summary'])

    def test_changed_identity_invalidates_the_authored_genotype_comparison(self):
        with mock.patch('scholion.personal_meaning.record', return_value={'record_digest': 'changed'}):
            result = describe(self.row())
        self.assertEqual('review_stale', result['status'])
        self.assertNotEqual('genotype_hypothesis', result['scope'])

    def test_verified_catalogue_sentence_precedes_general_study_context(self):
        row = self.row('MTHFR', 'rs1801133', 'GA')
        row['interpretation'] = {'summary': 'Synthetic verified genotype comparison.',
                                 'personalized': True, 'source': 'https://example.org/study'}
        row['reference_context']['scientific_review'] = [{
            'scope': 'variant', 'patient_summary': 'Synthetic general study description.'}]
        meaning = describe(row)
        self.assertEqual('catalogue_interpretation', meaning['status'])
        self.assertEqual(row['interpretation']['summary'], meaning['summary'])
        row['interpretation']['personalized'] = False
        self.assertEqual('research_context', describe(row)['scope'])
        self.assertEqual('Synthetic general study description.', describe(row)['summary'])

    def test_comt_and_urate_compare_actual_alleles_without_promoting_a_diagnosis(self):
        comt = describe(self.row('COMT', 'rs4680', 'GA'))
        self.assertIn('Val/Met', comt['summary'])
        self.assertIn('Lower COMT activity than Val/Val', comt['summary'])
        self.assertEqual('genome', comt['limitations_scope'])
        absent = describe(self.row('ABCG2', 'rs2231142', 'GG'))
        carried = describe(self.row('ABCG2', 'rs2231142', 'GT'))
        self.assertIn('absent', absent['summary'])
        self.assertIn('higher uric acid', carried['summary'])
        self.assertFalse(carried['clinical_eligibility_upgrade'])

    def test_existing_associations_are_reused_for_presence_and_absence(self):
        present = describe(self.row('MTNR1B', 'rs10830963', 'CG'))
        absent = describe(self.row('MTNR1B', 'rs10830963', 'CC'))
        self.assertEqual('genotype_hypothesis', present['status'])
        self.assertIn('glucose', present['summary'])
        self.assertIn('opposite effect', absent['summary'])
        self.assertEqual('absent', absent['associations'][0]['state'])
        heterozygous = describe(self.row('MTHFR', 'rs1801133', 'AG'))
        self.assertNotIn('associations', heterozygous)
        excluded = describe(self.row('FADS1', 'rs174546', 'CT'))
        self.assertNotIn('associations', excluded)
        apoe = describe(self.row('APOE', 'rs429358', 'CT'))
        self.assertNotIn('associations', apoe)

    def test_lookup_and_longevity_receive_the_same_reading_specific_meaning(self):
        from scholion.engine import genomics
        from scholion.panel_reference import longevity_interpretation
        row = self.row()
        spec = core._read_knowledge('longevity_directions.json')['directions']['rs13217795']
        with mock.patch('scholion.core.genotype_status', return_value=row['reading']), \
             mock.patch('scholion.genome.lookup', return_value={
                 'gene': 'FOXO3', 'rsid': 'rs13217795', 'result': row['reading']}), \
             mock.patch.object(genomics, 'gene_coverage', return_value={}), \
             mock.patch.object(genomics, 'locus_basis', return_value={}):
            lookup = genomics.genome_lookup(rsid='rs13217795')
            longevity = longevity_interpretation(row, spec)
        self.assertEqual(describe(row)['summary'], lookup['personal_meaning']['summary'])
        self.assertEqual(lookup['personal_meaning']['summary'], longevity['personal_meaning']['summary'])

    def test_the_selected_observation_cannot_be_replaced_by_a_flat_genotype(self):
        from scholion.variant_readings import resolve
        row = self.row()
        row['reading'] = resolve('rs13217795', row['reading'])
        row['reading']['genotype'] = 'CC'
        self.assertEqual('reference_only', describe(row)['status'])

    def test_literal_catalogue_reading_can_match_a_separate_study_without_clinical_permission(self):
        from scholion import genome
        from scholion.variant_readings import resolve, permits_interpretation
        locus = core.loci()['loci']['rs13217795']
        reading = {'confidence': 'called', 'genotype': 'TT', 'depth': 23, 'source': 'vcf',
                   'assembly': 'GRCh38', 'read_pos': locus['pos'], 'ref': 'C',
                   'variant_identity': {'assembly': 'GRCh38', 'chrom': '6', 'pos': locus['pos'], 'ref': 'C'}}
        with mock.patch.object(genome, '_read_gt_at', return_value=reading):
            resolved = resolve('rs13217795', genome._gt_at(locus))
        row = {**self.row(), 'reading': resolved}
        self.assertFalse(permits_interpretation(resolved))
        self.assertEqual('genotype_hypothesis', describe(row)['status'])
        for update in ({'read_pos': locus['pos'] + 1}, {'assembly': 'unknown'},
                       {'conflict': {'kind': 'source_disagreement'}}, {'genotype': 'GG'},
                       {'interpretation_restriction': 'different_alt'}):
            other = deepcopy(row)
            other['reading'].update(update)
            self.assertNotEqual('genotype_hypothesis', describe(other)['status'], update)

    def test_observations_remain_exact_and_can_contradict_the_predisposition(self):
        row = self.row('ABCG2', 'rs2231142', 'GT')
        comparison = {'eligible': True, 'gene': 'ABCG2', 'rsid': 'rs2231142',
                      'relation': 'different_direction', 'comparison': 'Measured urate is lower',
                      'observation': {'value': 180}, 'causal': False}
        row['comparisons'] = [comparison, {**comparison, 'rsid': 'rs1'},
                              {**comparison, 'eligible': False}]
        before = deepcopy(row)
        result = describe(row)
        self.assertEqual(1, len(result['context']))
        self.assertEqual('different_direction', result['context'][0]['relation'])
        self.assertIn('higher uric acid', result['summary'])
        self.assertEqual(before, row)

    def test_insight_visit_and_text_keep_the_same_meaning_without_changing_selection(self):
        from scholion.insight_context import _genetic_context
        from scholion.visit_focus import _reading_row
        from scholion.format_visit_focus import _gene_lines
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            row = attach(self.row('ABCG2', 'rs2231142', 'GT'))
            row.update(genotype=row['reading'], read=True, carrier=True, comparisons=[])
            context = _genetic_context(row, {})
            visit = _reading_row(context)
            self.assertEqual(row['personal_meaning'], context['personal_meaning'])
            self.assertEqual(context['personal_meaning'], visit['personal_meaning'])
            self.assertEqual(row['personal_meaning']['summary'], visit['summary'])
            text = '\n'.join(_gene_lines(visit))
            for key in ('summary', 'mechanism', 'limitations'):
                self.assertIn(row['personal_meaning'][key], text)
            self.assertFalse(visit['personal_effect_established'])

    def test_identity_and_selected_quality_survive_thin_panel_projections(self):
        from scholion.variant_readings import resolve
        row = self.row('COMT', 'rs4680', 'GA')
        row['reading'] = resolve('rs4680', row['reading'])
        row['reading'].pop('ref')
        self.assertEqual('genotype_hypothesis', describe(row)['status'])
        for field, value in (('pos', 1), ('ref', 'T'), ('chrom', '1'), ('assembly', 'GRCh37')):
            other = deepcopy(row)
            other['reading']['variant_identity'][field] = value
            self.assertEqual('reference_only', describe(other)['status'])
        low = self.row('COMT', 'rs4680', 'GA', depth=3)
        low['reading'] = resolve('rs4680', low['reading'])
        low['reading']['depth'] = 50
        self.assertEqual('reference_only', describe(low)['status'])

    def test_all_authored_genotypes_have_sourced_bilingual_comparisons(self):
        book = core._read_knowledge_raw('research_interpretations.json')['variants']
        for key, spec in book.items():
            self.assertTrue(spec['sources'], key)
            self.assertTrue(spec['source_records'], key)
            gene, rsid = key.split('|')
            for language in ('en', 'ru'):
                i18n.set_lang(language)
                for genotype, statement in spec['genotypes'].items():
                    result = describe(self.row(gene, rsid, genotype))
                    self.assertEqual(statement[language], result['summary'], (key, genotype, language))
                    self.assertEqual('genotype_hypothesis', result['status'])

    @unittest.skipUnless(shutil.which('node'), 'requires the shared browser renderer')
    def test_card_displays_core_meaning_before_qualifications_and_sources(self):
        row = attach(self.row(interpretation_applicable=False))
        script = 'const cards=require(' + json.dumps(str(support.SRC/'scholion/web/gene-cards.js')) + ');\n'
        script += 'const row=' + json.dumps(row) + ';\n'
        script += "const model=cards.project(row); const assert=require('node:assert/strict');\n"
        script += "assert.equal(model.summary,row.personal_meaning.summary);\n"
        script += "const html=cards.render(row,{t:k=>k,escape:String,grade:String});\n"
        script += "assert.ok(html.indexOf(row.personal_meaning.summary)<html.indexOf(row.personal_meaning.limitations));\n"
        script += "assert.ok(html.includes('34436732'));\n"
        script += "assert.ok(!html.includes('web.gene_card.interpretation_blocked'));\n"
        script += "const conflict={...row,reading:{...row.reading,conflict:{kind:'source_disagreement'}}};\n"
        script += "assert.ok(cards.render(conflict,{t:k=>k,escape:String,grade:String}).includes('genome.source_conflict'));\n"
        script += "const ui=cards.create({t:k=>k,escape:String,grade:String,register:()=> 'patient',passport:()=>'',authorNote:()=>'',clinicalBasis:()=>''});\n"
        script += "assert.ok(ui.brief(row).includes(row.personal_meaning.summary));\n"
        script += "const changed={...row,reading:{...row.reading,genotype:'CC'}};\n"
        script += "assert.ok(!ui.preview(changed).includes(row.personal_meaning.summary));\n"
        comt = attach(self.row('COMT', 'rs4680', 'GA'))
        script += 'const comt=' + json.dumps(comt) + ';\n'
        script += "assert.ok(ui.render(comt).includes(comt.personal_meaning.summary));\n"
        script += "assert.ok(!ui.render(comt).includes(comt.personal_meaning.limitations));\n"
        script += "assert.ok(ui.brief(comt).includes(comt.personal_meaning.limitations));\n"
        result = gene_card_support.run(script, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__':
    unittest.main()
