"""Executable level-five selection and comparison cannot silently lose meaning."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import support
from scholion import contract

sys.path.insert(0, str(support.ROOT / 'src/tools'))
import check_interfaces as checks  # noqa: E402


class InterfaceAcceptance(unittest.TestCase):
    def test_selection_uses_routes_and_keeps_both_system_registers(self):
        selected, write = checks.select(['system'], contract.PARITY, contract.PLUGIN)
        self.assertEqual({'system-patient', 'system-clinician', 'systems-list'}, {s.name for s in selected})
        self.assertFalse(write)
        selected, write = checks.select(['focus-log'], contract.PARITY, contract.PLUGIN)
        self.assertEqual([], selected)
        self.assertTrue(write)

    def test_unknown_capabilities_or_changed_contract_refuse_acceptance(self):
        for commands, parity, plugins in (
            (['not-a-command'], contract.PARITY, contract.PLUGIN),
            (['metrics'], {**contract.PARITY, 'GET /api/metrics': 'labs'}, contract.PLUGIN),
            (['metrics'], contract.PARITY, {}),
            (['focus-log'], {}, contract.PLUGIN),
        ):
            with self.subTest(commands=commands), self.assertRaises(ValueError):
                checks.select(commands, parity, plugins)

    def test_comparison_retains_dates_sources_qualifications_and_actions(self):
        data = {'container': {'id': 'synthetic'}, 'value': 42, 'date': '2026-01-01',
                'source': 'synthetic-lab', 'qualified': True,
                'action': {'available': False, 'reason': 'missing_input'}}
        for key in ('value', 'date', 'source', 'qualified', 'action'):
            changed = {**data, key: None}
            with self.subTest(field=key), self.assertRaises(AssertionError):
                checks.equal(checks.payload(data), checks.payload(changed), 'different meaning')

    def test_actual_write_adapters_refuse_and_persist_equivalently(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary).resolve() / 'evidence.json'
            result = subprocess.run([sys.executable, str(support.ROOT / 'src/tools/check_interfaces.py'),
                                     '--commands', 'focus-log', '--out', str(out)],
                                    env=support.env(), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            evidence = json.loads(out.read_text(encoding='utf-8'))
            self.assertTrue(evidence['ok'])
            self.assertTrue(evidence['profile_preserved'])
            self.assertEqual(['en', 'ru'], [r['language'] for r in evidence['checks']])
            self.assertTrue(all(r['equal_persisted_records'] for r in evidence['checks']))
            self.assertIn('recompute', evidence['unexercised_commands'])
            original = out.read_bytes()
            repeated = subprocess.run([sys.executable, str(support.ROOT / 'src/tools/check_interfaces.py'),
                                       '--out', str(out)], env=support.env(), stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
            self.assertNotEqual(0, repeated.returncode)
            self.assertEqual(original, out.read_bytes())
