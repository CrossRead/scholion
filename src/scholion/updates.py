"""What an update asks of the data already on disk — read from the journal the package carries.

Every release note has a section «What needs recomputing», and for months nothing
read it: a person who upgraded learned what to re-run only by reading the whole
journal, and a doctor ran the product three days behind a release that closed
her own complaint (13.09.2026). The section is now written in a form a program
can read, and this module reads it.

**The grammar.** A section either starts with «Nothing», or holds one or more
action paragraphs whose first line is a bold lead of one of two shapes:

    **Run `scholion <command>` — <when it applies>.**
    **By hand — <when it applies>.**

followed by the explanation. A lead may name several commands, each in
backticks. The journal is parsed from the copy the package carries
(`scholion doc changelog`), so a pip install reads exactly what shipped and there
is no second file to drift from the first. `tests/test_every_release_says_what_to_recompute_in_a_form_a_program_reads.py`
holds the grammar; a section that breaks it fails the build.

**What the data was last used with.** `.last_version` beside the profile holds
the version the person last acknowledged. It is written by `scholion init`, by
`scholion version --seen` and by the «Understood» button — never silently by an
ordinary run, so an update note stays until a person has read it. It sits beside
the PROFILE, not in `work/`: the marker describes the data, and a test that pins
the profile pins the marker with it (a marker under the data root would have
been written into the source tree by the server test, silencing the note for
whoever runs from that tree).

**The registry.** `check_registry()` asks PyPI which version is current — one
request, only on an explicit command or click, refused by `SCHOLION_OFFLINE`. The
owner allowed this host on 13.09.2026 for exactly this purpose; nothing asks it
in the background or at start-up.

Standard library only.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

_HEAD = re.compile(r"^## v(\d+(?:\.\d+)*)\s+—\s+(\d{2}\.\d{2}\.\d{4})\s*$", re.M)
_LEAD = re.compile(r"^\*\*(?:Run (?P<cmds>.+?)|By hand) — (?P<cond>.+?)\.\*\*\s*$")
_LOOKS_LIKE_LEAD = re.compile(r"^\*\*(Run\b|By hand\b)")
_CMD = re.compile(r"`([^`]+)`")


def version_tuple(v: Any) -> Tuple[int, ...]:
    """`0.4.10` > `0.4.9`: numbers, never strings. A suffix (`+local`) is ignored."""
    parts = re.findall(r"\d+", str(v or "").split("+")[0])
    return tuple(int(x) for x in parts[:3]) or (0,)


def _section_body(block: str) -> Optional[str]:
    s = re.search(r"^### What needs recomputing\s*$", block, re.M)
    if not s:
        return None
    body = block[s.end():]
    stop = re.search(r"^### ", body, re.M)
    return (body[:stop.start()] if stop else body).strip()


def parse_section(body: str) -> Dict[str, Any]:
    """One section → {nothing, actions[], problems[]}."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    actions: List[Dict[str, Any]] = []
    problems: List[str] = []
    for j, para in enumerate(paras):
        first = para.split("\n", 1)[0].strip()
        lead = _LEAD.match(first)
        if not lead:
            if _LOOKS_LIKE_LEAD.match(first):
                problems.append(f"a lead that does not follow the grammar: {first[:80]}")
            continue
        rest = para.split("\n", 1)[1].strip() if "\n" in para else ""
        expl = [rest] if rest else []
        for q in paras[j + 1:]:
            q_first = q.split("\n", 1)[0].strip()
            if _LEAD.match(q_first) or q.startswith("Nothing"):
                break
            expl.append(q)
        manual = lead.group("cmds") is None
        commands = [] if manual else _CMD.findall(lead.group("cmds"))
        if not manual and not commands:
            problems.append(f"a Run lead names no command in backticks: {first[:80]}")
        for c in commands:
            if not (c.startswith("scholion ") or c == "scholion"
                    or c.startswith("python3 -m scholion")):
                problems.append(f"a Run lead names something that is not a scholion command: `{c}`")
        actions.append({"manual": manual, "commands": commands,
                        "condition": lead.group("cond").strip(),
                        "text": "\n\n".join(expl)})
    nothing = bool(paras) and paras[0].startswith("Nothing")
    if not actions and not nothing:
        problems.append("the section neither starts with «Nothing» nor holds an action lead")
    return {"nothing": nothing and not actions, "actions": actions, "problems": problems}


def parse_journal(text: str) -> List[Dict[str, Any]]:
    """Every `## vX.Y.Z — DD.MM.YYYY` entry, newest first as the journal is written."""
    heads = list(_HEAD.finditer(text))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[m.end():end]
        nxt = re.search(r"^## ", block, re.M)
        if nxt:
            block = block[:nxt.start()]
        body = _section_body(block)
        entry = {"version": m.group(1), "date": m.group(2), "has_section": body is not None}
        entry.update(parse_section(body) if body is not None
                     else {"nothing": True, "actions": [], "problems": []})
        out.append(entry)
    return out


def journal_text() -> str:
    """The journal as this build carries it — the package copy, never the repository."""
    from . import docs as _docs
    p = _docs.path_of("changelog")
    return p.read_text(encoding="utf-8") if p is not None else ""


def between(since: Any, until: Any, text: Optional[str] = None) -> List[Dict[str, Any]]:
    """Entries newer than `since` and not newer than `until` that ask for an action."""
    lo, hi = version_tuple(since), version_tuple(until)
    entries = parse_journal(journal_text() if text is None else text)
    return [e for e in entries
            if lo < version_tuple(e["version"]) <= hi and e["actions"]]


#: The one address the version check asks. A constant, never composed from input.
REGISTRY = "https://pypi.org/pypi/scholion/json"
MARKER = ".last_version"


def installed() -> str:
    import scholion
    return getattr(scholion, "__version__", "") or ""


def _marker_path():
    from . import core
    return core.profile_dir() / MARKER


def last_used() -> Optional[str]:
    try:
        v = _marker_path().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return v or None


def mark_seen(version: Optional[str] = None) -> Dict[str, Any]:
    """Record that the data is now used with this build. Beside the profile, atomically."""
    import os
    v = version or installed()
    path = _marker_path()
    if not path.parent.is_dir():
        return {"ok": False, "error": "no_profile", "recorded": None}
    tmp = path.with_name(f"{MARKER}.tmp-{os.getpid()}")
    tmp.write_text(v + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return {"ok": True, "recorded": v}


def status(since: Optional[str] = None) -> Dict[str, Any]:
    """The build, its age, the version the data was last used with, and what lies between."""
    from .engine.sources import build_freshness
    try:
        build = build_freshness()
    except Exception as exc:                                         # noqa: BLE001
        build = {"status": "unknown", "reason": type(exc).__name__}
    now = installed()
    used = last_used()
    base = since or used
    changed = bool(used) and version_tuple(used) != version_tuple(now)
    pending = between(base, now) if base else []
    try:
        stale = written_before()
    except Exception as exc:                                         # noqa: BLE001
        stale = {"files": [], "unstamped": [], "reason": type(exc).__name__}
    return {"installed": now, "build": build, "last_used": used, "since": base,
            "explicit_since": bool(since), "changed": changed,
            "pending": pending, "written_before": stale,
            "why": None if base else "not_recorded"}


def check_registry(fetch=None) -> Dict[str, Any]:
    """Which version PyPI calls current — asked only when a person asks."""
    from . import net
    now = installed()
    if fetch is None:
        if net.offline():
            return {"status": "offline", "installed": now, "latest": None}
        fetch = net.get_json
    data = fetch(REGISTRY)
    latest = ((data or {}).get("info") or {}).get("version") if isinstance(data, dict) else None
    if not latest:
        return {"status": "unreachable", "installed": now, "latest": None}
    newer = version_tuple(latest) > version_tuple(now)
    return {"status": "newer" if newer else "current", "installed": now, "latest": latest,
            "command": "pip install --upgrade scholion" if newer else None}


#: The command that writes each profile file a release may ask to rebuild. A lead
#: naming one of these commands is a request to rebuild that file.
COMMAND_FILES = {
    "scholion ingest-labs": ("labs.json",),
    "scholion import-labs": ("labs.json",),
    "scholion ingest-studies": ("studies.json",),
    "scholion ingest-garmin": ("wearable_trends.json",),
    "scholion ingest-wearable": ("wearable_trends.json",),
    "python3 -m scholion.prs": ("prs_results.json",),
}


def written_before(text: Optional[str] = None) -> Dict[str, Any]:
    """Profile files written by a build older than a release that asks to rebuild them."""
    import json as _json
    from . import core
    now = installed()
    entries = parse_journal(journal_text() if text is None else text)
    out, unstamped = [], []
    for name in sorted({f for files in COMMAND_FILES.values() for f in files}):
        p = core.profile_dir() / name
        if not p.is_file():
            continue
        try:
            meta = (_json.loads(p.read_text(encoding="utf-8")) or {}).get("_meta") or {}
        except (OSError, ValueError, AttributeError):
            continue
        engine = meta.get("engine")
        if not engine:
            unstamped.append(name)
            continue
        asks = []
        for e in entries:
            if not version_tuple(engine) < version_tuple(e["version"]) <= version_tuple(now):
                continue
            for a in e["actions"]:
                cmds = [c for c in a["commands"]
                        if any(c.startswith(k) and name in fs for k, fs in COMMAND_FILES.items())]
                if cmds:
                    asks.append({"version": e["version"], "commands": cmds,
                                 "condition": a["condition"]})
        if asks:
            out.append({"file": name, "engine": engine, "asks": asks})
    return {"files": out, "unstamped": unstamped}


#: Where hosts that read a skills folder keep a copy of the entry, under the home
#: directory. A copy made by hand does not update itself; these are the places
#: `selfcheck` looks, read-only.
SKILL_DIRS = (".agents/skills/scholion", ".claude/skills/scholion",
              ".hermes/skills/scholion", ".gemini/skills/scholion")
SKILL_SIDECAR = ".scholion-version"
#: How a stale copy is reported: as an error. A host reading an old entry is
#: operated under instructions this build no longer gives, and a model working
#: from the wrong instructions produces a quietly wrong answer rather than a
#: failure, so `selfcheck` fails until the copy is replaced.
STALE_SKILL_IS = "error"


def _home():
    import os
    from pathlib import Path as _P
    return _P(os.path.expanduser("~"))


def package_skill_entry():
    from pathlib import Path as _P
    import scholion
    return _P(scholion.__file__).resolve().parent / "skill" / "SKILL.md"


def install_skill(dest: Optional[str] = None) -> Dict[str, Any]:
    """Copy the entry into a skills folder and record the build beside it."""
    from pathlib import Path as _P
    src = package_skill_entry()
    if not src.is_file():
        return {"ok": False, "error": "no_entry"}
    folder = _P(dest).expanduser() if dest else _home() / SKILL_DIRS[0]
    target = folder / "SKILL.md"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        previous = None
        side = folder / SKILL_SIDECAR
        if side.is_file():
            previous = side.read_text(encoding="utf-8").strip() or None
        new = src.read_bytes()
        same = target.is_file() and target.read_bytes() == new
        if not same:
            target.write_bytes(new)
        side.write_text(installed() + "\n", encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": "not_writable", "path": str(folder), "reason": type(exc).__name__}
    return {"ok": True, "path": str(target), "version": installed(), "previous": previous,
            "action": "unchanged" if same else ("replaced" if previous or target.exists() else "installed")}


def skill_copies() -> List[Dict[str, Any]]:
    """Copies of the entry in the usual skills folders, and whether each matches this build."""
    src = package_skill_entry()
    want = src.read_bytes() if src.is_file() else None
    out = []
    for rel in SKILL_DIRS:
        folder = _home() / rel
        entry = folder / "SKILL.md"
        try:
            if not entry.is_file():
                continue
            side = folder / SKILL_SIDECAR
            marked = side.read_text(encoding="utf-8").strip() if side.is_file() else None
            same = want is not None and entry.read_bytes() == want
        except OSError:
            continue
        status = ("current" if same else "older" if marked else "unmarked")
        out.append({"path": str(entry), "version": marked, "status": status,
                    "severity": None if same else STALE_SKILL_IS})
    return out
