"""The review report distinguishes a duplicate body from an overwritten method."""
from pathlib import Path
import sys
import tempfile
import unittest

import support
sys.path.insert(0, str(support.ROOT / 'src/tools'))
import test_inventory as inventory  # noqa: E402


class TestInventory(unittest.TestCase):
    def test_identical_bodies_are_only_candidates_and_overwrites_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tests').mkdir()
            (root / 'tests/test_sample.py').write_text('''class First:
 def setUp(self): self.input = 1
 def test_value(self):
  """A description is not a different assertion."""
  self.assertEqual(self.input, 1)
class Second:
 def setUp(self): self.input = 2
 def test_value(self): self.assertEqual(self.input, 1)
 def test_value(self): self.assertEqual(self.input, 2)
''', encoding='utf-8')
            report = inventory.static_inventory(root)
            self.assertEqual(['tests/test_sample.py:Second.test_value'], report['overwritten_methods'])
            self.assertEqual([['tests/test_sample.py:First.test_value', 'tests/test_sample.py:Second.test_value']],
                             report['identical_bodies_for_review'])

    def test_nested_suites_retain_order_and_all_ids(self):
        a = unittest.FunctionTestCase(lambda: None)
        b = unittest.FunctionTestCase(lambda: None)
        suite = unittest.TestSuite([a, unittest.TestSuite([b])])
        self.assertEqual([a, b], list(inventory.flatten(suite)))
