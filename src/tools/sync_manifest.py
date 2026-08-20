#!/usr/bin/env python3
"""Write the host manifest from the build, instead of checking a typed one.

    python3 src/tools/sync_manifest.py            # report
    python3 src/tools/sync_manifest.py --write    # bring it up to date

The Ouroboros Hub skill is a file a HOST reads in order to decide what this can
do — and it is the only description of this product that is not derived from it.
It said `version: 0.3.2` against a 0.4 build and «23 tools» against 28, and named
no Model Context Protocol server because there was none when it was written. A
host reading it saw a Scholion that no longer existed, and an assistant working
from that description had no way to reach a surface that was sitting there.

A test that CHECKS a hand-written number is the weaker half of the fix: it tells
you the number is wrong, after you have already written it wrong, and it makes
every version bump a fourth thing to remember. The stronger half is here — the
same shape as `sync_docs.py` for documents and `sync_rules.py` for the rules:
the fields that can be derived are written by the build, and the prose stays a
person's to write.

Two fields, and only two, because they are the ones that go stale in silence:
the version and the tool count. Everything else in that file is a judgement
about what to say, and a generator has no business writing it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "ouroboros_plugin" / "hub" / "scholion" / "SKILL.md"


def _tool_count() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from scholion.ouroboros_tools import get_tools
    return len(get_tools())


def render(text: str, version: str, tools: int) -> str:
    out = re.sub(r"^version: .*$", f"version: {version}", text, count=1, flags=re.M)
    # «N tools» wherever it is claimed — in the front-matter description a host
    # shows, and in the body a model reads. One number, one source.
    out = re.sub(r"\b\d+ tools\b", f"{tools} tools", out)
    return out


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not MANIFEST.exists():
        print("· no Hub manifest in this build — nothing to do")
        return 0
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    tools = _tool_count()
    text = MANIFEST.read_text(encoding="utf-8")
    fresh = render(text, version, tools)
    if fresh == text:
        print(f"✓ the Hub manifest matches the build (v{version}, {tools} tools)")
        return 0
    if "--write" in argv:
        MANIFEST.write_text(fresh, encoding="utf-8")
        print(f"✓ Hub manifest written from the build: v{version}, {tools} tools")
        return 0
    print(f"✗ the Hub manifest does not match the build (v{version}, {tools} tools)")
    print("   python3 src/tools/sync_manifest.py --write")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
