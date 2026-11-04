"""A person's state at one curated position (tasks 199, 201).

absent / het / hom count copies of the named allele; a position positively
read with no allele named is `risk_allele_not_declared`; a missing row in a
whole-genome file may be TAKEN BY THE REFERENCE under the conditions spelled
out below; everything else is unread, with the reader's own reason. Split out
of `system_panels.py` on 18.09.2026; the card imports it back by name.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .. import core
from . import panel_gate


def _loc_from_hgvs(hgvs, rsid, gene):
    from .system_panels import _loc_from_hgvs as loc
    return loc(hgvs, rsid, gene)


_HGVS = panel_gate.HGVS


def _has_alignment() -> bool:
    """Whether an alignment is on this machine — asked once per card, not per position."""
    from ..gene_region import bam_path
    return bool(bam_path())


def _reference_presumption_refusal(rsid: str, gene: str, scan: Dict[str, Any],
                                  has_bam: bool) -> Optional[str]:
    """A missing row can be qualified only for a known whole-genome locus."""
    from .genomics import NARROW_INPUTS, gene_coverage

    if has_bam:
        return "alignment_at_hand"
    if scan.get("input_profile") in NARROW_INPUTS:
        return "narrow_input"
    if scan.get("input_profile") != "whole_genome":
        return "not_whole_genome"
    if rsid not in (core.loci().get("loci") or {}):
        return "not_in_catalogue"
    if (gene_coverage(gene) or {}).get("state") in ("low", "gene_not_in_table"):
        return "coverage_objects"
    return None


def _genotype(rsid: str, hgvs: str, gene: str, risk_allele: Optional[str],
              scan: Dict[str, Any], at=None, has_bam: Optional[bool] = None) -> Dict[str, Any]:
    """The person's genotype at one position, as a STATE of the named allele.

    absent / het / hom count copies of the allele the author named; a position
    that was positively read (called, or confirmed against the reference) with
    no allele named is `risk_allele_not_declared` — read, and no phrase can be
    chosen for it; everything else is `unread`, with the reader's own reason,
    because a position with no row in the file is not a reference call.
    """
    recorded = core.profile_genotypes().get(rsid)
    if scan.get("status") != "ok":
        if recorded:
            return _from_profile(recorded, risk_allele, at)
        return {"state": None, "read": None, "why": scan.get("reason")}
    from .. import genome
    try:
        r = (genome.lookup(rsid, allow_network=False) if scan.get("local_only") else genome.lookup(rsid)) or {}
    except Exception as exc:                                         # noqa: BLE001
        return {"state": "unread", "read": False, "why": type(exc).__name__}
    res: Optional[Dict[str, Any]] = None
    if r.get("status") == "ok":
        res = r.get("result") or {}
    elif r.get("status") == "unknown_rsid":
        loc = _loc_from_hgvs(hgvs, rsid, gene)
        if loc is None:
            return {"state": "unread", "read": False, "why": "position_not_resolved"}
        try:
            res = genome._gt_at(loc) or {}
            from ..variant_readings import resolve
            res = resolve(rsid, res, recorded) or {}
        except Exception as exc:                                     # noqa: BLE001
            return {"state": "unread", "read": False, "why": type(exc).__name__}
    else:
        return {"state": "unread", "read": False, "why": r.get("status")}
    conf = res.get("confidence")
    if conf == "reported":
        return _from_profile(res, risk_allele, at)
    out = {"genotype": res.get("genotype"), "confidence": conf, "depth": res.get("depth"),
           **{k: res[k] for k in ("source", "assembly", "read_pos", "filter", "qual", "allele_fraction",
               "low_depth", "filtered", "imputed", "unverified_locus", "needs_confirmation", "date", "observations", "variant_identity", "raw_genotype", "phased", "interpretation_applicable", "conflict", "reading_record",
               "note", "source_identity", "confirmation_reasons", "strand_ambiguous", "depth_unverified") if k in res}}
    if res.get("conflict"):
        return {**out, "state": "risk_allele_not_declared", "read": bool(res.get("genotype")),
                "why": "source_conflict"}
    if res.get("interpretation_applicable") is False and res.get("genotype"):
        return {**out, "state": "risk_allele_not_declared", "read": True,
                "why": "effect_allele_not_applicable"}
    if res.get("depth_unverified"):
        # The reader's own word (`genome._mark_depth_unverified`): the row is in
        # the file, it states no depth, and no alignment is here to measure one.
        out["depth_unverified"] = True
    m = _HGVS.match((hgvs or "").strip())
    ref = m.group(3) if m else None
    if conf == "called":
        if not risk_allele:
            return {**out, "state": "risk_allele_not_declared", "read": True}
        # A genotype holding a letter that is not one of the two at this
        # position is not of this locus; counting the allele in it would give
        # zero and print «absent» (task 199).
        copies = panel_gate.copies(res.get("genotype") or "", risk_allele, at)
        if copies is None:
            return {**out, "state": "unread", "read": False, "why": "genotype_not_comparable"}
        return {**out, "state": ("absent", "het", "hom")[min(copies, 2)], "read": True}
    if conf == "confirmed_ref":
        if not risk_allele:
            return {**out, "state": "risk_allele_not_declared", "read": True}
        same = bool(ref) and ref.upper() == str(risk_allele).upper()
        return {**out, "state": "hom" if same else "absent", "read": True}
    if conf == "assumed_ref":
        # No row at this position (task 201). In a whole-genome file that is
        # usually not a gap — the position is omitted BECAUSE it matched the
        # reference — and the answer is almost certainly there. Three states:
        #  · `confirmed_ref` is a measured 0/0 with its depth (handled above);
        #  · `presumed_ref` is taken by the reference, and is allowed only when
        #    ALL of these hold: the file is whole-genome by its own breadth
        #    probe (on a chip, a genotype table or a panel a missing row means
        #    «not on the chip», never «matched the reference»); the coverage
        #    table does not object (the gene is not low or absent in a table
        #    that exists — no table at all is no objection); the position is in
        #    the catalogue, so its coordinate and its ref/alt pair are known;
        #    and no alignment is here to read it from — with one, the honest
        #    answer is «not read yet» and the step that reads it;
        #  · otherwise it stays `assumed_ref`: nothing to presume from.
        if has_bam is None:
            has_bam = _has_alignment()
        why_not = _reference_presumption_refusal(rsid, gene, scan, has_bam)
        if not why_not and not risk_allele:
            why_not = "risk_allele_not_declared"
        if why_not:
            return {**out, "state": "unread", "read": False, "why": "assumed_ref", "presumed_refused": why_not}
        same = bool(ref) and ref.upper() == str(risk_allele).upper()
        return {**out, "state": "hom" if same else "absent", "read": False,
                "presumed": True, "why": "presumed_ref"}
    if recorded:
        # The file did not read it and the profile has it written down (0.6.0).
        return _from_profile(recorded, risk_allele, at)
    return {**out, "state": "unread", "read": False, "why": conf or "no_row"}


def _from_profile(rec: Dict[str, Any], risk_allele: Optional[str], at=None) -> Dict[str, Any]:
    """A genotype the profile records (`core.profile_genotypes`), as a state.
    It is a reading with a named source rather than a call with a depth."""
    if "reading_record" not in rec:
        from ..variant_readings import resolve
        rec = resolve(rec.get("rsid") or "", None, rec) or rec
    out = {**rec, "genotype": rec["genotype"], "confidence": "profile",
           "from_profile": rec.get("from_profile") or rec.get("source")}
    out.setdefault("depth", None)
    if rec.get("conflict") or rec.get("interpretation_applicable") is False:
        return {**out, "state": "risk_allele_not_declared", "read": True,
                "why": "source_conflict" if rec.get("conflict") else "effect_allele_not_applicable"}
    if not risk_allele:
        return {**out, "state": "risk_allele_not_declared", "read": True}
    if not at:
        return {**out, "state": "unread", "read": False, "why": "genotype_not_comparable"}
    copies = panel_gate.copies(rec["genotype"], risk_allele, at)
    pair = set(at or ())
    if copies is None and pair and pair not in ({"A", "T"}, {"C", "G"}):
        # A report writes a gene on the minus strand in the gene's letters: F5
        # rs6025 is G/A there and C/T in the file. Complemented once, and never
        # at an A/T or C/G position, where both strands spell the same pair.
        flip = "".join(panel_gate._COMPLEMENT.get(c, c) for c in str(rec["genotype"]).upper())
        copies = panel_gate.copies(flip, risk_allele, at)
        if copies is not None:
            out["strand_of_record"] = "-"
    if copies is None:
        return {**out, "state": "unread", "read": False, "why": "genotype_not_comparable"}
    return {**out, "state": ("absent", "het", "hom")[min(copies, 2)], "read": True}


# ---- one copy of X (task 205 B, F) -----------------------------------------
#: The two pseudoautosomal regions of GRCh38 chrX, where a man has two copies.
_PAR_X = ((10001, 2781479), (155701383, 156030895))


def on_x(p: Dict[str, Any]) -> bool:
    """The row's position lies on X outside its pseudoautosomal regions,
    where a man carries one copy and a woman two."""
    m = _HGVS.match(str(p.get("hgvs") or "").strip())
    if not m or m.group(1) != "NC_000023":
        return False
    pos = int(m.group(2))
    return not any(lo <= pos <= hi for lo, hi in _PAR_X)


def as_hemizygous(geno: Dict[str, Any], sex: Optional[str]) -> Dict[str, Any]:
    """A reading of an X position, told by the profile's sex.

    A man has one copy there, so «one copy of the named allele» is all of it —
    state `hemi` — and a heterozygous call is not a reading at all but an
    artefact of calling his X as two copies. A file writes his single copy
    either as `T` or as `T/T`; both are the same one allele. With the sex not
    recorded the two readings cannot be told apart, and the position is not
    read rather than read as a woman's.
    """
    state = geno.get("state")
    if state == "risk_allele_not_declared" and sex != "female":
        if sex != "male":
            return {**geno, "state": "unread", "read": False, "why": "sex_unknown_on_x"}
        bases = set(str(geno.get("genotype") or "").replace("/", "").replace("|", ""))
        if len(bases) > 1:
            return {**geno, "state": "unread", "read": False, "why": "het_on_male_x"}
        if not bases or bases - set("ACGT"):
            return {**geno, "state": "unread", "read": False, "why": "genotype_not_comparable"}
        # Ploidy is known even while the clinical allele direction is open.
        return {**geno, "hemizygous": True}
    if sex == "female" or state not in ("het", "hom", "absent"):
        return geno
    if sex != "male":
        return {**geno, "state": "unread", "read": False, "why": "sex_unknown_on_x"}
    if state == "het":
        return {**geno, "state": "unread", "read": False, "why": "het_on_male_x"}
    return {**geno, "state": "hemi" if state == "hom" else "absent", "hemizygous": True}


def hemizygous_ladder(lad: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """The two states of a man's single copy, from the diploid ladder."""
    if not lad or not lad.get("base") or not lad.get("hom"):
        return None
    return {"base": lad["base"][0], "hom": lad["hom"][0]}
