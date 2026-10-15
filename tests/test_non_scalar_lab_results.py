"""Qualitative forms survive transcription, storage, inspection and reconciliation."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, engine, format as fmt, ingest_labs, reconcile, store
from scholion.lab_observations import parse_observations

DATE = 'Collected: 2024-11-05 08:15\n'
URINE = DATE + '''Urinalysis
Colour dark yellow straw yellow
Clarity clear clear
Protein absent g/L <0.1
Leukocytes 0-2 /HPF 0-4
Bacteria absent /HPF absent
'''
PCR = DATE + '''Respiratory PCR
Adenovirus groups B, C, E
not detected not detected
DNA
Parainfluenza virus 1 RNA detected not detected
Parainfluenza virus 2 RNA not detected not detected
'''
ANTIBODY = DATE + '''Sample type: blood serum
Total IgM / IgG antibodies to the receptor
binding domain of SARS-CoV-2 S
<0.82 BAU/ml Negative
BAU/ml 1250.5
>0.82 BAU/ml Positive
'''


class TypedResultCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.profile = self.root / 'profile'
        self.forms = self.root / 'forms'
        self.profile.mkdir()
        self.forms.mkdir()
        self.env = mock.patch.dict(os.environ, {'SCHOLION_PROFILE_DIR': str(self.profile)})
        self.env.start()
        self.restore_cache = support.pin_cache(self.root / 'cache')
        core.reset_cache()

    def tearDown(self):
        self.restore_cache()
        self.env.stop()
        core.reset_cache()
        self.tmp.cleanup()

    def test_absence_and_interval_are_not_zero_or_midpoint(self):
        rows = {r['key']: r for r in parse_observations(URINE)}
        protein = rows['urinalysis_protein']
        self.assertEqual(protein['code'], 'absent')
        self.assertNotIn('value', protein)
        self.assertEqual(protein['reference_text'], '<0.1')
        count = rows['urinalysis_wbc']
        self.assertEqual((count['kind'], count['low'], count['high']), ('interval', 0, 2))
        self.assertNotIn('value', count)
        self.assertEqual(count['unit'], '/HPF')

    def test_pcr_wrapping_negation_and_target_identity(self):
        rows = parse_observations(PCR)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r['code'] for r in rows], ['not_detected', 'detected', 'not_detected'])
        self.assertTrue(all(r['method'] == 'PCR' for r in rows))
        self.assertNotEqual(rows[1]['key'], rows[2]['key'])

    def test_no_reference_or_neighbour_is_a_result(self):
        self.assertEqual(parse_observations(DATE + 'Urinalysis\nProtein unknown g/L 0-1\n'), [])
        rows = parse_observations(DATE + 'Urinalysis\nBacteria\nLeukocytes 0-1 /HPF 0-4\n')
        self.assertEqual([r['key'] for r in rows], ['urinalysis_wbc'])
        self.assertEqual(parse_observations('Protein absent g/L <0.1'), [])

    def test_single_count_keeps_count_in_urine_not_blood(self):
        row = parse_observations(DATE + 'Urinalysis\nLeukocytes 3 /HPF 0-4')[0]
        self.assertEqual((row['kind'], row['value']), ('count', 3))
        self.assertEqual(row['key'], 'urinalysis_wbc')

    def test_antibody_unit_first_and_thresholds_are_separate(self):
        date, found = ingest_labs.parse_report(ANTIBODY, core.lab_markers()['markers'])
        self.assertEqual(date, '2024-11-05T08:15')
        row = found['sars_cov_2_s_total_antibodies']
        self.assertEqual(row['value'], 1250.5)
        self.assertIsNone(row['ref_high'])
        self.assertEqual(row['unit'], 'BAU/ml')
        self.assertNotIn('sars_cov_2_s_total_antibodies', ingest_labs.parse_report(
            ANTIBODY.replace('BAU/ml 1250.5', ''), core.lab_markers()['markers'])[1])

    def test_import_persist_idempotence_and_all_readers(self):
        for name, text in [('urine.txt', URINE), ('pcr.txt', PCR), ('antibodies.txt', ANTIBODY)]:
            (self.forms / name).write_text(text, encoding="utf-8")
        first = ingest_labs.ingest(str(self.forms))
        self.assertEqual(first['errors'], [])
        self.assertEqual(first['observations_added'], 8)
        self.assertEqual(first['files_processed'], 3)
        self.assertEqual(ingest_labs.ingest(str(self.forms))['skipped'], 3)
        second = ingest_labs.ingest(str(self.forms), force=True)
        self.assertEqual(second['observation_conflicts'], [])
        saved = json.loads((self.profile / 'labs.json').read_text(encoding="utf-8"))
        self.assertEqual(len(saved['observations']), 8)
        self.assertTrue(all(len(o['series']) == 1 for o in saved['observations'].values()))
        result = engine.analyze_labs()
        self.assertEqual(len(result['observations']), 8)
        self.assertIn('0-2', fmt.labs_report(result))
        self.assertIn('1250.5', fmt.labs_report(result, include_history=True))
        self.assertIn('8', fmt.ingest_labs_report(first))
        self.assertTrue(all(o['proposed_rule'] for o in result['observations']))

    def test_conflicts_do_not_silently_replace_another_form(self):
        a = parse_observations(URINE)
        b = parse_observations(URINE.replace('Protein absent', 'Protein present'))
        store._add_lab_observations(a, '2024-11-05T08:15', source='one', date_source='form', subject='owner')
        r = store._add_lab_observations(b, '2024-11-05T08:15', source='two', date_source='form', subject='owner')
        self.assertEqual(len(r['conflicts']), 1)
        self.assertEqual(r['conflicts'][0]['marker'], 'urinalysis_protein')
        # Corrected output of the SAME source can replace it explicitly.
        store._add_lab_observations(b, '2024-11-05T08:15', source='one', date_source='form', subject='owner')
        self.assertEqual(core.labs()['observations']['urinalysis_protein']['series'][0]['code'], 'present')

    def test_reconcile_detects_typed_omissions_and_disagreements(self):
        form = self.forms / 'synthetic.pdf'
        form.write_bytes(b'%PDF-1.4\n')
        text = URINE + '\n' + 'Synthetic padding. ' * 25
        with mock.patch.object(ingest_labs, '_read_pdf', return_value=text):
            before = reconcile.reconcile(str(self.forms))
        self.assertEqual(len(before['missing']), 5)
        store._add_lab_observations(parse_observations(text), '2024-11-05T08:15',
                                    source=str(form), date_source='form', subject='owner')
        with mock.patch.object(ingest_labs, '_read_pdf', return_value=text):
            after = reconcile.reconcile(str(self.forms))
        self.assertEqual(after['observation_covered'], 5)
        self.assertEqual(after['missing'], [])

    def test_failure_and_cancel_keep_previous_observations(self):
        (self.forms / 'a.txt').write_text(URINE, encoding="utf-8")
        ingest_labs.ingest(str(self.forms))
        original = (self.profile / 'labs.json').read_bytes()
        with mock.patch.object(ingest_labs, '_read_any', side_effect=OSError('synthetic failure')):
            failed = ingest_labs.ingest(str(self.forms), force=True)
        self.assertEqual(len(failed['errors']), 1)
        self.assertEqual((self.profile / 'labs.json').read_bytes(), original)
        with self.assertRaises(InterruptedError):
            ingest_labs.ingest(str(self.forms), force=True,
                               progress=mock.Mock(side_effect=InterruptedError))
        self.assertEqual((self.profile / 'labs.json').read_bytes(), original)


    def test_archive_observations_preview_consent_and_atomic_persistence(self):
        from scholion import lab_archive
        form = self.forms / 'typed-archive.pdf'
        form.write_bytes(b'Synthetic extraction fixture')
        text = 'Collection date: 2024-11-05 08:15\nSpecimen: urine\nOrder ID: synthetic\nPage 1 of 1\n' + URINE.split('\n', 1)[1]
        with mock.patch.object(ingest_labs, '_ensure_extractor', return_value='synthetic'), \
                mock.patch.object(ingest_labs, '_read_any', return_value=text):
            preview = lab_archive.run(str(self.forms))
            self.assertTrue(preview.get('approval_token'), preview)
            self.assertFalse((self.profile / 'labs.json').exists())
            self.assertIn('absent', fmt.ingest_labs_report(preview))
            result = lab_archive.run(str(self.forms), preview['approval_token'])
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['observations_added'], 5)
        saved = (self.profile / 'labs.json').read_bytes()
        with mock.patch.object(ingest_labs, '_ensure_extractor', return_value='synthetic'), \
                mock.patch.object(ingest_labs, '_read_any', return_value=text.replace('Protein absent', 'Protein present')):
            rejected = lab_archive.run(str(self.forms), preview['approval_token'])
        self.assertFalse(rejected['ok'])
        self.assertEqual(saved, (self.profile / 'labs.json').read_bytes())

    def test_no_comment_can_supply_an_unreported_pcr_result(self):
        self.assertEqual(parse_observations(DATE + 'PCR\nAdenovirus\nComment: negative results do not exclude infection'), [])


    def test_pcr_specimen_needs_a_printed_header(self):
        self.assertEqual(parse_observations(PCR)[0]['specimen'], 'unknown')
        rows = parse_observations('Specimen: respiratory swab\n' + PCR)
        self.assertTrue(all(row['specimen'] == 'respiratory_swab' for row in rows))
        from scholion.lab_observations import equivalent
        self.assertFalse(equivalent(rows[0], parse_observations(PCR)[0]))

    def test_wrapped_reference_last_column_unit_and_count(self):
        text = DATE + 'Urinalysis\nColour yellow straw yellow,\nlight yellow\nLeukocytes 0-2 0-4 /HPF\n'
        rows = parse_observations(text)
        self.assertEqual(rows[0]['reference_text'], 'straw yellow, light yellow')
        self.assertEqual(rows[1]['unit'], '/HPF')
        self.assertEqual(rows[1]['reference_text'], '0-4')

    def test_agent_force_parameter_is_boolean_and_reaches_worker(self):
        from scholion import ouroboros_tools as tools
        spec = next(t for t in tools.get_tools() if t.name == 'sch_ingest_labs')
        self.assertEqual(spec.schema['parameters']['properties']['force']['type'], 'boolean')

    def test_archive_conflicting_qualitative_results_refuse_without_writing(self):
        from scholion import lab_archive
        (self.forms / 'existing.txt').write_text(URINE, encoding='utf-8')
        ingest_labs.ingest(str(self.forms))
        original = (self.profile / 'labs.json').read_bytes()
        archive = self.root / 'archive'
        archive.mkdir()
        for name in ('one.pdf', 'two.pdf'):
            (archive / name).write_bytes(b'Synthetic PDF extraction fixture')
        header = 'Collection date: 2024-11-05 08:15\nSpecimen: urine\nOrder ID: synthetic\nPage 1 of 1\n'
        first = header + URINE.split('\n', 1)[1]
        second = first.replace('Protein absent', 'Protein present')
        with mock.patch.object(ingest_labs, '_ensure_extractor', return_value='synthetic'), \
                mock.patch.object(ingest_labs, '_read_any', side_effect=lambda p: first if p.name == 'one.pdf' else second):
            preview = lab_archive.run(str(archive))
            self.assertIsNone(preview['approval_token'])
            self.assertTrue(any(r['reason'] == 'conflicting_observations' and
                                r['marker'] == 'urinalysis_protein' for r in preview['not_ingested']))
            refused = lab_archive.run(str(archive), 'unreviewed')
            self.assertFalse(refused['ok'])
        self.assertEqual((self.profile / 'labs.json').read_bytes(), original)
