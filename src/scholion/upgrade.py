"""Finding and installing a newer Scholion — from the page, the command line, or inside an assistant's session.

A person who uses the package through an assistant never opens the page where
the update note lives, so a newer version went unseen: «otherwise they will not
even know» (owner, 14.09.2026). Two halves, and each is the person's:

* The notice. Which version the package registry calls current, remembered in
  the cache for a day so a session does not ask on every call, and never asked
  with SCHOLION_OFFLINE. Only the package's name leaves the machine — no profile,
  no value, no identifier.
* The install. The command that updates THIS environment — pip in the running
  interpreter, pipx, or uv tool — run only after a person said yes. A source
  checkout is never «upgraded» from the registry behind its own history: it is
  told to pull.

A third case arrived from the Ouroboros Hub maintainer (review of PR #74,
19.09.2026): a skill the host installs is run by a child of the HOST's
interpreter, so «pip in the running interpreter» would install into the host's
Python, not into the skill's isolated environment — a side effect on somebody
else's environment, from a process no person watches. A door that knows its host
manages the install says so in `SCHOLION_MANAGED_BY`, and then `update` names
the host instead of running anything. The same review found the session note
repeating on every answer: «once per process» meant «every call» on a host that
starts a process per call. The note is now remembered beside the registry's
answer, so it is said once a day whatever the process does.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import core, updates

NOTICE_FILE = "update_notice.json"
MAX_AGE_HOURS = 24
PACKAGE = "scholion"


def _notice_path() -> Path:
    return core.cache_dir() / NOTICE_FILE


def _read_cached() -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(_notice_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def route(prefix: Optional[str] = None, package_dir: Optional[Path] = None,
          executable: Optional[str] = None) -> Dict[str, Any]:
    """How this very installation is updated: the command, and whether it may be run here."""
    host = (os.environ.get("SCHOLION_MANAGED_BY") or "").strip()
    if host:
        # First, before the source check: under a host the interpreter is the
        # host's, and every branch below would be a guess about somebody else's
        # environment.
        return {"kind": "host", "host": host, "command": [], "installable": False}
    prefix = (sys.prefix if prefix is None else prefix).replace("\\", "/")
    package_dir = package_dir or Path(__file__).resolve().parent
    root = package_dir.parent.parent
    if (root / ".git").exists() and (root / "pyproject.toml").exists():
        return {"kind": "source", "command": ["git", "-C", str(root), "pull"], "installable": False}
    if "/pipx/venvs/" in prefix:
        return {"kind": "pipx", "command": ["pipx", "upgrade", PACKAGE], "installable": True}
    if "/uv/tools/" in prefix:
        return {"kind": "uv", "command": ["uv", "tool", "upgrade", PACKAGE], "installable": True}
    return {"kind": "pip", "installable": True,
            "command": [executable or sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE]}


def notice(max_age_hours: float = MAX_AGE_HOURS, fetch: Optional[Callable] = None,
           now: Optional[float] = None) -> Dict[str, Any]:
    """Whether a newer version exists: from a check younger than a day, or asked now.

    A check is remembered only when the registry answered; an unreachable
    registry is asked again next time rather than read as «current» for a day.
    """
    from . import net
    now = time.time() if now is None else now
    installed = updates.installed()
    cached = _read_cached()
    if (cached and cached.get("installed") == installed
            and now - float(cached.get("checked_at") or 0) < max_age_hours * 3600):
        return {**cached, "from_cache": True, "route": route()}
    if fetch is None and net.offline():
        return {"status": "offline", "installed": installed, "latest": None,
                "from_cache": False, "route": route()}
    r = updates.check_registry(fetch)
    record = {"status": r["status"], "installed": installed, "latest": r.get("latest"),
              "checked_at": now}
    if r["status"] in ("newer", "current"):
        try:
            path = _notice_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            # What was already said survives a fresh check: otherwise the next
            # question to the registry would make the same release news again.
            said = (cached or {}).get("said")
            path.write_text(json.dumps({**record, **({"said": said} if said else {})}),
                            encoding="utf-8")
        except OSError:
            pass
    return {**record, "from_cache": False, "route": route()}


def _version_on_disk() -> str:
    """The version installed now, asked of a fresh interpreter: this process still runs the old one."""
    try:
        p = subprocess.run([sys.executable, "-c",
                            "import importlib.metadata as m; print(m.version('scholion'))"],
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        return (p.stdout or "").strip() or updates.installed()
    except (OSError, subprocess.TimeoutExpired):
        return updates.installed()


def install(confirm: bool = False, run: Optional[Callable] = None,
            version_after: Optional[Callable[[], str]] = None) -> Dict[str, Any]:
    """Install the newest version into this environment — only with `confirm`, never in a source tree."""
    from . import net
    r = route()
    base: Dict[str, Any] = {"route": r, "installed": updates.installed()}
    if not confirm:
        return {**base, "ok": False, "reason": "not_confirmed"}
    if not r["installable"]:
        return {**base, "ok": False, "reason": "host_managed" if r["kind"] == "host" else "source_tree"}
    if net.offline():
        return {**base, "ok": False, "reason": "offline"}
    try:
        p = (run or subprocess.run)(r["command"], capture_output=True, text=True, timeout=600,
                                    stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {**base, "ok": False, "reason": "failed", "code": None, "tail": str(e)[-800:]}
    tail = ((p.stdout or "") + (p.stderr or ""))[-800:]
    if p.returncode != 0:
        return {**base, "ok": False, "reason": "failed", "code": p.returncode, "tail": tail}
    after = (version_after or _version_on_disk)()
    try:
        _notice_path().unlink()
    except OSError:
        pass
    changed = after != base["installed"]
    return {**base, "ok": True, "reason": "installed" if changed else "already_current",
            "after": after, "restart": changed, "tail": tail}


_SAID = False
#: How long a note, once said, stays said. The registry is asked at most this often
#: too, so a person hears about one release at most once a day, on any host.
SAID_HOURS = 24


def _said_recently(latest: str, now: float) -> bool:
    said = (_read_cached() or {}).get("said") or {}
    return (said.get("latest") == latest
            and now - float(said.get("at") or 0) < SAID_HOURS * 3600)


def _remember_said(latest: str, now: float) -> None:
    try:
        path = _notice_path()
        data = _read_cached() or {}
        data["said"] = {"latest": latest, "at": now}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def session_note(now: Optional[float] = None) -> str:
    """One line when a newer version is known — once a day, whatever the process does.

    «The first answer of a session» used to be kept in a module variable, which
    is the first answer of a PROCESS. That holds for the web server and the MCP
    server over stdio, which live for a session; on a host that starts a fresh
    process for every tool call it is every answer (OuroborosHub review,
    19.09.2026). The mark now lives beside the registry's answer in the cache,
    so the note is said once a day for a given release on every door, and the
    variable stays only as the in-process short cut.
    """
    global _SAID
    if _SAID:
        return ""
    _SAID = True
    now = time.time() if now is None else now
    try:
        n = notice(now=now)
    except Exception:                                    # noqa: BLE001 - a notice never breaks an answer
        return ""
    if n.get("status") != "newer":
        return ""
    latest = str(n.get("latest") or "")
    if _said_recently(latest, now):
        return ""
    _remember_said(latest, now)
    from .i18n import t as _t
    key = "upgrade.session_note_host" if (n.get("route") or {}).get("kind") == "host" else "upgrade.session_note"
    return _t(key, latest=latest or "—", installed=n.get("installed") or "—",
              host=(n.get("route") or {}).get("host") or "—")
