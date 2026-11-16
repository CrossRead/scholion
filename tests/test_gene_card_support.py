"""Renderer fixtures retain their bytes without large native stdin pipe reads."""
from __future__ import annotations
import hashlib
import json
import shutil
import unittest
import gene_card_support


@unittest.skipUnless(shutil.which('node'), 'requires the renderer runtime')
class RendererInput(unittest.TestCase):
    SCRIPT = """
const fs=require('node:fs'),crypto=require('node:crypto');
const data=fs.readFileSync(0);
console.log(JSON.stringify({size:data.length,regular:fs.fstatSync(0).isFile(),
 sha256:crypto.createHash('sha256').update(data).digest('hex')}));
"""

    def test_large_unicode_fixture_is_a_seekable_complete_utf8_stream(self):
        payload = ('Synthetic \u03bb \u0433\u0435\u043d\n' * 250000)
        result = gene_card_support.run(self.SCRIPT, input=payload, text=True,
                                       capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = payload.encode('utf-8')
        self.assertEqual(json.loads(result.stdout), {
            'size': len(expected), 'regular': True,
            'sha256': hashlib.sha256(expected).hexdigest()})

    def test_binary_fixture_is_not_decoded_or_truncated(self):
        payload = bytes(range(256)) * 4096
        result = gene_card_support.run(self.SCRIPT, input=payload,
                                       capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            'size': len(payload), 'regular': True,
            'sha256': hashlib.sha256(payload).hexdigest()})

    def test_omitted_input_reaches_eof_without_reading_the_terminal(self):
        result = gene_card_support.run(self.SCRIPT, text=True,
                                       capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['size'], 0)

    def test_renderer_failure_is_returned_to_the_assertion(self):
        result = gene_card_support.run(
            "process.stderr.write('SYNTHETIC_FAILURE');process.exit(7)",
            input='{}', text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stderr, 'SYNTHETIC_FAILURE')
