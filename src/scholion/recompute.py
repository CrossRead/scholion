"""Recompute after an update: run what the releases ask, one step at a time, where a person can see it.

`scholion version` reads what every release between the data's version and this
build asks of the data, and until 13.09.2026 that was all: it printed commands,
and a person copied them into a terminal, filled in a folder by hand, and
watched a silent process for minutes. The genome steps were worse — they lived
only in the preparation guide — and after 0.5.1 grew the locus catalogue a
profile read 21 of its 92 radar panel positions as not read, with nothing in
the product saying why or offering to fix it.

**The plan.** `plan()` joins two sources. The journal: every «Run» lead whose
command this build can run is a step, merged when several releases ask for the
same command; every «By hand» lead is listed for a person to do. The data: a
genome whose catalogue positions were never genotyped, or were genotyped for a
smaller catalogue, gets the genotyping step whether or not a release named it —
a new person has the same gap as an old one. Each step is judged before anything
runs: `ready`, `needs_input` (a folder not named, an alignment not found — said
which), `not_applicable` (nothing of that kind was ever stored), `already_current`
(the file records a build that already did it), `not_run_here` (a command this
face does not run, printed for a person).

**The run.** Nothing starts without a confirmation (`--yes`, or the button after
its question). Steps run in order and a failed one stops the sequence, because a
later step may read what an earlier one writes. A profile file a step rewrites
is copied into the archive slot first. The version marker is recorded only
when every step finished and nothing is left for a person to do by hand.

**The progress is a file, not a variable.** `.recompute.json` beside the profile
holds each step's state, «item i of N», the item being read, the time spent and
an estimate of what is left from the items already done. The page and `scholion
recompute --status` read the same file, so the progress survives a reload, is
visible from a terminal while the page runs the job, and a job whose process died
is reported as interrupted rather than as running for ever. A stop is a second
file (`.recompute.stop`), honoured between items. What a stopped step leaves is
said as it is, not as it would be nicer: the genotyping replaces its file only
when every chromosome succeeded, so the previous file stays; a laboratory ingest
has already added the points of the forms it read, but records the forms as read
only at its end, so running it again reads the whole folder; and the copies made
before the run are in the archive either way.

Standard library only.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

JOB = ".recompute.json"
STOP = ".recompute.stop"
_WRITE_EVERY = 0.5          # seconds between progress writes; state changes are written at once


class Stopped(Exception):
    """A stop was requested; raised from a progress tick, outside any per-item `try`."""


# ------------------------------------------------------------------ the runners
def _call_labs(step, tick):
    from . import ingest_labs
    return ingest_labs.ingest(step["folder"], force=bool(step.get("force")), progress=tick)


def _call_provenance(step, tick):
    """The reverse check of the lab points against the forms — reads, rewrites
    only the coverage cache of the forms, and counts what disagrees."""
    from . import provenance
    return provenance.audit(refresh=True, lab_dir=step["folder"])


def _call_studies(step, tick):
    from . import ingest_studies
    return ingest_studies.ingest(step["folder"], force=bool(step.get("force")), progress=tick)


def _call_garmin(step, tick):
    from . import wearables
    return wearables.reingest(None, source="garmin", progress=tick)


def _call_acmg(step, tick):
    from . import acmg_scan
    return acmg_scan.scan(progress=tick)


def _call_coverage(step, tick):
    from . import coverage
    return coverage.measure(progress=tick, stop=_stop_requested)


def _call_sites(step, tick):
    from . import sites
    return sites.genotype(progress=tick, stop=_stop_requested)


#: What this build runs by itself, keyed by the command a journal lead names.
#: `folder` — the source folder the command reads (from `profile/sources.json`);
#: `profile_file` / `genome_file` — what it rewrites, and what must exist for a
#: release's «if … was ingested by an earlier version» to apply at all.
RUNNERS: Dict[str, Dict[str, Any]] = {
    "scholion ingest-labs": {"folder": "labs_docs", "profile_file": "labs.json", "call": _call_labs},
    "scholion ingest-studies": {"folder": "labs_docs", "profile_file": "studies.json",
                                "call": _call_studies},
    "scholion ingest-garmin": {"profile_file": "wearable_trends.json", "call": _call_garmin},
    "scholion acmg-scan": {"genome_file": "acmg_sf_hits.tsv", "call": _call_acmg},
    "scholion genotype-sites": {"genome_file": "loci_sites.vcf.gz", "call": _call_sites},
    "scholion coverage": {"profile_file": "callability.tsv", "call": _call_coverage},
    "scholion provenance": {"folder": "labs_docs", "profile_file": "labs.json", "call": _call_provenance},
}


def runner_key(command: str) -> Optional[str]:
    words = command.split()
    if words[:3] == ["python3", "-m", "scholion"]:
        words = ["scholion"] + words[3:]
    head = " ".join(words[:2])
    return head if head in RUNNERS else None


# ------------------------------------------------------------------ the files
def _profile() -> Path:
    from . import core
    return core.profile_dir()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


_last_write = [0.0]


def _write(job: Dict[str, Any], force: bool = False) -> None:
    now = time.monotonic()
    if not force and now - _last_write[0] < _WRITE_EVERY:
        return
    _last_write[0] = now
    path = _profile() / JOB
    if not path.parent.is_dir():
        return
    tmp = path.with_name(f"{JOB}.tmp-{os.getpid()}")
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, path)


_STILL_ACTIVE = 259            # GetExitCodeProcess: the process has not exited
_ERROR_ACCESS_DENIED = 5       # OpenProcess refused: the process exists, it is not ours


def _alive_windows(pid: int, kernel32: Any = None, last_error: Any = None) -> bool:
    """Whether a process is running, asked the way Windows answers it.

    Windows has no signal 0: `os.kill(pid, 0)` raises OSError for a process that
    is gone, and read as «alive» that left a stopped job «running» for ever. The
    exit code is asked instead; a process that exists but cannot be opened is
    alive. `kernel32` and `last_error` are passed in so the answer can be checked
    on any machine.
    """
    import ctypes
    kernel32 = kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
    last_error = last_error or ctypes.get_last_error
    handle = kernel32.OpenProcess(0x1000, False, pid)       # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return last_error() == _ERROR_ACCESS_DENIED
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _alive(pid: Any, windows: bool = os.name == "nt") -> bool:
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return True
    if windows:
        return _alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


def _stop_requested() -> bool:
    return (_profile() / STOP).exists()


def _clear_stop() -> None:
    try:
        (_profile() / STOP).unlink()
    except OSError:
        pass


def status() -> Dict[str, Any]:
    """The last job as its file describes it; a running job whose process is gone is `interrupted`."""
    try:
        job = json.loads((_profile() / JOB).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "none"}
    if not isinstance(job, dict):
        return {"status": "none"}
    if job.get("status") == "running" and job.get("pid") != os.getpid() and not _alive(job.get("pid")):
        job["status"] = "interrupted"
    return job


def stop() -> Dict[str, Any]:
    """Ask a running job to stop after the item it is reading."""
    if status().get("status") != "running":
        return {"ok": False, "reason": "not_running"}
    (_profile() / STOP).write_text(_now() + "\n", encoding="utf-8")
    return {"ok": True, "requested": True}


# ------------------------------------------------------------------ the plan
def _engine_of(path: Path) -> Optional[str]:
    try:
        meta = (json.loads(path.read_text(encoding="utf-8")) or {}).get("_meta") or {}
    except (OSError, ValueError, AttributeError):
        return None
    return meta.get("engine") if isinstance(meta, dict) else None


def _judge(step: Dict[str, Any]) -> None:
    from . import core, sites, updates
    spec = RUNNERS[step["key"]]
    step["detail"] = {}
    if step["key"] == "scholion coverage":
        from . import coverage as _cov
        st = step.get("data") or _cov.state()
        step["detail"] = {"genes": st.get("genes_wanted"), "held": st.get("genes_held")}
        if st.get("status") == "no_vcf":
            step["state"], step["why"] = "not_applicable", "no_vcf"
        elif st.get("status") == "current":
            step["state"], step["why"] = "already_current", "coverage_current"
        elif st.get("status") == "unrecorded":
            # A table made before this build recorded what it covered cannot be
            # told from a current one, and is not asked to be rebuilt — the same
            # rule the genotyped positions follow.
            step["state"], step["why"] = "already_current", "coverage_current"
        elif st.get("refusal"):
            step["state"], step["why"] = "needs_input", st["refusal"]
        else:
            step["state"], step["why"] = "ready", "coverage_" + str(st.get("status"))
        return
    if step["key"] == "scholion genotype-sites":
        st = step.get("data") or sites.state()
        step["detail"] = {"positions": st.get("catalogue_positions"),
                          "held": st.get("positions_held"), "made": st.get("made")}
        if st.get("status") == "no_vcf":
            step["state"], step["why"] = "not_applicable", "no_vcf"
        elif st.get("status") in ("current", "unrecorded"):
            step["state"], step["why"] = "already_current", "sites_current"
        elif st.get("refusal"):
            step["state"], step["why"] = "needs_input", st["refusal"]
        else:
            step["state"], step["why"] = "ready", "sites_" + str(st.get("status"))
        return
    pf = spec.get("profile_file")
    if pf:
        path = core.profile_dir() / pf
        step["detail"]["file"] = pf
        if not path.is_file():
            step["state"], step["why"] = "not_applicable", "no_file"
            return
        engine = _engine_of(path)
        if engine and step["versions"] and all(
                updates.version_tuple(engine) >= updates.version_tuple(v) for v in step["versions"]):
            step["state"], step["why"] = "already_current", "written_by"
            step["detail"]["engine"] = engine
            return
    gf = spec.get("genome_file")
    if gf and not any((b / gf).exists() for b in core.genome_bases()):
        step["state"], step["why"] = "not_applicable", "no_file"
        step["detail"]["file"] = gf
        return
    if step["key"] == "scholion acmg-scan":
        # The scan refuses without the published ClinVar VCF; said here, before
        # anything runs, rather than as a failed step after the ones before it.
        from .coverage import clinvar_path
        if clinvar_path() is None:
            step["state"], step["why"] = "needs_input", "no_clinvar"
            return
    domain = spec.get("folder")
    if domain:
        folder = core.source_config().get(domain)
        step["detail"]["domain"] = domain
        if not folder or not Path(folder).expanduser().is_dir():
            step["state"], step["why"] = "needs_input", "no_folder"
            return
        step["folder"] = str(Path(folder).expanduser())
    step["state"], step["why"] = "ready", None


_UNSET = object()


def program_prefix(installed: Any = _UNSET) -> str:
    """How `scholion` has to be spelled on THIS machine: the word itself, or `python3 -m scholion`.

    Every command this product prints is written the way the project names it. On a
    machine where the package is installed but its console script is not on the PATH —
    a system Python on macOS, a virtual environment that was never activated — the word
    `scholion` is not one the shell knows, and a person who copies the line printed to
    them gets «command not found» instead of the step it promised (owner, 18.09.2026).
    The commands stay written as they are, in one spelling for every language; what is
    said, once, is how this machine spells them. `installed` is the answer of the PATH,
    passed in by the tests so a run does not depend on what the machine happens to have.
    """
    found = shutil.which("scholion") if installed is _UNSET else installed
    if found:
        return "scholion"
    python = os.path.basename(sys.executable or "") or "python3"
    return python + " -m scholion"


def plan(since: Optional[str] = None, text: Optional[str] = None) -> Dict[str, Any]:
    """What would run, what a person has to do, and why each of the rest does not apply."""
    from . import sites, updates
    now = updates.installed()
    base = since or updates.last_used()
    entries = updates.between(base, now, text) if base else []
    entries = sorted(entries, key=lambda e: updates.version_tuple(e["version"]))
    steps: List[Dict[str, Any]] = []
    by_key: Dict[str, Dict[str, Any]] = {}
    for e in entries:
        for a in e["actions"]:
            if a["manual"]:
                steps.append({"kind": "by_hand", "state": "by_hand", "versions": [e["version"]],
                              "conditions": [a["condition"]], "text": a["text"]})
                continue
            for command in a["commands"]:
                key = runner_key(command)
                if key is None:
                    steps.append({"kind": "command", "key": None, "command": command,
                                  "state": "not_run_here", "why": "not_runnable",
                                  "versions": [e["version"]], "conditions": [a["condition"]],
                                  "text": a["text"]})
                    continue
                force = "--force" in command.split()
                if key in by_key:
                    s = by_key[key]
                    s["versions"].append(e["version"])
                    s["conditions"].append(a["condition"])
                    s["force"] = s["force"] or force
                    continue
                s = {"kind": "command", "key": key, "force": force, "source": "journal",
                     "versions": [e["version"]], "conditions": [a["condition"]], "text": a["text"]}
                by_key[key] = s
                steps.append(s)
    from . import coverage as _cov
    try:
        cst = _cov.state()
    except Exception as exc:                                         # noqa: BLE001
        cst = {"status": "unknown", "error": type(exc).__name__}
    if cst.get("status") in ("missing", "older_than_panels"):
        c = by_key.get("scholion coverage")
        if c is None:
            c = {"kind": "command", "key": "scholion coverage", "force": False,
                 "source": "data", "versions": [], "conditions": [], "text": None}
            by_key[c["key"]] = c
            steps.append(c)
        c["data"] = cst
    try:
        st = sites.state()
    except Exception as exc:                                         # noqa: BLE001
        st = {"status": "unknown", "error": type(exc).__name__}
    if st.get("status") in ("missing", "older_than_catalogue"):
        s = by_key.get("scholion genotype-sites")
        if s is None:
            s = {"kind": "command", "key": "scholion genotype-sites", "force": False,
                 "source": "data", "versions": [], "conditions": [], "text": None}
            by_key[s["key"]] = s
            steps.append(s)
        s["data"] = st
    for s in steps:
        if s.get("key"):
            s["command"] = s["key"] + (" --force" if s.get("force") else "")
            _judge(s)
        s.pop("data", None)
    for i, s in enumerate(steps, 1):
        s["id"] = i
    count = lambda state: sum(1 for s in steps if s.get("state") == state)
    return {"installed": now, "since": base, "steps": steps,
            "ready": count("ready"), "needs_input": count("needs_input"),
            "by_hand": count("by_hand"), "not_run_here": count("not_run_here"),
            "job": status()}


# ------------------------------------------------------------------ the run
def _backup(step: Dict[str, Any], folder: Optional[Path]) -> Optional[Path]:
    """Copy what the step rewrites into the archive slot, once per job."""
    from . import core
    spec = RUNNERS[step["key"]]
    sources = []
    if spec.get("profile_file"):
        sources.append(core.profile_dir() / spec["profile_file"])
    if spec.get("genome_file"):
        sources += [b / spec["genome_file"] for b in core.genome_bases()]
    sources = [p for p in sources if p.is_file()]
    if not sources:
        return folder
    if folder is None:
        folder = core.archive_dir() / "recompute" / datetime.now().strftime("%Y%m%d-%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    for p in sources:
        shutil.copy2(p, folder / p.name)
    return folder


def _succeeded(key: str, res: Any) -> bool:
    if not isinstance(res, dict):
        return False
    if key == "scholion acmg-scan":
        return res.get("status") == "ok"
    if key == "scholion ingest-labs":
        return bool(res.get("ok")) and not res.get("errors")
    return bool(res.get("ok"))


def _summary(res: Any) -> Dict[str, Any]:
    if not isinstance(res, dict):
        return {}
    keep = ("files_seen", "files_processed", "errors", "positions", "chromosomes", "metrics",
            "status", "reason", "error", "message", "rows", "path")
    return {k: res[k] for k in keep if k in res and not isinstance(res[k], (dict,))}


def run(confirm: bool = False, since: Optional[str] = None, text: Optional[str] = None,
        calls: Optional[Dict[str, Callable]] = None,
        echo: Optional[Callable[[Dict[str, Any], int], None]] = None,
        claimed: bool = False) -> Dict[str, Any]:
    """Run every `ready` step in order; nothing starts without `confirm`."""
    from . import updates
    p = plan(since=since, text=text)
    ready = [s for s in p["steps"] if s.get("state") == "ready"]
    if not confirm:
        return {"ok": False, "started": False, "reason": "not_confirmed", "plan": p}
    if not claimed and p["job"].get("status") == "running":
        return {"ok": False, "started": False, "reason": "busy", "job": p["job"]}
    if not ready:
        return {"ok": False, "started": False, "reason": "nothing_ready", "plan": p}
    own_claim = None
    if not claimed:
        own_claim = _claim()
        if own_claim is None:
            return {"ok": False, "started": False, "reason": "busy", "job": status()}
    try:
        return _run_steps(p, ready, calls, echo)
    finally:
        _release(own_claim)


def _run_steps(p: Dict[str, Any], ready: List[Dict[str, Any]], calls: Optional[Dict[str, Callable]],
               echo: Optional[Callable[[Dict[str, Any], int], None]]) -> Dict[str, Any]:
    from . import updates
    _clear_stop()
    job: Dict[str, Any] = {
        "status": "running", "pid": os.getpid(), "started": _now(), "since": p["since"],
        "installed": p["installed"], "current": 0, "by_hand": p["by_hand"],
        "needs_input": p["needs_input"], "backup": None,
        "steps": [{"command": s["command"], "key": s["key"], "state": "waiting",
                   "done": 0, "total": None, "item": None} for s in ready]}
    _write(job, force=True)
    backup: Optional[Path] = None
    table = {k: v["call"] for k, v in RUNNERS.items()}
    table.update(calls or {})
    for i, step in enumerate(ready):
        js = job["steps"][i]
        job["current"] = i
        js.update(state="running", started=_now())
        t0 = time.monotonic()
        _write(job, force=True)

        def tick(done, total, item=None, _js=js, _t0=t0, _i=i):
            if _stop_requested():
                raise Stopped()
            elapsed = time.monotonic() - _t0
            _js.update(done=int(done), total=int(total) if total else None, item=item,
                       elapsed=round(elapsed, 1))
            _js["left"] = (round(elapsed / done * (total - done), 1)
                           if done and total and done < total else None)
            _write(job)
            if echo is not None:
                echo(job, _i)

        try:
            backup = _backup(step, backup)
            job["backup"] = str(backup) if backup else None
            res = table[step["key"]](step, tick)
            js["state"] = "done" if _succeeded(step["key"], res) else "failed"
            js["summary"] = _summary(res)
            if js["state"] == "done" and js.get("total"):
                # A loader ticks as each item STARTS, so its last tick says «N−1 of
                # N»; a finished step is shown as finished.
                js["done"], js["item"] = js["total"], None
        except Stopped:
            js["state"] = "stopped"
        except Exception as exc:                                     # noqa: BLE001
            js["state"] = "failed"
            js["summary"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        js["finished"] = _now()
        js["elapsed"] = round(time.monotonic() - t0, 1)
        js["left"] = None
        _write(job, force=True)
        if echo is not None:
            echo(job, i)
        if js["state"] != "done":
            break
    states = [x["state"] for x in job["steps"]]
    job["status"] = ("finished" if all(x == "done" for x in states)
                     else "stopped" if "stopped" in states else "failed")
    job["finished"] = _now()
    if job["status"] == "finished" and not p["by_hand"] and not p["needs_input"]:
        if p["since"]:
            job["recorded"] = updates.mark_seen().get("recorded")
        else:
            # Data that never recorded its version had no releases planned for
            # it: recording the version now would claim those steps were done.
            job["not_recorded"] = "since_unknown"
    _write(job, force=True)
    _clear_stop()
    return {"ok": job["status"] == "finished", "started": True, "job": job}


CLAIM = ".recompute.claim"


def _claim() -> Optional[Path]:
    """Take the job atomically, or None when somebody else holds it.

    Reading the job file and then writing «running» into it let two starters —
    the page's button and `recompute --yes` in a terminal — both see «not
    running» and both run the same steps. The claim is a file created with
    O_EXCL; a claim whose owner is gone is taken over.
    """
    path = _profile() / CLAIM
    if not path.parent.is_dir():
        return None
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            try:
                owner = int(path.read_text(encoding="utf-8").strip() or 0)
            except (OSError, ValueError):
                owner = 0
            if owner and _alive(owner):
                return None
            try:
                path.unlink()
            except OSError:
                return None
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        return path
    return None


def _release(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        path.unlink()
    except OSError:
        pass


def _run_claimed(since: Optional[str], claim: Optional[Path]) -> None:
    """The thread's body: whatever `run` returns or raises, the job file ends in a
    terminal state and the claim is released. `run` can return before writing
    anything — the plan changed between the check and the start — and a job file
    left at «running» by a process that is still alive (the page's server) was
    read as busy until the server restarted."""
    try:
        res = run(confirm=True, since=since, claimed=True)
        if not res.get("started"):
            _write({"status": "failed", "pid": os.getpid(), "finished": _now(),
                    "reason": res.get("reason") or "not_started", "steps": []}, force=True)
    except Exception as exc:                                        # noqa: BLE001
        _write({"status": "failed", "pid": os.getpid(), "finished": _now(),
                "reason": f"{type(exc).__name__}: {exc}"[:300], "steps": []}, force=True)
    finally:
        _release(claim)


def per_call_host() -> Optional[str]:
    """The host that runs this package in a fresh process for every call, if any.

    Under such a host (the Ouroboros Hub) the process ends with the call, and a
    step started on a thread dies with it: the next call finds the job
    interrupted, nothing finished (OuroborosHub review, 22.09.2026). The plan is
    still answered there; the run is not started."""
    return (os.environ.get("SCHOLION_MANAGED_BY") or "").strip() or None


def start_in_background(since: Optional[str] = None) -> Dict[str, Any]:
    """For the page: claim the job, then run it on a thread; the file carries the progress."""
    import threading
    host = per_call_host()
    if host:
        return {"started": False, "reason": "per_call_host", "host": host, "plan": plan(since=since)}
    p = plan(since=since)
    if p["job"].get("status") == "running":
        return {"started": False, "reason": "busy", "job": p["job"]}
    ready = [s for s in p["steps"] if s.get("state") == "ready"]
    if not ready:
        return {"started": False, "reason": "nothing_ready", "plan": p}
    claim = _claim()
    if claim is None:
        return {"started": False, "reason": "busy", "job": status()}
    _write({"status": "running", "pid": os.getpid(), "started": _now(), "current": 0,
            "steps": [{"command": s["command"], "key": s["key"], "state": "waiting",
                       "done": 0, "total": None, "item": None} for s in ready]}, force=True)
    threading.Thread(target=_run_claimed, args=(since, claim), daemon=True).start()
    return {"started": True, "steps": len(ready)}
