"""Rendering of engine structures into markdown strings. Used by the CLI, the Claude skill and the Ouroboros plugin."""
from __future__ import annotations
from typing import Any, Dict, Optional

from .i18n import plural as _plural, t as _t

_LEVEL_ICON = {"high": "🔴", "moderate": "🟠", "low": "🟢", "unknown": "⚪"}
_FLAG_ICON = {"high": "🔴", "low": "🟠", "ok": "🟢"}
_NEAR_ICON = "🟡"          # within range, but pressed against the edge of the corridor
# No reference range at all. Deliberately a neutral dot rather than any colour:
# every colour on this scale is a verdict, and there is nothing here to base one
# on. A green tick beside a number with no corridor reads as «this is fine» —
# which is a statement about a person made from the absence of data.
_NORANGE_ICON = "·"


def _mark_icon(m, default="•"):
    """Marker icon: 🟡 for "within range but at the edge", otherwise the plain flag."""
    if m.get("near_limit") and m.get("flag") == "ok":
        return _NEAR_ICON
    if m.get("flag") in ("norange", "unconfirmed_rule"):
        # The same neutral mark as «no corridor». Both mean the value stands and
        # no verdict is offered on it; a green tick here would be a claim.
        return _NORANGE_ICON
    return _FLAG_ICON.get(m.get("flag"), default)


def _decision_suffix(m, context=False) -> str:
    """Clinical action thresholds. Crossed ones are always shown; ones not crossed only
    in the context of a drug, where they are the substantive answer ("haematocrit below the
    intervention threshold of 54 — there is headroom")."""
    ds = m.get("decisions") or []
    hit = [d for d in ds if d.get("crossed")]
    out = []
    for d in hit:
        out.append(" · ❗" + _t("decision.crossed", label=d["label"],
                               sign="≥" if d.get("side") == "high" else "≤",
                               value=f"{d['value']:g}"))
    if context and not hit and ds:
        d = ds[0]
        out.append(" · " + _t("decision.not_reached", value=f"{d['value']:g}", label=d["label"]))
    return "".join(out)


def _near_suffix(m) -> str:
    nl = m.get("near_limit")
    if not nl or m.get("flag") != "ok":
        return ""
    side = _t("near.upper" if nl["side"] == "high" else "near.lower")
    cp = (", " + _t("near.corridor", pct=f"{nl['corridor_pct']:g}")
          if nl.get("corridor_pct") is not None else "")
    mv = f"; {nl['movement']}" if nl.get("movement") else ""
    # Task 100. The caveat travels WITH the claim it qualifies. A move measured
    # between two days, one of which the form never printed, is a move of
    # uncertain size, and saying so anywhere else than here would be saying it
    # where nobody is reading.
    if nl.get("date_caveat"):
        mv += " " + nl["date_caveat"]
    return " · " + _t("near.at_edge", margin=f"{nl['margin_pct']:g}", side=side,
                      bound=f"{nl['bound']:g}") + cp + mv
_PRIO_ICON = {"high": "🔴", "moderate": "🟠", "low": "🟢"}


def drug_check(r: Dict[str, Any]) -> str:
    if r["status"] == "error":
        return f"⚠️ {r['message']}"
    if r["status"] in ("not_in_panel", "not_found"):
        return f"ℹ️ {r['message']}\n\n_{r['disclaimer']}_"
    if r["status"] == "found_online":
        ref = "\n" + _t("drug.reference", url=r["reference"]) if r.get("reference") else ""
        return f"🌍 {r['message']}{ref}\n\n_{r['disclaimer']}_"
    if r.get("no_pgx"):
        # In the text path the result is language-resolved before it reaches here
        # (as every other field is); the dict fallback is only for a direct caller.
        note = r.get("note") or r.get("recommendation") or ""
        text = note if isinstance(note, str) else (note.get("en") or "")
        return f"ℹ️ {text}\n\n_{r.get('disclaimer','')}_"
    icon = _LEVEL_ICON.get(r["level"], "•")
    lines = [icon + " " + _t("drug.headline", drug=r["drug"], gene=r["gene"],
                             drug_class=r["drug_class"], level=r["level"]), ""]
    if r.get("why"):
        lines.append(_t("drug.why_gene", text=r["why"]))
    if r.get("phenotype_label"):
        lines.append(_t("drug.phenotype", phenotype=r["phenotype"], label=r["phenotype_label"]))
    for c in r.get("co_genes") or []:
        if c.get("phenotype_label"):
            lines.append(_t("drug.co_phenotype", gene=c["gene"],
                            phenotype=c["phenotype"], label=c["phenotype_label"]))
    if r.get("driving_gene") and r.get("driving_gene") != r.get("gene"):
        lines.append(_t("drug.driven_by", gene=r["driving_gene"]))
    lines.append("")
    lines.append(_t("drug.discuss", text=r["recommendation"]))
    cp = r.get("cpic")
    if isinstance(cp, dict) and cp.get("recommendation"):
        # Quoted and attributed. The line above is this project's wording for the
        # person; this one is the guideline's own, in the guideline's language,
        # so a doctor can check it against the source instead of trusting a
        # translation of a paraphrase.
        lines.append("")
        lines.append(_t("drug.cpic_header", phenotype=cp.get("phenotype", ""),
                        classification=cp.get("classification", "")))
        lines.append(f"> {cp['recommendation']}")
        if cp.get("implication"):
            lines.append(f"> ")
            lines.append(f"> _{cp['implication']}_")
    if r.get("markers_found"):
        lines.append("\n" + _t("drug.markers_header"))
        for m in r["markers_found"]:
            if "copies" in m:  # computed marker
                star = f" ({m['star']})" if m.get("star") else ""
                lines.append(f"- `{m['rsid']}`{star} {m['genotype']} — "
                             + _t("drug.marker_computed", copies=m["copies"],
                                  function=m["function"]))
            elif m.get("diplotype"):
                # A CALLED star allele, not a marker: it has no rsID because it
                # is not one position — it is a diplotype called from a BAM. This
                # branch was missing, so the renderer raised KeyError('rsid') the
                # moment the called-diplotype path finally reached it.
                lines.append(f"- **{m['diplotype']}** — {m.get('phenotype_text', '')}"
                             + (f" ({m['source']})" if m.get("source") else ""))
            elif m.get("rsid"):   # marker from the profile
                lines.append(f"- `{m['rsid']}` {m['genotype']} — {m.get('interpretation', '')}")
    cvb = _clinvar_block(r.get("clinvar"))
    if cvb:
        lines.append(cvb)
    lines.append(f"\n_{r['disclaimer']}_")
    return "\n".join(lines)


def labs_report(r: Dict[str, Any]) -> str:
    near_n, cross_n = r.get("near_limit_count"), r.get("decision_crossed_count")
    near_s = ", " + _t("labs.near_more", n=near_n) if near_n else ""
    cross_s = "; " + _t("labs.crossed", n=cross_n) if cross_n else ""
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
        t = m.get("trend")
        if t:
            arrow = {"up": "↑", "down": "↓", "flat": "→"}[t["direction"]]
            pct = f" {t['pct']:+g}%" if t.get("pct") is not None else ""
            line += (" · " + _t("common.trend", arrow=arrow, pct=pct)
                     + f" ({t['from_date']}→{t['to_date']})")
        if m.get("genome_link"):
            line += " · " + _t("labs.genome_link", text=m["genome_link"])
        line += _near_suffix(m) + _decision_suffix(m)
        if m.get("note"):
            line += f" · _{m['note']}_"
        lines.append(line)
    lines.append(f"\n_{r['disclaimer']}_")
    return "\n".join(lines)


def _fmt_ref(m: Dict[str, Any]) -> str:
    """The corridor beside the value — and, when it is a guess, that it is one.

    `ref_sex_unknown` was computed by the engine for months and read by nobody:
    a grep of the whole tree found it only in the file that produced it. It marks
    exactly the case where the range shown may be the wrong one — the marker's
    interval differs by sex and the profile never recorded a sex — which is how a
    woman's normal testosterone was printed against a male corridor. A safety
    signal that nothing renders is not a safety signal.
    """
    lo, hi = m.get("ref_low"), m.get("ref_high")
    warn = f" {_t('ref.sex_unknown')}" if m.get("ref_sex_unknown") and (
        lo is not None or hi is not None) else ""
    if lo is not None and hi is not None:
        return f" [{_t('ref.range', low=lo, high=hi)}]{warn}"
    if hi is not None:
        return f" [{_t('ref.max', high=hi)}]{warn}"
    if lo is not None:
        return f" [{_t('ref.min', low=lo)}]{warn}"
    if m.get("ref_sex_unknown"):
        return f" {_t('ref.sex_unknown_no_range')}"
    return ""


def _refused_head(value: Optional[str]) -> str:
    """The one-line reason a locus has no answer — and never a catalogue key.

    Task 88. This head was built by gluing a value onto a prefix:
    `"genome.refused_head." + confidence`. `confidence` is not an enumeration of
    refusal reasons, two of its values had no line in either language, and the
    resolver printed the key itself — so the commonest question anybody asks of
    a chip, «what is my APOE», answered with ⟦genome.refused_head.not_on_chip⟧.

    A missing line is now a missing line, not a leak: the fallback says the true
    and useful thing (there is no answer here and the sentence below explains
    why), and `tests/test_no_refusal_prints_a_key.py` walks every value that can
    reach this function so that the next one is caught before a person sees it.
    """
    key = "genome.refused_head." + (value or "no_file")
    text = _t(key)
    if text.startswith("\u27e6") or text == key:
        return _t("genome.refused_head.unnamed")
    return text


def genome_report(r: Dict[str, Any]) -> str:
    st = r.get("status")
    if st == "unknown_rsid":
        return f"⚠️ {r.get('message','')}"
    if st == "unknown_gene":
        return "⚠️ " + _t("genome.unknown_gene", gene=r.get("gene"))
    if st == "no_genome":
        # The coordinate is in `r` itself; `r["locus"]` was never set on this
        # path, so every field came back empty and the line printed as
        # «rs429358 (, None:None)» — a dangling comma and two Nones leaking a
        # missing dictionary lookup into what a person reads. The nested form is
        # kept as a fallback for callers that do send it.
        loc = r.get("locus") or {}
        gene = r.get("gene") or loc.get("gene") or "—"
        chrom = r.get("chrom") or loc.get("chrom")
        pos = r.get("pos") or loc.get("pos")
        where = f"{chrom}:{pos}" if chrom and pos else _t("genome.no_coordinate")
        head = (f"⚪ {r.get('rsid')} ({gene}, {where}) — "
                + _refused_head(r.get("reason")))
        lines = [head, f"_{r.get('message','')}_"]
        amb = r.get("ambiguous") or {}
        if amb.get("choices"):
            lines.append("· " + "\n· ".join(str(c) for c in amb["choices"][:8]))
        return "\n".join(lines)
    if r.get("gene") and "loci" in r:
        lines = [_t("genome.loci", gene=r["gene"])]
        for item in r["loci"]:
            lines.append("• " + genome_report(item).split("\n")[0])
        return "\n".join(lines)
    # a single rsID, ok
    res = r.get("result") or {}
    if not res.get("genotype"):
        # Nothing came back from the reader. Printing `genotype **?** ()` here —
        # a genotype-shaped hole with an empty parenthesis after it — was the
        # third leak of the same kind as `(, None:None)`: an absent value
        # rendered in the shape of a present one.
        loc = r.get("locus") or {}
        # The same rule as the answered line: print the coordinate that was
        # actually looked at, and name the set it belongs to. A refusal that
        # quotes the other build's number sends the reader to the wrong base.
        _asm = res.get("assembly")
        _pos = res.get("read_pos") if res.get("read_pos") is not None else (
            r.get("pos") or loc.get("pos"))
        _chrom = r.get("chrom") or loc.get("chrom")
        where = (f"{(_asm + ' ') if _asm else ''}{_chrom}:{_pos}"
                 if _chrom else _t("genome.no_coordinate"))
        head = _refused_head(res.get("confidence") or "unreadable_file")
        why = res.get("note") or _t("genome.refused.no_answer")
        return f"⚪ {r.get('rsid')} ({r.get('gene') or '—'}, {where}) — {head}\n_{why}_"
    gt = res.get("genotype", "?")
    # All three levels of confidence are named. `confirmed_ref` had no line at
    # all, so the STRONGEST of them printed as an empty string and the sentence
    # came out as "(, depth 25)" — a dangling comma where the reassurance should
    # be, while the weaker `assumed_ref` was labelled properly. A reader
    # comparing two loci would have read the better-evidenced one as the vaguer.
    conf = {"called": _t("genome.called"),
            "called_array": _t("genome.called_array"),
            "called_array_ambiguous": _t("genome.called_array_ambiguous"),
            "confirmed_ref": _t("genome.confirmed_ref_short"),
            "assumed_ref": _t("genome.assumed_ref")}.get(res.get("confidence"), "")
    # An imputed genotype is the output of a model over a reference panel, not a
    # base anybody observed in this person. One corpus file was 98.8 % imputed
    # and every row of it read as «called from the VCF».
    if res.get("imputed"):
        conf = _t("genome.imputed_short")
    elif res.get("filtered"):
        conf = _t("genome.filtered_short", value=res["filtered"])
    star = f" {r.get('star')}" if r.get("star") else ""
    dp = ", " + _t("genome.depth", value=res["depth"]) if res.get("depth") is not None else ""
    gene = r.get("gene") or "—"
    # Task 83, the last item of its acceptance. The catalogue holds two
    # coordinates for every locus and the file's own build decides which one is
    # read; printing the other one unlabelled sent a person with a GRCh37 file
    # to look up a position holding a different base in their own data. Name the
    # set, and print the number that was actually used.
    asm_used = res.get("assembly")
    pos_shown = res.get("read_pos") if res.get("read_pos") is not None else r.get("pos")
    line = (f"🧬 **{r.get('rsid')}**{star} — "
            + _t("genome.gene_at", gene=gene, chrom=r.get("chrom"), pos=pos_shown,
                 assembly=(asm_used + " ") if asm_used else "")
            + ": " + _t("genome.genotype", genotype=gt) + f" ({conf}{dp})")
    # Two sources for one position, and what became of them. A flag computed in
    # the data layer and printed nowhere is the failure this project keeps
    # finding in itself; this is the last mile for the one task 64 added.
    if res.get("conflict"):
        c = res["conflict"]
        line += "\n⚠️ " + _t("genome.conflict", reported=c.get("reported"),
                             called=c.get("called"))
    elif res.get("confirmed_by") == "profile":
        line += "\n" + _t("genome.confirmed_by_report")
    cs = r.get("clinical_significance")
    if cs:
        line += "\n" + _t("genome.significance", values=", ".join(cs))
    if r.get("consequence"):
        line += "\n" + _t("genome.consequence", text=r["consequence"])
    if r.get("resolved_by") and r["resolved_by"] != "catalog":
        line += f"\n_{_t('genome.resolved_by', source=r['resolved_by'])}_"
    # Two different notes live here, and only the harmless one was being printed.
    #
    # `r["note"]` is the CATALOGUE's remark about the locus — the same text for
    # everybody. `res["note"]` is about THIS read of THIS person's genome, and it
    # is where "depth is low (4 reads) — the call is unreliable" lives. It was
    # never printed in any channel: not the CLI, not the web, not the plugin. The
    # locus that demonstrated it is rs4149056, statin myopathy, read four times.
    #
    # The measurement goes first: a warning that the call cannot be trusted
    # changes what the catalogue's remark is worth.
    if res.get("note"):
        line += f"\n⚠️ _{res['note']}_"
    if r.get("note"):
        line += f"\n_{r['note']}_"
    line += f"\n\n_{r.get('disclaimer','')}_"
    return line


_SEV_ICON = {"high": "🔴", "moderate": "🟠", "low": "🟢"}
_TIER_ICON = {"drug": "💊", "pathogenic": "🔴", "risk": "🟠", "protective": "🟢"}


def _clinvar_block(cv: Dict[str, Any]) -> str:
    """Block of ClinVar findings that relate to the drug (drug_response and others)."""
    if not cv or not cv.get("available") or not cv.get("hits"):
        return ""
    out = ["\n**🧬 " + _t("clinvar_block.header") + "**"]
    for h in cv["hits"][:12]:
        ic = _TIER_ICON.get(h.get("tier"), "•")
        sig = (h.get("clnsig") or "").replace("_", " ")
        via = (_t("clinvar_block.via_gene", gene=h["gene"]) if h.get("gene")
               else _t("clinvar_block.via_name"))
        dis = f" — {h['disease']}" if h.get("disease") else ""
        gt = _t("clinvar_block.genotype", genotype=h.get("genotype", "?"))
        out.append(f"{ic} `{h.get('rsid','')}` {sig} ({gt}, {via}){dis}")
    return "\n".join(out)


def prescription_check(r: Dict[str, Any]) -> str:
    """SECOND OPINION on a drug — personal: 🧬 the patient's genome, 🧪 their labs,
    🔗 their prescriptions. Works for any drug (genes from CPIC via rxcui)."""
    if r.get("status") != "ok":
        return f"⚠️ {r.get('message','')}"
    ov = _SEV_ICON.get(r.get("overall"), "•")
    ident = r.get("identified", {})
    src = {"rxnorm": "RxNorm", "local": _t("source.local"),
           "none": _t("source.none")}.get(ident.get("source"), "")
    lines = [ov + " " + _t("prescription.title", drug=r.get("drug"), overall=r.get("overall")),
             f"_{_t('prescription.class', value=r.get('class_display', '—'))}_"
             + (" · " + _t("prescription.source", value=src) if src else ""), ""]

    # What could not be determined, printed BEFORE the findings rather than after.
    # The engine lifts the verdict off "low" for each of these; if the reason were
    # not printed, the reader would be left with a raised verdict and no way to see
    # what raised it — which is the same defect as the green field, mirrored.
    unresolved = r.get("unresolved") or []
    if unresolved:
        lines.append("**" + _t("prescription.unresolved_h") + "**")
        for u in unresolved:
            detail = u.get("detail") or u.get("what", "")
            lines.append("- " + (_t("prescription.unresolved_gene", detail=detail, gene=u["gene"])
                                 if u.get("gene") else detail))
        lines.append("")

    # 🔴 Red flags from the owner's own file — printed FIRST, above every computed
    # section. A documented diagnosis of this patient outranks a rule inferred from a
    # class, and a flag rendered at the bottom of a long answer is a flag not read.
    for fl in (r.get("safety_flags") or []):
        icon = "🔴" if fl.get("severity") == "red_flag" else "🟡"
        lines.append(icon + " **" + _t("prescription.safety_h") + "**")
        if fl.get("factor"):
            lines.append("- " + _t("prescription.safety_factor", text=fl["factor"]))
        for key, field in (("prescription.safety_why", "why_it_matters"),
                           ("prescription.safety_pro", "what_is_known_in_favour"),
                           ("prescription.safety_unknown", "uncertainty"),
                           ("prescription.safety_action", "action"),
                           ("prescription.safety_source", "source")):
            if fl.get(field):
                lines.append("- " + _t(key, text=fl[field]))
        lines.append("")

    # 🧬 The patient's genome
    lines.append("**🧬 " + _t("prescription.genome_header") + "**")
    g = r.get("genome", {})
    genes = g.get("genes", [])
    if not genes:
        cp = g.get("cpic") or {}
        lines.append(f"_{_t('prescription.no_pgx')}_" if cp.get("asked") else
                     "_" + _t("prescription.pgx_unchecked",
                              why=_t("pgx_unchecked." + (cp.get("reason") or "unreachable"))) + "_")
    else:
        for ge in genes:
            # "куратор" is a VALUE engine.py writes to mark the project's own base apart
            # from a CPIC level; it is compared here and in the web page, never printed.
            lvl = (_t("source.local") if ge.get("cpic_level") == "куратор"
                   else f"CPIC {ge.get('cpic_level')}")
            tag = " — " + _t("prescription.actionable") if ge.get("actionable") else ""
            if ge.get("computable"):
                lines.append(f"- **{ge['gene']}** ({lvl}{tag}): "
                             + _t("prescription.gene_phenotype", phenotype=ge.get("phenotype"),
                                  label=ge.get("label", "")))
            else:
                mk = ", ".join(f"`{m.get('rsid')}` {m.get('genotype','')}" for m in ge.get("markers", []))
                pre = _t("prescription.variants", list=mk) + "; " if mk else ""
                lines.append(f"- **{ge['gene']}** ({lvl}{tag}): {pre}{ge.get('label','')}")

    # 🧪 The patient's labs
    lines.append("\n**🧪 " + _t("prescription.labs_header") + "**")
    lb = r.get("labs", {})
    if not lb.get("markers"):
        lb_basis = lb.get("basis") or {}
        if not lb_basis.get("classes"):
            lines.append(f"_{_t('prescription.labs_class_unknown')}_")
        elif not lb_basis.get("with_rules"):
            lines.append("_" + _t("prescription.labs_no_rule",
                                  classes=r.get("class_display", "—")) + "_")
        else:
            lines.append(f"_{_t('prescription.no_lab_control')}_")
    else:
        if lb.get("reason"):
            lines.append(_t("prescription.monitor", text=lb["reason"]) + ".")
        watch = lb.get("watch", [])
        if watch:
            lines.append("⚠️ " + _t("prescription.already_abnormal",
                                    names=", ".join(w["name"] for w in watch)))
        crossed = lb.get("crossed", [])
        if crossed:
            for c in crossed:
                for d in (c.get("decisions") or []):
                    if d.get("crossed"):
                        lines.append("❗" + _t("prescription.threshold_crossed",
                                               name=c["name"], value=c["value"],
                                               threshold=f"{d['value']:g}", label=d["label"])
                                     + f" {d.get('action','')} ["
                                     + _t("prescription.source_ref",
                                          source=d.get("source", "")) + "]")
        near = lb.get("near", [])
        if near:
            lines.append("🟡 " + _t("prescription.near_edge",
                                    names=", ".join(w["name"] for w in near)))
        for m in lb["markers"]:
            icon = _mark_icon(m) if m.get("present") else "⚪"
            val = (f"{m['value']} {m.get('unit','')}".strip() if m.get("present")
                   else _t("prescription.not_tested"))
            lines.append(f"{icon} {m['name']}: {val}{_near_suffix(m)}{_decision_suffix(m, context=True)}")

    # 🔗 Interactions with the prescriptions
    lines.append("\n**🔗 " + _t("prescription.interactions_header") + "**")
    inter = r.get("interactions", {})
    hits = inter.get("interactions", [])
    if hits:
        for it in hits:
            ic = _SEV_ICON.get(it.get("severity"), "•")
            lines.append(ic + " " + _t(
                "prescription.interaction",
                meds=", ".join(it.get("with_meds", [])) or it.get("with_class", ""),
                effect=it.get("effect", ""), mechanism=it.get("mechanism", ""))
                + " " + _t("prescription.what_to_do", text=it.get("manage", "")))
    elif inter.get("status") in ("no_rules", "unknown_class"):
        lines.append(f"_{inter.get('message','')}_")
    else:
        unrec = (inter.get("baseline") or {}).get("unclassified") or []
        lines.append(f"_{_t('prescription.no_interactions')}_"
                     if not unrec else
                     "_" + _t("prescription.no_interactions_partial",
                              names=", ".join(unrec[:6])) + "_")

    cvb = _clinvar_block(r.get("clinvar"))
    if cvb:
        lines.append(cvb)

    # ⚖ Dose and critical-claim context (concrete numbers, not 'in the general direction')
    dc = r.get("dose_context") or {}
    if dc.get("matched"):
        lines.append("\n**⚖ " + _t("prescription.dose_header") + "**")
        nd, pd = dc.get("nutritional_dose"), dc.get("pharmacologic_dose")
        if nd or pd:
            lines.append(_t("prescription.doses", nutritional=nd or "—", pharmacologic=pd or "—"))
        for it in dc.get("items", []):
            head = f"- {it.get('claim')}"
            if it.get("source"):
                head += f" [{it['source']}]"
            lines.append(head)
            if it.get("effect_size"):
                lines.append("    • " + _t("prescription.effect", text=it["effect_size"]))
            if it.get("low_dose_note"):
                lines.append("    • " + _t("prescription.by_dose", text=it["low_dose_note"]))
            comps = []
            for pt in it.get("patient", []):
                if pt.get("measured"):
                    lo, hi = pt.get("ref_low"), pt.get("ref_high")
                    if lo is not None and hi is not None:
                        ref = _t("ref.range", low=lo, high=hi)
                    elif hi is not None:
                        ref = _t("ref.max", high=hi)
                    elif lo is not None:
                        ref = _t("ref.min", low=lo)
                    else:
                        ref = ""
                    fl = {"high": "↑", "low": "↓",
                          "ok": _t("common.in_range")}.get(pt.get("flag"), "")
                    tail = "; ".join(x for x in (ref, fl) if x)
                    v = f"{pt['name']} {pt['value']} {pt.get('unit','')}".strip()
                    comps.append(v + (f" ({tail})" if tail else ""))
                else:
                    comps.append(_t("prescription.not_measured", name=pt["name"]))
            if comps:
                lines.append("    • " + _t("prescription.your_numbers",
                                           items="; ".join(comps)))
        if dc.get("forms"):
            lines.append(_t("prescription.forms", text=dc["forms"]))
        if dc.get("note"):
            lines.append(dc["note"])
        for alt in dc.get("alternatives") or []:
            lines.append("- " + _t("prescription.alternative", name=alt.get("name")))
            for k, lbl_key in (("melatonin", "prescription.alt_melatonin"),
                               ("metabolic", "prescription.alt_metabolic"),
                               ("caveat", "prescription.alt_caveat")):
                if alt.get(k):
                    lines.append(f"    • {_t(lbl_key)}: {alt[k]}")
        if dc.get("verdict_rule"):
            lines.append(f"→ {dc['verdict_rule']}")

    lines.append(f"\n_{r.get('disclaimer','')}_")
    return "\n".join(lines)


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
        lines.append(f"{icon} {m['name']}: **{m['value']} {m.get('unit','')}**".rstrip() +
                     f" ({m.get('date','')}){tr}")
    lines.append(f"\n_{r.get('disclaimer','')}_")
    return "\n".join(lines)


def clinvar_report(r: Dict[str, Any]) -> str:
    """The patient's clinically significant findings (ClinVar × the personal VCF)."""
    st = r.get("status")
    if st in ("input_is_an_array", "input_too_narrow"):
        # Task 99. A closed path is INFORMATION, not a warning: nothing went
        # wrong, the input simply cannot carry this answer. The generic branch
        # below prefixes ⚠️, and a refusal that looks like a failure sends people
        # looking for a fix that does not exist.
        return f"ℹ️ {r.get('message','')}\n\n{r.get('open_instead','')}"
    if st == "not_run":
        return f"ℹ️ {r.get('message','')}\n\n" + _t("clinvar.how_to_run")
    if st != "ok":
        return f"⚠️ {r.get('message','')}"
    # The indel caveat qualifies an EMPTY list as much as a full one: an indel
    # that could not be matched is missing from both.
    _indel = ("\n\n" + r["indel_caveat"]) if r.get("indel_caveat") else ""
    if not r.get("count"):
        return _t("clinvar.empty") + _indel
    lines = [_t("clinvar.header", n=r["count"]) + " " + _t("clinvar.shown", n=len(r["hits"])), ""]
    if r.get("low_confidence"):
        lines += [_t("clinvar.low_confidence_note", n=r["low_confidence"]), ""]
    if r.get("indel_caveat"):
        lines += [r["indel_caveat"], ""]
    for h in r["hits"]:
        sig = (h.get("clnsig") or "").replace("_", " ")
        icon = "🔴" if "pathogenic" in (h.get("clnsig", "").lower()) else "🟠"
        cond = (h.get("clndn") or "").replace("|", " / ").replace("_", " ")
        stars = h.get("stars")
        star_mark = (" " + "★" * stars + "☆" * (4 - stars)) if isinstance(stars, int) else ""
        lowc = " ⚠️" + _t("clinvar.low_confidence") if h.get("low_confidence") else ""
        lines.append(f"{icon} `{h.get('rsid','')}` {h.get('chrom')}:{h.get('pos')} "
                     f"{h.get('ref')}→{h.get('alt')} [{h.get('genotype','')}] — **{sig}**"
                     + (f" · {cond}" if cond and cond != "." else "")
                     + star_mark + lowc)
        # What the stars MEAN, in the base's own words. The star count is a
        # number; `penetrance.json` holds the sentence that says what weight it
        # carries, and that sentence had never reached a reader.
        rc = h.get("review_confidence")
        if rc and h.get("low_confidence"):
            lines.append(f"    ↳ {rc}")
    pen = r.get("penetrance") or {}
    if pen.get("one_line"):
        lines.append("\n" + _t("clinvar.how_to_read") + f" {pen['one_line']}")
        for p in (pen.get("principles") or [])[:3]:
            lines.append(f"- {p.get('title')}: {p.get('text')}")
    lines.append(f"\n_{r.get('disclaimer','')}_")
    return "\n".join(lines)


def acmg_report(r: Dict[str, Any]) -> str:
    """ACMG SF secondary findings — a short list of what is actionable, with caveats."""
    st = r.get("status")
    if st in ("input_is_an_array", "input_too_narrow"):
        # Task 99. A closed path is INFORMATION, not a warning: nothing went
        # wrong, the input simply cannot carry this answer. The generic branch
        # below prefixes ⚠️, and a refusal that looks like a failure sends people
        # looking for a fix that does not exist.
        return f"ℹ️ {r.get('message','')}\n\n{r.get('open_instead','')}"
    if st == "not_run":
        return f"ℹ️ {r.get('message','')}\n\n" + _t("acmg.how_to_run")
    if st != "ok":
        return f"⚠️ {r.get('message','')}"
    ver = r.get("version", "ACMG SF")
    out = [_t("acmg.header", version=ver, genes=r.get("gene_count"),
              scanned=r.get("scanned") or "—"), ""]
    rep, car = r.get("reportable") or [], r.get("carriers") or []
    if rep:
        out.append("🔴 " + _t("acmg.reportable", n=len(rep)))
        for h in rep:
            out.append(f"- **{h.get('gene')}** {h.get('rsid','')} [{h.get('zygosity')}] — "
                       f"{h.get('phenotype','')} · {(h.get('clnsig') or '').replace('_',' ')}")
        out.append("")
    else:
        out.append("✅ " + _t("acmg.no_reportable"))
        # A negative is only as wide as the reading behind it. The number was
        # computed and printed by another command; saying «none found» without it
        # is the flagship claim of this layer resting on an unstated premise.
        cov = r.get("coverage") or {}
        if cov.get("note"):
            out.append(cov["note"])
            for w in (cov.get("weak") or [])[:5]:
                out.append(f"  · {w['gene']} — {w['pct_10x']:g} % at 10×")
        out.append("")
    if car:
        out.append("⚪️ " + _t("acmg.carriers", n=len(car)))
        for h in car:
            out.append(f"- {h.get('gene')} {h.get('rsid','')} [{h.get('zygosity')}] — "
                       f"{h.get('phenotype','')} ({h.get('inheritance')})")
        out.append("")
    pen = r.get("penetrance") or {}
    if pen.get("one_line"):
        out.append(f"_{pen['one_line']}_")
    out.append("\n⚠️ " + _t("acmg.caveat"))
    out.append(f"\n_{r.get('disclaimer','')}_")
    # What the panel could NOT read. Printed whether or not anything was found:
    # «no pathogenic variant» in a gene read at 72 % is a different sentence from
    # the same words about a gene read end to end, and nothing on screen told
    # them apart.
    unread = r.get("unread_genes") or []
    if unread:
        out += ["", _t("acmg.unread_header", n=len(unread))]
        out.append("  " + ", ".join(f"{x['gene']} {x['pct']}%" for x in unread[:12]))
    ph = r.get("needs_phase") or []
    if ph:
        out += ["", _t("acmg.needs_phase_header", n=len(ph))]
        genes = sorted({h.get("gene") for h in ph if h.get("gene")})
        out.append("  " + ", ".join(genes))
    nc = r.get("needs_variant_class") or []
    if nc:
        out += ["", _t("acmg.needs_class_header", n=len(nc))]
        for h in nc[:8]:
            out.append(f"- {h.get('gene')} `{h.get('rsid') or ''}` — "
                       + str((h.get("report_rule_note") or {}) if isinstance(
                           h.get("report_rule_note"), str) else
                           (h.get("report_rule_note") or ""))[:200])
    return "\n".join(out)


def _n(x: Any) -> str:
    try:
        return str(int(x)) if float(x).is_integer() else str(x)
    except Exception:
        return str(x)


def lifestyle_report(r: Dict[str, Any]) -> str:
    """Lifestyle (wearable devices): year-by-year trends + a workout summary."""
    ms = r.get("metrics", [])
    if not ms:
        return _t("lifestyle.empty")
    fs = r.get("fitness_score")
    lines = [_t("lifestyle.title")
             + (" · " + _t("lifestyle.fitness_score", score=fs) if fs is not None else ""), ""]
    ar = {"up": "↑", "down": "↓", "flat": "→"}
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
        lines.append(f"{icon.get(m.get('status'),'•')} {m['label']}: **{_n(m['value'])} {m['unit']}**".rstrip()
                     + f" ({m['date']}){tr}{improv}{brk}")
    wk = r.get("workouts", [])
    if wk:
        top = ", ".join(f"{x['type']} ({x['total']})" for x in wk[:6])
        lines.append("\n" + _t("lifestyle.workouts", items=top))
    lines.append(f"\n_{r.get('disclaimer','')}_")
    return "\n".join(lines)


def prs_report(r: Dict[str, Any]) -> str:
    """Polygenic risks (PGS): statistics + "above average" + by category."""
    if not r.get("available"):
        return r.get("message", _t("prs.not_ready"))
    s = r.get("stats", {})
    lines = [_t("prs.title") + " · "
             + _t("prs.reliable", reliable=s.get("reliable"), total=s.get("total")) + " · "
             + _t("prs.reference", population=s.get("superpopulation", "EUR")), ""]
    # EUR is a DEFAULT, not a finding. A percentile is a position within a
    # reference population; computing it against one the person does not belong
    # to and printing it as an ordinary number is the same silent substitution
    # that gave a woman a male testosterone range — a plausible stand-in for a
    # missing precondition, delivered with the confidence of a measured fact.
    if not s.get("ancestry_stated"):
        lines.append(_t("prs.population_not_stated",
                        population=s.get("superpopulation", "EUR")))
        lines.append("")
    for w in (r.get("withheld_by_sex") or []):
        lines.append("· " + str(w.get("label")) + " — " + str(w.get("note")))
    if r.get("withheld_by_sex"):
        lines.append("")
    high = r.get("high", [])
    if high:
        lines.append(_t("prs.above_average"))
        for t in high:
            p = t.get("percentile")
            lines.append(f"  🔶 {t['label']}: P{round(p) if isinstance(p,(int,float)) else '—'}"
                         + (f" · {t['effect_size']}" if t.get("effect_size") else "")
                         + (f" · {t['evidence_label']}" if t.get("evidence_label") else ""))
            if t.get("evidence_note"):
                lines.append(f"      {t['evidence_note']}")
            if t.get("validity_note"):
                lines.append(f"      ⚠ {t['validity_note']}")
        lines.append("")
    for c in (r.get("method_caveats") or []):
        lines.append("· " + c["note"])
    if r.get("method_caveats"):
        lines.append("")
    lines.append(_t("prs.evidence_legend"))
    lines.append("")
    for c in r.get("categories", []):
        lines.append(f"__{c['category']}__")
        for t in c.get("traits", []):
            p = t.get("percentile")
            ps = f"P{round(p)}" if isinstance(p, (int, float)) else _t("prs.no_model")
            warn = "" if t.get("reliable") else " ⚠"
            ev = {"clinical": " ✚", "supportive": " ·"}.get(t.get("evidence"), "")
            lines.append(f"  {t['label']}: {ps}{warn}{ev}")
        lines.append("")
    lines.append(f"_{r.get('disclaimer','')}_")
    return "\n".join(lines)


def longevity_report(r: Dict[str, Any]) -> str:
    """Longevity layer (LongevityMap): APOE ε + key markers + significant genes."""
    if not r.get("available"):
        return r.get("message", _t("longevity.not_ready"))
    lines = [_t("longevity.title"), ""]
    ap = r.get("apoe")
    if ap:
        # The longevity layer writes the key genotype, the early report wrote epsilon.
        # Both are read: otherwise an already computed result is shown as a dash.
        _eps = ap.get("epsilon") or ap.get("genotype") or "—"
        if ap.get("status") == "ambiguous_without_phase":
            # Both SNPs heterozygous: two readings, and which one is true depends
            # on which allele sits on which chromosome — a fact an unphased file
            # does not carry. Printing the likelier one as «the» status is the
            # defect this replaced.
            _eps = " / ".join(ap.get("candidates") or [])
        lines.append(_t("longevity.apoe", epsilon=_eps,
                        rs429358=ap.get("rs429358"), rs7412=ap.get("rs7412")))
        if ap.get("status") == "ambiguous_without_phase":
            lines.append("  ⚠ " + str(ap.get("message") or ""))
        lines.append("")
    lines.append(_t("longevity.key_markers"))
    for k in r.get("known", []):
        mk = " ✔" + _t("longevity.carries") if k.get("carries_named_allele") is True else ""
        lines.append(f"  {k['gene']} {k['rsid']}: {k.get('genotype') or '—'}{mk} — {k.get('note','')}")
    st = r.get("stats", {})
    genes = ", ".join(g["gene"] for g in r.get("significant_genes", [])[:16])
    lines.append("\n" + _t("longevity.significant",
                           carriers=st.get("significant_carriers"),
                           genes=_plural(st.get("significant_genes") or 0, "count.genes_in")))
    if genes:
        lines.append(_t("longevity.genes_first", genes=genes))
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
        icon = _PRIO_ICON.get(s.get("priority", "low"), "•")
        spec = (" · " + _t("tests.specialist", name=s["specialist"])
                if s.get("specialist") and s["specialist"] != "—" else "")
        lines.append(f"{icon} **{s['suggest']}**{spec}\n   " + _t("tests.why", text=s["why"]))
    if not pending:
        lines.append(f"_{_t('tests.nothing_pending')}_")
    for s in errs:
        lines.append("⚠️ " + _t("tests.rule_error", id=s["id"], error=s["error"]))
    if done:
        lines.append("\n" + _t("tests.routine_header"))
        for s in done:
            lm = s.get("last_measured", ""); rm = s.get("recheck_months", 3)
            lines.append("✓ " + _t("tests.done", name=s["suggest"], date=lm, months=rm))
    lines.append(f"\n_{r['disclaimer']}_")
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
                         f"({_t('reconcile.bytes', n=u['bytes'])})")
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


# ==========================================================================
# Parity with the web interface: what used to be drawn only in the tabs.
# There are no computations here — this is the presentation of what the engine has
# already computed, exactly as in every renderer above. Absent data is printed in words
# and not as emptiness: "none" and "not connected" are legitimate answers, an empty table is not.
# ==========================================================================

def _flag_icon(flag: str) -> str:
    return {"high": "🔴", "low": "🔵", "ok": "🟢"}.get(flag, "•")


def overview_report(r: Dict[str, Any]) -> str:
    """Main screen summary (the "Overview" tab).

    First report moved onto the message catalogue. Numbers are computed by the
    engine and only formatted here, so the language of a report changes how it
    reads and never what it says.
    """
    head = _t("overview.title") + " " + _t(
        "overview.counts", total=r.get("markers_total", 0), abnormal=r.get("abnormal_count", 0))
    if r.get("stale_abnormal_count"):
        head += _t("overview.stale_note", n=r["stale_abnormal_count"])
    out = [head + ".", ""]

    for key, phrase in (("high_flags", "overview.high"), ("watch_flags", "overview.low")):
        items = r.get(key) or []
        if items:
            out.append(_t(phrase, n=len(items)))
            for m in items:
                out.append(f"  {_flag_icon(m.get('flag'))} {m.get('name')}: "
                           f"{m.get('value')} {m.get('unit', '')} ({m.get('date', '')})")
            out.append("")

    hs = r.get("high_suggestions") or []
    line = _t("overview.suggestions", n=r.get("suggestions_count", 0))
    if hs:
        line += _t("overview.suggestions_priority", n=len(hs))
    out.append(line + ".")
    for s in hs:
        out.append(f"  · {s.get('suggest')} — {s.get('why', '')}")

    g = r.get("genome") or {}
    out.append("")
    state = _t("genome.connected" if g.get("ready") else "genome.not_connected")
    line = _t("overview.genome", state=state)
    if r.get("genome_gaps"):
        line += _t("overview.genome_gaps", genes=", ".join(r["genome_gaps"]))
    out.append(line)
    out.append(_t("overview.medications", n=r.get("medications_count", 0)))

    ls = r.get("lifestyle") or {}
    if ls.get("watch"):
        out.append(_t("overview.lifestyle_watch", items=", ".join(
            f"{w['label']} {w['value']} {w.get('unit', '')}".strip() for w in ls["watch"])))

    out.append(f"\n_{r.get('disclaimer', '')}_")
    return "\n".join(out)


def radar_report(r: Dict[str, Any]) -> str:
    """Health index by body system (the same radar as in the web UI, but as text)."""
    out = []
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
    out = [_t("second_opinion.title"), ""]
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
    out.append(f"\n_{_t('second_opinion.note')}_")
    out.append(f"_{r.get('disclaimer', '')}_")
    return "\n".join(out)


def medications_report(r: Dict[str, Any]) -> str:
    meds = r.get("medications") or []
    if not meds:
        return _t("medications.empty")
    out = [_t("medications.header", n=len(meds))]
    for m in meds:
        line = f"  · {m.get('name', '?')}"
        if m.get("dose"):
            line += f" — {m['dose']}"
        if m.get("note"):
            line += f" ({m['note']})"
        out.append(line)
    return "\n".join(out)


def genome_status_report(r: Dict[str, Any]) -> str:
    # The build comes first, before «connected» and before «no index». A file in
    # the wrong assembly is neither broken nor missing: it is fine, and it is the
    # wrong coordinate system for our catalogue. Reported as «no index» it would
    # send the reader to run tabix and arrive back at the same wall.
    if r.get("assembly_mismatch"):
        out = [_t("genome_status.assembly_mismatch",
                  found=r.get("assembly"), want=r.get("assembly_expected")),
               _t("genome_status.file", path=r.get("vcf")),
               _t("genome_status.assembly_fix", want=r.get("assembly_expected"))]
        if r.get("gaps"):
            out.append(_t("genome_status.gaps", genes=", ".join(r["gaps"])))
        return "\n".join(out)
    amb = r.get("ambiguous") or {}
    if amb.get("reason") == "several_files":
        out = [_t("genome_status.several_files", count=len(amb["choices"]))]
        out += ["  · " + str(c) for c in amb["choices"][:12]]
        out.append(_t("genome_status.several_files_fix", cmd=amb.get("fix", "")))
        for it in (r.get("foreign") or [])[:8]:
            out.append(_t("genome_status.foreign_" + it["kind"], path=it["path"]))
        return "\n".join(out)
    if amb.get("reason") == "sample_not_found":
        return "\n".join([_t("genome_status.sample_not_found",
                             names=", ".join(str(c) for c in amb["choices"][:12]) or "—"),
                          _t("genome_status.file", path=r.get("vcf", "?")),
                          _t("genome_status.sample_not_found_fix", cmd=amb.get("fix", ""))])
    if amb.get("reason") == "several_samples":
        out = [_t("genome_status.several_samples", count=len(amb["choices"]),
                  names=", ".join(str(c) for c in amb["choices"][:12])),
               _t("genome_status.file", path=r.get("vcf", "?")),
               _t("genome_status.several_samples_fix", cmd=amb.get("fix", ""))]
        return "\n".join(out)
    if r.get("ready") and r.get("input_class") == "tabular" and not r.get("vcf"):
        # Task 89. A third class of input, and the same rule as for the array: it
        # gets its own headline and its own ceiling rather than borrowing the
        # genome's, because what may be claimed from it is different.
        tb = r.get("tabular") or {}
        if tb.get("kind") == "container_vcf":
            out = [_t("genome_status.tabular_container",
                      variants=tb.get("variants") or 0, per_mb=tb.get("observed_per_mb") or 0),
                   _t("genome_status.file", path=tb.get("path") or "?")]
            cls = tb.get("class")
            if cls and cls != "unmeasured":
                out.append(_t("genome_status.callset_" + cls,
                              per_mb=tb.get("observed_per_mb"), share=0))
        else:
            out = [_t("genome_status.tabular_table", rows=tb.get("rows") or 0,
                      present=tb.get("loci_present") or 0),
                   _t("genome_status.file", path=tb.get("path") or "?"),
                   _t("genome_status.tabular_ceiling")]
        if r.get("gaps"):
            out.append(_t("genome_status.gaps", genes=", ".join(r["gaps"])))
        return "\n".join(out)
    if r.get("ready") and r.get("input_class") == "array" and not r.get("vcf"):
        # Task 64, its last item. This line used to read «**Genome connected.**
        # File: None» — twice wrong in eight words, and printed to every one of
        # the twelve array owners in the reference corpus. An array is not a genome;
        # the model already knows that (`input_class: "array"`), and the path to
        # the array was in the JSON the whole time while the human sentence
        # printed the path of the VCF that does not exist.
        arr = r.get("array") or {}
        out = [_t("genome_status.array_connected",
                  vendor=arr.get("vendor") or "?", markers=arr.get("markers") or 0),
               _t("genome_status.file", path=arr.get("path") or "?"),
               _t("genome_status.array_ceiling")]
        if r.get("gaps"):
            out.append(_t("genome_status.gaps", genes=", ".join(r["gaps"])))
        return "\n".join(out)
    if r.get("ready"):
        out = [_t("genome_status.connected") + " " + _t("genome_status.file", path=r.get("vcf", "?"))]
        # What this call set actually is, measured rather than assumed (task 87).
        cs = r.get("callset") or {}
        if cs.get("class") and cs["class"] != "unmeasured":
            out.append(_t("genome_status.callset_" + cs["class"],
                          per_mb=cs.get("observed_per_mb"),
                          share=int(round((cs.get("imputed_share") or 0) * 100))))
        if r.get("sample"):
            out.append(_t("genome_status.sample", name=r["sample"]))
        if r.get("reader"):
            out.append(_t("genome_status.reader", reader=r["reader"]))
        if r.get("engine_pinned"):
            # Which reader answered is part of the answer when somebody pinned
            # one: two runs through different readers are not comparable, and
            # the whole reason the pin exists is to make that visible.
            out.append(_t("genome_status.engine_pinned", engine=r["engine_pinned"]))
        if r.get("assembly"):
            out.append(_t("genome_status.assembly_ok", found=r.get("assembly")))
            # HOW the build was established, when it was not measured off the
            # file. «GRCh37» from a contig length and «GRCh37» from a provider's
            # habit are the same word and not the same claim (task 75).
            if r.get("assembly_how") == "provider_signature":
                out.append(_t("genome_status.assembly_from_signature",
                              provider=r.get("assembly_provider") or "?",
                              why=r.get("assembly_why") or ""))
            elif r.get("assembly_how") == "reference_line":
                out.append(_t("genome_status.assembly_from_reference_line",
                              detail=r.get("assembly_detail") or ""))
            # Which coordinate set answered, and how much of the catalogue can
            # answer that way. Silence here would hide the one thing that makes
            # the reading possible — and hide that a secondary build covers only
            # part of the catalogue.
            cov = r.get("catalogue_by_assembly") or {}
            served = r.get("coordinates")
            if served and served != r.get("assembly_expected"):
                out.append(_t("genome_status.coordinates_secondary", assembly=served,
                              have=cov.get(served, 0), total=cov.get("total", 0)))
        elif r.get("assembly_unknown"):
            # Not a refusal: refusing on «we could not tell» is the same mistake
            # as answering on it. Named, so the reader knows what the answers rest on.
            out.append(_t("genome_status.assembly_unknown", want=r.get("assembly_expected")))
            # The actions, not just the diagnosis. This output is read by an
            # assistant as often as by a person, and «could not be determined»
            # gives neither of them anything to do next.
            out.append(_t("genome_status.assembly_unknown_actions", path=r.get("vcf", "<file>")))
    elif r.get("vcf"):
        # «No index» is the right answer only when an index is genuinely all that
        # is missing. A gzip-not-bgzip archive lands here too, and telling that
        # person to run tabix sends them into an error about the format that
        # explains nothing — the file has to be recompressed first.
        un = r.get("unusable") or {}
        if un.get("reason") == "gzip_not_bgzip":
            out = [_t("genome_status.unusable_gzip_not_bgzip", path=un["path"]),
                   _t("genome_status.unusable_fix", cmd=un["fix"])]
        else:
            out = [_t("genome_status.not_ready", reason=r.get("reason") or _t("genome_status.no_index")),
                   _t("genome_status.file", path=r.get("vcf")),
                   _t("genome_status.build_index")]
    else:
        # A file that is there and unreadable is a different message from no file
        # at all: one needs a command, the other needs a sequencing run.
        un = r.get("unusable") or {}
        mine = r.get("not_ours") or {}
        pin = r.get("engine_problem") or {}
        if pin:
            # A pin that could not be honoured is not «no genome»: the file is
            # there, and the person asked to read it a particular way.
            out = [_t("genome_status." + pin["reason"], value=pin.get("value", ""),
                      accepted=pin.get("accepted", ""))]
        elif mine:
            # Not «no genome». The file is there and readable, and belongs to
            # somebody else — the sentence has to say so, or the reader spends
            # the evening checking a path that is correct.
            out = [mine.get("message", ""), mine.get("fix", "")]
        elif un:
            out = [_t("genome_status.unusable_" + un["reason"], path=un["path"]),
                   _t("genome_status.unusable_fix", cmd=un["fix"])]
        elif r.get("foreign"):
            # Eleven formats used to print «the full VCF is not connected» at a
            # person whose BAM, FASTQ, BCF or provider archive was lying in that
            # very folder. Each class needs a different next step, and only the
            # class can say which.
            out = [_t("genome_status.foreign_head")]
            out += [_t("genome_status.foreign_" + it["kind"], path=it["path"])
                    for it in r["foreign"][:8]]
        else:
            out = [_t("genome_status.no_vcf"), _t("genome_status.how_to_get")]
    if r.get("gaps"):
        out.append(_t("genome_status.gaps", genes=", ".join(r["gaps"])))
    return "\n".join(out)


def genome_updates_report(r: Dict[str, Any]) -> str:
    if not r.get("available"):
        return _t("genome_updates.not_run")
    cv = r.get("clinvar") or {}
    out = [_t("genome_updates.last_checked", date=r.get("last_checked", "?")) + "; "
           + _t("genome_updates.release", release=cv.get("release", "?"))]
    for title_key, key in (("genome_updates.new", "new"), ("genome_updates.changed", "changed")):
        items, title = cv.get(key) or [], _t(title_key)
        out.append(f"**{title} ({len(items)}):**" if items else f"**{title}:** {_t('common.none')}")
        for it in items[:20]:
            out.append(f"  · {it.get('gene', '')} {it.get('rsid', '')} "
                       f"{it.get('significance', '')}".rstrip())
    return "\n".join(out)


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
        L.append(_t("fhir.dry_run", n=len(r.get("points") or [])))
    elif added:
        L.append(_t("fhir.added", n=len(added)))
    for p in (r.get("points") or []):
        mark = "·" if r.get("dry_run") else "✓"
        rng = ""
        if p.get("ref_low") is not None or p.get("ref_high") is not None:
            rng = f" [{p.get('ref_low')}–{p.get('ref_high')}]"
        L.append(f"  {mark} {p['key']} {p['value']:g} {p.get('unit') or ''} "
                 f"({p['date']}, LOINC {p['loinc']}){rng}")
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
            names = ", ".join(sorted({str(i["label"]) for i in items})[:6])
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
        L.append("✓ " + _t("import.dry_ok", n=r.get("accepted", 0)))
    else:
        L.append("✓ " + _t("import.written", n=r.get("written", 0)))
    if r.get("markers"):
        L.append("")
        L.append(_t("import.markers", markers=", ".join(r["markers"])))
    return "\n".join(L)


def limits_report(r: Dict[str, Any]) -> str:
    """«What cannot be said from this data» — and what would close each item.

    Every line ends in an instruction. A report of limitations that stops at the
    limitation is a shrug in the shape of a document; the whole reason this
    command exists is that the reader can act on it.
    """
    L = [_t("limits.title"), ""]
    # The cell first, the list second: what may be claimed at all depends on the
    # class of the input and on the architecture of the trait, and a reader who
    # does not know the cell mis-reads every line that follows.
    sc = r.get("scope") or {}
    if sc.get("input_note"):
        L.append(_t("limits.scope.title"))
        L.append(sc["input_note"])
        for row in sc.get("rows") or []:
            L.append(f"  · {row['note']}")
        if sc.get("heritability_note"):
            L.append(f"  · {sc['heritability_note']}")
        L.append("")
    cov = r.get("coverage") or {}
    if cov.get("known"):
        L.append(_t("limits.coverage_line", genes=cov.get("genes"),
                    mean=cov.get("mean_pct_10x"), acmg_genes=cov.get("acmg_genes"),
                    acmg_pct=cov.get("acmg_pct_10x")))
        # What the percentage is OVER. Without it the reader supplies the
        # assumption themselves, and they supply the flattering one.
        ib = cov.get("interval_basis") or {}
        if ib.get("note"):
            L.append("  · " + ib["note"])
        if cov.get("weak_total"):
            L.append(_t("limits.coverage_weak_line", n=cov["weak_total"]))
        L.append("")
    items = r.get("items") or []
    if not items:
        L.append(_t("limits.none"))
        return "\n".join(L)
    for it in items:
        head = f"**{it['what']}**"
        if it.get("certainty") == "assumed":
            head += f" — {_t('phenotype.assumed', label='')}".rstrip(" —")
        L.append(f"- {head}")
        L.append(f"  {it['why']}")
        if it.get("closes"):
            L.append(f"  → {_t('limits.closes_label')}: {it['closes']}")
        L.append("")
    L.append("_" + _t("limits.summary", count=r.get("count", 0),
                      closable=r.get("closable", 0)) + "_")
    if r.get("disclaimer"):
        L.append("")
        L.append("_" + r["disclaimer"] + "_")
    return "\n".join(L)


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
    if r.get("skipped"):
        L += ["", f"**{_t('goalgen.skipped_h')}**"]
        for skp in r["skipped"]:
            L.append(f"- {skp['name']} — {_t('goalgen.skip.' + skp['reason'])}")
    if r.get("written"):
        w = r["written"]
        L += ["", _t("web.goalgen.saved", n=len(w.get("added") or [])), f"  {w.get('path','')}"]
    L += ["", f"_{r.get('disclaimer','')}_"]
    return "\n".join(L) + "\n"


def lipid_genetics_report(r: Dict[str, Any]) -> str:
    """PCSK9 and Lp(a) in one block, each line carrying what it is worth."""
    L = [f"**{_t('lipidgen.title')}**", "", r.get("headline", ""), "",
         r.get("how_to_read", ""), ""]
    for x in r.get("pcsk9", []):
        if x["status"] == "unread":
            L.append(f"- `{x['rsid']}` {x['gene']} — **{_t('lipidgen.unread')}**")
        elif x["status"] == "no_data":
            L.append(f"- `{x['rsid']}` {x['gene']} — {_t('lipidgen.unread')}")
        else:
            mark = _t("lipidgen.carrier") if x["carrier"] else _t("lipidgen.not_carrier")
            L.append(f"- `{x['rsid']}` {x['gene']} {x['genotype']} — **{mark}**")
            if x.get("verdict"):
                L.append(f"  {x['verdict']}")
        if x.get("population_note"):
            L.append(f"  ⚠ {x['population_note']}")
        if x.get("pmids"):
            L.append("  PMID: " + ", ".join(x["pmids"]))
    if r.get("pcsk9_waiting"):
        L += ["", f"**{_t('lipidgen.waiting_h')}**"]
        for w in r["pcsk9_waiting"]:
            L.append(f"- `{w['rsid']}` {w['gene']} — {w.get('why','')}")
    lpa = r.get("lpa") or {}
    L += ["", f"**{_t('lipidgen.lpa.h')}**"]
    m = lpa.get("measured")
    if m:
        L.append("- " + _t("lipidgen.lpa.measured", value=m["value"], unit=m["unit"],
                           date=m["date"]))
        if m.get("above"):
            L.append("  ⚠ " + _t("lipidgen.lpa.above", ref=m.get("ref_high")))
    else:
        L.append("- " + (lpa.get("what_to_do") or ""))
    if lpa.get("estimate"):
        e = lpa["estimate"]
        L.append(f"- {e.get('label','')}: {e.get('percentile')} ({e.get('pgs_id')}, "
                 f"{e.get('quality')})")
        L.append(f"  ⚠ {lpa.get('estimate_is_not_a_measurement','')}")
    L += ["", f"_{r.get('disclaimer','')}_"]
    return "\n".join(L) + "\n"


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
                if f.get("local"):
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
    return "\n".join(L) + "\n"


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
    if r.get("shared_metrics"):
        lines.append(_t("wearables.shared", metrics=", ".join(r["shared_metrics"])))
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


def array_report(r: Dict[str, Any]) -> str:
    """The three numbers a chip owes, and the loci it owes them about by name.

    A percentage on its own invites the reading «85 % of my genome» — which is
    not what it says. It says: of the catalogue this build actually asks about,
    this chip carries that many. The absent ones are listed because a locus
    nobody looked at is the one a reader would otherwise assume was clean.
    """
    if not r.get("available"):
        if r.get("reason") == "array_unreadable":
            return r.get("note", _t("array.unreadable", vendor=r.get("vendor") or "")) + "\n"
        return _t("array.no_array") + "\n"
    L = [_t("array.coverage_title"), "",
         _t("array.summary", vendor=r["vendor"], markers=r["markers"]), "",
         _t("array.coverage_line", called=r["called"], total=r["catalogue_total"],
            pct=r["pct"], no_call=r["no_call"], absent=r["absent"])]
    if r.get("assembly_declared"):
        L.append(_t("array.assembly_declared", assembly=r["assembly_declared"]))
    if r.get("strand_ambiguous"):
        L += ["", _t("array.ambiguous_header")]
        for a in r["strand_ambiguous"]:
            L.append(f"- `{a['rsid']}` ({a.get('gene') or '—'})")
    if r.get("absent_rsids"):
        L += ["", _t("array.absent_header")]
        L.append("  " + ", ".join(f"`{x}`" for x in r["absent_rsids"][:24]))
    L += ["", _t("array.what_it_cannot_do")]
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
