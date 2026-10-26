"""A classification is about a variant; personal meaning needs inheritance."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import finding_context as context, genome, i18n
from scholion.format_genome import clinvar_report


def hit(gt='0/1', gene='GENE', pos='100', **extra):
    return {**dict(gene=gene, chrom='2', pos=pos, ref='G', alt='A', genotype=gt,
                   clnsig='Pathogenic', clndn='Disease', rsid='rsSynthetic'), **extra}


def assertion(mode='AR', classification='Definitive', disease='Disease'):
    return dict(moi_code=mode, classification=classification, disease=disease)


class FindingMeaning(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        i18n.set_lang('en')

    def annotate(self, rows, assertions=None):
        with mock.patch.object(context, '_reference', return_value={
                'GENE': assertions if assertions is not None else [assertion()]}):
            return context.attach(rows)

    def test_one_recessive_copy_is_carriage_without_a_diagnosis(self):
        for gt in ('0/1', '1/0', '0|1', '1|0'):
            rows = [hit(gt)]; self.annotate(rows)
            p = rows[0]['personal_context']
            self.assertEqual('carrier_context', p['status'])
            self.assertEqual('heterozygous', p['zygosity'])
            self.assertFalse(p['diagnosis_established'])
            self.assertEqual(1, p['alternative_copies'])

    def test_two_rows_are_not_assumed_to_be_in_trans_even_when_each_is_phased(self):
        for other in ('0/1', '0|1', '1/1'):
            rows = [hit(), hit(other, pos='200')]; self.annotate(rows)
            self.assertEqual('phase_unresolved', rows[0]['personal_context']['status'])
        rows = [hit(), {**hit(), 'chrom': 'chr2'}]
        self.annotate(rows)
        self.assertEqual('carrier_context', rows[0]['personal_context']['status'])

    def test_filtered_rows_do_not_supply_a_second_allele(self):
        rows = [hit(), hit(pos='200', filter='LowQual')]; self.annotate(rows)
        self.assertEqual('carrier_context', rows[0]['personal_context']['status'])
        self.assertEqual('reading_unresolved', rows[1]['personal_context']['status'])

    def test_homozygous_dominant_x_linked_and_incomplete_calls_are_separate(self):
        for gt, mode, expected in [('1/1', 'AR', 'recessive_review'),
                ('0/1', 'AD', 'dominant_review'), ('0/1', 'XL', 'x_linked_review'),
                ('1', 'XL', 'x_linked_review'), ('1', 'AR', 'reading_unresolved'),
                ('0/.', 'AR', 'reading_unresolved'), ('0/0', 'AR', 'reading_unresolved'),
                ('0/2', 'AR', 'reading_unresolved'), ('1/2', 'AR', 'reading_unresolved')]:
            with self.subTest(gt=gt, mode=mode):
                rows = [hit(gt)]; self.annotate(rows, [assertion(mode)])
                self.assertEqual(expected, rows[0]['personal_context']['status'])

    def test_condition_matching_does_not_borrow_another_diseases_inheritance(self):
        refs = [assertion('AR'), assertion('AD', disease='Other disease')]
        rows = [hit()]; self.annotate(rows, refs)
        self.assertEqual('carrier_context', rows[0]['personal_context']['status'])
        self.assertEqual('condition', rows[0]['personal_context']['inheritance']['scope'])
        rows = [hit()]; rows[0]['clndn'] = 'GENE-related_disorder'
        self.annotate(rows, refs)
        self.assertEqual('inheritance_mixed', rows[0]['personal_context']['status'])

    def test_missing_or_only_weak_evidence_never_invents_carriage(self):
        for refs in ([], [assertion(classification='Limited')],
                     [assertion(classification='Disputed')]):
            rows = [hit()]; self.annotate(rows, refs)
            self.assertEqual('inheritance_unknown', rows[0]['personal_context']['status'])
        rows = [hit()]; self.annotate(rows, [assertion(), assertion('AD', 'Supportive')])
        self.assertEqual('inheritance_mixed', rows[0]['personal_context']['status'])
        for classification in ('Disputed', 'Disputed Evidence', 'Refuted', 'Refuted Evidence'):
            rows = [hit()]; self.annotate(rows, [assertion(), assertion('AD', classification)])
            self.assertEqual('carrier_context', rows[0]['personal_context']['status'])
        rows = [hit(gene='GENE|OTHER')]; self.annotate(rows)
        self.assertEqual('inheritance_unknown', rows[0]['personal_context']['status'])

    def test_drug_risk_protective_and_conflicting_labels_do_not_become_monogenic_findings(self):
        for sig in ('drug_response', 'risk_factor', 'protective', 'association',
                    'Uncertain_significance', 'Conflicting_classifications_of_pathogenicity'):
            rows = [{**hit(), 'clnsig': sig}]; self.annotate(rows)
            self.assertEqual('classification_only', rows[0]['personal_context']['status'])
            text = context.lines(rows[0])
            self.assertEqual(2, len(text))
            self.assertIn(rows[0]['personal_context']['inclusion_reason'], text)
            self.assertIn('0/1', text[1])
            self.assertNotIn(rows[0]['personal_context']['summary'], text)
        rows = [{**hit(), 'clnsig': 'External classification', 'tier': 'unknown_source_category'}]
        self.annotate(rows)
        self.assertEqual(i18n.t('finding.reason.uncertain'), rows[0]['personal_context']['inclusion_reason'])
        self.assertNotIn('⟦', rows[0]['personal_context']['inclusion_reason'])

    def test_verified_acmg_zygosity_is_used_without_inventing_a_raw_genotype(self):
        row = {**hit(), 'genotype': '', 'zygosity': 'het', 'reportable': 'carrier_only'}
        cat = {'genes': {'GENE': {'inheritance': 'AR', 'phenotype': 'Disease'}}}
        context.attach([row], cat)
        self.assertEqual('carrier_context', row['personal_context']['status'])
        self.assertEqual('', row['personal_context']['genotype'])
        row['reportable'] = 'needs_variant_class'; context.attach([row], cat)
        self.assertEqual('variant_class_review', row['personal_context']['status'])

    def test_pagination_cannot_hide_the_second_allele_from_the_context(self):
        with tempfile.TemporaryDirectory() as folder:
            fields = list(hit())
            rows = [hit(), hit(pos='200')]
            Path(folder, 'clinvar_hits.tsv').write_text('\t'.join(fields)+'\n'+
                '\n'.join('\t'.join(str(r[k]) for k in fields) for r in rows)+'\n', encoding='utf-8')
            with mock.patch.object(genome.core, 'genome_bases', return_value=[Path(folder)]), \
                    mock.patch.object(genome, '_clinvar_local_gene_map', return_value={}), \
                    mock.patch.object(context, '_reference', return_value={'GENE': [assertion()]}):
                result = genome.clinvar_hits(limit=1)
            self.assertEqual(2, result['count'])
            self.assertEqual(1, len(result['hits']))
            self.assertEqual({'phase_unresolved': 2}, result['personal_context_counts'])
            self.assertEqual('phase_unresolved', result['hits'][0]['personal_context']['status'])

    def test_both_languages_keep_the_same_facts_and_no_untranslated_keys(self):
        for language in ('ru', 'en'):
            i18n.set_lang(language); rows = [hit()]; self.annotate(rows)
            text = clinvar_report({'status': 'ok', 'count': 1, 'hits': rows})
            self.assertIn(i18n.t('finding.zygosity.heterozygous'), text)
            self.assertIn(i18n.t('finding.mode.AR'), text)
            self.assertIn(rows[0]['personal_context']['summary'], text)
            self.assertNotIn('⟦', text)
            self.assertNotIn('🔴', text)

    def test_drug_lookup_keeps_the_context_from_the_full_findings_list(self):
        from scholion.engine.pgx import clinvar_for_drug
        from scholion.format_primitives import _clinvar_block
        from scholion.panel_reference import attach_finding_biology
        rows = [hit(gene='SNUPN', tier='pathogenic')]
        context.attach(rows); attach_finding_biology(rows)
        with mock.patch.object(genome, 'clinvar_hits', return_value={'status': 'ok', 'hits': rows}), \
                mock.patch('scholion.engine.pgx._rsids_for_genes', return_value={'rsSynthetic': 'SNUPN'}):
            result = clinvar_for_drug('Synthetic drug', {'genes': [{'gene': 'SNUPN'}]})
        self.assertEqual(rows[0]['personal_context'], result['hits'][0]['personal_context'])
        text = _clinvar_block(result)
        self.assertIn(rows[0]['personal_context']['summary'], text)
        self.assertIn(i18n.t('finding.mode.AR'), text)
        self.assertNotIn('🔴', text)
        biology = rows[0]['gene_contexts'][0]['reference_context']['gene_function']
        self.assertLess(text.index(biology), text.index(rows[0]['personal_context']['summary']))

    @unittest.skipUnless(shutil.which('node'), 'Node is required for real renderer probes')
    def test_findings_and_clinvar_render_the_engine_context_without_red_carrier_badges(self):
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        functions = []
        for name in ('findingContextHtml', 'geneticPreviewHtml', 'geneticBriefHtml', 'genomeGeneTable', 'genomeFindings', 'renderClinvar', 'renderACMG', 'rxCard'):
            start = page.index('function '+name+'(')
            functions.append(page[start:page.index('\n}', start)+2])
        for language in ('en', 'ru'):
            i18n.set_lang(language); rows = [hit(gene='SNUPN', tier='pathogenic', stars=2)]
            with mock.patch.object(context, '_reference', return_value={'SNUPN': [assertion()]}):
                context.attach(rows)
            from scholion.panel_reference import attach_finding_biology
            attach_finding_biology(rows)
            cv = dict(status='ok', count=1, hits=rows, counts={}, actionable=1)
            payload = {'cv': cv, 'messages': i18n.CATALOGUES[language]}
            script = """
const fs=require('fs'),{cv,messages}=JSON.parse(fs.readFileSync(0,'utf8'));
const esc=x=>String(x??'').replaceAll('<','&lt;').replaceAll('"','&quot;');
const t=(k,a={})=>Object.entries(a).reduce((s,[k,v])=>s.replaceAll('{'+k+'}',v),messages[k]||k);
const badge=(c,x)=>`<span class="${c}">${x}</span>`,isRsid=()=>true,clnsigText=x=>x,diseaseText=x=>x;
const prsPercentile=()=>'',DISPLAY_MODE='patient',levelChip=x=>`<span>${x||''}</span>`;
const mechanismHtml=()=>'',passportHtml=()=>'',authorNoteHtml=()=>'',clinicalBasisHTML=()=>'';
const SEV={unknown:{cls:'b-unknown',key:'common.unknown'}},rxFold=(a,b,c)=>c||'';
const flagsHTML=()=>'',doseHTML=()=>'',ctxCount=()=>0,contextHtml=()=>'';
"""+'\n'.join(functions)+"""
console.log(JSON.stringify([genomeFindings(cv,null,null,null),renderClinvar(cv),renderACMG({status:'ok',carriers:cv.hits}),rxCard({status:'ok',drug:'Synthetic drug',clinvar:cv})]));
"""
            result = subprocess.run([shutil.which('node'), '-e', script], input=json.dumps(payload),
                                    text=True, capture_output=True, timeout=20)
            self.assertEqual(0, result.returncode, result.stderr)
            for html in json.loads(result.stdout):
                self.assertIn(rows[0]['personal_context']['summary'], html)
                self.assertIn(i18n.t('finding.zygosity.heterozygous'), html)
                self.assertNotIn('b-critical', html)
                biology = rows[0]['gene_contexts'][0]['reference_context']['gene_function']
                self.assertIn(biology, html)
                self.assertLess(html.index(biology), html.index(rows[0]['personal_context']['inclusion_reason']))
                self.assertLess(html.index(rows[0]['personal_context']['inclusion_reason']), html.index(rows[0]['personal_context']['summary']))
                self.assertNotIn('<p>'+rows[0]['personal_context']['summary']+'</p>', html)

    def test_inheritance_snapshot_is_public_and_retains_all_source_witnesses(self):
        book = context.core._read_knowledge('gencc_inheritance.json')
        self.assertEqual(len(book['genes']), book['_meta']['gene_count'])
        self.assertEqual(book['_meta']['source_rows'], sum(
            len(a['submission_ids']) for g in book['genes'].values() for a in g['submissions']))
        self.assertEqual('CC0', book['_meta']['license'].split()[0])
        refs = context._reference()
        for gene in ('CYP27A1', 'PIGQ', 'MLPH', 'SNUPN', 'IRF2BPL'):
            self.assertTrue(refs.get(gene), gene)

    def test_other_inheritance_and_missing_context_stay_explicit(self):
        for mode in ('Mitochondrial', 'Unknown', 'Y-linked inheritance'):
            rows = [hit('1')]; self.annotate(rows, [assertion(mode)])
            self.assertNotEqual('carrier_context', rows[0]['personal_context']['status'])
            self.assertNotIn('⟦', rows[0]['personal_context']['inheritance_label'])
        self.assertEqual([], context.lines({}))
        rows = [hit(alt='A,T')]; self.annotate(rows)
        self.assertEqual('reading_unresolved', rows[0]['personal_context']['status'])

    def test_biology_is_shared_for_coordinate_only_multigene_and_exact_locus_rows(self):
        from scholion.panel_reference import attach_finding_biology
        rows = [hit(gene='SNUPN', rsid='rs.'), hit(gene='IRF2BPL|SNUPN|SNUPN'),
                hit(gene=None, rsid='rs429358'), hit(gene='—')]
        original = [{key: row[key] for key in ('gene', 'rsid', 'genotype', 'pos')} for row in rows]
        attach_finding_biology(rows)
        self.assertEqual(original, [{key: row[key] for key in original[0]} for row in rows])
        first = rows[0]['gene_contexts'][0]
        self.assertEqual('', first['rsid'])
        self.assertEqual('not_curated', first['reference_context']['variant_status'])
        self.assertEqual('E', first['level'])
        self.assertIn('Snurportin', first['reference_context']['gene_function'])
        self.assertEqual(['IRF2BPL', 'SNUPN'], [c['gene'] for c in rows[1]['gene_contexts']])
        self.assertEqual('APOE', rows[2]['gene_contexts'][0]['gene'])
        self.assertEqual([], rows[3]['gene_contexts'])

    def test_regulatory_regions_and_noncoding_transcripts_do_not_become_protein_genes(self):
        from scholion.panel_reference import genome_context, reference_lines
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            region = genome_context('LOC110366355', 'rsSynthetic')
            self.assertEqual('genomic_annotation', region['reference_context']['gene_source_scope'])
            self.assertEqual('regulatory_region', region['reference_context']['function_status'])
            self.assertEqual(i18n.t('reference.region', text=region['reference_context']['gene_function']),
                             reference_lines(region)[0])
            transcript = genome_context('DPYD-AS1', 'rsSynthetic')
            self.assertEqual('noncoding_identity', transcript['reference_context']['function_status'])
            self.assertEqual('E', transcript['level'])
            self.assertNotIn('0/1', transcript['reference_context']['gene_function'])
            alias = genome_context('LOC105374344')
            self.assertEqual('RNF212-DT', alias['reference_context']['canonical_symbol'])

    def test_existing_catalogues_supply_only_an_absent_snapshot_entry(self):
        books = {'gencc_inheritance.json': {'genes': {'GENE': {'submissions': [assertion()]}}},
                 'gencc_gene_disease.json': {'systems': {'x': {'genes': {
                     'GENE': {'submissions': [assertion('AD')]},
                     'OTHER': {'submissions': [assertion('AD')]}}}}},
                 'gencc_panel_assertions.json': {'genes': {'THIRD': {'submissions': [assertion('XL')]}}}}
        with mock.patch.object(context.core, '_read_knowledge', side_effect=lambda n: books[n]):
            refs = context._reference()
        self.assertEqual('AR', refs['GENE'][0]['moi_code'])
        self.assertEqual('AD', refs['OTHER'][0]['moi_code'])
        self.assertEqual('XL', refs['THIRD'][0]['moi_code'])
