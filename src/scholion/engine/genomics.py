"""Genome-derived findings: lookups, ClinVar, ACMG, APOE, PRS, longevity, lipids.

Every answer distinguishes a genuine read from an assumed reference: a value is
inseparable from its evidential status, and a variant the VCF never covered is
reported as not-read, not as absent.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from .. import core
from ..i18n import lang as _lang, t as _t
from ._helpers import DISCLAIMER


def genome_lookup(rsid: Optional[str] = None, gene: Optional[str] = None) -> Dict[str, Any]:
    """Lookup of any locus in the personal full VCF (through the coordinate reference)."""
    from .. import genome
    r = genome.lookup(rsid=rsid, gene=gene)
    r["disclaimer"] = DISCLAIMER()
    return r


def genome_status() -> Dict[str, Any]:
    from .. import genome
    return genome.available()


#: Inputs from which ClinVar, the ACMG secondary-findings list and polygenic
#: scores may not be answered. Named by the MEASURED class (task 87), not by the
#: file's extension or the vendor's label.
NARROW_INPUTS = frozenset({
    "array",                     # a consumer chip, whatever it arrived in
    "genotype_table",            # a table of chosen positions — a chip by another name
    "panel",                     # a genotyping panel distributed as a VCF
    "sparse",                    # a low-pass screen
    "imputed_panel",             # mostly inferred, not observed
    "partial_callset_indels",    # half a call set
    "partial_callset_snvs",      # the other half
    "unmeasured",                # breadth not established — see the docstring
})


def _array_only_input() -> Optional[Dict[str, Any]]:
    """A refusal when the input is a genotyping array, for the three paths that
    must not run on one.

    ClinVar screening, ACMG secondary findings and polygenic scores are closed on
    an array not because the code cannot execute them but because the RESULT
    would not mean what it says. A chip's positive predictive value for rare
    pathogenic variants is 4.2 % for BRCA1/2 (Weedon, BMJ 2021 — 889 positives,
    37 confirmed) and 40 % of variants sent for confirmation from raw consumer
    data were false (Moscarello 2019). And a chip carries no depth, so «nothing
    found» in a gene says only that its handful of probes were negative.

    These three stay shut until the frequency floor (task 2) and the input
    quality label (task 8) exist. Until then the honest behaviour is to refuse
    with the reason — never to answer with a value that reads like a finding.
    The locus catalogue is a different matter and stays open: it is made of
    common pharmacogenetic and trait variants, which is the register where a chip
    works as designed.

    Task 99. The gate used to key on the CARRIER — `input_class == "array"` — and
    a chip does not stop being a chip by arriving as a VCF. Measured on the
    reference corpus: a genotyping panel distributed as a VCF holds 553 197
    variants and a genotype table 48 838 chosen positions, and both of them
    answered «your VCF has not been annotated yet — run the preparation», which
    is an INVITATION to do the exact thing this gate exists to prevent. Task 87
    measured the breadth of every input and nothing read the measurement; now
    this does.

    `unmeasured` is on the closed side deliberately. The two errors here are not
    symmetric: refusing a genome whose windows could not be probed costs one
    command and a sentence, while opening a screen that was never measured costs
    a finding a person may act on. Where the evidence is missing, the answer is
    the refusal — the same rule as everywhere else in this codebase.
    """
    from .. import genome
    st = genome.available()
    if not st.get("ready"):
        # No input at all is a different sentence, and the callers already have
        # it: «this has not been annotated yet». Closing here would tell a person
        # with no genome that their genome is too narrow.
        return None
    profile = st.get("input_profile")
    if profile not in NARROW_INPUTS:
        return None
    if profile == "array":
        arr = st.get("array") or {}
        return {"status": "input_is_an_array", "available": False,
                "input_profile": profile, "vendor": arr.get("vendor"),
                "message": _t("array.path_closed"),
                "open_instead": _t("array.open_instead")}
    measured = st.get("callset") or st.get("tabular") or {}
    return {"status": "input_too_narrow", "available": False,
            "input_profile": profile,
            "measured": {k: measured.get(k) for k in
                         ("observed_per_mb", "variants", "rows", "imputed_share")
                         if measured.get(k) is not None},
            "message": _t("narrow.path_closed_" + profile,
                          per_mb=measured.get("observed_per_mb") or 0,
                          rows=measured.get("rows") or 0,
                          share=int(round((measured.get("imputed_share") or 0) * 100))),
            "open_instead": _t("array.open_instead")}


def clinvar_findings(limit: int = 200) -> Dict[str, Any]:
    """The patient's clinically significant findings (ClinVar × the personal VCF)."""
    closed = _array_only_input()
    if closed:
        return closed
    from .. import genome
    r = genome.clinvar_hits(limit=limit)
    r["disclaimer"] = DISCLAIMER()
    r["penetrance"] = _penetrance_block()
    # Whether an indel in this list could have been matched at all. Attached
    # always, because it qualifies the SILENCE as much as the hits: without
    # left-alignment a pathogenic indel spelled differently from ClinVar's copy
    # simply does not appear, and nothing on screen distinguishes that from a
    # genome that does not carry one.
    norm = genome.clinvar_normalisation()
    r["normalisation"] = norm
    if not norm.get("left_aligned"):
        r["indel_caveat"] = _t("genome.indels_not_left_aligned")
    return r


def _penetrance_block() -> Dict[str, Any]:
    """Penetrance caveats — what a list of pathogenic findings misleads without."""
    from .. import genome
    pn = genome.penetrance_notes()
    return {"one_line": pn.get("_meta", {}).get("one_line"),
            "principles": [{"title": p.get("title"), "text": p.get("text"), "source": p.get("source")}
                           for p in pn.get("principles", [])]}


def _unread_genes(genes) -> List[Dict[str, Any]]:
    """Genes among `genes` whose bases were not read deeply enough to decide.

    «No pathogenic variant found» in a gene that was never read is the same
    sentence as «no pathogenic variant found» in a gene read end to end, and a
    reader cannot tell them apart. The coverage has been computed all along —
    `limits.callability()` reads it — and the findings report never consulted it.
    Two facts held, neither compared with the other.
    """
    from .. import limits
    cov = limits.callability() or {}
    out = []
    for g in genes:
        row = cov.get(g)
        if not row:
            continue
        pct = row.get("pct_10x")
        if pct is None:
            continue
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            continue
        if pct < 90.0:
            out.append({"gene": g, "pct": round(pct, 1)})
    return sorted(out, key=lambda x: x["pct"])


def acmg_findings() -> Dict[str, Any]:
    """ACMG SF secondary findings + the layer of honesty about interpretation."""
    closed = _array_only_input()
    if closed:
        return closed
    from .. import genome
    r = genome.acmg_sf_findings()
    r["disclaimer"] = DISCLAIMER()
    r["penetrance"] = _penetrance_block()
    # An empty result is a claim about the panel, so it has to carry what of the
    # panel was actually readable. Attached whether or not anything was found:
    # a gene read at 72 % qualifies a finding as much as it qualifies a silence.
    from .. import genome as _g
    genes = list((_g.acmg_catalogue().get("genes") or {})) if hasattr(_g, "acmg_catalogue") \
        else list((core._read_knowledge("acmg_sf.json").get("genes") or {}))
    r["unread_genes"] = _unread_genes(genes)
    return r


def apoe() -> Dict[str, Any]:
    from .. import genome
    return genome.apoe_status()


# ==========================================================================
# Polygenic risks (PGS) and the longevity layer (LongevityMap)
# ==========================================================================
def _panel_facts(data: Dict[str, Any]) -> Dict[str, Any]:
    """The panel these numbers were computed against, and whether it is still the
    one that applies.

    Three separate facts that were being reported as one, wrongly. `stats` used
    to carry the stored panel beside `ancestry_stated`, and that flag asked the
    PROFILE whether a panel was known — not the file whether these percentiles
    had been computed against it. Once the panel began to be determined from the
    genome, the flag went true for everybody with a genome while the numbers went
    on being whatever the scoring run had been given, which defaulted to EUR.
    The interface then said the panel was settled and showed percentiles computed
    against another one. Nothing could tell.

    So: what the numbers used, where THAT came from, what applies now, and
    whether the two agree. `ancestry_stated` stays — the contract may not
    shrink — and now means what it says: the panel behind these numbers was
    chosen rather than fallen back on. A file written before the source was
    recorded cannot say, and «cannot say» is not «yes».
    """
    meta = data.get("_meta") or {}
    used = meta.get("superpopulation", "EUR")
    used_source = meta.get("superpopulation_source")
    applies = core.ancestry()
    return {
        "superpopulation": used,
        "superpopulation_source": used_source,
        "ancestry_stated": used_source in ("asked", "stated", "genome"),
        "ancestry_determined": applies["value"],
        "ancestry_source": applies["source"],
        # True only when there IS something to disagree with. No determination
        # is not a disagreement — it is the ordinary state before the genome has
        # been asked, and it has its own line in `limits`.
        "panel_out_of_date": bool(applies["value"]) and applies["value"] != used,
    }


def _panel_caveat(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Said out loud when the panel behind the numbers is not the one that applies.

    A field nobody prints is a fact nobody meets. These percentiles carry the
    panel they were computed against into every screen; when the genome has since
    named a different one, the number is a position inside the wrong population
    and the reader is owed that sentence beside it rather than a flag in a
    structure.
    """
    facts = _panel_facts(data)
    if facts["panel_out_of_date"]:
        return [{"key": "panel_out_of_date",
                 "note": _t("prs.caveat.panel_out_of_date",
                            used=facts["superpopulation"],
                            applies=facts["ancestry_determined"])}]
    if not facts["ancestry_stated"]:
        return [{"key": "panel_defaulted",
                 "note": _t("prs.caveat.panel_defaulted", used=facts["superpopulation"])}]
    return []


def prs_method_caveats() -> List[Dict[str, str]]:
    """What the polygenic computation does NOT do, said once and carried.

    The scoring itself happens in a separate process (`just-prs-mcp`), so these
    are not defects this codebase can repair — which is exactly why they have to
    be printed rather than left implicit. A percentile that arrives without them
    reads as a measurement; with them it reads as what it is.

    Three of the four are structural to how the score is summed, and the fourth
    is about provenance:

    · STRAND-AMBIGUOUS VARIANTS. A locus whose alleles are their own complement
      (A/T, C/G) matches whichever strand it is reported on, so a strand flip is
      indistinguishable from a correct call. This build identifies those loci on
      the array path (`array_genome.strand_ambiguous_loci`, computed from the
      catalogue) and cannot do so inside a score it does not sum.
    · MISSING VARIANTS. A variant absent from the file is simply not added,
      which is arithmetically the same as imputing a zero dose and biases the sum
      downward. This one IS measured here — `weight_mass_coverage` says how much
      of the model's weight was actually present, and the percentile is withdrawn
      from trust below the threshold rather than printed with a footnote.
    · HARD GENOTYPES ONLY. No dosage; an uncertain call counts as a certain one.
    · THE REFERENCE PANEL. The percentile is a position within a reference
      sample. The scoring package is pinned by version, not by hash, and the
      1000 Genomes cache it downloads on first use is not pinned at all — so two
      machines can, in principle, produce percentiles from different reference
      data for the same genome.
    """
    return [{"key": k, "note": _t(f"prs.caveat.{k}")}
            for k in ("strand_ambiguous", "missing_as_zero", "hard_genotypes",
                      "reference_panel")]


def PRS_DISCLAIMER() -> str:
    """The caveat specific to polygenic scores — see the note on DISCLAIMER()."""
    return _t("disclaimer.prs")


def _annotate_prs_evidence(traits: List[Dict[str, Any]]) -> None:
    """Set the level of evidence from knowledge/prs_traits.json.

    Without it all 74 traits look equally weighty, and that is not true: coronary
    artery disease and prostate cancer have prospective data, most of the rest have
    only a population association.
    """
    cat = core._read_knowledge("prs_traits.json")
    tiers = (cat.get("_meta") or {}).get("evidence_tiers", {})
    by_term, by_label = {}, {}
    for c in cat.get("traits", []):
        if c.get("term"):
            by_term[c["term"].lower()] = c
        if c.get("label"):
            by_label[c["label"].lower()] = c
    for t in traits:
        src = by_term.get(str(t.get("term", "")).lower()) or by_label.get(str(t.get("label", "")).lower())
        if not src:
            continue
        ev = src.get("evidence")
        if not ev:
            continue
        t["evidence"] = ev
        t["evidence_label"] = (tiers.get(ev) or {}).get("label", ev)
        if src.get("evidence_note"):
            t["evidence_note"] = src["evidence_note"]


#: The same 0.90 the variant-count gate uses, applied to the WEIGHT the model
#: actually places on what was found. Kept equal deliberately: two thresholds
#: with different numbers would be two policies, and nobody could say which one
#: a withdrawn percentile failed.
_PRS_MIN_WEIGHT_MASS = 0.90


def _withheld_by_sex(traits):
    """(kept, withheld). A trait the catalogue marks for one sex only.

    Symmetric, and it also withholds when the sex is NOT RECORDED: choosing a
    side there would be the same failure pointing the other way. The catalogue is
    the authority — a stored result carries no such mark, and matching is by the
    trait term the catalogue uses.
    """
    marked = {}
    for t in (core._read_knowledge("prs_traits.json").get("traits") or []):
        if t.get("applies_to_sex"):
            marked[(t.get("term") or "").strip().lower()] = t["applies_to_sex"]
    if not marked:
        return traits, []
    sex = core.profile_sex()
    kept, withheld = [], []
    for t in traits:
        need = marked.get((t.get("term") or t.get("trait") or "").strip().lower())
        if need and need != sex:
            withheld.append({"label": t.get("label") or t.get("term"),
                             "applies_to_sex": need,
                             "reason": "sex_not_recorded" if not sex else "other_sex",
                             "note": _t("prs.withheld_by_sex" if sex
                                        else "prs.withheld_sex_unknown", sex=need)})
            continue
        kept.append(t)
    return kept, withheld


def prs_findings() -> Dict[str, Any]:
    """Aggregated polygenic scores (profile/prs_results.json), grouped by category.

    Closed on an array input for now: a score computed from a chip needs
    imputation and an ancestry-matched reference before its percentile means
    anything, and neither the frequency floor (task 2) nor the input quality
    label (task 8) exists yet. Refusing with the reason is the only honest state
    in between.

    Returns {categories:[{category, traits:[...]}], high[], stats, disclaimer}.
    high — the reliable traits with a percentile ≥80 (what to look at when screening).
    """
    closed = _array_only_input()
    if closed:
        return closed
    data = core.prs_results()
    traits = data.get("traits", []) if isinstance(data, dict) else []
    if not traits:
        return {"available": False, "disclaimer": PRS_DISCLAIMER(),
                "message": _t("prs.not_computed")}
    # WHERE THESE NUMBERS CAME FROM, and when. A polygenic score is a stored
    # RESULT: it was computed once from a VCF and lives in the profile afterwards.
    # So the screen could show twelve percentiles a centimetre below a chip
    # reading «Full genome (VCF): no data», both true and reading as a
    # contradiction — a reader has no way to tell which of the two to believe.
    # The answer is neither: the file was there when this was computed and is not
    # attached now, and saying so is shorter than either half.
    _pm = core.profile_meta(data)
    _computed = _pm.get("generated") or _pm.get("updated")
    _connected = bool(genome_status().get("ready"))
    for tr in traits:                      # a guard layer: double counting of the input shows at once
        _mr = tr.get("match_rate")
        if isinstance(_mr, (int, float)) and _mr > 1.0001:
            tr["reliable"] = False
            tr["integrity_note"] = _t("prs.integrity_double")
        # A FLAT threshold on the COUNT of matched variants is weight-blind, and
        # a polygenic score is not a vote — its variants carry wildly different
        # weights. Ninety per cent of the variants can be sixty per cent of the
        # weight, and the percentile computed from what is left is a number about
        # a different model. The engine already returns `weight_mass_coverage`;
        # nothing consulted it. The gate now takes the WEAKER of the two and says
        # which one withdrew trust.
        _wm = tr.get("weight_mass_coverage")
        if isinstance(_wm, (int, float)) and _wm < _PRS_MIN_WEIGHT_MASS:
            tr["reliable"] = False
            tr["weight_mass_note"] = _t("prs.weight_mass_low",
                                        pct=round(float(_wm) * 100, 1))
    # THE SEX GUARD, applied where the report is built and not only where the
    # score is computed. `prs_results.json` is a stored result: it may have been
    # computed before the person recorded their sex, or on another machine
    # entirely, and a percentile for an organ the reader does not have would then
    # sail through as an ordinary line. Withheld traits are NAMED — a trait that
    # disappears from a panel in silence is indistinguishable from one that was
    # never in it.
    traits, withheld_by_sex = _withheld_by_sex(traits)
    _annotate_prs_evidence(traits)
    cats: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for t in traits:
        c = t.get("category") or _t("prs.category_other")
        if c not in cats:
            cats[c] = []; order.append(c)
        cats[c].append(t)
    def pnum(t):
        p = t.get("percentile")
        return p if isinstance(p, (int, float)) else -1
    high = sorted([t for t in traits if t.get("reliable") and pnum(t) >= 80],
                  key=lambda t: -pnum(t))
    reliable = [t for t in traits if t.get("reliable")]
    return {
        "available": True,
        "categories": [{"category": c, "traits": cats[c]} for c in order],
        "provenance": {
            "computed": _computed, "genome_connected": _connected,
            "note": (None if _connected
                     else _t("prs.from_a_genome_not_attached", date=_computed or "—")),
        },
        "high": high,
        "withheld_by_sex": withheld_by_sex,
        # Said on every report rather than remembered by whoever reads it: the
        # sum happens in another process, and what that process does not do is
        # part of what this number means.
        "method_caveats": prs_method_caveats() + _panel_caveat(data),
        "stats": {"total": len(traits), "reliable": len(reliable),
                  "high": len(high), **_panel_facts(data),
                  "updated": (data.get("_meta") or {}).get("updated")},
        "disclaimer": PRS_DISCLAIMER(),
    }


def genome_updates() -> Dict[str, Any]:
    """Result of the last check for database updates (genome/whats_new.json).
    Shows what appeared when the genome was checked against a fresh ClinVar."""
    data = core.whats_new()
    if not data or not data.get("clinvar"):
        return {"available": False}
    cv = data.get("clinvar", {})
    return {"available": True, "last_checked": data.get("last_checked"),
            "clinvar": {"release": cv.get("release"), "new": cv.get("new", []),
                        "changed": cv.get("changed", []), "counts": cv.get("counts", {})}}


def longevity_findings() -> Dict[str, Any]:
    """Longevity layer (LongevityMap × the owner's genome, profile/longevity_findings.json).

    Returns {available, apoe, known[], significant_genes[], stats, disclaimer}.
    The key parts are the APOE ε status and the well-studied markers (FOXO3 and so on).
    """
    data = core.longevity_data()
    if not data or not data.get("known"):
        return {"available": False, "disclaimer": DISCLAIMER(),
                "message": _t("longevity.not_built")}
    sig = data.get("significant_by_gene", {}) or {}
    # the famous longevity genes come first
    famous = ["FOXO3", "APOE", "SIRT1", "SIRT3", "CETP", "IL6", "TP53", "KL", "IGF1R",
              "AKT1", "APOC3", "ADIPOQ", "ACE", "TOMM40"]
    genes = sorted(sig.keys(), key=lambda g: (famous.index(g) if g in famous else 999, g))
    sig_genes = [{"gene": g, "variants": sig[g]} for g in genes]
    meta = data.get("_meta", {})
    return {
        "available": True,
        "apoe": data.get("apoe"),
        "known": data.get("known", []),
        "significant_genes": sig_genes,
        "stats": {"genotyped": meta.get("genotyped"), "carriers": meta.get("carriers"),
                  "significant_carriers": meta.get("significant_carriers"),
                  "significant_genes": len(sig_genes)},
        "disclaimer": (meta.get("disclaimer") or "") + " " + DISCLAIMER(),
    }


# ==================== the genetic side of the lipid profile ==================
# Task 63. Two facts that belong beside each other and were sitting in three
# different places: whether a protective loss-of-function variant of PCSK9 is
# carried, and what Lp(a) is. Neither is a risk calculation; together they say
# how much of a lipid picture is inheritance a person cannot change and how much
# is the part that moves.
#
# The reason this is one card and not two lines on two tabs is that each is
# misread alone. A low LDL-C with a PCSK9 LOF variant behind it means something
# different from the same number reached on a statin. And Lp(a) is invisible to
# the rest of a lipid panel entirely: it is set at birth, it does not respond to
# the things LDL-C responds to, and a normal panel with a high Lp(a) is a normal
# panel that has missed the finding.
#
# Two limits are printed rather than left implicit, because both are the kind
# that turn an absence into a false reassurance:
#
#   · Lp(a) level is driven mostly by the number of KIV-2 repeats in LPA — a
#     copy-number variant. Short-read sequencing and SNP arrays see it poorly.
#     A polygenic score is a genetic ESTIMATE and cannot stand in for the
#     measurement; the catalogue's own «Moderate» quality mark on PGS002101 is
#     that limit, stated in the place a reader will not look.
#   · Not carrying C679X is close to meaningless outside populations of African
#     descent, where it is almost absent. «Not a carrier» has to say so.

_PCSK9_LOF = ["rs11591147", "rs28362286"]        # direction resolved, primary PMIDs


_PCSK9_WAITING = ["rs28362263", "rs72646508"]    # position known, direction unresolved


_LPA_PGS = "PGS002101"


def _copies_of(genotype: str, allele: str) -> Optional[int]:
    if not genotype or not allele:
        return None
    g = genotype.replace("|", "").replace("/", "").strip().upper()
    if not g or set(g) - set("ACGT"):
        return None
    return g.count(allele.upper())


def lipid_genetics() -> Dict[str, Any]:
    """PCSK9 carriage and Lp(a), in one answer, each with what it is worth.

    Every branch has to say something. A card that renders nothing when the
    genome is absent is the failure this project exists to refuse: the reader
    concludes there was nothing to find, when the truth is that nothing was
    looked at. So the empty states carry the test that would fill them —
    for Lp(a), once in a lifetime, in nmol/L, and before a therapy decision
    rather than after it.
    """
    directions = (core.longevity_directions().get("directions") or {})
    loci = (core.loci().get("loci") or {})

    pcsk9 = []
    for rsid in _PCSK9_LOF:
        d = directions.get(rsid) or {}
        st = core.genotype_status(rsid)
        gt = (st or {}).get("genotype") or ""
        copies = _copies_of(gt, d.get("favorable") or "")
        # `assumed_ref` is not «reference». It means there is no row at this
        # position: either the reference, or nothing was read there. Counting it
        # as zero copies is the exact defect the answerability layer was built
        # after, so it is reported as unread instead.
        unread = bool(st and st.get("confidence") == "assumed_ref")
        # The catalogue stores a TOKEN per copy count, and the sentence lives in
        # the message catalogue. Prose inside a knowledge file prints raw into a
        # report the moment a field name is one the resolver does not know, and
        # it is invisible to the language gate besides.
        token = None
        if copies is not None and not unread:
            token = (d.get("verdict_by_copies") or {}).get(str(min(copies, 2)))
        pcsk9.append({
            "rsid": rsid, "gene": "PCSK9",
            "label": core._localized(d.get("label") or {}, _lang()) or "",
            "genotype": None if unread else (gt or None),
            "confidence": (st or {}).get("confidence"),
            "source": (st or {}).get("source"),
            "favorable": d.get("favorable"),
            "copies": None if unread else copies,
            "carrier": None if (copies is None or unread) else copies > 0,
            "verdict_token": token,
            "verdict": (_t(f"lipidgen.copies.{min(copies, 2)}")
                        if (token and copies is not None) else None),
            "population_note": core._localized(d.get("population_caveat") or {}, _lang()) or None,
            "action": core._localized(d.get("action") or {}, _lang()) or None,
            "pmids": d.get("pmids") or [],
            "status": "unread" if unread else ("read" if copies is not None else "no_data"),
        })

    # --- Lp(a): the measurement, and separately the genetic estimate ---------
    lab = (core.labs().get("markers") or {}).get("lpa") or {}
    pts = sorted([p for p in (lab.get("series") or []) if p.get("value") is not None],
                 key=lambda p: str(p.get("date", "")))
    measured = None
    if pts:
        last = pts[-1]
        hi = lab.get("ref_high")
        measured = {"value": last["value"], "unit": lab.get("unit") or "",
                    "date": str(last.get("date", "")), "ref_high": hi,
                    "above": (hi is not None and float(last["value"]) > float(hi))}
    estimate = None
    for cat in (prs_findings().get("categories") or []):
        for tr in cat.get("traits") or []:
            if tr.get("pgs_id") == _LPA_PGS:
                estimate = {"percentile": tr.get("percentile"), "pgs_id": tr.get("pgs_id"),
                            "quality": tr.get("quality_label"), "label": tr.get("label")}
    lpa = {
        "measured": measured,
        "estimate": estimate,
        # Printed whenever an estimate is on screen without a measurement — which
        # is precisely when it is most likely to be read as one.
        "estimate_is_not_a_measurement": _t("lipidgen.lpa.estimate_limit"),
        "what_to_do": None if measured else _t("lipidgen.lpa.order_it"),
    }

    read = [x for x in pcsk9 if x["status"] == "read"]
    carriers = [x for x in read if x["carrier"]]
    return {
        "status": "ok",
        "pcsk9": pcsk9,
        "pcsk9_waiting": [{"rsid": r, "gene": "PCSK9",
                           "why": core._localized(((core.longevity_directions().get("unresolved") or {})
                                                   .get("variants") or {}).get(r, {}).get("why") or {},
                                                  _lang())}
                          for r in _PCSK9_WAITING if r in loci],
        "lpa": lpa,
        "headline": (_t("lipidgen.headline.carrier") if carriers
                     else (_t("lipidgen.headline.not_carrier") if read
                           else _t("lipidgen.headline.unread"))),
        "how_to_read": _t("lipidgen.how_to_read"),
        "disclaimer": DISCLAIMER(),
    }
