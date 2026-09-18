"""Rendering of engine structures into markdown strings. Used by the CLI, the Claude skill and the Ouroboros plugin."""
from __future__ import annotations
from typing import Any, Dict, List, Optional

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
    # A corridor that is not this draw's own says so: the marker's recorded
    # range answering for a form that printed none is a weaker claim than the
    # range printed beside the number, and the two must not read alike.
    origin = f" {_t('ref.origin_profile')}" if m.get("ref_origin") == "profile" else ""
    if lo is not None and hi is not None:
        return f" [{_t('ref.range', low=lo, high=hi)}]{warn}{origin}"
    if hi is not None:
        return f" [{_t('ref.max', high=hi)}]{warn}{origin}"
    if lo is not None:
        return f" [{_t('ref.min', low=lo)}]{warn}{origin}"
    if m.get("sex_not_applicable"):
        return f" {_t('ref.sex_not_applicable')}"
    if m.get("ref_sex_other"):
        return f" {_t('ref.sex_other_no_range')}"
    if m.get("ref_sex_unreviewed"):
        return f" {_t('ref.sex_unreviewed_no_range')}"
    if m.get("ref_sex_unknown"):
        return f" {_t('ref.sex_unknown_no_range')}"
    if m.get("ref_age_other"):
        return f" {_t('ref.age_other_no_range')}"
    if m.get("ref_age_unknown"):
        return f" {_t('ref.age_unknown_no_range')}"
    if m.get("ref_age_unbanded"):
        return f" {_t('ref.age_unbanded_no_range')}"
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


def _gene_region_report(r: Dict[str, Any]) -> str:
    """A gene answered from the owner's own reads (task 127).

    The order of the blocks is the argument: what was read comes BEFORE what was
    found. A report that opens with «no pathogenic variant» and mentions coverage
    at the bottom has already been believed by the time the qualification arrives.
    """
    if r.get("status") == "unresolved_gene":
        # A coordinate is one thing we know about a gene, and not the only one.
        # This branch used to print the failure to obtain it and stop, so a
        # clinician asking about BRCA1 with no annotation file on the machine was
        # told nothing at all — while the build ships the 84 symbols of the ACMG
        # panel and can say, with no network, that BRCA1 is one of them.
        lines = ["\u26a0\ufe0f " + r.get("message", ""), ""]
        if r.get("searched"):
            lines.append("\u00b7 " + "\n\u00b7 ".join(r["searched"][:8]))
        if r.get("fix"):
            lines += ["", "`" + r["fix"] + "`"]
        if r.get("layers"):
            lines += ["", gene_layers_report(r["layers"])]
        return "\n".join(lines)
    loc = r.get("location") or {}
    if r.get("status") == "no_genome":
        # The coordinate WAS found; it is the personal file that cannot answer.
        # Saying both, in that order, is what keeps the reader from concluding
        # that the gene is unknown when the gene is the one thing that is known.
        return ("\u26a0\ufe0f " + _t("gene.header", gene=r.get("gene"), chrom=loc.get("chrom"),
                                start=loc.get("start"), end=loc.get("end"),
                                strand=loc.get("strand"), assembly=loc.get("assembly"),
                                transcript=loc.get("transcript") or "\u2014")
                + "\n_" + str(r.get("message", "")) + "_")
    if r.get("status") in ("needs_index", "not_sequenced", "unreadable_file"):
        # The same shape as `no_genome`: the gene is known, the input is what
        # cannot carry a region — a chip that reads chosen positions, a file
        # read in one pass, a file that ends before its end. Rendered here by
        # name; through the generic listing below these refusals would print as
        # a gene with no variants, which is a sentence about the person.
        return ("\u26a0\ufe0f " + _t("gene.header", gene=r.get("gene"), chrom=loc.get("chrom"),
                                start=loc.get("start"), end=loc.get("end"),
                                strand=loc.get("strand"), assembly=loc.get("assembly"),
                                transcript=loc.get("transcript") or "\u2014")
                + "\n_" + str(r.get("message", "")) + "_"
                + (f"\n`{r['fix']}`" if r.get("fix") else ""))
    lines = [_t("gene.header", gene=r.get("gene"), chrom=loc.get("chrom"),
                start=loc.get("start"), end=loc.get("end"), strand=loc.get("strand"),
                assembly=loc.get("assembly"), transcript=loc.get("transcript") or "—"),
             "_" + _t("gene.coords_from", source=loc.get("source_file") or loc.get("source")) + "_",
             ""]
    cov = r.get("coverage") or {}
    if cov.get("source") == "bam":
        for key, label in (("gene", _t("gene.whole")), ("cds", _t("gene.cds"))):
            s = cov.get(key)
            if s:
                lines.append("· " + _t("gene.coverage_line", what=label, mean=s["mean"],
                                       min=s["min"], pct10=s["pct_10x"], pct20=s["pct_20x"]))
    else:
        # The whole value of this line is the reason. Printed empty it ends in a
        # dash and nothing — which reads as text that broke off, and a reader
        # cannot tell «no alignment file» from «the gene is outside the coverage
        # table» from a render that failed. Those need opposite actions.
        lines.append("⚠️ " + _t("gene.coverage_missing",
                                why=(cov.get("why") or "").strip()
                                or _t("gene.coverage_not_computed")))
    lines.append("")
    v = r.get("variants") or {}
    conseq = v.get("consequential")
    lines.append(_t("gene.counts", total=v.get("total", 0), coding=v.get("coding", 0),
                    consequential=_t("gene.not_computed") if conseq is None else conseq))
    rows = v.get("coding_rows") or []
    if not rows:
        lines.append("_" + _t("gene.coding_none") + "_")
    for row in rows:
        p = row.get("protein") or {}
        kind = p.get("kind")
        # The consequence class is a phrase for a reader, not an internal token:
        # printing `synonymous` inside a Russian report is a hole in the wall
        # between the code and the page, and it is the reader who falls through.
        named = _t("gene.kind." + kind) if kind else None
        what = p.get("hgvs_p") or named or _t("gene.not_computed")
        ad = row.get("allele_depth")
        depth = (f", {row['depth']}×" if row.get("depth") else "")
        alleles = (f" [{'/'.join(str(x) for x in ad)}]" if ad else "")
        lines.append(f"• {row['chrom']}:{row['pos']} {row['ref']}>{row['alt']} "
                     f"{row.get('genotype') or '?'}{depth}{alleles} — {what}"
                     + (f" ({named})" if p.get("hgvs_p") and named else ""))
    lines.append("")
    hits = r.get("clinvar") or []
    if not hits:
        lines.append("_" + _t("gene.no_flagged") + "_")
    else:
        lines.append(_t("gene.flagged"))
        for h in hits[:20]:
            lines.append(f"• {h.get('chrom')}:{h.get('pos')} {h.get('rsid') or ''} "
                         f"{h.get('genotype') or ''} — {h.get('clnsig')}")
    gaps = r.get("gaps") or []
    if gaps:
        lines += ["", _t("gene.gaps")]
        for g in gaps:
            lines.append("• " + g["what"] + (f" — `{g['fix']}`" if g.get("fix") else ""))
    blind = r.get("blind_spots") or []
    if blind:
        lines += ["", _t("gene.blind")]
        lines += ["• " + b for b in blind]
    return "\n".join(lines)


def genome_report(r: Dict[str, Any]) -> str:
    st = r.get("status")
    # The gene-region answer is recognised BEFORE the refusal branches below.
    # Those are shaped around a single rsID and print «⚪ None (CASR, …)» when
    # handed a gene: a real refusal, rendered in the shape of a different question.
    if r.get("region") or st == "unresolved_gene":
        return _gene_region_report(r)
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
        # The frame first, then the findings — the same rule the genome status
        # follows and for the same reason. A reader who is not told WHICH
        # shelves were asked cannot tell an answer from a silence, and the
        # catalogue is only one of four.
        lines = []
        if r.get("layers"):
            lines += [gene_layers_report(r["layers"]), ""]
        lines.append(_t("genome.loci", gene=r["gene"]))
        for item in r["loci"]:
            lines.append("• " + genome_report(item).split("\n")[0])
            # The cut to one line is what makes this listing readable, and it is
            # also what threw away the sentence that mattered most on one of
            # these loci: the catalogue's own note saying the variant read here
            # is the minor one for most readers, and that the main one is not a
            # SNP and cannot be read from this file at all. A caveat that
            # survives only in the single-locus view is a caveat the reader of a
            # gene never meets. It is reprinted here, indented, under its locus.
            for _q in _locus_qualifier_lines(item):
                lines.append("  " + _q)
        # And the verdict again, under the genotypes. Each locus line here is cut
        # to its first line, so anything a locus wants to add about itself is
        # already gone; a reader who scrolled past the frame to the genotypes
        # would otherwise meet them bare. Two lines, and the whole point.
        lines += _verdict_lines((r.get("layers") or {}).get("verdict") or {})
        return "\n".join(lines)
    # a single rsID, ok
    res = r.get("result") or {}
    # `assumed_ref` joins the refusal shape rather than the answer shape.
    #
    # It was rendered as an answer: «genotype TT (reference (the site is not
    # variant))», with the honest note under it. On a single locus a reader saw
    # both — a reassuring label and a warning contradicting it on the next line.
    # In a GENE LISTING they saw only the first, because the list keeps
    # `.split("\n")[0]`, and the note is the second. A physician running
    # `genome --gene DPYD` met eight positions labelled reference, six of which
    # have no row in the file at all.
    #
    # The engine has been right about this all along — `assumed_ref` is excluded
    # from every decision in `pgx`, `core` and `genomics`, each with a comment
    # saying why. Only the last mile asserted. The refusal shape says the same
    # thing in one line, so it survives being cut down to one line: «there is no
    # row at this position».
    if not res.get("genotype") or res.get("confidence") == "assumed_ref":
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
        # A genotype read from a position the curated catalogue does not carry
        # is a number with nothing standing behind it, and the silence where the
        # reading should be is filled by whoever is talking. It was: a clinician
        # asked about COMT, the product returned rs4680 = AA with depth 36 and
        # said, correctly, that the variant is outside its curated set — and the
        # assistant supplied «the low-activity variant, slower breakdown of
        # dopamine» out of its own general knowledge, with no source inside the
        # product and none of its five reading filters applied.
        #
        # This line is a statement about THIS BUILD's catalogue, not about
        # medicine: it says a curated reading does not exist here, which is a
        # fact we can check, and leaves the medicine to somebody who can.
        line += "\n_" + _t("genome.no_curated_reading") + "_"
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
    # How well the gene around this position was read. On a gene query the frame
    # above carries it; a single locus has no frame, and «nothing found at this
    # position» in a gene read at eight per cent is the same silence that made a
    # missing row print as «reference». Said only when it is worth saying.
    cov = r.get("coverage") or {}
    if cov.get("state") == "low":
        line += "\n⚠️ _" + _coverage_line(cov) + "_"
    if res.get("note"):
        line += f"\n⚠️ _{res['note']}_"
    if r.get("note"):
        line += f"\n_{r['note']}_"
    for _q in _locus_basis_lines(r):
        line += "\n" + _q
    line += f"\n\n_{r.get('disclaimer','')}_"
    return line


def gene_layers_report(l: Dict[str, Any]) -> str:
    """Which shelves hold anything about this gene, one line each.

    Three outcomes per layer and never two: what it holds, that it holds
    nothing, or that it could not be asked and what would let it be. A layer
    that is silently skipped is the defect this block exists to prevent.
    """
    out = ["**" + _t("gene.layers_header", gene=l.get("gene", "—")) + "**"]
    out += _verdict_lines(l.get("verdict") or {})
    cat = (l.get("catalogue") or {}).get("count") or 0
    out.append("· " + (_t("gene.layer.catalogue", count=cat) if cat
                       else _t("gene.layer.catalogue_none")))
    cv = l.get("clinvar") or {}
    reg = cv.get("region") or {}
    status = cv.get("status")
    # Branched on the STATUS, not on «ok or not». Every status that is not
    # `ok` used to print «the gene's coordinates were not obtained» — and the
    # commonest of them, a scan nobody has run yet, arrives WITH a region and
    # a resolver. The frame then blamed the gene lookup for a missing table,
    # and sent the reader to fetch an annotation file they did not need.
    if status == "ok" and reg:
        out.append("· " + _t("gene.layer.clinvar", count=cv.get("count") or 0,
                             chrom=reg.get("chrom"), start=reg.get("start"),
                             end=reg.get("end"), source=cv.get("resolved_by") or "—"))
        if cv.get("truncated"):
            out.append("  _" + _t("clinvar.truncated_for_gene",
                                  read=cv["truncated"]["read"], of=cv["truncated"]["of"]) + "_")
    elif status == "gene_unresolved":
        out.append("· " + _t("gene.layer.clinvar_unresolved"))
        if cv.get("fix"):
            out.append("  _" + str(cv["fix"]) + "_")
    elif status == "not_run":
        out.append("· " + _t("gene.layer.clinvar_not_run"))
        if cv.get("scan_note"):
            out.append("  _" + str(cv["scan_note"]) + "_")
    else:
        out.append("· " + _t("gene.layer.clinvar_unavailable", status=status or "—"))
        if cv.get("scan_note") or cv.get("fix"):
            out.append("  _" + str(cv.get("scan_note") or cv.get("fix")) + "_")
    ac = l.get("acmg") or {}
    ac_status = ac.get("status")
    if ac.get("in_panel") and ac.get("unread"):
        out.append("· " + _t("gene.layer.acmg_unread"))
    elif ac.get("in_panel") and ac_status == "not_run":
        # «In it, 0 findings» over a panel nobody scanned is a false «clean»
        # on hereditary cancer. The count is a count only once the scan ran.
        out.append("· " + _t("gene.layer.acmg_not_run"))
    elif ac.get("in_panel") and ac_status not in (None, "ok"):
        out.append("· " + _t("gene.layer.acmg_unavailable", status=ac_status))
    elif ac.get("in_panel"):
        out.append("· " + _t("gene.layer.acmg_in",
                             findings=_plural(ac.get("count") or 0, "count.findings")))
    elif ac.get("in_panel") is False:
        out.append("· " + _t("gene.layer.acmg_out"))
    else:
        out.append("· " + _t("gene.layer.acmg_unavailable", status=ac_status or "—"))
    out.append("· " + _coverage_line(l.get("coverage") or {}))
    return "\n".join(out)


def _depth_span(v: Dict[str, Any]) -> str:
    """«26×» when the positions agree, «24–34×» when they do not."""
    lo, hi = v.get("depth_min"), v.get("depth_max")
    if lo is None or hi is None:
        return "—"
    fmt = lambda x: f"{x:g}"                                    # noqa: E731
    return fmt(lo) + "×" if lo == hi else f"{fmt(lo)}–{fmt(hi)}×"


def screen_report(r: Dict[str, Any]) -> str:
    """The second entry: no prescription, a class of disease.

    The list of classes is printed with the answer, always. A reader who is not
    shown which classes are answerable cannot tell a class this build holds
    nothing for from one it has looked at and found nothing in — which is the
    same confusion, one level up, that the whole of this layer exists to undo.
    """
    from .engine.screening import verdict_line as _line
    L = ["**" + _t("screen.title") + "**", ""]
    if r.get("mode") == "class":
        L.append("**" + str(r.get("class_label") or r.get("class") or "—") + "**"
                 + (" · " + _t("screen.scanned_on", date=r["scanned"]) if r.get("scanned") else ""))
        L.append(_line(r.get("verdict") or {}))
        L.append("")
        for row in (r.get("genes") or []):
            line = "· " + _t("screen.gene_row", gene=row.get("gene"),
                             phenotype=row.get("phenotype") or "—",
                             inheritance=row.get("inheritance") or "—")
            if row.get("findings"):
                line += " — " + _t("screen.gene_findings", n=row["findings"])
            if row.get("read") is False:
                line += " — " + _t("screen.gene_unread")
            L.append(line)
        L.append("")
    L += _class_listing(r.get("classes") or r)
    if r.get("disclaimer"):
        L += ["", "_" + r["disclaimer"] + "_"]
    return "\n".join(L)


def _class_listing(c: Dict[str, Any]) -> List[str]:
    """What this build can be asked about, and what it is asked about and cannot."""
    L = ["**" + _t("screen.classes_header") + "**"]
    for row in (c.get("held") or []):
        L.append("· " + _t("screen.class_row", label=row.get("label") or row.get("key"),
                           count=row.get("count") or 0, source=row.get("source") or "—"))
    named = c.get("named") or []
    L += ["", "**" + _t("screen.named_header") + "**"]
    if not named:
        L.append("_" + _t("screen.no_named") + "_")
    for row in named:
        L.append("· " + _t("screen.class_row", label=row.get("label") or row.get("key"),
                           count=row.get("count") or 0, source=row.get("source") or "—"))
    if c.get("refused"):
        L.append("_" + _t("screen.dropped", n=c["refused"]) + "_")
    return L


def _variant_state_line(v: Dict[str, Any]) -> str:
    """On what evidence this build has nothing to report in a gene.

    Four states and not one of them is «the gene is absent» — everybody has the
    gene. Read and matching the reference, held and unread, and held nowhere are
    three different facts, and the first of them is the only one that is a
    finding rather than a gap.
    """
    state = v.get("state")
    if not state:
        return ""
    if state == "variant_called":
        return "_" + _t("decision.variant.variant_called", n=v.get("called") or 0) + "_"
    if state == "no_variant_called":
        line = _t("decision.variant.no_variant_called",
                  n=v.get("confirmed_ref") or 0, total=v.get("positions") or 0,
                  depth=_depth_span(v))
        # The positions with no row are named in the same breath. Two confirmed
        # out of eight held is not «no variants in this gene»; it is a finding
        # about two of them and a gap about six.
        if v.get("unread"):
            line += "; " + _t("decision.variant.and_unread", n=v["unread"])
        return "_" + line + "_"
    if state == "not_read":
        return "_" + _t("decision.variant.not_read", n=v.get("positions") or 0) + "_"
    return "_" + _t("decision.variant.no_positions") + "_"


def _context_lines(ctx: Dict[str, Any]) -> List[str]:
    """The three classes that carry no rule, and the named absence of the list.

    The computed classes are printed by the block below this one — they have
    genotypes to show. These three have only sentences, and a sentence about
    what does not follow from a gene is printed with its source or not at all.

    The last line is the one worth having. Where nobody has written a context
    list for this prescription, the answer says so; a screen that says nothing
    there is completed by whoever is talking to the reader, out of knowledge
    that is not in this build and has passed none of its filters.
    """
    if not ctx:
        return []
    out: List[str] = []
    blocks = ctx.get("blocks") or {}
    for kind in ("mechanism", "asked_about", "no_variant"):
        for row in blocks.get(kind) or []:
            said = (str(row.get("text")) if row.get("text")
                    else _t("decision.not_written_yet"))
            out.append("- **" + str(row.get("gene")) + "** — "
                       + _t("decision.kind." + kind) + ": " + said)
            vs = _variant_state_line(row.get("variant") or {})
            if vs:
                out.append("  " + vs)
            out.append("  _" + _t("decision.source", source=str(row.get("source"))) + "_")
    # Named and unclassified: a gene a clinician put on the list, whose class of
    # link she has not assigned either. Assigning one here would be this program
    # answering a medical question on her behalf.
    for row in ctx.get("named") or []:
        out.append("- **" + str(row.get("gene")) + "** — " + _t("decision.kind.unassigned"))
        out.append("  _" + _t("decision.source", source=str(row.get("source"))) + "_")
    cur = ctx.get("curated") or {}
    # The systems the prescription's class acts on, each with what it handed
    # over: a system whose genetic half is not composed is named as such,
    # because «no genes inherited» from it is a fact about the build.
    for s in cur.get("systems") or []:
        out.append("_" + (_t("decision.system_reached", system=s.get("key"), n=s.get("genes") or 0)
                          if s.get("status") == "composed"
                          else _t("decision.system_not_composed", system=s.get("key"))) + "_")
    if cur.get("excluded"):
        out.append("_" + _t("decision.excluded_by_clinician", genes=", ".join(cur["excluded"])) + "_")
    if not cur.get("asked"):
        out.append("_" + _t("decision.no_context_list") + "_")
    elif cur.get("refused"):
        # Dropped entries are counted out loud. One that vanishes quietly is
        # indistinguishable from one that was never written, and the gate that
        # dropped it then looks like an empty file.
        out.append("_" + _t("decision.entries_without_source", n=cur["refused"]) + "_")
    if out:
        out.append("")
    return out


def _gene_coverage_note(ge: Dict[str, Any]) -> str:
    """The coverage line for a gene on the prescription path, or nothing.

    One state is silent and it is `fine`, which means «not unusual for this
    file» and never «enough»: sufficiency depends on the question, and the
    product does not know the question. Every other state speaks, because on
    this screen a silence is read as permission.
    """
    c = ge.get("coverage") or {}
    if not c or c.get("state") == "fine":
        return ""
    return "_" + _coverage_line(c) + "_"


def _locus_qualifier_lines(item: Dict[str, Any]) -> List[str]:
    """Everything about one locus that must not be lost to the one-line cut.

    The curated note, the note about THIS read, and the named refusal. They are
    the three things that change what the genotype on the line above is worth.
    """
    out: List[str] = []
    res = item.get("result") or {}
    if res.get("note"):
        out.append("⚠️ _" + str(res["note"]) + "_")
    if item.get("note"):
        out.append("_" + str(item["note"]) + "_")
    out += _locus_basis_lines(item)
    return out


def _locus_basis_lines(item: Dict[str, Any]) -> List[str]:
    """The named refusal a locus with nothing behind it has to carry.

    Four of the five states already print something of their own — a rule, a
    note, a verdict about the gene, or the fact that the pair is recognised. The
    fifth printed a genotype and stopped, and a genotype that stops is read as a
    finding. Nothing here interprets: the line says this build holds no reading
    for the position, which is a fact about the build.
    """
    b = item.get("basis") or {}
    if b.get("kind") == "none":
        return ["_" + _t("genome.locus_no_basis") + "_"]
    if b.get("kind") == "pair":
        return ["_" + _t("genome.locus_pair_only", gene=b.get("gene") or "—") + "_"]
    return []


def _verdict_lines(v: Dict[str, Any]) -> List[str]:
    """The curated verdict about the gene, with where it came from.

    Two lines and never one: the sentence, and the file it is quoted from. A
    verdict of this kind says what does not follow from a gene, which is as much
    a medical statement as saying what does — and this project prints neither
    without an attributable origin.
    """
    if not v.get("text"):
        return []
    return ["⚖️ " + _t("gene.verdict", text=v["text"]),
            "  _" + _t("gene.verdict_source", source=v.get("source") or "—") + "_"]


def _coverage_line(c: Dict[str, Any]) -> str:
    """One line about how well this gene was read.

    `fine` is deliberately terse and deliberately not «adequate»: the product
    does not know what the reader's question needs, only that this gene is not
    unusual for this file. Every other state carries its number.
    """
    state = c.get("state")
    if state == "low":
        return _t("gene.coverage.low", pct=c.get("pct_20x"),
                  median=c.get("median_pct_20x"))
    if state == "fine":
        return _t("gene.coverage.fine", pct=c.get("pct_20x"))
    if state == "gene_not_in_table":
        return _t("gene.coverage.not_in_table", n=c.get("table_size") or 0)
    if state == "unavailable":
        # A table that could not be read, told apart from one nobody made:
        # «not measured» sends the reader to run the measurement, and here the
        # measurement exists.
        return _t("gene.coverage.unavailable", reason=c.get("reason") or "—")
    return _t("gene.layer.coverage_no")


def clinvar_gene_report(r: Dict[str, Any]) -> str:
    """ClinVar findings inside one gene."""
    g = r.get("gene") or "—"
    if r.get("status") != "ok":
        return f"⚠️ {g} — " + str(r.get("fix") or r.get("scan_note")
                                  or _t("genome.refused.no_answer"))
    reg = r.get("region") or {}
    head = ("**" + g + "** — "
            + _t("gene.layer.clinvar", count=r.get("count") or 0,
                 chrom=reg.get("chrom"), start=reg.get("start"),
                 end=reg.get("end"), source=r.get("resolved_by") or "—"))
    if r.get("scanned") is not None:
        head += _t("clinvar.gene_of_scanned",
                   total=_plural(int(r["scanned"]), "count.findings"))
    if r.get("truncated"):
        head += "\n_" + _t("clinvar.truncated_for_gene",
                           read=r["truncated"]["read"], of=r["truncated"]["of"]) + "_"
    if not r.get("hits"):
        return head
    return head + "\n" + clinvar_report({**r, "status": "ok",
                                         "count": r.get("count"),
                                         "disclaimer": r.get("disclaimer", "")})


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
             + (" · " + _t("prescription.source", value=src) if src else "")]
    # The judgement about the DECISION, above the sections that make it. The line
    # at the top of this card grades interactions, labs and flags together; what
    # it never said is whether anything genetic bears on the choice at all, and
    # that is the question the card is opened with.
    ctx = r.get("genetic_context") or {}
    if ctx.get("verdict"):
        from .engine.decision import verdict_line as _verdict_line
        lines.append("🧬 " + _verdict_line(ctx["verdict"]))
    lines.append("")

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
    lines += _context_lines(r.get("genetic_context") or {})
    g = r.get("genome", {})
    genes = g.get("genes", [])
    if not genes:
        cp = g.get("cpic") or {}
        lines.append("_" + _t("prescription.no_pgx",
                              date=cp.get("snapshot") or _t("common.unknown_date")) + "_"
                     if cp.get("asked") else
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
            elif ge.get("needs_full_diplotype"):
                # The tag SNPs are real readings and stay visible — under a name
                # that says what they are. Printed as the gene's variants, beside
                # the word «important», «rs3892097 A/A» is read as the answer, and
                # for this gene a tag SNP cannot be one.
                lines.append(f"- **{ge['gene']}** ({lvl}{tag}): {ge.get('label','')}")
                tm = ", ".join(f"`{m.get('rsid')}` {m.get('genotype','')}"
                               for m in ge.get("tag_markers", []))
                if tm:
                    lines.append("    · " + _t("prescription.tag_snps_only", list=tm))
                if ge.get("closes"):
                    lines.append("    · " + ge["closes"])
            else:
                mk = ", ".join(f"`{m.get('rsid')}` {m.get('genotype','')}" for m in ge.get("markers", []))
                pre = _t("prescription.variants", list=mk) + "; " if mk else ""
                lines.append(f"- **{ge['gene']}** ({lvl}{tag}): {pre}{ge.get('label','')}")
            # After the branch, not inside it. Put between the `if` and its
            # `elif` this line broke the chain: a gene that could be phenotyped
            # and had nothing to say about its coverage fell through to the
            # generic branch and printed twice, and a gene that could NOT be
            # phenotyped but did have a coverage note printed the note INSTEAD
            # of its own answer. How well a gene was read qualifies whichever
            # answer was given; it does not choose between them.
            _cov = _gene_coverage_note(ge)
            if _cov:
                lines.append("  " + _cov)

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
    # What the comparison deliberately did not include. Printed whether or not
    # anything was found: a warning that disappears because a drug was stopped and
    # a warning nobody computed read the same on the page, and only one of them is
    # good news.
    base = inter.get("baseline") or {}
    excluded = base.get("excluded") or []
    if excluded:
        lines.append("_" + _t("prescription.excluded_from_check",
                              names=", ".join(f"{e.get('name')} ({e.get('status')})"
                                              for e in excluded[:6])) + "_")
    no_status = base.get("status_not_recorded") or []
    if no_status:
        lines.append("_" + _t("prescription.status_not_recorded",
                              names=", ".join(no_status[:6])) + "_")

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
            if t.get("distinguishable") is False:
                tr += " · " + _t("labs.below_own_scatter",
                                 pct=t["change_floor"]["rcv_pct"],
                                 pairs=t["change_floor"]["pairs"])
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
        # What the latest month stands on. A month averaged over nineteen nights of
        # thirty-one is not the month, and the number alone cannot say so.
        cov = m.get("coverage") or {}
        cvr = (" · " + _t("lifestyle.coverage", n=cov["n"], days=cov["days"])
               if cov.get("n") and cov.get("days") and cov["n"] < cov["days"] else "")
        lines.append(f"{icon.get(m.get('status'),'•')} {m['label']}: **{_n(m['value'])} {m['unit']}**".rstrip()
                     + f" ({m['date']}){tr}{improv}{brk}{cvr}")
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


def _prs_measurement_line(t: Dict[str, Any]) -> str:
    """Stability of the number and informativeness of the model, one line.

    Each figure that is not on the machine is named as absent rather than left
    out: a line with three numbers and a line with one look alike only when the
    missing two are not mentioned.
    """
    st = t.get("stability") or {}
    inf = t.get("informativeness") or {}
    stab = []
    if st.get("ancestry_spread_pp") is not None:
        stab.append(_t("prs.stab_ancestry", pp=st["ancestry_spread_pp"],
                       pops=_plural(int(st.get("populations") or 0), "count.populations")))
    else:
        stab.append(_t("prs.stab_ancestry_missing"))
    if st.get("models_spread_pp") is not None:
        stab.append(_t("prs.stab_models", pp=st["models_spread_pp"],
                       models=_plural(int(st.get("models_scored") or 0), "count.models")))
    else:
        stab.append(_t("prs.stab_models_missing"))
    if st.get("coverage_pct") is not None:
        stab.append(_t("prs.stab_coverage", pct=st["coverage_pct"]))
    info = []
    if inf.get("auroc") is not None:
        info.append(_t("prs.info_auroc", auroc=inf["auroc"]))
    if inf.get("p90_vs_p10_ratio") is not None:
        info.append(_t("prs.info_ratio", kind=inf.get("kind"), x=inf["p90_vs_p10_ratio"]))
    elif inf.get("p90_vs_p10_shift") is not None:
        info.append(_t("prs.info_shift", value=inf["p90_vs_p10_shift"]))
    if not info:
        info.append(_t("prs.info_missing"))
    return _t("prs.measure_line", stability=" · ".join(stab), informativeness=" · ".join(info))


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
            lines.append("      ↳ " + _prs_measurement_line(t))
        lines.append("")
    for c in (r.get("method_caveats") or []):
        lines.append("· " + c["note"])
    if r.get("method_caveats"):
        lines.append("")
    lines.append(_t("prs.evidence_legend"))
    lines.append(_t("prs.measure_legend"))
    lines.append("")
    for c in r.get("categories", []):
        lines.append(f"__{c['category']}__")
        for t in c.get("traits", []):
            p = t.get("percentile")
            ps = f"P{round(p)}" if isinstance(p, (int, float)) else _t("prs.no_model")
            warn = "" if t.get("reliable") else " ⚠"
            ev = {"clinical": " ✚", "supportive": " ·"}.get(t.get("evidence"), "")
            lines.append(f"  {t['label']}: {ps}{warn}{ev}")
            lines.append("    ↳ " + _prs_measurement_line(t))
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
    # Only when it is worth saying. A line printed on every run is a line nobody
    # reads by the third one, and «this build is two days old» is not news.
    b = r.get("build") or {}
    if b.get("status") == "ageing":
        head += "\n" + _t("overview.build_ageing", version=b.get("installed") or "—",
                          released=b.get("released") or "—",
                          ago=_plural(int(b.get("days") or 0), "count.days"))
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


def _pgx_mark(name: str) -> str:
    """Whether this entry can take part in a pharmacogenetic answer at all.

    A regimen of thirty supplements produced «no interactions found», which is
    true and tells the reader nothing: omega-3 and inositol are not in the model
    and never could be. Which of them the model can even speak about was only
    discoverable afterwards, by running another command.
    """
    try:
        from . import core
        q = (name or "").strip().lower()
        if not q:
            return ""
        for entry in core.cpic_kb().get("drugs", []):
            for n in entry.get("names", []):
                # Equality, or one name contained in the other AND long enough
                # for the containment to mean something. The bare substring rule
                # this was copied from lives inside a lookup where the caller has
                # already typed a drug name; here it labels a LIST, and «и» — one
                # letter of a supplement's name — matched «ипп» and earned a
                # vitamin the tag «pharmacogenetics: CYP2C19».
                if q == n or (min(len(q), len(n)) >= 4 and (q in n or n in q)):
                    return " " + _t("medications.in_pgx", gene=entry.get("gene") or "—")
    except Exception as exc:                                         # noqa: BLE001
        # An empty mark means «outside the model» — the legend says so under
        # the list. A base that could not be READ returned the same empty
        # mark, so one unreadable file declared every drug in the regimen
        # pharmacogenetically irrelevant. The failure is a mark of its own.
        return " " + _t("medications.pgx_unavailable", reason=type(exc).__name__)
    return ""


#: The most of a prescription note that the LIST prints. These notes are prose
#: somebody wrote at the time, and a «first sentence» can itself run for three
#: hundred characters; `--json` and `prescription` carry the whole of it.
NOTE_FOLD_CEILING = 150

#: Abbreviations a full stop does not end a sentence after. A fold that cut at
#: «e.g. » printed «Take with food, e.g…» and lost the example it was folding
#: to keep. Short on purpose: the cases seen in real notes, not a dictionary.
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "т.е.", "т.к.", "напр.", "др.")


def _first_sentence(note: str) -> str:
    """The first sentence of a note, with the ceiling above applied to it."""
    start = 0
    head = note
    while True:
        cut = note.find(". ", start)
        if cut < 0:
            break
        before = note[:cut + 1]
        if any(before.endswith(a) for a in _ABBREVIATIONS):
            start = cut + 1
            continue
        head = before[:-1]
        break
    head = head.strip()
    if len(head) > NOTE_FOLD_CEILING:
        head = head[:NOTE_FOLD_CEILING].rsplit(" ", 1)[0]
    return head


def _status_mark(m: Dict[str, Any]) -> str:
    """The status of an entry that is NOT current, for a listing.

    Every place that lists the regimen printed a stopped drug in the same
    shape as one taken this morning. The comparison already excluded it —
    and a list that does not say so shows the reader a regimen the engine
    is not using.
    """
    from . import core
    if core.is_active_medication(m):
        return ""
    return " " + _t("medications.not_current", status=m.get("status") or "—")


def medications_report(r: Dict[str, Any]) -> str:
    meds = r.get("medications") or []
    if not meds:
        return _t("medications.empty")
    out = [_t("medications.header", n=len(meds))]
    for m in meds:
        line = (f"  · {m.get('name', '?')}" + _status_mark(m)
                + _pgx_mark(m.get("name")))
        if m.get("dose"):
            line += f" — {m['dose']}"
        # The note is kept and no longer printed in full on the list. Entries in
        # this profile carry up to fifteen hundred characters of history each,
        # and a list of forty-five of them is not a list a person reads. The
        # first sentence says what it is; `--json` and `prescription` carry all
        # of it, which is where the detail was always meant to be read.
        note = (m.get("note") or "").strip()
        if note:
            head = _first_sentence(note)
            line += f" ({head}…)" if len(note) > len(head) + 2 else f" ({head})"
        out.append(line)
    out.append("")
    out.append(_t("medications.pgx_legend"))
    return "\n".join(out)


def _catalogue_size() -> int:
    """How many positions the curated catalogue actually holds.

    Written the day a locus was added to it. Several sentences in this build
    carried the number as a word, and they were stale before anybody noticed: the
    catalogue had grown from 54 to 60 while the screens still said 54. A count
    that lives in prose goes stale the first time somebody does the very thing
    the prose describes.
    """
    try:
        from . import genome
        return len((genome.loci() or {}).get("loci") or {})
    except Exception:
        return 0


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
                              per_mb=tb.get("observed_per_mb"), share=0,
                              coding_per_mb=tb.get("coding_per_mb") or 0))
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
                          coding_per_mb=cs.get("coding_per_mb") or 0,
                          share=int(round((cs.get("imputed_share") or 0) * 100))))
        paths = r.get("paths") or []
        if paths:
            # The frame, before the findings. A reader who meets an answer without
            # the question set it belongs to fills the set in themselves, and
            # fills it in wrong: pharmacogenetics arrives looking like everything
            # that was there to find.
            out.append(_t("genome_status.paths_head"))
            for it in paths:
                name = _t("paths." + it["path"], n=_catalogue_size())
                out.append(_t("genome_status.path_open", name=name) if it.get("open")
                           else _t("genome_status.path_closed", name=name,
                                   why=_t("paths.why." + (it.get("why") or "no_genome"))))
        if r.get("engine") == "linear":
            # The reader that needs no index is not a detail of implementation
            # here: it changes how long the first question takes, and a person
            # who is not told that reads the wait as a hang.
            out.append(_t("genome_status.no_index_linear"))
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


def _level_counts_line(counts: Dict[str, int]) -> str:
    parts = [f"{k} — {counts[k]}" for k in ("A", "B", "C", "D", "E") if counts.get(k)]
    return _t("system.genetics.levels", levels=", ".join(parts) or "—", none=counts.get("none", 0))


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
            L.append(_t("limits.coverage_weak_line",
                        genes=_plural(cov["weak_total"], "count.genes")))
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
        order = {"conclusion_not_extracted": 0, "unclassified": 1, "no_text": 2,
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


# ---- the update procedure (scholion version) ---------------------------------
def spelling_note(tail: str = "recompute") -> str:
    """One line, only where it is needed: how this machine spells the commands just printed.

    Empty when `scholion` is a word the shell knows, which is the usual case and
    deserves no line at all."""
    from . import recompute as _rc  # noqa: E402
    prefix = _rc.program_prefix()
    if prefix == "scholion":
        return ""
    return _t("command.spelled_here", prefix=prefix, example=f"{prefix} {tail}".strip())


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
        lines.append(_t("update.how.source" if route.get("kind") == "source" else "update.how.install",
                        command=command))
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


def recompute_why(step: Dict[str, Any]) -> str:
    why = step.get("why")
    if not why:
        return ""
    d = step.get("detail") or {}
    positions = d.get("positions")
    return _t("recompute.why." + str(why), file=d.get("file") or "—", engine=d.get("engine") or "—",
              domain=d.get("domain") or "—",
              positions=_plural(int(positions), "count.positions") if isinstance(positions, int) else "—")


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
    head = _t("recompute.not_confirmed") if reason == "not_confirmed" else _t("recompute.nothing_ready")
    return head + ("\n\n" + recompute_plan_report(r["plan"]) if r.get("plan") else "")


def recompute_stop_report(r: Dict[str, Any]) -> str:
    return _t("recompute.stop_requested") if r.get("ok") else _t("recompute.stop_not_running")


def coverage_report(r: Dict[str, Any]) -> str:
    """What the coverage measurement did, or why it did nothing."""
    st = r.get("status")
    if st == "written":
        line = _t("coverage.done", genes=_plural(int(r.get("genes") or 0), "count.genes"),
                  seconds=r.get("seconds") if r.get("seconds") is not None else "—",
                  path=r.get("path") or "—")
        if r.get("without_clinvar"):
            line += "\n" + "_" + _t("coverage.without_clinvar", n=r["without_clinvar"]) + "_"
        return line
    if st == "stopped":
        return _t("coverage.stopped", measured=r.get("measured") or 0, genes=r.get("genes") or 0)
    if st == "failed":
        return _t("coverage.failed", error=(r.get("error") or "").strip() or "—")
    return "✗ " + recompute_why({"why": r.get("reason") or "no_bam", "detail": {}})


def genotype_sites_report(r: Dict[str, Any]) -> str:
    st = r.get("status")
    if st == "written":
        return _t("sites.done", positions=_plural(int(r.get("positions") or 0), "count.positions"),
                  assembly=r.get("assembly") or "—",
                  chromosomes=_plural(int(r.get("chromosomes") or 0), "count.chromosomes"),
                  seconds=r.get("seconds") if r.get("seconds") is not None else "—",
                  path=r.get("path") or "—")
    if st == "failed":
        return _t("sites.failed", step=r.get("step") or "—", rc=r.get("rc") if r.get("rc") is not None else "—",
                  error=(r.get("error") or "").strip() or "—")
    if st == "stopped":
        return _t("sites.stopped")
    return "✗ " + recompute_why({"why": r.get("reason") or "no_vcf", "detail": {}})


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


def genotype_conclusion_lines(positions: List[Dict[str, Any]]) -> List[str]:
    """The genotype of a system as one conclusion — assembled from the panel's
    own sentences, never phrased here: which named alleles were found and what
    the panel says of each, which were not carried, which were not read."""
    # A position with no reading at all — no genome, a build nobody could tell —
    # is not read, whatever its state says; «none found» over such a panel
    # would claim a check that never happened.
    found = [p for p in positions if p.get("read") is True and p.get("state") in ("het", "hom")]
    absent = [p for p in positions if p.get("read") is True and p.get("state") == "absent"]
    unread = [p for p in positions if p.get("read") is not True]
    name = lambda p: f"{p.get('gene')} {p.get('rsid') or ''}".strip()
    L = ["**" + _t("system.panel.conclusion_h") + "**"]
    if found:
        L.append(_t("system.panel.conclusion_found", found=len(found),
                    positions=_plural(len(positions), "count.positions"),
                    genes=", ".join(name(p) for p in found)))
        L += ["  · " + (p.get("text") or name(p)) for p in found]
    elif len(unread) < len(positions):
        L.append(_t("system.panel.conclusion_none_found",
                    positions=_plural(len(positions) - len(unread), "count.positions")))
    if absent:
        L.append(_t("system.panel.conclusion_absent", genes=", ".join(name(p) for p in absent)))
    if unread:
        L.append(_t("system.panel.conclusion_unread",
                    positions=_plural(len(unread), "count.positions"),
                    genes=", ".join(name(p) for p in unread)))
    # The genotype against the measurements, in the same words as the page: a
    # found position that names a marker is a question (printed among the
    # questions); none found says so; the alleles not carried say what did not apply.
    L.append("**" + _t("system.panel.compare_h") + "**")
    if not any(p.get("expect") for p in found):
        L.append(_t("system.panel.compare_none"))
    na: Dict[str, List[str]] = {}
    for p in absent:
        if p.get("expect"):
            na.setdefault(p["expect"].get("name") or p["expect"].get("marker") or "—", []).append(name(p))
    L += [_t("system.panel.compare_absent", name=k, positions=", ".join(v)) for k, v in sorted(na.items())]
    return L


def panel_report(r: Dict[str, Any]) -> str:
    """The panel as the catalogue describes it — for a clinician, with the references."""
    if r.get("status") == "unknown_system":
        return "✗ " + _t("system.unknown", key=r.get("key"), systems=", ".join(r.get("systems") or []))
    if "systems" in r and "positions" not in r:
        L = ["**" + _t("panel.list_h") + "**"]
        for s_ in r["systems"]:
            L.append("· " + _t("panel.list_row", label=s_.get("label"), key=s_.get("key"),
                               positions=_plural(int(s_.get("positions") or 0), "count.positions"),
                               unreadable=s_.get("unreadable") or 0))
        return "\n".join(L)
    c = r.get("counts") or {}
    L = ["**" + _t("panel.title", label=r.get("label") or r.get("key")) + "**",
         _t("panel.counts", positions=_plural(int(c.get("positions") or 0), "count.positions"),
            genes=_plural(int(c.get("genes") or 0), "count.genes"), with_study=c.get("with_study") or 0,
            with_expectation=c.get("with_expectation") or 0, signed=c.get("signed_by_clinician") or 0),
         _t("panel.source", updated=r.get("catalogue_updated") or "—")]
    for g in r.get("genes") or []:
        L += ["", "**" + str(g.get("gene")) + "**"]
        for p in g.get("positions") or []:
            head = f"· **{p.get('rsid') or '—'}**"
            if p.get("protein"):
                head += f" {p['protein']}"
            head += " — " + _t("system.kind." + str(p.get("kind") or "unassigned")) + \
                    "; " + _t("system.mode." + str(p.get("mode") or "unknown"))
            L.append(head)
            L.append("  " + _t("panel.locus", hgvs=p.get("hgvs") or "—", allele=p.get("risk_allele") or "—"))
            for state in ("het", "hom"):
                if (p.get("text") or {}).get(state):
                    L.append("  " + _t("panel.state." + state) + ": " + p["text"][state])
            if p.get("classification"):
                L.append("  " + _t("panel.classification", classification=p["classification"],
                                   moi=p.get("moi") or "—", disease=p.get("disease") or "—"))
            if p.get("expect"):
                e = p["expect"]
                L.append("  " + _t("panel.expect", marker=e.get("marker") or "—",
                                   direction=e.get("direction") or "—", note=e.get("note") or "—"))
            if p.get("effect_size"):
                L.append("  " + _t("panel.effect", effect=p["effect_size"]))
            L.append("  " + _t("panel.source_row", source=p.get("source") or "—",
                               study=p.get("study") or "—"))
            L.append("  " + _t("panel.signed." + str(p.get("signature") or "open"),
                               on=p.get("signed_on") or "—",
                               curated=p.get("curated_on") or "—"))
    for u in r.get("unreadable") or []:
        L += ["", "**" + str(u.get("gene")) + "** — " + _t("panel.unreadable", reason=u.get("reason") or "—",
                                                            source=u.get("source") or "—")]
    if r.get("disclaimer"):
        L += ["", "_" + str(r["disclaimer"]) + "_"]
    return "\n".join(L)


# The system card and the pages beside it live in `format_system.py` since
# 18.09.2026; the names stay reachable here, because every face and every
# test calls them at this address.
from .format_system import (_names, _system_gene_row, _system_polygenic, _correction_route_lines, system_report, _test_row, systems_report, _panel_lines, evidence_levels_report)  # noqa: E402,F401
