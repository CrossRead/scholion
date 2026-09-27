"""The build itself: version, update, recompute, sources, capabilities, redaction, skill copies.

Split out of `format.py`; every face still calls these names through `format`,
which re-exports them."""
from __future__ import annotations

from typing import Any, Dict, List, Optional  # noqa: F401

from .i18n import plural as _plural, t as _t  # noqa: F401
from .format_primitives import recompute_why, spelling_note


def redact_report(r: Dict[str, Any]) -> str:
    """The redacted text, with an honest account of what was and was not touched.

    The counts come before the text on purpose: a person who scrolls straight to
    the output and copies it has still seen the sentence saying the tool cannot
    tell a lab value from a version number.
    """
    if r.get("ok") is False:
        return f"⚠️ {r.get('error')}"
    L = [_t("redact.title"), ""]
    rep = r.get("replaced") or {}
    if rep:
        L.append(_t("redact.replaced",
                    what=", ".join(f"{k} × {v}" for k, v in sorted(rep.items()))))
    else:
        L.append(_t("redact.replaced_none"))
    if r.get("warning"):
        L.append("")
        L.append("⚠️ " + r["warning"])
    notices = r.get("notices") or {}
    if notices:
        L.append("")
        L.append(_t("redact.notices_head"))
        for kind, n in sorted(notices.items()):
            key = "redact.notice_" + kind
            L.append(f"- {_t(key, n=n)}")
    L.append("")
    L.append("_" + _t("redact.footer") + "_")
    if r.get("written_to"):
        L.append("")
        L.append(f"→ {r['written_to']}")
    else:
        L.append("")
        L.append("```")
        L.append(r.get("text", "").rstrip())
        L.append("```")
    return "\n".join(L)


def capabilities_report(r: Dict[str, Any]) -> str:
    """The manifest, for a reader who will act on it.

    Grouped by whether a command CHANGES anything, because that is the only
    distinction a caller must not get wrong. The rest it can discover by running
    the thing; this one it has to know before it runs anything.
    """
    L = [_t("capabilities.title", version=r.get("version", "?"), n=r.get("count", 0)), "",
         _t("capabilities.how_to_read"), ""]
    for group, key in (("reads_only", "capabilities.reads_h"),
                       ("writes", "capabilities.writes_h")):
        names = set(r.get(group) or [])
        if not names:
            continue
        L += [f"**{_t(key, n=len(names))}**", ""]
        for c in r.get("commands", []):
            if c["command"] not in names:
                continue
            faces = c.get("faces") or {}
            marks = []
            if c.get("kind") in ("authors", "transcribes"):
                marks.append(_t("capabilities.kind." + c["kind"]))
            if faces.get("web"):
                marks.append(_t("capabilities.face.web"))
            if faces.get("plugin"):
                marks.append(faces["plugin"])
            L.append(f"- `scholion {c['command']}` — {c['does']}"
                     + (f"  _[{', '.join(marks)}]_" if marks else ""))
        L.append("")
    return "\n".join(L) + "\n"


def sources_report(r: Dict[str, Any]) -> str:
    """Every external source, grouped by what kind of dependency it is.

    Three kinds, because they fail differently. A MIRROR is data carried in the
    build: it drifts silently when the upstream moves, so it needs an import
    path and a date. A PIPELINE source is a large download the genome track
    fetches through a script. A LIVE source is asked at query time and stored
    nowhere — it has no date because there is nothing to be stale.
    """
    L = [_t("sources.title"), "", _t("sources.how_to_read"), ""]
    order = [("mirror", "sources.kind.mirror"), ("pipeline", "sources.kind.pipeline"),
             ("live", "sources.kind.live")]
    for kind, key in order:
        group = [s for s in r.get("sources", []) if s.get("kind") == kind]
        if not group:
            continue
        L += [f"**{_t(key, n=len(group))}**", ""]
        for s in group:
            home = f" · {s['homepage']}" if s.get("homepage") else ""
            L.append(f"- **{s['title']}**{home}")
            L.append(f"  {_t('sources.license_line', license=s['license'])}")
            if s.get("cadence"):
                L.append(f"  {_t('sources.cadence', text=s['cadence'])}")
            for f in s.get("files", []):
                why = f.get("why_answers")
                if why == "bundled_newer":
                    # A refresh exists and is older than the copy this build carries:
                    # the bundled one answers, and the reader is told why their
                    # import is not the one in use.
                    mark = _t("sources.line_bundled_newer", local=f.get("local_stamp") or "—",
                              bundled=f.get("bundled_stamp") or "—")
                elif why == "unstamped":
                    mark = _t("sources.line_local_undated")
                elif f.get("local"):
                    mark = _t("sources.line_local", date=f.get("imported") or "—")
                elif f.get("bundled_stamp"):
                    stamp = str(f["bundled_stamp"])
                    stamp = stamp if len(stamp) <= 40 else stamp[:37] + "…"
                    mark = _t("sources.line_bundled_stamped", date=stamp)
                else:
                    mark = _t("sources.line_bundled")
                L.append(f"  `{f['file']}` — {mark}")
            if s.get("auto"):
                L.append(f"  `scholion sources --refresh --only {s['id']}`")
            else:
                if s.get("why_manual"):
                    L.append(f"  {_t(s['why_manual'])}")
                if s.get("command"):
                    L.append(f"  `{s['command']}`")
        L.append("")
    for res in r.get("results", []) or []:
        if res.get("skipped"):
            L.append(f"ℹ️ {res['source']}: {res.get('reason','')}")
            continue
        n_changed = len(res.get("changes") or [])
        L.append("✓ " + (_t("sources.refreshed", source=res["source"],
                            n=res.get("checked", 0), changed=n_changed)
                         if n_changed else
                         _t("sources.no_changes", source=res["source"])))
        for c in (res.get("changes") or [])[:20]:
            if c.get("field") == "function":
                L.append(f"  - {c['gene']} {c.get('star','')} `{c.get('rsid','')}`: "
                         f"{c.get('was')} → {c.get('now')} ({c.get('upstream')})")
            else:
                L.append(f"  - {c['gene']}: {c.get('field')} {c.get('was')} → {c.get('now')}")
    # Where each domain of the profile comes from — the block the web's source
    # badges read from `/api/sources` (parity, 12.09.2026): a person reading
    # the markdown sees what the page shows.
    data = r.get("data_sources") or {}
    if data:
        L += ["", _t("sources.data_h")]
        for key, row in data.items():
            if not isinstance(row, dict):
                continue
            L.append(f"· **{row.get('label') or key}** — {row.get('origin') or '—'}"
                     + (f" · {row.get('updated')}" if row.get("updated") else ""))
    return "\n".join(L) + "\n"


def version_report(r: Dict[str, Any]) -> str:
    """The build, its age, and what the releases since the data's version ask for."""
    b = r.get("build") or {}
    L = ["**" + _t("version.title", version=r.get("installed") or "—") + "**"]
    if b.get("released"):
        L.append(_t("version.released", released=b["released"],
                    ago=_plural(int(b.get("days") or 0), "count.days")))
    if r.get("last_used"):
        L.append(_t("version.last_used", version=r["last_used"]))
    else:
        L.append(_t("version.not_recorded"))
    pend = r.get("pending") or []
    if r.get("since") and (r.get("changed") or r.get("explicit_since")):
        if pend:
            L += ["", _t("version.since_head", since=r["since"],
                         entries=_plural(len(pend), "count.entries"))]
            for e in pend:
                L.append(f"  **v{e['version']}** ({e['date']})")
                for n in e.get("news") or []:
                    L.append("   ✦ " + _t("version.news", news=n))
                for a in e.get("actions") or []:
                    lead = (_t("version.by_hand", condition=a["condition"]) if a.get("manual")
                            else _t("version.run", commands=", ".join(f"`{c}`" for c in a["commands"]),
                                    condition=a["condition"]))
                    L.append("   · " + lead)
                    if a.get("text"):
                        L.append("     " + a["text"].replace("\n", "\n     "))
        else:
            L += ["", _t("version.nothing_since", since=r["since"])]
        if r.get("changed"):
            L += ["", _t("version.seen_hint")]
    wb = r.get("written_before") or {}
    if wb.get("files"):
        L += ["", _t("version.written_before_head")]
        from . import updates as _upd
        for f in wb["files"]:
            cmds = sorted({c for a in f["asks"] for c in a["commands"]})
            rel = sorted({a["version"] for a in f["asks"]}, key=_upd.version_tuple)
            L.append("   · " + _t("version.written_before_row", file=f["file"], engine=f["engine"],
                                  commands=", ".join(f"`{c}`" for c in cmds),
                                  releases=", ".join(rel)))
    if wb.get("unstamped"):
        L.append(_t("version.unstamped", files=", ".join(wb["unstamped"])))
    L += ["", _t("version.how_to_update")]
    note = spelling_note("version")
    if note:
        L += ["", note]
    return "\n".join(L)


def version_seen_report(r: Dict[str, Any]) -> str:
    if not r.get("ok"):
        return "✗ " + _t("version.seen_no_profile")
    return "✓ " + _t("version.seen_done", version=r.get("recorded") or "—")


def version_check_report(r: Dict[str, Any]) -> str:
    st = r.get("status")
    if st == "offline":
        return _t("version.check_offline")
    if st == "unreachable":
        return _t("version.check_unreachable", installed=r.get("installed") or "—")
    if st == "newer":
        return _t("version.check_newer", installed=r.get("installed") or "—",
                  latest=r.get("latest") or "—")
    return _t("version.check_current", installed=r.get("installed") or "—")


def update_report(n: Dict[str, Any]) -> str:
    """Whether a newer build is out and how it installs here — what a session opens with."""
    st = n.get("status")
    installed = n.get("installed") or "—"
    if st == "newer":
        lines = [_t("update.newer", latest=n.get("latest") or "—", installed=installed)]
    elif st == "current":
        lines = [_t("update.current", installed=installed)]
    elif st == "offline":
        lines = [_t("version.check_offline")]
    else:
        lines = [_t("version.check_unreachable", installed=installed)]
    if n.get("from_cache"):
        lines.append(_t("update.cached"))
    route = n.get("route") or {}
    command = " ".join(route.get("command") or [])
    if st == "newer":
        kind = route.get("kind")
        key = {"source": "update.how.source", "host": "update.how.host",
               "tree": "update.how.tree"}.get(kind, "update.how.install")
        lines.append(_t(key, command=command, host=route.get("host") or "—"))
    return "\n".join(lines)


def update_install_report(r: Dict[str, Any]) -> str:
    """What an install did — or, when it did nothing, why and what it would have run."""
    reason = r.get("reason")
    command = " ".join((r.get("route") or {}).get("command") or [])
    if reason == "installed":
        return _t("update.installed", before=r.get("installed") or "—", after=r.get("after") or "—")
    if reason == "already_current":
        return _t("update.already_current", installed=r.get("after") or r.get("installed") or "—")
    if reason == "not_confirmed":
        return _t("update.not_confirmed", command=command)
    if reason == "source_tree":
        return _t("update.how.source", command=command)
    if reason == "unpacked_tree":
        return _t("update.how.tree")
    if reason == "host_managed":
        return _t("update.how.host", host=(r.get("route") or {}).get("host") or "—")
    if reason == "offline":
        return _t("version.check_offline")
    code = r.get("code")
    head = _t("update.failed", code="—" if code is None else code, command=command)
    return head + ("\n" + r["tail"] if r.get("tail") else "")


def skill_install_report(r: Dict[str, Any]) -> str:
    if not r.get("ok"):
        return "✗ " + _t("skill.install.failed", path=r.get("path") or "—")
    key = {"installed": "skill.install.installed", "replaced": "skill.install.replaced",
           "unchanged": "skill.install.unchanged"}[r.get("action") or "installed"]
    return "✓ " + _t(key, path=r.get("path") or "—", version=r.get("version") or "—",
                     previous=r.get("previous") or "—")


def skill_copies_lines(copies: Any) -> str:
    """One line per copy of the skill entry that does not match this build."""
    lines = []
    for c in copies or []:
        icon = "🔴 " if c.get("severity") == "error" else "⚠️ "
        if c.get("status") == "older":
            lines.append(icon + _t("selfcheck.skill_copy_older", path=c["path"], version=c.get("version") or "—"))
        elif c.get("status") == "unmarked":
            lines.append(icon + _t("selfcheck.skill_copy_unmarked", path=c["path"]))
    return ("\n" + "\n".join(lines)) if lines else ""


# ---------------------------------------------------------------- recompute (task 183)
_RC_ICON = {"ready": "▶", "needs_input": "⚠️", "not_applicable": "·", "already_current": "✓",
            "not_run_here": "↪", "by_hand": "✋"}


_RC_JOB_ICON = {"waiting": "…", "running": "▶", "done": "✓", "failed": "✗", "stopped": "■"}


def _clock(seconds: Any) -> str:
    s = int(round(float(seconds or 0)))
    h, rest = divmod(s, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _recompute_step_line(s: Dict[str, Any]) -> str:
    if s.get("kind") == "by_hand":
        head = _t("recompute.step.by_hand", condition="; ".join(s.get("conditions") or []))
    else:
        head = f"`{s.get('command')}`"
    versions = ", ".join("v" + v for v in s.get("versions") or [])
    src = _t("recompute.from_releases", versions=versions) if versions else _t("recompute.from_data")
    why = recompute_why(s)
    line = (f"{_RC_ICON.get(s.get('state'), '·')} {head} — {_t('recompute.state.' + str(s.get('state')))}"
            + (f": {why}" if why else "") + f" ({src})")
    if s.get("text") and s.get("state") in ("by_hand", "not_run_here"):
        line += "\n     " + s["text"].replace("\n", "\n     ")
    return line


def recompute_plan_report(r: Dict[str, Any]) -> str:
    L = ["**" + _t("recompute.title") + "**"]
    if r.get("since"):
        L.append(_t("recompute.since", since=r["since"], installed=r.get("installed") or "—"))
    else:
        L.append(_t("recompute.since_unknown", installed=r.get("installed") or "—"))
    steps = r.get("steps") or []
    if not steps:
        L += ["", _t("recompute.nothing")]
        note = spelling_note("recompute --since 0.4.8")
        if note:
            L += ["", note]
        return "\n".join(L)
    L.append("")
    L += [_recompute_step_line(s) for s in steps]
    job = r.get("job") or {}
    if job.get("status") == "running":
        L += ["", _t("recompute.running_now")]
    elif r.get("ready"):
        L += ["", _t("recompute.hint_run", steps=_plural(int(r["ready"]), "count.steps"))]
    else:
        L += ["", _t("recompute.hint_nothing_ready")]
    note = spelling_note("recompute --yes")
    if note:
        L += ["", note]
    return "\n".join(L)


def recompute_progress_line(job: Dict[str, Any], i: int) -> str:
    steps = job.get("steps") or []
    s = steps[i] if 0 <= i < len(steps) else {}
    parts = [_t("recompute.progress.step", i=i + 1, n=len(steps), command=s.get("command") or "—")]
    total = s.get("total")
    if total:
        done = int(s.get("done") or 0)
        parts.append(_t("recompute.progress.percent", pct=min(100, round(100 * done / total)))
                     if total > 1000 else _t("recompute.progress.items", done=done, total=total))
    if s.get("item"):
        parts.append(str(s["item"]))
    if s.get("elapsed") is not None:
        parts.append(_t("recompute.progress.elapsed", time=_clock(s["elapsed"])))
    if s.get("left") is not None:
        parts.append(_t("recompute.progress.left", time=_clock(s["left"])))
    parts.append(_t("recompute.job_step." + str(s.get("state") or "waiting")))
    return " · ".join(parts)


def recompute_status_report(job: Dict[str, Any]) -> str:
    st = job.get("status") or "none"
    if st == "none":
        return _t("recompute.status.none")
    L = ["**" + _t("recompute.status." + st, started=job.get("started") or "—",
                   finished=job.get("finished") or "—") + "**"]
    for i, s in enumerate(job.get("steps") or []):
        L.append(f"{_RC_JOB_ICON.get(s.get('state'), '·')} " + recompute_progress_line(job, i))
        summary = s.get("summary") or {}
        err = summary.get("error") or summary.get("message") or summary.get("reason")
        if s.get("state") == "failed" and err:
            L.append("     " + str(err))
    if job.get("backup"):
        L.append(_t("recompute.backup", path=job["backup"]))
    if job.get("recorded"):
        L.append(_t("recompute.recorded", version=job["recorded"]))
    elif job.get("not_recorded") == "since_unknown":
        L.append(_t("recompute.not_recorded_since_unknown"))
    elif st == "finished" and (job.get("by_hand") or job.get("needs_input")):
        L.append(_t("recompute.remaining", by_hand=_plural(int(job.get("by_hand") or 0), "count.steps"),
                    needs_input=_plural(int(job.get("needs_input") or 0), "count.steps")))
    return "\n".join(L)


def recompute_run_report(r: Dict[str, Any]) -> str:
    if r.get("started"):
        return recompute_status_report(r.get("job") or {})
    reason = r.get("reason")
    if reason == "busy":
        return _t("recompute.busy")
    if reason == "per_call_host":
        return _t("recompute.per_call_host", host=r.get("host") or "—") + (
            "\n\n" + recompute_plan_report(r["plan"]) if r.get("plan") else "")
    head = _t("recompute.not_confirmed") if reason == "not_confirmed" else _t("recompute.nothing_ready")
    return head + ("\n\n" + recompute_plan_report(r["plan"]) if r.get("plan") else "")


def recompute_stop_report(r: Dict[str, Any]) -> str:
    return _t("recompute.stop_requested") if r.get("ok") else _t("recompute.stop_not_running")
