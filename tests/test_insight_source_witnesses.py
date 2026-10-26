"""Source-bound system reviews preserve facts and avoid unrelated invalidation."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, i18n, insight_history
from scholion.engine.insight_events import _event, _fact, _fact_identity
from scholion.insight_basis import bind, fact_source
from scholion.knowledge_provenance import record


class TestInsightSourceWitnesses(unittest.TestCase):
    def test_clinician_report_keeps_missing_sources_and_dated_knowledge_visible(self):
        from scholion.format_insights import attention_report, basis_lines
        self.assertEqual(basis_lines({}), [])
        item = {'title': 'Synthetic system', 'priority': 1, 'date': '2026-10-20',
                'reason': 'Synthetic direction', 'facts': [], 'events': [],
                'provenance': {'basis': {
                    'facts': [{'source': 'same-form.pdf', 'date': '2026-10-20'},
                              {'source': 'same-form.pdf', 'date': '2026-10-20'},
                              {'date': '2026-10-19', 'availability': 'unavailable'}],
                    'knowledge': [{'source': 'PMID 12345678', 'checked_on': '2026-10-01', 'version': '2'}],
                    'rule_sources': [{}]}}}
        self.addCleanup(i18n.set_lang, i18n.lang())
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            text = attention_report({'title': 'Synthetic report', 'items': [item]}, clinician=True)
            self.assertEqual(text.count('same-form.pdf'), 1)
            self.assertIn('2026-10-19', text)
            self.assertIn(i18n.t('insight.basis.unavailable'), text)
            self.assertIn(i18n.t('insight.basis.source_unknown'), text)
            self.assertIn('PMID 12345678', text)
            self.assertIn('2026-10-01', text)
            self.assertIn(i18n.t('insight.basis.recorded'), text)
            self.assertIn(i18n.t('insight.basis.refresh'), text)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(i18n.set_lang, i18n.lang())

    def item(self):
        return {'id': 'panel:synthetic', 'name': 'Synthetic system', 'title': 'Synthetic change',
                'date': '2026-10-20', 'level': None, 'member_ids': ['lab:first', 'lab:second'],
                'facts': [{'record': 'labs.json', 'key': key, 'date': '2026-10-20',
                           'value': value, 'unit': 'synthetic', 'source': 'synthetic form'}
                          for key, value in [('first', 1), ('second', 2)]],
                'events': [{'kind': 'period_shift', 'rule': {'id': 'synthetic', 'version': '1', 'digest': 'rule-v1'}}]}

    def test_selected_record_not_whole_catalogue_is_the_content_identity(self):
        path = self.root / 'synthetic.json'
        book = {'_meta': {'version': '1'}, 'links': [
            {'association_id': 'used', 'source': 'https://example.org/used', 'checked_on': '2026-10-01', 'meaning': 'original'},
            {'association_id': 'unused', 'meaning': 'not used'}]}
        def save():
            path.write_text(json.dumps(book), encoding="utf-8")
        save()
        with mock.patch.object(core, 'knowledge_path', return_value=path):
            before = record('synthetic.json', 'links', 'used')
            book['_meta']['version'] = '2'
            book['links'][1]['meaning'] = 'unrelated new content'
            save()
            after = record('synthetic.json', 'links', 'used')
            self.assertEqual(before['record_digest'], after['record_digest'])
            self.assertNotEqual(before['version'], after['version'])
            book['links'][0]['meaning'] = 'changed used content'
            save()
            changed = record('synthetic.json', 'links', 'used')
            self.assertNotEqual(before['record_digest'], changed['record_digest'])
            self.assertEqual(record('synthetic.json', 'links', 'absent')['status'], 'not_recorded')
            book['links'].append(dict(book['links'][0]))
            save()
            self.assertEqual(record('synthetic.json', 'links', 'used')['status'], 'not_recorded')
        with mock.patch.object(core, 'knowledge_path', return_value=self.root / 'absent.json'):
            missing = record('missing.json', 'genes', 'ABSENT')
        self.assertIsNone(missing['record_digest'])

    def test_missing_document_preserves_recorded_hash_without_claiming_verification(self):
        path = self.root / 'source.json'
        path.write_text('new file contents', encoding="utf-8")
        point = {'record': 'labs.json', 'key': 'synthetic', 'date': '2026-10-20',
                 'source_record': {'path': str(path), 'source_sha256': 'recorded-earlier',
                                   'resource_id': 'observation', 'component': 0}}
        with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('do not rehash original')):
            available = fact_source(point)
        self.assertEqual(available['availability'], 'available')
        self.assertEqual(available['recorded_sha256'], 'recorded-earlier')
        self.assertEqual(available['verification'], 'recorded_witness_not_current_content_verification')
        path.unlink()
        missing = fact_source(point)
        self.assertEqual(missing['availability'], 'unavailable')
        self.assertEqual(missing['recorded_sha256'], 'recorded-earlier')
        self.assertNotEqual(fact_source({})['availability'], 'available')
        with mock.patch.object(Path, 'is_file', side_effect=PermissionError):
            self.assertEqual(fact_source(point)['availability'], 'unavailable')

    def test_form_section_and_fhir_identity_survive_the_event_envelope(self):
        point = {'date': '2026-10-20', 'value': 2, 'source': 'synthetic',
                 'source_record': {'resource_id': 'obs-2', 'source_sha256': 'abc'},
                 'ingest_method': {'section': {'index': 2, 'date': '2026-10-20'}},
                 'sample_id': 'second-draw'}
        fact = _fact('synthetic', point, {'unit': 'synthetic'})
        self.assertEqual(fact['source_record'], point['source_record'])
        self.assertEqual(_fact_identity(fact)['ingest_method'], point['ingest_method'])
        witness = fact_source(fact)
        self.assertEqual(witness['section']['index'], 2)
        other = fact_source({**fact, 'sample_id': 'another-draw'})
        self.assertNotEqual(witness['id'], other['id'])
        self.assertNotIn('source_record', _fact('legacy', {'date': '2026-10-20', 'value': 1}, {}))

    def test_every_member_and_qualitative_context_affects_the_system_basis(self):
        before = self.item()
        before['context'] = {'lifestyle': [{'record': 'focus_log.json', 'system': 'synthetic',
                                          'date': '2026-10-20', 'change': 'better', 'note': 'synthetic report'}]}
        bind(before)
        after = copy.deepcopy(before)
        after['facts'][1]['value'] = 3
        bind(after)
        self.assertNotEqual(before['provenance']['facts_digest'], after['provenance']['facts_digest'])
        after = copy.deepcopy(before)
        after['context']['lifestyle'][0]['change'] = 'worse'
        bind(after)
        self.assertNotEqual(before['provenance']['facts_digest'], after['provenance']['facts_digest'])
        after = copy.deepcopy(before)
        after['title'] = 'Another output language'
        after['facts'][0]['unit_display'] = 'Translated unit'
        bind(after)
        self.assertEqual(before['provenance']['facts_digest'], after['provenance']['facts_digest'])
        refresh = after['provenance']['basis']['refresh']
        self.assertFalse(refresh['writes_profile'])
        self.assertFalse(refresh['requires_genome_preparation'])
        self.assertFalse(refresh['requires_pgs_calculation'])

    def test_rules_use_selected_content_and_explicit_unknowns(self):
        item = self.item()
        witness = {'id': 'synthetic:used', 'record_digest': 'v1', 'status': 'recorded',
                   'version': '1', 'source': 'https://example.org', 'checked_on': '2026-10-20'}
        item['events'][0]['knowledge_records'] = [witness]
        bind(item)
        before = copy.deepcopy(item['provenance'])
        witness['version'] = '2'
        bind(item)
        self.assertEqual(before['rules_digest'], item['provenance']['rules_digest'])
        witness['record_digest'] = 'v2'
        bind(item)
        self.assertNotEqual(before['rules_digest'], item['provenance']['rules_digest'])
        witness.update(status='not_recorded', record_digest=None)
        bind(item)
        self.assertEqual(item['provenance']['basis']['unknown_knowledge'], ['synthetic:used'])
        item['provenance']['facts_digest'] = 'legacy'
        bind(item, preserve_existing=True)
        self.assertEqual(item['provenance']['facts_digest'], 'legacy')

    def test_used_rule_keeps_its_explicit_citation_without_inventing_a_date(self):
        event = _event('abnormal', 'synthetic', 'Synthetic', [],
                       rule={'source': 'https://example.org/guideline', 'version': '2',
                             'threshold_basis': {'source': 'PMID:1'}})
        item = self.item()
        item['events'] = [event]
        bind(item)
        sources = item['provenance']['basis']['rule_sources']
        self.assertEqual({r['source'] for r in sources}, {'https://example.org/guideline', 'PMID:1'})
        self.assertTrue(all(r['checked_on'] is None for r in sources))
        self.assertEqual(next(r for r in sources if r['source'].startswith('https:'))['version'], '2')

    def test_review_tracks_system_reason_without_duplicate_member_rows(self):
        item = self.item()
        bind(item)
        feed = {'policy': 'synthetic', 'as_of': '2026-10-20', 'states': {},
                'items': [{'id': 'lab:first', 'name': 'first', 'title': 'first',
                           'date': '2026-10-20', 'events': [],
                           'provenance': {'facts_digest': 'unchanged', 'rules_digest': 'unchanged'}}],
                'highlights': [item]}
        with mock.patch.object(insight_history.container, 'named', return_value={'id': 'synthetic'}), \
             mock.patch.object(core, 'profile_dir', return_value=self.root), \
             mock.patch.object(insight_history, '_reference_reviews', return_value=[]), \
             mock.patch.object(core, 'write_json', side_effect=AssertionError('review reads never write')):
            previous = insight_history._snapshot(feed)
            item['facts'][1]['value'] = 99
            bind(item)
            result = insight_history.compare_review(feed, previous)
            self.assertEqual(result['system_items'][0]['reason'], 'data')
            self.assertEqual(result['system_items'][0]['basis_changes'][0]['kind'], 'fact')
            self.assertEqual([r['id'] for r in result['display_items']], ['panel:synthetic'])
            del previous['system_items']
            legacy = insight_history.compare_review(feed, previous)
            self.assertFalse(legacy['system_baseline'])
            self.assertEqual(legacy['system_items'], [])

    def test_system_history_distinguishes_new_unavailable_and_withdrawn_support(self):
        item=self.item();item['level']='B';bind(item)
        feed={'policy':'synthetic','as_of':'2026-10-20','states':{},'items':[], 'highlights':[item]}
        with mock.patch.object(insight_history.container,'named',return_value={'id':'synthetic'}), \
             mock.patch.object(core,'profile_dir',return_value=self.root), \
             mock.patch.object(insight_history,'_reference_reviews',return_value=[]):
            old=insight_history._snapshot({**feed,'highlights':[]})
            result=insight_history.compare_review(feed,old)['system_items'][0]
            self.assertEqual((result['status'],result['reason']),('new','data'))
            previous=insight_history._snapshot(feed)
            missing=insight_history.compare_review({**feed,'highlights':[]},previous)['system_items'][0]
            self.assertEqual((missing['status'],missing['reason']),('unavailable','unknown'))
            self.assertIsNotNone(missing['previous']);self.assertIsNone(missing['current'])
            item['level']='C'
            withdrawn=insight_history.compare_review(feed,previous)['system_items'][0]
            self.assertEqual((withdrawn['status'],withdrawn['reason']),('withdrawn','rules'))
            self.assertEqual(withdrawn['current']['provenance']['facts_digest'],withdrawn['previous']['provenance']['facts_digest'])
