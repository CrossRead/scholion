"""assistant.py — the assistant layer: what the application does by itself and where a model helps.

Why this module. The application is self-sufficient: numbers, flags, trends,
pharmacogenetics, the «second opinion» and the draw checklist are computed by local code,
without the internet and without any language model. The assistant is an optional layer on
top: it puts things into words, sets priorities and updates the curated texts of the
profile. From the outside this was not obvious: a person opening the application understood
neither that it works on its own, nor how to connect a model when one is wanted.

The module answers three questions and changes nothing in the data:
  1. Whether it is true that the core works without a model → ``status()['audit']`` checks
     that by SCANNING ITS OWN CODE at request time, not by a declaration in prose.
     A claim that verifies itself does not go stale at the next edit.
  2. What exactly the assistant adds → a list of the profile's curated texts with the date
     of the update and a staleness sign (the engine already derives it from watch lists).
  3. How to connect one → which entry points were found on this machine and how to build
     the context for any other model.

Run: python3 -m scholion assistant [--context [--out FILE]]
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core
from .i18n import t as _t

PKG = Path(__file__).resolve().parent
REPO = PKG.parents[1]

# Markers of a CALL to a language model: an endpoint address, a client import, a variable
# holding a key. A call, not a word: model names occur in this very file as ordinary text
# («paste it into ChatGPT»), and on a name alone the check would catch itself. The strings
# are glued together from pieces for the same reason — so that the list of markers is not
# found as a match. No file is excluded from the check, this one included.
_LLM_MARKERS = [
    "api." + "anthropic.com", "api." + "openai.com", "generativelanguage." + "googleapis.com",
    "api." + "mistral.ai", "import " + "anthropic", "import " + "openai",
    "ANTHROPIC_" + "API_KEY", "OPENAI_" + "API_KEY", "localhost:" + "11434",
    "/v1/chat/" + "completions", "/v1/" + "messages",
]
_URL_RE = re.compile(r"https?://([a-zA-Z0-9.\-]+)")


def _scan_python(path: Path):
    """(lines, marker hits, hosts) for a single Python file.

    Hosts are collected only from REQUEST STRINGS — assignments of the form
    ``_X = "https://…"`` and literals inside urlopen/Request. Addresses out of
    comments and documentation (a link to an article, to a utility's site) do not
    get into the list: otherwise the report «where the application goes» would mix
    real requests with a bibliography.
    """
    txt = path.read_text(encoding="utf-8", errors="replace")
    hits, hosts = [], set()
    low = txt.lower()
    for mark in _LLM_MARKERS:
        if mark.lower() in low:
            hits.append({"file": path.name, "marker": mark})
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("#") or "http" not in s:
            continue
        head = s.split("http", 1)[0]
        if "=" not in head and "urlopen(" not in head and "Request(" not in head:
            continue                       # a mention in prose, not a request
        for h in _URL_RE.findall(s):
            if h not in ("127.0.0.1", "localhost"):
                hosts.add(h)
    return txt.count("\n") + 1, hits, hosts


def _scan_shell(path: Path):
    """(lines, hosts) for a shell script.

    The heuristic here is deliberately wider than in Python: in a shell the address most
    often stands as an argument (`curl -O https://…`), and requiring an assignment is not
    possible. A superfluous address in the inventory is safer than a missed one: the
    inventory exists to OVERSTATE the surface, not to understate it.
    """
    txt = path.read_text(encoding="utf-8", errors="replace")
    hosts = set()
    for line in txt.splitlines():
        s = line.strip()
        if s.startswith("#") or "http" not in s:
            continue
        for h in _URL_RE.findall(s):
            if h not in ("127.0.0.1", "localhost"):
                hosts.add(h)
    return txt.count("\n") + 1, hosts


def _audit_core() -> Dict[str, Any]:
    """A scan: whether there are calls to language models, and where the code goes at all.

    Two DIFFERENT checks, and they must not be mixed. The first is about language models:
    the verdict concerns the core, because it is the core that computes the conclusions.
    The second is an inventory of outgoing addresses, and it has two layers:

      · the core — what a running application can send;
      · the data preparation scripts (`ingest`) — what a person runs by hand when
        assembling the genome or updating the reference books.

    Mixing them would mean either attributing the ClinVar download to the application, or
    passing over it in silence. Both of those are untrue.

    COVERAGE is returned separately: how many files and which directories were read.
    A negative result without coverage is not a statement; the project applies that rule
    to the genome, and it applies to its own code in exactly the same way.
    """
    files = lines = 0
    hits: List[Dict[str, str]] = []
    hosts: set = set()
    for f in sorted(PKG.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        try:
            n, h, hh = _scan_python(f)
        except OSError:
            continue
        files += 1
        lines += n
        hits += h
        hosts |= hh

    # The data preparation directory: in the source tree and in the de-identified
    # distribution it lies next to the package, in an installed wheel it is absent
    # altogether. Absence is not an error, but it cannot be passed over either: the
    # coverage must name what exactly was read.
    ing_files = ing_lines = 0
    ing_hosts: set = set()
    ingest_dir = PKG.parent / "ingest"
    if ingest_dir.is_dir():
        for f in sorted(list(ingest_dir.rglob("*.py")) + list(ingest_dir.rglob("*.sh"))):
            if "__pycache__" in f.parts:
                continue
            try:
                if f.suffix == ".py":
                    n, h, hh = _scan_python(f)
                    hits += h
                else:
                    n, hh = _scan_shell(f)
            except OSError:
                continue
            ing_files += 1
            ing_lines += n
            ing_hosts |= hh

    scanned = [_t("assistant.scan_core", files=files, lines=lines)]
    if ingest_dir.is_dir():
        scanned.append(_t("assistant.scan_ingest", files=ing_files, lines=ing_lines))
    else:
        scanned.append(_t("assistant.scan_ingest_absent"))

    return {"files": files, "lines": lines, "llm_hits": hits,
            "network_hosts": sorted(hosts),
            "ingest_hosts": sorted(ing_hosts - hosts),
            "scanned": scanned,
            "verdict": _t("assistant.verdict_clean") if not hits
                       else _t("assistant.verdict_hits")}


# --------------------------------------------------------------------------
# what the code computes and what the assistant adds
# --------------------------------------------------------------------------
# The lists hold KEYS, not phrases: the language is chosen when `status()` is called,
# and the web server calls it once per request, in the language of that request.
ENGINE_DOES = [
    "assistant.engine.parsing",
    "assistant.engine.flags",
    "assistant.engine.genome",
    "assistant.engine.pgx",
    "assistant.engine.second_opinion",
    "assistant.engine.checklist",
    "assistant.engine.goals",
]
# Everything listed is available both in the web UI and from the command line: parity of
# entry points is a project rule, not a coincidence (see contract.py and tests/test_parity.py).
ASSISTANT_ADDS = [
    "assistant.adds.narrative",
    "assistant.adds.provenance",
    "assistant.adds.what_if",
    "assistant.adds.questions",
    "assistant.adds.curated",
]

# curated texts: the assistant writes the wording, the engine substitutes the numbers
# `title` and `tab` are catalogue KEYS here; `_curated_state()` resolves them, so the
# tab a text belongs to is named with the same phrase the tab itself carries.
CURATED = [
    {"id": "brief", "file": "lifestyle_brief.json", "title": "assistant.curated.brief",
     "tab": "web.tab.lifestyle", "cmd": "python3 -m scholion brief"},
    {"id": "focus", "file": "focus.json", "title": "assistant.curated.focus",
     "tab": "web.tab.overview", "cmd": "python3 -m scholion focus"},
    {"id": "goal", "file": "health_goals.json", "title": "assistant.curated.goal",
     "tab": "web.tab.overview", "cmd": "python3 -m scholion goal"},
]


def _meta_date(obj: Dict[str, Any]) -> Optional[str]:
    meta = obj.get("_meta") or obj.get("meta") or {}
    for k in ("updated", "compiled", "reviewed", "date"):
        v = meta.get(k) or obj.get(k)
        if isinstance(v, str) and re.match(r"\d{4}-\d{2}", v):
            return v
    return None


def _curated_state() -> List[Dict[str, Any]]:
    """Curated texts: when they were updated and whether they lag behind newer data."""
    out = []
    prof = Path(core.profile_dir())
    for c in CURATED:
        p = prof / c["file"]
        item = {**c, "title": _t(c["title"]), "tab": _t(c["tab"]),
                "exists": p.exists(), "updated": None, "stale": False,
                "stale_blocks": [], "note": ""}
        if not p.exists():
            item["note"] = _t("assistant.curated.absent")
            out.append(item)
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                   # noqa: BLE001
            item["note"] = _t("assistant.curated.unreadable")
            out.append(item)
            continue
        item["updated"] = _meta_date(obj)
        if c["id"] == "brief":
            try:
                from . import engine
                b = engine.lifestyle_brief()
                item["stale"] = bool(b.get("needs_review"))
                item["stale_blocks"] = [x.get("title") for x in (b.get("stale_blocks") or [])]
                if item["stale"]:
                    item["note"] = _t("assistant.curated.stale")
            except Exception:                               # noqa: BLE001
                pass
        out.append(item)
    return out


# --------------------------------------------------------------------------
# entry points: what was found on this machine
# --------------------------------------------------------------------------
def _entrypoints() -> List[Dict[str, Any]]:
    home = Path.home()
    eps: List[Dict[str, Any]] = []

    # 1. the skill for Claude
    skill_src = REPO / "src" / "skill" / "SKILL.md"
    installed = [p for p in (home / ".claude" / "skills").glob("*/SKILL.md")
                 if "scholion" in p.parent.name.lower()] if (home / ".claude" / "skills").is_dir() else []
    eps.append({
        "id": "skill", "title": _t("assistant.ep.skill.title"),
        "state": "ok" if installed else ("ready" if skill_src.exists() else "missing"),
        "detail": (_t("assistant.ep.skill.installed", path=installed[0].parent) if installed
                   else (_t("assistant.ep.skill.ready") if skill_src.exists()
                         else _t("assistant.ep.skill.missing"))),
        "how": ("mkdir -p ~/.claude/skills && ln -s "
                f"'{skill_src.parent}' ~/.claude/skills/scholion"),
        "what": _t("assistant.ep.skill.what"),
    })

    # 2. the Ouroboros plugin
    plug = REPO / "ouroboros_plugin" / "scholion_tools.py"
    eps.append({
        "id": "ouroboros", "title": _t("assistant.ep.ouroboros.title"),
        "state": "ready" if plug.exists() else "missing",
        "detail": (_t("assistant.ep.ouroboros.ready", path=plug.relative_to(REPO))
                   if plug.exists() else _t("assistant.ep.ouroboros.missing")),
        "how": _t("assistant.ep.ouroboros.how"),
        "what": _t("assistant.ep.ouroboros.what"),
    })

    # 3. any other model
    eps.append({
        "id": "any", "title": _t("assistant.ep.any.title"),
        "state": "ready",
        "detail": _t("assistant.ep.any.detail"),
        "how": "python3 -m scholion assistant --context",
        "what": _t("assistant.ep.any.what"),
    })
    return eps


def status() -> Dict[str, Any]:
    return {
        "works_without_assistant": True,
        "audit": _audit_core(),
        "engine_does": [_t(k) for k in ENGINE_DOES],
        "assistant_adds": [_t(k) for k in ASSISTANT_ADDS],
        "curated": _curated_state(),
        "data_layout": core.source_status(),
        "entrypoints": _entrypoints(),
        "planned": _t("assistant.planned"),
        "disclaimer": _t("assistant.disclaimer"),
    }


# --------------------------------------------------------------------------
# the context to paste into any model
# --------------------------------------------------------------------------
def _fmt_meds() -> str:
    meds = core.medications_json().get("medications", []) or []
    if not meds:
        return _t("assistant.ctx.no_meds")
    rows = []
    for m in meds:
        name = m.get("name") or m.get("drug") or "?"
        dose = m.get("dose") or m.get("dosage") or ""
        since = m.get("since") or m.get("start") or ""
        since_s = _t("assistant.ctx.med_since", date=since) if since else ""
        rows.append(f"— {name} {dose} {since_s}".rstrip())
    return "\n".join(rows) + "\n"


def _fmt_ref(m: Dict[str, Any]) -> str:
    """The reference range in words. A one-sided threshold is written as «<x» / «>x», not
    «None–x»: an empty bound in prose is read by a model as a real value."""
    lo, hi = m.get("ref_low"), m.get("ref_high")
    if lo is not None and hi is not None:
        return _t("assistant.ctx.ref_range", low=lo, high=hi)
    if hi is not None:
        return _t("assistant.ctx.ref_max", high=hi)
    if lo is not None:
        return _t("assistant.ctx.ref_min", low=lo)
    return _t("assistant.ctx.ref_none")


def context_bundle(limit_abnormal: int = 25) -> str:
    """Text to paste into a dialogue with any model. CONTAINS PERSONAL DATA."""
    from . import engine

    parts: List[str] = []
    parts.append(_t("assistant.ctx.title"))
    parts.append(_t("assistant.ctx.collected", date=date.today().isoformat()))
    parts.append(_t("assistant.ctx.personal"))
    parts.append("\n" + _t("assistant.ctx.rules"))

    prof = engine.load_profile()
    gs = engine.genome_status()
    parts.append(_t("assistant.ctx.connected_h"))
    parts.append(_t("assistant.ctx.markers", n=len(prof.get('labs_markers') or [])))
    parts.append(_t("assistant.ctx.pgx_genes", n=len(prof.get('pgx_genes') or [])))
    parts.append(_t("assistant.ctx.genome",
                    state=_t("genome.connected" if gs.get("ready") else "genome.not_connected")))

    parts.append(_t("assistant.ctx.meds_h"))
    parts.append(_fmt_meds())

    labs = engine.analyze_labs()
    all_ab = [m for m in labs.get("markers", []) if m.get("abnormal")]
    ab = all_ab[:limit_abnormal]
    parts.append(_t("assistant.ctx.abnormal_h", abnormal=labs.get('abnormal_count', 0),
                    total=labs.get('count', 0)))
    if ab:
        for m in ab:
            parts.append(_t("assistant.ctx.abnormal_row", name=m.get('name'),
                            value=m.get('value'), unit=m.get('unit', ''), ref=_fmt_ref(m),
                            date=m.get('date', ''), flag=m.get('flag')))
        if len(all_ab) > len(ab):
            # silent truncation is forbidden here: the model would decide it sees everything
            parts.append(_t("assistant.ctx.truncated", shown=len(ab), total=len(all_ab)))
    else:
        parts.append(_t("assistant.ctx.none_row"))

    tests = engine.suggest_tests()
    pend = [s for s in tests.get("suggestions", []) if not s.get("done_recently")][:12]
    parts.append(_t("assistant.ctx.tests_h", n=len(pend)))
    for s in pend:
        parts.append(_t("assistant.ctx.test_row", suggest=s.get('suggest'),
                        why=s.get('why', ''), priority=s.get('priority', '')))
    if not pend:
        parts.append(_t("assistant.ctx.none_row"))

    try:
        f = engine.focus_dashboard()
        if f.get("available", True) and f.get("title"):
            parts.append(_t("assistant.ctx.focus_h", title=f.get('title')))
    except Exception:                                       # noqa: BLE001
        pass

    parts.append(_t("assistant.ctx.commands"))
    return "".join(parts)


def format_status(st: Dict[str, Any]) -> str:
    a = st["audit"]
    L = [_t("assistant.works_without",
            answer=_t("common.yes" if st["works_without_assistant"] else "common.no")),
         _t("assistant.code_check", scanned='; '.join(a.get('scanned') or []),
            verdict=a['verdict']),
         "",
         _t("assistant.network_lead"),
         f"  · {', '.join(a['network_hosts']) or '—'}",
         _t("assistant.network_detail"),
         "", _t("assistant.engine_does_h")]
    if a.get("ingest_hosts"):
        L[6:6] = [_t("assistant.ingest_hosts", hosts=', '.join(a['ingest_hosts']))]
    L += [f"  · {x}" for x in st["engine_does"]]
    L += ["", _t("assistant.adds_h")] + [f"  · {x}" for x in st["assistant_adds"]]
    L += ["", _t("assistant.curated_h")]
    for c in st["curated"]:
        mark = "✓" if c["exists"] and not c["stale"] else ("⚠" if c["exists"] else "·")
        L.append(f"  {mark} {c['title']} — {c['updated'] or _t('common.none')}"
                 + (f" · {c['note']}" if c["note"] else ""))
    # Not the whole layout is shown, only what a person needs to know about: what was moved
    # to another disk and what is absent. Listing five folders, four of which are in place,
    # is noise behind which the fifth stops being noticed.
    notable = [s for s in st.get("data_layout", [])
               if s["external"] or not s["connected"]]
    if notable:
        L += ["", _t("layout.header")]
        for s in notable:
            if not s["connected"]:
                L.append(_t("layout.missing", slot=s["slot"], path=s["path"]))
            else:
                L.append(_t("layout.external", slot=s["slot"], path=s["path"]))

    L += ["", _t("assistant.entrypoints_h")]
    for e in st["entrypoints"]:
        mark = {"ok": "✓", "ready": "·", "missing": "✗"}.get(e["state"], "·")
        L.append(f"  {mark} {e['title']}: {e['detail']}")
        L.append(f"      {e['how']}")
    L += ["", st["planned"], "", st["disclaimer"]]
    return "\n".join(L)
