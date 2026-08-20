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
    """The four lines a stranger copies, run in the order and the state they are in.

    The previous version of this class handed every command an environment with
    `SCHOLION_PROFILE_DIR` already pointing at the repository's own demo profile,
    and skipped the first line altogether. So it proved that the commands work
    when somebody has already arranged for them to work — which is the exact
    shape of check this project has caught itself making three times, and it
    missed a defect that met every new user:

        scholion demo        writes into <data>/demo/profile
        scholion overview    reads   <data>/profile

    The first two commands of the README produced an empty profile. Reported from
    a clean-machine run of `pip install scholion`; the test was green throughout,
    because a command that prints «profile is empty» exits 0 and prints something.

    Two things changed. The run starts from an empty data directory and sets no
    profile path, so the commands have to arrange the state themselves. And the
    output is read: exit 0 and non-empty is what an honest refusal looks like too.
    """

    #: argv after `python3 -m scholion`, in the order the README prints them.
    #: The first line has to be the one that puts the demo where the rest read
    #: from — `demo` builds it in a directory of its own on purpose, which is
    #: right, and is why it cannot be the opening line of the first screen.
    FIRST_SCREEN = (("init", "--demo"), ("overview",), ("limits",), ("phenoage", "--panels"))

    #: What the demo profile must be seen to contain. Not a phrase from the
    #: report's own wording — a fact about the fictional person, so that a
    #: rewrite of the prose does not silently turn this into a check of nothing.
    EVIDENCE = {"overview": re.compile(r"markers:\s*([1-9]\d*)")}

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.env = {**os.environ,
                    "PYTHONPATH": str(support.ROOT / "src"),
                    "SCHOLION_OFFLINE": "1",
                    "SCHOLION_LANG": "en",
                    # An empty data root and NO profile path: exactly what a person
                    # has after `pip install` and nothing else.
                    "SCHOLION_REPO_DIR": str(self.dir),
                    "SCHOLION_GENOME_VCF": str(self.dir / "no-such-file.vcf.gz"),
                    "SCHOLION_GENOME_DIR": str(self.dir / "no-genome")}
        self.env.pop("SCHOLION_PROFILE_DIR", None)

    def _run(self, argv):
        return subprocess.run([sys.executable, "-m", "scholion", *argv],
                              cwd=support.ROOT, env=self.env,
                              capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)

    def test_the_readme_prints_the_same_first_screen_this_test_runs(self):
        """Otherwise the two drift and each of them looks right on its own."""
        if not README.exists():
            self.skipTest("README.md is not part of this build")
        text = README.read_text(encoding="utf-8")
        i = text.index("## Sixty seconds")
        block = text[i:text.index("## Why", i)]
        for argv in self.FIRST_SCREEN:
            with self.subTest(command=" ".join(argv)):
                self.assertIn("scholion " + " ".join(argv), block,
                              "the first screen this test runs is not the one the README shows")

    def test_the_four_lines_work_one_after_another_from_nothing(self):
        for argv in self.FIRST_SCREEN:
            cmd = " ".join(argv)
            with self.subTest(command=cmd):
                p = self._run(argv)
                self.assertEqual(p.returncode, 0,
                                 f"`scholion {cmd}` fails:\n{p.stderr[-600:]}")
                self.assertTrue(p.stdout.strip(), f"`scholion {cmd}` printed nothing")

    def test_the_screen_shows_the_demo_rather_than_an_empty_profile(self):
        """The assertion the old one was missing.

        «profile is empty» is a correct, well-behaved, zero-exit answer. It is
        also the answer that made the first screen useless, and no check that
        looks at the exit code can tell the two apart.
        """
        for argv in self.FIRST_SCREEN:
            self._run(argv)
        out = self._run(("overview",)).stdout
        self.assertNotIn("profile is empty", out,
                         "the first screen ends on an empty profile — the demo was written "
                         "somewhere the rest of the commands do not read from")
        m = self.EVIDENCE["overview"].search(out)
        self.assertIsNotNone(m, f"`overview` does not report a marker count at all:\n{out[:400]}")
        self.assertGreater(int(m.group(1)), 0, "the demo profile came out with no markers")

    def test_the_separate_demo_directory_says_how_to_look_at_it(self):
        """`scholion demo` is not the defect and is not being removed.

        Building the profile away from a real one is the right default — a demo
        that overwrites somebody's medical history would be far worse than an
        awkward second step. What it owes the reader is the command, and it
        prints it.
        """
        p = self._run(("demo",))
        self.assertEqual(p.returncode, 0, p.stderr[-400:])
        self.assertIn("SCHOLION_PROFILE_DIR", p.stdout,
                      "`demo` writes to a directory of its own and does not say how to read it")


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
        """Rewritten 19.08.2026, because the answer changed.

        It used to require the word «convert»: an array was not read, and a
        README that said so without naming the conversion route left a reader to
        discover in `genome/README.md` that the first screen had been wrong. In
        0.4.0 the array IS read, so the test now requires the command that reads
        it. The shape of the check is the same — the page must name a road that
        exists — only the road has moved.
        """
        claim = self._array_claim()
        self.assertTrue("scholion array" in claim or "read directly" in claim,
                        "an array is read now, and the page that mentions arrays has to say "
                        "how — a capability nobody can find is indistinguishable from one "
                        "that is not there")

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
        self.assertTrue("never interrogated" in claim or "unread" in claim
                        or "not on this chip" in claim
                        or "not equal reference" in claim,
                        "the array route is offered without the caveat that makes it safe to "
                        "take: on a chip the absence of a variant is not the reference — the "
                        "position was never looked at")


if __name__ == "__main__":
    unittest.main()


class TestTheDocumentsTheOutputNamesCanBeOpened(unittest.TestCase):
    """Advice to open a file the reader cannot open is worse than no advice.

    A `pip install` gets `src/scholion` and nothing else — that is what the wheel
    declares. Meanwhile `limits` sends the reader to PREPARING-THE-GENOME, the
    skill to README, the data layer to DATA-LAYOUT. Reported from a clean-machine
    run: the advice arrives, the file is not there, and with the repository still
    private there is no second place to look. To the person it reads as a broken
    installation rather than as a closed door.

    So the documents travel inside the package and `scholion doc <name>` prints
    one — the same shape as `scholion skill`, which has carried the instruction
    inside the package from the beginning for the same reason.
    """

    #: Documents the product's own output names. Checked by what the code says,
    #: not by a list somebody remembered to update.
    def _referenced(self):
        names = set()
        src = support.ROOT / "src" / "scholion"
        for f in list(src.glob("*.py")) + list((src / "i18n").glob("*.py")):
            for m in re.finditer(r"\b([A-Z][A-Z0-9-]{3,})\.md\b", f.read_text(encoding="utf-8")):
                names.add(m.group(1).lower())
        return names

    def test_every_document_the_output_names_is_carried_or_is_the_skill(self):
        from scholion import docs as _docs
        carried = {k for k, _ in _docs.available()}
        # The skill files have their own command and their own place inside the
        # package: `scholion skill` prints the entry, `--full` the instruction,
        # `--rules` the canon. Carrying them through `doc` as well would give the
        # same text two names, which is the thing the rename was for.
        own = {"skill", "instruction", "assistant-rules"}
        missing = sorted(n for n in self._referenced() if n not in carried and n not in own)
        self.assertEqual(
            missing, [],
            "the output names documents a pip user has no way to open: " + ", ".join(missing)
            + " — add them to src/tools/sync_docs.py, or stop naming them")

    def test_the_check_reaches_something(self):
        """A regex that matched nothing would pass for ever in silence."""
        self.assertTrue(self._referenced(), "no document is named anywhere in the output code")

    def test_the_copies_equal_their_sources(self):
        """A copy is a synchronisation problem, and this is where it surfaces."""
        tool = support.ROOT / "src" / "tools" / "sync_docs.py"
        if not tool.exists():
            self.skipTest("the synchroniser is not part of this build")
        p = subprocess.run([sys.executable, str(tool)], cwd=support.ROOT,
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_the_command_prints_a_document_and_refuses_an_unknown_one(self):
        env = {**os.environ, "PYTHONPATH": str(support.ROOT / "src"),
               "SCHOLION_OFFLINE": "1", "SCHOLION_LANG": "en"}
        ok = subprocess.run([sys.executable, "-m", "scholion", "doc", "data-layout"],
                            cwd=support.ROOT, env=env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(ok.returncode, 0, ok.stderr[-300:])
        self.assertGreater(len(ok.stdout), 1000, "the document came out empty or truncated")

        bad = subprocess.run([sys.executable, "-m", "scholion", "doc", "no-such-thing"],
                             cwd=support.ROOT, env=env, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual(bad.returncode, 1, "an unknown name is answered as if it existed")
        self.assertIn("data-layout", bad.stderr, "the refusal does not say what there is")
