"""The second entry: no prescription, a class of disease.

A clinician answered the question «is the prescription the way you think about
it» with «yes, but»: when the history and the examination say a person is well,
what is wanted is the genes for the conditions where inheritance carries most of
the weight — hereditary syndromes, oncology, autoimmune, neurodegenerative,
metabolic, endocrine.

That is a different entry, not a correction of the first. The prescription
entry DERIVES its gene list from the drug; here nothing derives it — the list is
fixed in advance, which is the thing this project declined to invent when it
declined to invent panels. The refusal stands and costs nothing, because a
published list already travels inside this build: the ACMG secondary-findings
panel, 84 genes, each with its condition, its inheritance and its category, and
a citation for the whole table. Its categories are the classes this entry can
answer for. Everything else is named as absent — by class, out loud, so that a
class a clinician asked about and this build does not hold is a visible gap
rather than a screen that looks complete.

The judgement has the same three shapes as the first entry and one more, because
here reading is the whole question: something reportable was found; nothing was
found and every gene of the class was read; nothing was found and part of the
class was not read — which is not the same sentence; or the screen has not been
run at all. The third of those is the one this module exists for. «Nothing found»
over a gene nobody read is a statement about the file, and on a screening screen
it is read as health.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import core
from . import panel_form
#: The four answers and their sentences live in `panel_form` since task 171:
#: this entry was the reference for them, and the other two now say the same
#: sentence through the same code. The names keep this address.
from .panel_form import VERDICTS, one_language as _one_language  # noqa: F401


def _panel() -> Dict[str, Any]:
    """The panel with its category fields UNRESOLVED, in both languages.

    The ordinary reader resolves a localizable field to the current language,
    and a class key that changes with the language is not a key: the same
    profile would answer to «oncology» in one session and to «онкология» in the
    next. The key is the English spelling, the label is whichever the reader
    speaks, and a class is looked up by either.
    """
    import json
    path = core.PKG / "knowledge" / "acmg_sf.json" if hasattr(core, "PKG") \
        else Path(__file__).resolve().parents[1] / "knowledge" / "acmg_sf.json"
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                                                # noqa: BLE001
        return core._read_knowledge("acmg_sf.json") or {}


def _curated() -> Dict[str, Any]:
    try:
        return core._read_knowledge("disease_class_panels.json") or {}
    except Exception:                                                # noqa: BLE001
        return {}


def disease_classes() -> Dict[str, Any]:
    """The classes this build can screen, and the ones it is asked about and cannot.

    Both halves are printed. A list of what we hold, without the list of what we
    do not, reads as the whole of what there is to ask.
    """
    held: Dict[str, Dict[str, Any]] = {}
    for gene, spec in (_panel().get("genes") or {}).items():
        cat = (spec or {}).get("category")
        key = (cat.get("en") if isinstance(cat, dict) else str(cat or "")) or "—"
        row = held.setdefault(key, {"key": key, "label": _one_language(cat) or key,
                                    "aliases": _aliases(cat), "genes": [],
                                    "source": "ACMG SF"})
        row["genes"].append(gene)
    for row in held.values():
        row["genes"].sort()
        row["count"] = len(row["genes"])

    named: List[Dict[str, Any]] = []
    refused = 0
    book = _curated().get("classes") or {}
    for key, spec in book.items():
        if not isinstance(spec, dict):
            refused += 1
            continue
        source = _one_language(spec.get("source"))
        # The same gate as the prescription side, for the same reason: which
        # genes belong to a class of disease is a medical statement, and one
        # with nothing standing behind it cannot be told from one this program
        # made up.
        if not source:
            refused += 1
            continue
        genes = sorted({str(g).upper() for g in (spec.get("genes") or [])})
        named.append({"key": key, "label": key, "aliases": [key.strip().lower()],
                      "genes": genes, "count": len(genes), "source": source})

    return {"held": sorted(held.values(), key=lambda r: -r["count"]),
            "named": named, "refused": refused,
            "panel_version": (_panel().get("_meta") or {}).get("version")
            or (_panel().get("_meta") or {}).get("updated")}


def _aliases(cat: Any) -> List[str]:
    """Every spelling a reader might type for one class — both languages."""
    if isinstance(cat, dict):
        return sorted({str(v).strip().lower() for v in cat.values() if v})
    return [str(cat or "").strip().lower()]


def _find_class(key: str, listing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    q = (key or "").strip().lower()
    for row in listing["held"] + listing["named"]:
        if q == row["key"].strip().lower() or q in (row.get("aliases") or []):
            return row
    return None


def screen(class_key: Optional[str] = None) -> Dict[str, Any]:
    """What this build can say about one class of disease, gene by gene.

    With no class, the answer is the list of classes — because a reader who does
    not know which classes are answerable cannot tell a class this build has
    nothing for from one where it has looked and found nothing.
    """
    listing = disease_classes()
    if not class_key:
        return {"status": "ok", "mode": "list", **listing}

    row = _find_class(class_key, listing)
    if row is None:
        # A class named and not held is not an error and not an empty result: it
        # is the gap this entry prints out loud, because a screen that answers
        # only for what it holds looks complete.
        return {"status": "ok", "mode": "class", "class": class_key,
                "class_source": None, "count": 0, "genes": [],
                "scan_status": None, "scanned": None,
                "unread_count": 0, "read_count": 0, "finding_count": 0,
                "reportable": None,
                "verdict": {"kind": "not_determined", "why": "class_not_held"},
                "classes": listing}

    from .genomics import acmg_findings
    try:
        scan = acmg_findings() or {}
    except Exception as exc:                                         # noqa: BLE001
        scan = {"status": "unavailable", "reason": type(exc).__name__}

    panel = _panel().get("genes") or {}
    # WHICH genes were read poorly, not how many. `unread_genes` on the scan is
    # a count, and the first version of this line treated it as a list: the
    # guard silently produced an empty set, and a class holding a gene read at
    # eighty-two per cent came back «read end to end, nothing found». A clear
    # that was never measured is the one answer this entry exists to prevent.
    cov = scan.get("coverage") or {}
    unread = {str((w or {}).get("gene") or "").upper()
              for w in (cov.get("weak") or []) if isinstance(w, dict)}
    unread |= {str(g).upper() for g in (cov.get("unmeasured") or [])}
    hits = [h for h in (scan.get("hits") or []) if isinstance(h, dict)] \
        if isinstance(scan.get("hits"), list) else []
    by_gene: Dict[str, List[Dict[str, Any]]] = {}
    for h in hits:
        by_gene.setdefault(str(h.get("gene") or "").upper(), []).append(h)

    rows: List[Dict[str, Any]] = []
    for gene in row["genes"]:
        spec = panel.get(gene) or {}
        rows.append({"gene": gene,
                     "phenotype": _one_language(spec.get("phenotype")) or None,
                     "inheritance": spec.get("inheritance"),
                     "in_panel": gene in panel,
                     "read": (gene not in unread) if scan.get("status") == "ok" else None,
                     "findings": len(by_gene.get(gene) or [])})

    return {"status": "ok", "mode": "class", "class": row["key"],
            "class_label": row.get("label") or row["key"],
            "class_source": row.get("source"), "count": row["count"],
            "genes": rows, "scan_status": scan.get("status"),
            "scanned": scan.get("scanned"),
            "unread_count": sum(1 for r in rows if r["read"] is False),
            "read_count": sum(1 for r in rows if r["read"] is True),
            "finding_count": sum(r["findings"] for r in rows),
            "reportable": scan.get("reportable"),
            "coverage_threshold": (scan.get("coverage") or {}).get("threshold"),
            "verdict": verdict(rows, scan), **{"classes": listing}}


def verdict(rows: List[Dict[str, Any]], scan: Dict[str, Any]) -> Dict[str, Any]:
    """Four answers, and the third is why this module exists — see `panel_form.verdict`.

    «Nothing was found» over a gene nobody read is a statement about the file.
    On a screening screen a reader takes it for health, so the count of unread
    genes travels inside the verdict rather than in a footnote under it.
    """
    return panel_form.verdict(rows, scan)


def verdict_line(v: Dict[str, Any]) -> str:
    """The verdict in one sentence, for whichever face is printing it."""
    return panel_form.verdict_line(v)
