"""A consumer's Crossread snapshot has an explicit version and cannot drift silently."""
import hashlib
import json
from pathlib import Path
import unittest


class TestCrossreadVendor(unittest.TestCase):
    def test_vendored_css_matches_the_versioned_distribution(self):
        web = Path(__file__).resolve().parents[1] / 'src/scholion/web'
        manifest = json.loads((web / 'crossread.manifest.json').read_text(encoding='utf-8'))
        self.assertEqual('Crossread', manifest['name'])
        self.assertEqual('1.1.0', manifest['version'])
        self.assertEqual('Apache-2.0', manifest['license'])
        self.assertEqual([], manifest['runtime_dependencies'])
        self.assertEqual(18, len(manifest['components']))
        css = (web / 'crossread.css').read_bytes()
        self.assertEqual(manifest['sha256'], hashlib.sha256(css).hexdigest())

    def test_checkout_keeps_the_vendor_checksum_bytes_on_windows(self):
        root = Path(__file__).resolve().parents[1]
        attributes = (root / '.gitattributes').read_text(encoding='utf-8')
        self.assertIn('src/scholion/web/crossread.css text eol=lf', attributes)
