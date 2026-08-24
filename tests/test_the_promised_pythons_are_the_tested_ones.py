"""`requires-python` is a promise, and three places have to mean the same by it.

The promise itself lives in `pyproject.toml`. The versions actually exercised
live in the CI matrix. And the runner now takes the oldest of them and runs the
suite under it before a tag rather than after one. Three statements of one fact,
which is how they drift — so they are compared here instead of remembered.

The cost of not comparing them was paid twice in two days, both times on a tag
that was already out. A repair verified on one interpreter, promised about four:
first a release build that failed on the runner and never reached the registry,
then a published version whose matrix went red on Python 3.10 over a difference
in how an empty module is numbered. Neither was found by a test; both were found
by the matrix, and the matrix lives where it can only answer after publication.

What this file cannot check is that somebody has uv installed. The runner says so
out loud when it does not — a check that cannot run is not a check that passed —
and that sentence is the last line of defence when this one has done all it can.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import support

ROOT = support.ROOT


def floor_from_pyproject(text: str):
    m = re.search(r'^requires-python\s*=\s*"[^0-9]*([0-9]+\.[0-9]+)', text, re.M)
    return m.group(1) if m else None


def versions_from_classifiers(text: str):
    return sorted(re.findall(r'"Programming Language :: Python :: (3\.\d+)"', text),
                  key=lambda v: [int(x) for x in v.split(".")])


class TestTheFloorIsOneNumber(unittest.TestCase):

    def setUp(self):
        self.pyproject = ROOT / "pyproject.toml"
        if not self.pyproject.exists():
            self.skipTest("this build carries no pyproject.toml")
        self.text = self.pyproject.read_text(encoding="utf-8")

    def test_the_promise_is_readable_at_all(self):
        self.assertIsNotNone(floor_from_pyproject(self.text),
                             "requires-python names no floor the runner could read")

    def test_the_promise_matches_the_oldest_version_claimed_in_the_classifiers(self):
        """Two claims about the same thing, one line apart in one file."""
        classifiers = versions_from_classifiers(self.text)
        self.assertTrue(classifiers, "no Python versions are claimed in the classifiers")
        self.assertEqual(classifiers[0], floor_from_pyproject(self.text),
                         "requires-python and the oldest classifier disagree about the floor")


class TestTheMatrixRunsWhatIsPromised(unittest.TestCase):

    def setUp(self):
        self.wf = ROOT / ".github" / "workflows" / "tests.yml"
        pyproject = ROOT / "pyproject.toml"
        if not (self.wf.exists() and pyproject.exists()):
            self.skipTest("this build carries no workflow or no pyproject.toml")
        self.claimed = versions_from_classifiers(pyproject.read_text(encoding="utf-8"))
        text = self.wf.read_text(encoding="utf-8")
        m = re.search(r'^\s*python:\s*\[([^\]]+)\]', text, re.M)
        self.assertIsNotNone(m, "the matrix names no python list this test can read")
        self.tested = sorted(re.findall(r'"(3\.\d+)"', m.group(1)),
                             key=lambda v: [int(x) for x in v.split(".")])

    def test_every_promised_version_is_in_the_matrix(self):
        missing = [v for v in self.claimed if v not in self.tested]
        self.assertEqual([], missing,
                         "promised and never run: " + ", ".join(missing))

    def test_the_matrix_promises_nothing_extra(self):
        extra = [v for v in self.tested if v not in self.claimed]
        self.assertEqual([], extra,
                         "run but not promised — either claim them or stop paying for them: "
                         + ", ".join(extra))


class TestTheRunnerTakesTheFloorFromThePromise(unittest.TestCase):
    """Not from a number typed into the shell script.

    A version written into the runner is a fourth statement of the same fact, and
    the one nobody would think to update: the promise would move and the local
    check would go on reassuring about the version it used to be.
    """

    def setUp(self):
        self.script = ROOT / "run_tests.sh"
        if not self.script.exists():
            self.skipTest("this build carries no runner")
        self.text = self.script.read_text(encoding="utf-8")

    def test_the_step_exists(self):
        self.assertIn("SCHOLION_SKIP_OLDEST", self.text,
                      "the runner does not check the oldest promised Python at all")

    def test_it_reads_the_floor_rather_than_naming_one(self):
        step = self.text[self.text.index("SCHOLION_SKIP_OLDEST"):]
        self.assertIn("pyproject.toml", step,
                      "the runner does not read the floor from the promise")
        hardcoded = re.findall(r'--python "?3\.\d+', step)
        self.assertEqual([], hardcoded,
                         "the runner names a version instead of reading it: " + ", ".join(hardcoded))

    def test_it_says_so_when_it_cannot_run(self):
        """The failure mode of this whole arrangement is a step that quietly does
        nothing on a machine without uv, leaving `requires-python` unverified and
        looking verified."""
        step = self.text[self.text.index("SCHOLION_SKIP_OLDEST"):]
        self.assertIn("uv is not installed", step,
                      "a machine without uv would skip the check in silence")

    def test_it_carries_no_control_characters(self):
        """Written after this file's own step was spliced in with a `\\1` that
        became the byte 0x01: the shell then read a control character as a
        version number, and «not empty» passed for «looks like a version»."""
        raw = self.script.read_bytes()
        bad = sorted({b for b in raw if b < 9 or 13 < b < 32})
        self.assertEqual([], bad,
                         "the runner contains control bytes: " + ", ".join(map(hex, bad)))


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
