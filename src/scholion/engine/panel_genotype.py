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


def _genotype(rsid: str, hgvs: str, gene: str, risk_allele: Optional[str],
              scan: Dict[str, Any], at=None, has_bam: Optional[bool] = None) -> Dict[str, Any]:
    """The person's genotype at one position, as a STATE of the named allele.

    absent / het / hom count copies of the allele the author named; a position
    that was positively read (called, or confirmed against the reference) with
    no allele named is `risk_allele_not_declared` — read, and no phrase can be
    chosen for it; everything else is `unread`, with the reader's own reason,
    because a position with no row in the file is not a reference call.
    """
    if scan.get("status") != "ok":
        return {"state": None, "read": None, "why": scan.get("reason")}
    from .. import genome
    try:
        r = genome.lookup(rsid) or {}
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
        except Exception as exc:                                     # noqa: BLE001
            return {"state": "unread", "read": False, "why": type(exc).__name__}
    else:
        return {"state": "unread", "read": False, "why": r.get("status")}
    conf = res.get("confidence")
    out = {"genotype": res.get("genotype"), "confidence": conf, "depth": res.get("depth")}
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
        from .genomics import NARROW_INPUTS, gene_coverage
        if has_bam is None:
            has_bam = _has_alignment()
        why_not = None
        if has_bam:
            why_not = "alignment_at_hand"
        elif scan.get("input_profile") in NARROW_INPUTS:
            why_not = "narrow_input"
        elif rsid not in (core.loci().get("loci") or {}):
            why_not = "not_in_catalogue"
        elif (gene_coverage(gene) or {}).get("state") in ("low", "gene_not_in_table"):
            why_not = "coverage_objects"
        elif not risk_allele:
            why_not = "risk_allele_not_declared"
        if why_not:
            return {**out, "state": "unread", "read": False, "why": "assumed_ref", "presumed_refused": why_not}
        same = bool(ref) and ref.upper() == str(risk_allele).upper()
        return {**out, "state": "hom" if same else "absent", "read": False,
                "presumed": True, "why": "presumed_ref"}
    return {**out, "state": "unread", "read": False, "why": conf or "no_row"}
