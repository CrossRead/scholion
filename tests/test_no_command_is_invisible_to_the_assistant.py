# -*- coding: utf-8 -*-
"""A command an assistant never hears about is a command the person does not have.

The skill ships in two layers on purpose: a thin entry that a runtime loads by
itself, and the full instruction it points at. That split is fine — what is not
fine is a subcommand that appears in NEITHER, because then the only way to reach
it is to already know it exists.

This was not hypothetical. `focus-log` — the one command behind "note that
yesterday had wine" — existed, worked, and was named in no entry the assistant
reads. The owner asked "will the assistant understand if I ask it to log that?"
and the honest answer was no, not unless it had read `--help` on its own.

The guard walks the argparse tree rather than a hand-written list, so a command
added tomorrow is covered the day it is added.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Wherever this build keeps the entry. Three editions of one file exist and
# `sync_rules.py` keeps them identical; which of them is on disk depends on
# whether this is the source tree, the public package or an installed wheel.
# `src/skill/SKILL.md` is the source tree's copy and it is NOT in the package —
# only `src/skill/INSTRUCTION.md` lands at that path there — so asking for it by
# name passed here and failed for the recipient with "the thin entry was not
# readable". That is the class this project has paid for three times: a test
# that asks the artefact for something only the repository has.
import sys as _sys
_sys.path.insert(0, str(ROOT / "src"))
from scholion import contract as _contract  # noqa: E402

ENTRY = _contract.skill_entry_path() or (ROOT / "src" / "skill" / "SKILL.md")

# Both editions, checked separately. The owner's edition and the generalised one
# that travels in the package are different files, and a command named only in
# the private one is invisible to everybody else — which is the same defect one
# level down. Only the ones this build actually carries: the owner's edition
# never ships, and the shared source lives beside it only in the source tree.
EDITIONS = tuple(p for p in (ROOT / "src" / "skill" / "INSTRUCTION.owner.md",
                             ROOT / "share" / "skill" / "INSTRUCTION.md",
                             ROOT / "src" / "scholion" / "skill" / "INSTRUCTION.md")
                 if p.exists())

# Named here rather than silently skipped: these are not part of what an
# assistant does for a person, and each has a reason a reader can check.
NOT_FOR_THE_ASSISTANT = {
    "mcp",        # the tool-server door itself; the entry describes it in prose
    "serve",      # starts the local web interface, a person's action
    "demo",       # builds a fictional profile for a screenshot
    "init",       # first-run layout, described in "make it run"
    "set-folder", # points at a data folder; the person picks the folder
    "skill",      # prints this very instruction
    "doc",        # prints the documents the instruction already names
}


def subcommands() -> set[str]:
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from scholion.cli import build_parser
    import argparse

    out: set[str] = set()
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            out |= set(action.choices)
    return out


class NoCommandIsInvisible(unittest.TestCase):
    def test_the_walk_found_the_commands(self):
        # The same check every guard in this project carries: a walk that finds
        # nothing must fail loudly, or an empty parse passes as a clean tree.
        self.assertGreater(len(subcommands()), 30)

    def test_every_command_is_named_in_each_edition(self):
        entry = ENTRY.read_text(encoding="utf-8") if ENTRY.exists() else ""
        self.assertTrue(entry, "the thin entry was not readable")
        for edition in EDITIONS:
            self.assertTrue(edition.exists(), f"missing instruction edition: {edition}")
            text = entry + edition.read_text(encoding="utf-8")
            invisible = sorted(
                c for c in subcommands() - NOT_FOR_THE_ASSISTANT
                if not re.search(r"(?<![\w-])" + re.escape(c) + r"(?![\w-])", text)
            )
            self.assertEqual(
                invisible, [],
                f"{edition.name}: these commands exist and nothing the assistant reads "
                "names them: " + ", ".join(invisible))


if __name__ == "__main__":
    unittest.main()
