"""Russian does not creep back into the public tree.

`src/tools/check_language.py` measures how much Russian is left in what ships.
The original plan was to drive that number to zero and then fail on the first
Cyrillic letter — but the number does not reach zero, and not because the work
was left half done. What remains is a recogniser quoting the lab-form line it
matches, a pattern that parses a Russian PDF, the endonym in a language
switcher. Each was examined and each has to stay.

A gate set at an unreachable number never turns on. So the gate sits on the
derivative: `src/tools/language_baseline.json` records what was accepted after
that review, and this test fails when a file exceeds its accepted count or when
a file nobody reviewed shows up. The enforced property is not "there is no
Russian" but "no Russian was added without somebody looking at it".

Lowering the baseline is not automatic either. A file that fell below its
accepted count means work was done, and re-recording it is a deliberate act
(`--accept`), so that a drop and a rise both appear in the same diff instead of
the drop being pocketed silently.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

import support

TOOL = support.ROOT / "src" / "tools" / "check_language.py"
BASELINE = support.ROOT / "src" / "tools" / "language_baseline.json"


@unittest.skipUnless(TOOL.exists(), "the language meter is not part of this build")
class TestTheRemainderDoesNotGrow(unittest.TestCase):

    def test_strict_passes(self):
        p = subprocess.run([sys.executable, str(TOOL), "--strict"],
                           cwd=str(support.ROOT), capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0,
                         "Russian was added to a file that ships:\n" + p.stdout + p.stderr)

    def test_the_baseline_is_present_and_explains_itself(self):
        self.assertTrue(BASELINE.exists(),
                        "without the baseline --strict compares against nothing and "
                        "reports every file as new")
        data = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertIn("files", data)
        self.assertTrue(data.get("_note"),
                        "a bare table of numbers gives the next reader no way to tell "
                        "an accepted decision from an unpaid debt")

    @unittest.skipUnless((support.ROOT / "share" / "skill" / "INSTRUCTION.md").exists(),
                         "only the source repository holds every file the baseline names")
    def test_the_baseline_does_not_name_files_that_are_gone(self):
        """A stale entry is a hole in the gate.

        An accepted count for a deleted file keeps its allowance alive: recreate
        the path later and the old number lets the Russian back in without
        review.

        Checked in the source repository only. The package is a subset of it —
        `share/`, the CI workflow and the internal tools stay behind — so inside
        the package a name the baseline knows and the tree does not is normal,
        not a hole.
        """
        data = json.loads(BASELINE.read_text(encoding="utf-8")).get("files", {})
        missing = sorted(k for k in data if not (support.ROOT / k).exists())
        self.assertEqual(missing, [],
                         "the baseline names files that no longer exist — "
                         "re-record it with --accept: " + ", ".join(missing[:10]))


if __name__ == "__main__":
    unittest.main()
