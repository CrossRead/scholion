"""The one form three entries share: kinds, the gate, a gene row, the verdict.

Three things generate a list of genes — a prescription (`decision.py`), a class
of disease (`screening.py`) and a body system (`system_panels.py`) — and they
differ only in where the list comes from and what the subject is called. The
FORM is the same: five kinds of link; a gate that prints an entry only when it
carries both a sentence and a source and counts what it dropped; a gene named
without a sentence kept as pending; a row that says whether the gene was read;
and a verdict in four states that carries the count of unread genes inside it.

Task 171 put the form here before the third entry was written, for one reason:
the refusal is the product. «Nothing was found, and part of the list was not
read» is the sentence every entry exists to say, and three copies of it drift
into three sentences within a week — one of which will eventually call a list
clear that nobody read. One copy cannot drift, and
`tests/test_three_entries_refuse_in_one_voice.py` holds the three entries to it.

What this module does NOT decide is what a list contains or what the subject
is. It classifies, gates, counts and phrases; the entries own their lists.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional

from ..i18n import CATALOGUES, DEFAULT as _DEFAULT, plural as _plural, t as _t
from .panel_reading import (CLOSES_WITH, NO_TABLE, UNREAD_CLASSES, _unread_breakdown, _unread_counts,  # noqa: F401
                            read_state, unread_block, unread_class, unread_line)

#: In the order a reader should meet them: what decides, what is recognised but
#: undecided, what explains without deciding, what explains nothing, what is
#: absent. The order is also the order of strength, and it is used as one.
KINDS = ("guideline", "pair", "mechanism", "asked_about", "no_variant")

#: The four answers, and the order is the order of strength. `clear_partial` is
#: not a weaker `clear_measured` — it is a different claim, and the count of
#: genes nobody read is what separates them.
VERDICTS = ("finding", "clear_measured", "clear_partial", "not_determined")


def one_language(raw: Any) -> str:
    """One of the two, and it is the reader's.

    A version of this preferred Russian whatever the reader spoke, because the
    line was copied from a place where the catalogue was already resolved. A
    curated file may be read UNRESOLVED — that is what keeps a class key stable
    across languages — so the choice has to be made on purpose, and a report in
    English came out with Russian phenotypes until it was.
    """
    if isinstance(raw, dict):
        from ..i18n import lang as _lang
        code = _lang() or "en"
        raw = raw.get(code) or raw.get("en") or raw.get("ru")
    return str(raw or "").strip()


def gate(entries: Dict[str, Any], list_source: Any = None, *,
         resolve: Callable[[Any], str] = one_language) -> Dict[str, Any]:
    """The curated rows that may be printed, the ones that wait, and a count of the rest.

    `entries` is `{SYMBOL: spec}` as a curated file holds it. Three outcomes per
    entry, and the third is a number rather than a silence:

      genes    — a sentence AND a source: printed
      pending  — a source (its own, or the list's) and no sentence: printed as
                 waiting, because it is the most informative row on the screen —
                 a clinician put the gene there, and what follows is still to be
                 written
      refused  — no source anywhere, or a kind outside the five: dropped and
                 COUNTED, so that a dropped entry is visible as a number rather
                 than looking like one that never existed
    """
    list_src = resolve(list_source)
    out: List[Dict[str, Any]] = []
    pending: List[Dict[str, Any]] = []
    refused = 0
    for gene, spec in (entries or {}).items():
        if not isinstance(spec, dict):
            refused += 1
            continue
        text = resolve(spec.get("text"))
        source = resolve(spec.get("source")) or list_src
        kind = spec.get("kind")
        # The gate. A sentence about what does not follow from a gene is a
        # medical statement; unattributed, it is indistinguishable from one this
        # program made up, and this program does not make them.
        # The CLASS is hers too. Putting a gene she named into «handles this
        # substance, no dosing rule follows» would be this program deciding a
        # medical question on her behalf — the very thing the gate exists to
        # stop, one field over from the sentence it already guards. A row may
        # arrive with no class, and then it is printed as named and unclassified.
        if (kind is not None and kind not in KINDS) or not source:
            refused += 1
            continue
        row = {"gene": (gene or "").upper(), "kind": kind,
               "text": text, "source": source}
        # A gene somebody NAMED and whose sentence nobody has written yet is a
        # third thing, and dropping it with the unattributed ones was wrong: it
        # is the most informative row on the screen. It says a clinician put
        # this gene on the list, and that what follows from it is still to be
        # written — which is a request, addressed to a person, and visible.
        (out if text else pending).append(row)
    out.sort(key=kind_order)
    pending.sort(key=kind_order)
    return {"genes": out, "pending": pending, "refused": refused,
            "source": list_src or None}


def kind_order(row: Dict[str, Any]) -> tuple:
    """Rows in the order of the kinds, unclassified last, then by symbol."""
    kind = row.get("kind")
    return (KINDS.index(kind) if kind in KINDS else len(KINDS), row.get("gene") or "")


def scan_for(genes: Iterable[str]) -> Dict[str, Any]:
    """Whether THIS person's genome can be read at all, as the scan the verdict needs.

    The screening entry runs the ACMG scan and hands its result in; the
    prescription and system entries hold lists the scan was never built for, so
    they ask the genome frame directly. Either way the verdict receives one
    shape — `status` and, when it is not «ok», the reason — and the entries
    never phrase the refusal themselves.
    """
    from .. import genome
    names = sorted({str(g).upper() for g in genes})
    try:
        st = genome.available() or {}
    except Exception as exc:                                         # noqa: BLE001
        return {"status": "unavailable", "reason": type(exc).__name__, "genes": names}
    if st.get("ready"):
        # The measured class of the input travels with the scan: a rare variant
        # read off a chip is a signal to confirm, not a finding (task 2).
        return {"status": "ok", "genes": names, "input_profile": st.get("input_profile")}
    # `reason` is what the verdict prints and it names THIS refusal — the genome
    # is not readable — while the frame's own code travels beside it for the
    # basket that sends the reader to the genome status. Put straight into the
    # verdict, the frame's code printed «the coordinate was found, but…» over a
    # list of genes, a sentence about a locus lookup nobody had made.
    return {"status": "not_ready", "reason": "not_ready",
            "genome_reason": st.get("reason") or "no_file", "genes": names}


def gene_row(gene: str, entry: Optional[Dict[str, Any]] = None,
             scan: Optional[Dict[str, Any]] = None, *,
             layers: bool = False) -> Dict[str, Any]:
    """One gene on a list, with what this build measured about it.

    `variant_state` — read and matching the reference is not the same as not
    read; `coverage` — four states, and only `fine` may be silent; `read` — the
    boolean the verdict counts, decided from the variant state (a gene whose
    positions were read, whether or not anything was called, is read; one whose
    positions were not, or which this build holds no position for, is not) and
    left `None` when the scan did not run, so that no gene is counted either
    way on a genome nobody could open.

    `layers` — the full frame of a gene (catalogue, ClinVar by coordinate, the
    ACMG panel) is asked for only when a reader wants it: it scans a table per
    gene and a list of eighty genes does not need it eighty times to print.
    """
    from .decision import variant_state
    from .genomics import gene_coverage, gene_layers
    g = (gene or "").upper()
    row: Dict[str, Any] = dict(entry or {})
    row["gene"] = g
    row.setdefault("pending", not bool(row.get("text")))
    if scan is not None and scan.get("status") != "ok":
        row["variant_state"] = None
        row["coverage"] = None
        row["read"] = None
    else:
        vs = variant_state(g)
        row["variant_state"] = vs
        row["coverage"] = gene_coverage(g)
        row["read"] = vs.get("state") in ("variant_called", "no_variant_called")
    row.setdefault("findings", 0)
    if layers:
        row["layers"] = gene_layers(g)
    return row


def bases_read(gene: str, coverage: Optional[Dict[str, Any]] = None,
               rows=None) -> "tuple":
    """Were this gene's bases read — `(True, None)` or `(False, reason)`.

    One definition for every entry that asks (task 175). Only a coverage table
    that measured the gene and found it ordinary for this file says yes; a table
    nobody made says `coverage_not_measured`, never yes. The screening entry
    used to take its unread genes from the ACMG scan's weak list alone, which is
    empty without a table — and a class read nowhere came back «read end to
    end».
    """
    from .genomics import gene_coverage
    cov = coverage if coverage is not None else gene_coverage(gene, rows)
    state = (cov or {}).get("state")
    if state == "fine":
        return True, None
    return False, "coverage_" + str(state or "not_measured")


def verdict(rows: List[Dict[str, Any]], scan: Dict[str, Any]) -> Dict[str, Any]:
    """Four answers, and the third is why this form exists.

    «Nothing was found» over a gene nobody read is a statement about the file.
    On a screening screen a reader takes it for health, so the count of unread
    genes travels inside the verdict rather than in a footnote under it.

    A row counts as a finding through `findings` (an integer), as unread through
    `read is False`, and — the system entry's case — as a carrier through
    `carrier`: one copy of a recessive allele is not a finding about the person's
    own risk and does not turn the verdict, but it is not nothing either, so its
    count travels beside the others and the sentence names it.
    """
    if (scan or {}).get("status") != "ok":
        return {"kind": "not_determined",
                "why": (scan or {}).get("reason") or "scan_not_run"}
    found = sum(int(r.get("findings") or 0) for r in rows)
    # The list holds genes AND, in the system entry, positions of a curated
    # panel; a row is one entry of it either way. The count below is over the
    # whole list — the three entries answer in one voice (task 171), and a
    # per-half count would give three sentences for one state. What was wrong
    # on the lipid card was the NOUN: «unread of its genes: 34, of a list of
    # 45» over a list of 38 genes and 7 positions. The sentence now says rows,
    # and the summary above it counts each half against its own denominator.
    # Taken by the reference (task 201): not read, and not a gap either — its
    # own counter, outside «read N of M», and it never lets the list be called
    # read end to end.
    # It stays among the unread for the VERDICT — the three entries answer one
    # state in one voice, and two of them do not know a position's state — and
    # is named apart on the line beside it.
    presumed = [r["gene"] for r in rows if r.get("read_state") == "presumed"]
    unread = [r["gene"] for r in rows if r.get("read") is False]
    # Read by the file, with the depth unmeasured: not a gap in the list and not
    # a measured «nothing here» either, so it is counted on its own and said.
    depthless = [r["gene"] for r in rows if r.get("read_state") == "file_only"]
    carriers = sum(1 for r in rows if r.get("carrier"))
    out: Dict[str, Any]
    if found:
        # A finding does not cancel the gap. A list can hold both, and a
        # sentence that reports the first and drops the second lets a reader
        # take the rest of the list for checked.
        out = {"kind": "finding", "n": found, "unread": len(unread),
               "total": len(rows), "why_counts": _unread_counts(rows),
               "genes": sorted({r["gene"] for r in rows if r.get("findings")})}
    elif unread:
        out = {"kind": "clear_partial", "unread": len(unread),
               "total": len(rows), "genes": sorted(set(unread))[:12],
               "why_counts": _unread_counts(rows),
               # The rows are counted, the NAMES are listed, and one gene can
               # hold two rows — so the two numbers differ and the sentence says
               # so rather than letting a reader count the names and disbelieve
               # the number (owner, 17.09.2026).
               "gene_count": len(set(unread)), "genes_shown": min(12, len(set(unread)))}
    elif depthless:
        out = {"kind": "clear_file_only", "total": len(rows), "depthless": len(depthless)}
    else:
        out = {"kind": "clear_measured", "total": len(rows)}
    if depthless and out["kind"] != "clear_file_only":
        out["depthless"] = len(depthless)
    if presumed:
        out["presumed"] = len(presumed)
    if carriers:
        out["carriers"] = carriers
    return out


def _why_text(why: str) -> str:
    """The reason in words: the screen's own vocabulary first, then the genome
    frame's refusals, then the code itself rather than a placeholder — a reason
    the catalogue does not know is still a reason, and ⟦…⟧ is not."""
    from ..i18n import lang as _lang
    cats = (CATALOGUES.get(_lang() or _DEFAULT, {}), CATALOGUES.get(_DEFAULT, {}))
    for prefix in ("screen.why.", "genome.refused."):
        if any((prefix + why) in c for c in cats):
            return _t(prefix + why)
    return why


def verdict_line(v: Dict[str, Any]) -> str:
    """The verdict in one sentence, for whichever face is printing it."""
    kind = (v or {}).get("kind")
    if kind == "finding":
        line = _t("screen.finding", n=v.get("n") or 0,
                  genes=", ".join(v.get("genes") or []))
        if v.get("unread"):
            line += "; " + _t("screen.and_unread", unread=_plural(v["unread"], "count.rows"),
                              total=v.get("total") or 0)
    elif kind == "clear_measured":
        line = _t("screen.clear_measured", total=v.get("total") or 0)
    elif kind == "clear_file_only":
        line = _t("screen.clear_file_only", total=v.get("total") or 0,
                  depthless=v.get("depthless") or 0)
    elif kind == "clear_partial":
        # No list of names and no lecture: the names are in the rows underneath,
        # and the sentence a reader needs here is what is missing and what would
        # close it (owner, 17.09.2026: «это вообще лишнее»).
        line = _t("screen.clear_partial", unread=_plural(v.get("unread") or 0, "count.rows"),
                  total=v.get("total") or 0)
    else:
        return _t("screen.not_determined",
                  why=_why_text((v or {}).get("why") or "scan_not_run"))
    if v.get("depthless") and kind != "clear_file_only":
        line += "; " + _t("screen.and_depth_unmeasured", rows=_plural(v["depthless"], "count.rows"))
    if v.get("carriers"):
        line += "; " + _t("screen.and_carriers", n=v["carriers"])
    return line
