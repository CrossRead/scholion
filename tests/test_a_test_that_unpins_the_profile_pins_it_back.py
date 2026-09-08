"""A test that removes SCHOLION_PROFILE_DIR puts back what it found.

`run_tests.sh` pins the profile to the synthetic fixture and promises, in its own
header, that the tests «neither read nor change anyone's real profile». The pin is
one environment variable, and `core.profile_dir()` falls through to
`<repo>/profile` when it is absent — which on the owner's machine is the real one.

Two tests removed the pin in their cleanup with a bare `os.environ.pop(...)`
instead of restoring the previous value, so from that point of the run every
in-process reader with no pin of its own was reading the owner's profile. Nothing
failed: the tests do not assert on what they read. What it did was inflate the
reach measurement — `engine/lifestyle.py` reached 85.1% on the owner's machine
and 70.4% anywhere else, on identical code and fixture, because the brief and
focus reports had real wearable data to run over there (task 125). A baseline
that only reproduces on one machine is a gate only one person can run.

This is the enumerator: every place in tests/ that unsets the pin has to restore
it, and the check names the file that does not. The forbidden shape is a bare
`os.environ.pop("SCHOLION_PROFILE_DIR", …)` that is not the `is None` half of a
save-and-restore.
"""
from __future__ import annotations

import pathlib
import re
import unittest

import support  # noqa: F401

TESTS = pathlib.Path(__file__).resolve().parent

POP = re.compile(r'os\.environ\.pop\(\s*"SCHOLION_PROFILE_DIR"|del\s+os\.environ\[\s*"SCHOLION_PROFILE_DIR"')
#: the line before a legitimate pop is the `if <saved> is None:` of a restore
RESTORE_HEAD = re.compile(r"^\s*if\s+\w+(\.\w+)?\s+is\s+None\s*:\s*$")


#: a pin saved for restoring, or the whole environment snapshotted for the same
SAVED = re.compile(r'=\s*os\.environ\.get\(\s*"SCHOLION_PROFILE_DIR"|=\s*dict\(os\.environ\)')


def unrestored_pops(text: str):
    """Line numbers (1-based) of pops that are neither the `is None` half of a
    restore nor preceded, a few lines up, by saving what is about to be removed."""
    lines = text.splitlines()
    bad = []
    for i, line in enumerate(lines):
        if not POP.search(line) or line.lstrip().startswith("#"):
            continue
        prev = lines[i - 1] if i else ""
        if RESTORE_HEAD.match(prev):
            continue
        if any(SAVED.search(l) for l in lines[max(0, i - 12):i]):
            continue
        bad.append(i + 1)
    return bad


class TestThePinIsPutBack(unittest.TestCase):

    def test_every_pop_of_the_pin_is_half_of_a_restore(self):
        offenders = []
        for f in sorted(TESTS.glob("test_*.py")):
            if f.name == pathlib.Path(__file__).name:
                continue
            for ln in unrestored_pops(f.read_text(encoding="utf-8")):
                offenders.append(f"{f.name}:{ln}")
        self.assertEqual(offenders, [],
                         "these remove SCHOLION_PROFILE_DIR without restoring what was there — "
                         "every later in-process reader then falls through to <repo>/profile, "
                         "the owner's real one: save `os.environ.get(...)` first and put it back")

    def test_the_check_sees_the_bare_shape(self):
        bare = 'def tearDown(self):\n    os.environ.pop("SCHOLION_PROFILE_DIR", None)\n'
        self.assertEqual(unrestored_pops(bare), [2])

    def test_the_check_accepts_a_deliberate_unpin_that_was_saved_first(self):
        saved = ('old_pin = os.environ.get("SCHOLION_PROFILE_DIR")\n'
                 'os.environ["SCHOLION_REPO_DIR"] = str(root)\n'
                 'os.environ.pop("SCHOLION_PROFILE_DIR", None)\n')
        self.assertEqual(unrestored_pops(saved), [])
        snap = 'self._env = dict(os.environ)\nos.environ.pop("SCHOLION_PROFILE_DIR", None)\n'
        self.assertEqual(unrestored_pops(snap), [])

    def test_the_check_accepts_the_restore_idiom(self):
        good = ('if old is None:\n    os.environ.pop("SCHOLION_PROFILE_DIR", None)\n'
                'else:\n    os.environ["SCHOLION_PROFILE_DIR"] = old\n')
        self.assertEqual(unrestored_pops(good), [])
        good_attr = ('if self._old is None:\n    del os.environ["SCHOLION_PROFILE_DIR"]\n'
                     'else:\n    os.environ["SCHOLION_PROFILE_DIR"] = self._old\n')
        self.assertEqual(unrestored_pops(good_attr), [])

    def test_the_check_looks_at_something(self):
        touched = [f.name for f in TESTS.glob("test_*.py")
                   if f.name != pathlib.Path(__file__).name
                   and POP.search(f.read_text(encoding="utf-8"))]
        self.assertGreaterEqual(len(touched), 3, "the shape it guards is not in the tree any more — retire or retarget the check")


if __name__ == "__main__":
    unittest.main()
