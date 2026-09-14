"""The panel of a body system as the catalogue describes it — for the clinician, with the studies.

The radar shows a person the panel read against their genome; a clinician asked
for the panel itself: what each position is, why it is in the panel, which
guideline or study it rests on, what it expects of a marker, and who signed the
sentence (owner, 14.09.2026). That is a description of knowledge, not of a
person: nothing here reads the genome or the labs, so the same page is right for
anybody and carries no personal data. The radar keeps the reading; this page
carries the references.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..i18n import t as _t
from . import panel_form
from ._helpers import DISCLAIMER
from .system_panels import _curated, _labels, domains

#: What a position carries, in the order the page prints it. `text` is the
#: authored sentence per genotype state, in both languages; the page prints the
#: reader's own.
_FIELDS = ("rsid", "gene", "hgvs", "protein", "risk_allele", "mode", "kind", "source", "study",
           "effect_size", "classification", "moi", "disease", "submitter", "curated_on",
           "signed_by", "signed_on")


def _position(p: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: p.get(k) for k in _FIELDS}
    # The catalogue is read localised: a phrase is already the reader's string,
    # or still a {en, ru} pair when read raw — both are taken.
    text = p.get("text") if isinstance(p.get("text"), dict) else {}
    out["text"] = {state: (panel_form.one_language(v) if isinstance(v, dict) else str(v))
                   for state, v in text.items() if state in ("het", "hom") and v}
    exp = p.get("expect") if isinstance(p.get("expect"), dict) else None
    out["expect"] = ({"marker": exp.get("marker"), "direction": exp.get("direction"),
                      "note": panel_form.one_language(exp.get("note"))} if exp else None)
    out["signature"] = "clinician" if p.get("signed_by") == "clinician" else (
        "author" if p.get("signed_by") else "open")
    return out


def panel_description(key: Optional[str] = None) -> Dict[str, Any]:
    """One system's panel as the catalogue holds it; with no key, every system that has one."""
    cur = _curated()
    systems = cur.get("systems") or {}
    meta = cur.get("_meta") or {}
    known = {d["key"] for d in domains()}
    if key and key not in known:
        return {"status": "unknown_system", "key": key, "systems": sorted(known)}
    if not key:
        return {"status": "ok", "systems": [
            {"key": k, "label": _t("radar.domain." + k), "positions": len((s or {}).get("positions") or []),
             "unreadable": len((s or {}).get("unreadable") or {})}
            for k, s in systems.items() if k in known]}
    spec = systems.get(key) if isinstance(systems.get(key), dict) else {}
    positions = [_position(p) for p in spec.get("positions") or [] if isinstance(p, dict)]
    by_gene: Dict[str, List[Dict[str, Any]]] = {}
    for p in positions:
        by_gene.setdefault(str(p.get("gene") or "—").upper(), []).append(p)
    unreadable = [{"gene": g, "reason": panel_form.one_language((u or {}).get("reason")),
                   "source": (u or {}).get("source")}
                  for g, u in (spec.get("unreadable") or {}).items()]
    # The catalogue's `_meta` notes and the spec's `source` are written to the
    # panel's authors — a repository path, a note on how `signed_by` is read.
    # The page for a clinician carries each row's own source and study instead.
    return {"status": "ok", "key": key, "label": _t("radar.domain." + key), "labels": _labels(key),
            "catalogue_updated": meta.get("updated"), "source_tier": meta.get("source_tier"),
            "positions": positions, "genes": [{"gene": g, "positions": v} for g, v in sorted(by_gene.items())],
            "unreadable": unreadable,
            "counts": {"positions": len(positions), "genes": len(by_gene),
                       "signed_by_clinician": sum(1 for p in positions if p["signature"] == "clinician"),
                       "with_study": sum(1 for p in positions if p.get("study")),
                       "with_expectation": sum(1 for p in positions if p.get("expect"))},
            "disclaimer": DISCLAIMER()}
