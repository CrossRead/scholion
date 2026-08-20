#!/usr/bin/env python3
"""A published version cannot be rewritten — so it must not be re-published changed.

    python3 src/tools/check_published.py --check     # before building
    python3 src/tools/check_published.py --record    # after a successful publish

The rule this enforces is not new; the silence around it is. A tag may legitimately
move — the ordinary reason is a correction to the release notes — and when it does,
the version is already in the registry and the upload is skipped rather than failed.
That is right for a correction to text OUTSIDE the package. It is exactly wrong for a
change INSIDE it: the upload is skipped just as quietly, the registry keeps the old
artefact, and the tag now points at code that nobody can install. Two facts, and
nothing compared them.

So this compares them. Three things decide the answer, and each is derived:

* **What counts as inside the package** — read out of `pyproject.toml`, from the same
  `packages` and `include` lists the build itself uses. A second list here would drift
  from that one, and the day it did, the check would be about a package that no longer
  exists.
* **Whether it changed** — a fingerprint over those files, recorded at the moment of a
  successful publish and compared on the next run.
* **Whether the version is already out** — asked of the registry, not remembered.

The three answers meet in one of four verdicts, and the fourth matters most: with no
record of what was published, the honest answer is «I cannot tell», not «probably
fine». That is what `--allow-unverified` is for, and why it has to be typed.

Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "published.json"
PYPI = "https://pypi.org/pypi/{name}/{version}/json"
_SKIP = ("__pycache__", ".pyc", ".DS_Store")


def project_name() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^name\s*=\s*"([^"]+)"', text, re.M)
    return m.group(1) if m else "scholion"


def packaged_paths() -> list:
    """What travels, read out of the build configuration rather than listed again."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    out: set = set()
    m = re.search(r"^packages\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if m:
        out |= {p.strip().strip('"').strip("/") for p in m.group(1).split(",") if p.strip()}
    m = re.search(r"^include\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if m:
        for line in m.group(1).splitlines():
            line = line.split("#", 1)[0].strip().rstrip(",").strip()
            if line.startswith('"') and line.endswith('"'):
                out.add(line.strip('"').strip("/"))
    return sorted(p for p in out if p)


def fingerprint() -> str:
    """One hash over every file that travels, path and content both."""
    h = hashlib.sha256()
    for rel in packaged_paths():
        base = ROOT / rel
        files = sorted(base.rglob("*")) if base.is_dir() else [base]
        for f in files:
            if not f.is_file() or any(s in str(f) for s in _SKIP):
                continue
            h.update(str(f.relative_to(ROOT)).encode())
            h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def _record() -> dict:
    try:
        return json.loads(RECORD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def published(name: str, version: str):
    """True / False / None — and None is an answer, not a failure to get one."""
    try:
        with urllib.request.urlopen(PYPI.format(name=name, version=version), timeout=30):
            return True
    except urllib.error.HTTPError as e:
        return False if e.code == 404 else None
    except Exception:                                   # noqa: BLE001 — no network, DNS, proxy
        return None


def check(allow_unverified: bool = False) -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    name = project_name()
    now = fingerprint()
    out = published(name, version)

    if out is False:
        print(f"  ✓ {name} {version} is not in the registry yet — this is a first publication")
        return 0
    if out is None:
        print(f"  ⚠ could not ask PyPI whether {name} {version} exists.")
        if not allow_unverified:
            print("    Refusing rather than guessing: if the version is already out and the")
            print("    package has changed, the upload would be skipped in silence and the")
            print("    registry would keep the old artefact under this tag.")
            print("    Publish anyway with --allow-unverified once you have checked by hand.")
            return 1
        print("    --allow-unverified: continuing without the comparison.")
        return 0

    was = _record().get(version)
    if was is None:
        print(f"  ⚠ {name} {version} is already published, and there is no record of what")
        print("    went into it, so «has the package changed» cannot be answered here.")
        if not allow_unverified:
            print("    Bump VERSION, or pass --allow-unverified if you know the package is")
            print("    unchanged — a published version cannot be rewritten.")
            return 1
        print("    --allow-unverified: continuing.")
        return 0
    if was == now:
        print(f"  ✓ {name} {version} is published and the package is unchanged")
        print("    (the registry will skip the upload; only what travels outside the")
        print("    package is being re-published)")
        return 0

    print(f"  ✗ {name} {version} is already published AND the package has changed since.")
    print("    A published version cannot be rewritten: the upload would be skipped, the")
    print("    registry would keep the old artefact, and the tag would point at code")
    print("    nobody can install. Bump VERSION.")
    print(f"    what travels: {', '.join(packaged_paths())}")
    return 1


def record() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    data = _record()
    data[version] = fingerprint()
    RECORD.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"  ✓ recorded what went into {version}")
    return 0


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--allow-unverified", action="store_true")
    a = ap.parse_args(argv)
    if a.record:
        return record()
    return check(a.allow_unverified)


if __name__ == "__main__":
    raise SystemExit(main())
