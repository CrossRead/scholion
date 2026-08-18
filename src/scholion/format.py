"""Rendering of engine structures into markdown strings. Used by the CLI, the Claude skill and the Ouroboros plugin."""
from __future__ import annotations
from typing import Any, Dict

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
    if m.get("flag") == "norange":
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
    icon = _LEVEL_ICON.get(r["level"], "•")
    lines = [icon + " " + _t("drug.headline", drug=r["drug"], gene=r["gene"],
                             drug_class=r["drug_class"], level=r["level"]), ""]
    if r.get("why"):
        lines.append(_t("drug.why_gene", text=r["why"]))
    if r.get("phenotype_label"):
        lines.append(_t("drug.phenotype", phenotype=r["phenotype"], label=r["phenotype_label"]))
    lines.append("")
    lines.append(_t("drug.discuss", text=r["recommendation"]))
    if r.get("markers_found"):
        lines.append("\n" + _t("drug.markers_header"))
        for m in r["markers_found"]:
            if "copies" in m:  # computed marker
                star = f" ({m['star']})" if m.get("star") else ""
                lines.append(f"- `{m['rsid']}`{star} {m['genotype']} — "
                             + _t("drug.marker_computed", copies=m["copies"],
                                  function=m["function"]))
            else:              # marker from the profile
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
    for m in r["markers"]:
        icon = _mark_icon(m)
        ref = _fmt_ref(m)
        val = f"{m['value']} {m['unit']}".strip()
        line = f"{icon} {m['name']}: **{val}** ({m['date']}){ref}"
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
    lo, hi = m.get("ref_low"), m.get("ref_high")
    if lo is not None and hi is not None:
        return f" [{_t('ref.range', low=lo, high=hi)}]"
    if hi is not None:
        return f" [{_t('ref.max', high=hi)}]"
    if lo is not None:
        return f" [{_t('ref.min', low=lo)}]"
    return ""


def genome_report(r: Dict[str, Any]) -> str:
    st = r.get("status")
    if st == "unknown_rsid":
        return f"⚠️ {r.get('message','')}"
    if st == "unknown_gene":
        return "⚠️ " + _t("genome.unknown_gene", gene=r.get("gene"))
    if st == "no_genome":
        loc = r.get("locus", {})
        return (f"⚪ {r.get('rsid')} ({loc.get('gene','')}, {loc.get('chrom')}:{loc.get('pos')}) — "
                + _t("genome.no_database") + f"\n_{r.get('message','')}_")
    if r.get("gene") and "loci" in r:
        lines = [_t("genome.loci", gene=r["gene"])]
        for item in r["loci"]:
            lines.append("• " + genome_report(item).split("\n")[0])
        return "\n".join(lines)
    # a single rsID, ok
    res = r.get("result") or {}
    gt = res.get("genotype", "?")
    # All three levels of confidence are named. `confirmed_ref` had no line at
    # all, so the STRONGEST of them printed as an empty string and the sentence
    # came out as "(, depth 25)" — a dangling comma where the reassurance should
    # be, while the weaker `assumed_ref` was labelled properly. A reader
    # comparing two loci would have read the better-evidenced one as the vaguer.
    conf = {"called": _t("genome.called"),
            "confirmed_ref": _t("genome.confirmed_ref_short"),
            "assumed_ref": _t("genome.assumed_ref")}.get(res.get("confidence"), "")
    star = f" {r.get('star')}" if r.get("star") else ""
    dp = ", " + _t("genome.depth", value=res["depth"]) if res.get("depth") is not None else ""
    gene = r.get("gene") or "—"
    line = (f"🧬 **{r.get('rsid')}**{star} — "
            + _t("genome.gene_at", gene=gene, chrom=r.get("chrom"), pos=r.get("pos"))
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
    if st == "not_run":
        return f"ℹ️ {r.get('message','')}\n\n" + _t("clinvar.how_to_run")
    if st != "ok":
        return f"⚠️ {r.get('message','')}"
    if not r.get("count"):
        return _t("clinvar.empty")
    lines = [_t("clinvar.header", n=r["count"]) + " " + _t("clinvar.shown", n=len(r["hits"])), ""]
    for h in r["hits"]:
        sig = (h.get("clnsig") or "").replace("_", " ")
        icon = "🔴" if "pathogenic" in (h.get("clnsig", "").lower()) else "🟠"
        cond = (h.get("clndn") or "").replace("|", " / ").replace("_", " ")
        lines.append(f"{icon} `{h.get('rsid','')}` {h.get('chrom')}:{h.get('pos')} "
                     f"{h.get('ref')}→{h.get('alt')} [{h.get('genotype','')}] — **{sig}**"
                     + (f" · {cond}" if cond and cond != "." else ""))
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
        lines.append(_t("longevity.apoe", epsilon=_eps,
                        rs429358=ap.get("rs429358"), rs7412=ap.get("rs7412")))
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
    if r.get("ready"):
        out = [_t("genome_status.connected") + " " + _t("genome_status.file", path=r.get("vcf", "?"))]
        if r.get("reader"):
            out.append(_t("genome_status.reader", reader=r["reader"]))
    elif r.get("vcf"):
        out = [_t("genome_status.not_ready", reason=r.get("reason") or _t("genome_status.no_index")),
               _t("genome_status.file", path=r.get("vcf")),
               _t("genome_status.build_index")]
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
    """Result of a writing command. A refusal is printed in words, not silently."""
    if r.get("ok") is False or r.get("error"):
        return f"⚠️ {r.get('error') or _t('write.failed')}"
    bits = [f"{k}: {v}" for k, v in r.items() if k not in ("ok",) and not isinstance(v, (dict, list))]
    return "✓ " + _t("write.saved") + (" · " + "; ".join(bits) if bits else "") + "."


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
