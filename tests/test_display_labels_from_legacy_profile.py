"""Legacy spellings keep their measurements and use current display labels."""
from __future__ import annotations

import copy
import importlib
import json
import shutil
import subprocess
import unittest
from unittest import mock

import support
from scholion import core, i18n
from scholion.format_views import radar_report

life = importlib.import_module('scholion.engine.lifestyle')


class TestLegacyDisplayLabels(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())

    def test_radar_keeps_original_units_and_localises_both_current_and_movement(self):
        unit = '\u043c\u043c\u043e\u043b\u044c/\u043b'
        row = {'key': 'glucose', 'name': 'Synthetic glucose', 'value': 10,
               'unit': unit, 'ref_low': 3, 'ref_high': 6, 'date': '2026-10-19',
               'flag': 'high', 'abnormal': True}
        raw = {'markers': {'glucose': {**row, 'series': [
            {'date': '2026-09-01', 'value': 5}, {'date': '2026-10-19', 'value': 10}]}}}
        before = copy.deepcopy(raw)
        scores = []
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            with mock.patch.object(life, 'analyze_labs', return_value={'markers': [row]}), \
                    mock.patch.object(core, 'labs', return_value=raw), \
                    mock.patch.object(life, 'lifestyle', return_value={'metrics': []}):
                result = life.health_radar()
            domain = next(d for d in result['domains'] if d['key'] == 'glucose')
            self.assertEqual(domain['abnormal'][0]['unit'], unit)
            self.assertEqual(domain['abnormal'][0]['unit_display'], core.unit_label(unit))
            self.assertEqual(domain['moved'][0]['unit_display'], core.unit_label(unit))
            self.assertIn(core.unit_label(unit), radar_report(result))
            scores.append((domain['score'], domain['delta'], domain['moved'][0]['to_value']))
        self.assertEqual(scores[0], scores[1])
        self.assertEqual(raw, before)

    def test_snapshot_label_follows_metric_identity_not_saved_caption(self):
        saved = {'label': 'Legacy caption', 'token': '[[life:BodyFat]]', 'target_value': 22}
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            label = core.wearable_metrics()['metrics']['BodyFat']['label']
            with mock.patch.object(life, 'lifestyle', return_value={'metrics': [
                    {'key': 'BodyFat', 'label': label, 'value': 27.6, 'unit': '%',
                     'date': '2026-10-19', 'status': 'warn'}]}):
                result = life._brief_snapshot_item(saved)
            self.assertEqual(result['label'], label)
            self.assertEqual(result['key'], 'BodyFat')
            self.assertEqual(result['raw'], 27.6)
            self.assertEqual(saved['label'], 'Legacy caption')

    @unittest.skipUnless(shutil.which('node'), 'requires node for the actual renderer')
    def test_combined_clinvar_token_keeps_its_localised_qualification(self):
        page = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        start = page.index('function clnsigText(')
        function = page[start:page.index('\n}\n', start)+2]
        for language in ('en', 'ru'):
            messages = {key: value for key, value in i18n.messages(language).items()
                        if key.startswith('clinvar.sig.')}
            script = 'const messages=' + json.dumps(messages) + ';const t=k=>messages[k]||"\u27e6"+k+"\u27e7";\n' + function
            script += '\nprocess.stdout.write(clnsigText("Pathogenic/Pathogenic,_low_penetrance|risk_factor"));'
            got = subprocess.check_output([shutil.which('node'), '-e', script], text=True,
                                          encoding='utf-8', stdin=subprocess.DEVNULL, timeout=15)
            expected = ' / '.join(messages['clinvar.sig.' + key] for key in
                                  ('pathogenic', 'pathogenic', 'low_penetrance', 'risk_factor'))
            self.assertEqual(got, expected)
