"""Source witnesses retain assertion scope and invalidate dependent meanings."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import core, reference_checks as checks, reference_updates as updates
from scholion import variant_annotations as annotations
from tests.test_variant_knowledge_refresh import RefreshReferenceKnowledge


class SourceParsers(unittest.TestCase):
    def test_publication_retraction_and_correction_change_without_claiming_fulltext_review(self):
        base = {"source": "MED", "pmid": "100", "title": "An experiment", "abstractText": "No increased activity."}
        first = checks.publication(base)
        self.assertNotIn("abstract", first)
        self.assertTrue(first["abstract_present"])
        self.assertFalse(first["retraction_flag_supplied"])
        corrected = checks.publication({**base, "isRetracted": "Y", "commentCorrectionList": {
            "commentCorrection": [{"type": "Retraction in", "id": "200"}]}})
        self.assertNotEqual(annotations.digest(first), annotations.digest(corrected))
        self.assertEqual(first, checks.publication({**base, "citedByCount": 10000}))
        with self.assertRaises(ValueError):
            checks.publication({**base, "source": "PMC"})

    def test_refsnp_preserves_multi_alleles_orientation_merge_and_withdrawal(self):
        record = {"refsnp_id": "100", "primary_snapshot_data": {"placements_with_allele": [
            {"seq_id": "NC_000001.11", "placement_annot": {"is_aln_opposite_orientation": True},
             "alleles": [{"allele": {"spdi": {"inserted_sequence": allele}}, "hgvs": allele} for allele in ["A", "C", "G"]]}]}}
        result = checks.refsnp(record, "rs100")
        self.assertEqual(len(result["placements"][0]["alleles"]), 3)
        self.assertTrue(result["placements"][0]["opposite_orientation"])
        self.assertNotIn("effect_allele", result)
        self.assertEqual(checks.refsnp({"refsnp_id": "100", "merged_snapshot_data": {"merged_into": ["200"]}}, "rs100")["state"], "merged_snapshot_data")
        self.assertEqual(checks.refsnp({"refsnp_id": "100", "withdrawn_snapshot_data": {}}, "rs100")["state"], "withdrawn_snapshot_data")
        with self.assertRaises(ValueError):
            checks.refsnp(record, "rs101")

    def test_exact_clinvar_allele_location_and_condition_not_gene_span(self):
        xml = '''<ClinVarResult-Set><VariationArchive Accession="VCV000000100" Version="2"><ClassifiedRecord>
        <SimpleAllele><GeneList><Gene Symbol="SYNTH"><Location><SequenceLocation start="1" stop="10000"/></Location></Gene></GeneList>
        <Location><SequenceLocation start="42" stop="42" Assembly="GRCh38"/></Location></SimpleAllele>
        <Classifications><GermlineClassification><Description>Conflicting classifications</Description></GermlineClassification></Classifications>
        <RCVList><RCVAccession Accession="RCV000000100" Version="3"><ClassifiedConditionList><ClassifiedCondition DB="MedGen" ID="C1">Condition one</ClassifiedCondition></ClassifiedConditionList>
        <RCVClassifications><GermlineClassification><Description>Pathogenic</Description></GermlineClassification></RCVClassifications></RCVAccession></RCVList>
        </ClassifiedRecord></VariationArchive></ClinVarResult-Set>'''
        result = checks.clinvar(xml, "VCV000000100")
        self.assertEqual(result["allele_locations"][0]["start"], "42")
        self.assertEqual(result["germline_aggregate"]["description"], "Conflicting classifications")
        self.assertEqual(result["condition_assertions"][0]["germline"]["description"], "Pathogenic")
        with self.assertRaises(ValueError):
            checks.clinvar(xml, "VCV000000101")
        with self.assertRaisesRegex(ValueError, "haplotype"):
            checks.clinvar(xml.replace('SimpleAllele', 'Haplotype'), "VCV000000100")

    def test_gencc_disagreements_and_inheritance_stay_separate_submissions(self):
        text = 'sgc_id\tgene_curie\tdisease_curie\tclassification_title\tmoi_title\n1\tHGNC:1\tMONDO:1\tDefinitive\tAutosomal dominant\n2\tHGNC:1\tMONDO:1\tRefuted\tAutosomal recessive\n'
        result = checks.gencc(text, {"HGNC:1"})
        self.assertEqual(len(result), 2)
        self.assertEqual(result['2']['classification_title'], 'Refuted')
        self.assertEqual(result['1']['moi_title'], 'Autosomal dominant')
        with self.assertRaises(ValueError):
            checks.gencc('gene\tdisease\nA\tB', {'HGNC:1'})

    def test_cpic_requires_exact_gene_and_keeps_allele_version(self):
        result = checks.cpic([{'genesymbol': 'SYNTH', 'name': '*2', 'id': 123, 'version': 4,
                              'clinicalfunctionalstatus': 'No function'}], 'SYNTH', 'allele')
        self.assertEqual(result['*2']['version'], 4)
        self.assertEqual(result['*2']['clinicalfunctionalstatus'], 'No function')
        with self.assertRaises(ValueError):
            checks.cpic([{'genesymbol': 'OTHER', 'name': '*2'}], 'SYNTH', 'allele')
        with self.assertRaises(ValueError):
            checks.cpic([], 'SYNTH', 'diplotype')

    def test_wrong_species_identity_and_unversioned_transcript_refused(self):
        with self.assertRaises(ValueError):
            checks.ncbi_gene({'gene_id': 1, 'tax_id': 10090})
        with self.assertRaises(ValueError):
            checks.ncbi_gene({'gene_id': 1, 'tax_id': 9606, 'nomenclature_authority': {'identifier': 'HGNC:2'}}, 'HGNC:1')
        with self.assertRaises(ValueError):
            checks.refseq('<GBSet/>', 'NM_000001')

    def test_failure_retains_previous_fingerprint_and_check_date(self):
        previous = {'provider': 'HGNC', 'fingerprint': 'old', 'compared_on': '2026-01-01'}
        result = checks.refresh({'genes': {'HGNC:1': {'symbol': 'SYNTH'}}, 'models': [],
                                 'source_checks': {'hgnc:catalogue': previous}},
                                fetch_json=lambda url: None, fetch_text=lambda url: None)
        self.assertEqual(result['records']['hgnc:catalogue']['fingerprint'], 'old')
        self.assertEqual(result['records']['hgnc:catalogue']['compared_on'], '2026-01-01')
        self.assertEqual(result['records']['hgnc:catalogue']['status'], 'unavailable')
        self.assertFalse(result['primary_semantic_review_renewed'])


class SourceDependencyLifecycle(RefreshReferenceKnowledge):
    def test_changed_linked_record_blocks_dependent_personal_meaning_only_after_acceptance(self):
        self.base['_meta']['check_linked_sources'] = True
        self.base['models'][0]['hgnc_id'] = 'HGNC:1'
        self.bundled.write_text(json.dumps(self.base), encoding="utf-8")
        checked = {'records': {'pubmed:100': {'status': 'current'}}, 'events': [
            {'key': 'pubmed:100', 'provider': 'Europe PMC', 'kind': 'source_record_changed', 'before': {}, 'after': {'is_retracted': 'Y'}}],
            'models_requiring_review': ['model-a'], 'requests_completed': 1, 'failures': []}
        with patch.object(checks, 'refresh', return_value=checked), patch('scholion.sources._prepare_cpic', side_effect=RuntimeError('Unavailable')):
            preview = updates.preview(lambda url: self.response())
        self.assertFalse(annotations.needs_source_review('SYNTH', 'rs100'))
        updates.accept(preview['token'])
        self.assertTrue(annotations.needs_source_review('SYNTH', 'rs100'))
        self.assertFalse(annotations.needs_source_review('SYNTH', 'rs200'))
        self.assertEqual(annotations.catalogue()['models'][0]['checked_on'], '2026-11-13')

    def test_new_bundled_models_remain_visible_behind_later_local_source_import(self):
        preview = updates.preview(lambda url: self.response())
        updates.accept(preview['token'])
        self.base['_meta']['authored_revision'] = 'new-product-curation'
        self.base['genes']['HGNC:2'] = {'symbol': 'SECOND', 'aliases': []}
        self.base['models'].append({'model_id': 'new-model', 'hgnc_id': 'HGNC:2', 'gene': 'SECOND', 'variant_ids': ['rs200'], 'genotypes': []})
        self.bundled.write_text(json.dumps(self.base), encoding="utf-8")
        core.reset_cache()
        result = annotations.catalogue()
        self.assertEqual(result['_meta']['authored_revision'], 'new-product-curation')
        self.assertEqual(result['models'][-1]['model_id'], 'new-model')
        self.assertEqual(annotations.reference('SECOND')['gene_id'], 'HGNC:2')

    def test_cpic_overlay_is_staged_atomically_and_later_standalone_import_wins(self):
        for name in ('cpic_drug_gene.json', 'cpic_pairs.json'):
            (self.bundle / name).write_text(json.dumps({'_meta': {'updated': '2026-01-01'}, 'genes': {'SYNTH': {'effect': 'old'}}}), encoding="utf-8")
        self.base['_meta']['check_linked_sources'] = True
        self.bundled.write_text(json.dumps(self.base), encoding="utf-8")
        checked = {'records': {}, 'events': [], 'models_requiring_review': [], 'requests_completed': 0, 'failures': []}
        prepared = {'data': {'genes': {'SYNTH': {'effect': 'new'}}}, 'pairs': {'pairs': []}, 'checked': 2, 'changes': []}
        with patch.object(checks, 'refresh', return_value=checked), patch('scholion.sources._prepare_cpic', return_value=prepared):
            preview = updates.preview(lambda url: self.response())
        self.assertEqual(core.cpic_kb()['genes']['SYNTH']['effect'], 'old')
        updates.accept(preview['token'])
        self.assertEqual(core.cpic_kb()['genes']['SYNTH']['effect'], 'new')
        from scholion import sources
        cpic_source = next(row for row in sources.state() if row['id'] == 'cpic')
        self.assertTrue(all(row.get('reference_snapshot') for row in cpic_source['files']))
        self.assertTrue(all(row['answers'] == 'accepted_reference_snapshot' for row in cpic_source['files']))
        core.write_knowledge_local('cpic_drug_gene.json', {'_meta': {'updated': '2026-12-01'}, 'genes': {'SYNTH': {'effect': 'later'}}})
        self.assertEqual(core.cpic_kb()['genes']['SYNTH']['effect'], 'later')

    def test_status_formatter_handles_preview_diff_failure_and_schedule(self):
        from scholion.format_build import sources_report
        for result in [{'status': 'review_ready', 'token': 'a' * 32}, {'status': 'failed', 'error': 'Unavailable'}, {'schedule': {'enabled': False}}]:
            self.assertTrue(sources_report({'results': [result]}))


class RefreshedTransporterModel(unittest.TestCase):
    def test_no_function_label_still_produces_transporter_phenotype(self):
        from scholion.engine import pgx
        with patch.object(pgx, '_called_diplotype', return_value=None), patch.object(core, 'genome_gaps', return_value={}):
            for genotype, copies, expected in [('TT', 0, 'normal_function'), ('TC', 1, 'intermediate_function'), ('CC', 2, 'low_function')]:
                with self.subTest(genotype=genotype), patch.object(core, 'genotype_status', return_value={'genotype': genotype, 'confidence': 'called', 'depth': 30}), patch.object(pgx, '_copies_at_locus', return_value=copies):
                    self.assertEqual(pgx.compute_phenotype('SLCO1B1')['phenotype'], expected)


class VersionedTransport(unittest.TestCase):
    def test_offline_never_opens_and_release_headers_survive(self):
        from scholion import net
        with patch.object(net, 'offline', return_value=True), patch.object(net, '_diag_opener') as opener:
            self.assertIsNone(net.get_json_response('https://rest.uniprot.org/uniprotkb/search'))
            opener.assert_not_called()
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"results": []}'
        response.headers = {'X-UniProt-Release': '2026_04'}
        response.status = 200
        opener = MagicMock()
        opener.open.return_value = response
        with patch.object(net, 'offline', return_value=False), patch.object(net, '_diag_opener', return_value=opener):
            self.assertEqual(net.get_json_response('https://rest.uniprot.org/uniprotkb/search')['headers']['x-uniprot-release'], '2026_04')
            self.assertIsNone(net.get_json_response('https://rest.uniprot.org/uniprotkb/search', max_bytes=1))

    def test_tls_failure_does_not_silently_disable_verification(self):
        from scholion import net
        import ssl
        from unittest.mock import MagicMock
        opener = MagicMock()
        opener.open.side_effect = ssl.SSLCertVerificationError('synthetic verification failure')
        with patch.object(net, 'offline', return_value=False), patch.object(net, 'insecure_allowed', return_value=False), patch.object(net, '_diag_opener', return_value=opener):
            self.assertIsNone(net.get_json_response('https://rest.uniprot.org/uniprotkb/search'))
            self.assertEqual(opener.open.call_count, 1)


class ReferenceHTTPControls(RefreshReferenceKnowledge):
    def test_real_http_controls_stage_accept_schedule_and_cancel(self):
        import time
        import threading
        from tests.test_interface_acceptance import checks as interfaces
        from scholion import net
        with interfaces.http_server() as base:
            code, status = interfaces.request(base, '/api/reference-updates')
            self.assertEqual(code, 200)
            self.assertFalse(status['schedule']['enabled'])
            code, refused = interfaces.request(base, '/api/reference-updates', {'action': 'schedule', 'enabled': True, 'interval_months': 0})
            self.assertEqual(code, 400)
            self.assertIn('calendar months', refused['error'])
            code, refused = interfaces.request(base, '/api/reference-updates?token=' + 'a' * 32)
            self.assertEqual(code, 400)
            self.assertIn('does not exist', refused['error'])
            code, status = interfaces.request(base, '/api/reference-updates', {'action': 'schedule', 'enabled': True, 'interval_months': 3})
            self.assertEqual(code, 200)
            self.assertTrue(status['schedule']['enabled'])
            with patch.object(net, 'get_json_response', side_effect=lambda url: self.response('Changed synthetic source.')):
                code, started = interfaces.request(base, '/api/reference-updates', {'action': 'check'})
                self.assertEqual(code, 200)
                self.assertEqual(started['status'], 'running')
                for _ in range(100):
                    code, status = interfaces.request(base, '/api/reference-updates')
                    if status['job']['status'] != 'running':
                        break
                    time.sleep(0.01)
            self.assertEqual(status['job']['status'], 'review_ready')
            token = started['token']
            code, diff = interfaces.request(base, '/api/reference-updates?token=' + token + '&limit=1')
            self.assertEqual(code, 200)
            self.assertEqual(diff['total'], 1)
            self.assertFalse((self.repo / 'knowledge' / annotations.ANNOTATIONS).exists())
            code, accepted = interfaces.request(base, '/api/reference-updates', {'action': 'accept', 'token': token})
            self.assertEqual(code, 200)
            self.assertTrue(accepted['accepted'])
            saved = core.knowledge_path(annotations.ANNOTATIONS).read_bytes()
            entered, release = threading.Event(), threading.Event()
            def delayed(url):
                entered.set()
                release.wait(5)
                return self.response('Another change.')
            with patch.object(net, 'get_json_response', side_effect=delayed):
                interfaces.request(base, '/api/reference-updates', {'action': 'check'})
                self.assertTrue(entered.wait(5))
                interfaces.request(base, '/api/reference-updates', {'action': 'cancel'})
                release.set()
                for _ in range(100):
                    _, status = interfaces.request(base, '/api/reference-updates')
                    if status['job']['status'] != 'running':
                        break
                    time.sleep(0.01)
            self.assertEqual(status['job']['status'], 'cancelled')
            self.assertEqual(core.knowledge_path(annotations.ANNOTATIONS).read_bytes(), saved)

    def test_a_background_check_cannot_write_into_a_switched_container(self):
        import threading
        entered, release = threading.Event(), threading.Event()
        def delayed(url):
            entered.set()
            release.wait(5)
            return self.response()
        started = updates.start(delayed)
        self.assertTrue(entered.wait(5))
        with updates._ACTIVE_LOCK:
            worker = next(iter(updates._ACTIVE.values()))
        other = self.root / "person-b"
        (other / "profile").mkdir(parents=True)
        with patch.dict(os.environ, {"SCHOLION_REPO_DIR": str(other), "SCHOLION_PROFILE_DIR": str(other / "profile")}):
            self.assertFalse(updates.status()["job"])
            release.set()
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertFalse((other / "knowledge" / annotations.ANNOTATIONS).exists())
        self.assertEqual(updates.status()["job"]["token"], started["token"])
        self.assertIn(updates.status()["job"]["status"], ("interrupted", "failed"))
        self.assertEqual(self.bundled.read_bytes(), self.original)

    def test_due_background_check_is_staged_and_large_population_loss_is_refused(self):
        updates.configure(True, 3)
        with patch.object(updates, 'start', return_value={'status': 'running'}) as start:
            self.assertEqual(updates.check_due(__import__('datetime').date(2027, 3, 1), background=True)['status'], 'running')
            start.assert_called_once()
        self.base['_meta']['source_entry_count'] = 20000
        self.bundled.write_text(json.dumps(self.base), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unexpectedly shrank'):
            updates.preview(lambda url: self.response())
        self.assertEqual(self.bundled.read_bytes(), json.dumps(self.base).encode())


class CompleteCPICTables(unittest.TestCase):
    def test_all_rows_are_collected_even_when_the_server_caps_pages_below_requested_size(self):
        calls = []
        def fetch(url, request_headers):
            calls.append((url, request_headers))
            offset = int(url.rsplit('offset=', 1)[1])
            rows = [{'name': '*1'}, {'name': '*2'}, {'name': '*3'}]
            return {'data': rows[offset:offset+2], 'headers': {'Content-Range': f'{offset}-{min(offset+1,2)}/3'}}
        result = checks.cpic_table('https://api.cpicpgx.org/v1/allele?genesymbol=eq.SYNTH', fetch)
        self.assertEqual([row['name'] for row in result], ['*1', '*2', '*3'])
        self.assertEqual(len(calls), 2)
        self.assertIn('order=name.asc', calls[0][0])
        self.assertEqual(calls[0][1], {'Prefer': 'count=exact'})

    def test_unknown_extent_and_missing_page_cannot_refresh_a_complete_table(self):
        for headers in ({'content-range': '0-0/*'}, {'content-range': '1-1/2'}, {}):
            with self.subTest(headers=headers), self.assertRaises(ValueError):
                checks.cpic_table('https://api.cpicpgx.org/v1/allele?genesymbol=eq.SYNTH',
                                  lambda *a, **k: {'data': [{'name': '*1'}], 'headers': headers})

    def test_count_change_during_download_is_rejected(self):
        pages = iter([{'data': [1], 'headers': {'content-range': '0-0/2'}},
                      {'data': [2], 'headers': {'content-range': '1-1/3'}}])
        with self.assertRaisesRegex(ValueError, 'size changed'):
            checks.cpic_table('https://api.cpicpgx.org/v1/diplotype?genesymbol=eq.SYNTH', lambda *a, **k: next(pages))

    def test_repeated_model_identity_does_not_silently_replace_an_assertion(self):
        with self.assertRaisesRegex(ValueError, 'repeated table identities'):
            checks.cpic([{'genesymbol': 'SYNTH', 'name': '*2', 'clinicalfunctionalstatus': status}
                         for status in ['Normal function', 'No function']], 'SYNTH', 'allele')


class LinkedRecordRefresh(unittest.TestCase):
    def test_exact_source_changes_invalidate_the_bound_model_and_retain_claim_review_date(self):
        data = {'genes': {'HGNC:1': {'symbol': 'SYNTH', 'ncbi_id': '1'}}, 'models': [
            {'model_id': 'synthetic-model', 'gene': 'SYNTH', 'hgnc_id': 'HGNC:1', 'variant_ids': ['rs100'],
             'checked_on': '2026-01-01', 'sources': [{'pmid': '100', 'url': 'https://pubmed.ncbi.nlm.nih.gov/100/'},
                 {'url': 'https://www.ncbi.nlm.nih.gov/clinvar/VCV000000100'},
                 {'url': 'https://www.ncbi.nlm.nih.gov/nuccore/NM_000001.1'},
                 {'url': 'https://api.cpicpgx.org/v1/allele?genesymbol=eq.SYNTH'},
                 {'url': 'https://thegencc.org/'}]}]}
        publication = {'source': 'MED', 'pmid': '100', 'title': 'Synthetic experiment', 'abstractText': 'No increase in transport.'}
        def fetch_json(url):
            if url == checks.HGNC_URL:
                return {'response': {'numFound': 1, 'docs': [{'hgnc_id': 'HGNC:1', 'symbol': 'SYNTH', 'status': 'Approved'}]}}
            if '/datasets/' in url:
                return {'reports': [{'gene': {'gene_id': 1, 'tax_id': 9606, 'symbol': 'SYNTH',
                    'nomenclature_authority': {'identifier': 'HGNC:1'}, 'summary': [{'description': 'Synthetic gene function.'}]}}]}
            if 'europepmc' in url:
                return {'resultList': {'result': [publication]}}
            if '/refsnp/' in url:
                return {'refsnp_id': '100', 'primary_snapshot_data': {'placements_with_allele': []}}
            if '/allele?' in url:
                return [{'genesymbol': 'SYNTH', 'name': '*2', 'id': 2, 'version': 3, 'clinicalfunctionalstatus': 'No function'}]
            if '/diplotype?' in url:
                return [{'genesymbol': 'SYNTH', 'diplotypekey': {'*1': 1, '*2': 1}, 'generesult': 'Intermediate Metabolizer'}]
            raise AssertionError(url)
        def fetch_text(url):
            if url == checks.GENCC_URL:
                return 'sgc_id\tgene_curie\tdisease_curie\tclassification_title\tmoi_title\n1\tHGNC:1\tMONDO:1\tDefinitive\tAutosomal recessive\n'
            if 'db=clinvar' in url:
                return '<ClinVarResult-Set><VariationArchive Accession="VCV000000100" Version="1"><ClassifiedRecord><SimpleAllele><Location><SequenceLocation start="42" stop="42"/></Location></SimpleAllele></ClassifiedRecord></VariationArchive></ClinVarResult-Set>'
            if 'db=nuccore' in url:
                return '<GBSet><GBSeq><GBSeq_accession-version>NM_000001.1</GBSeq_accession-version><GBSeq_organism>Homo sapiens</GBSeq_organism><GBSeq_length>1000</GBSeq_length></GBSeq></GBSet>'
            raise AssertionError(url)
        first = checks.refresh(data, fetch_json=fetch_json, fetch_text=fetch_text)
        self.assertEqual(first['failures'], [])
        self.assertEqual(first['models_requiring_review'], [])
        self.assertEqual(len(first['records']), 9)
        publication['isRetracted'] = 'Y'
        second = checks.refresh({**data, 'source_checks': first['records']}, fetch_json=fetch_json, fetch_text=fetch_text)
        self.assertEqual(second['models_requiring_review'], ['synthetic-model'])
        self.assertEqual([row['key'] for row in second['events']], ['pubmed:100'])
        self.assertEqual(data['models'][0]['checked_on'], '2026-01-01')
        self.assertFalse(second['primary_semantic_review_renewed'])
        self.assertEqual(second['records']['gencc:HGNC:1']['scope'], 'gene_disease_validity_and_inheritance_not_variant_effect')


class ReferenceTransportFailureBoundaries(unittest.TestCase):
    def test_versioned_transport_retries_a_certificate_failure_only_after_explicit_opt_in(self):
        import contextlib
        import io
        import ssl
        import urllib.error
        from unittest.mock import MagicMock
        from scholion import net
        first, second, context = MagicMock(), MagicMock(), object()
        first.open.side_effect = urllib.error.URLError(ssl.SSLCertVerificationError('synthetic certificate failure'))
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"results": []}'
        response.headers = {'X-UniProt-Release': '2026_04'}
        response.status = 200
        second.open.return_value = response
        warning = io.StringIO()
        with patch.object(net, 'offline', return_value=False), patch.object(net, 'insecure_allowed', return_value=True), patch.object(net, '_unverified', return_value=context), patch.object(net, '_diag_opener', side_effect=[first, second]) as opener, contextlib.redirect_stderr(warning):
            result = net.get_json_response('https://rest.uniprot.org/uniprotkb/search')
        self.assertEqual(result['headers']['x-uniprot-release'], '2026_04')
        self.assertEqual(opener.call_args_list[1].args, (context,))
        self.assertTrue(warning.getvalue())

    def test_an_unexpected_internal_error_does_not_reveal_a_filename(self):
        from scholion import net
        self.assertNotIn('/private/', net.reference_error(TypeError('/private/synthetic/error.json')))
