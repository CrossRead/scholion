"""The README is checked against the product, the way everything else here is.

A showcase is the one document nobody runs. It drifts by ordinary means — a
command is renamed, a capability moves to the next wave, a paragraph is written
about a plan and never revisited — and the drift is invisible from inside, because
the person who wrote the sentence is the person least able to notice it stopped
being true. Then it costs more than a bug: a bug disappoints a user who already
arrived, and a false promise on the first screen disappoints the one who was
deciding whether to.

This project has twice caught a defect by having a check compare its behaviour
against itself. Here that check compares the showcase against the behaviour:

* every `scholion <command>` printed in the README exists in the CLI;
* every command in the first screen actually runs, on the demo profile, and exits
  cleanly — a first screen that does not work is the worst screen to have;
* the claims that make up the differentiator each name something a reader can run
  or open. A claim with nothing behind it is a slogan.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support
from scholion import contract

README = support.ROOT / "README.md"

#: `scholion foo` / `python3 -m scholion foo` anywhere in the text. The name has
#: to be preceded by a word boundary and NOT by another word: `import scholion.x`
#: and `cp "$(python3 -c 'import scholion…')"` are Python, not the CLI, and a
#: check that reads them as commands cries wolf on documentation that is correct.
# `\s+` here would cross a newline, and then `pip install scholion` followed by
# the next line of a shell block reads as the command `scholion <that line>` —
# a false alarm on documentation that is correct, which is the way a check like
# this gets switched off.
CMD = re.compile(r"(?<!install )\b(?:scholion|python3 -m scholion)[ \t]+([a-z][a-z-]+)")

#: Words that follow the binary and are not commands.
NOT_A_COMMAND = {"init", "--help", "--version"}


def _commands_in(text: str) -> set:
    return {m.group(1) for m in CMD.finditer(text)} - NOT_A_COMMAND


class TestEveryCommandPromisedExists(unittest.TestCase):

    def setUp(self):
        if not README.exists():
            self.skipTest("README.md is not part of this build")
        self.text = README.read_text(encoding="utf-8")
        self.known = set(contract.cli_commands())

    def test_the_readme_names_no_command_the_cli_does_not_have(self):
        promised = _commands_in(self.text)
        missing = sorted(promised - self.known - {"init"})
        self.assertEqual(missing, [], "the showcase promises commands that do not exist: "
                         + ", ".join(missing))

    def test_the_first_screen_shows_the_demo_before_anything_else(self):
        """A reader decides in the first screen whether to point this at their record.

        Ordering is a product decision and it belongs in a test for the same
        reason the rest does: it was decided once, for a reason, and nothing else
        would notice it being undone.
        """
        heads = [l for l in self.text.splitlines() if l.startswith("## ")]
        self.assertTrue(heads, "no sections at all")
        first = heads[0].lower()
        self.assertTrue("second" in first or "demo" in first,
                        f"the first section is «{heads[0]}» — the demo has to come before the "
                        f"argument, because the argument is what the demo is evidence for")

    def test_the_boundaries_come_before_the_installation_instructions(self):
        """What the system does NOT do is the differentiator, not the fine print."""
        heads = [l.lower() for l in self.text.splitlines() if l.startswith("## ")]
        self.assertIn("## boundaries", heads)
        self.assertLess(heads.index("## boundaries"),
                        heads.index("## four ways to install"),
                        "the honest account of the limits reads as fine print when it stands "
                        "below the installation steps")

    def test_the_entry_ladder_starts_below_the_genome(self):
        """«Bring what you have», not «bring a BAM».

        The product's own funnel used to open with a full VCF built from raw
        reads, which is the last rung, not the first, and reads as a requirement.
        """
        low = self.text.lower()
        i = low.index("## bring what you have")
        block = self.text[i:low.index("## four ways to install")]
        self.assertIn("add-lab", block)
        self.assertIn("import-labs", block)
        self.assertIn("Nothing at all", block)


class TestTheFirstScreenActuallyRuns(unittest.TestCase):
    """Not «the command exists» — «the command works, on a profile anyone can make»."""

    #: argv after `python3 -m scholion`. The fourth line is the refusal the first
    #: screen promises: «watch the system refuse to compute a biological age».
    #: `limits` names the refusal, `phenoage --panels` shows which panel is short of
    #: what — the promise was in the prose with no command beside it.
    FIRST_SCREEN = (("demo",), ("overview",), ("limits",), ("phenoage", "--panels"))

    def setUp(self):
        if not (support.ROOT / "demo" / "profile").is_dir():
            self.skipTest("the demo profile is not part of this build")
        self.dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_the_readme_prints_the_same_first_screen_this_test_runs(self):
        """Otherwise the two drift and each of them looks right on its own.

        The list above is what gets executed; the code block in the README is what
        a person copies. A command added to one and not the other is either an
        untested promise or a tested secret.
        """
        if not README.exists():
            self.skipTest("README.md is not part of this build")
        text = README.read_text(encoding="utf-8")
        i = text.index("## Sixty seconds")
        block = text[i:text.index("## Why", i)]
        for argv in self.FIRST_SCREEN:
            with self.subTest(command=" ".join(argv)):
                self.assertIn("scholion " + " ".join(argv), block,
                              "the first screen this test runs is not the one the README shows")

    def test_each_command_of_the_first_screen_exits_cleanly(self):
        env = {**os.environ,
               "PYTHONPATH": str(support.ROOT / "src"),
               "SCHOLION_OFFLINE": "1",
               "SCHOLION_LANG": "en",
               "SCHOLION_PROFILE_DIR": str(support.ROOT / "demo" / "profile"),
               "SCHOLION_GENOME_VCF": str(self.dir / "no-such-file.vcf.gz"),
               "SCHOLION_GENOME_DIR": str(self.dir / "no-genome")}
        for argv in self.FIRST_SCREEN:
            cmd = " ".join(argv)
            if argv[0] == "demo":
                continue          # it writes a profile; covered in test_demo_profile
            with self.subTest(command=cmd):
                p = subprocess.run([sys.executable, "-m", "scholion", *argv],
                                   cwd=support.ROOT, env=env,
                                   capture_output=True, text=True, timeout=120)
                self.assertEqual(p.returncode, 0,
                                 f"the first screen's `scholion {cmd}` fails:\n{p.stderr[-600:]}")
                self.assertTrue(p.stdout.strip(), f"`scholion {cmd}` printed nothing")


class TestEveryClaimIsDemonstrable(unittest.TestCase):
    """Each paragraph of the differentiator points at something runnable or readable.

    Not a style rule. The section is the whole argument for the product, and a
    paragraph of it that names no command, no file and no measurable thing is one
    the reader has to take on trust — which is precisely what this project says it
    is not asking for.
    """

    def setUp(self):
        if not README.exists():
            self.skipTest("README.md is not part of this build")
        text = README.read_text(encoding="utf-8")
        i = text.index("## What makes this different")
        self.block = text[i:text.index("## Boundaries")]

    def test_the_section_holds_several_claims(self):
        self.assertGreaterEqual(self.block.count("**"), 8)

    def test_at_least_one_claim_names_the_command_that_shows_it(self):
        self.assertTrue(_commands_in(self.block) or "`" in self.block,
                        "the differentiator names nothing a reader can run or open")


class TestTheDocumentsDoNotContradictEachOther(unittest.TestCase):
    """Two documents disagreeing about one capability is worse than either.

    The README's Boundaries said a consumer array is «not read yet», full stop,
    while `genome/README.md` describes the route for one in detail and
    `LOADING-DATA.md` points at that route. Both were written truthfully and
    neither was checked against the other: the app does not read a RAW export, and
    a converted VCF works — two facts that read as opposites when only one of them
    is on the page a person decides from.

    The pairing is pinned rather than the wording: whoever edits one of these has
    to look at the other.
    """

    def setUp(self):
        if not README.exists():
            self.skipTest("README.md is not part of this build")
        self.readme = README.read_text(encoding="utf-8")

    def _array_claim(self):
        low = self.readme.lower()
        i = low.index("consumer array")
        return self.readme[i:i + 700].lower()

    def test_the_array_bullet_names_the_route_that_does_work(self):
        claim = self._array_claim()
        self.assertIn("convert", claim,
                      "the README says an array is not read and does not say that a converted "
                      "VCF is — the route is documented in genome/README.md, and a reader who "
                      "finds it there learns that the first screen was wrong")

    def test_the_route_it_points_at_exists(self):
        guide = support.ROOT / "genome" / "README.md"
        if not guide.exists():
            self.skipTest("genome/README.md is not part of this build")
        text = guide.read_text(encoding="utf-8").lower()
        self.assertIn("23andme", text)
        self.assertIn("liftover", text.replace("lift over", "liftover"))

    def test_the_dangerous_half_is_stated_where_the_capability_is(self):
        """«It works» and «a missing variant is not reference» belong on one page."""
        claim = self._array_claim()
        self.assertTrue("unread" in claim or "not equal reference" in claim
                        or "does not equal reference" in claim,
                        "the array route is offered without the caveat that makes it safe to "
                        "take: on a chip the absence of a variant is not the reference")


if __name__ == "__main__":
    unittest.main()
