"""The project's own rule, finally run: on what share of objects did a flag fire?

README, ASSISTANT-RULES and the model instruction all carry the same sentence —
«A threshold that fires on almost everything gets fixed, not explained. A cheap
check before any interpretation: what fraction of objects did the flag hit?» The
colleagues' audit found that sentence in four markdown files and no function
anywhere. A rule stated four times and checked zero times is worse than an
unstated one: it reads as a property of the build.

What the check must NOT become is a suppressor. A person whose panel really is
all abnormal should see every marker flagged, and a rule that hid those flags
because there were many of them would be worse than the defect it fixes. So the
number is computed and shown, and the only thing asserted is arithmetic.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401
from scholion import prevalence


class TestTheRuleIsActuallyImplemented(unittest.TestCase):
    def test_the_sentence_in_the_readme_now_has_a_function(self):
        import pathlib
        readme = pathlib.Path("README.md").read_text(encoding="utf-8")
        self.assertIn("what fraction of objects did the flag hit", readme)
        self.assertTrue(callable(prevalence.report))

    def test_every_row_carries_its_own_denominator(self):
        """«Out of range» looked at every marker with a corridor; «at the edge»
        only at those inside theirs. One shared total would understate the
        second exactly where the check matters most."""
        r = prevalence.report()
        for row in r["rows"]:
            with self.subTest(flag=row["flag"]):
                self.assertIn("looked_at", row)
                self.assertLessEqual(row["hit"], row["looked_at"])

    def test_the_rate_is_arithmetic_not_a_verdict(self):
        r = prevalence.report()
        for row in r["rows"]:
            if row["looked_at"]:
                self.assertAlmostEqual(row["rate"], row["hit"] / row["looked_at"], places=3)

    def test_nothing_is_suppressed_by_a_high_rate(self):
        """The check reports; it must never remove a flag from a person's data."""
        from scholion.engine import labs
        before = len([m for m in labs.analyze_labs().get("markers", []) if m.get("abnormal")])
        prevalence.report()
        after = len([m for m in labs.analyze_labs().get("markers", []) if m.get("abnormal")])
        self.assertEqual(before, after)


class TestTheFlatEdgeZoneIsNamed(unittest.TestCase):
    """The audit's «flat 10 %»: one constant for every analyte, where the correct
    measure is a reference change value that differs by an order of magnitude
    between sodium and CRP. The numbers that would fix it come from a database,
    not from memory — so the limit is stated rather than silently kept."""

    def test_the_constant_says_what_it_is(self):
        import inspect
        from scholion.engine import labs
        src = inspect.getsource(labs)
        self.assertIn("Reference Change Value", src)
        self.assertIn("NEAR_LIMIT_FRACTION", src)

    def test_the_database_that_would_close_it_is_registered(self):
        from scholion import sources
        ids = {s["id"] for s in sources.state()}
        self.assertIn("eflm_biological_variation", ids)


if __name__ == "__main__":
    unittest.main()
