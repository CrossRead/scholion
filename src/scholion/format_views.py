"""The pages that combine layers: overview, radar, focus, brief, goals, lifestyle.

Split out of `format.py`; every face still calls these names through `format`,
which re-exports them."""
from __future__ import annotations

from typing import Any, Dict, List, Optional  # noqa: F401

from .i18n import plural as _plural, t as _t  # noqa: F401
from .format_primitives import _PRIO_ICON, _flag_icon, _n
from .test_proposals import test_basis_text
from .goal_basis import goal_basis_text
from .clinical_claims import basis_lines


def lifestyle_report(r: Dict[str, Any]) -> str:
    """Lifestyle (wearable devices): year-by-year trends + a workout summary."""
    ms = r.get("metrics", [])
    if not ms:
        return _t("lifestyle.empty")
    fs = r.get("fitness_score")
    lines = [_t("lifestyle.title")
             + (" · " + _t("lifestyle.fitness_score", score=fs) if fs is not None else ""), "", _t('clinical.display_limit'), ""]
    icon = {"ok": "🟢", "warn": "🟠", "bad": "🔴", "none": "•"}
    for m in ms:
        t = m.get("trend")
        tr = f" · {m['first_date']}→{m['date']}: {_n(m['first'])}→{_n(m['value'])}" if m.get("first_date") != m.get("date") else ""
        improv = ""
        if m.get("improving") is True:
            improv = f" ({_t('lifestyle.improving')})"
        elif m.get("improving") is False:
            improv = f" ({_t('lifestyle.worsening')})"
        # The break in the series is named out loud: otherwise "from 2022-01" reads as
        # "there was no data before then", while there is data, it is not comparable.
        brk = (" · " + _t("lifestyle.comparable_from", date=m["comparable_from"])
               if m.get("comparable_from") else "")
        # What the latest month stands on. A month averaged over nineteen nights of
        # thirty-one is not the month, and the number alone cannot say so.
        cov = m.get("coverage") or {}
        cvr = (" · " + _t("lifestyle.coverage", n=cov["n"], days=cov["days"])
               if cov.get("n") and cov.get("days") and cov["n"] < cov["days"] else "")
        lines.append(f"{icon.get(m.get('status'),'•')} {m['label']}: **{_n(m['value'])} {m['unit']}**".rstrip()
                     + f" ({m['date']}){tr}{improv}{brk}{cvr}")
        lines.extend(basis_lines(m))
        # A movement the sample cannot tell from its own noise says so, with the
        # size of the difference that WOULD be visible. Printed under the metric
        # rather than folded into the arrow: it is the reason there is no arrow.
        if t and t.get("distinguishable") is False:
            lines.append("    " + _t("lifestyle.not_distinguishable",
                                     delta=_n(abs(t["delta"])), mdd=_n(t["mdd"]),
                                     unit=m.get("unit", "")).rstrip())
    wk = r.get("workouts", [])
    if wk:
        top = ", ".join(f"{x['type']} ({x['total']})" for x in wk[:6])
        lines.append("\n" + _t("lifestyle.workouts", items=top))
    lines.append(f"\n_{r.get('disclaimer','')}_")
    return "\n".join(lines)


def goal_report(r: Dict[str, Any]) -> str:
    """Goal for the metrics ("get the 2021–2022 shape back"): a now→goal table on live data."""
    if not r.get("available"):
        return r.get("message", _t("goal.not_set"))
    lines = [f"**🎯 {r.get('title', _t('goal.title_default'))}**"
             + (" · " + _t("goal.as_of", date=r["as_of"]) if r.get("as_of") else ""), ""]
    if r.get("headline"):
        lines.append(_t("goal.headline", text=r["headline"]))
        lines.append("")
    for entity in r.get('entities', []):
        origin = entity['origin']
        lines.append(f"• {entity['title']} [{entity['id']}]: "
                     + _t('goal.origin.line', origin=origin['label'], reason=origin.get('reason') or '—'))
        lines.append(f"  {entity['record']['file']} · {entity.get('target') if entity.get('target') is not None else '—'}")
    for p in r.get("peaks", []):
        lines.append(f"• {p.get('title')} · {p.get('year')}: {p.get('text')}")
    if r.get("peaks"):
        lines.append("")
    lines.append(_t("goal.targets_header"))
    for t in r.get("targets", []):
        lines.append(f"  {t['label']}: {t.get('now','—')} → {t.get('target','')} · "
                     + _t("goal.best", value=t.get("best", "")))
    lines.append("")
    lines.append(f"_{_t('goal.live_note')} {_t('goal.progress_rule')} {r.get('disclaimer','')}_")
    return "\n".join(lines)


def tests_report(r: Dict[str, Any]) -> str:
    if not r["suggestions"]:
        return _t("tests.none")
    pending = [s for s in r["suggestions"] if not s.get("done_recently") and "error" not in s]
    done = [s for s in r["suggestions"] if s.get("done_recently")]
    errs = [s for s in r["suggestions"] if "error" in s]
    lines = [_t("tests.header", n=len(pending)), ""]
    for s in pending:
        icon = _PRIO_ICON.get(s.get("priority"), "•")
        spec = (" · " + _t("tests.specialist", name=s["specialist"])
                if s.get("specialist") and s["specialist"] != "—" else "")
        lines.append(f"{icon} **{s['suggest']}**{spec}\n   " + _t("tests.why", text=s["why"]))
        lines.append(test_basis_text(s))
        if s.get("last_measured_unreadable"):
            lines.append("   " + _t("tests.last_date_unreadable",
                                    date=s["last_measured_unreadable"]))
    if not pending:
        lines.append(f"_{_t('tests.nothing_pending')}_")
    for s in errs:
        lines.append("⚠️ " + _t("tests.rule_error", id=s["id"], error=s["error"]))
    if done:
        lines.append("\n" + _t("tests.routine_header"))
        for s in done:
            lm = s.get("last_measured", ""); rm = s.get("recheck_months")
            lines.append("✓ " + _t("tests.done", name=s["suggest"], date=lm, months=rm))
            lines.append(test_basis_text(s))
    lines.append(f"\n_{r['disclaimer']}_")
    return "\n".join(lines)


def render_brief(d: dict) -> str:
    """Lifestyle brief — as text for the terminal."""
    if not d.get("available"):
        return _t("brief.not_compiled", reason=str(d.get("reason", "")))
    out = [d.get("title", _t("brief.title_default"))]
    if d.get("subtitle"):
        out.append(d["subtitle"])
    if d.get("compiled"):
        out.append(_t("brief.compiled", date=d["compiled"]))
    snap = d.get("snapshot") or []
    if snap:
        out.append("")
        for s in snap:
            out.append(f"  {s['label']:<24} {s['value']}"
                       + (f"   [{s['target']}]" if s.get("target") else ""))
    if d.get("needs_review"):
        out.append("")
        out.append("⚠ " + _t("brief.needs_review"))
        for s in d["stale_blocks"]:
            out.append("   · " + _t("brief.stale_block", title=s["title"],
                                    reviewed=s["reviewed"], newest=s["newest_data"]))
            if s.get("review_hint"):
                out.append("     " + _t("brief.review_hint", text=s["review_hint"]))
    for sec in d.get("sections", []):
        out.append("")
        out.append("── " + sec["title"].upper())
        if sec.get("lead"):
            out.append(sec["lead"])
        for b in sec["blocks"]:
            out.append("")
            out.append(("⚠ " if b.get("stale") else "") + b["title"])
            out.append(b["body"])
    if d.get("actions"):
        out.append("")
        out.append("── " + _t("brief.actions"))
        for i, a in enumerate(d["actions"], 1):
            out.append(f"  {i}. {a}")
    if d.get("dropped"):
        out.append("")
        out.append("── " + _t("brief.dropped"))
        for x in d["dropped"]:
            out.append(f"  · {x}")
    out.append("")
    out.append(d.get("disclaimer", ""))
    return "\n".join(out)


def render_focus(d: Dict[str, Any]) -> str:
    """Focus of attention — as text. Prescribes nothing: the levers are observations on one's own data."""
    if not d.get("available"):
        return d.get("reason") or _t("focus.not_set")
    m = d.get("metric") or {}
    out = ["🎯 " + _t("focus.title", title=d.get("title")),
           f"_{_t('focus.since', date=d.get('started'))}_", ""]
    if d.get('goal_entity'):
        origin = d['goal_entity']['origin']
        out.append(_t('goal.origin.line', origin=origin['label'], reason=origin.get('reason') or '—'))
    out.append(_t('clinical.recorded_focus'))
    if d.get("why"):
        out += [d["why"], ""]
    val = m.get("value") or "—"
    line = _t("focus.now", label=m.get("label"), value=val)
    if m.get("as_of"):
        line += f" ({_t('focus.as_of', date=m['as_of'])})"
    out.append(line)
    if m.get("mean_30") is not None:
        out.append("  · " + _t("focus.last_nights_export",
                               nights=_plural(m.get("nights_30") or 0, "count.nights"),
                               window_from=m.get("window_from"), window_to=m.get("window_to"),
                               value=m["mean_30"], unit=m.get("unit")))
    if m.get("mean_90") is not None:
        out.append("  · " + _t("focus.last_nights",
                               nights=_plural(m.get("nights_90") or 0, "count.nights"),
                               value=m["mean_90"], unit=m.get("unit")))
    if m.get("baseline") is not None:
        d_ = m.get("delta")
        out.append("  · " + _t("focus.baseline", value=m["baseline"],
                               note=m.get("baseline_note") or "")
                   + (" → " + _t("focus.shift", delta=f"{d_:+}", direction=m.get("direction"))
                      if d_ is not None else ""))
    if m.get("target") is not None:
        out.append("  · " + _t("focus.target", value=m["target"], unit=m.get("unit"),
                               note=m.get("target_note") or ""))
    out.append("")
    order = {"primary": 0, "secondary": 1, "hypothesis": 2}
    MARK = {"primary": "▶", "secondary": "·", "hypothesis": "?"}
    out.append(_t("focus.levers"))
    for lv in sorted(d.get("levers") or [], key=lambda x: order.get(x.get("status"), 3)):
        out.append(f"{MARK.get(lv.get('status'), '·')} "
                   + _t("focus.lever", title=lv.get("title"),
                        expected=lv.get("expected") or "—"))
        now = lv.get("now") or {}
        if now.get("text"):
            out.append("    " + _t("focus.lever_now", text=now["text"]))
    out.append("")
    j = (d.get("journal") or {}).get("state") or {}
    if j.get("text"):
        out += [_t("focus.journal") + " " + j["text"], ""]
    tr = d.get("tracks") or []
    if tr:
        out.append(_t("focus.tracks", n=len(tr)))
        for t_ in tr:
            out.append(f"  ▸ {t_.get('title')}  [{t_.get('owner')}]")
            if t_.get("state"):
                out.append(f"      {t_['state']}")
            for x in t_.get("closed_today") or []:
                out.append("      ✓ " + _t("focus.closed", text=x))
            for x in t_.get("next") or []:
                out.append(f"      → {x}")
        out.append("")
    ev = d.get("evidence") or {}
    if ev.get("count"):
        out.append(_t("focus.evidence", n=ev["count"]))
        for s in ev["studies"]:
            out.append(f"  · {s.get('date')} {s.get('kind')} — {s.get('conclusion')}")
            for a in s.get("answers") or []:
                out.append(f"      ✓ {a}")
            for a in s.get("does_not_answer") or []:
                out.append("      ✗ " + _t("focus.does_not_answer", text=a))
        if ev.get("open"):
            out.append(_t("focus.open"))
            for o in ev["open"]:
                out.append(f"  · {o.get('what')} — {o.get('note') or ''} [{o.get('from')}]")
        out.append("")
    if d.get("questions"):
        out.append(_t("focus.questions"))
        for q in d["questions"]:
            # A question can be written by hand as a string rather than as an object
            # {to, text}. It is shown as it is instead of taking the tab down.
            if isinstance(q, str):
                out.append(f"  · {q}")
            else:
                out.append(f"  · [{q.get('to')}] {q.get('text')}")
        out.append("")
    out.append("_" + (d.get("disclaimer") or "") + "_")
    return "\n".join(out)


def overview_report(r: Dict[str, Any]) -> str:
    """Main screen summary (the "Overview" tab).

    First report moved onto the message catalogue. Numbers are computed by the
    engine and only formatted here, so the language of a report changes how it
    reads and never what it says.
    """
    head = _t("overview.title") + " " + _t(
        "overview.counts", total=r.get("markers_total", 0), abnormal=r.get("abnormal_count", 0))
    # Only when it is worth saying. A line printed on every run is a line nobody
    # reads by the third one, and «this build is two days old» is not news.
    b = r.get("build") or {}
    if b.get("status") == "ageing":
        head += "\n" + _t("overview.build_ageing", version=b.get("installed") or "—",
                          released=b.get("released") or "—",
                          ago=_plural(int(b.get("days") or 0), "count.days"))
    if r.get("stale_abnormal_count"):
        head += _t("overview.stale_note", n=r["stale_abnormal_count"])
    from .format_prescription import caution_lines, control_lines
    out = caution_lines(r.get("regimen_cautions") or []) + [head + ".", ""]
    if r.get("overdue_controls"):
        out += [_t("treatment.overdue")] + control_lines(r["overdue_controls"]) + [""]

    for key, phrase in (("high_flags", "overview.high"), ("watch_flags", "overview.low")):
        items = r.get(key) or []
        if items:
            out.append(_t(phrase, n=len(items)))
            for m in items:
                out.append(f"  {_flag_icon(m.get('flag'))} {m.get('name')}: "
                           f"{m.get('value')} {m.get('unit', '')} ({m.get('date', '')})")
            out.append("")

    hs = r.get("pending_suggestions") or r.get("high_suggestions") or []
    line = _t("overview.suggestions", n=r.get("suggestions_count", 0))
    if r.get("high_suggestions"):
        line += _t("overview.suggestions_priority", n=len(r["high_suggestions"]))
    out.append(line + ".")
    for s in hs:
        out.append(f"  · {s.get('suggest')} — {s.get('why', '')}")
        out.append(test_basis_text(s))

    g = r.get("genome") or {}
    out.append("")
    state = _t("genome.connected" if g.get("ready") else "genome.not_connected")
    line = _t("overview.genome", state=state)
    if r.get("genome_gaps"):
        line += _t("overview.genome_gaps", genes=", ".join(r["genome_gaps"]))
    out.append(line)
    out.append(_t("overview.medications", n=r.get("medications_count", 0)))

    ls = r.get("lifestyle") or {}
    if ls.get("unread"):
        out.append(_t("overview.lifestyle_unread", reason=ls["unread"]))
    elif ls.get("watch"):
        out.append(_t("overview.lifestyle_watch", items=", ".join(
            f"{w['label']} {w['value']} {w.get('unit', '')}".strip() for w in ls["watch"])))

    out.append(f"\n_{r.get('disclaimer', '')}_")
    return "\n".join(out)


def radar_report(r: Dict[str, Any]) -> str:
    """Health index by body system (the same radar as in the web UI, but as text)."""
    out = [_t('clinical.display_limit'), '']
    if r.get("overall") is not None:
        line = _t("radar.overall", score=r["overall"])
        if r.get("prev_overall") is not None:
            d = r.get("overall_delta")
            sign = "+" if (d or 0) > 0 else ""
            line += (f" ({_t('radar.delta', delta=f'{sign}{d}')}"
                     f"{', ' + r['prev_date'] if r.get('prev_date') else ''}: {r['prev_overall']})")
        out += [line, ""]
    for dom in r.get("domains") or []:
        if dom.get("score") is None:
            out.append(f"  ⚪ {dom.get('label')}: {_t('common.no_data')}")
            continue
        icon = {"good": "🟢", "warning": "🟡", "critical": "🔴"}.get(dom.get("status"), "•")
        measured, total = dom.get("measured", dom.get("total", 0)), dom.get("total", 0)
        # A partly measured domain says so on the same line as its score. The score
        # is a mean over what was drawn; without the second number the reader takes
        # it for a statement about the whole system.
        counts = (_t("radar.domain_counts", abnormal=len(dom.get("abnormal") or []), total=total)
                  if measured >= total else
                  _t("radar.domain_partial", abnormal=len(dom.get("abnormal") or []),
                     measured=measured, total=total))
        out.append(f"  {icon} {dom.get('label')}: {dom['score']}/100 ({counts})")
        for m in (dom.get("abnormal") or [])[:5]:
            stale = f" · {_t('common.stale')}" if m.get("stale") else ""
            out.append(f"      {_flag_icon(m.get('flag'))} {m.get('name')}: "
                       f"{m.get('value')} {m.get('unit', '')} ({m.get('date', '')}){stale}")
    out.append(f"\n_{r.get('disclaimer', '')}_")
    return "\n".join(out)


def second_opinion_report(r: Dict[str, Any]) -> str:
    """The "second look" before a visit to the doctor (the "Second look" tab)."""
    from .format_prescription import caution_lines
    out = [_t("second_opinion.title"), ""] + caution_lines(r.get("regimen_cautions") or [])
    red = r.get("red_labs") or []
    out.append(_t("second_opinion.abnormal", n=len(red)) if red
               else _t("second_opinion.no_abnormal"))
    for m in red:
        out.append(f"  {_flag_icon(m.get('flag'))} {m.get('name')}: {m.get('value')} "
                   f"{m.get('unit', '')} ({m.get('date', '')})"
                   + (f" · {_t('second_opinion.stale')}" if m.get("stale") else ""))
    df = r.get("drug_flags") or []
    out += ["", _t("second_opinion.pgx", n=len(df)) if df
            else _t("second_opinion.pgx_none")]
    for d in df:
        out.append(f"  · {d.get('drug')} → {d.get('gene')} ({d.get('phenotype')}): "
                   f"{d.get('recommendation', '')}")
    sg = [s for s in (r.get("suggestions") or []) if not s.get("done_recently")]
    out += ["", _t("second_opinion.tests", n=len(sg)) if sg else _t("second_opinion.tests_none")]
    for s in sg:
        out.append(f"  · {s.get('suggest')} — {s.get('why', '')} [{s.get('priority', '')}]")
        out.append(test_basis_text(s))
    out.append(f"\n_{_t('second_opinion.note')}_")
    out.append(f"_{r.get('disclaimer', '')}_")
    return "\n".join(out)


def goal_suggest_report(r: Dict[str, Any]) -> str:
    """The proposals, each with the source of its number on the same line.

    The three lists are printed, not just the first: what was proposed, what is
    already met, and what nothing could be proposed for and why. A page of five
    suggestions with no account of the forty markers passed over reads as «these
    five are what matter», which is a different and false claim.
    """
    L = [f"**{_t('goalgen.title')}**", "", r.get("how_to_read", ""), ""]
    SRC = {"guideline": "goalgen.src.guideline", "personal_best": "goalgen.src.personal_best",
           "reference": "goalgen.src.reference"}
    if not r.get("proposals"):
        L.append(_t("goalgen.none"))
    for p in r.get("proposals", []):
        t = p.get("target") or {}
        now = p.get("now") or {}
        src = _t(SRC.get(p.get("proposed"), "goalgen.src.reference"))
        L.append(f"- **{p['name']}** {now.get('value', '—')} {p.get('unit','')} "
                 f"→ **{t.get('comparator','')}{t.get('value','')}**  _[{src}]_")
        cand = next((c for c in (p.get("candidates") or [])
                     if c.get("source") == p.get("proposed")), {})
        if cand.get("why"):
            L.append(f"  {cand['why']}")
        L.append(goal_basis_text(cand))
        if cand.get("citation"):
            c = cand["citation"]
            L.append(f"  — {c.get('body','')}, {c.get('document','')} ({c.get('year','')})"
                     + (f" {c['url']}" if c.get("url") else ""))
        if cand.get("assumed"):
            L.append(f"  ⚠ {cand['assumed'].get('note','')}")
        if p.get("caveat"):
            L.append(f"  ⚠ {p['caveat']}")
    if r.get("already_met"):
        L += ["", f"**{_t('goalgen.title')} — {_t('web.goalgen.reached')}**"]
        for a in r["already_met"]:
            met = ", ".join(f"{m['comparator']}{m['value']}" for m in a.get("met", []))
            L.append(f"- {a['name']} {(a.get('now') or {}).get('value','—')} "
                     f"{a.get('unit','')} — {met}")
            L.extend(goal_basis_text(c) for c in a.get('candidates') or [] if c.get('proposal_status') == 'held')
    if r.get("skipped"):
        L += ["", f"**{_t('goalgen.skipped_h')}**"]
        for skp in r["skipped"]:
            L.append(f"- {skp['name']} — {_t('goalgen.skip.' + skp['reason'])}")
            for cand in skp.get('candidates') or []:
                L.append('  ' + goal_basis_text(cand))
                if cand.get('proposal_status') == 'observation':
                    L.append('  ' + _t('goalgen.observed_value', value=cand.get('value'),
                                      unit=cand.get('unit') or '',
                                      date=(cand.get('observed') or {}).get('date') or '—'))
    if r.get("written"):
        w = r["written"]
        L += ["", _t("web.goalgen.saved", n=len(w.get("added") or [])), f"  {w.get('path','')}"]
    L += ["", f"_{r.get('disclaimer','')}_"]
    return "\n".join(L) + "\n"


def prevalence_report(r: Dict[str, Any]) -> str:
    """How often each flag fires, over what it actually looked at."""
    rows = r.get("rows") or []
    if not rows:
        return _t("prevalence.none") + "\n"
    L = [_t("prevalence.title"), "", _t("prevalence.how_to_read"), ""]
    for row in rows:
        L.append("· " + _t("prevalence.row", what=row["what"], hit=row["hit"],
                           looked_at=row["looked_at"], pct=round(row["rate"] * 100, 1)))
        if row.get("notable"):
            L.append("  " + _t("prevalence.notable", pct=round(row["rate"] * 100, 1)))
    return "\n".join(L) + "\n"


def brief_review_report(r: Dict[str, Any]) -> str:
    """What arrived since each brief block was read, and the request for the assistant."""
    if not r.get("ok"):
        return "✗ " + (r.get("message") or "")
    blocks = r.get("blocks") or []
    if not blocks:
        return _t("brief.review.nothing")
    from .engine.brief_review import _change_line
    L: List[str] = []
    for b in blocks:
        L += ["**" + _t("brief.review.title", title=b.get("title") or "—", block=b.get("id") or "—") + "**",
              _t("brief.review.reviewed", reviewed=b.get("reviewed") or "—", newest=b.get("newest_data") or "—")]
        changed = [c for c in b.get("markers") or [] if c.get("after")]
        L += ["  · " + _change_line(c) for c in changed] or ["  " + _t("brief.review.no_changes")]
        if b.get("review_hint"):
            L.append("  " + b["review_hint"])
        L += ["", _t("brief.review.request_h"), b.get("request") or "", ""]
    return "\n".join(L).rstrip()
