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


def clinvar_findings(limit: int = 200) -> Dict[str, Any]:
    """The patient's clinically significant findings (ClinVar × the personal VCF)."""
    from .. import genome
    r = genome.clinvar_hits(limit=limit)
    r["disclaimer"] = DISCLAIMER()
    r["penetrance"] = _penetrance_block()
    return r


def _penetrance_block() -> Dict[str, Any]:
    """Penetrance caveats — what a list of pathogenic findings misleads without."""
    from .. import genome
    pn = genome.penetrance_notes()
    return {"one_line": pn.get("_meta", {}).get("one_line"),
            "principles": [{"title": p.get("title"), "text": p.get("text"), "source": p.get("source")}
                           for p in pn.get("principles", [])]}


def acmg_findings() -> Dict[str, Any]:
    """ACMG SF secondary findings + the layer of honesty about interpretation."""
    from .. import genome
    r = genome.acmg_sf_findings()
    r["disclaimer"] = DISCLAIMER()
    r["penetrance"] = _penetrance_block()
    return r


def apoe() -> Dict[str, Any]:
    from .. import genome
    return genome.apoe_status()


# ==========================================================================
# Polygenic risks (PGS) and the longevity layer (LongevityMap)
# ==========================================================================
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


def prs_findings() -> Dict[str, Any]:
    """Aggregated polygenic scores (profile/prs_results.json), grouped by category.

    Returns {categories:[{category, traits:[...]}], high[], stats, disclaimer}.
    high — the reliable traits with a percentile ≥80 (what to look at when screening).
    """
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
        "stats": {"total": len(traits), "reliable": len(reliable),
                  "high": len(high), "superpopulation": (data.get("_meta") or {}).get("superpopulation", "EUR"),
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
