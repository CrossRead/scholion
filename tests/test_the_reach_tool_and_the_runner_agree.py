"""The reach measurement answers about the run `run_tests.sh` performs.

`check_test_reach.py` runs the suite itself, in a child, and it therefore has to
build the environment itself. That means two spellings of one contract — the
`export` lines in the shell script and the `SUITE_ENV` table in the tool — and
two spellings of one contract is how they drift apart. This project has paid for
that shape before; the answer it settled on is to compare them mechanically
rather than to remember.

The drift would not announce itself. Point `SCHOLION_GENOME_VCF` at nothing in
one and at a real file in the other, and reach over `genome.py` moves by tens of
points for a reason that has nothing to do with any test — and the baseline then
records a number nobody can reproduce.

Nothing here runs the measurement. It takes a minute and a half and it starts a
few hundred processes; a suite that did that to itself on every run would be
switched off within a week. What is checked here is everything the measurement
depends on: the environment, the line counter, the ratchet, and whether the
baseline still describes this tree.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import unittest

import support  # noqa: F401

ROOT = support.ROOT
sys.path.insert(0, str(ROOT / "src" / "tools"))
import check_test_reach as reach  # noqa: E402


class TestTheToolAndTheRunnerAgree(unittest.TestCase):

    def setUp(self):
        script = ROOT / "run_tests.sh"
        if not script.exists():
            self.skipTest("this build does not carry the runner")
        text = script.read_text(encoding="utf-8")
        self.exported = {}
        for m in re.finditer(r'^export (SCHOLION_[A-Z_]+)=(.+)$', text, re.M):
            value = m.group(2).strip().strip('"')
            self.exported[m.group(1)] = value.replace("$ROOT", str(ROOT))

    def test_the_runner_sets_nothing_the_tool_does_not(self):
        missing = sorted(set(self.exported) - set(reach.SUITE_ENV))
        self.assertEqual([], missing,
                         "run_tests.sh pins these and the reach measurement does not, so it "
                         "measures a different run: " + ", ".join(missing))

    def test_the_tool_sets_nothing_the_runner_does_not(self):
        extra = sorted(set(reach.SUITE_ENV) - set(self.exported))
        self.assertEqual([], extra,
                         "the reach measurement pins these and run_tests.sh does not: "
                         + ", ".join(extra))

    def test_every_value_is_the_same_value(self):
        for name, want in sorted(self.exported.items()):
            with self.subTest(variable=name):
                self.assertEqual(want, reach.SUITE_ENV.get(name),
                                 f"{name} differs between the runner and the measurement")

    def test_the_genome_is_switched_off_in_both(self):
        """The one that would move the number most, named on purpose: a run with
        somebody's real VCF connected reaches code no test asked for."""
        for name in ("SCHOLION_GENOME_VCF", "SCHOLION_GENOME_DIR"):
            self.assertFalse(pathlib.Path(reach.SUITE_ENV[name]).exists(),
                             f"{name} points at something that exists — the measured run "
                             f"would read a genome")


class TestTheLineCounterIsRight(unittest.TestCase):
    """What counts as an executable line, checked against cases that were each
    wrong in the first version of this measurement."""

    def _lines(self, src: str) -> set:
        p = pathlib.Path(self.tmp) / "sample.py"
        p.write_text(src, encoding="utf-8")
        return reach.executable_lines(p)

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_docstring_counts_where_it_is_actually_executed(self):
        """And that is not where intuition puts it, which is why it is pinned.

        A MODULE docstring is an executable line: it compiles to a store into
        `__doc__`, and it runs on import. A FUNCTION docstring is not: it sits in
        the code object's constants and nothing ever executes it. A counter that
        treated both the same would be wrong for every file in this project, and
        wrong in the flattering direction for the ones with the longest prose —
        which, here, is most of them.
        """
        module_doc = self._lines('"""Just a docstring."""\nx = 1\n')
        self.assertEqual({1, 2}, module_doc,
                         "a module docstring stores __doc__ and is executed")
        function_doc = self._lines('def f():\n    """Just a docstring."""\n    return 1\n')
        self.assertNotIn(2, function_doc,
                         "a function docstring is a constant — counting it would inflate "
                         "every module in this repository")
        self.assertEqual({1, 3}, function_doc)

    def test_a_decorator_and_its_function_are_both_lines(self):
        src = "def d(f):\n    return f\n\n@d\ndef g():\n    return 1\n"
        got = self._lines(src)
        self.assertIn(4, got, "the decorator line is executed and was not counted")
        self.assertIn(5, got, "the def line is executed and was not counted")

    def test_a_body_inside_a_function_counts(self):
        """The whole point of walking nested code objects: a function body lives
        in its own code object, and a counter that reads only the module's
        misses every line of every function."""
        got = self._lines("def f():\n    a = 1\n    return a\n")
        self.assertIn(2, got)
        self.assertIn(3, got)

    def test_a_module_with_no_statements_has_nothing_to_reach(self):
        """And answers the same on every Python this project supports.

        An empty `__init__.py` compiles to an implicit return, and the line that
        return is numbered at moved between 3.10 and 3.11: 1 there, 0 here. This
        counter drops line 0, so one empty file was measured on one interpreter
        and skipped on the other — and a baseline recorded here then failed on
        3.10 over a module with no code in it. The vendored package has such a
        file, and the matrix found it the only way it could: after publication.

        So the question is answered from the SOURCE. No statements, nothing to
        reach, on every version.
        """
        self.assertEqual(set(), self._lines(""))
        self.assertEqual(set(), self._lines("\n\n"))
        self.assertEqual(set(), self._lines("# only a comment\n"))

    def test_a_docstring_alone_is_still_a_statement(self):
        """It stores `__doc__`, so it runs. Which LINE it is numbered at is not
        asserted: that is exactly the kind of detail that differs between
        versions, and pinning it here would be repeating the mistake above."""
        self.assertTrue(self._lines('"""just a docstring"""\n'),
                        "a module docstring executes and must be counted")

    def test_a_file_that_does_not_compile_is_not_a_crash(self):
        got = self._lines("def broken(:\n")
        self.assertEqual(set(), got)

    def test_the_real_package_is_not_empty(self):
        """A counter that returns nothing makes every module 0/0 and the ratchet
        silent. The failure mode of a measurement is always a confident zero."""
        got = reach.executable_lines(ROOT / "src" / "scholion" / "core.py")
        self.assertGreater(len(got), 100, "core.py cannot plausibly have this few lines")


class TestTheRatchetCanFire(unittest.TestCase):

    def _result(self, modules):
        return {"modules": {k: {"percent": v, "hit": 1, "total": 1} for k, v in modules.items()}}

    def test_a_module_that_fell_is_reported(self):
        accepted = reach._baseline()
        rel, was = next(iter(sorted(accepted.items())))
        fell, unlisted, vanished = reach.compare(self._result({rel: was - 0.1}))
        self.assertEqual([(rel, was, was - 0.1)], fell)

    def test_a_module_nobody_reviewed_is_reported(self):
        fell, unlisted, vanished = reach.compare(self._result({"src/scholion/brand_new.py": 3.0}))
        self.assertIn("src/scholion/brand_new.py", unlisted,
                      "a new module could arrive with no reach at all and nothing would say so")

    def test_a_module_that_rose_is_not_an_error(self):
        accepted = reach._baseline()
        rel, was = next(iter(sorted(accepted.items())))
        fell, unlisted, vanished = reach.compare(self._result({rel: min(100.0, was + 5)}))
        self.assertEqual([], fell)

    def test_holding_exactly_the_accepted_number_passes(self):
        accepted = reach._baseline()
        rel, was = next(iter(sorted(accepted.items())))
        fell, _, _ = reach.compare(self._result({rel: was}))
        self.assertEqual([], fell, "the baseline is a floor, not a target to exceed")


class TestTheBaselineDescribesThisTree(unittest.TestCase):
    """Cheap, and it catches the case the expensive measurement exists for: a
    module added without anybody deciding how well it is tested."""

    def setUp(self):
        if not reach.BASELINE.exists():
            self.skipTest("no baseline in this build")
        self.accepted = json.loads(reach.BASELINE.read_text(encoding="utf-8"))["modules"]
        self.present = {p.relative_to(ROOT).as_posix()
                        for p in (ROOT / "src" / "scholion").rglob("*.py")
                        if "__pycache__" not in p.parts and reach.executable_lines(p)}

    def test_every_module_in_the_tree_has_an_accepted_number(self):
        missing = sorted(self.present - set(self.accepted))
        self.assertEqual([], missing,
                         "these modules have no accepted reach — run "
                         "`python3 src/tools/check_test_reach.py --accept` and justify the "
                         "numbers in the commit: " + ", ".join(missing))

    def test_the_baseline_names_nothing_that_is_gone(self):
        stale = sorted(set(self.accepted) - self.present)
        self.assertEqual([], stale,
                         "the baseline holds modules this tree does not: " + ", ".join(stale))

    def test_no_accepted_number_is_impossible(self):
        for rel, pct in sorted(self.accepted.items()):
            with self.subTest(module=rel):
                self.assertGreaterEqual(pct, 0.0)
                self.assertLessEqual(pct, 100.0)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
