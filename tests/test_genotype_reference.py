"""A genotype key explains sequence letters without inventing normality."""
from __future__ import annotations

import copy
import json
import shutil
import unittest
from unittest import mock

import support  # noqa: F401
import gene_card_support
from scholion import core, i18n
from scholion.genotype_reference import describe, lines
from scholion.panel_reference import genome_context, reference_lines


class ReferenceExamples(unittest.TestCase):
    def test_reversed_reference_changes_the_examples_not_their_clinical_rank(self):
        for ref, alt in [('C', 'G'), ('G', 'C')]:
            with mock.patch.object(core, 'loci', return_value={'loci': {
                    'rs123': {'gene': 'SYNTHETIC', 'pos': 100, 'ref': ref, 'alt': alt}}}):
                guide = describe('rs123', 'SYNTHETIC')
            rows = guide['frames'][0]['rows']
            self.assertEqual([(r['genotype'], r['kind']) for r in rows], [
                (ref+'/'+ref, 'reference_homozygous'),
                (ref+'/'+alt, 'heterozygous'), (alt+'/'+alt, 'alternative_homozygous')])
            self.assertEqual(guide['scope'], 'sequence_reference_not_personal_reading')
            self.assertEqual(guide['study_examples'], [])
            self.assertNotIn('effect', rows[-1])
            self.assertIsNone(guide['frames'][0]['checked_on'])

    def test_explicit_build_mapping_can_reverse_which_allele_is_reference(self):
        locus = {'pos': 100, 'pos_grch37': 90, 'ref': 'A', 'alt': 'G',
                 'assembly_alleles': {'GRCh37': {'ref': 'G', 'alt': 'A', 'position': 90,
                                      'source': 'https://example.org/synthetic-record'}}}
        with mock.patch.object(core, 'loci', return_value={'loci': {'rs123': locus}}):
            guide = describe('rs123')
        self.assertEqual([f['rows'][0]['genotype'] for f in guide['frames']], ['A/A', 'G/G'])
        locus['assembly_alleles']['GRCh37']['position'] = 91
        with mock.patch.object(core, 'loci', return_value={'loci': {'rs123': locus}}):
            self.assertEqual(len(describe('rs123')['frames']), 1)

    def test_multiallelic_position_keeps_two_different_alternatives_heterozygous(self):
        guide = describe('rs4588', 'GC')
        for frame in guide['frames']:
            self.assertEqual(len(frame['rows']), 10)
            self.assertEqual(next(r['kind'] for r in frame['rows'] if r['genotype']=='A/C'), 'heterozygous')
            self.assertEqual(frame['reference'], 'G')
            self.assertTrue(frame['source'])
            self.assertTrue(frame['checked_on'])

    def test_unknown_and_non_snp_inputs_cannot_invent_an_allele_key(self):
        self.assertEqual(describe(''), {})
        self.assertEqual(describe('rs999999999999'), {})
        for ref, alt in [('A', 'AT'), ('A', 'A'), ('N', 'G')]:
            with mock.patch.object(core, 'loci', return_value={'loci': {
                    'rs123': {'pos': 100, 'ref': ref, 'alt': alt}}}):
                self.assertEqual(describe('rs123'), {})

    def test_bad_sequence_passport_never_falls_back_to_catalogue_letters(self):
        locus = copy.deepcopy(core.loci()['loci']['rs4588'])
        for frame in locus['allele_identity']['builds'].values():
            frame['sequence_reference'] = 'T'
        with mock.patch.object(core, 'loci', return_value={'loci': {'rs4588': locus}}):
            self.assertEqual(describe('rs4588', 'GC'), {})

    def test_changed_source_withholds_study_comparisons_but_keeps_sequence_key(self):
        locus = copy.deepcopy(core.loci()['loci']['rs13217795'])
        locus['note'] = 'Synthetic changed witness'
        with mock.patch.object(core, 'loci', return_value={'loci': {'rs13217795': locus}}), \
             mock.patch('scholion.knowledge_provenance.record', return_value={'record_digest': 'changed'}):
            guide = describe('rs13217795', 'FOXO3')
        self.assertTrue(guide['frames'])
        self.assertEqual(guide['study_examples'], [])

    def test_study_descriptions_are_conditional_and_keep_sources_and_limits(self):
        guide = describe('rs13217795', 'FOXO3')
        self.assertTrue(guide['study_examples'])
        self.assertTrue(guide['study_sources'])
        self.assertTrue(guide['study_limitations'])
        self.assertTrue(guide['study_notice'])
        self.assertEqual({r['genotype'] for r in guide['study_examples']}, {'CC', 'CT', 'TT'})
        self.assertFalse(describe('rs13217795', 'OTHER')['study_examples'])

    def test_reference_context_and_text_share_the_key_without_a_personal_reading(self):
        for language in ('en', 'ru'):
            with mock.patch.dict('os.environ', {'SCHOLION_LANG': language}):
                row = genome_context('SLCO1B1', 'rs4149056')
                guide = row['reference_context']['genotype_reference']
                self.assertEqual(guide['frames'][0]['rows'][0]['genotype'], 'T/T')
                self.assertNotIn('genotype', row)
                output = '\n'.join(reference_lines(row))
                self.assertIn(guide['title'], output)
                self.assertIn('C/C', output)
                self.assertIn(guide['notice'], output)
                self.assertEqual(lines({}), [])

    @unittest.skipUnless(shutil.which('node'), 'requires the actual shared component')
    def test_both_languages_and_registers_keep_examples_apart_from_unread_personal_data(self):
        for language in ('en', 'ru'):
            with mock.patch.dict('os.environ', {'SCHOLION_LANG': language}):
                row = genome_context('FOXO3', 'rs13217795')
            row['reading'] = {'confidence': 'assumed_ref', 'genotype': 'CC'}
            row['read'] = False
            script = 'const cards=require('+json.dumps(str(support.SRC/'scholion/web/gene-cards.js'))+');\n'
            script += 'const row='+json.dumps(row)+';const messages='+json.dumps(i18n.CATALOGUES[language])+';\n'
            script += r'''
const assert=require('node:assert/strict');
const escape=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const t=(k,a={})=>Object.entries(a).reduce((s,[key,v])=>s.replaceAll('{'+key+'}',v),messages[k]||k);
for(const register of ['patient','clinician']) {
  const component=cards.create({t,escape,grade:escape,formatDate:escape,register:()=>register,passport:()=>'',authorNote:()=>'',clinicalBasis:()=>''});
  const before=JSON.stringify(row);const html=component.render(row);
  assert.ok(html.includes('data-genotype-reference'));
  assert.ok(html.includes('C/C')&&html.includes('C/T')&&html.includes('T/T'));
  assert.ok(html.includes(row.reference_context.genotype_reference.notice));
  assert.ok(!html.includes('gene-card-genotype">CC<'));
  assert.equal(cards.project(row).genotype,'');
  assert.equal(JSON.stringify(row),before);
  const gene=component.render({gene:'SYNTHETIC',reference_context:row.reference_context});
  assert.ok(!gene.includes('data-genotype-reference'));
}
'''
            result = gene_card_support.run(script, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
