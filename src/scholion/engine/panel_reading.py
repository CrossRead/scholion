"""What «read» means for a row, and why a row was not read (tasks 175, 201, 203).

Four states where there were two — read · read with the depth unmeasured ·
taken by the reference · not read — and the classes of reason that differ in
WHAT CLOSES THEM. Split out of `panel_form.py` on 18.09.2026; the names stay
reachable there.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..i18n import plural as _plural, t as _t


#: A coverage table that was never made says nothing about the gene — it does
#: not say the gene was not read. The file read it; how deeply is unmeasured.
#: A table that WAS made and found the gene thin is a different answer, and that
#: one is «not read» (owner, 17.09.2026: «правда в том, что ген прочитан,
#: покрытие не измерено»).
NO_TABLE = {"coverage_not_measured", "coverage_gene_not_in_table", "coverage_unavailable",
            "coverage_unmeasured", "coverage_absent"}


def _coverage_step(gene: str, coverage: Dict[str, Any]) -> Dict[str, Any]:
    """Describe a measured interval with its own ploidy and comparison baseline."""
    depth = 10 if coverage.get("copies") == 1 else 20
    pct = coverage.get(f"pct_{depth}x")
    median = coverage.get(f"median_pct_{depth}x")
    return {"origin": "coverage", "gene": gene, "why": "coverage_low",
            "coverage": coverage,
            "text": _t("system.next.coverage", gene=gene, depth=depth,
                       pct=pct if pct is not None else "—",
                       median=median if median is not None else "—")}


def read_state(read: bool, why: Optional[str]) -> str:
    """`read` · `file_only` · `presumed` · `unread` — four answers where there were two.

    `presumed` (task 201) is a value the file did not state and the reference
    implies: the position has no row because it matched the reference, and no
    alignment is here to read it from. It is a value, and it is not a reading.
    """
    if read:
        return "read"
    code = str(why or "")
    if code in NO_TABLE:
        return "file_only"
    if code == "presumed_ref":
        return "presumed"
    return "unread"


#: Why a row is not read, in the four classes that differ in WHAT CLOSES THEM.
#: A reader who is told «28 of 373 are unread» and has just run every recompute
#: the product offered is owed the next step, and the next step is not the same
#: for a gene read too thinly (deeper sequencing) as for a position with no row
#: in the file (genotype it from the alignment) — owner, 17.09.2026.
UNREAD_CLASSES = (
    ("thin", ("coverage_low", "coverage_weak")),
    ("no_table", ("coverage_not_measured", "coverage_gene_not_in_table", "coverage_unavailable",
                  "coverage_unmeasured", "coverage_absent")),
    ("no_row", ("assumed_ref", "no_row", "position_not_resolved", "genotype_not_comparable")),
    # The build of the file was never established, so an empty position means
    # either «no variant here» or «read in the wrong coordinate system».
    ("build", ("no_row_and_build_unknown",)),
    ("clinvar", ("clinvar_not_run", "clinvar_unavailable", "clinvar_not_ready",
                 "clinvar_input_too_narrow")),
)


def unread_class(why: Optional[str]) -> str:
    code = str(why or "")
    for name, codes in UNREAD_CLASSES:
        if code in codes:
            return name
    return "other"


#: What closes each class of reason — a COMMAND where a command does it, so a
#: model reading the structure does not have to parse a sentence (task 203).
CLOSES_WITH = {"thin": None, "no_table": "scholion recompute", "no_row": "scholion recompute",
               "build": "scholion choose-genome", "clinvar": None, "other": None}


def unread_block(v: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The reasons as a FIELD beside `unread_line`: class, count, what closes it."""
    counts = (v or {}).get("why_counts") or {}
    presumed = int((v or {}).get("presumed") or 0)
    if not counts and not presumed:
        return None
    order = [n for n, _ in UNREAD_CLASSES] + ["other"]
    rows = [{"reason": k, "positions": counts[k], "closes_with": CLOSES_WITH.get(k),
             "text": _t("screen.unread_all." + k)} for k in order if counts.get(k)]
    return {"total": sum(counts.values()), "by_reason": rows,
            "presumed_ref": {"positions": presumed, "closes_with": "an alignment (BAM) beside the profile, then scholion recompute"} if presumed else None}


def _unread_counts(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in rows:
        if r.get("read") is False and r.get("read_state") != "presumed":
            k = unread_class(r.get("read_why"))
            out[k] = out.get(k, 0) + 1
    return out


def _unread_breakdown(counts: Dict[str, int]) -> str:
    """«27 read too thinly, 1 with no coverage measured» — each with its own cure."""
    order = [n for n, _ in UNREAD_CLASSES] + ["other"]
    named = [name for name in order if counts.get(name)]
    if len(named) == 1:
        # One reason for all of them: repeating the count after having just
        # given it reads as two different numbers to check against each other.
        return _t("screen.unread_all." + named[0])
    return " · ".join(_t("screen.unread." + name, rows=_plural(counts[name], "count.rows"))
                      for name in named)


def unread_line(v: Dict[str, Any]) -> Optional[str]:
    """Explain the limitations that apply to the rows beside the verdict."""
    counts = (v or {}).get("why_counts") or {}
    presumed = int((v or {}).get("presumed") or 0)
    if not counts and not presumed:
        return None
    parts = []
    if len(counts) == 1 and counts.get("thin") and v.get("total"):
        parts.append(_plural(v["total"], "screen.unread_thin_panel", affected=counts["thin"]))
    elif counts:
        parts.append(_t("screen.unread_next", why=_unread_breakdown(counts)))
    if presumed:
        # Its own counter, outside the reasons (task 201): these are not gaps
        # in the file, and they are not readings either.
        parts.append(_t("screen.and_presumed", rows=_plural(presumed, "count.rows")))
    return "; ".join(parts)


def _read_why_text(code) -> Optional[str]:
    """The reason a gene or a position was not read, as a sentence in the
    reader's language — the code (`clinvar_not_run`) printed as such on every
    row and every basket line until 13.09.2026."""
    if not code:
        return None
    text = _t("system.read_why." + str(code))
    if text.startswith("⟦"):
        text = _t("genome.refused_head." + str(code))
    return _t("system.read_why.unknown") if text.startswith("⟦") else text
