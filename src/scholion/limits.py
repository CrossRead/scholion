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

#: Below this fraction of bases at ≥10× a gene cannot be called negative. 10× is
#: the depth at which a heterozygote is decided at all — see qc_callability.sh,
#: which uses the same threshold; the number is not repeated here by coincidence.
WEAK_10X = 90.0

#: A polygenic score whose model is called below this is a number without a
#: population behind it. The same threshold the PGS layer uses to withdraw a
#: percentile from trust.
PRS_MIN_MATCH = 0.90


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
                    }
                except ValueError:
                    continue
    except OSError:
        return {}
    return out


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
    ready = bool(genome.available().get("ready"))
    if not ready:
        out.append(_item(_t("limits.no_genome_what"), _t("limits.no_genome_why"),
                         _t("limits.no_genome_closes"), kind="genome"))
        return out

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
            _t("limits.no_corridor_what", n=len(no_range)),
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
    has_vcf = bool(genome.available().get("ready"))
    traits = (core.prs_results() or {}).get("traits") or {}
    rows = []
    if has_vcf:
        rows.append({"architecture": "monogenic", "state": "supported",
                     "note": _t("limits.scope.monogenic")})
        rows.append({"architecture": "oligogenic", "state": "partial",
                     "note": _t("limits.scope.oligogenic")})
        rows.append({"architecture": "polygenic", "state": "supported",
                     "note": _t("limits.scope.polygenic")})
    return {
        "input": "wgs" if has_vcf else "none",
        "input_note": _t("limits.scope.input_wgs") if has_vcf
                      else _t("limits.scope.input_none"),
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
    items = _genome_limits() + _lab_limits() + _prs_limits() + _input_limits()
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
