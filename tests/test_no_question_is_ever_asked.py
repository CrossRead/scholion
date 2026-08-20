"""The test suite may not ask anybody anything.

This is one of the rules that reads as obvious and had already been broken. A
publication run took thirteen minutes and failed: seven tests had spawned
`scholion init`, which asks two questions behind an `isatty()` guard, and the
guard was TRUE — `subprocess.run(capture_output=True)` redirects the two OUTPUT
streams and leaves file descriptor 0 alone, so the child inherited the
developer's terminal. Each waited out its 120-second timeout.

The same suite passed on CI, where stdin is closed before anything starts. That
is the shape of the defect worth naming: a check that behaves differently
depending on whether a human is watching measures the human. It also means CI
could never have caught it, so a test has to.

Three guards, deliberately overlapping, because each covers a hole the others
leave:

* `run_tests.sh` redirects the whole discovery from `/dev/null` — covers
  everything, and only when the suite is started that way;
* `tests/support.py` replaces descriptor 0 at import — covers any runner,
  including an IDE, and only for processes started after the first import;
* the enumeration below — covers the source itself, so a spawn written next
  month is named here rather than discovered in a publication run.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

import support

TESTS = Path(__file__).resolve().parent


def _spawns(tree: ast.AST):
    """Calls that start a process: subprocess.run / Popen / check_output / call."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name in ("run", "Popen", "check_output", "check_call", "call"):
            mod = getattr(getattr(fn, "value", None), "id", "")
            if mod == "subprocess" or name == "Popen":
                yield node


class TestNoTestCanAskAQuestion(unittest.TestCase):

    def test_every_spawn_says_what_its_stdin_is(self):
        """Not «no test currently hangs» — «no test can».

        A spawn without `stdin=` inherits whatever the runner had. That is the
        whole defect, and it is invisible on CI, so it is asserted in the source.
        """
        offenders = []
        for f in sorted(TESTS.glob("*.py")):
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except SyntaxError:                      # pragma: no cover
                continue
            for call in _spawns(tree):
                # `input=` counts: it makes subprocess open a pipe and feed it, so
                # the child's stdin is stated as plainly as by `stdin=`. What is
                # forbidden is saying NOTHING, because then the child gets
                # whatever the runner had — which on a developer's machine is a
                # terminal.
                if not any(k.arg in ("stdin", "input") for k in call.keywords):
                    offenders.append(f"{f.name}:{call.lineno}")
        self.assertEqual(offenders, [], "these spawn a process with the runner's "
                                        "stdin inherited — pass stdin=subprocess.DEVNULL, "
                                        "or input=... if the test feeds the child")

    def test_the_harness_really_did_close_it(self):
        """The guard above is about source; this is about the running process."""
        if os.environ.get("SCHOLION_TESTS_KEEP_STDIN"):
            self.skipTest("stdin deliberately kept for an interactive debugger")
        self.assertFalse(sys.stdin.isatty() if sys.stdin else False,
                         "the suite is holding a terminal — a test could block on it")

    def test_a_command_that_would_ask_does_not(self):
        """The end-to-end version, on the command that actually asks.

        `init` is the one place in the product with a question in it. Run from
        the suite it must complete on its own; if this ever hangs, it fails on
        the timeout rather than waiting for somebody to notice.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            code, out, err = support.run(["init", "--dir", d], timeout=60)
        self.assertEqual(code, 0, err[-400:])
        self.assertIn("data directory", out.lower() + err.lower())


class TestTheProductDoesNotAskWhenNobodyCanAnswer(unittest.TestCase):
    """The other half: a terminal is not the same thing as a person.

    An `isatty()` guard is right for a pipeline and useless for automation that
    runs from a terminal — a Makefile, a provisioning script, a CI job with a
    pseudo-terminal allocated. Those declare themselves, and the product honours
    the declaration.
    """

    def _init(self, env_extra):
        import tempfile
        env = {**os.environ, **env_extra, "PYTHONPATH": str(support.SRC),
               "SCHOLION_OFFLINE": "1", "SCHOLION_LANG": "en"}
        env.pop("SCHOLION_PROFILE_DIR", None)
        with tempfile.TemporaryDirectory() as d:
            return subprocess.run([sys.executable, "-m", "scholion", "init", "--dir", d],
                                  cwd=support.ROOT, env=env, capture_output=True,
                                  text=True, timeout=60, stdin=subprocess.DEVNULL)

    def test_ci_is_taken_as_an_answer(self):
        p = self._init({"CI": "true"})
        self.assertEqual(p.returncode, 0, p.stderr[-400:])

    def test_the_variable_is_taken_as_an_answer(self):
        p = self._init({"SCHOLION_NONINTERACTIVE": "1"})
        self.assertEqual(p.returncode, 0, p.stderr[-400:])


if __name__ == "__main__":
    unittest.main()
