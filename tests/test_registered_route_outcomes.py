"""Stored outcomes for routes with inputs or boundaries outside the parity driver."""
from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

import support
from scholion import core
from tests import test_every_door_of_the_local_server_answers as live
from tests.test_a_brief_block_due_for_a_review_opens_what_changed import BRIEF
from tests.test_a_study_that_was_done_is_not_called_not_done import ULTRASOUND
from tests.test_body_composition_is_paired_and_qualified import record


class TestRegisteredRouteOutcomes(live._Live):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='scholion-outcomes-')).resolve()
        self.addCleanup(shutil.rmtree, self.work)
        self.profile = self.work / 'profile'
        shutil.copytree(support.FIXTURE_PROFILE, self.profile)
        self.addCleanup(support.pin_profile(self.profile))
        core.reset_cache()
        self.addCleanup(core.reset_cache)

    def cli(self, *args, genome=None):
        env = support.env(self.profile)
        if genome is not None:
            env['SCHOLION_GENOME_DIR'] = str(genome)
        result = subprocess.run([sys.executable, '-m', 'scholion', *args, '--json'],
                                cwd=support.ROOT, env=env, timeout=20,
                                capture_output=True, encoding='utf-8', stdin=subprocess.DEVNULL)
        self.assertEqual(0, result.returncode, result.stderr)
        return json.loads(result.stdout)

    def stored(self, name):
        return json.loads((self.profile / name).read_text(encoding='utf-8'))

    def test_marker_catalogue_keeps_keys_on_both_human_surfaces(self):
        web = self.json_of('/api/markers')
        self.assertEqual(self.cli('markers')['markers'], web['markers'])
        self.assertTrue(any(row['key'] == 'glucose' for row in web['markers']))

    def test_assistant_status_separates_optional_model_from_local_engine(self):
        web = self.json_of('/api/assistant')
        cli = self.cli('assistant')
        for key in ('works_without_assistant', 'engine_does', 'assistant_adds', 'curated', 'disclaimer'):
            self.assertEqual(cli[key], web[key], key)
        self.assertTrue(web['works_without_assistant'])
        self.assertEqual([], web['audit']['llm_hits'])
        self.assertTrue(web['assistant_adds'])

    def test_genome_update_reports_absence_and_saved_clinvar_version(self):
        genome = self.work / 'genome'
        genome.mkdir()
        with mock.patch.dict(os.environ, {'SCHOLION_GENOME_DIR': str(genome)}):
            web = self.json_of('/api/genome-updates')
            self.assertFalse(web['available'])
            self.assertEqual(self.cli('genome-updates', genome=genome)['available'], web['available'])
            report = {'last_checked': '2026-06-01', 'clinvar': {
                'release': 'synthetic-2026-05', 'new': [], 'changed': [], 'counts': {'new': 0},
            }}
            (genome / 'whats_new.json').write_text(json.dumps(report), encoding='utf-8')
            core.reset_cache()
            cli = self.cli('genome-updates', genome=genome)
            web = self.json_of('/api/genome-updates')
            for key, value in report.items():
                self.assertEqual(value, cli[key])
                self.assertEqual(value, web[key])
            self.assertTrue(web['available'])

    def test_brief_review_saves_date_without_rewriting_wording(self):
        path = self.profile / 'lifestyle_brief.json'
        original = json.dumps(BRIEF)
        path.write_text(original, encoding='utf-8')
        invalid = self.json_of('/api/brief-reviewed', data={'block': 'unknown'})
        self.assertFalse(invalid['ok'])
        self.assertEqual(original, path.read_text(encoding='utf-8'))
        saved = self.json_of('/api/brief-reviewed', data={'block': 'ir'})
        self.assertTrue(saved['ok'], saved)
        expected = json.loads(original)
        expected['blocks'][0]['reviewed'] = date.today().isoformat()
        stored = self.stored(path.name)
        self.assertEqual(expected['blocks'], stored['blocks'])
        self.assertEqual(expected['title'], stored['title'])

    def test_table_ingest_exposes_the_value_and_reimport_does_not_duplicate(self):
        forms = self.work / 'forms'
        forms.mkdir()
        (forms / 'synthetic.csv').write_text(
            'Date,Test,Result,Units,Range\n2026-05-22,Ferritin,17,ng/mL,13-150\n',
            encoding='utf-8',
        )
        first = self.json_of('/api/ingest-labs', data={'path': str(forms)})
        self.assertTrue(first['ok'], first)
        self.assertEqual(1, first['points_added'])
        again = self.json_of('/api/ingest-labs', data={'path': str(forms)})
        self.assertEqual(0, again['points_added'])
        series = self.stored('labs.json')['markers']['ferritin']['series']
        self.assertEqual([17], [p['value'] for p in series if p['date'] == '2026-05-22'])
        web = self.json_of('/api/labs')
        cli = self.cli('labs')
        self.assertEqual(cli['markers'], web['markers'])
        self.assertIn('ferritin', json.dumps(web['markers']))

    def test_study_preview_rejects_a_changed_file_and_commits_one_current_study(self):
        forms = self.work / 'studies'
        forms.mkdir()
        pdf = forms / 'synthetic.pdf'
        pdf.write_bytes(b'%PDF-1.4\n')
        args = {'path': str(forms)}
        history = self.profile / 'studies.json'
        original = history.read_bytes() if history.exists() else None
        with mock.patch('scholion.ingest_studies._ensure_extractor', return_value=True), \
                mock.patch('scholion.ingest_studies._read_pdf', return_value=ULTRASOUND):
            preview = self.json_of('/api/ingest-studies', data={**args, 'preview': True})
            self.assertEqual(1, preview['would_add'])
            pdf.write_bytes(b'%PDF-1.4\n%changed\n')
            refused = self.json_of('/api/ingest-studies',
                                   data={**args, 'confirm': preview['approval_token']})
            self.assertFalse(refused['ok'])
            self.assertEqual(original, history.read_bytes() if history.exists() else None)
            preview = self.json_of('/api/ingest-studies', data={**args, 'preview': True})
            saved = self.json_of('/api/ingest-studies',
                                 data={**args, 'confirm': preview['approval_token']})
            self.assertEqual(1, saved['added'])
            self.assertEqual(0, self.json_of('/api/ingest-studies', data=args)['added'])
        self.assertEqual(1, len(self.stored('studies.json')['studies']))

    def test_both_wearable_routes_rebuild_the_same_series_and_keep_manual_preference(self):
        connect = self.work / 'DI_CONNECT'
        wellness = connect / 'DI-Connect-Wellness'
        wellness.mkdir(parents=True)
        (connect / 'DI-Connect-Aggregator').mkdir()
        (wellness / 'synthetic_userBioMetrics.json').write_text(
            json.dumps([record(weight=60000, bodyFat=25)]), encoding='utf-8')
        args = {'path': str(self.work)}
        first = self.json_of('/api/ingest-wearable', data={**args, 'device': 'garmin'})
        self.assertTrue(first['ok'], first)
        saved = self.stored('wearable_trends.json')['sources']['garmin']
        self.assertEqual(60, saved['metrics']['Weight']['2026-01'])
        again = self.json_of('/api/ingest-garmin', data=args)
        self.assertTrue(again['ok'], again)
        rebuilt = self.stored('wearable_trends.json')['sources']['garmin']
        self.assertEqual(saved['metrics'], rebuilt['metrics'])
        self.assertEqual(saved['body_composition']['events'], rebuilt['body_composition']['events'])
        change = self.json_of('/api/wearable-primary', data={'device': 'garmin'})
        self.assertTrue(change['ok'], change)
        self.assertEqual('garmin', self.stored('metrics.json')['profile']['wearable_primary'])
        before = (self.profile / 'wearable_trends.json').read_bytes()
        refusal = self.json_of('/api/ingest-wearable', data={**args, 'device': 'whoop'})
        self.assertFalse(refusal['ok'])
        self.assertEqual(before, (self.profile / 'wearable_trends.json').read_bytes())
