"""Laboratory values, targets, metrics and what reading a folder of forms did.

Split out of `format.py`; every face still calls these names through `format`,
which re-exports them."""
from __future__ import annotations

from typing import Any, Dict, List, Optional  # noqa: F401

from .i18n import plural as _plural, t as _t  # noqa: F401
from .format_primitives import _FLAG_ICON, _decision_suffix, _fmt_ref, _mark_icon, _near_suffix


def labs_report(r: Dict[str, Any]) -> str:
    near_n, cross_n = r.get("near_limit_count"), r.get("decision_crossed_count")
    near_s = ", " + _t("labs.near_more", n=near_n) if near_n else ""
    cross_s = "; " + _t("labs.crossed", n=cross_n) if cross_n else ""
    open_n = r.get("decision_unresolved_count")
    if open_n:
        cross_s += "; " + _t("labs.thresholds_not_comparable", n=open_n)
    head = _t("labs.header",
              abnormal=_plural(r["abnormal_count"], "count.abnormal"),
              total=_plural(r["count"], "count.markers_of"))
    lines = [f"{head}{near_s}{cross_s}.", ""]
    if near_s:
        # Say what «at the edge» rests on. A flat ten per cent is not an
        # analyte-specific reference change value, and the difference is an order
        # of magnitude for some markers.
        lines += [_t("labs.near_limit_is_flat"), ""]
    for m in r["markers"]:
        icon = _mark_icon(m)
        ref = _fmt_ref(m)
        val = f"{m['value']} {m['unit']}".strip()
        # Task 100. A date that did not come off the form is marked where the
        # date is shown, not only in the log of the ingest that stored it.
        _ds = m.get("date_source")
        _dmark = (" " + _t("labs.date_source_" + _ds)) if _ds in ("ordered", "filename") else ""
        line = f"{icon} {m['name']}: **{val}** ({m['date']}{_dmark}){ref}"
        for rep in m.get("repeats") or []:
            times = ", ".join(f"{p['at'] or '—'} {p['value']}" for p in rep["points"])
            line += "\n   " + _t("labs.same_day_repeat", day=rep["day"], points=times)
            if rep.get("context"):
                line += "\n   " + _t("labs.same_day_context", text=rep["context"])
            else:
                # The question IS the feature. Two numbers from one day mean nothing
                # until somebody says what stood between them; asking is the only way
                # the pair becomes a reading rather than a puzzle.
                line += "\n   " + _t("labs.same_day_ask")
        if m.get("proposed_rule"):
            line += "\n   " + _t("markers.proposed_no_flag", key=m["key"])
        if m.get("positions"):
            # The genetics of this marker (task 199 G): gene, rsID, level, the
            # direction the author expects; the state is on the system card.
            line += "\n   " + _t("labs.genetics_line", positions=", ".join(
                f"{p.get('gene')} {p.get('rsid')}" + (f" ({p.get('level')})" if p.get("level") else "")
                + (f" {_t('system.panel.dir.' + str(p['direction']))}" if p.get("direction") else "")
                + (f" — {p['system_label']}" if p.get("system_label") else "")
                for p in m["positions"]))
        if m.get("fasting_not_established"):
            ctx = next((r.get("context") for r in reversed(m.get("repeats") or [])
                        if r.get("context")), "")
            line += "\n   " + (_t("labs.fasting_after_event", text=ctx) if ctx
                                else _t("labs.condition_unknown"))
        if m.get("ref_reference_base"):
            # Say whose interval this is. A general population range answering
            # where the person's own form was silent is useful, and pretending it
            # came from their laboratory would be a stronger claim than the data
            # supports.
            line += " · " + _t("labs.ref_from_reference_base")
        if m.get("corridor_note"):
            line += "\n   " + m["corridor_note"]
        t = m.get("trend")
        if t:
            arrow = {"up": "↑", "down": "↓", "flat": "→"}[t["direction"]]
            pct = f" {t['pct']:+g}%" if t.get("pct") is not None else ""
            line += (" · " + _t("common.trend", arrow=arrow, pct=pct)
                     + f" ({t['from_date']}→{t['to_date']})")
            # The arrow is arithmetic and stays. What follows it is whether this
            # series has ever shown itself able to tell a change that size from
            # its own scatter — without which an arrow is read as a finding.
            if t.get("distinguishable") is False:
                line += " · " + _t("labs.below_own_scatter",
                                   pct=t["change_floor"]["rcv_pct"],
                                   pairs=t["change_floor"]["pairs"])
        if m.get("genome_link"):
            # The owner's own line about a marker, marked as such: free text
            # with no source, and until task 168 it printed in the same voice
            # as a curated sentence that had passed the gate.
            line += " · " + (_t("labs.owner_note", text=m["genome_link"])
                             if m.get("genome_link_kind") == "owner_note"
                             else _t("labs.genome_link", text=m["genome_link"]))
        line += _target_suffix(m)
        line += _near_suffix(m) + _decision_suffix(m)
        for mn in (m.get("method_notes") or []):
            line += "\n   _" + mn + "_"
        if m.get("note"):
            line += f" · _{m['note']}_"
        lines.append(line)
    lines.append(f"\n_{r['disclaimer']}_")
    return "\n".join(lines)


def target_spec(tg: Dict[str, Any]) -> str:
    """The figures of a target as one token: «1–2», «≤2», «≥1» or «16.7»."""
    lo, hi, one = tg.get("low"), tg.get("high"), tg.get("value")
    f = lambda x: f"{float(x):g}"          # noqa: E731 — one formatter, four branches
    if lo is not None and hi is not None:
        return _t("target.spec_range", low=f(lo), high=f(hi))
    if hi is not None:
        return _t("target.spec_max", high=f(hi))
    if lo is not None:
        return _t("target.spec_min", low=f(lo))
    if one is not None:
        return _t("target.spec_value", value=f(one))
    return ""


def _target_suffix(m: Dict[str, Any]) -> str:
    """The clinician's target beside the corridor, with who set it and when (task 170).

    The provenance is printed on the same line as the figures, every time: a
    target that appeared without an author would read as the product's own
    verdict, and the product has none — it prints what the person entered.
    The question below it is asked ONLY for a value the corridor calls normal:
    a value already flagged has the flag speaking for it, and two lines saying
    «look here» about one number is noise. It is a question, not an instruction.
    """
    tg = m.get("target")
    if not tg:
        return ""
    out = " · " + _t("target.beside", spec=target_spec(tg), set_by=tg.get("set_by", ""),
                     set_on=tg.get("set_on", ""))
    if tg.get("note"):
        out += f" ({tg['note']})"
    if m.get("outside_target") and m.get("flag") == "ok":
        side = _t("target.side_above" if tg.get("side") == "above" else "target.side_below")
        out += "\n   " + _t("target.discuss", side=side, spec=target_spec(tg),
                            set_by=tg.get("set_by", ""), set_on=tg.get("set_on", ""))
    return out


def targets_report(r: Dict[str, Any]) -> str:
    """`scholion target list`: every clinician's target beside its marker's value.

    Ends with the frame note rather than opening with it, and never omits it:
    a list of targets with «outside» beside half of them reads as a list of
    deficits unless the reader is told, in the same breath, that it is not one.
    """
    if not r.get("targets"):
        return _t("target.list_none")
    L = [_t("target.list_title", targets=_plural(r["count"], "count.targets")), ""]
    for tg in r["targets"]:
        unit = f" {tg['unit']}" if tg.get("unit") else ""
        line = "• " + _t("target.list_line", name=tg["name"], spec=target_spec(tg) + unit,
                         set_by=tg.get("set_by", ""), set_on=tg.get("set_on", ""))
        if tg.get("note"):
            line += f" _({tg['note']})_"
        cur = tg.get("current")
        if not cur:
            line += "\n   " + _t("target.now_none")
        else:
            now = _t("target.now", value=cur["value"], date=cur["date"])
            if tg.get("outside_target"):
                side = _t("target.side_above" if tg.get("side") == "above"
                          else "target.side_below")
                if tg.get("in_corridor"):
                    now += " — " + _t("target.discuss", side=side, spec=target_spec(tg),
                                      set_by=tg.get("set_by", ""), set_on=tg.get("set_on", ""))
                else:
                    now += " — " + _t("target.outside_and_flagged", side=side)
            elif tg.get("outside_target") is False:
                now += " — " + _t("target.within")
            line += "\n   " + now
        L.append(line)
    L += ["", "_" + _t("target.frame_note") + "_"]
    return "\n".join(L)


def metrics_report(r: Dict[str, Any]) -> str:
    """Personal health metrics: age, BMI, latest values, trends."""
    if r.get("status") != "ok":
        return f"⚠️ {r.get('message','')}"
    prof = r.get("profile", {})
    head = []
    if r.get("age") is not None:
        head.append(_t("metrics.age", value=r["age"]))
    if prof.get("height_cm"):
        head.append(_t("metrics.height", value=prof["height_cm"]))
    if r.get("bmi"):
        b = r["bmi"]
        head.append(_t("metrics.bmi", value=b["value"], category=b["category"]))
    lines = [_t("metrics.title") + (f" — {', '.join(head)}" if head else ""), ""]
    filled = [m for m in r.get("metrics", []) if m.get("value") is not None]
    if not filled:
        lines.append(f"_{_t('metrics.empty')} {_t('metrics.empty_hint')}_")
    for m in filled:
        icon = _FLAG_ICON.get(m.get("flag"), "•")
        tr = ""
        t = m.get("trend")
        if t:
            arrow = {"up": "↑", "down": "↓", "flat": "→"}[t["direction"]]
            pct = f" {t['pct']:+g}%" if t.get("pct") is not None else ""
            tr = " · " + _t("common.trend", arrow=arrow, pct=pct)
            if t.get("distinguishable") is False:
                tr += " · " + _t("labs.below_own_scatter",
                                 pct=t["change_floor"]["rcv_pct"],
                                 pairs=t["change_floor"]["pairs"])
        lines.append(f"{icon} {m['name']}: **{m['value']} {m.get('unit','')}**".rstrip() +
                     f" ({m.get('date','')}){tr}")
    lines.append(f"\n_{r.get('disclaimer','')}_")
    return "\n".join(lines)


def reconcile_report(r: Dict[str, Any]) -> str:
    """Audit report on the completeness of labs.json against the source PDFs."""
    if not r.get("ok"):
        return f"⚠️ {r.get('error')}"
    lines = [_t("reconcile.title"),
             _t("reconcile.folder", path=r["lab_dir"]),
             _t("reconcile.pdf_total", n=r["files_total"]) + " · "
             + _t("reconcile.pdf_non_lab", n=r["files_non_lab"]) + " · "
             + _t("reconcile.points_matched", n=r["covered_points"]) + " · "
             + _t("reconcile.markers_seen", n=len(r["markers_seen"])),
             ""]

    unread = r.get("unreadable", [])
    if unread:
        lines.append("🔴 " + _t("reconcile.unreadable", n=len(unread)))
        for u in unread:
            lines.append(f"   • {u['file']} — {u['reason']} "
                         f"({_plural(u['bytes'], 'count.bytes')})")
        lines.append("")
    else:
        lines.append("🟢 " + _t("reconcile.all_readable"))

    miss = r.get("missing", [])
    if miss:
        lines.append("\n🟡 " + _t("reconcile.missing", n=len(miss)))
        for m in miss:
            u = f" {m['unit']}" if m.get("unit") else ""
            lines.append(f"   • {m['marker']} {m['date']} = {m['value']}{u}  ← {m['file']} ({m['reason']})")
    else:
        lines.append("\n🟢 " + _t("reconcile.no_missing"))

    mm = r.get("mismatch", [])
    if mm:
        lines.append("\n🟠 " + _t("reconcile.mismatch", n=len(mm)))
        for m in mm:
            lines.append("   • " + _t("reconcile.mismatch_row", marker=m["marker"],
                                      date=m["date"], pdf=m["pdf"], profile=m["profile"])
                         + f"  ({m['file']})")

    lines.append(f"\n_{_t('reconcile.provenance', path=r.get('coverage_path'))} "
                 f"{_t('reconcile.read_only')} {_t('reconcile.how_to_fill')}_")
    return "\n".join(lines)


def markers_report(r: Dict[str, Any]) -> str:
    ms = r.get("markers") or []
    if not ms:
        return _t("markers.empty")
    out = [_t("markers.header", n=len(ms))]
    for m in ms:
        out.append(f"  · {m.get('name')} [{m.get('key')}] {m.get('unit', '')}"
                   f"{_fmt_ref(m)}".rstrip())
    out.append(f"\n_{_t('markers.note')}_")
    return "\n".join(out)


def fhir_report(r: Dict[str, Any]) -> str:
    """What the bundle gave, what it did not, and what was deliberately not taken."""
    if not r.get("ok"):
        return "❌ " + str(r.get("error", "")) + "\n"
    L = [_t("fhir.title", path=r.get("path", ""), observations=r.get("observations", 0))]
    added = r.get("added") or []
    if r.get("dry_run"):
        L.append(_t("fhir.dry_run",
                    results=_plural(len(r.get("points") or []), "count.results")))
    elif added:
        L.append(_t("fhir.added", n=len(added)))
    for p in (r.get("points") or []):
        mark = "·" if r.get("dry_run") else "✓"
        rng = ""
        if p.get("ref_low") is not None or p.get("ref_high") is not None:
            rng = f" [{p.get('ref_low')}–{p.get('ref_high')}]"
        L.append(f"  {mark} {p['key']} {p['value']:g} {p.get('unit') or ''} "
                 f"({p['date']}, LOINC {p['loinc']}){rng}")
    # The body measurements, counted apart from the laboratory points: they went
    # to a different layer, and a reader who sees one number cannot tell.
    n_metrics = len(r.get("metrics") or [])
    if n_metrics:
        L.append(_t("fhir.metrics_dry" if r.get("dry_run") else "fhir.metrics_taken",
                    n=len(r.get("added_metrics") or []) if not r.get("dry_run") else n_metrics))
    for ref in (r.get("refused") or []):
        L.append("  ✗ " + _t("fhir.refused", label=ref.get("label"), reason=ref.get("reason")))
    # The skipped ones are grouped by REASON rather than listed one by one: the
    # useful question is «what kind of thing did this bundle hold that we cannot
    # place», and the answer to that is a handful of lines, not fifty.
    groups: Dict[str, list] = {}
    for s in (r.get("skipped") or []):
        groups.setdefault(s["reason"], []).append(s)
    if groups:
        L += ["", _t("fhir.not_taken")]
        for reason, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            # The unplaced code is printed WITH the code, not only with its
            # label: «Calcium» is what somebody has to look up, «Calcium
            # (49765-1)» is what they can act on — and the code is the thing a
            # dictionary entry is keyed by. It was carried in the record all
            # along and stopped one line short of the screen.
            if reason in ("loinc_not_in_catalogue", "loinc_is_a_body_metric"):
                shown = sorted({f"{i['label']} ({i.get('detail') or '?'})" for i in items})
            else:
                shown = sorted({str(i["label"]) for i in items})
            names = ", ".join(shown[:6])
            L.append(f"  · {_t('fhir.reason.' + reason)} — {len(items)}: {names}")
    facts = r.get("profile_facts") or {}
    if facts:
        L += ["", _t("fhir.profile_facts",
                     facts=", ".join(f"{k}={v}" for k, v in sorted(facts.items())))]
    return "\n".join(L) + "\n"


def import_report(r: Dict[str, Any]) -> str:
    """The outcome of a CSV import, row by row where it went wrong.

    Every rejected row is printed with its number and its reason. «3 rows
    rejected» tells a person that something is wrong and not what, and the file
    they have to fix is in front of them — naming the row is the whole difference
    between a report and a notification.
    """
    if r.get("error") and not r.get("problems"):
        return f"⚠️ {r['error']}"
    L = []
    if r.get("problems"):
        L.append("⚠️ " + (r.get("error") or _t("write.failed")))
        L.append("")
        for p in r["problems"]:
            who = f" · {p['marker']}" if p.get("marker") else ""
            L.append(f"- {_t('import.row', row=p['row'])}{who}: {p['reason']}")
        return "\n".join(L)
    if r.get("dry_run"):
        L.append("✓ " + _t("import.dry_ok",
                            rows=_plural(r.get("accepted", 0), "count.rows")))
    else:
        L.append("✓ " + _t("import.written",
                            rows=_plural(r.get("written", 0), "count.rows")))
    if r.get("markers"):
        L.append("")
        L.append(_t("import.markers", markers=", ".join(r["markers"])))
    return "\n".join(L)


def write_result(r: Dict[str, Any]) -> str:
    """Result of a writing command. A refusal is printed in words, not silently.

    An erased demonstration is printed FIRST and on its own line. It is the
    largest thing that happened — a whole profile of a fictional person is gone
    — and folding it into the «marker: glucose; points: 3» tail would be the same
    class of quiet as the defect it comes from.
    """
    if r.get("ok") is False or r.get("error"):
        return f"⚠️ {r.get('error') or _t('write.failed')}"
    bits = [f"{k}: {v}" for k, v in r.items() if k not in ("ok",) and not isinstance(v, (dict, list))]
    line = "✓ " + _t("write.saved") + (" · " + "; ".join(bits) if bits else "") + "."
    claimed = r.get("claimed") or {}
    if claimed.get("message"):
        return "⚠️ " + claimed["message"] + "\n" + line
    return line


def draw_context_report(r: Dict[str, Any]) -> str:
    """What was recorded about a day that holds two draws."""
    if not r.get("ok"):
        return f"✗ {r.get('error', '')}"
    return (_t("labs.draw_context_saved", day=r["day"], context=r["context"],
               n=len(r["markers"])) + "\n")


def wearable_ingest_report(r: Dict[str, Any]) -> str:
    """What one device's export gave — and, when it matters, what it did not.

    Three things are printed that a count of metrics would hide: the device it
    was actually read as, the columns nothing was read from, and the metrics
    another device also reports. The last one is the reason this layer was
    rebuilt: two series under one name is a chart that lies quietly.
    """
    if not r.get("ok"):
        out = f"⚠️ {r.get('error')}"
        if r.get("candidate_hint"):
            out += "\n" + r["candidate_hint"]
        return out + "\n"
    lines = []
    if (r.get("claimed") or {}).get("message"):
        # First, and before the count: a demonstration profile has just gone.
        lines.append("⚠️ " + r["claimed"]["message"])
    lines.append(_t("wearables.done", device=r.get("source"), metrics=r.get("metrics"),
                    nights=r.get("nights"), preserved=r.get("preserved")))
    if r.get("range"):
        lines.append(f"  {r['range']}")
    if r.get("unrecognised_columns"):
        lines.append(_t("wearables.columns_unknown",
                        columns=", ".join(r["unrecognised_columns"])))
    if r.get("unreadable_files"):
        lines.append(_t("wearables.files_unreadable", n=len(r["unreadable_files"]),
                        files="; ".join(r["unreadable_files"])))
    if r.get("shared_metrics"):
        lines.append(_t("wearables.shared", metrics=", ".join(r["shared_metrics"])))
    # A hand-made decision about this series answers for itself out loud: what was
    # applied, what no longer matches anything, and what was not accepted and why.
    # A corrections file that quietly stops matching is one nobody can trust.
    for key, line in (("corrections_applied", "wearables.correction_applied"),
                      ("corrections_stale", "wearables.correction_stale"),
                      ("corrections_refused", "wearables.correction_refused")):
        for c in (r.get(key) or [])[:10]:
            lines.append(_t(line, metric=c.get("metric"), month=c.get("month"),
                            action=c.get("action"), why=c.get("why") or "",
                            refused=c.get("refused") or ""))
    if r.get("backup"):
        lines.append(_t("ingest.garmin_backup", path=r["backup"]).strip())
    return "\n".join(lines) + "\n"


def profile_set_report(r: Dict[str, Any]) -> str:
    if not r.get("ok"):
        return f"✗ {r.get('error', '')}"
    return _t("profile.recorded", fields=", ".join(
        f"{k} = {v}" for k, v in sorted((r.get("profile") or r.get("updated") or {}).items()))) + "\n"


def ingest_labs_report(r: Dict[str, Any]) -> str:
    """What was read, and — by name — what was not.

    The counts alone were what let nineteen files out of forty-seven go past in
    silence: `skipped` meant «unchanged since last run», and the three paths that
    give up on a file touched no counter at all. A file that produced nothing now
    says which file, why, and — when the reason is that no row matched the
    dictionary — which printed labels nobody could place.
    """
    if not r.get("ok"):
        return f"⚠️ {r.get('error', '')}"
    L = [_t("ingest.labs_done", files=r.get("files_processed", 0),
            points=r.get("points_added", 0), skipped=r.get("skipped", 0))]
    missed = r.get("not_ingested") or []
    if missed:
        L += ["", _t("ingest.not_ingested_header", n=len(missed))]
        for it in missed[:20]:
            L.append(f"- `{it['file']}` — {it.get('detail', it.get('reason', ''))}")
            for row in (it.get("unrecognised") or [])[:6]:
                unit = f" [{row['unit']}]" if row.get("unit") else ""
                L.append(f"    · «{row['label']}»{unit}")
        if len(missed) > 20:
            L.append(_t("ingest.not_ingested_more", n=len(missed) - 20))
    # A point whose date did not come off the form has to say so where the file
    # is listed, not only in the JSON. Two weaker witnesses, each named: the date
    # the tests were ORDERED, and the name of the file.
    named = {it["file"] for it in missed}
    for key in ("date_not_the_draw", "date_from_filename"):
        for it in (r.get(key) or [])[:10]:
            # A file already listed above with its own reason is not listed
            # again: two lines about one file read as two problems.
            if it["file"] in named:
                continue
            L.append(f"- `{it['file']}` — {it.get('note', '')}")
    for c in (r.get("conflicts") or [])[:10]:
        L.append(_t("ingest.conflict", marker=c["marker"], date=c["date"],
                    kept=c["kept"], other=c["other"]))
    for rep in (r.get("repeats") or [])[:10]:
        L.append(_t("ingest.repeat", marker=rep["marker"], day=rep["day"],
                    first=rep["first"]["value"], second=rep["second"]["value"]))
    for mix in (r.get("resolution_mixed") or [])[:10]:
        L.append(_t("store.resolution_mixed", marker=mix["marker"],
                    dates=", ".join(mix["others"])))
    for rep in (r.get("same_day_replaced") or [])[:10]:
        L.append(_t("ingest.same_day_replaced", marker=rep["marker"], date=rep["date"],
                    replaced=", ".join(rep["replaced"])))
    if r.get("errors"):
        L.append(_t("ingest.errors_footer",
                    files=_plural(len(r["errors"]), "count.files_errored")))
    if r.get("manifest_moved"):
        # Said once, on the run that carried the list over: a reader who sees
        # every earlier form counted as «skipped» on a fresh profile deserves the
        # sentence that explains it (task 133).
        L.append(r["manifest_moved"]["note"])
    return "\n".join(L) + "\n"


def ingest_studies_report(r: Dict[str, Any]) -> str:
    """What was taken, and — by name — every file that gave up nothing.

    The counts used to be the whole report, and `files_seen` was never reconciled
    against them: a file read and dropped touched no counter, so a ten-page
    discharge summary carrying four diagnoses could pass through the loader
    without leaving a trace anywhere. `ingest_labs` had already been taught this;
    this is the same report for the loader that had not.

    The two lines that head the list are `ingest_labs`'s own: one wording for
    one meaning, so the two loaders answer «what did you not take» in the same
    words. A second copy of the same sentence is a second thing to keep in step.

    A laboratory form here is not a complaint — the other loader owns it, and it
    is listed apart so the two files that DID go missing are not buried under
    forty that went where they belong.
    """
    if not r.get("ok"):
        return f"⚠️ {r.get('error', '')}"
    L = [_t("ingest.studies_done", total=r.get("total"), added=r.get("added"),
            updated=r.get("updated"), seen=r.get("files_seen"), hint=r.get("hint", ""))]
    missed = r.get("not_ingested") or []
    if missed:
        L += ["", _t("ingest.not_ingested_header", n=len(missed))]
        # The alarming ones first: a reader who stops after three lines should
        # have read the ones that mean something was lost.
        order = {"unreadable": 0, "conclusion_not_extracted": 0, "unclassified": 1, "no_text": 2,
                 "looks_like_a_lab_form": 3}
        for it in sorted(missed, key=lambda m: order.get(m.get("reason"), 9))[:20]:
            L.append(f"- `{it['file']}` — {it.get('detail', it.get('reason', ''))}")
            # What was inside a file that could not be split is the actionable part:
            # a count says something was lost, these say WHAT was lost.
            for sec in (it.get("sections") or [])[:8]:
                L.append(f"    · {sec['what']} — {sec['date']}")
        if len(missed) > 20:
            L.append(_t("ingest.not_ingested_more", n=len(missed) - 20))
    if r.get("manifest_moved"):
        L.append(r["manifest_moved"]["note"])
    return "\n".join(L) + "\n"


def markers_local_report(r: Dict[str, Any]) -> str:
    """Locally added dictionary entries and what may be claimed on each."""
    if not r.get("ok"):
        return f"✗ {r.get('error', '')}"
    if "entries" in r:
        if not r["entries"]:
            return _t("markers.none_local") + "\n"
        L = [_t("markers.local_header", n=len(r["entries"])), ""]
        for e in r["entries"]:
            mark = "✓" if e["status"] == "confirmed" else "·"
            names = ", ".join(f"«{n}»" for n in e["names"][:3])
            L.append(f"{mark} `{e['key']}` [{e['status']}] {e.get('unit','')} — {names}"
                     + (f" ({e['by']}, {e['on']})" if e.get("by") else ""))
        L += ["", _t("markers.local_footer", path=r["path"])]
        return "\n".join(L) + "\n"
    return _t("markers.entry_status", key=r["key"], status=r["status"]) + "\n"
