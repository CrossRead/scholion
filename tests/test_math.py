"""The arithmetic that cannot be checked by eye.

Only those quantities that have an externally verifiable answer are here: the
combinatorial sensitivity bound of n-of-1, the behaviour of the permutation test
and the rule for excluding days with a protocol violation. Checks like these do
not depend on any particular person's data and survive any interface edits.
"""
import importlib.util
import unittest
from math import comb
from pathlib import Path

import support

_spec = importlib.util.spec_from_file_location("nof1", support.ROOT / "src" / "ingest" / "nof1.py")
nof1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nof1)


class TestSensitivityBound(unittest.TestCase):
    """Significance is bounded by the NUMBER OF BLOCKS, not by the number of days observed."""

    def test_the_minimum_achievable_p(self):
        for n in (4, 6, 8, 10):
            with self.subTest(blocks=n):
                self.assertAlmostEqual(nof1.min_achievable_p(n), 1 / comb(n, n // 2), places=12)

    def test_the_classic_ABAB_yields_no_significance(self):
        """Four blocks: a minimum of 1/6 ≈ 0.167. No duration will fix that."""
        self.assertGreater(nof1.min_achievable_p(4), 0.05)
        self.assertLessEqual(nof1.min_achievable_p(6), 0.05)

    def test_a_perfect_separation_yields_the_minimum(self):
        """If every A block is worse than every B block, the test is obliged to return exactly the lower bound."""
        a, b = [10.0, 11.0, 12.0], [20.0, 21.0, 22.0]
        _obs, p, _perm = nof1.block_permutation_test(a, b, direction="increase")
        self.assertAlmostEqual(p, nof1.min_achievable_p(6), places=12)

    def test_shuffled_blocks_yield_no_significance(self):
        a, b = [10.0, 21.0, 12.0], [20.0, 11.0, 22.0]
        _obs, p, _perm = nof1.block_permutation_test(a, b, direction="increase")
        self.assertGreater(p, 0.05)


class TestCompliance(unittest.TestCase):
    """A day with a protocol violation drops out together with the following one (carry-over of the effect)."""

    def test_a_violation_removes_the_day_and_the_next_one(self):
        excluded = nof1._excluded_days({"compliance_log": {"2026-08-05": {"ok": False}}})
        self.assertIn("2026-08-05", excluded)
        self.assertIn("2026-08-06", excluded, "the day after a violation is not clean either")
        self.assertNotIn("2026-08-07", excluded)

    def test_a_day_without_a_mark_does_not_count_as_complied_with(self):
        excluded = nof1._excluded_days({"compliance_log": {"2026-08-05": {"ok": True}}})
        self.assertEqual(excluded, set(),
                         "a day with no mark is not excluded, but neither does it count as "
                         "complied with — it goes into the unknowns and lowers the coverage")


if __name__ == "__main__":
    unittest.main()
