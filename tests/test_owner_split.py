"""The personal part does not travel into the package, the shared part does.

The split "shared part in English, personal part in Russian" is held together by
the `<!-- OWNER:BEGIN -->` / `<!-- OWNER:END -->` markers — the same markup the
canon of the assistant rules uses. One markup per project: introduce a second one
and in a month nobody will remember which of them is the real one.

Both sides of the agreement are checked, not one. A test that watches only for
the leak would miss the opposite failure: too much was cut out, and the recipient
was left without the project's rules — with nobody to notice it, because the
owner's own file is intact.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import support

BEGIN, END = "<!-- OWNER:BEGIN -->", "<!-- OWNER:END -->"
CYRILLIC = re.compile(r"[Ѐ-ӿ]")

# Files with a split: path in the repository → what its copy in the package is called.
SPLIT_FILES = {
    "CLAUDE.md": "CLAUDE.md",
    # The canon of the rules: the personal block itself declares that it does not
    # travel into the package — the check makes sure the delivery mechanism
    # enforces that rule.
    "ASSISTANT-RULES.md": "src/scholion/skill/ASSISTANT-RULES.md",
}


class TestSplitByMarkers(unittest.TestCase):

    def setUp(self):
        self.in_repository = (support.ROOT / "share" / "skill" / "INSTRUCTION.md").exists()
        if not self.in_repository:
            self.skipTest("a built package: the source is not next to it")

    def test_the_markers_are_paired(self):
        """A marker without its pair means the file was edited and left broken.

        Cutting along half of the markup is more dangerous than not cutting at
        all: you can carry outward exactly the block you were hiding.
        """
        for name in SPLIT_FILES:
            text = (support.ROOT / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertEqual(text.count(BEGIN), text.count(END),
                                 f"{name}: the OWNER markers do not come in pairs")
                if BEGIN in text:
                    self.assertLess(text.index(BEGIN), text.index(END),
                                    f"{name}: END comes before BEGIN")

    # Files whose shared part has not been translated yet. The list SHRINKS and
    # never grows: an empty list means the shop window is entirely in English.
    NOT_YET_TRANSLATED: set = set()

    def test_the_shared_part_has_no_cyrillic(self):
        """Everything before the marker is public text, and it is obliged to be English."""
        for name in set(SPLIT_FILES) - self.NOT_YET_TRANSLATED:
            text = (support.ROOT / name).read_text(encoding="utf-8")
            shared = text.split(BEGIN)[0]
            lines = [n for n, ln in enumerate(shared.splitlines(), 1) if CYRILLIC.search(ln)]
            with self.subTest(file=name):
                self.assertEqual(lines, [], f"{name}: Russian in the shared part, lines {lines[:10]}")

    def test_the_personal_part_is_not_empty(self):
        """An empty personal block means the split has degenerated.

        Then the file is simply public, and the markers mislead: the next editor
        will decide that the personal part "went missing somewhere" and will put
        it higher up.
        """
        for name in SPLIT_FILES:
            text = (support.ROOT / name).read_text(encoding="utf-8")
            if BEGIN not in text:
                continue
            block = text.split(BEGIN)[1].split(END)[0]
            with self.subTest(file=name):
                self.assertTrue(block.strip(), f"{name}: the personal block is empty")


class TestCopyInThePackage(unittest.TestCase):
    """The check goes over the built package, if it is next door.

    The package is the only place where the result is visible: in the repository
    both blocks are in place by definition.
    """

    def setUp(self):
        # The build root IS the delivered project now: there is no container
        # level above it any more.
        roots = [support.ROOT.parent / "Scholion-SHARE"]
        self.package = next((p for p in roots if p.is_dir()), None)
        if self.package is None:
            self.skipTest("there is no built package next door")

    def test_the_personal_block_is_absent(self):
        for name, in_package in SPLIT_FILES.items():
            p = self.package / in_package
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertNotIn(BEGIN, text, f"{in_package}: the marker travelled into the package")
                self.assertNotIn(END, text)
                if name not in TestSplitByMarkers.NOT_YET_TRANSLATED:
                    self.assertEqual(
                        [n for n, ln in enumerate(text.splitlines(), 1) if CYRILLIC.search(ln)],
                        [], f"{in_package}: Russian was left in the package")

    def test_the_shared_part_arrived(self):
        """Too much was cut out — the recipient was left without the project's rules."""
        for name, in_package in SPLIT_FILES.items():
            p = self.package / in_package
            if not p.exists():
                continue
            with self.subTest(file=name):
                self.assertGreater(len(p.read_text(encoding="utf-8")), 1000,
                                   f"{in_package}: too short — more was cut out than should have been")


if __name__ == "__main__":
    unittest.main()
