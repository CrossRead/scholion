"""The printed card of one body system, and the pages beside it (the systems index, the evidence legend).

Split out of `format.py` on 18.09.2026, when that module reached 3,600 lines
and the system card alone was a fifth of it. Same functions, same names — the
faces import them from `format` as before, which re-exports them from here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .i18n import plural as _plural, t as _t
from .format import _PRIO_ICON, _flag_icon, _level_counts_line, genotype_conclusion_lines  # noqa: E402


def _names(rows: Any, key: str = "name") -> str:
    return ", ".join(str((r or {}).get(key) or r) if isinstance(r, dict) else str(r)
                     for r in (rows or []))


def _system_gene_row(r: Dict[str, Any], register: str) -> str:
    """One row of the genetic half — its mode first, because the three modes
    make different claims and are never printed alike."""
    mode = _t("system.mode." + str(r.get("mode") or "unknown"))
    if r.get("unit") == "position":
        st = r.get("state") or (r.get("genotype") or {}).get("state")
        head = _t("system.row.position", gene=r.get("gene"), rsid=r.get("rsid") or "—",
                  mode=mode, state=_t("system.state." + str(st)))
    else:
        head = _t("system.row.gene", gene=r.get("gene"), mode=mode,
                  classifications=", ".join(r.get("classifications") or []) or "—",
                  moi=", ".join(r.get("moi_codes") or [r.get("moi") or "—"]))
    marks = []
    if r.get("findings"):
        marks.append(_t("system.row.finding", n=r["findings"]))
    if r.get("carrier"):
        marks.append(_t("system.row.carrier"))
    if r.get("unit") == "position":
        marks.insert(0, _t("system.row.level", level=r["level"], short=r.get("level_short") or "—")
                     if r.get("level") else _t("system.row.level_none"))
    if r.get("needs_confirmation"):
        marks.append(_t("system.row.needs_confirmation"))
    if r.get("not_a_finding_why") == "level":
        marks.append(_t("system.row.not_finding_level"))
    if r.get("not_a_finding_why") == "kind":
        marks.append(_t("system.row.not_finding_kind", kind=_t("system.kind." + str(r.get("kind") or "unassigned"))))
    if r.get("pending"):
        marks.append(_t("system.row.pending"))
    if r.get("signature") == "open":
        marks.append(_t("system.row.signature_open"))
    if r.get("read") is False:
        marks.append(_t("system.row.unread", why=r.get("read_why_text") or r.get("read_why") or "—"))
    if r.get("link_text"):
        marks.append(_t("system.panel.link", link=r["link_text"]))
    line = "· " + head + ((" — " + "; ".join(marks)) if marks else "")
    if r.get("text"):
        line += "\n   " + str(r["text"])
    if r.get("local_note"):
        n = r["local_note"]
        line += "\n   " + _t("system.row.local_note", by=_t("system.row.local_note_by." + str(n.get("by_role") or "clinician")),
                             on=n.get("on") or "—") + ": " + str(n.get("text") or "")
    if r.get("depth_note"):
        line += "\n   " + str(r["depth_note"])
    if r.get("presumed") and r.get("closes_text"):
        line += "\n   " + str(r["closes_text"])
    if r.get("file_says_text"):
        line += "\n   " + str(r["file_says_text"])
    for extra in ("carrier_class_text", "two_variants_text"):
        if r.get(extra):
            line += "\n   " + str(r[extra])
    rt = r.get("route") if isinstance(r.get("route"), dict) else None
    if rt and rt.get("routes"):
        line += "\n   " + _t("system.panel.route_head", list=" · ".join(
            "%s — %s" % (x.get("route_text"), _t("system.panel.route." + str(x.get("state"))))
            for x in rt["routes"])) + " (" + _t("system.panel.route_basis." + str(rt.get("basis") or "mechanism")) + ")"
    ul = r.get("under_load") if isinstance(r.get("under_load"), dict) else None
    if ul and ul.get("what_it_reveals"):
        line += "\n   " + _t("system.panel.under_load", test=ul.get("test_text") or ul.get("test"),
                             reveals=ul["what_it_reveals"])
    if r.get("ladder_refused"):
        line += "\n   " + _t("system.row.ladder_refused")
    if r.get("ladder"):
        own = str((r.get("genotype") or {}).get("genotype") or "").replace("/", "").replace("|", "")
        if r.get("hemizygous") and own and len(set(own)) == 1:
            own = own[0]          # a man's single X, written T or T/T by the caller
        rungs = [("**" + g + "**" if own and sorted(own) == sorted(g) else g)
                 for g in (r["ladder"].get(k) for k in ("base", "het", "hom")) if g]
        line += "\n   " + _t("system.row.ladder", rungs=" · ".join(rungs))
    if register == "clinician":
        detail = []
        g = r.get("genotype") or {}
        if g.get("genotype"):
            detail.append(_t("system.row.genotype", genotype=g["genotype"],
                             confidence=g.get("confidence") or "—",
                             depth=g.get("depth") if g.get("depth") is not None else "—"))
        for a in r.get("assertions") or []:
            detail.append(_t("system.row.assertion", disease=a.get("disease") or "—",
                             classification=a.get("classification") or "—",
                             moi=a.get("moi") or "—", submitter=a.get("submitter") or "—",
                             date=a.get("curated_on") or "—"))
        if r.get("signature") == "clinician":
            # The exception is marked on the row; the rule is counted in the
            # summary, which both registers print. With every row signed by the
            # same hand on the same day, a line under each said nothing the
            # count does not — and buried the one row a clinician had signed.
            detail.append(_t("system.row.signature_clinician",
                             date=r.get("signed_on") or "—"))
        if r.get("source"):
            detail.append(_t("decision.source", source=r["source"]))
        line += "".join("\n   _" + d + "_" for d in detail)
    return line


def _system_polygenic(poly: Any, register: str) -> List[str]:
    """The common variation of a system, as scores under their own head — never
    interleaved with the gene rows, because a percentile inside a reference
    panel and a classified variant are two different claims (task 178)."""
    if not isinstance(poly, dict) or poly.get("status") in (None, "no_genetic_half"):
        return []
    L = ["   **" + _t("system.polygenic.title") + "**"]
    if poly.get("status") != "ok":
        L.append("   " + str(poly.get("why") or ""))
        return L
    L.append("   " + _t("system.polygenic.line", mapped=poly.get("mapped") or 0,
                        scored=poly.get("scored") or 0, high=len(poly.get("high") or [])))
    for r in poly.get("rows") or []:
        line = "   · " + _t("system.polygenic.row", label=r.get("label"),
                            percentile=r.get("percentile") if r.get("percentile") is not None else "—",
                            reliable=_t("system.polygenic.reliable" if r.get("reliable")
                                        else "system.polygenic.unreliable"))
        if register == "clinician":
            detail = [_t("system.polygenic.detail", pgs_id=r.get("pgs_id") or "—",
                         evidence=r.get("evidence_label") or r.get("evidence") or "—")]
            detail += [str(r[k]) for k in ("validity_note", "integrity_note", "weight_mass_note",
                                           "evidence_note") if r.get(k)]
            if r.get("model_changed_from"):
                detail.append(_t("system.polygenic.model_changed", previous=r["model_changed_from"]))
            line += "".join("\n     _" + d + "_" for d in detail)
        L.append(line)
    if poly.get("unscored"):
        L.append("   " + _t("system.polygenic.unscored", traits=", ".join(poly["unscored"])))
    L.append("   _" + (poly.get("caveat") or _t("system.polygenic.caveat")) + "_")
    return L


def _correction_route_lines(cr) -> List[str]:
    """«If a decision to correct has been made» — grouped by class, never ranked.

    Not a numbered layer: the seven layers are the brief's frame, and this block
    answers a decision the product did not make. Every printed line carries what
    to recheck and when, and `adds_nothing` is printed rather than left silent.
    """
    if not isinstance(cr, dict) or cr.get("status") != "ok":
        return []
    out = ["", "**" + str(cr.get("head") or "") + "**", "   " + str(cr.get("caveat") or "")]
    def rows(group):
        lines = []
        for x in group:
            lines.append("   · **" + str(x.get("route_text") or "—") + "** — " + str(x.get("because") or ""))
            if x.get("on"):
                lines.append("      " + _t("system.routes.on", markers=", ".join(x["on"])))
            if x.get("positions"):
                lines.append("      " + _t("system.routes.positions", positions=", ".join(x["positions"])))
            rc = x.get("recheck")
            if rc:
                lines.append("      " + _t("system.routes.recheck",
                                           marker=rc.get("marker_name") or rc.get("marker"),
                                           weeks=_plural(int(rc.get("after_weeks") or 0), "count.weeks"),
                                           change=rc.get("what_counts_as_change")))
            src = (x.get("evidence") or {}).get("source")
            if src:
                lines.append("      _" + _t("system.routes.source", source=src) + "_")
        return lines
    for g in cr.get("groups") or []:
        out.append("   " + str(g.get("says_text") or g.get("says")))
        out += rows(g.get("rows") or [])
    quiet = cr.get("adds_nothing") or []
    if quiet:
        out.append("   " + str(quiet[0].get("says_text") or ""))
        out += rows(quiet)
    return out


def system_report(r: Dict[str, Any]) -> str:
    """The third entry, as one block: seven layers, the verdict, the questions,
    the three baskets. The two registers print the same facts at two densities
    and the verdict is the same line in both (brief §7).
    """
    if r.get("status") == "unknown_system":
        return _t("system.unknown", key=r.get("key") or "—", systems=", ".join(r.get("systems") or []))
    if r.get("status") == "unknown_register":
        return _t("system.unknown_register", register=r.get("register") or "—",
                  registers=", ".join(r.get("registers") or []))
    reg = r.get("register") or "patient"
    L = ["**" + _t("system.title", label=r.get("label") or r.get("key")) + "** · "
         + _t("system.register." + reg), "", r.get("verdict_line") or ""]
    if r.get("on_demand"):
        # A panel without a radar domain (task 199 F): the reason first, then
        # the positions the way a system's genetic half prints, and nothing
        # about laboratory layers that do not exist.
        if r.get("unread_line"):
            L.append(r["unread_line"])
        L += ["", "**" + _t("system.on_demand.head") + "**",
              "   " + _t("system.on_demand.why", why=r.get("why_no_domain") or "—"), "",
              "**" + _t("system.layer.on_demand_genetics") + "**"]
        gen = r.get("genetics") or {}
        for g in gen.get("groups") or []:
            L.append("   · **" + str(g.get("label")) + "** — " + _plural(int(g.get("count") or 0), "count.positions")
                     + ((" — " + _t("system.row.level", level=g.get("level"), short=g.get("level_short") or "")) if g.get("level") else ""))
            if g.get("text"):
                L.append("      " + str(g["text"]))
            for m in g.get("members") or []:
                if m.get("state") in ("het", "hom", "hemi") or m.get("read") is not True:
                    L.append("      " + _system_gene_row({**m, "unit": "position"}, reg).replace("\n", "\n      "))
        grouped = {rs for g in gen.get("groups") or [] for rs in g.get("positions") or []}
        for row in gen.get("rows") or []:
            if row.get("rsid") in grouped:
                continue
            L.append("   " + _system_gene_row(row, reg).replace("\n", "\n   "))
        if not gen.get("rows"):
            L.append("   " + str((gen.get("curated") or {}).get("why_empty") or ""))
        return "\n".join(L).rstrip() + "\n"
    if r.get("unread_line"):
        L.append(r["unread_line"])
    L.append("")
    # 1 — the laboratory half
    lab = r.get("labs") or {}
    L.append("**1. " + _t("system.layer.labs") + "**")
    if lab.get("status") == "absent":
        L.append("   " + _t("system.labs.absent"))
    elif lab.get("status") == "nodata":
        L.append("   " + _t("system.labs.nodata", total=lab.get("total") or 0))
    else:
        L.append("   " + _t("system.labs.line", score=lab.get("score"),
                            level=_t("system.level." + str(lab.get("level") or "nodata")),
                            measured=lab.get("measured") or 0, total=lab.get("total") or 0))
        for m in lab.get("abnormal") or []:
            L.append(f"   {_flag_icon(m.get('flag'))} {m.get('name')}: {m.get('value')} "
                     f"{m.get('unit', '')} ({m.get('date', '')})")
    if lab.get("missing"):
        L.append("   " + _t("system.labs.missing",
                            markers=_names(lab.get("missing_names") or lab["missing"])))
    if lab.get("stale"):
        L.append("   " + _t("system.labs.stale", markers=_names(lab["stale"])))
    if lab.get("panel_term"):
        pt = lab["panel_term"]
        L.append("   " + _t("system.panel_labs.term", outside=pt["outside"], judged=pt["judged"], score=pt["score"]))
    L += _panel_lines(lab.get("panel"))
    # 2 — the dynamics
    dyn = r.get("dynamics") or {}
    L += ["", "**2. " + _t("system.layer.dynamics") + "**"]
    if dyn.get("status") == "ok":
        d = dyn.get("delta") or 0
        # Both scores are over the SAME markers — the ones with an earlier
        # point — so the movement is a comparison and not two different means.
        L.append("   " + _t("system.dynamics.line", prev=dyn.get("prev_score"),
                            score=dyn.get("compared_score"), delta=f"{'+' if d > 0 else ''}{d}",
                            date=dyn.get("prev_date") or "—", compared=dyn.get("compared") or 0))
        for m in dyn.get("moved") or []:
            L.append("   · " + _t("system.dynamics.moved", name=m.get("name"),
                                  from_value=m.get("from_value"), to_value=m.get("to_value"),
                                  unit=m.get("unit") or ""))
    else:
        L.append("   " + _t("system.dynamics." + str(dyn.get("status") or "absent")))
    # 3 — the genetic half
    gen = r.get("genetics") or {}
    L += ["", "**3. " + _t("system.layer.genetics") + "**"]
    if gen.get("status") == "composed":
        base = gen.get("base") or {}
        L.append("   " + _t("system.genetics.composed",
                            source=base.get("source") or "—", version=base.get("version") or "—",
                            base_genes=base.get("genes") or 0,
                            positions=(gen.get("curated") or {}).get("positions") or 0,
                            read_genes=gen.get("read_genes") or 0,
                            read_positions=gen.get("read_positions") or 0,
                            findings=gen.get("finding_count") or 0,
                            carriers=gen.get("carrier_count") or 0,
                            pending=gen.get("pending_count") or 0))
        if gen.get("signature_author_count"):
            L.append("   " + _t("system.genetics.signature_author",
                                n=gen["signature_author_count"],
                                date=gen.get("signature_author_date") or "—"))
        if gen.get("signature_open_count"):
            L.append("   " + _t("system.genetics.signature_open",
                                n=gen["signature_open_count"]))
        if gen.get("level_counts"):
            L.append("   " + _level_counts_line(gen["level_counts"]))
        if gen.get("withheld_by_classification"):
            L.append("   " + _t("system.genetics.withheld", n=gen["withheld_by_classification"]))
        if gen.get("excluded"):
            L.append("   " + _t("system.genetics.excluded", genes=_names(gen["excluded"], "gene")))
        refused = gen.get("refused") or {}
        if refused.get("total"):
            by = refused.get("by_reason") or {}
            L.append("   " + _t("system.genetics.refused", n=refused["total"])
                     + ((" — " + ", ".join(f"{k}: {v}" for k, v in by.items())) if by else ""))
        for u in gen.get("unreadable") or []:
            L.append("   " + _t("system.genetics.unreadable", gene=u.get("gene"), reason=u.get("reason") or "—"))
        # Groups first (task 199, decision 3): one line for N positions, then the
        # positions the groups do not hold, then the genes of the base.
        grouped = set()
        for g in gen.get("groups") or []:
            grouped.update(g.get("positions") or [])
            L.append("   · **" + str(g.get("label")) + "** — " + _plural(int(g.get("count") or 0), "count.positions")
                     + ((" — " + _t("system.row.level", level=g.get("level"), short=g.get("level_short") or "")) if g.get("level") else ""))
            if g.get("text"):
                L.append("      " + str(g["text"]))
            st = g.get("states") or {}
            L.append("      " + ", ".join(f"{_t('system.panel.state.' + k)} {v}" for k, v in st.items()))
            for m in g.get("members") or []:
                if m.get("state") in ("het", "hom", "hemi") or m.get("read") is not True:
                    L.append("      " + _system_gene_row({**m, "unit": "position"}, reg).replace("\n", "\n      "))
        for row in gen.get("rows") or []:
            if row.get("unit") == "position" and row.get("rsid") in grouped:
                continue
            L.append("   " + _system_gene_row(row, reg).replace("\n", "\n   "))
        n_assumed = sum(1 for row in gen.get("rows") or [] if row.get("read_why") == "assumed_ref")
        if n_assumed:
            L.append("   " + _t("system.genetics.assumed_ref_hint",
                                positions=_plural(n_assumed, "count.positions")))
        if gen.get("rows_withheld_as_detail"):
            L.append("   _" + _t("system.row.patient_withheld", n=gen["rows_withheld_as_detail"]) + "_")
        if gen.get("positions"):
            L += ["   " + ln for ln in genotype_conclusion_lines(gen["positions"])]
    elif gen.get("status") == "not_composed":
        L.append("   " + _t("system.genetics.not_composed",
                            why=gen.get("why_empty") or _t("screen.why.no_panel")))
    else:
        L.append("   " + _t("screen.why.no_genetic_half"))
    L += _system_polygenic(gen.get("polygenic"), reg)
    # 4 — the prescriptions acting here
    med = r.get("medications") or {}
    L += _correction_route_lines(r.get("correction_routes"))
    L += ["", "**4. " + _t("system.layer.medications") + "**"]
    for m in med.get("rows") or []:
        L.append("   · " + _t("system.meds.row", name=m.get("name"), dose=m.get("dose") or "",
                              classes=", ".join(m.get("via") or [])).replace("  ", " "))
    if med.get("empty_reason"):
        L.append("   " + med["empty_reason"])
    if med.get("unmapped"):
        L.append("   " + _t("system.meds.unmapped", names=_names(med["unmapped"])))
    if med.get("unclassified"):
        L.append("   " + _t("system.meds.unclassified", names=_names(med["unclassified"])))
    # 5 — the clinician's target
    tg = r.get("target") or {}
    L += ["", "**5. " + _t("system.layer.target") + "**"]
    for row in tg.get("rows") or []:
        cur = row.get("current")
        if cur:
            side = _t("target.side_above" if row.get("side") == "above" else "target.side_below") \
                if row.get("outside_target") else _t("system.target.within")
            L.append("   · " + _t("system.target.row", name=row.get("name"), spec=row.get("spec"),
                                  unit=row.get("unit") or "", set_by=row.get("set_by") or "",
                                  set_on=row.get("set_on") or "", value=cur.get("value"),
                                  date=cur.get("date") or "—", side=side))
        else:
            L.append("   · " + _t("system.target.no_value", name=row.get("name"), spec=row.get("spec"),
                                  unit=row.get("unit") or "", set_by=row.get("set_by") or "",
                                  set_on=row.get("set_on") or ""))
    if tg.get("empty_reason"):
        L.append("   " + tg["empty_reason"])
    # 6 — what to test
    tests = r.get("tests") or {}
    L += ["", "**6. " + _t("system.layer.tests") + "**"]
    for s in tests.get("rows") or []:
        L.append("   " + _PRIO_ICON.get(s.get("priority", "low"), "•") + " " + _test_row(s))
    if tests.get("empty_why"):
        L.append("   " + _t("system.why." + tests["empty_why"]))
    # 7 — the questions
    qs = r.get("questions") or {}
    L += ["", "**7. " + _t("system.layer.questions") + "**"]
    for i, q in enumerate(qs.get("rows") or [], 1):
        L.append(f"   {i}. {q.get('text')}")
    if qs.get("empty_why"):
        L.append("   " + _t("system.why." + qs["empty_why"]))
    # the three baskets
    nxt = r.get("next") or {}
    L += ["", "**" + _t("system.layer.next") + "**"]
    for basket in ("lab", "genome", "ask"):
        b = nxt.get(basket) or {}
        L.append("   **" + _t("system.next." + basket) + "**")
        for row in b.get("rows") or []:
            line = _test_row(row) if row.get("origin") == "rule" else str(row.get("text"))
            if row.get("closes"):
                line += " — " + str(row["closes"])
            L.append("   · " + line)
        if b.get("empty_reason"):
            L.append("   _" + b["empty_reason"] + "_")
        if (b.get("full_genome") or {}).get("text"):
            L.append("   " + str(b["full_genome"]["text"]))
    if r.get("disclaimer"):
        L += ["", "_" + r["disclaimer"] + "_"]
    return "\n".join(L)


def _test_row(s: Dict[str, Any]) -> str:
    spec = (" · " + _t("tests.specialist", name=s["specialist"])
            if s.get("specialist") and s["specialist"] != "—" else "")
    return f"**{s.get('suggest')}**{spec} — " + _t("tests.why", text=s.get("why") or "—")


def systems_report(r: Dict[str, Any]) -> str:
    """The systems, one line each: the two halves and what acts on it."""
    L = ["**" + _t("systems.title") + "**", ""]
    acting: Dict[str, int] = {}
    for p in r.get("prescriptions") or []:
        for k in p.get("systems") or []:
            acting[k] = acting.get(k, 0) + 1
    for s in r.get("systems") or []:
        lab, gen = s.get("labs") or {}, s.get("genetics") or {}
        if not s.get("lab_half"):
            labs = _t("system.labs.absent")
        elif lab.get("score") is None:
            labs = _t("common.no_data")
        else:
            labs = _t("systems.labs", score=lab.get("score"), measured=lab.get("measured") or 0,
                      total=lab.get("total") or 0)
        if gen.get("status") == "composed":
            g = _t("systems.genetics.composed", n=gen.get("base_genes") or 0,
                   version=gen.get("base_version") or "—", positions=gen.get("curated_positions") or 0,
                   read=gen.get("read_count") or 0, unread=gen.get("unread_count") or 0)
        elif gen.get("status") == "not_composed":
            g = _t("systems.genetics.not_composed")
        else:
            g = _t("systems.genetics.no_half")
        poly = gen.get("polygenic") or {}
        if poly.get("mapped"):
            g += "; " + _t("systems.polygenic", scored=poly.get("scored") or 0, mapped=poly["mapped"])
        L.append("· **" + str(s.get("label")) + "** (`" + str(s.get("key")) + "`) — " + labs
                 + "; " + g + "; " + _t("systems.acting", n=acting.get(s.get("key"), 0)))
    L += ["", _t("systems.hint")]
    if r.get("disclaimer"):
        L += ["", "_" + r["disclaimer"] + "_"]
    return "\n".join(L)


def _panel_lines(panel: Optional[Dict[str, Any]]) -> List[str]:
    """A system's long panel and its ratios: shown, not scored."""
    if not panel:
        return []
    L = ["   " + _t("system.panel_labs.head", measured=len(panel.get("markers") or []),
                    total=panel.get("total") or 0)]
    by_key = {m["key"]: m for m in panel.get("markers") or []}

    def marker(m: Dict[str, Any], pad: str) -> List[str]:
        out = [f"{pad}{_flag_icon(m.get('flag'))} {m.get('name')}: {m.get('value')} {m.get('unit') or ''}"
               f" ({m.get('date') or '—'})"
               + (" — " + _t("system.panel_labs.display_only") if m.get("display_only") else "")]
        comp = m.get("companions") or []
        if comp:
            out.append(pad + "  " + _t("system.panel_labs.companions", list="; ".join(
                f"{c['name']} {c['value']} {c.get('unit') or ''}".rstrip() if c.get("measured")
                else _t("system.panel_labs.companion_missing", name=c["name"]) for c in comp)))
        return out

    grouped = set()
    if panel.get("groups"):
        L.append("   " + _t("system.panel_labs.groups_head"))
        for g in panel["groups"]:
            L.append("   ▸ " + _t("system.panel_labs.group", label=g["label"], measured=g["measured"], total=g["total"]))
            for x in g["members"]:
                grouped.add(x["key"])
                if not g["measured"]:
                    continue          # «measured 0 of N» already says it; N empty lines would not
                if x["key"] in by_key:
                    L += marker(by_key[x["key"]], "      ")
                elif x.get("measured"):
                    L.append(f"      {_flag_icon(x.get('flag'))} {x['name']}: {x['value']} {x.get('unit') or ''}"
                             f" ({x.get('date') or '—'})")
                else:
                    L.append(f"      · {x['name']} — " + _t("system.panel_labs.not_measured"))
            for r in g.get("ratios") or []:
                if r.get("origin") in ("printed", "computed"):
                    L.append("      · " + _t("system.panel_labs.ratio_" + r["origin"], name=r.get("name") or r["key"],
                                               value=r.get("value"), date=r.get("date") or "—"))
    for m in panel.get("markers") or []:
        if m["key"] not in grouped:
            L += marker(m, "   ")
    for x in panel.get("ratios") or []:
        if x.get("origin") in ("printed", "computed"):
            L.append("   · " + _t("system.panel_labs.ratio_" + x["origin"], name=x.get("name") or x["key"],
                                  value=x.get("value"), date=x.get("date") or "—")
                     + ("" if x.get("has_range") else " — " + _t("system.panel_labs.no_range")))
        else:
            L.append("   · " + _t("system.panel_labs.ratio_" + x["origin"], name=x.get("name") or x["key"],
                                  missing=", ".join(x.get("missing_names") or x.get("missing") or []) or "—"))
    return L


def evidence_levels_report(r: Dict[str, Any]) -> str:
    """The legend of evidence levels A–E, one line per level."""
    if r.get("status") != "ok":
        return _t("evidence.unavailable")
    L = ["**" + _t("evidence.title") + "**", ""]
    for x in r.get("levels") or []:
        L.append(_t("evidence.row", level=x.get("level"), short=x.get("short") or "—",
                    full=x.get("full") or "—", says=x.get("says") or "—"))
    L += ["", _t("evidence.boundary", levels=", ".join(r.get("verdict_levels") or []) or "—"),
          "", _t("evidence.more")]
    if r.get("disclaimer"):
        L += ["", "_" + r["disclaimer"] + "_"]
    return "\n".join(L)
