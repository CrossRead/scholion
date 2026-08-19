"""Small shared leaves every domain module reaches for.

Kept deliberately tiny: date-window filtering, the standing disclaimer, basis
notes for phenotype calls, and two cycle-breaking leaves (_active_names_by_class,
_brief_num) that used to live inside the pgx and lifestyle clusters -- moving
them here is what lets labs<->pgx and half of lifestyle<->pgx import one way.
"""
from __future__ import annotations

import datetime
from typing import Any, Dict, List
from .. import core
from ..i18n import t as _t


def _recent(date_str: str, months: int = 12) -> bool:
    """A date (YYYY-MM / YYYY-MM-DD) no older than `months` from today (sliding window).
    Unrecognised dates are not hidden (True is returned)."""
    if not date_str:
        return False
    try:
        parts = str(date_str).split("-")
        y, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 1
    except Exception:
        return True
    today = datetime.date.today()
    cy, cm = today.year, today.month - months
    while cm <= 0:
        cm += 12
        cy -= 1
    return (y, m) >= (cy, cm)


def DISCLAIMER() -> str:
    """The standing caveat under every report.

    A function and not a constant: the language is chosen when the report is built,
    and the web server builds two reports in two languages at the same time.
    """
    return _t("disclaimer.general")


# ==========================================================================
# 1. Checking a prescription against pharmacogenetics
# ==========================================================================
_OPS = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b}


def _match_count(count: int, expr: str) -> bool:
    """Check of a condition of the form '>=2' / '==1' against the number of allele copies."""
    for op in (">=", "<=", "==", ">", "<"):
        if expr.startswith(op):
            return _OPS[op](count, int(expr[len(op):]))
    return count == int(expr)


def _basis(gene: str, gdef: Dict[str, Any], found: List[Dict[str, Any]]) -> Dict[str, Any]:
    """What was read for this gene, what was not, and whether the gap can be closed.

    Exists because "unknown" on its own is a dead end for the reader. Knowing that
    a phenotype was not determined tells nobody what to do; knowing that one of
    two markers was read, that the missing one is rs12248560 (*17), and that its
    coordinates are in the locus catalogue so a full VCF closes it — that is an
    instruction. The same structure decides whether an answer may be called
    ASSUMED rather than refused: a partial panel still carries information, and
    throwing it away is its own kind of dishonesty.
    """
    model = gdef.get("markers", []) if gdef else []
    read = {f["rsid"] for f in found}
    from .. import genome as _genome          # lazy: genome imports core, core imports nothing back
    try:
        catalogue = _genome.loci().get("loci", {}) or {}
    except Exception:                                            # noqa: BLE001
        catalogue = {}
    missing = []
    for m in model:
        if m["rsid"] in read:
            continue
        missing.append({"rsid": m["rsid"], "star": m.get("star", ""),
                        "function": m.get("function", ""),
                        "obtainable": m["rsid"] in catalogue})
    # Deficient alleles the project's own catalogue knows and this gene's model does
    # not. Named because a reader is entitled to know that the panel is narrower
    # than the data the project already ships.
    modelled = {m["rsid"] for m in model}
    not_modelled = [r for r, e in catalogue.items()
                    if e.get("gene") == gene and r not in modelled]
    return {"read": sorted(read), "total": len(model),
            "missing": missing, "not_modelled": sorted(not_modelled)}


def _basis_note(gene: str, basis: Dict[str, Any]) -> str:
    """One sentence: what is there, what is missing, and what would close it."""
    parts = []
    read, total = len(basis["read"]), basis["total"]
    if total:
        parts.append(_t("basis.read", read=read, total=total))
    miss = basis["missing"]
    if miss:
        names = ", ".join(f"{m['rsid']}{(' (' + m['star'] + ')') if m['star'] else ''}"
                          for m in miss)
        parts.append(_t("basis.missing", names=names))
        # "Build a VCF" is the wrong instruction when the VCF is already there and
        # these very positions carry no row in it. The remedy then is to genotype
        # them from the BAM, and `basis.not_called` says so a line below; offering
        # both would be advice that argues with itself.
        not_called = set(basis.get("not_called") or [])
        outstanding = [m for m in miss if m["rsid"] not in not_called]
        if outstanding:
            if any(m["obtainable"] for m in outstanding):
                parts.append(_t("basis.obtainable"))
            else:
                parts.append(_t("basis.not_in_catalogue"))
    if basis.get("not_called"):
        # A different remedy from "you have no VCF": the file is there, these
        # positions simply carry no row, so the answer is to genotype them from
        # the BAM rather than to build a VCF.
        parts.append(_t("basis.not_called", names=", ".join(basis["not_called"])))
    if basis["not_modelled"]:
        parts.append(_t("basis.not_modelled", names=", ".join(basis["not_modelled"])))
    return " ".join(parts)


def _active_names_by_class() -> Dict[str, List[str]]:
    """Which of the patient's concrete prescriptions fall into each active class."""
    out: Dict[str, List[str]] = {}
    names = core.medications_json().get("medications", [])
    classes = core.med_classes().get("classes", {})
    for m in names:
        nm = m.get("name", "")
        for cls in core.classify_drug(nm):
            out.setdefault(cls, [])
            if nm not in out[cls]:
                out[cls].append(nm)
    return out


def _brief_num(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return f"{v:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return str(v)
