"""Rendering primitives shared by `format` and the pages split out of it.

This module imports nothing from the package except the message catalogue, and
that is its whole reason to exist. `format_system` used to take these four names
from `format`, while `format` imported `format_system` at its last line; the pair
worked only while `format` happened to be imported first, and
`import scholion.format_system` on its own died with a circular import. A leaf
that both depend on makes that loop impossible by construction.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .i18n import plural as _plural, t as _t  # noqa: F401


_PRIO_ICON = {"high": "🔴", "moderate": "🟠", "low": "🟢"}


def subclaim_lines(row: Dict[str, Any]) -> List[str]:
    """Print an adjacent claim's own basis, or the reason it was withheld."""
    return [_t("conclusion.subclaim." + name) + ": " +
            (str(basis.get("reason")) if basis.get("status") == "incomplete" else
             str(basis.get("mechanism") or "") + " — " + str(basis.get("source") or ""))
            for name, basis in (row.get("subclaim_basis") or {}).items()]


def _flag_icon(flag: str) -> str:
    return {"high": "🔴", "low": "🔵", "ok": "🟢"}.get(flag, "•")


def _level_counts_line(counts: Dict[str, int]) -> str:
    parts = [f"{k} — {counts[k]}" for k in ("A", "B", "C", "D", "E") if counts.get(k)]
    return _t("system.genetics.levels", levels=", ".join(parts) or "—", none=counts.get("none", 0))


def genotype_conclusion_lines(positions: List[Dict[str, Any]]) -> List[str]:
    """The genotype of a system as one conclusion — assembled from the panel's
    own sentences, never phrased here: which named alleles were found and what
    the panel says of each, which were not carried, which were not read."""
    # A position with no reading at all — no genome, a build nobody could tell —
    # is not read, whatever its state says; «none found» over such a panel
    # would claim a check that never happened.
    held = [p for p in positions if (p.get("conclusion_basis") or {}).get("status") == "incomplete"]
    available = [p for p in positions if (p.get("conclusion_basis") or {}).get("status") != "incomplete"]
    observed = [p for p in positions if p.get("read") is True and p.get("state") in ("het", "hom", "hemi")]
    found = [p for p in available if p.get("read") is True and p.get("state") in ("het", "hom", "hemi")]
    absent = [p for p in available if p.get("read") is True and p.get("state") == "absent"]
    unread = [p for p in positions if p.get("read") is not True]
    name = lambda p: f"{p.get('gene')} {p.get('rsid') or ''}".strip()
    L = ["**" + _t("system.panel.conclusion_h") + "**"]
    if observed:
        L.append(_t("system.panel.conclusion_found", found=len(observed),
                    positions=_plural(len(positions), "count.positions"),
                    genes=", ".join(name(p) for p in observed)))
        L += ["  · " + (p.get("text") or name(p)) for p in found]
    elif not held and len(unread) < len(positions):
        L.append(_t("system.panel.conclusion_none_found",
                    positions=_plural(len(positions) - len(unread), "count.positions")))
    if absent:
        L.append(_t("system.panel.conclusion_absent", genes=", ".join(name(p) for p in absent)))
    L += [name(p) + " — " + str((p.get("genotype") or {}).get("genotype") or "—") + "; " +
          p["conclusion_basis"]["reason"] for p in held]
    L += [name(p) + " — " + detail for p in positions for detail in subclaim_lines(p)]
    from .genome_routes import route_text
    L += [name(p) + ' — ' + route_text(p) for p in positions if route_text(p)]
    if unread:
        L.append(_t("system.panel.conclusion_unread",
                    positions=_plural(len(unread), "count.positions"),
                    genes=", ".join(name(p) for p in unread)))
    # The genotype against the measurements, in the same words as the page: a
    # found position that names a marker is a question (printed among the
    # questions); none found says so; the alleles not carried say what did not apply.
    L.append("**" + _t("system.panel.compare_h") + "**")
    if not held and not any(p.get("expect") for p in found):
        L.append(_t("system.panel.compare_none"))
    na: Dict[str, List[str]] = {}
    for p in absent:
        if p.get("expect"):
            na.setdefault(p["expect"].get("name") or p["expect"].get("marker") or "—", []).append(name(p))
    L += [_t("system.panel.compare_absent", name=k, positions=", ".join(v)) for k, v in sorted(na.items())]
    return L


_LEVEL_ICON = {"high": "🔴", "moderate": "🟠", "low": "🟢", "unknown": "⚪"}


_FLAG_ICON = {"high": "🔴", "low": "🟠", "ok": "🟢"}


_NEAR_ICON = "🟡"          # within range, but pressed against the edge of the corridor


# No reference range at all. Deliberately a neutral dot rather than any colour:
# every colour on this scale is a verdict, and there is nothing here to base one
# on. A green tick beside a number with no corridor reads as «this is fine» —
# which is a statement about a person made from the absence of data.
_NORANGE_ICON = "·"


def _mark_icon(m, default="•"):
    """Marker icon: 🟡 for "within range but at the edge", otherwise the plain flag."""
    if m.get("near_limit") and m.get("flag") == "ok":
        return _NEAR_ICON
    if m.get("flag") in ("norange", "unconfirmed_rule"):
        # The same neutral mark as «no corridor». Both mean the value stands and
        # no verdict is offered on it; a green tick here would be a claim.
        return _NORANGE_ICON
    return _FLAG_ICON.get(m.get("flag"), default)


def _decision_suffix(m, context=False) -> str:
    """Clinical action thresholds. Crossed ones are always shown; ones not crossed only
    in the context of a drug, where they are the substantive answer ("haematocrit below the
    intervention threshold of 54 — there is headroom")."""
    ds = m.get("decisions") or []
    hit = [d for d in ds if d.get("crossed")]
    # `crossed: None` — the value could not be compared with the threshold. It
    # is printed wherever a crossed one would be, because it may BE crossed;
    # «not reached» is said only of a threshold that was actually compared.
    open_ = [d for d in ds if "crossed" in d and d["crossed"] is None]
    out = []
    for d in hit:
        out.append(" · ❗" + _t("decision.crossed", label=d["label"],
                               sign={"gt": ">", "lt": "<"}.get(d.get("comparison"), "≥" if d.get("side") == "high" else "≤"),
                               value=f"{d['value']:g}"))
    for d in open_:
        value = f"{d['value']:g}" if isinstance(d.get('value'), (int, float)) else '—'
        if d.get('why') == 'threshold_basis':
            out.append(' · ' + _t('decision.withheld', value=value, reason=d['threshold_basis']['reason']))
        else:
            out.append(" · " + _t("decision.censored" if d.get('why') == 'censored' or d.get('value') is None else "decision.not_comparable", value=value,
                                  label=d["label"]))
    resolved = [d for d in ds if d.get("crossed") is False]
    if context and not hit and not open_ and resolved:
        d = resolved[0]
        out.append(" · " + _t("decision.not_reached", value=f"{d['value']:g}", label=d["label"]))
    for d in hit + (resolved[:1] if context and not hit and not open_ else []):
        basis = d.get('threshold_basis') or {}
        if basis.get('status') == 'complete':
            out.append(f" · {basis['mechanism']} [{basis['source']}]")
        action_basis = d.get('action_basis') or {}
        if d.get('action'):
            out.append(f" · {d['action']} · {action_basis.get('mechanism', '')} [{action_basis.get('source', '')}]")
        elif d.get('crossed') is True and action_basis.get('status') == 'incomplete':
            out.append(' · ' + _t('decision.action_gap', reason=action_basis['reason']))
    return "".join(out)


def _near_suffix(m) -> str:
    nl = m.get("near_limit")
    if not nl or m.get("flag") != "ok":
        return ""
    side = _t("near.upper" if nl["side"] == "high" else "near.lower")
    cp = (", " + _t("near.corridor", pct=f"{nl['corridor_pct']:g}")
          if nl.get("corridor_pct") is not None else "")
    mv = f"; {nl['movement']}" if nl.get("movement") else ""
    # Task 100. The caveat travels WITH the claim it qualifies. A move measured
    # between two days, one of which the form never printed, is a move of
    # uncertain size, and saying so anywhere else than here would be saying it
    # where nobody is reading.
    if nl.get("date_caveat"):
        mv += " " + nl["date_caveat"]
    return " · " + _t("near.at_edge", margin=f"{nl['margin_pct']:g}", side=side,
                      bound=f"{nl['bound']:g}") + cp + mv


def _fmt_ref(m: Dict[str, Any]) -> str:
    """The corridor beside the value — and, when it is a guess, that it is one.

    `ref_sex_unknown` was computed by the engine for months and read by nobody:
    a grep of the whole tree found it only in the file that produced it. It marks
    exactly the case where the range shown may be the wrong one — the marker's
    interval differs by sex and the profile never recorded a sex — which is how a
    woman's normal testosterone was printed against a male corridor. A safety
    signal that nothing renders is not a safety signal.
    """
    if m.get("proposed_rule"):
        return ""
    lo, hi = m.get("ref_low"), m.get("ref_high")
    warn = f" {_t('ref.sex_unknown')}" if m.get("ref_sex_unknown") and (
        lo is not None or hi is not None) else ""
    # A corridor that is not this draw's own says so: the marker's recorded
    # range answering for a form that printed none is a weaker claim than the
    # range printed beside the number, and the two must not read alike.
    origin = f" {_t('ref.origin_profile')}" if m.get("ref_origin") == "profile" else ""
    if lo is not None and hi is not None:
        return f" [{_t('ref.range', low=lo, high=hi)}]{warn}{origin}"
    if hi is not None:
        return f" [{_t('ref.max', high=hi)}]{warn}{origin}"
    if lo is not None:
        return f" [{_t('ref.min', low=lo)}]{warn}{origin}"
    if m.get("sex_not_applicable"):
        return f" {_t('ref.sex_not_applicable')}"
    if m.get("ref_sex_other"):
        return f" {_t('ref.sex_other_no_range')}"
    if m.get("ref_sex_unreviewed"):
        return f" {_t('ref.sex_unreviewed_no_range')}"
    if m.get("ref_sex_unknown"):
        return f" {_t('ref.sex_unknown_no_range')}"
    if m.get("ref_age_other"):
        return f" {_t('ref.age_other_no_range')}"
    if m.get("ref_age_unknown"):
        return f" {_t('ref.age_unknown_no_range')}"
    if m.get("ref_age_unbanded"):
        return f" {_t('ref.age_unbanded_no_range')}"
    return ""


def _depth_span(v: Dict[str, Any]) -> str:
    """«26×» when the positions agree, «24–34×» when they do not."""
    lo, hi = v.get("depth_min"), v.get("depth_max")
    if lo is None or hi is None:
        return "—"
    fmt = lambda x: f"{x:g}"                                    # noqa: E731
    return fmt(lo) + "×" if lo == hi else f"{fmt(lo)}–{fmt(hi)}×"


def _variant_state_line(v: Dict[str, Any]) -> str:
    """On what evidence this build has nothing to report in a gene.

    Four states and not one of them is «the gene is absent» — everybody has the
    gene. Read and matching the reference, held and unread, and held nowhere are
    three different facts, and the first of them is the only one that is a
    finding rather than a gap.
    """
    state = v.get("state")
    if not state:
        return ""
    if state == "variant_called":
        return "_" + _t("decision.variant.variant_called", n=v.get("called") or 0) + "_"
    if state == "no_variant_called":
        line = _t("decision.variant.no_variant_called",
                  n=v.get("confirmed_ref") or 0, total=v.get("positions") or 0,
                  depth=_depth_span(v))
        # The positions with no row are named in the same breath. Two confirmed
        # out of eight held is not «no variants in this gene»; it is a finding
        # about two of them and a gap about six.
        if v.get("unread"):
            line += "; " + _t("decision.variant.and_unread", n=v["unread"])
        return "_" + line + "_"
    if state == "not_read":
        return "_" + _t("decision.variant.not_read", n=v.get("positions") or 0) + "_"
    return "_" + _t("decision.variant.no_positions") + "_"


def _context_lines(ctx: Dict[str, Any]) -> List[str]:
    """The three classes that carry no rule, and the named absence of the list.

    The computed classes are printed by the block below this one — they have
    genotypes to show. These three have only sentences, and a sentence about
    what does not follow from a gene is printed with its source or not at all.

    The last line is the one worth having. Where nobody has written a context
    list for this prescription, the answer says so; a screen that says nothing
    there is completed by whoever is talking to the reader, out of knowledge
    that is not in this build and has passed none of its filters.
    """
    if not ctx:
        return []
    out: List[str] = []
    blocks = ctx.get("blocks") or {}
    for kind in ("mechanism", "asked_about", "no_variant"):
        for row in blocks.get(kind) or []:
            said = (str(row.get("text")) if row.get("text")
                    else _t("decision.not_written_yet"))
            out.append("- **" + str(row.get("gene")) + "** — "
                       + _t("decision.kind." + kind) + ": " + said)
            vs = _variant_state_line(row.get("variant") or {})
            if vs:
                out.append("  " + vs)
            out.append("  _" + _t("decision.source", source=str(row.get("source"))) + "_")
    # Named and unclassified: a gene a clinician put on the list, whose class of
    # link she has not assigned either. Assigning one here would be this program
    # answering a medical question on her behalf.
    for row in ctx.get("named") or []:
        out.append("- **" + str(row.get("gene")) + "** — " + _t("decision.kind.unassigned"))
        out.append("  _" + _t("decision.source", source=str(row.get("source"))) + "_")
    cur = ctx.get("curated") or {}
    # The systems the prescription's class acts on, each with what it handed
    # over: a system whose genetic half is not composed is named as such,
    # because «no genes inherited» from it is a fact about the build.
    for s in cur.get("systems") or []:
        out.append("_" + (_t("decision.system_reached", system=s.get("key"), n=s.get("genes") or 0)
                          if s.get("status") == "composed"
                          else _t("decision.system_not_composed", system=s.get("key"))) + "_")
    if cur.get("excluded"):
        out.append("_" + _t("decision.excluded_by_clinician", genes=", ".join(cur["excluded"])) + "_")
    if not cur.get("asked"):
        out.append("_" + _t("decision.no_context_list") + "_")
    elif cur.get("refused"):
        # Dropped entries are counted out loud. One that vanishes quietly is
        # indistinguishable from one that was never written, and the gate that
        # dropped it then looks like an empty file.
        out.append("_" + _t("decision.entries_without_source", n=cur["refused"]) + "_")
    if out:
        out.append("")
    return out


def _gene_coverage_note(ge: Dict[str, Any]) -> str:
    """The coverage line for a gene on the prescription path, or nothing.

    One state is silent and it is `fine`, which means «not unusual for this
    file» and never «enough»: sufficiency depends on the question, and the
    product does not know the question. Every other state speaks, because on
    this screen a silence is read as permission.
    """
    c = ge.get("coverage") or {}
    if not c or c.get("state") == "fine":
        return ""
    return "_" + _coverage_line(c) + "_"


def _coverage_line(c: Dict[str, Any]) -> str:
    """One line about how well this gene was read.

    `fine` is deliberately terse and deliberately not «adequate»: the product
    does not know what the reader's question needs, only that this gene is not
    unusual for this file. Every other state carries its number.
    """
    state = c.get("state")
    if state == "low":
        return _t("gene.coverage.low", pct=c.get("pct_20x"),
                  median=c.get("median_pct_20x"))
    if state == "fine":
        return _t("gene.coverage.fine", pct=c.get("pct_20x"))
    if state == "gene_not_in_table":
        return _t("gene.coverage.not_in_table", n=c.get("table_size") or 0)
    if state == "unavailable":
        # A table that could not be read, told apart from one nobody made:
        # «not measured» sends the reader to run the measurement, and here the
        # measurement exists.
        return _t("gene.coverage.unavailable", reason=c.get("reason") or "—")
    return _t("gene.layer.coverage_no")


_SEV_ICON = {"high": "🔴", "moderate": "🟠", "low": "🟢"}


_TIER_ICON = {"drug": "💊", "pathogenic": "🔴", "risk": "🟠", "protective": "🟢"}


def _clinvar_block(cv: Dict[str, Any]) -> str:
    """Block of ClinVar findings that relate to the drug (drug_response and others)."""
    if not cv or not cv.get("available") or not cv.get("hits"):
        return ""
    out = ["\n**🧬 " + _t("clinvar_block.header") + "**"]
    for h in cv["hits"][:12]:
        ic = _TIER_ICON.get(h.get("tier"), "•")
        sig = (h.get("clnsig") or "").replace("_", " ")
        via = (_t("clinvar_block.via_gene", gene=h["gene"]) if h.get("gene")
               else _t("clinvar_block.via_name"))
        dis = f" — {h['disease']}" if h.get("disease") else ""
        gt = _t("clinvar_block.genotype", genotype=h.get("genotype", "?"))
        out.append(f"{ic} `{h.get('rsid','')}` {sig} ({gt}, {via}){dis}")
    return "\n".join(out)


def _n(x: Any) -> str:
    try:
        return str(int(x)) if float(x).is_integer() else str(x)
    except Exception:
        return str(x)


#: The most of a prescription note that the LIST prints. These notes are prose
#: somebody wrote at the time, and a «first sentence» can itself run for three
#: hundred characters; `--json` and `prescription` carry the whole of it.
NOTE_FOLD_CEILING = 150


#: Abbreviations a full stop does not end a sentence after. A fold that cut at
#: «e.g. » printed «Take with food, e.g…» and lost the example it was folding
#: to keep. Short on purpose: the cases seen in real notes, not a dictionary.
_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "т.е.", "т.к.", "напр.", "др.")


def _first_sentence(note: str) -> str:
    """The first sentence of a note, with the ceiling above applied to it."""
    start = 0
    head = note
    while True:
        cut = note.find(". ", start)
        if cut < 0:
            break
        before = note[:cut + 1]
        if any(before.endswith(a) for a in _ABBREVIATIONS):
            start = cut + 1
            continue
        head = before[:-1]
        break
    head = head.strip()
    if len(head) > NOTE_FOLD_CEILING:
        head = head[:NOTE_FOLD_CEILING].rsplit(" ", 1)[0]
    return head


def _status_mark(m: Dict[str, Any]) -> str:
    """The status of an entry that is NOT current, for a listing.

    Every place that lists the regimen printed a stopped drug in the same
    shape as one taken this morning. The comparison already excluded it —
    and a list that does not say so shows the reader a regimen the engine
    is not using.
    """
    from . import core
    if core.is_active_medication(m):
        return ""
    return " " + _t("medications.not_current", status=m.get("status") or "—")


# ---- the update procedure (scholion version) ---------------------------------
def spelling_note(tail: str = "recompute") -> str:
    """One line, only where it is needed: how this machine spells the commands just printed.

    Empty when `scholion` is a word the shell knows, which is the usual case and
    deserves no line at all."""
    from . import recompute as _rc  # noqa: E402
    prefix = _rc.program_prefix()
    if prefix == "scholion":
        return ""
    return _t("command.spelled_here", prefix=prefix, example=f"{prefix} {tail}".strip())


def recompute_why(step: Dict[str, Any]) -> str:
    why = step.get("why")
    if not why:
        return ""
    d = step.get("detail") or {}
    positions = d.get("positions")
    return _t("recompute.why." + str(why), file=d.get("file") or "—", engine=d.get("engine") or "—",
              domain=d.get("domain") or "—",
              positions=_plural(int(positions), "count.positions") if isinstance(positions, int) else "—")
