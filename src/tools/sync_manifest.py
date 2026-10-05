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
#: The plugin folder carries two manifests of one package — the Agent Plugins
#: format and the one Claude's catalogue reads. Each has a `version`, and 0.6.0
#: is the first release with two to forget. Only the version is written; the
#: description is prose and stays a person's.
PLUGIN_MANIFESTS = (ROOT / "agent-plugin" / "plugin.json",
                    ROOT / "agent-plugin" / ".claude-plugin" / "plugin.json")


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


def render_plugin(text: str, version: str) -> str:
    """The version line of a plugin manifest, rewritten in place.

    A substitution rather than load-and-dump, so the key order and the
    indentation a reviewer sees in a diff are the ones a person wrote."""
    return re.sub(r'^(\s*"version"\s*:\s*)"[^"]*"', lambda m: f'{m.group(1)}"{version}"',
                  text, count=1, flags=re.M)


def sync_plugins(version: str, write: bool) -> int:
    stale = 0
    for path in PLUGIN_MANIFESTS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        fresh = render_plugin(text, version)
        if fresh == text:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if write:
            path.write_text(fresh, encoding="utf-8")
            print(f"✓ {rel} written from the build: v{version}")
        else:
            print(f"✗ {rel} does not carry v{version}")
            stale += 1
    return stale


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    stale = sync_plugins((ROOT / "VERSION").read_text(encoding="utf-8").strip(),
                         "--write" in argv)
    if stale:
        print("   python3 src/tools/sync_manifest.py --write")
        return 1
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
