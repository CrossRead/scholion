"""One person per data directory, many of them on one machine (task 192).

A **container** is one person's data directory: the five slots of
`core.DATA_SLOTS` (the external ones included, wherever `sources.json` puts
them) and `container.json` beside `profile/`. The file names the container by
a technical ID — `p-` and six characters, or a clinic's own number — and never
by the person: the table «ID ↔ person» is the clinic's and lives outside the
product (owner, 27.09.2026, R1). An optional label is printed only where the
person reading is at this machine: the command line and the local page.

A **workstation** is the machine's own file, `workstation.json` in the user
data directory (R8: a file, not an environment variable, so a plugin started
from an app finds it without `.zshrc`). It holds the root new containers are
made under, the registry of containers by ID and the active one. It exists
only once somebody has asked for a second person (`init --patient`); without
it every path resolves exactly as in 0.5 — the data directory is the one
container, and nothing talks about choosing (P1).

Resolution, most explicit first — the environment still beats everything, so
a test or a script keeps the directory it named:

  1. `SCHOLION_REPO_DIR` / `SCHOLION_PROFILE_DIR` — as before;
  2. `--patient <id>` — one command, the active container left as it is (R3);
  3. the workstation's active container;
  4. the data directory of 0.5 (the source tree, or the user data directory).

**The integrity gate.** A command, a request, a session reads the container
that is active when it starts. If the active one changes under it — `use` in
another terminal while a long command runs — a write would land in the other
person's profile. `pinned()` records the container at the start; every profile
write passes `gate()`, which refuses when the container it would write to is
not the one that was read.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

WORKSTATION_FILE = "workstation.json"
CONTAINER_FILE = "container.json"
#: The version of the shape of both files.
FORM = 1
#: A clinic may give its own number; the product cannot check that it names nobody.
ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{3,32}$")
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"   # no 0/o, 1/l/i: an ID is read aloud
_NAMING_LOCK = threading.RLock()
_LAZY_NAMES: Dict[str, tuple] = {}


class ContainerError(Exception):
    """A refusal about which person's data a command may touch."""
    code = "container.error"

    def __init__(self, code: str, **fields: Any) -> None:
        self.code = code
        self.fields = fields
        super().__init__(self.message())

    def message(self) -> str:
        from .i18n import t
        return t(self.code, **self.fields)


# ── the workstation ──────────────────────────────────────────────────────────
def workstation_path() -> Path:
    """`SCHOLION_WORKSTATION` for tests only (R8); otherwise the user data directory."""
    env = os.environ.get("SCHOLION_WORKSTATION")
    if env:
        return Path(env).expanduser()
    from . import core
    return core.user_data_dir() / WORKSTATION_FILE


def workstation() -> Dict[str, Any]:
    """The workstation file, or {} when there is none (one container, as in 0.5).

    A file that does not read is a refusal, not an empty dict: {} would mean
    «no workstation», and the data directory of 0.5 — container №1, somebody's
    data — would answer in place of the one that was active."""
    path = workstation_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("containers"), dict):
            raise ValueError("invalid workstation schema")
        if not isinstance(data.get("active"), str) or not data["active"]:
            raise ValueError("missing active container")
        if any(not isinstance(k, str) or not isinstance(v, str)
               for k, v in data["containers"].items()):
            raise ValueError("invalid container registry")
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise ContainerError("container.workstation_unreadable", path=path,
                             error=type(exc).__name__) from exc
    return data


def _write_workstation(data: Dict[str, Any]) -> None:
    from . import core
    data = dict(data)
    data["_meta"] = {"form": FORM, "shape": "root: where new containers are made; containers: "
                     "ID -> folder; active: the ID every command reads unless told otherwise"}
    path = workstation_path()
    core.mkdir_private(path.parent)
    core.write_json(path, data)


def legacy_dir() -> Path:
    """The data directory as 0.5 resolved it — container №1 on an existing install."""
    from . import core
    src = core._source_tree_root()
    return src if src is not None else core.user_data_dir()


def explicit_environment() -> bool:
    """A test or a script named the directory itself; no workstation is consulted."""
    return bool(os.environ.get("SCHOLION_REPO_DIR") or os.environ.get("SCHOLION_PROFILE_DIR"))


def registry() -> Dict[str, Path]:
    """Every container this workstation knows: the recorded ones, and any folder
    under the root that carries a `container.json` (a container copied in by hand)."""
    ws = workstation()
    out = {cid: Path(p).expanduser() for cid, p in (ws.get("containers") or {}).items()
           if isinstance(cid, str) and isinstance(p, str)}
    root = ws.get("root")
    if isinstance(root, str) and root:
        base = Path(root).expanduser()
        if base.is_dir():
            for d in sorted(base.iterdir()):
                cid = (read(d) or {}).get("id")
                if isinstance(cid, str) and cid not in out:
                    out[cid] = d
    return out


def path_of(cid: str) -> Path:
    found = registry().get(cid)
    if found is None:
        raise ContainerError("container.unknown", id=cid)
    if not found.is_dir():
        raise ContainerError("container.missing", id=cid, path=found)
    if (read(found) or {}).get("id") != cid:
        raise ContainerError("container.identity_unreadable", error="registry ID mismatch")
    if (read(found) or {}).get("lifecycle") == "erasing":
        raise ContainerError("container.lifecycle_pending", id=cid)
    return found


# ── which container this call reads ─────────────────────────────────────────
#: `--patient` for one command. Process-wide, set by the command line only.
_ONE_COMMAND: Dict[str, Optional[str]] = {"id": None}


def for_one_command(cid: Optional[str]) -> None:
    """`--patient <id>`: this command reads that container; the active one stays."""
    if cid is not None:
        path_of(cid)
    _ONE_COMMAND["id"] = cid


def active_dir() -> Optional[Path]:
    """The folder of the container this call reads, or None for the 0.5 data directory."""
    if explicit_environment():
        return None
    if _ONE_COMMAND["id"]:
        return path_of(_ONE_COMMAND["id"])
    cid = workstation().get("active")
    if not cid:
        return None
    # An active ID whose folder is gone is refused. Falling back to the 0.5 data
    # directory would answer with container №1 — another person — in its place.
    return path_of(cid)


def home() -> Path:
    """The folder `container.json` lives in: the parent of the profile slot, so a
    profile named by `SCHOLION_PROFILE_DIR` carries its identity with it."""
    from . import core
    return core.profile_dir().parent


def read(folder: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """`container.json` of a folder, or None when it has none yet."""
    path = Path(folder if folder is not None else home()) / CONTAINER_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise ContainerError("container.identity_unreadable", error=type(exc).__name__) from exc
    if not isinstance(data, dict) or not isinstance(data.get("id"), str) or not ID_PATTERN.fullmatch(data["id"]):
        raise ContainerError("container.identity_unreadable", error="invalid container schema")
    return data


def identity() -> Dict[str, Any]:
    """{id, path} of the container this call reads; `id` is None before its first write."""
    # Deliberately bypass bound paths: the gate compares the live selection
    # with the context captured when the operation began.
    profile = os.environ.get("SCHOLION_PROFILE_DIR")
    repo = os.environ.get("SCHOLION_REPO_DIR")
    folder = (Path(profile).expanduser().resolve().parent if profile else
              Path(repo).expanduser().resolve() if repo else
              (active_dir() or legacy_dir()).resolve())
    root = Path(repo).expanduser().resolve() if repo else (
        legacy_dir().resolve() if profile else folder)
    record = read(folder) or {}
    if record.get("lifecycle") == "erasing":
        raise ContainerError("container.lifecycle_pending", id=record.get("id"))
    return {"id": record.get("id"), "path": str(folder),
            "repo": str(root), "profile": str(Path(profile).expanduser().resolve()
                                              if profile else root / "profile")}


def new_id(taken: Optional[set] = None) -> str:
    taken = taken or set()
    while True:
        cid = "p-" + "".join(secrets.choice(_ALPHABET) for _ in range(6))
        if cid not in taken:
            return cid


def _record(cid: str, label: Optional[str]) -> Dict[str, Any]:
    from . import __version__
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    rec: Dict[str, Any] = {"_meta": {"form": FORM, "shape": "the technical ID of this person's "
                                     "data; the table ID -> person is kept by the clinic"},
                           "id": cid, "created": now, "engine": __version__}
    if label:
        rec["label"] = label
    return rec


def ensure(folder: Optional[Path] = None) -> Dict[str, Any]:
    """Write `container.json` if the folder has none — lazily, at the first write
    into the profile, so an install that never asks for a second person gets one
    file more and nothing else. The engine that last wrote is kept current."""
    with _NAMING_LOCK:
        return _ensure(folder)


def _ensure(folder: Optional[Path]) -> Dict[str, Any]:
    from . import __version__, core
    folder = Path(folder if folder is not None else home())
    rec = read(folder)
    if rec and rec.get("id"):
        if rec.get("engine") != __version__:
            rec["engine"] = __version__
            core.write_json(folder / CONTAINER_FILE, rec)
        return rec
    ws = workstation() if not explicit_environment() else {}
    rec = _record(new_id(set((ws.get("containers") or {}))), None)
    core.mkdir_private(folder)
    core.write_json(folder / CONTAINER_FILE, rec)
    _LAZY_NAMES[str(folder.resolve())] = (rec["id"], time.monotonic())
    pin = getattr(_PIN, "value", None)
    if pin is not None and pin["path"] == str(folder.resolve()) and pin["id"] is None:
        pin["id"] = rec["id"]  # this operation performed the first, lazy naming
    return rec


# ── the integrity gate ───────────────────────────────────────────────────────
_PIN = threading.local()


def capture() -> Dict[str, Any]:
    """A portable context for this operation, including a background worker."""
    bound = getattr(_PIN, "value", None)
    if bound is not None:
        return dict(bound)
    with _NAMING_LOCK:
        value = identity()
        value["captured_at"] = time.monotonic()
    return value


def bound_path(slot: str) -> Optional[Path]:
    value = getattr(_PIN, "value", None)
    return Path(value[slot]) if value is not None and slot in value else None


@contextlib.contextmanager
def pinned(value: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
    """Record which container this command, request or session reads — the one
    active now, or `value` when an agent's conversation was pinned earlier."""
    outer = getattr(_PIN, "value", None)
    if outer is None:
        _PIN.value = value if value is not None else capture()
    try:
        yield _PIN.value
    finally:
        if outer is None:
            _PIN.value = None


def in_use() -> bool:
    """Whether this machine holds several people: a workstation, not overridden."""
    return not explicit_environment() and bool(workstation())


def named() -> Dict[str, Any]:
    """What an answer carries about whose it is: the ID and never the label (R1).
    Everything a tool returns reaches the model's provider."""
    gate()
    return {"id": (getattr(_PIN, "value", None) or identity())["id"]}


class AgentPin:
    """The container an agent's conversation is fixed to (R2).

    A model's context is a cache nothing can clear: after `use`, a conversation
    that goes on would mix two people in one answer. So it is not cleared — it
    is refused. The pin is taken at the start of the conversation (the MCP
    handshake, or the first call in a process); every call after a switch is
    refused with both IDs and no data of the new person. A legacy or explicitly
    selected profile is pinned too: a workstation may be created later."""

    def __init__(self) -> None:
        self.value: Optional[Dict[str, Any]] = None

    def take(self) -> None:
        if self.value is None:
            self.value = capture()

    def check(self) -> Optional[Dict[str, Any]]:
        """The pin, after refusing a call that would read another person."""
        if self.value is None:
            self.take()
            return self.value
        now = identity()
        if not _same_identity(self.value):
            raise ContainerError("container.changed_session",
                                 was=self.value["id"] or "?", now=now["id"] or "?")
        return self.value

    def reset(self) -> None:
        self.value = None


def gate() -> None:
    """Refuse a write into a container other than the one that was read."""
    pin = getattr(_PIN, "value", None)
    if pin is None:
        return
    now = identity()
    if not _same_identity(pin):
        raise ContainerError("container.changed", was=pin["id"] or pin["path"],
                             now=now["id"] or now["path"])


def _same_identity(pin: Dict[str, Any]) -> bool:
    with _NAMING_LOCK:
        now = identity()
        if any(now[k] != pin.get(k) for k in ("path", "profile", "repo")):
            return False
        if now["id"] == pin["id"]:
            return True
        # Another thread may have performed this unchanged profile's first
        # write. Accept only a naming event witnessed in this process AFTER
        # capture; an arbitrary ID copied into an unnamed folder is refused.
        event = _LAZY_NAMES.get(pin["path"])
        if (pin["id"] is None and event and event[0] == now["id"]
                and event[1] >= pin.get("captured_at", float("inf"))):
            pin["id"] = now["id"]
            return True
        return False


def on_profile_write() -> None:
    """Called by `core.write_json` before every write into the profile slot."""
    gate()
    ensure()


# ── what a person does at the workstation ───────────────────────────────────
def _modified(folder: Path) -> Optional[str]:
    try:
        stamps = [p.stat().st_mtime for p in (folder / "profile").glob("*.json")]
    except OSError:
        stamps = []
    return time.strftime("%Y-%m-%d", time.localtime(max(stamps))) if stamps else None


def listing() -> Dict[str, Any]:
    """`patients`: every container, and which one is active."""
    ws = {} if explicit_environment() else workstation()
    active = ws.get("active")
    rows: List[Dict[str, Any]] = []
    for cid, folder in sorted(registry().items()) if ws else []:
        rec = read(folder) or {}
        rows.append({"id": cid, "label": rec.get("label"), "path": str(folder),
                     "exists": folder.is_dir(), "engine": rec.get("engine"),
                     "modified": _modified(folder), "active": cid == active})
    if not rows:
        # One container: the data directory in use. P1 — no choice is offered.
        me = identity()
        rows.append({"id": me["id"], "label": (read() or {}).get("label"), "path": me["path"],
                     "exists": True, "engine": (read() or {}).get("engine"),
                     "modified": _modified(Path(me["path"])), "active": True})
    return {"workstation": str(workstation_path()) if ws else None,
            "root": ws.get("root"), "containers": rows,
            "explicit_environment": explicit_environment()}


def use(cid: str, *, surface: str = 'cli-script') -> Dict[str, Any]:
    """`use <id>`: the active container becomes this one. A person's act (P4)."""
    from .lifecycle import _workstation_lock
    with _workstation_lock():
        return _use(cid, surface)


def _use(cid: str, surface: str) -> Dict[str, Any]:
    if explicit_environment():
        raise ContainerError("container.env_wins")
    if not workstation():
        raise ContainerError("container.no_workstation")
    folder = path_of(cid)
    from .lifecycle import record
    record(cid, 'use', surface)
    ws = workstation()
    was = ws.get("active")
    _write_workstation({**ws, "active": cid})
    from . import core
    core.reset_cache()
    rec = read(folder) or {}
    return {"ok": True, "id": cid, "label": rec.get("label"), "path": str(folder), "was": was}


def default_root() -> Path:
    from . import core
    return core.user_data_dir() / "patients"


def create(cid: Optional[str] = None, label: Optional[str] = None,
           root: Optional[str] = None, *, surface: str = 'cli-script') -> Dict[str, Any]:
    """`init --patient`: a new container under the root.

    The first call makes the workstation. The data directory in use until then
    becomes container №1 where it lies — nothing is moved — if it holds a
    profile; it stays active, because switching the person is `use`, not a side
    effect of creating another one."""
    from .lifecycle import _workstation_lock
    with _workstation_lock():
        result = _create(cid, label, root)
        from .lifecycle import record
        record(result['id'], 'create', surface)
        return result


def _create(cid: Optional[str], label: Optional[str], root: Optional[str]) -> Dict[str, Any]:
    if explicit_environment():
        raise ContainerError("container.env_wins")
    if cid is not None and not ID_PATTERN.match(cid):
        raise ContainerError("container.bad_id", id=cid)
    own = cid is not None
    ws = workstation()
    first = not ws
    known = registry() if ws else {}
    adopted = None
    if first:
        ws = {"root": str(Path(root).expanduser().resolve() if root else default_root()),
              "containers": {}}
        legacy = legacy_dir()
        if any((legacy / "profile").glob("*.json")):
            rec = ensure(legacy)
            ws["containers"][rec["id"]] = str(legacy)
            ws["active"] = rec["id"]
            known = {rec["id"]: legacy}
            adopted = rec["id"]
    elif root:
        raise ContainerError("container.root_is_set", root=ws.get("root"))
    if cid is not None and cid in known:
        raise ContainerError("container.id_taken", id=cid)
    cid = cid or new_id(set(known))
    folder = Path(ws["root"]).expanduser() / cid
    if folder.exists() and any(folder.iterdir()):
        raise ContainerError("container.folder_taken", path=folder)
    from . import core
    core.mkdir_private(folder)
    rec = _record(cid, label)
    core.write_json(folder / CONTAINER_FILE, rec)
    ws["containers"] = {**(ws.get("containers") or {}), cid: str(folder)}
    ws.setdefault("active", None)
    if not ws["active"]:
        ws["active"] = cid
    _write_workstation(ws)
    return {"ok": True, "id": cid, "label": label, "path": str(folder), "first": first,
            "adopted": adopted, "active": ws["active"], "own_id": own}
