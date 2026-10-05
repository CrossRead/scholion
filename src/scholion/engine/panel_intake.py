"""Patient readings of the full intake list, separate from its reference book."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .. import core
from ..i18n import t as _t


@core.in_reading
def author_readings() -> Dict[str, Any]:
    """Every intake row, with sourced local values, never a new verdict.

    This supplement does not assign a waiting position to a disease panel or
    turn a refused classification into a finding. Resolution is LOCAL ONLY:
    opening a list is not permission to send its rsIDs to a remote service.
    """
    from .. import genome
    from .panel_catalogue import panel_description
    from ..genome_routes import decision_route
    book = panel_description("author_list")
    state = genome.available()
    recorded = core.profile_genotypes()
    from .labs import analyze_labs
    markers = {m['key']: m for m in analyze_labs()['markers']}
    for row in book["positions"]:
        # Hypothetical sentences for every genotype belong to the reference
        # book, not beside this person's value. Existing system cards retain
        # their findings and hypothesis passports; this view is a reading list.
        row["text"] = {}
        row["reading"] = _intake_reading(row["rsid"], state, row.get("read_refusal"),
                                         recorded.get(row["rsid"]))
        row["value_only"] = row.get("level") == "E"
        row['decision_route'] = decision_route(row, markers)
    book.update(reference_only=False, patient_readings=True, register="clinician",
                reading_note=_t("panel.patient_readings_note"), genome_status=state)
    book["counts"]["read"] = sum(p["reading"]["read"] for p in book["positions"])
    return book


def _intake_reading(rsid: str, state: Dict[str, Any], refusal: Optional[str] = None,
                    recorded: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    from .. import genome
    out: Dict[str, Any] = {"read": False, "genotype": None, "reason": None}
    loc = genome.resolve_rsid(rsid, allow_network=False)
    if refusal == "indel_unsupported":
        out["reason"] = refusal
    elif not loc:
        out["reason"] = "position_not_resolved"
    elif genome._indel_event(loc):
        out["reason"] = "indel_unsupported"
    elif not state.get("ready"):
        out["reason"] = "input_unavailable"
    else:
        try:
            value = genome._gt_at(loc) or {}
        except (OSError, ValueError):
            # A failed local read is shown as a refusal, never a reference call.
            value = {"confidence": "read_failed"}
        confidence = value.get("confidence")
        out["confidence"] = confidence
        out["source"] = value.get("source")
        out["depth"] = value.get("depth")
        out["quality"] = {k: value[k] for k in ("low_depth", "depth_unverified", "filtered",
                           "strand_ambiguous", "imputed", "confirmation_reasons") if k in value}
        if confidence in ("called", "confirmed_ref", "called_array") and value.get("genotype"):
            out.update(read=True, genotype=value["genotype"])
        else:
            out["reason"] = "not_positively_read"
    if not out["read"] and recorded and recorded.get("genotype") and recorded.get("source"):
        # C26: the absence of a current file call must not erase a sourced
        # value already written in this container. It is NOT a fresh VCF call.
        out.update(read=True, genotype=recorded["genotype"], confidence="profile",
                   source=recorded["source"], depth=None, reader_refusal=out["reason"],
                   reason=None, quality={})
        out["message"] = _t("panel.reading.recorded", genotype=out["genotype"], source=out["source"])
    else:
        out["message"] = (_t("panel.reading." + out["reason"]) if out["reason"] else
                      _t("system.row.genotype", genotype=out["genotype"],
                         confidence=out.get("confidence") or "—",
                         depth=out["depth"] if out.get("depth") is not None else "—"))
    return out
