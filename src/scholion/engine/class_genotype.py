"""A class of prescription against a genotype that changes whether it may be given.

The table is `knowledge/class_genotype_cautions.json`: a class, an allele, the
reading of it that matters, and a caution with its source. Asked from two ends:

* a prescription being considered — `cautions(classes)` adds the caution to
  the safety flags of the prescription check, printed before anything else;
* the regimen already taken — `regimen_cautions()` walks the current
  prescriptions, so the overview, the treatment view and the genome view can
  say it without anybody having to ask.

Until 0.6.0 the one such combination on the demo — factor V Leiden under a
combined oral contraceptive — lived only as a sentence in the profile's own
notes, and no screen printed it (the interface review of 25.09.2026).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import core
from ..conclusion_basis import conclusion_basis
from ..i18n import lang as _lang, t as _t


def _table() -> List[Dict[str, Any]]:
    data = core._read_knowledge("class_genotype_cautions.json")
    return [c for c in (data.get("cautions") or []) if isinstance(c, dict)]


def _state(rule: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The person's reading at the rule's position: the state and where it came from.
    None when nothing reads it — a caution is never raised on a guess."""
    from . import panel_gate
    got = core.genotype_status(rule["rsid"]) or {}
    if not got.get("genotype") or got.get("confidence") not in ("called", "reported"):
        return None
    loc = (core.loci().get("loci") or {}).get(rule["rsid"]) or {}
    at = (str(loc["ref"]).upper(), str(loc["alt"]).upper()) if loc.get("ref") and loc.get("alt") else None
    risk = str(rule["risk_allele"]).upper()
    copies = panel_gate.copies(got["genotype"], risk, at)
    if copies is None and at and set(at) not in ({"A", "T"}, {"C", "G"}):
        # A report writes a minus-strand gene in the gene's letters (F5: G/A for C/T).
        flip = "".join(panel_gate._COMPLEMENT.get(c, c) for c in str(got["genotype"]).upper())
        copies = panel_gate.copies(flip, risk, at)
    if copies is None:
        return None
    return {"state": ("absent", "het", "hom")[min(copies, 2)], "genotype": got["genotype"],
            "source": got.get("source") or "vcf"}


def _one(value: Any) -> str:
    if isinstance(value, dict):
        return value.get(_lang()) or value.get("en") or next(iter(value.values()), "")
    return str(value or "")


def cautions(classes: List[str], drug: str = "") -> List[Dict[str, Any]]:
    """Safety flags for a prescription of these classes, in the shape of the
    person's own flags (`pgx._own_safety_flags`), so the renderer prints both."""
    out = []
    for rule in _table():
        if rule.get("class") not in (classes or []):
            continue
        st = _state(rule)
        if not st or st["state"] not in (rule.get("states") or []):
            continue
        basis = conclusion_basis(rule)
        supported = basis["status"] == "complete" and rule.get("level") in ("A", "B")
        out.append({"severity": (rule.get("severity") or "caution") if supported else "caution", "origin": "genotype",
                    "drug": drug, "class": rule["class"], "gene": rule.get("gene"),
                    "rsid": rule["rsid"], "genotype": st["genotype"], "state": st["state"],
                    "genotype_source": st["source"], "level": rule.get("level"),
                    "factor": _one(rule.get("summary")) if supported else None,
                    "why_it_matters": _one(rule.get("why")) if supported else None,
                    "action": _one(rule.get("action")) if supported else None, "source": basis["source"],
                    "conclusion_basis": basis,
                    "mechanism": basis["mechanism"] if supported else None,
                    "interpretation_withheld": not supported,
                    "uncertainty": (basis["reason"] or _t("conclusion.caution_level")) if not supported else None})
    return out


def regimen_cautions() -> List[Dict[str, Any]]:
    """The same cautions for every prescription the person takes now."""
    out: List[Dict[str, Any]] = []
    for med in core.active_medications():
        name = med.get("name") or ""
        out += cautions(core.classify_drug(name), name)
    return out


def medications_view() -> Dict[str, Any]:
    """The regimen as every face reads it: the list, and what a genotype read
    says against any of it. One function, so the CLI, the page and the tool
    cannot drift apart on whether the caution is printed."""
    from .. import store
    from .treatment import treatment_timeline
    return {"medications": store.list_medications(), "cautions": regimen_cautions(),
            "treatment": treatment_timeline()}
