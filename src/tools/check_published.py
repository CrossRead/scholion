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


CATALOGUE = ("src", "scholion", "knowledge", "loci.json")
#: The lead a release entry has to carry when the catalogue grew. It is matched as
#: text rather than parsed: the journal is prose for a reader, and what matters here
#: is that the command a person must run is named in the entry at all.
REGENOTYPE = "genotype-sites"


def version_tuple(v) -> tuple:
    out = []
    for part in str(v).split("."):
        digits = "".join(c for c in part if c.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def catalogue():
    """The size of the locus catalogue that travels in this build, and its date.

    A person's `loci_sites.vcf.gz` answers for the catalogue it was made from. The
    catalogue grew three times in five weeks — 61 → 113 → 141 → 250 — and every time
    the positions added since read as «not read» on a profile that was never
    re-genotyped, and every time it was noticed on the owner's own data rather than
    at the release (task 202). Recording the size at publication is what lets a
    release know it grew.
    """
    try:
        data = json.loads(ROOT.joinpath(*CATALOGUE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A tree with no catalogue is not a tree with an empty one. The anonymised
        # package and the probe trees the tests build are the honest cases: there
        # is nothing to record and nothing to compare, and saying «0 positions»
        # would be a measurement nobody made.
        return None
    meta = data.get("_meta") or {}
    stamp = str(meta.get("catalog_updated") or meta.get("updated") or "")[:10]
    return {"positions": len(data.get("loci") or {}), "updated": stamp or None}


def _entry(value) -> dict:
    """One record, whichever shape it was written in.

    Everything published before 0.5.5 recorded the fingerprint alone, as a string.
    Those entries are read, not rewritten: a record of what was published is not a
    place to invent a number nobody measured at the time.
    """
    if isinstance(value, str):
        return {"fingerprint": value, "catalogue": None}
    if isinstance(value, dict):
        return {"fingerprint": value.get("fingerprint"), "catalogue": value.get("catalogue")}
    return {"fingerprint": None, "catalogue": None}


def _last_recorded_catalogue(data: dict, before: str):
    """The newest version below this one that recorded a catalogue, and what it recorded."""
    best, found = None, None
    for version, value in data.items():
        cat = _entry(value).get("catalogue")
        if not cat or version_tuple(version) >= version_tuple(before):
            continue
        if best is None or version_tuple(version) > version_tuple(best):
            best, found = version, cat
    return best, found


def _entry_body(version: str) -> str:
    """The journal section of one version, as text."""
    try:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"^##\s+v?" + re.escape(version) + r"\b(.*?)(?=^##\s+v?\d|\Z)",
                  text, re.M | re.S)
    return m.group(1) if m else ""


def catalogue_check(version: str, data: dict) -> int:
    """Did the catalogue grow, and if so does this entry tell people to re-run the step?"""
    now = catalogue()
    if now is None:
        return 0
    was_version, was = _last_recorded_catalogue(data, version)
    if not was:
        print(f"  · the locus catalogue: {now['positions']} positions ({now['updated'] or '—'});")
        print("    no earlier version recorded one, so there is nothing to compare it with yet")
        return 0
    if int(was.get("positions") or 0) == int(now["positions"]):
        print(f"  ✓ the locus catalogue is the same size as in {was_version} "
              f"({now['positions']} positions)")
        return 0
    grew = int(now["positions"]) - int(was.get("positions") or 0)
    body = _entry_body(version)
    if REGENOTYPE in body:
        print(f"  ✓ the locus catalogue changed since {was_version} "
              f"({was.get('positions')} → {now['positions']}, {grew:+d}), and the entry for "
              f"{version} says to run `scholion {REGENOTYPE}`")
        return 0
    print(f"  ✗ the locus catalogue changed since {was_version}: "
          f"{was.get('positions')} → {now['positions']} ({grew:+d} positions).")
    print("    Everybody's `loci_sites.vcf.gz` was made for the smaller one, so every position")
    print("    added since will read as «not read» on their profile until they re-run the step —")
    print(f"    and the entry for {version} does not mention `scholion {REGENOTYPE}`.")
    print(f"    Add it under «What needs recomputing» in CHANGELOG.md, or say there why this")
    print("    growth needs nothing.")
    return 1


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
        return catalogue_check(version, _record())
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

    data = _record()
    was = _entry(data.get(version)).get("fingerprint") if version in data else None
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
        return catalogue_check(version, data)

    print(f"  ✗ {name} {version} is already published AND the package has changed since.")
    print("    A published version cannot be rewritten: the upload would be skipped, the")
    print("    registry would keep the old artefact, and the tag would point at code")
    print("    nobody can install. Bump VERSION.")
    print(f"    what travels: {', '.join(packaged_paths())}")
    return 1


def record() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    data = _record()
    cat = catalogue()
    if cat is not None and not cat.get("positions"):
        print("  ✗ the locus catalogue is there and reads as empty; nothing was recorded.")
        return 1
    data[version] = {"fingerprint": fingerprint(), "catalogue": cat}
    RECORD.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    said = (f" — and its locus catalogue ({cat['positions']} positions, "
            f"{cat['updated'] or 'no date'})") if cat else ""
    print(f"  ✓ recorded what went into {version}{said}")
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
