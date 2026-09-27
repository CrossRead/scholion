"""A drug: the pharmacogenetic check, the second opinion on a prescription, the list of prescriptions.

Split out of `format.py`; every face still calls these names through `format`,
which re-exports them."""
from __future__ import annotations

from typing import Any, Dict, List, Optional  # noqa: F401

from .i18n import plural as _plural, t as _t  # noqa: F401
from .format_primitives import _LEVEL_ICON, _SEV_ICON, _clinvar_block, _context_lines, _decision_suffix, _first_sentence, _gene_coverage_note, _mark_icon, _near_suffix, _status_mark


def drug_check(r: Dict[str, Any]) -> str:
    if r["status"] == "error":
        return f"⚠️ {r['message']}"
    if r["status"] in ("not_in_panel", "not_found", "not_checked"):
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
            lines.append("> ")
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


def _rx_safety_lines(r: Dict[str, Any]) -> List[str]:
    """Red flags from the person's own file — printed first, above every computed section."""
    lines: List[str] = []
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
    return lines


def _rx_genome_lines(r: Dict[str, Any]) -> List[str]:
    """🧬 The person's genome for this drug: the rule, the genes, how well each was read."""
    lines: List[str] = []
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
    return lines


def _rx_labs_lines(r: Dict[str, Any]) -> List[str]:
    """🧪 The labs this drug is monitored by, and which of them are already out of range."""
    lines: List[str] = []
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
    return lines


def _rx_interactions_lines(r: Dict[str, Any]) -> List[str]:
    """🔗 The current prescriptions: what interacts, and what the comparison left out."""
    lines: List[str] = []
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
    return lines


def _rx_dose_lines(r: Dict[str, Any]) -> List[str]:
    """⚖ The dose and critical context, when the drug has an entry in the dose layer."""
    lines: List[str] = []
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
    return lines


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

    lines += _rx_safety_lines(r)

    lines += _rx_genome_lines(r)

    lines += _rx_labs_lines(r)

    lines += _rx_interactions_lines(r)

    cvb = _clinvar_block(r.get("clinvar"))
    if cvb:
        lines.append(cvb)

    lines += _rx_dose_lines(r)

    lines.append(f"\n_{r.get('disclaimer','')}_")
    return "\n".join(lines)


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
                # Now the same whole-word rule as the lookup itself: «нистатин»
                # held «статин» and was labelled a statin with an SLCO1B1 note.
                from .engine.pgx import name_matches
                if name_matches(q, n):
                    return " " + _t("medications.in_pgx", gene=entry.get("gene") or "—")
    except Exception as exc:                                         # noqa: BLE001
        # An empty mark means «outside the model» — the legend says so under
        # the list. A base that could not be READ returned the same empty
        # mark, so one unreadable file declared every drug in the regimen
        # pharmacogenetically irrelevant. The failure is a mark of its own.
        return " " + _t("medications.pgx_unavailable", reason=type(exc).__name__)
    return ""


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
