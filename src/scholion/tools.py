"""External command-line tools: what is missing, why it matters, and how to get it.

The analysis runs on the standard library. The data preparation does not: reading
a VCF needs bcftools, indexing it needs htslib, measuring coverage needs mosdepth.
Each script already checks its own tools and stops with a hint — correct
behaviour, at the worst possible moment. On the genome path that moment arrives an
hour into an alignment, and the hint names one binary out of the eleven the job
will end up needing.

So the check moved to the front, to `scholion init`, and the list moved into
`knowledge/external_tools.json` where it can be read instead of remembered. The
binary and the package are frequently not the same word — `bgzip` and `tabix` both
come out of `htslib`, `uvx` comes out of `uv` — which is why a list of binaries
cannot simply be handed to a package manager.

Two rules bound what this module is allowed to do, and both exist because the
project has already broken one of them.

**Nothing is installed without an explicit answer.** `install()` refuses unless
`confirm=True` is passed. This is not a formality: until v2.6.1 the PDF path ran
`pip install pdfplumber` by itself the moment a form appeared in a folder — with
`--break-system-packages` as the last resort. A tool whose whole claim is that it
acts only on command must not change somebody's machine while they are not
looking.

**Nothing here asks for administrator rights.** Homebrew and conda install into
the user's own prefix, and that is the reason those two are the managers we drive.
Anything that would need `sudo` — a distribution package, a container runtime — is
printed as text for the person to run themselves, and a test asserts that the word
never appears in a command this module generates.

What the module offers:

    status()                  what is present, what is missing, per set
    plan(names, manager)      the exact commands, grouped by package
    install(names, manager, confirm=True)   run them
    report(...)               the same picture as text, for the CLI
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence

from . import core
from .i18n import t as _t

# ---------------------------------------------------------------------------
# The managers we are willing to drive, and the ones we only ever quote.
#
# `key` is the name under which a package is looked up in the knowledge file:
# mamba and conda install from the same channels under the same names, so they
# share one key rather than duplicating every entry.
#
# `auto` is what may be chosen without being asked for. pip is deliberately not
# auto: it writes into the interpreter the application itself runs on, and
# choosing that for somebody is exactly the behaviour removed in v2.6.1. It stays
# available, by name, for the two tools that have no other route on Linux.
MANAGERS: Dict[str, Dict[str, Any]] = {
    "brew":  {"key": "brew",  "auto": True,  "probe": "brew"},
    "mamba": {"key": "conda", "auto": True,  "probe": "mamba"},
    "conda": {"key": "conda", "auto": True,  "probe": "conda"},
    "pip":   {"key": "pip",   "auto": False, "probe": None},
}

# The order is a preference, not an alphabet. Homebrew first: on macOS, which is
# where this project runs, it is the one most people already have, and its prefix
# is the user's own. mamba before conda because it resolves bioconda in seconds
# rather than minutes — same packages, same channels.
AUTO_ORDER = ("brew", "mamba", "conda")

CHANNELS = ("conda-forge", "bioconda")


def catalogue() -> Dict[str, Any]:
    """The knowledge file, with its curated fields already in the current language."""
    return core.external_tools()


# --- what is on this machine ----------------------------------------------

def which(name: str) -> Optional[str]:
    return shutil.which(name)


def _pip_present() -> bool:
    try:
        import importlib.util
        return importlib.util.find_spec("pip") is not None
    except Exception:                                   # a broken import path is not a crash here
        return False


def available_managers() -> List[str]:
    """Managers actually installed, in preference order. pip is listed last and only if importable."""
    found = [m for m in AUTO_ORDER if which(MANAGERS[m]["probe"])]
    if _pip_present():
        found.append("pip")
    return found


def pick_manager(preferred: Optional[str] = None) -> Optional[str]:
    """Which manager to use. A named one is honoured only if it is really there."""
    if preferred:
        if preferred not in MANAGERS:
            raise ValueError(f"unknown package manager: {preferred}")
        return preferred if preferred in available_managers() else None
    for m in available_managers():
        if MANAGERS[m]["auto"]:
            return m
    return None


# --- what a tool needs -----------------------------------------------------

def package_for(tool: str, manager: str) -> Optional[str]:
    """The package name for this tool under this manager, or None if we do not know one.

    None is a real answer and is printed as one. Guessing a name is worse than
    admitting the gap: the person runs the guess, it fails, and now the rest of
    the list is suspect too.
    """
    entry = catalogue().get("tools", {}).get(tool) or {}
    return (entry.get("packages") or {}).get(MANAGERS[manager]["key"])


def _argv(manager: str, package: str) -> List[str]:
    if manager == "brew":
        return ["brew", "install", package]
    if manager in ("conda", "mamba"):
        argv = [manager, "install", "-y"]
        for c in CHANNELS:
            argv += ["-c", c]
        return argv + [package]
    if manager == "pip":
        # The interpreter is named explicitly: `pip` on the PATH is regularly a
        # different interpreter from the one running this code, and the package
        # would then land where the application cannot see it.
        return [sys.executable, "-m", "pip", "install", package]
    raise ValueError(f"unknown package manager: {manager}")


def plan(names: Sequence[str], manager: Optional[str]) -> Dict[str, Any]:
    """The commands that would install `names` — grouped by package, in order.

    Grouping is not tidiness: `bgzip` and `tabix` are one package, and a plan that
    installed `htslib` twice would look like a plan written by something that did
    not understand what it was doing.
    """
    steps: List[Dict[str, Any]] = []
    unhandled: List[Dict[str, Any]] = []
    seen: Dict[str, Dict[str, Any]] = {}
    kb = catalogue().get("tools", {})
    for name in names:
        entry = kb.get(name) or {}
        package = package_for(name, manager) if manager else None
        if not package:
            unhandled.append({"tool": name, "note": entry.get("note"),
                              "system": bool(entry.get("system"))})
            continue
        if package in seen:
            seen[package]["tools"].append(name)
            continue
        argv = _argv(manager, package)
        step = {"package": package, "manager": manager, "argv": argv,
                "text": " ".join(shlex.quote(a) for a in argv), "tools": [name]}
        seen[package] = step
        steps.append(step)
    return {"manager": manager, "steps": steps, "unhandled": unhandled}


def combined_command(manager: str, packages: Sequence[str]) -> str:
    """One readable line for several packages of the same manager.

    For SHOWING only. Running still goes package by package: `brew install a b c`
    stops at the first failure and leaves the rest uninstalled, which in a report
    afterwards is indistinguishable from never having been asked for.
    """
    argv = _argv(manager, "PLACEHOLDER")
    argv = argv[:argv.index("PLACEHOLDER")] + list(packages)
    return " ".join(shlex.quote(a) for a in argv)


def other_routes(tool: str, besides: Optional[str] = None) -> List[str]:
    """Every manager that does have a package for this tool, as ready commands.

    This exists because of a defect in the first version of the report: with no
    manager installed it announced «no verified install command» for bcftools —
    a tool whose package name is known for both managers. «We do not know how»
    and «you have no manager» are different sentences, and printing the first
    when the second is true teaches the reader to distrust the whole list.
    """
    out = []
    for m in ("brew", "conda", "pip"):
        if besides and MANAGERS[m]["key"] == MANAGERS[besides]["key"]:
            continue
        pkg = package_for(tool, m)
        if pkg:
            out.append(combined_command(m, [pkg]))
    return out


# --- the picture -----------------------------------------------------------

def status(manager: Optional[str] = None) -> Dict[str, Any]:
    """Everything the report and the JSON output need, computed once."""
    kb = catalogue()
    chosen = pick_manager(manager)
    tools: Dict[str, Dict[str, Any]] = {}
    for name, entry in (kb.get("tools") or {}).items():
        path = which(name)
        tools[name] = {
            "tool": name,
            "present": bool(path),
            "path": path,
            "why": entry.get("why") or "",
            "system": bool(entry.get("system")),
            "note": entry.get("note"),
            "package": package_for(name, chosen) if chosen else None,
        }
    sets: List[Dict[str, Any]] = []
    for key, s in (kb.get("sets") or {}).items():
        required = list(s.get("tools") or [])
        extra = list(s.get("optional") or [])
        missing = [n for n in required if not tools.get(n, {}).get("present")]
        sets.append({
            "key": key,
            "label": s.get("label") or key,
            "why": s.get("why") or "",
            "offer_at_init": bool(s.get("offer_at_init")),
            "tools": required,
            "optional": extra,
            "missing": missing,
            "missing_optional": [n for n in extra if not tools.get(n, {}).get("present")],
            "complete": not missing,
        })
    missing_all = sorted({n for s in sets for n in s["missing"]})
    return {
        "ok": True,
        "manager": chosen,
        "managers_found": available_managers(),
        "sets": sets,
        "tools": [tools[n] for n in sorted(tools)],
        "missing": missing_all,
        "missing_count": len(missing_all),
    }


def set_names(status_obj: Optional[Dict[str, Any]] = None) -> List[str]:
    return [s["key"] for s in (status_obj or status())["sets"]]


def tools_of(sets: Sequence[str], status_obj: Optional[Dict[str, Any]] = None,
             *, missing_only: bool = True) -> List[str]:
    """The tools of the named sets, in declaration order and without repeats.

    `hla` and `base` both need samtools; installing it twice is not wrong, but a
    list that says so twice reads as carelessness.
    """
    st = status_obj or status()
    wanted = set(sets)
    out: List[str] = []
    for s in st["sets"]:
        if s["key"] not in wanted:
            continue
        for n in (s["missing"] if missing_only else s["tools"]):
            if n not in out:
                out.append(n)
    return out


# --- doing it --------------------------------------------------------------

def install(names: Sequence[str], manager: Optional[str] = None, *,
            confirm: bool = False, timeout: int = 1800) -> Dict[str, Any]:
    """Install the named tools. Runs nothing at all unless `confirm=True`.

    The refusal is a returned value rather than an exception because every caller
    has to show it to somebody: a person who declined the question is not an error
    condition. What matters is that no branch reaches `subprocess` without the
    flag, and a test holds that shut.
    """
    from . import net
    if not confirm:
        return {"ok": False, "refused": True, "reason": "not_confirmed",
                "message": _t("tools.not_confirmed"), "ran": [], "installed": [],
                "still_missing": list(names)}
    if net.offline():
        # SCHOLION_OFFLINE is a statement about this machine, not about a single
        # request. Installing reaches the network, so it is covered by it.
        return {"ok": False, "refused": True, "reason": "offline",
                "message": _t("tools.offline"), "ran": [], "installed": [],
                "still_missing": list(names)}
    chosen = pick_manager(manager)
    if not chosen:
        return {"ok": False, "refused": True, "reason": "no_manager",
                "message": _t("tools.no_manager"), "ran": [], "installed": [],
                "still_missing": list(names)}
    p = plan(names, chosen)
    ran: List[Dict[str, Any]] = []
    for step in p["steps"]:
        assert "sudo" not in step["argv"], "a command with sudo must never be run from here"
        print(_t("tools.running", command=step["text"]), flush=True)
        try:
            # No shell: the package name comes out of a JSON file, and a shell
            # would turn a bad line in that file into arbitrary code. Output is
            # left on the terminal — brew and conda report progress, and hiding a
            # ten-minute build behind silence looks like a hang.
            done = subprocess.run(step["argv"], timeout=timeout)
            code = done.returncode
        except FileNotFoundError:
            code = 127
        except subprocess.TimeoutExpired:
            code = 124
        ran.append({"package": step["package"], "text": step["text"], "code": code,
                    "tools": step["tools"]})
    # Asked of the machine again rather than deduced from the exit codes: a manager
    # can return 0 and leave the binary off the PATH — Homebrew's keg-only formulae
    # do exactly that, which is why `java` carries a note about it.
    installed = [n for n in names if which(n)]
    still = [n for n in names if not which(n)]
    return {"ok": not still, "refused": False, "manager": chosen, "ran": ran,
            "installed": installed, "still_missing": still,
            "unhandled": [u["tool"] for u in p["unhandled"]]}


# --- the same picture as text ----------------------------------------------
# Rendering lives here rather than in `format.py` because this is a maintenance
# command about the machine, not a report about a person: nothing on this screen
# comes out of the engine, and putting it beside the health reports would make
# the boundary between them harder to see, not easier.

def report(status_obj: Optional[Dict[str, Any]] = None) -> str:
    st = status_obj or status()
    out: List[str] = [_t("tools.title"), "", _t("tools.intro"), ""]
    if st["manager"]:
        out.append(_t("tools.manager_found", name=st["manager"]))
    else:
        out.append(_t("tools.no_manager"))
    out.append(_t("tools.sudo_never"))
    out.append("")
    by_name = {t["tool"]: t for t in st["tools"]}
    for s in st["sets"]:
        mark = "✅" if s["complete"] else "⚠️"
        out.append(f"{mark} **{s['label']}**" + ("" if s["complete"] else
                                                 f" — {_t('tools.state_missing', n=len(s['missing']))}"))
        out.append(f"   {s['why']}")
        for name in s["tools"] + s["optional"]:
            info = by_name.get(name) or {"present": False, "why": "", "system": False}
            tail = _t("tools.optional") if name in s["optional"] else ""
            if info["present"]:
                out.append(f"   ✓ {name} — {info['why']}{tail}")
            elif info["system"]:
                out.append(f"   ✗ {name} — {info['why']} — {_t('tools.system')}{tail}")
            else:
                out.append(f"   ✗ {name} — {info['why']}{tail}")
        out.append("")
    missing = st["missing"]
    if not missing:
        out.append(_t("tools.all_present"))
        return "\n".join(out).rstrip() + "\n"
    if st["manager"]:
        p = plan(missing, st["manager"])
        if p["steps"]:
            out.append(_t("tools.will_run"))
            width = max(len(s["text"]) for s in p["steps"])
            for step in p["steps"]:
                out.append(f"   {step['text']:<{width}}   # {', '.join(step['tools'])}")
            out.append("")
        for u in p["unhandled"]:
            name = u["tool"]
            alt = other_routes(name, st["manager"])
            if u["system"]:
                out.append(f"✗ {name} — {_t('tools.system')}")
            elif alt:
                out.append(_t("tools.other_route", tool=name, manager=st["manager"],
                              command=alt[0]))
            else:
                out.append(_t("tools.no_route", tool=name))
            if u["note"]:
                out.append(f"   {u['note']}")
        if p["unhandled"]:
            out.append("")
        for name in missing:
            note = (by_name.get(name) or {}).get("note")
            if note and all(name != u["tool"] for u in p["unhandled"]):
                out.append(f"ℹ️ {name}: {note}")
        out.append("")
    else:
        # No manager on this machine. The commands are still known, and showing
        # them is the difference between «install one of these two and run one
        # line» and «work it out yourself».
        out.append(_t("tools.routes_header"))
        for m in ("brew", "conda", "pip"):
            packages, covered = [], []
            for name in missing:
                pkg = package_for(name, m)
                if pkg and pkg not in packages:
                    packages.append(pkg)
                if pkg:
                    covered.append(name)
            if packages:
                out.append(f"   {combined_command(m, packages)}")
                out.append(f"       # {', '.join(covered)}")
        out.append("")
        for name in missing:
            info = by_name.get(name) or {}
            if other_routes(name):
                if info.get("note"):
                    out.append(f"ℹ️ {name}: {info['note']}")
                continue
            if info.get("system"):
                out.append(f"✗ {name} — {_t('tools.system')}")
            else:
                out.append(_t("tools.no_route", tool=name))
            if info.get("note"):
                out.append(f"   {info['note']}")
        out.append("")
    out.append(_t("tools.later"))
    return "\n".join(out).rstrip() + "\n"


# --- the question asked once, at the end of `init` --------------------------

def _affirmative(answer: str) -> bool:
    """`y` and `yes` always work; the catalogue adds the current language's own word.

    Hard-coding the Latin letters is not laziness — a person typing into a
    terminal that has just printed English prompts will reach for `y` whatever
    language the report is in.
    """
    answer = (answer or "").strip().lower()
    words = {"y", "yes"} | {w.strip().lower() for w in _t("tools.yes_words").split(",") if w.strip()}
    return answer in words


def offer_after_init(*, assume_yes: bool = False, skip: bool = False,
                     stream=None) -> Dict[str, Any]:
    """The first-run question: name what is missing, then ask before touching anything.

    Deliberately narrow. Only the sets marked `offer_at_init` are involved — the
    ones without which the genome layer does not work at all. Everything else is
    offered by the step that needs it, when it needs it: a first run that opens
    with eleven installations reads as a demand, and the honest answer to "do you
    need a container runtime" is "not until you ask for WGS calling".
    """
    stream = stream or sys.stdout
    if skip:
        return {"asked": False, "reason": "skipped"}
    st = status()
    wanted = [s["key"] for s in st["sets"] if s["offer_at_init"]]
    missing = tools_of(wanted, st)
    if not missing:
        return {"asked": False, "reason": "nothing_missing"}
    print(file=stream)
    from .i18n import plural as _plural
    print(_t("tools.init_intro", programs=_plural(len(missing), "count.programs")), file=stream)
    by_name = {t["tool"]: t for t in st["tools"]}
    for name in missing:
        print(f"   ✗ {name} — {by_name.get(name, {}).get('why', '')}", file=stream)
    p = plan(missing, st["manager"])
    if not p["steps"]:
        print(_t("tools.no_manager"), file=stream)
        print(_t("tools.later"), file=stream)
        return {"asked": False, "reason": "no_manager", "missing": missing}
    print(file=stream)
    print(_t("tools.will_run"), file=stream)
    for step in p["steps"]:
        print(f"   {step['text']}", file=stream)
    if not assume_yes:
        if not sys.stdin.isatty():
            # A pipeline, a CI job, a launchd shortcut. There is nobody to answer,
            # and taking silence for consent is how an installer earns its
            # reputation.
            print(_t("tools.not_a_tty"), file=stream)
            return {"asked": False, "reason": "not_a_tty", "missing": missing}
        try:
            answer = input(_t("tools.ask"))
        except (EOFError, KeyboardInterrupt):
            print(file=stream)
            print(_t("tools.declined"), file=stream)
            return {"asked": True, "confirmed": False, "missing": missing}
        if not _affirmative(answer):
            print(_t("tools.declined"), file=stream)
            return {"asked": True, "confirmed": False, "missing": missing}
    r = install(missing, st["manager"], confirm=True)
    print(file=stream)
    if r.get("installed"):
        print(_t("tools.installed_ok", tools=", ".join(r["installed"])), file=stream)
    if r.get("still_missing"):
        print(_t("tools.install_failed", tools=", ".join(r["still_missing"])), file=stream)
        print(_t("tools.later"), file=stream)
    if r.get("message"):
        print(r["message"], file=stream)
    return {"asked": not assume_yes, "confirmed": True, "result": r, "missing": missing}
