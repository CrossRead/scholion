#!/usr/bin/env python3
"""Is our vendored copy still the upstream's — and has upstream moved?

    python3 src/tools/check_vendor.py            # compare, report, change nothing
    python3 src/tools/check_vendor.py --refresh  # re-fetch at the pinned commit

Vendoring is only defensible if the copy stays comparable. A file copied once and
then quietly edited is worse than a dependency: it looks like somebody else's
reviewed code while being nobody's. So the pinned commit and the sha256 of every
file as fetched live in UPSTREAM.md, and this tool answers three questions in one
run:

  · does our copy still match what we pinned (i.e. has anyone edited it here
    beyond the changes we declared)?
  · has upstream moved since we pinned it?
  · if it has, which of our declared changes would have to be re-applied?

It never writes without `--refresh`, and even then it keeps our headers: the
attribution and the change log are ours, the code below them is theirs.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
VENDOR = ROOT / "src" / "scholion" / "vendor" / "genomi"
UPSTREAM_MD = VENDOR / "UPSTREAM.md"
RAW = "https://raw.githubusercontent.com/exon-research/genomi/{ref}/{path}"

#: our file → (upstream path, the sha256 recorded in UPSTREAM.md)
FILES = {
    "detection.py": "src/genomi/active_genome_index/source_intake/detection.py",
    "text_io.py": "src/genomi/active_genome_index/source_intake/text_io.py",
}
TESTS = {
    "tests/test_genomi_source_detection.py": "tests/test_source_detection.py",
}

_HEADER_END = "# ---------------------------------------------------------------------------\n"


def pinned():
    """The commit and the checksums this repository claims to carry."""
    text = UPSTREAM_MD.read_text(encoding="utf-8")
    commit = re.search(r"\*\*Commit:\*\*\s*`([0-9a-f]+)`", text)
    sums = dict(re.findall(r"\|\s*`?([\w./]+\.py)`?\s*\|[^|]*\|[^|]*\|\s*`([0-9a-f]{64})`", text))
    return (commit.group(1) if commit else None), sums


def fetch(ref: str, path: str) -> bytes | None:
    try:
        with urllib.request.urlopen(RAW.format(ref=ref, path=path), timeout=20) as r:
            return r.read()
    except Exception:
        return None


def body_of(p: pathlib.Path) -> bytes:
    """Our file with OUR header removed — what should equal upstream byte for byte."""
    text = p.read_text(encoding="utf-8")
    if text.startswith("# ---"):
        end = text.find(_HEADER_END, len(_HEADER_END))
        if end != -1:
            text = text[end + len(_HEADER_END):]
    return text.encode("utf-8")


def main(argv):
    refresh = "--refresh" in argv
    commit, sums = pinned()
    if not commit:
        print("✗ UPSTREAM.md does not name a commit — nothing to compare against")
        return 1
    print(f"pinned at {commit}\n")
    drift, moved, unreachable = [], [], []
    for ours, theirs in FILES.items():
        p = VENDOR / ours
        local = hashlib.sha256(body_of(p)).hexdigest()
        want = sums.get(ours)
        # 1. did WE edit it beyond the declared changes?
        if want and local != want:
            n = body_of(p).decode("utf-8").count("SCHOLION CHANGE")
            drift.append(f"{ours}: differs from the pinned original "
                         f"({n} declared change{'s' if n != 1 else ''} in the file)")
        # 2. has upstream moved?
        head = fetch("master", theirs)
        if head is None:
            unreachable.append(ours)
            print(f"  {ours}: upstream unreachable — offline, or the path moved")
            continue
        if want and hashlib.sha256(head).hexdigest() != want:
            moved.append(ours)
        if refresh:
            at_pin = fetch(commit, theirs)
            if at_pin:
                header = p.read_text(encoding="utf-8").split(_HEADER_END)[0] + _HEADER_END
                p.write_text(header + at_pin.decode("utf-8"), encoding="utf-8")
                print(f"  {ours}: re-fetched at {commit}, header kept — RE-APPLY the "
                      f"declared changes, they are gone now")
    print()
    if drift:
        print("Our copy differs from the pinned original — expected where we declared a change,\n"
              "and a finding where we did not:")
        for d in drift:
            print("  · " + d)
        print()
    if moved:
        print("Upstream has MOVED since we pinned it:")
        for m in moved:
            print(f"  · {m}")
        print("\nUpdating is a decision, not a chore: their change may be a fix worth taking\n"
              "or a default worth refusing. See «Changes from upstream» in UPSTREAM.md.")
        return 0
    if unreachable:
        # A check that could not run is not a check that passed. Reporting «has
        # not moved» here would be a clean bill of health produced by the absence
        # of a network — the exact failure this project keeps finding elsewhere.
        print("⚠ upstream could not be reached for "
              f"{', '.join(unreachable)} — this run says NOTHING about whether it moved.")
        print("  (The device bridge has no network; run this from a terminal that has one.)")
        return 0
    print("✅ upstream has not moved from the pinned commit")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
