"""A gene-disease validity assertion remains independent of variant confidence."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import support  # noqa: F401
from scholion import core, i18n
from scholion.panel_reference import gene_reference_context, reference_lines


class TestGenCCPanelSnapshot(unittest.TestCase):
    def test_every_selected_identity_is_accounted_for_in_both_languages(self):
        book=core._read_knowledge('gencc_panel_assertions.json');genes=book['genes']
        themes=core._read_knowledge('thematic_gene_panels.json')['panels']
        self.assertEqual(set(genes),{g for p in themes.values() for g in p['genes']})
        self.assertEqual(len(genes),525)
        self.addCleanup(i18n.set_lang,i18n.lang())
        classes=set()
        for language in ('en','ru'):
            i18n.set_lang(language)
            with patch.object(core,'profile_genotypes',side_effect=AssertionError('reference must not read genome')):
                for name,entry in genes.items():
                    context=gene_reference_context(name,[])
                    rows=context['gencc_assertions'];self.assertEqual(len(rows),len(entry['submissions']),name)
                    self.assertIsNone(context['level']);self.assertEqual(context['gencc_version'],'2026-10-14')
                    self.assertEqual(context['scope'],'reference_only')
                    self.assertEqual({r['submission_id'] for r in rows},{r['submission_id'] for r in entry['submissions']})
                    for row in rows:
                        classes.add(row['classification'])
                        self.assertTrue(row['submitter']);self.assertTrue(row['submission_version'])
                        self.assertTrue(row['classification_label']);self.assertNotIn('⟦',row['moi_label'])
                        if language=='ru':
                            self.assertRegex(row['disease_label'],'[А-Яа-яЁё]',name)
                            self.assertRegex(row['classification_label'],'[А-Яа-яЁё]',name)
                            self.assertRegex(row['moi_label'],'[А-Яа-яЁё]',name)
                    if not rows:
                        self.assertEqual(context['gencc_status'],'no_assertions_in_snapshot')
                        self.assertTrue(any('2026-10-14' in line for line in reference_lines({'reference_context':context})))
        self.assertEqual(classes,{'Definitive','Strong','Moderate','Limited','Supportive',
                                 'Disputed Evidence','Refuted Evidence','No Known Disease Relationship'})
