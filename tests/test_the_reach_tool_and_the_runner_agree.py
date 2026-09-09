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
import os
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
        def same(a, b):
            # A path from the shell script is «$ROOT/tests/…» with the root
            # substituted; on Windows the root carries backslashes and the tool
            # builds the same path with `Path`. Compare the path, not the string.
            if a and b and ("/" in a or os.sep in a):
                return os.path.normpath(a) == os.path.normpath(b)
            return a == b
        for name, want in sorted(self.exported.items()):
            with self.subTest(variable=name):
                self.assertTrue(same(want, reach.SUITE_ENV.get(name)),
                                f"{name} differs between the runner and the measurement: "
                                f"{want!r} vs {reach.SUITE_ENV.get(name)!r}")

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


class TestNothingIsMeasuredWhenNothingCanBeCompared(unittest.TestCase):
    """`--strict` in a built package answers before it works, not after.

    The accepted numbers describe the source tree; the package skips the tests
    only that tree can run, so its reach is legitimately lower and comparing the
    two would fail for being the wrong tree. That was already the answer — but it
    was reached AFTER running the whole suite a second time under the coverage
    hook, on every cell of the matrix and on the release build. A minute and a
    half, each time, to print a sentence that was decided before a line of it
    executed.
    """

    def test_strict_outside_the_source_tree_does_not_run_the_suite(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as elsewhere:
            with mock.patch.object(reach, "ROOT", pathlib.Path(elsewhere)), \
                    mock.patch.object(reach, "measure",
                                      side_effect=AssertionError("the suite was run")) as m:
                code = reach.main(["--strict"])
        self.assertEqual(0, code, "a package that cannot compare must not fail the build")
        self.assertFalse(m.called, "the suite was measured to reach a foregone conclusion")

    def test_a_plain_report_still_measures_wherever_it_is_run(self):
        """Only the comparison is foregone. Somebody who wants to know how much of
        their own copy the suite runs is asking a real question, and gets it."""
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as elsewhere:
            with mock.patch.object(reach, "ROOT", pathlib.Path(elsewhere)), \
                    mock.patch.object(reach, "measure", return_value={
                        "suite_ok": True, "suite_tail": [], "processes": 1,
                        "backend": "test", "overall": {"hit": 1, "total": 2, "percent": 50.0},
                        "modules": {"x.py": {"hit": 1, "total": 2, "percent": 50.0}},
                    }) as m:
                # The report prints a table, and a fake one in the middle of a
                # suite run reads as a real measurement of something. Swallowed.
                import contextlib as _c, io as _io
                with _c.redirect_stdout(_io.StringIO()):
                    code = reach.main([])
        self.assertEqual(0, code)
        self.assertTrue(m.called, "a plain report stopped measuring")



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


class _WithABaselineOfItsOwn(unittest.TestCase):
    """A throwaway baseline and a suite that does not run.

    Shared by every class below. The measurement costs a minute and a half and
    proves nothing about which numbers get WRITTEN, which is what all of these
    are about; `_fake_measure` also records what the baseline said at the moment
    the suite would have started, because one of these properties is about
    exactly that moment.
    """

    #: What the file claims measured it. Overridden where the point is a
    #: mismatch; `None` leaves the file unstamped, as files written before the
    #: stamp existed are.
    STAMP = None

    def setUp(self):
        import tempfile
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.baseline = self.tmp / "test_reach_baseline.json"
        self.present = reach.tree_modules()
        self.assertGreater(len(self.present), 1, "nothing in the tree to measure")
        self.victim = sorted(self.present)[-1]
        self.assertTrue(self.victim.endswith(".py"))
        self.others = {rel: 50.0 for rel in self.present if rel != self.victim}
        doc = {"_note": "test", "overall": 50.0, "modules": dict(self.others)}
        if self.STAMP:
            doc["taken_with"] = self.STAMP
        self.baseline.write_text(json.dumps(doc), encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fake_measure(self, ok=True, percent=75.0):
        seen = {}

        def measure(argv=None):
            seen["modules"] = json.loads(self.baseline.read_text(encoding="utf-8"))["modules"]
            return {"suite_ok": ok, "suite_tail": ["FAILED"] if not ok else ["OK"],
                    "processes": 1, "backend": "test",
                    "overall": {"hit": 1, "total": 2, "percent": 50.0},
                    "modules": {rel: {"hit": 3, "total": 4, "percent": percent}
                                for rel in self.present}}
        return measure, seen

    def _run(self, argv, ok=True, percent=75.0):
        import contextlib, io
        from unittest import mock
        measure, seen = self._fake_measure(ok, percent)
        out = io.StringIO()
        with mock.patch.object(reach, "BASELINE", self.baseline), \
                mock.patch.object(reach, "measure", side_effect=measure), \
                contextlib.redirect_stdout(out):
            code = reach.main(argv)
        return code, seen, out.getvalue()

    def _run_refusing_to_measure(self, argv):
        """The suite must not be run at all. It raises if it is."""
        import contextlib, io
        from unittest import mock
        out = io.StringIO()
        with mock.patch.object(reach, "BASELINE", self.baseline), \
                mock.patch.object(reach, "measure",
                                  side_effect=AssertionError("the suite was measured")), \
                contextlib.redirect_stdout(out):
            code = reach.main(argv)
        return code, out.getvalue()

    def written(self):
        return json.loads(self.baseline.read_text(encoding="utf-8"))


class TestAcceptCanBeRunWhenTheGuardAboveIsWhatFails(_WithABaselineOfItsOwn):
    """The circle, reproduced: a module in the tree with no accepted number.

    `test_every_module_in_the_tree_has_an_accepted_number` turns the suite red
    and says «run --accept»; `--accept` refuses to record a red suite. For any
    commit that adds a module the instruction could therefore not be followed,
    and four modules were seeded at 0.0 by hand on 08.09.2026 to get out. The
    tool now seeds them itself, BEFORE the measured run starts — which is the
    property checked here: at the moment the suite is measured, the baseline
    already lists the module, so the guard above has nothing to object to.
    """

    def test_accept_succeeds_and_the_written_baseline_names_the_new_module(self):
        code, seen, out = self._run(["--accept"])
        self.assertEqual(0, code, out)
        self.assertIn(self.victim, seen["modules"],
                      "the suite was measured against a baseline that did not list the "
                      "new module — the guard test would have turned it red")
        self.assertEqual(0.0, seen["modules"][self.victim],
                         "a module nobody has reviewed is seeded at 0.0, not at a number "
                         "somebody might mistake for a measurement")
        written = json.loads(self.baseline.read_text(encoding="utf-8"))["modules"]
        self.assertEqual(75.0, written[self.victim],
                         "the measured number, not the seed, is what gets recorded")
        self.assertIn(self.victim, out, "what was seeded is said out loud")

    def test_a_stale_line_is_the_same_circle_from_the_other_side(self):
        """`test_the_baseline_names_nothing_that_is_gone` is the mirror guard:
        a module removed from the tree turns the suite red the same way."""
        doc = json.loads(self.baseline.read_text(encoding="utf-8"))
        doc["modules"]["src/scholion/no_longer_here.py"] = 12.0
        self.baseline.write_text(json.dumps(doc), encoding="utf-8")
        code, seen, out = self._run(["--accept"])
        self.assertEqual(0, code, out)
        self.assertNotIn("src/scholion/no_longer_here.py", seen["modules"])
        written = json.loads(self.baseline.read_text(encoding="utf-8"))["modules"]
        self.assertNotIn("src/scholion/no_longer_here.py", written)

    def test_a_refused_accept_leaves_the_file_as_it_found_it(self):
        before = self.baseline.read_text(encoding="utf-8")
        code, seen, out = self._run(["--accept"], ok=False)
        self.assertEqual(1, code)
        self.assertIn(self.victim, seen["modules"], "seeded for the run all the same")
        self.assertEqual(before, self.baseline.read_text(encoding="utf-8"),
                         "a red suite records nothing — not even the seed")

    def test_strict_still_refuses_a_module_nobody_reviewed(self):
        """The seed is `--accept`'s alone. `--strict` is the gate, and a gate
        that fills in its own gaps is not a gate."""
        if not (reach.ROOT / "share").is_dir():
            # Outside the source repository `--strict` compares nothing, by
            # design (the package skips the tests only the tree can run), and
            # answers 0 before measuring. The gate this test guards exists in
            # the tree; in the package there is nothing for it to refuse.
            self.skipTest("outside the source repository --strict compares nothing")
        before = self.baseline.read_text(encoding="utf-8")
        code, seen, out = self._run(["--strict"])
        self.assertEqual(1, code, out)
        self.assertNotIn(self.victim, seen["modules"])
        self.assertIn("nobody has reviewed", out)
        self.assertEqual(before, self.baseline.read_text(encoding="utf-8"))

class TestABaselineIsNotMovedBetweenMachinesByAccident(_WithABaselineOfItsOwn):
    """A full `--accept` from a second machine does not record work.

    A number in this file is not a property of the code alone: it is what the
    suite reached on one interpreter, with one backend, on one machine — and for
    `bamlite.py` it is 89.4% only where the owner's own alignment sits, because
    the test that reaches it says in its own docstring that it skips everywhere
    else. Run from anywhere but there, `--accept` rewrote all of it, restamped
    the file, and said «✓ recorded as accepted» in one line. On 09.09.2026 that
    would have lowered six modules, one of them from 89.4 to 0.0.

    `--strict` had been printing a warning about this same mismatch for months.
    `--accept` was the half of the pair that ignored it. The refusal comes
    BEFORE the measurement, because the answer never depended on it.
    """

    STAMP = {"python": "1.0", "backend": "the-other-one", "platform": "nowhere"}

    def test_accept_refuses_across_the_stamp(self):
        before = self.baseline.read_text(encoding="utf-8")
        code, out = self._run_refusing_to_measure(["--accept"])
        self.assertEqual(1, code, out)
        self.assertEqual(before, self.baseline.read_text(encoding="utf-8"),
                         "the baseline was moved to this machine anyway")

    def test_the_refusal_costs_nothing(self):
        """`_run_refusing_to_measure` raises if the suite runs. Ninety seconds
        to reach a conclusion settled before a line of it executed is the same
        waste `--strict` outside the source tree was cured of."""
        code, out = self._run_refusing_to_measure(["--accept"])
        self.assertEqual(1, code)
        self.assertIn("nowhere", out, "the refusal does not say what it compared")

    def test_the_refusal_names_both_ways_out(self):
        _code, out = self._run_refusing_to_measure(["--accept"])
        self.assertIn("--accept-new", out)
        self.assertIn("--rebaseline", out)

    def test_rebaseline_is_the_way_through(self):
        code, _seen, out = self._run(["--rebaseline"])
        self.assertEqual(0, code, out)
        self.assertEqual(75.0, self.written()["modules"][self.victim])

    def test_rebaseline_says_what_it_lowers_before_it_writes(self):
        """The file's own rule is that a number may only be lowered
        deliberately, and that the diff is somebody's to justify. Neither is
        true if nobody was shown it at the time."""
        doc = self.written()
        high = sorted(self.others)[0]
        doc["modules"][high] = 99.0
        self.baseline.write_text(json.dumps(doc), encoding="utf-8")
        code, _seen, out = self._run(["--rebaseline"])
        self.assertEqual(0, code, out)
        self.assertIn(high, out)
        self.assertIn("99.0% → 75.0%", out)

    def test_a_rebaseline_that_lowers_nothing_says_so(self):
        _code, _seen, out = self._run(["--rebaseline"], percent=100.0)
        self.assertIn("no accepted number falls", out)


class TestAnUnstampedFileIsNotAMismatch(_WithABaselineOfItsOwn):
    """A baseline written before the stamp existed says nothing about what
    measured it. Refusing over a fact nobody recorded would refuse for ever."""

    STAMP = None

    def test_accept_still_works(self):
        code, _seen, out = self._run(["--accept"])
        self.assertEqual(0, code, out)
        self.assertEqual(75.0, self.written()["modules"][self.victim])


class TestTheSameMachineAcceptsAsBefore(_WithABaselineOfItsOwn):
    """The refusal is about crossing machines, not about accepting."""

    def setUp(self):
        self.STAMP = reach._here()
        super().setUp()

    def test_accept_records_the_whole_measurement(self):
        code, _seen, out = self._run(["--accept"])
        self.assertEqual(0, code, out)
        self.assertEqual(75.0, self.written()["modules"][self.victim])


class TestOnlyTheNewNumberIsWritten(_WithABaselineOfItsOwn):
    """`--accept-new`: the operation the suite's own guard asks for.

    `test_every_module_in_the_tree_has_an_accepted_number` fails when a module
    is added and says «run --accept». What it needs is one line; what `--accept`
    does is rewrite the file. Between those two the whole baseline used to move
    for the sake of a module nobody had reviewed yet.

    Adding a line that did not exist cannot lower anybody's floor, so this one
    runs anywhere — including from a machine the numbers were not taken on,
    which is the case it exists for.
    """

    STAMP = {"python": "1.0", "backend": "the-other-one", "platform": "nowhere"}

    def test_the_new_module_gets_its_measured_number(self):
        code, _seen, out = self._run(["--accept-new"])
        self.assertEqual(0, code, out)
        self.assertEqual(75.0, self.written()["modules"][self.victim])

    def test_no_other_number_moves(self):
        self._run(["--accept-new"])
        after = self.written()["modules"]
        for rel, was in self.others.items():
            with self.subTest(module=rel):
                self.assertEqual(was, after[rel], "an accepted floor was rewritten")

    def test_the_stamp_and_the_overall_are_left_alone(self):
        self._run(["--accept-new"])
        doc = self.written()
        self.assertEqual(self.STAMP, doc["taken_with"],
                         "the file now claims to have been measured here")
        self.assertEqual(50.0, doc["overall"])

    def test_it_says_the_number_was_measured_somewhere_else(self):
        _code, _seen, out = self._run(["--accept-new"])
        self.assertIn("nowhere", out, "a number taken on another machine went in silently")

    def test_the_module_is_listed_before_the_suite_runs(self):
        """Same circle as `--accept`'s: the guard test would turn the suite red
        over exactly the module being recorded."""
        _code, seen, _out = self._run(["--accept-new"])
        self.assertIn(self.victim, seen["modules"])
        self.assertEqual(0.0, seen["modules"][self.victim])

    def test_a_line_with_no_file_behind_it_is_removed(self):
        doc = self.written()
        doc["modules"]["src/scholion/no_longer_here.py"] = 12.0
        self.baseline.write_text(json.dumps(doc), encoding="utf-8")
        code, _seen, out = self._run(["--accept-new"])
        self.assertEqual(0, code, out)
        self.assertNotIn("src/scholion/no_longer_here.py", self.written()["modules"])

    def test_a_red_suite_records_nothing(self):
        before = self.baseline.read_text(encoding="utf-8")
        code, _seen, _out = self._run(["--accept-new"], ok=False)
        self.assertEqual(1, code)
        self.assertEqual(before, self.baseline.read_text(encoding="utf-8"))


class TestNothingToAddIsNotMeasured(_WithABaselineOfItsOwn):
    """The suite costs a minute and a half; whether there is a module to record
    is known from the file. `--accept-new` on a baseline that already describes
    the tree is the commonest way to run it by mistake."""

    def setUp(self):
        super().setUp()
        doc = self.written()
        doc["modules"][self.victim] = 42.0          # nothing missing any more
        self.baseline.write_text(json.dumps(doc), encoding="utf-8")

    def test_it_does_not_run_the_suite(self):
        before = self.baseline.read_text(encoding="utf-8")
        code, out = self._run_refusing_to_measure(["--accept-new"])
        self.assertEqual(0, code, out)
        self.assertIn("nothing to record", out)
        self.assertEqual(before, self.baseline.read_text(encoding="utf-8"))


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
