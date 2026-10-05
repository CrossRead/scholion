"""C17 emitted-output acceptance: every read door, both languages and aggregates.

The denominator is emitted basis records, not catalogue entries. Family-specific
mutation regressions enforce withdrawal; this inventory checks their assembled
outputs, explicit nonclinical kinds and all command coverage. Identifier syntax
is not scientific certification and this test never contacts a clinical source.
"""
from __future__ import annotations

import io
import json
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout

import support  # noqa: F401 -- synthetic profile only
from scholion import cli, core, engine, i18n
from scholion.conclusion_basis import source_has_identifier
from test_every_face_carries_the_same_positions_and_levels import _Read
from test_one_container_looks_the_same_alone_and_among_many import CALLS

# Independently emitted bases. A new *_basis field must join this inventory.
BASIS_FIELDS = {'conclusion_basis', 'subclaim_basis', 'clinical_basis', 'proposal_basis',
                'target_basis', 'threshold_basis', 'action_basis', 'management_basis',
                'recheck_basis', 'cpic_basis', 'gene_role_basis', 'why_basis', 'quote_basis',
                'note_basis', 'still_matters_when_basis', 'effect_basis', 'reason_basis',
                'selection_basis', 'timing_basis', 'priority_basis', 'specialist_basis',
                'claim_basis', 'dose_basis', 'mechanism_basis', 'condition_basis', 'marker_basis', 'monitoring_basis', 'route_basis'}
# These name exactly a different kind of datum, never a general "clinical" escape.
NONCLINICAL_BASES = {'model_basis', 'display_basis', 'intervention_basis', 'basis'}
NONCLINICAL_KINDS = {'derived_measurement', 'display_reference_comparison', 'display_index',
                    'population_model_calculation', 'product_boundary'}


def emitted_bases(value, path=()):
    """Yield named structured bases with stable paths, including list aggregates."""
    if isinstance(value, dict):
        for name, basis in (value.get('subclaim_basis') or {}).items():
            if basis['status'] == 'incomplete':
                for destination in (name, 'expect_check' if name == 'expect' else name):
                    if value.get(destination) is not None:
                        raise AssertionError('Withheld adjacent claim emitted: ' + str((*path, destination)))
        for name, item in value.items():
            if name.endswith('_basis') and name not in BASIS_FIELDS | NONCLINICAL_BASES:
                raise AssertionError('Uninventoried basis field: ' + '.'.join(map(str, (*path, name))))
            if name in BASIS_FIELDS and isinstance(item, dict):
                entries = [(name, item)] if item.get('status') in ('complete', 'incomplete') else list(item.items())
                for claim, basis in entries:
                    if isinstance(basis, dict) and basis.get('status') in ('complete', 'incomplete'):
                        yield (*path, name, claim), basis
            yield from emitted_bases(item, (*path, name))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from emitted_bases(item, (*path, index))


class TestEveryConclusionCarriesASourceAndAMechanism(_Read):
    def test_all_read_commands_emit_supported_claims_or_explicit_refusals_in_both_languages(self):
        self.addCleanup(i18n.set_lang, getattr(i18n._state, 'current', None))
        counts = Counter()
        for language in ('en', 'ru'):
            i18n.set_lang(language)
            calls = CALLS + [['system', row['key'], '--register', register]
                            for row in engine.systems()['systems'] for register in ('patient', 'clinician')]
            for command in calls:
                with self.subTest(language=language, command=command):
                    out, err = io.StringIO(), io.StringIO()
                    with redirect_stdout(out), redirect_stderr(err):
                        code = cli.main(command + ['--json', '--lang', language])
                    self.assertEqual(0, code, err.getvalue())
                    raw = out.getvalue()
                    self.assertNotIn('⟦', raw)
                    # A few read doors intentionally print plain text (doc/skill).
                    try:
                        data = json.loads(raw)
                    except ValueError:
                        self.assertIn(command[0], ('doc', 'skill', 'assistant'))
                        continue
                    for path, basis in emitted_bases(data):
                        counts[language + ':' + basis['status']] += 1
                        if basis['status'] == 'complete':
                            self.assertTrue(source_has_identifier(basis.get('source')), path)
                            self.assertIsInstance(basis.get('mechanism'), str, path)
                            self.assertTrue(basis['mechanism'].strip(), path)
                            self.assertEqual([], basis.get('missing', []), path)
                        else:
                            self.assertTrue(basis.get('missing'), path)
                            self.assertTrue(basis.get('reason'), path)
                    core.reset_cache()
        for language in ('en', 'ru'):
            self.assertGreater(counts[language + ':complete'], 0, 'no supported clinical output was exercised')
            self.assertGreater(counts[language + ':incomplete'], 0, 'no refusal was exercised')
        self.assertEqual(counts['en:complete'], counts['ru:complete'])
        self.assertEqual(counts['en:incomplete'], counts['ru:incomplete'])

    def test_withheld_fields_in_the_other_output_families_do_not_leak_raw_clinical_prose(self):
        outputs = (engine.longevity_findings(), engine.lipid_genetics(), engine.metrics_summary(),
                   engine.lifestyle(), engine.health_radar(), engine.clinvar_findings(), engine.acmg_findings())

        def check(value):
            if isinstance(value, dict):
                for field, basis in (value.get('clinical_basis') or {}).items():
                    if basis['status'] == 'incomplete':
                        self.assertIn(value.get(field), (None, [], 'unknown'))
                if value.get('output_kind') in ('display_index', 'population_model_calculation'):
                    basis = value.get('display_basis') or value.get('model_basis')
                    self.assertTrue(basis['source'])
                    self.assertTrue(basis['method'])
                    self.assertTrue(basis['limitation'])
                for item in value.values():
                    check(item)
            elif isinstance(value, list):
                for item in value:
                    check(item)

        for output in outputs:
            check(output)


if __name__ == '__main__':
    unittest.main()
