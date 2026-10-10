"""The genome: a locus, a gene, a region, ClinVar, ACMG, polygenic scores, longevity, coverage.

Split out of `format.py`; every face still calls these names through `format`,
which re-exports them."""
from __future__ import annotations

from typing import Any, Dict, List, Optional  # noqa: F401

from .i18n import plural as _plural, t as _t  # noqa: F401
from .format_primitives import _coverage_line, recompute_why, subclaim_lines
from .genome_routes import route_text
from .clinical_claims import basis_lines


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
    if r.get("status") not in (None, "ok"):
        # Every refusal, by construction rather than by list: `assembly_mismatch`
        # and `contig_not_in_file` were missing from the list this replaced and
        # printed as «variants in the gene: 0» (task 209). The gene is known, the
        # input is what cannot carry a region — say that, never a count.
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
            lines.append(f"- {p.get('title') or p.get('id')}: {p.get('text') or _t('clinical.withheld')}")
            lines.extend(basis_lines(p))
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
    from .pgs_validation import percentile_label
    if not r.get("available"):
        return r.get("message", _t("prs.not_ready"))
    s = r.get("stats", {})
    lines = [_t("prs.title") + " · "
             + _t("prs.reliable", reliable=s.get("reliable"), total=s.get("total")) + " · "
             + _t("prs.reference", population=s.get("superpopulation", "EUR")), ""]
    if s.get("population_note"):
        lines += [s["population_note"], ""]
    for w in (r.get("withheld_by_sex") or []):
        lines.append("· " + str(w.get("label")) + " — " + str(w.get("note")))
    if r.get("withheld_by_sex"):
        lines.append("")
    high = r.get("high", [])
    if high:
        lines.append(_t("prs.above_average"))
        for t in high:
            p = t.get("percentile")
            lines.append(f"  🔶 {t['label']}: {percentile_label(p)}"
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
            ps = percentile_label(p) if isinstance(p, (int, float)) else _t("prs.no_model")
            warn = "" if t.get("reliable") else " ⚠"
            ev = {"clinical": " ✚", "supportive": " ·"}.get(t.get("evidence"), "")
            lines.append(f"  {t['label']}: {ps}{warn}{ev}")
            if t.get("calibration_note"):
                lines.append("    " + t["calibration_note"])
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
        lines.extend(basis_lines(ap, compact=True))
        lines.append("")
    lines.append(_t("longevity.key_markers"))
    for k in r.get("known", []):
        mk = " ✔" + _t("longevity.carries") if k.get("carries_named_allele") is True else ""
        lines.append(f"  {k['gene']} {k['rsid']}: {k.get('genotype') or '—'}{mk} — {k.get('note') or ''}")
        for field in ('label', 'verdict_label', 'action', 'zygosity_note', 'population_note'):
            if k.get(field):
                lines.append('  ' + str(k[field]))
        lines.extend(basis_lines(k, compact=True))
    st = r.get("stats", {})
    genes = ", ".join(g["gene"] for g in r.get("significant_genes", [])[:16])
    lines.append("\n" + _t("longevity.significant",
                           carriers=st.get("significant_carriers"),
                           genes=_plural(st.get("significant_genes") or 0, "count.genes_in")))
    if genes:
        lines.append(_t("longevity.genes_first", genes=genes))
    lines.append(f"\n_{r.get('disclaimer','')}_")
    return "\n".join(lines)


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
    except Exception:  # quiet: the size only labels a path of the catalogue; it says nothing about the person
        return 0


def genome_status_report(r: Dict[str, Any]) -> str:
    text = _genome_status_body(r)
    pop = r.get("population") or {}
    return text + ("\n\n" + pop["note"] + "\n" + pop.get("scope", "") if pop.get("note") else "")


def _genome_status_body(r: Dict[str, Any]) -> str:
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


def weak_bed_report(r: Dict[str, Any]) -> str:
    """The BED itself when there is one, so `limits --bed > file` is the file.

    Everything else — a refusal, an empty list, a file already written — is a
    sentence, because there is nothing a laboratory could read in it.
    """
    if r.get("ok") and r.get("written"):
        return _t("limits.bed_written", path=r["written"], n=r.get("regions", 0))
    if r.get("ok") and r.get("bed"):
        return r["bed"].rstrip("\n")
    return r.get("note") or ""


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
        L.extend(basis_lines(x))
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
        if lpa.get('what_to_do'):
            L.append('- ' + lpa['what_to_do'])
        L.extend(basis_lines(lpa))
    if lpa.get("estimate"):
        e = lpa["estimate"]
        L.append(f"- {e.get('label','')}: {e.get('percentile')} ({e.get('pgs_id')}, "
                 f"{e.get('quality')})")
        L.append(f"  ⚠ {lpa.get('estimate_is_not_a_measurement','')}")
    L += ["", f"_{r.get('disclaimer','')}_"]
    return "\n".join(L) + "\n"


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
    if r.get("reason") == "assembly_mismatch":
        return "✗ " + _t("coverage.why.assembly_mismatch")
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


def panel_report(r: Dict[str, Any]) -> str:
    """The panel as the catalogue describes it — for a clinician, with the references."""
    from .panel_notes import note_lines
    from .panel_reference import reference_lines
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
    L.append(_t("panel.withheld_count", n=c.get("withheld_interpretations") or 0))
    if r.get("reading_note"):
        L.append(r["reading_note"])
    for g in r.get("genes") or []:
        L += ["", "**" + str(g.get("gene")) + "**"]
        for p in g.get("positions") or []:
            head = f"· **{p.get('rsid') or '—'}**"
            if p.get("protein"):
                head += f" {p['protein']}"
            head += " — " + _t("system.kind." + str(p.get("kind") or "unassigned")) + \
                    "; " + _t("system.mode." + str(p.get("mode") or "unknown"))
            L.append(head)
            L += ["  " + detail for detail in reference_lines(p)]
            if route_text(p):
                L.append('  ' + route_text(p))
            if p.get("reading"):
                L.append("  " + p["reading"]["message"])
                if p.get("value_only"):
                    L.append("  " + _t("panel.value_only"))
                if p["reading"].get("quality"):
                    L.append("  " + _t("panel.reading.quality") + ": " +
                             str(p["reading"]["quality"]))
            if p.get("disposition"):
                L.append("  " + _t("panel.intake." + p["disposition"]) +
                         (" — " + str(p["reason"]) if p.get("reason") else "") +
                         (" (" + _t("panel.intake.task", task=p["task"]) + ")" if p.get("task") else ""))
            L.append("  " + _t("panel.locus", hgvs=p.get("hgvs") or "—", allele=p.get("risk_allele") or "—"))
            if p.get("author_note"):
                L.append("  " + note_lines(p["author_note"]).replace("\n", "\n  "))
            for state in ("het", "hom", "hemi"):
                if (p.get("text") or {}).get(state):
                    L.append("  " + _t("panel.state." + state) + ": " + p["text"][state])
            if p.get("mechanism") and p.get("source"):
                L.append("  " + _t("system.row.mechanism", text=p["mechanism"]))
            if (p.get("conclusion_basis") or {}).get("status") == "incomplete":
                L.append("  " + p["conclusion_basis"]["reason"])
            L += ["  " + detail for detail in subclaim_lines(p)]
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
