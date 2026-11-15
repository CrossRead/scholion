"""Corrected citations retract cached benefits without discarding readings."""
import ast
import unittest
from unittest.mock import patch

import support
from scholion import core, i18n
from scholion.engine import genomics


class TestLongevitySourceCorrections(unittest.TestCase):
    def test_rejected_sources_cannot_support_current_directions(self):
        book = core._read_knowledge_raw('longevity_directions.json')
        self.assertEqual(len(book['_meta']['source_review_positions']), 12)
        for rs in book['_meta']['source_review_positions']:
            row = book['directions'][rs]
            with self.subTest(rs=rs):
                rejected = row['source_review']['rejected_pmid']
                self.assertNotIn(rejected, row['pmids'])
                self.assertNotIn('/'+rejected+'/', ';'.join(row['source_passport']['sources']))
                self.assertIsNone(row['favorable'])
                self.assertFalse(row['personal_effect_permitted'])
                self.assertFalse(row['verdict_by_copies'])

    def test_old_cached_advice_and_verdict_do_not_survive_a_source_correction(self):
        book = core._read_knowledge_raw('longevity_directions.json')
        old = [{'rsid': rs, 'gene': book['directions'][rs]['gene'], 'genotype': 'TT',
                'verdict': 'plus', 'copies_favorable': 2, 'favorable': 'T',
                'label': 'OBSOLETE', 'note': 'OBSOLETE', 'action': 'OBSOLETE',
                'zygosity_note': 'OBSOLETE', 'population_note': 'OBSOLETE',
                'confidence': 'high', 'pmids': [book['directions'][rs]['source_review']['rejected_pmid']]}
               for rs in book['_meta']['source_review_positions']]
        previous = i18n.lang()
        self.addCleanup(i18n.set_lang, previous)
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            with patch.object(core, 'longevity_data', return_value={'known': old}), \
                 patch.object(core, 'genotype_status', return_value={'genotype': 'TT', 'depth': 30, 'confidence': 'called'}), \
                 patch.object(genomics, 'apoe', return_value={'status': 'no_genome'}):
                result = genomics.longevity_findings()
            for row in result['known']:
                if row['rsid'] not in book['_meta']['source_review_positions']:
                    continue
                with self.subTest(language=language, rs=row['rsid']):
                    self.assertEqual(row['genotype'], 'TT')
                    self.assertIsNone(row['verdict_token'])
                    self.assertIsNone(row['verdict'])
                    self.assertIsNone(row['copies_favorable'])
                    self.assertFalse(row['interpretation']['personalized'])
                    self.assertNotIn('OBSOLETE', str(row))
                    self.assertEqual(row['pmids'], book['directions'][row['rsid']]['pmids'])

    def test_generator_does_not_create_new_neutral_or_positive_verdicts(self):
        # Execute the real pure builder function without its top-level VCF I/O.
        path = support.ROOT / 'src/ingest/longevity_findings_build.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('known_block', '_text')]
        book = core._read_knowledge_raw('longevity_directions.json')
        entries = {rs: book['directions'][rs] for rs in book['_meta']['source_review_positions']}
        env = {'directions': entries, 'G': {rs: {'gt': 'TT', 'dp': 30} for rs in entries}}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), 'exec'), env)
        result = env['known_block']()
        self.assertEqual(len(result), 12)
        self.assertTrue(all(r['verdict'] == 'reference_only' for r in result))


if __name__ == '__main__':
    unittest.main()
