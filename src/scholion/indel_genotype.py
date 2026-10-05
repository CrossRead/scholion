"""Read explicitly curated repeats from anchored VCF alleles, never from absence.

A verified reference window permits equivalent padding within a repeat, not
general left alignment or classification of a novel structural variant.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .i18n import t


def read(loc: Dict[str, Any]) -> Dict[str, Any]:
    from . import genome, linear
    vp = genome.vcf_path()
    base: Dict[str, Any] = {"source": "vcf", "genotype": None}
    def refused(why, **detail):
        return {**base, "confidence": why, "note": t("genome.indel_not_read"), **detail}
    if not vp or genome.file_unreadable(vp):
        return refused("unreadable_file")
    sample = genome.sample_index(str(vp))
    if sample is None:
        return refused("sample_not_chosen")
    assembly = genome.assembly_of(str(vp))
    pos = genome.locus_position(loc, assembly) if assembly else None
    if pos is None:
        return refused("no_coordinates_for_assembly", assembly=assembly)
    spec = loc.get("repeat_call") or {}
    window = str(spec.get("reference") or "").upper()
    labels = spec.get("alleles") or {}
    if not window or set(window) - set("ACGT") or window not in labels:
        return refused("alleles_not_comparable")
    try:
        rows = genome._query_region_range(str(vp), loc["chrom"], pos, pos + len(window) - 1)
    except genome.ContigNotInFile:
        return refused("contig_not_in_file")
    except genome.RangeNeedsIndex:
        return refused("needs_index")
    except linear.Unreadable as exc:
        return refused(exc.why, detail=exc.detail)
    calls: List[Dict[str, Any]] = []
    for row in rows:
        try:
            offset = int(row[1]) - pos
            ref = row[3].upper()
            if not ref or set(ref) - set("ACGT") or offset < 0 or window[offset:offset + len(ref)] != ref:
                continue
            alternatives = row[4].upper().split(",")
            haplotypes = [window[:offset] + alt + window[offset + len(ref):]
                          for alt in [ref] + alternatives]
            # A lone anchor or a symbolic block cannot establish repeat length.
            if not any(h != window and h in labels for h in haplotypes[1:]):
                continue
            values = dict(zip(row[8].split(":"), row[9 + sample].split(":")))
            raw = values.get("GT", "")
            indices = raw.replace("|", "/").split("/")
            if len(indices) != 2 or any(not i.isdigit() for i in indices):
                return refused("no_call_in_vcf")
            called_labels = [labels.get(haplotypes[int(i)]) for i in indices]
            if any(a is None for a in called_labels):
                return refused("alleles_not_comparable")
            alleles = [str(a) for a in called_labels]
            call: Dict[str, Any] = {**base, "genotype": "/".join(alleles), "alleles": alleles,
                    "confidence": "called", "assembly": assembly, "read_pos": pos,
                    "ref": ref, "alt": row[4], "raw_genotype": raw,
                    "depth": int(values["DP"]) if values.get("DP", "").isdigit() else None,
                    "filter": row[6], "note": t("genome.indel_called")}
            if re.search(r"(?:^|;)IMPUTED(?:;|$)|(?:^|;)TYPED=0(?:;|$)", row[7]):
                call["imputed"] = True
            if call["depth"] is not None and call["depth"] < genome._MIN_DEPTH:
                call["low_depth"] = True
            if row[6] not in ("PASS", ".", ""):
                call["filtered"] = True
            genome._mark_depth_unverified(call)
            calls.append(call)
        except (ValueError, IndexError, TypeError):
            return refused("malformed_genotype")
    if not calls:
        return refused("indel_not_read", assembly=assembly, read_pos=pos)
    if len({tuple(sorted(c["alleles"])) for c in calls}) != 1:
        return refused("alleles_not_comparable")
    # Equivalent rows may agree on alleles but disagree on quality. A duplicate
    # must never make the least-qualified observation look confirmed.
    if len(calls) > 1:
        return refused("duplicate_repeat_calls")
    return calls[0]
