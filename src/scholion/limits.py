"""What cannot be said from this person's data, and what would change that.

Every other command answers a question. This one states the questions that have
no answer yet — and it exists as its own command because a limitation that is
only ever mentioned inside another report is a limitation nobody can point at.

The reasoning behind it is the project's oldest rule, and it is not modesty. A
gene read at 70 % of its bases yields the same «no findings» as a gene read at
100 %. A pharmacogenetic phenotype computed from half a panel comes back
«normal». A polygenic score on a model whose variants were 58 % called still
prints a percentile. In each case the output is indistinguishable from the
confident one, so the only place the difference can live is a statement about
what was NOT read — and that statement has to be reachable in one command,
otherwise it is decoration.

**Every entry says three things**: what cannot be concluded, why, and what would
close it. The third is what makes this a work order rather than a shrug. Where
the answer is a guess rather than a fact, it says «assumed» and names what would
make it certain.

Coverage is published here rather than kept as an internal layer, which is also
what the standards ask for: ACMG 2013 puts the disclosure of achieved coverage in
the report as a «must», EuroGentest STATEMENT 23 and ISO 15189 say the same. The
number itself is computed by `src/ingest/qc_callability.sh` into
`profile/callability.tsv` — it was being computed and read by nothing.
"""
from __future__ import annotations

import csv
from typing import Any, Dict, List, Optional

from . import core
from .i18n import t as _t
from .i18n import plural as _plural

#: Below this fraction of bases at ≥10× a gene cannot be called negative. 10× is
#: the depth at which a heterozygote is decided at all — see qc_callability.sh,
#: which uses the same threshold; the number is not repeated here by coincidence.
#: AN AUTHOR SETTING — see AUTHOR_SETTINGS below.
WEAK_10X = 90.0

#: A polygenic score whose model is called below this is a number without a
#: population behind it. The same threshold the PGS layer uses to withdraw a
#: percentile from trust. AN AUTHOR SETTING — see AUTHOR_SETTINGS below.
PRS_MIN_MATCH = 0.90

#: EVERY NUMBER IN THIS PROJECT THAT NOBODY PUBLISHED.
#:
#: The reviewers' strongest single correction: three of the four numeric
#: thresholds in the lab and genome layers were described in our own notes as
#: «considered engineering decisions», and they are nothing of the kind. They are
#: an author's preferences. That is allowed — a product has to draw a line
#: somewhere — but the line has to say whose it is, because a threshold with no
#: document behind it, printed in the same voice as a guideline, borrows an
#: authority it does not have.
#:
#: An entry here says: what the number is, what it would take to replace it with
#: something external, and what it does NOT license. `test_author_settings.py`
#: enumerates the module-level numeric constants of these modules and fails on
#: one that is not registered — so a new magic number cannot join quietly.
AUTHOR_SETTINGS = {
    "WEAK_10X": {
        "module": "scholion.limits", "value": WEAK_10X, "unit": "% of bases at ≥10×",
        "basis": "author's setting — no published document sets this figure",
        "closes": "a coverage threshold from the laboratory's own report, the panel "
                  "protocol, or a pipeline validation document, attached by the user",
        "does_not_license": "a NEGATIVE conclusion. Without such a document the honest "
                            "answer over a weakly covered gene is «not enough data», not "
                            "«nothing found»",
    },
    "PRS_MIN_MATCH": {
        "module": "scholion.limits", "value": PRS_MIN_MATCH, "unit": "fraction of the model",
        "basis": "author's setting",
        "closes": "binding it to a PGS Catalog identifier, a computation version and the "
                  "result file, so the number belongs to a model rather than to a habit",
        "does_not_license": "presenting a percentile as clinically actionable",
    },
}


def callability() -> Dict[str, Any]:
    """`profile/callability.tsv` → {gene: row}. Empty when it has never been computed.

    Empty is a normal state and a reportable one: it means the coverage of this
    person's genome is unknown, which is different from being poor, and the
    difference is the whole reason this function does not return zeros.
    """
    path = core.profile_dir() / "callability.tsv"
    if not path.exists():
        return {}
    out: Dict[str, Any] = {}
    try:
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                gene = (row.get("gene") or "").strip().upper()
                if not gene:
                    continue
                try:
                    out[gene] = {
                        "panel": row.get("panel", ""),
                        "mean_depth": float(row.get("mean_depth") or 0),
                        "rel_to_panel": float(row.get("rel_to_panel") or 0),
                        "pct_10x": float(row.get("pct_10x") or 0),
                        "pct_20x": float(row.get("pct_20x") or 0),
                        # The interval the percentages were measured over, when
                        # the pipeline recorded it. Optional on purpose: a file
                        # written before it did is still a valid coverage table,
                        # and the export below refuses rather than inventing
                        # coordinates for it.
                        "chrom": (row.get("chrom") or "").strip() or None,
                        "start": int(row["start"]) if (row.get("start") or "").strip().isdigit() else None,
                        "end": int(row["end"]) if (row.get("end") or "").strip().isdigit() else None,
                    }
                except ValueError:
                    continue
    except OSError:
        return {}
    return out


#: What a coverage percentage is computed OVER, when the pipeline did not say.
#: Our own `build_clinical_bed.py` uses gene loci with a 10 kb margin and now
#: records that beside the BED; a file from anywhere else says nothing, and
#: «unknown» is then the honest answer rather than an assumption in our favour.
INTERVAL_BASIS_DEFAULT = "unknown"


def interval_basis() -> Dict[str, Any]:
    """On what intervals the callability percentages were measured.

    This matters more than it looks. Over a gene LOCUS with a margin, a 200 bp
    dropout in a 300 kb gene moves `pct_10x` by about 0.07 % — while a dropout
    inside the coding sequence is the single thing the number is consulted about.
    So a high percentage over loci is not the same statement as a high percentage
    over CDS, and printing them in the same words would be the quiet substitution
    this layer exists to prevent.
    """
    p = core.profile_dir() / "callability_meta.json"
    try:
        if p.is_file():
            import json as _json
            d = _json.loads(p.read_text(encoding="utf-8"))
            return {"basis": d.get("interval_basis") or INTERVAL_BASIS_DEFAULT,
                    "pad": d.get("pad_locus"), "stated": True,
                    "note": _t("limits.interval_basis_locus")
                    if (d.get("interval_basis") or "").startswith("gene_locus")
                    else None}
    except (OSError, ValueError):
        pass
    return {"basis": INTERVAL_BASIS_DEFAULT, "stated": False,
            "note": _t("limits.interval_basis_unknown")}


def weak_regions_bed(panels: Optional[List[str]] = None) -> Dict[str, Any]:
    """The genes a negative conclusion cannot rest on, as a BED — or a refusal.

    «Zero pathogenic findings across the ACMG genes» is honest exactly as far as
    those genes were read, and the coverage table already knows which ones were
    not. What it could not do is hand the list to anybody: a percentage names a
    gene, and a laboratory asked to re-read something needs coordinates.

    Two refusals rather than one, because they need different remedies:

    · the table has never been computed — there is nothing to export, and what
      produces it is named;
    · the table exists but predates the columns that carry coordinates. The
      genes are known and their intervals are NOT, and inventing them from a
      gene name is precisely the substitution this module exists against. The
      refusal says which run would fill them in.

    **The intervals are whole gene loci with a margin, not coding sequence.**
    That is stated in the track line rather than left to be assumed: a 200 bp
    dropout inside an exon moves a locus-wide percentage by almost nothing, so a
    BED built this way is a worklist of genes to look at again — not a map of
    the bases that were missed.
    """
    rows = callability()
    if not rows:
        return {"ok": False, "reason": "never_computed",
                "note": _t("limits.bed_never_computed")}
    wanted = {p.upper() for p in (panels or [])}
    weak = {g: r for g, r in rows.items()
            if r["pct_10x"] < WEAK_10X
            and (not wanted or str(r.get("panel", "")).upper() in wanted)}
    if not weak:
        return {"ok": True, "regions": 0, "bed": "", "note": _t("limits.bed_nothing_weak")}
    without = sorted(g for g, r in weak.items()
                     if not (r.get("chrom") and r.get("start") is not None
                             and r.get("end") is not None))
    if without:
        return {"ok": False, "reason": "no_coordinates", "genes": without,
                "note": _t("limits.bed_no_coordinates", genes=", ".join(without[:12]))}
    basis = interval_basis()
    lines = [f'track name=scholion_weak description="{_t("limits.bed_track", pct=WEAK_10X, basis=basis["basis"])}"']
    for gene in sorted(weak, key=lambda g: (weak[g]["pct_10x"], g)):
        r = weak[gene]
        # The score column carries the percentage, so a reader who opens the file
        # in a browser sees WHY each interval is here without a second file.
        lines.append(f"{r['chrom']}\t{r['start']}\t{r['end']}\t{gene}\t{r['pct_10x']:.1f}")
    return {"ok": True, "regions": len(weak), "basis": basis["basis"],
            "bed": "\n".join(lines) + "\n",
            "genes": sorted(weak, key=lambda g: weak[g]["pct_10x"])}


def coverage_summary() -> Dict[str, Any]:
    """The one paragraph a report owes its reader about how much was read."""
    rows = callability()
    if not rows:
        return {"known": False,
                "why": _t("limits.coverage_unknown"),
                "closes": _t("limits.coverage_closes")}
    acmg = [r for r in rows.values() if r["panel"].upper().startswith("ACMG")]
    weak = sorted((g for g, r in rows.items() if r["pct_10x"] < WEAK_10X),
                  key=lambda g: rows[g]["pct_10x"])
    def _mean(sel, field):
        return round(sum(r[field] for r in sel) / len(sel), 1) if sel else None
    return {"known": True, "genes": len(rows),
            "interval_basis": interval_basis(),
            "mean_pct_10x": _mean(list(rows.values()), "pct_10x"),
            "acmg_genes": len(acmg), "acmg_pct_10x": _mean(acmg, "pct_10x"),
            "weak": [{"gene": g, "pct_10x": rows[g]["pct_10x"],
                      "rel_to_panel": rows[g]["rel_to_panel"]} for g in weak[:20]],
            "weak_total": len(weak)}


def _item(what: str, why: str, closes: str, kind: str, subject: str = "",
          certainty: str = "determined") -> Dict[str, str]:
    """One limitation. `closes` is not optional — see the module docstring."""
    return {"kind": kind, "subject": subject, "what": what, "why": why,
            "closes": closes, "certainty": certainty}


def _genome_limits() -> List[Dict[str, str]]:
    from . import genome
    out: List[Dict[str, str]] = []
    av = genome.available()
    ready = bool(av.get("ready"))
    if not ready:
        # «There is no genome» and «the genome is in another coordinate system»
        # are different facts, and the remedy differs. Printing the first for the
        # second would be this layer telling the reader something untrue about
        # itself, which is the one thing it may not do.
        if av.get("assembly_mismatch"):
            out.append(_item(
                _t("limits.assembly_what", found=av.get("assembly")),
                _t("limits.assembly_why", found=av.get("assembly"),
                   want=av.get("assembly_expected")),
                _t("limits.assembly_closes", want=av.get("assembly_expected")),
                kind="genome"))
        else:
            out.append(_item(_t("limits.no_genome_what"), _t("limits.no_genome_why"),
                             _t("limits.no_genome_closes"), kind="genome"))

    # Task 100. Points written before the source of their date was recorded. Said
    # ONCE, here, with a number — not as a caveat on every one of them: the
    # person's own carefully entered history would be buried in marks about
    # itself. What is not claimed is that these dates came off a form.
    try:
        _unrec = sum(1 for m in (core.labs().get("markers") or {}).values()
                     for p in (m.get("series") or [])
                     if (p.get("date_source") or "unrecorded") == "unrecorded")
    except Exception:
        _unrec = 0
    if _unrec:
        out.append(_item(_t("limits.date_unrecorded_what", n=_unrec),
                         _t("limits.date_unrecorded_why"),
                         _t("limits.date_unrecorded_closes"), kind="labs"))
        return out
    if av.get("assembly_unknown"):
        out.append(_item(_t("limits.assembly_unknown_what"),
                         _t("limits.assembly_unknown_why", want=av.get("assembly_expected")),
                         _t("limits.assembly_unknown_closes"), kind="genome"))

    cov = coverage_summary()
    if not cov["known"]:
        out.append(_item(_t("limits.coverage_what"), cov["why"], cov["closes"], kind="genome"))
    else:
        for w in cov["weak"]:
            out.append(_item(
                _t("limits.weak_gene_what", gene=w["gene"]),
                _t("limits.weak_gene_why", gene=w["gene"], pct=w["pct_10x"]),
                _t("limits.weak_gene_closes", gene=w["gene"]),
                kind="genome", subject=w["gene"]))

    for gene in core.genome_gaps():
        from . import engine
        ph = engine.compute_phenotype(gene)
        out.append(_item(
            _t("limits.gene_not_read_what", gene=gene),
            ph.get("basis_note") or _t("limits.gene_not_read_why", gene=gene),
            _t("limits.gene_not_read_closes"),
            kind="pharmacogenetics", subject=gene,
            certainty=ph.get("certainty", "unknown")))
    return out


def _lab_limits() -> List[Dict[str, str]]:
    """Markers whose value is printed without a corridor, and rules that cannot fire."""
    out: List[Dict[str, str]] = []
    markers = core.labs().get("markers", {})
    known = core.lab_markers().get("markers", {})
    from .i18n import lang as _lang
    lang = _lang()
    no_range = []
    for key, m in markers.items():
        if m.get("ref_low") is None and m.get("ref_high") is None:
            spec = known.get(key) or {}
            if spec.get("ref_low") is None and spec.get("ref_high") is None:
                no_range.append(core.marker_display(spec, lang, m.get("name", key)))
    if no_range:
        out.append(_item(
            _plural(len(no_range), "limits.no_corridor_what"),
            _t("limits.no_corridor_why", markers=", ".join(sorted(no_range)[:12])),
            _t("limits.no_corridor_closes"), kind="labs"))
    if not markers:
        out.append(_item(_t("limits.no_labs_what"), _t("limits.no_labs_why"),
                         _t("limits.no_labs_closes"), kind="labs"))
    return out


def _measured_directly(trait: Dict[str, Any]):
    """Has this person MEASURED the quantity the score estimates?

    For a trait like «Ferritin level» the answer is usually yes, and then every
    remedy about genotyping is beside the point — the measurement answers the
    question outright and the model adds nothing to it. This is a fact about the
    person's own data rather than a judgement, so it is looked up rather than
    curated: the trait name is resolved against the marker dictionary the same way
    a lab form's row is, and the result counts only if there is an actual value.
    """
    from . import engine
    name = (trait.get("label") or trait.get("term") or "").strip()
    if not name:
        return None
    # «Ferritin level» is the trait; «Ferritin» is the marker. A PGS catalogue names
    # a quantity, a lab dictionary names a test, and the difference is usually one
    # trailing word. Nothing else is stripped: the resolver refuses an ambiguous
    # name rather than guessing, and a wrong match here would print a measurement
    # that does not belong to the score.
    tails = ("level", "levels", "concentration", "measurement")
    tries = [name]
    parts = name.split()
    if len(parts) > 1 and parts[-1].lower() in tails:
        tries.append(" ".join(parts[:-1]))
    key = None
    for n in tries:
        key = (core.resolve_marker(n) or {}).get("key")
        if key:
            break
    if not key:
        return None
    for m in engine.analyze_labs().get("markers", []):
        if m.get("key") == key and m.get("value") is not None:
            return m
    return None


def _prs_limits() -> List[Dict[str, str]]:
    """Percentiles withdrawn from trust — and the remedy chosen by the CAUSE.

    Two different things withdraw a score, and offering one remedy for both is
    the same defect this project fixed in the pharmacogenetic layer: an
    instruction that argues with its own diagnosis. Poor coverage is a fact about
    the reading and re-genotyping closes it. A model that does not reproduce
    between cohorts, or one whose effect size is near zero, is a fact about the
    MODEL — nothing in this person's data will close it, and telling them to
    re-genotype sends them to do work that cannot help.
    """
    out: List[Dict[str, str]] = []
    traits = core.prs_results().get("traits") or []
    for t in traits if isinstance(traits, list) else []:
        # The trigger is the PGS layer's OWN verdict, not a threshold repeated
        # here. Two screens in one session disagreeing about one number is worse
        # than either of them being wrong — a trait the layer trusts at 87 %
        # coverage must not appear in this list as untrustworthy.
        if not (t.get("reliable") is False or t.get("percentile_reliable") is False):
            continue
        match = t.get("match_rate")
        poor_coverage = match is not None and float(match) < PRS_MIN_MATCH
        why = t.get("validity_note") or (
            _t("limits.prs_why", pct=round(float(match) * 100)) if poor_coverage
            else _t("limits.prs_model_why"))
        # WHY the score was withdrawn — read from the record, not from the wording
        # of its note. The branch used to be `poor_coverage and validity_note`, and
        # every withdrawn score carries a note (that is what a note is for), so the
        # condition reduced to `poor_coverage` and all three of the demo's withdrawn
        # scores printed one sentence word for word. Two of them were wrong: a
        # near-zero effect size is not closed by re-genotyping anything.
        #
        # `withdrawn_because` is optional. When the PGS layer has not said, the
        # coverage figure is a fact and is used; a model that reads badly at good
        # coverage is a statement about the model.
        because = set(t.get("withdrawn_because") or
                      (["coverage"] if poor_coverage else ["model"]))
        measured = _measured_directly(t)
        if measured:
            # The strongest remedy there is, and it is not work: the quantity the
            # model estimates has been measured in this person's blood. Offered
            # before the others because it makes them beside the point.
            closes = _t("limits.prs_measured_closes", name=measured["name"],
                        value=measured["value"], unit=measured.get("unit", ""),
                        date=measured.get("date", ""))
        elif because >= {"coverage", "model"}:
            closes = _t("limits.prs_both_closes")
        elif "coverage" in because:
            closes = _t("limits.prs_closes")
        else:
            closes = _t("limits.prs_model_closes")
        out.append(_item(
            _t("limits.prs_what", trait=t.get("label") or t.get("term") or "?"),
            why, closes, kind="prs",
            subject=t.get("pgs_id", ""), certainty="unknown"))
    return out


def _input_limits() -> List[Dict[str, str]]:
    """Whole layers that are absent. Named, because an absent layer is silent."""
    out: List[Dict[str, str]] = []
    checks = (
        ("medications", bool(core.medication_names()), "limits.no_meds"),
        ("wearables", bool(core.wearable_trends()), "limits.no_wearables"),
    )
    for kind, present, stem in checks:
        if not present:
            out.append(_item(_t(stem + "_what"), _t(stem + "_why"), _t(stem + "_closes"),
                             kind=kind))
    return out


def _profile_limits() -> List[Dict[str, str]]:
    """The facts the engine cannot derive and will not invent.

    They belong here rather than in a place of their own. This layer already
    answers one question — «what cannot be said from this data, and what would
    close it» — and a missing precondition is exactly that: not an error, not a
    warning on every screen, but a sentence the product is not allowed to finish
    and a command that lets it. The assistant reads this list at the start of a
    conversation, so what it asks for is derived from the profile rather than
    from a list somebody typed into an instruction and then had to keep in step.

    Each is gated on being able to bite. Naming the reference population to
    somebody with no genome is noise: nothing will ever compute a percentile for
    them. Asking about a wearable is gated on the question never having been
    ANSWERED — `none` is an answer, and a person who gave it is not asked again.
    """
    out: List[Dict[str, str]] = []
    prof = core.metrics_json().get("profile") or {}

    if not core.profile_sex():
        out.append(_item(_t("limits.no_sex_what"), _t("limits.no_sex_why"),
                         _t("limits.no_sex_closes"), kind="profile"))
    if not (prof.get("birth_year") or prof.get("birth_date")):
        out.append(_item(_t("limits.no_birth_what"), _t("limits.no_birth_why"),
                         _t("limits.no_birth_closes"), kind="profile"))
    if not prof.get("height_cm"):
        out.append(_item(_t("limits.no_height_what"), _t("limits.no_height_why"),
                         _t("limits.no_height_closes"), kind="profile"))
    else:
        # A height with no weight beside it is the same sentence left unfinished
        # from the other end, and it names a different command.
        weights = ((core.metrics_json().get("metrics") or {}).get("weight") or {}).get("series")
        if not weights:
            out.append(_item(_t("limits.no_weight_what"), _t("limits.no_weight_why"),
                             _t("limits.no_weight_closes"), kind="profile"))

    if not core.ancestry()["value"]:
        try:
            from . import genome as _genome
            has_genome = bool(_genome.available().get("ready"))
        except Exception:                                        # noqa: BLE001
            has_genome = False
        # Raised only where it can bite, and phrased as what it is: a step of
        # preparing a genome that has not been run. It is NOT a question for the
        # person — nobody knows their own superpopulation in those terms, and a
        # product that asks gets a guess it cannot tell from a measurement.
        if has_genome:
            out.append(_item(_t("limits.no_ancestry_what"), _t("limits.no_ancestry_why"),
                             _t("limits.no_ancestry_closes"), kind="profile"))

    if not core.wearable_answered():
        out.append(_item(_t("limits.no_wearable_answer_what"),
                         _t("limits.no_wearable_answer_why"),
                         _t("limits.no_wearable_answer_closes",
                            none=core.NO_WEARABLE), kind="profile"))
    return out


def scope() -> Dict[str, Any]:
    """Which cell of the matrix an answer from this profile sits in.

    Input class (whole genome / exome / consumer array) × trait architecture
    (monogenic / oligogenic / polygenic). The pipeline is genuinely different in
    each cell, and so is what may be claimed: a monogenic call wants orthogonal
    confirmation, an array wants a frequency floor because most of what it seems
    to find is false, a polygenic score wants ancestry calibration and a note on
    how much of the variance genetics explains at all.

    Naming the cell is not decoration. A percentile with no architecture beside
    it reads as a verdict, and «no pathogenic variant found» in a gene the file
    never covered reads as reassurance. The whole reason this module exists is
    that the reader should not have to know which of those they are looking at.
    """
    from . import genome
    av = genome.available()
    # `ready` is now true for an array too, so the cell is chosen by the CLASS of
    # input, not by whether anything answered. An array in the «whole genome» row
    # would be the exact confusion this table exists to prevent.
    has_vcf = av.get("input_class") == "sequenced"
    is_array = av.get("input_class") == "array"
    traits = (core.prs_results() or {}).get("traits") or {}
    rows = []
    if is_array:
        # Monogenic on a chip is the dangerous cell, and it is the one people
        # arrive expecting to use. The chip's positive predictive value for rare
        # pathogenic variants is low enough that a hit is a reason to test, not a
        # finding: BMJ 2021 measured 4.2 % PPV for BRCA1/2 on consumer arrays, and
        # Moscarello 2019 found 40 % of variants sent for confirmation were false.
        rows.append({"architecture": "monogenic", "state": "not_supported",
                     "note": _t("limits.scope.array_monogenic")})
        rows.append({"architecture": "oligogenic", "state": "partial",
                     "note": _t("limits.scope.array_oligogenic")})
        rows.append({"architecture": "polygenic", "state": "partial",
                     "note": _t("limits.scope.array_polygenic")})
    if has_vcf:
        rows.append({"architecture": "monogenic", "state": "supported",
                     "note": _t("limits.scope.monogenic")})
        rows.append({"architecture": "oligogenic", "state": "partial",
                     "note": _t("limits.scope.oligogenic")})
        rows.append({"architecture": "polygenic", "state": "supported",
                     "note": _t("limits.scope.polygenic")})
    # Task 87. «Whole genome» is a claim about the file, and it used to be made
    # from the fact that the file was a readable VCF — which is not the same
    # thing. Measured against real third-party files this sentence was printed
    # over an imputed call set, two chips distributed as VCF, a low-pass screen
    # and two call sets holding indels and no substitutions, and it was false for
    # every one of them. The measured class now decides the sentence, and where
    # the measurement failed the sentence says so instead of promising breadth.
    cs = av.get("callset") or {}
    tb = av.get("tabular") or {}
    is_tabular = av.get("input_class") == "tabular"
    profile = av.get("input_profile") if has_vcf else None
    seq_note = None
    if has_vcf:
        if profile in ("panel", "sparse", "imputed_panel",
                       "partial_callset_indels", "partial_callset_snvs", "unmeasured"):
            seq_note = _t("limits.scope.input_" + profile,
                          per_mb=cs.get("observed_per_mb"),
                          share=int(round((cs.get("imputed_share") or 0) * 100)))
        else:
            seq_note = _t("limits.scope.input_wgs")
    if is_tabular:
        # Task 89. A container VCF is a call set and answers like one; a genotype
        # table is a list of chosen positions and carries the array's ceiling.
        seq_note = (_t("limits.scope.input_tabular_container",
                       variants=tb.get("variants") or 0,
                       per_mb=tb.get("observed_per_mb") or 0)
                    if tb.get("kind") == "container_vcf"
                    else _t("limits.scope.input_genotype_table", rows=tb.get("rows") or 0))
        rows.append({"architecture": "monogenic", "state": "not_supported",
                     "note": _t("limits.scope.array_monogenic")})
        rows.append({"architecture": "oligogenic", "state": "partial",
                     "note": _t("limits.scope.array_oligogenic")})
        rows.append({"architecture": "polygenic", "state": "partial",
                     "note": _t("limits.scope.array_polygenic")})
    return {
        "input": (profile or "wgs") if has_vcf else (
            "array" if is_array else ("tabular" if is_tabular else "none")),
        "array": av.get("array"),
        "callset": cs or None,
        # A file in the wrong build is not «no file»: saying so here would
        # contradict the item three lines below, which names it precisely.
        "tabular": tb or None,
        "input_note": (seq_note if (has_vcf or is_tabular)
                       else _t("limits.scope.input_array",
                               vendor=(av.get("array") or {}).get("vendor", ""),
                               markers=(av.get("array") or {}).get("markers", 0))
                       if is_array
                       else _t("limits.scope.input_wrong_build", found=av.get("assembly"))
                       if av.get("assembly_mismatch")
                       else _t("limits.scope.input_none")),
        "rows": rows,
        # Shown whenever a polygenic number is on screen at all: without it a
        # percentile is read as the whole of the risk rather than as the part of
        # it that inheritance accounts for.
        "heritability_note": _t("limits.scope.heritability") if traits else "",
    }


def _disclaimer() -> str:
    from . import engine
    return engine.DISCLAIMER()


def report() -> Dict[str, Any]:
    """Everything this profile cannot answer, with the reason and the remedy."""
    # The preconditions come FIRST: they are the cheapest to close — a sentence
    # from the person rather than a laboratory visit or a sequencing run — and a
    # reader scanning the list should meet those before the ones that need a
    # machine.
    items = (_profile_limits() + _genome_limits() + _lab_limits()
             + _prs_limits() + _input_limits())
    cov = coverage_summary()
    closable = [i for i in items if i["closes"]]
    return {
        "scope": scope(),
        "coverage": cov,
        "items": items,
        "count": len(items),
        "closable": len(closable),
        "by_kind": {k: sum(1 for i in items if i["kind"] == k)
                    for k in sorted({i["kind"] for i in items})},
        "disclaimer": _disclaimer(),
    }
