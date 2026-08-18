#!/usr/bin/env python3
"""Carrying the assistant rules from ASSISTANT-RULES.md into two skill editions.

The rules live in one file and the skills receive a copy mechanically — which is
why the edition inside a skill cannot fall behind the canon unnoticed.

**There are two editions, and they DIFFER in composition.** The personal one
(`src/skill/INSTRUCTION.owner.md`) gets "Core" + "Owner's personal refinements"; the shared one
(`share/skill/INSTRUCTION.md`), which travels in the depersonalised package, gets only
"Core".

Why the split. A rule and a special case of it are different things. An "orange
flag on the report" is the flag of ONE laboratory; "LDLR coverage 88.4 %" is ONE
genome. Copied into the shared edition, such refinements pass off local practice
as universal: another user with a different laboratory and a different instrument
receives a rule that does not apply to their data — and cannot tell, because the
source of the refinement is not named in the text.

    python3 src/tools/sync_rules.py            # check (the default)
    python3 src/tools/sync_rules.py --write    # carry over

Exit 0 — in sync, 1 — a divergence or broken markers.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "ASSISTANT-RULES.md"
# The third address is the edition INSIDE the package. The sdist carries
# `src/scholion/skill/`, while `src/skill/` and `share/` do not travel at all:
# without this line the sync check inside the built artefact failed with "not a
# single skill file", although the file is there. Exactly the case for whose sake
# the run is moved onto the artefact.
# `src/scholion/skill/INSTRUCTION.md` is deliberately NOT in this list, although that
# file also holds the rules block. It is not an edition of its own but a byte-for-
# byte copy of the shared one (see MIRROR below): a copy is by definition in sync
# with its original, and a second check of the same thing adds no guarantee — only
# two messages about one file and a second way to "fix" it that diverges from the
# first.
#
# Exception: in a BUILT package there are no sources for the mirror, and there this
# copy remains the only skill file — so the list of targets below is extended with
# it dynamically.
TARGETS = tuple(t for t in (
    ROOT / "src" / "skill" / "INSTRUCTION.owner.md",   # source repo: the owner's edition
    ROOT / "src" / "skill" / "INSTRUCTION.md",         # built package: the shared edition lands here
    ROOT / "share" / "skill" / "INSTRUCTION.md",
    ROOT / "src" / "scholion" / "skill" / "INSTRUCTION.md",
) if not ((ROOT / "share" / "skill" / "INSTRUCTION.md").exists()
          and t == ROOT / "src" / "scholion" / "skill" / "INSTRUCTION.md"))

SRC_BEGIN, SRC_END = "<!-- CORE:BEGIN -->", "<!-- CORE:END -->"
OWNER_BEGIN, OWNER_END = "<!-- OWNER:BEGIN -->", "<!-- OWNER:END -->"
DST_BEGIN, DST_END = "<!-- ASSISTANT-RULES:BEGIN -->", "<!-- ASSISTANT-RULES:END -->"

# Which edition gets what. The key is the target path relative to the root.
#
# The subtlety this used to break on: in a BUILT PACKAGE the path
# `src/skill/INSTRUCTION.md` holds the SHARED edition. The name now says which is
# which — `.owner.` never leaves the source repository — but the check still has to
# check would demand the personal block from the shared edition and fail for the
# package recipient. The sign of the source repository is `share/skill/INSTRUCTION.md`
# lying next to it.
OWNER_EDITION = "src/skill/INSTRUCTION.owner.md"
IN_SOURCE_REPO = (ROOT / "share" / "skill" / "INSTRUCTION.md").exists()

# Copies inside the package. The reason is separate from block synchronisation:
# only what lies INSIDE `src/scholion` gets into the wheel (`pip install scholion`).
# If the instruction for an external model stays outside, then after installation a
# person receives a command line without the instruction it exists for, even though
# the package description promises them the skill. Hence the shared edition and the
# canon of rules are mirrored into the package byte for byte; the source stays one.
MIRROR = (
    (ROOT / "share" / "skill" / "INSTRUCTION.md", ROOT / "src" / "scholion" / "skill" / "INSTRUCTION.md"),
    # The entry carries no rules block of its own — it is copied verbatim, not synchronised.
    (ROOT / "share" / "skill" / "SKILL.md", ROOT / "src" / "scholion" / "skill" / "SKILL.md"),
    # The owner keeps ~/.claude/skills/scholion pointed at src/skill/, and the
    # runtime looks for SKILL.md there — so the entry is mirrored into the
    # owner's directory as well. Nothing personal is in it.
    (ROOT / "share" / "skill" / "SKILL.md", ROOT / "src" / "skill" / "SKILL.md"),
    (SOURCE, ROOT / "src" / "scholion" / "skill" / "ASSISTANT-RULES.md"),
)
HEADER = (
    "_Copied from `ASSISTANT-RULES.md` by `src/tools/sync_rules.py`. "
    "Edit the canon, not this copy: a divergence fails `run_tests.sh`._"
)


def _between(text: str, begin: str, end: str, where: Path) -> str:
    i, j = text.find(begin), text.find(end)
    if i < 0 or j < 0 or j < i:
        raise SystemExit(f"✗ {where.name}: markers {begin} … {end} not found")
    return text[i + len(begin):j].strip("\n")


def core() -> str:
    if not SOURCE.exists():
        raise SystemExit(f"✗ no canonical rules file: {SOURCE}")
    return _between(SOURCE.read_text(encoding="utf-8"), SRC_BEGIN, SRC_END, SOURCE)


def owner() -> str:
    """Personal refinements. An empty string if there is no block — that is legitimate."""
    text = SOURCE.read_text(encoding="utf-8")
    if OWNER_BEGIN not in text:
        return ""
    return _between(text, OWNER_BEGIN, OWNER_END, SOURCE)


def block(rules: str, extra: str = "") -> str:
    body = rules if not extra else f"{rules}\n\n### Owner's personal refinements\n\n{extra}"
    return f"{DST_BEGIN}\n{HEADER}\n\n{body}\n{DST_END}"


def main(argv: list[str]) -> int:
    write = "--write" in argv
    rules, personal = core(), owner()
    if not rules.strip():
        raise SystemExit("✗ the \"Core\" block in ASSISTANT-RULES.md is empty")
    stale = []
    # A depersonalised package holds only one skill edition: `share/skill/INSTRUCTION.md`
    # arrives at the recipient as `src/skill/INSTRUCTION.owner.md`, and they have no source file.
    # A missing target is not an error; the absence of ALL targets is an error.
    present = [t for t in TARGETS if t.exists()]
    if not present:
        raise SystemExit(f"✗ not a single skill file: {', '.join(str(t) for t in TARGETS)}")
    for target in present:
        text = target.read_text(encoding="utf-8")
        current = _between(text, DST_BEGIN, DST_END, target)
        rel = str(target.relative_to(ROOT))
        is_owner = IN_SOURCE_REPO and rel == OWNER_EDITION
        wanted = block(rules, personal if is_owner else "")
        if current.strip("\n") == wanted[len(DST_BEGIN):-len(DST_END)].strip("\n"):
            print(f"✓ {target.relative_to(ROOT)} — in sync")
            continue
        if not write:
            stale.append(target)
            print(f"✗ {target.relative_to(ROOT)} — has fallen behind ASSISTANT-RULES.md")
            continue
        i = text.find(DST_BEGIN)
        j = text.find(DST_END) + len(DST_END)
        target.write_text(text[:i] + wanted + text[j:], encoding="utf-8")
        print(f"→ {target.relative_to(ROOT)} — updated")
    stale += _mirror(write)
    if stale:
        print("\nThe assistant rules have diverged from the canon. Fix it with:")
        print("    python3 src/tools/sync_rules.py --write")
        print("Edit ASSISTANT-RULES.md, not the copy inside the skill.")
        return 1
    return 0


def _public_bytes(src: Path) -> bytes:
    """The file's content WITHOUT the personal block — what may travel in the package.

    Mirroring of the canon was introduced so that the rules would reach the wheel,
    and it copied the file whole. Meanwhile the canon itself states in the `OWNER`
    block, in plain words: "it is not copied into the depersonalised package". So it
    turned out that the delivery mechanism broke the rule written in the file being
    delivered — and an owner's laboratory and instrument specifics travelled to
    outsiders.

    The audit did not catch this and could not: there is no name and no sample
    identifier there, only clinical particulars. A content check cannot be replaced
    by a markup check, nor the other way round.
    """
    text = src.read_text(encoding="utf-8")
    i, j = text.find(OWNER_BEGIN), text.find(OWNER_END)
    if i >= 0 and j > i:
        text = (text[:i].rstrip() + "\n" + text[j + len(OWNER_END):].lstrip("\n"))
    elif i >= 0 or j >= 0:
        raise SystemExit(f"✗ {src.name}: an OWNER marker without its pair — cutting on "
                         f"half the markup is more dangerous than not cutting")
    return text.encode("utf-8")


def _mirror(write: bool) -> list:
    """Mirroring the shared edition and the canon into the package.

    Only in the source repository: the recipient of a depersonalised package has no
    sources for the mirror, and they cannot be demanded of them.
    """
    if not IN_SOURCE_REPO:
        return []
    stale = []
    for src, dst in MIRROR:
        if not src.exists():
            continue
        want = _public_bytes(src)
        if dst.exists() and dst.read_bytes() == want:
            print(f"✓ {dst.relative_to(ROOT)} — the copy in the package matches")
            continue
        if not write:
            stale.append(dst)
            print(f"✗ {dst.relative_to(ROOT)} — the copy in the package has fallen behind {src.name}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(want)
        print(f"→ {dst.relative_to(ROOT)} — the copy in the package updated")
    return stale


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
