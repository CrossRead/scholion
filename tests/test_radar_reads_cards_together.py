"""Batch readings retain every card while avoiding repeated work and stale UI state."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from unittest import mock

import support
from scholion import core, genome, i18n, limits
from scholion.engine import genomics, system_panels as panels


class TestFreshBatch(unittest.TestCase):
    def setUp(self):
        self.addCleanup(i18n.set_lang, i18n.lang())
        i18n.set_lang('en')

    def test_batch_matches_individual_cards_and_only_builds_each_layer_once(self):
        for register in ('patient', 'clinician'):
            with mock.patch.object(panels, '_genetics_layer', wraps=panels._genetics_layer) as build:
                batch = panels.systems(register)
            self.assertEqual(len(panels.domains()), build.call_count)
            self.assertEqual(len(panels.domains()), len(batch['cards']))
            for key, card in batch['cards'].items():
                self.assertEqual(panels.system(key, register), card, key)
            self.assertEqual(register, batch['register'])
        self.assertNotIn('cards', panels.systems())
        self.assertEqual('unknown_register', panels.systems('unknown')['status'])

    def test_input_and_coverage_references_are_fresh_after_each_reading(self):
        table = {'G1': {'chrom': '1', 'mean_depth': 30, 'pct_20x': 90, 'pct_10x': 100},
                 'G2': {'chrom': '2', 'mean_depth': 30, 'pct_20x': 95, 'pct_10x': 100},
                 'GX': {'chrom': 'X', 'mean_depth': 15, 'pct_20x': 10, 'pct_10x': 80}}
        with mock.patch.object(limits, 'callability', return_value=table), \
                mock.patch.object(genomics, '_coverage_median', wraps=genomics._coverage_median) as median, \
                mock.patch.object(genome, '_resolved_vcf', return_value=None) as path:
            with core.reading_session():
                for gene in table:
                    self.assertEqual(genomics.gene_coverage(gene, table), genomics.gene_coverage(gene))
                    genome.vcf_path()
                computed = median.call_count
                genomics.gene_coverage('G1')
                self.assertEqual(computed, median.call_count)
                self.assertEqual(1, path.call_count)
            table['G1']['pct_20x'] = 40
            with core.reading_session():
                self.assertEqual(40, genomics.gene_coverage('G1')['pct_20x'])
                self.assertEqual('low', genomics.gene_coverage('G1')['state'])
                genome.vcf_path()
            self.assertEqual(2, path.call_count)
            self.assertGreater(median.call_count, computed)

    def test_cli_batch_uses_the_same_core_and_register(self):
        data = support.run_json(['system', '--all', '--register', 'clinician'])
        self.assertEqual('clinician', data['register'])
        self.assertEqual({d['key'] for d in panels.domains()}, set(data['cards']))


@unittest.skipUnless(shutil.which('node'), 'requires node for actual page code')
class TestRadarPage(unittest.TestCase):
    def function(self, name):
        source = (support.SRC / 'scholion/web/index.html').read_text(encoding='utf-8')
        prefix = 'async function ' if name == 'viewSecond' else 'function '
        start = source.index(prefix + name + '(')
        return source[start:source.index('\n}\n', start) + 2]

    def run_js(self, script):
        result = subprocess.run([shutil.which('node'), '-e', script], capture_output=True,
                                text=True, stdin=subprocess.DEVNULL, timeout=30)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_only_supported_tests_are_displayed_and_batch_cache_obeys_epoch_and_language(self):
        script = """
const assert=require('node:assert/strict');
let _answerEpoch=2,LANG='ru',_systems=null;const _apiCache=new Map(),withLang=x=>x+'&lang='+LANG;
""" + self.function('visibleTestProposals') + self.function('rememberSystemCards') + """
const rows=[{proposal_status:'withheld',id:'diagnostic'},{proposal_status:'held',id:'supported'},
 {proposal_status:'held',error:'failure'},{id:'legacy'}];
assert.deepEqual(visibleTestProposals(rows).map(x=>x.id),['supported']);
const batch={cards:{amino:{status:'ok',register:'patient',genetics:{found:1}},
 bad:{status:'error',register:'patient'},wrong:{status:'ok',register:'clinician'}}};
rememberSystemCards(batch,'patient',1,'ru');assert.equal(_apiCache.size,0);
rememberSystemCards(batch,'patient',2,'en');assert.equal(_apiCache.size,0);
rememberSystemCards(batch,'patient',2,'ru');assert.equal(_apiCache.size,2);
assert.ok(!_systems.cards);assert.ok(!_systems.register);
batch.cards.amino.genetics.found=100;
assert.equal(JSON.parse([..._apiCache.values()][1]).genetics.found,1);
"""
        self.run_js(script)

    def test_radar_picture_arrives_before_cards_and_a_late_batch_cannot_replace_a_new_screen(self):
        script = """
const assert=require('node:assert/strict');
let DISPLAY_MODE='patient',_answerEpoch=0,LANG='en',painted=0,remembered=0;
const pending={},api=path=>new Promise(resolve=>{pending[path]=resolve;});
const sourceBar=()=>Promise.resolve(''),pageHead=()=>'<h1>RADAR</h1>',t=x=>x;
const renderSystems=()=>painted++,showLoader=()=>{},$=()=>({});
const rememberSystemCards=()=>remembered++;
const root={isConnected:true,innerHTML:''};
""" + self.function('viewSecond') + """
(async()=>{
 const read=viewSecond(root);
 assert.ok(pending['/api/systems?register=patient']);
 pending['/api/radar']({domains:[]});await Promise.resolve();await Promise.resolve();
 assert.equal(painted,1);assert.ok(root.innerHTML.includes('RADAR'));
 root.isConnected=false;root.innerHTML='NEW SCREEN';
 pending['/api/systems?register=patient']({cards:{}});
 pending['/api/second-opinion']({});pending['/api/suggest-tests']({});pending['/api/labs']({});
 await read;assert.equal(remembered,0);assert.equal(root.innerHTML,'NEW SCREEN');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
        self.run_js(script)
