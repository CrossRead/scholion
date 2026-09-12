"""Which genes bear on a named prescription, and in what way.

The product answers «gene → what we hold about it». A prescriber asks the
question from the other end: «before I give this, what in the genome bears on
it». The gene list is not something they carry — it is something they derive
from the drug, every time, and a tool that only answers the first question makes
them do that derivation by hand.

So the link between a prescription and a gene is classified here, and the CLASS
decides what may be said:

  guideline    a table for this pair exists in this build — dose, substitution,
               avoidance, with its source
  pair         the pair is recognised and this build holds no table — which is a
               statement about this build, and it travels with the copy's date
  mechanism    the gene handles this substance and no dosing rule follows
  asked_about  the gene is asked about in connection with this drug and nothing
               follows from it at all
  no_variant   named in the curated list, and this build has no variant to
               report there — which is three different facts and says which

The last three cannot be computed. Which genes belong to a prescription is a
medical statement, and so is «nothing follows from this one» — a missing gene
makes the whole answer falsely negative, and an invented reassurance is worse
than a silence. They are therefore READ from a curated file, never derived, and
an entry without a named source is dropped rather than shown: the gate is the
point of the mechanism, not a detail of it.

Which leaves the most useful thing this module does. Where no curated list
exists, the answer is not silence but a named absence — «this build holds no
context list for this prescription». Silence on that screen is filled by
whoever is talking to the reader, and what they supply comes from outside this
build entirely.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import core
from ..i18n import t as _t
from . import panel_form
#: The five kinds live in `panel_form` since task 171 — the class of a link is
#: the same vocabulary whether the list came from a drug, a class of disease or
#: a body system — and keep this address, which every consumer has used.
from .panel_form import KINDS  # noqa: F401 -- re-exported at the old address

#: The fifth class was first called «absent» and printed as «the gene is not
#: here». A clinician read it and answered: everybody has the gene; what can be
#: missing is a variant, or our knowledge of one. She was right literally, and
#: the repair goes one step further than she asked — «no variants» still glues
#: together two states this project separates everywhere else:
#:
#:   variant_called     something differs from the reference here
#:   no_variant_called  the positions were READ and matched the reference
#:   not_read           the positions are held and were not read in this file
#:   no_positions       this build holds no position for the gene at all
#:
#: The second is a measured absence of a finding; the third is an absence of
#: measurement; the fourth is a statement about this build and not about the
#: person. They read alike only on a screen, and the cost of confusing them is
#: the cost of reading «no pharmacogenetic findings» as permission to prescribe.
VARIANT_STATES = ("variant_called", "no_variant_called", "not_read", "no_positions")

#: The three answers this module gives about the DECISION rather than the gene.
#: Each is a statement about what this build holds, which is a thing that can be
#: checked, and none of them is a statement about what the reader should do.
VERDICTS = ("rule_fires", "rule_silent", "no_rule")


def _context() -> Dict[str, Any]:
    """The curated «prescription → genes» lists, or an empty one."""
    try:
        return core._read_knowledge("drug_gene_context.json") or {}
    except Exception:                                                # noqa: BLE001
        return {}


def curated_genes(drug: str, classes: Optional[List[str]] = None) -> Dict[str, Any]:
    """The curated context list for this prescription, and where it came from.

    `asked` says whether a list was found at all, which is the difference
    between «nothing bears on this» and «nobody has written down what does».
    `refused` counts entries dropped for having no source — printed as a number,
    because an entry silently dropped is an entry that looks like it never
    existed. The gate itself is `panel_form.gate`, shared with the other two
    entries: what decides whether a row may be printed is one rule, not three.
    """
    book = (_context().get("drugs") or {})
    q = (drug or "").strip().lower()
    entry = book.get(q)
    if entry is None:
        for key, value in book.items():
            names = [str(n).lower() for n in (value.get("names") or [key])]
            if q and (q in names or any(q == n for n in names)):
                entry = value
                break
    if entry is None and classes:
        for c in classes:
            if c in book:
                entry = book[c]
                break
    entry = entry if isinstance(entry, dict) else None
    # The base of the list is not written per drug any more (task 168, step 7):
    # a prescription reaches its genes through the SYSTEM its class acts on —
    # class → system → the system's genetic half, composed from a base with a
    # version and the clinician's positions. The drug entry is her layer of
    # EXCEPTIONS over that: a sentence about one gene, a class of link, or a
    # signed exclusion. A list nobody derives per drug cannot be falsely
    # negative by omission the way a hand-written one was.
    systems = _through_systems(classes if classes is not None else core.classify_drug(drug))
    if entry is None and not systems["genes"]:
        return {"asked": False, "source": None, "genes": [], "refused": 0,
                "systems": systems["systems"], "excluded": []}
    own, excluded, unsigned = _split_exclusions(entry or {})
    gated = panel_form.gate(own, (entry or {}).get("source"))
    named = {r["gene"] for r in gated["genes"] + gated["pending"]}
    inherited = [r for r in systems["genes"] if r["gene"] not in named and r["gene"] not in excluded]
    return {"asked": True, "source": gated["source"] or systems["source"],
            "genes": gated["genes"], "pending": gated["pending"] + inherited,
            "refused": gated["refused"] + unsigned, "systems": systems["systems"],
            "excluded": sorted(excluded), "inherited": len(inherited)}


def _through_systems(classes: List[str]) -> Dict[str, Any]:
    """The genes the prescription reaches through the systems its classes act on."""
    from . import system_panels as SP
    cmap = SP.class_systems()["classes"]
    keys = sorted({s for c in (classes or []) for s in cmap.get(c, [])})
    rows: List[Dict[str, Any]] = []
    seen: set = set()
    systems = []
    for key in keys:
        comp = SP.composition(key)
        systems.append({"key": key, "status": comp["status"], "genes": len(comp["genes"])})
        for g in comp["genes"]:
            if g["gene"] not in seen:
                seen.add(g["gene"])
                rows.append({"gene": g["gene"], "kind": None, "text": "",
                             "source": _t("decision.via_system", source=g["source"], system=key),
                             "via_system": key, "origin": g["origin"]})
    composed = [s["key"] for s in systems if s["status"] == "composed"]
    return {"systems": systems, "genes": rows,
            "source": _t("decision.through_systems", systems=", ".join(composed))
            if composed else None}


def _split_exclusions(entry: Dict[str, Any]):
    """The entry's rows apart from its exclusions: an `exclude` row with a source
    (its own, or the list's) strikes the gene from the inherited list; one with
    no source anywhere is refused and COUNTED, like any unattributed row."""
    own: Dict[str, Any] = {}
    excluded: set = set()
    unsigned = 0
    for gene, spec in (entry.get("genes") or {}).items():
        if isinstance(spec, dict) and spec.get("exclude"):
            if panel_form.one_language(spec.get("source")) or panel_form.one_language(entry.get("source")):
                excluded.add(str(gene).upper())
            else:
                unsigned += 1
        else:
            own[gene] = spec
    return own, excluded, unsigned


def variant_state(gene: str) -> Dict[str, Any]:
    """What this build can say about variants in one gene, and on what evidence.

    Decided from the data every time — from the positions the catalogue holds
    for the gene and from what the person's own file says at each of them. Never
    from a default: a state that arrives because nothing else matched is exactly
    the silence this class was renamed to stop printing.
    """
    from .. import genome
    g = (gene or "").upper()
    book = core.loci().get("loci") or {}
    held = [rs for rs, e in book.items()
            if isinstance(e, dict) and (e.get("gene") or "").upper() == g]
    out: Dict[str, Any] = {"gene": g, "positions": len(held)}
    if not held:
        out["state"] = "no_positions"
        return out
    called, confirmed, depths = [], [], []
    for rs in held:
        try:
            res = (genome.lookup(rs) or {}).get("result") or {}
        except Exception:                                            # noqa: BLE001
            continue
        conf = res.get("confidence")
        if conf == "called":
            called.append(rs)
        elif conf == "confirmed_ref":
            confirmed.append(rs)
        if isinstance(res.get("depth"), (int, float)):
            depths.append(float(res["depth"]))
    # How many of the positions the catalogue holds were not read at all. Left
    # out, this was the same glue one level down: eight positions held for a
    # gene, two of them confirmed against the reference and six with no row in
    # the file, printed as one reassuring «no variants».
    out.update({"called": len(called), "confirmed_ref": len(confirmed),
                "unread": len(held) - len(called) - len(confirmed),
                "depth_min": min(depths) if depths else None,
                "depth_max": max(depths) if depths else None})
    if called:
        out["state"] = "variant_called"
    elif confirmed:
        out["state"] = "no_variant_called"
    else:
        out["state"] = "not_read"
    return out


def classify(genome_section: Dict[str, Any], drug: str = "",
             classes: Optional[List[str]] = None) -> Dict[str, Any]:
    """The genes this build can bring to a named prescription, by class of link.

    The first two classes are computed — they are facts about this build's own
    tables. The rest are read from the curated list, and the answer says plainly
    when there is no list to read.
    """
    g = genome_section or {}
    cp = g.get("cpic") or {}
    blocks: Dict[str, List[Dict[str, Any]]] = {k: [] for k in KINDS}

    for row in (g.get("genes") or []):
        # A gene the build could actually phenotype is the only one that can
        # carry a rule. One it holds without being able to read it belongs with
        # the recognised-but-undecided pairs, not with the deciding ones.
        target = "guideline" if row.get("computable") else "pair"
        blocks[target].append({"gene": row.get("gene"), "kind": target,
                               "phenotype": row.get("phenotype"),
                               "label": row.get("label"),
                               "actionable": bool(row.get("actionable")),
                               "coverage": row.get("coverage") or {},
                               "level": row.get("cpic_level")})

    curated = curated_genes(drug, classes)
    known = {r["gene"] for rows in blocks.values() for r in rows}
    named: List[Dict[str, Any]] = []
    for row in list(curated["genes"]) + [{**r, "pending": True}
                                         for r in curated.get("pending") or []]:
        if row["gene"] in known:
            continue
        entry = dict(row)
        if entry.get("kind") not in KINDS:
            named.append(entry)
            continue
        # The fifth class is the only one whose answer depends on this person's
        # file rather than on the catalogue alone, so it is measured here.
        if entry["kind"] == "no_variant":
            entry["variant"] = variant_state(entry["gene"])
        blocks[entry["kind"]].append(entry)

    # The second verdict, and it is not this module's. `verdict` below answers
    # about the DECISION — did a rule fire. `panel_verdict` answers about the
    # READING of the curated list in the four states every list shares: were
    # the genes a clinician named read at all, and how many were not. Without
    # it a prescription screen could carry a context list of five genes, none
    # of them read, under a sentence that says nothing about that.
    listed = list(curated["genes"]) + [{**r, "pending": True}
                                       for r in curated.get("pending") or []]
    scan = panel_form.scan_for([r["gene"] for r in listed]) if listed \
        else {"status": "ok", "genes": []}
    rows = [panel_form.gene_row(r["gene"], r, scan) for r in listed]
    return {"blocks": blocks, "named": named, "curated": curated,
            "snapshot": cp.get("snapshot"), "asked": bool(cp.get("asked")),
            "reason": cp.get("reason"),
            "verdict": verdict(blocks, cp),
            "panel_rows": rows,
            "panel_verdict": panel_form.verdict(rows, scan) if listed else None}


def verdict(blocks: Dict[str, List[Dict[str, Any]]], cpic: Dict[str, Any]) -> Dict[str, Any]:
    """One of three, and every one of them is about this build, not the reader.

    «The rule fires» is not advice and «the rule is silent» is not clearance:
    both say what this build's own tables did when the person's genotype was put
    through them, which is a thing that can be checked. The third says no rule
    could be reached and names why — and that one is the whole reason the other
    two can be trusted.
    """
    rules = blocks.get("guideline") or []
    if not rules:
        return {"kind": "no_rule",
                "why": ("not_asked" if not (cpic or {}).get("asked") else "no_pair")}
    fired = [r for r in rules if r.get("actionable") and r.get("phenotype")
             not in (None, "", "unknown", "reported", "NM", "normal")]
    if fired:
        return {"kind": "rule_fires", "genes": [r["gene"] for r in fired]}
    return {"kind": "rule_silent", "genes": [r["gene"] for r in rules]}


def verdict_line(v: Dict[str, Any]) -> str:
    """The verdict in one sentence, for whichever face is printing it."""
    kind = (v or {}).get("kind")
    if kind == "rule_fires":
        return _t("decision.rule_fires", genes=", ".join(v.get("genes") or []))
    if kind == "rule_silent":
        return _t("decision.rule_silent", genes=", ".join(v.get("genes") or []))
    why = (v or {}).get("why") or "no_pair"
    return _t("decision.no_rule", why=_t("decision.why." + why))
