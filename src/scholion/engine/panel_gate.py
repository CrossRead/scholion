"""The gate a curated panel position passes before it is read against anybody.

A position is a medical statement about one base of somebody's genome, and the
file it comes from is written by hand. Everything here answers one question —
may this row be printed at all — and answers it with a REASON, so that a row
that was dropped is counted by what is wrong with it instead of vanishing.

Three of the reasons exist because a wrong row does not look wrong. A risk
allele that is not one of the two letters at its locus — a report written on the
other strand, or a letter copied from a neighbouring row — used to be counted in
the genotype, found zero times, and printed as «the allele is absent». A strand
error read as good news. The locus is now taken from the row's own HGVS, and a
letter that is not there refuses the row before any genotype is looked at.

The other two keep the package impersonal. The product prints its own sentence,
written against a named source, and says that it was reviewed and by whom in
ROLE, never by name (task 199): a clinician's own note about one person lives in
that person's profile and never ships.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

#: A single-nucleotide change on a RefSeq chromosome, the only shape a position
#: may be addressed by: `NC_000012.12:g.21178615T>C`.
HGVS = re.compile(r"^(NC_\d{6})\.\d+:g\.(\d+)([ACGT])>([ACGT])$")

MODES = ("monogenic", "common_variant", "pgx")

#: Who may be named as the reviewer of a row's sentence, and what the card says.
#: A role, not a person: the build is read by people whose clinician is somebody
#: else, and a name under a sentence can be neither updated nor withdrawn.
REVIEWERS = {"panel_author": "author", "clinician": "clinician"}

#: A submitter is a batch — `panel_2026_09_13`, `clinical_review_2026_09` — and
#: never a person. Lower case, digits and underscores, starting with a letter.
BATCH = re.compile(r"^[a-z][a-z0-9_]*$")

_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}


def locus(p: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """The two alleles at the row's position, on the plus strand the genome is read on.

    Taken from explicit `ref`/`alt` when the row carries them, otherwise from its
    HGVS, which is always written on the plus strand.
    """
    ref, alt = p.get("ref"), p.get("alt")
    if not (ref and alt):
        m = HGVS.match(str(p.get("hgvs") or "").strip())
        if not m:
            return None
        ref, alt = m.group(3), m.group(4)
    return str(ref).upper(), str(alt).upper()


def risk_on_plus(p: Dict[str, Any]) -> Optional[str]:
    """The risk allele as the genome file writes it.

    A row declared on the minus strand (`strand: "-"`) names its allele as a
    report on that strand prints it; the genotype read from the file is on the
    plus strand, so the letter is complemented once, here, and nowhere else.
    """
    risk = p.get("risk_allele")
    if not risk:
        return None
    risk = str(risk).upper()
    return _COMPLEMENT.get(risk, risk) if str(p.get("strand") or "+") == "-" else risk


def _bilingual(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("en")) and bool(value.get("ru"))


def _texts_bilingual(text: Any) -> bool:
    """Every sentence the row carries exists in both languages.

    A row carries either one sentence (`{en, ru}`) or one per genotype state
    (`{het: {en, ru}, hom: …}`); a state left null is a sentence not yet written,
    which the card shows as pending, not a language missing.
    """
    if not isinstance(text, dict) or not text:
        return True
    if "en" in text or "ru" in text:
        return _bilingual(text)
    # The engine reads the catalogue localised, so a state may already be the
    # reader's string; the raw file is held to both languages by
    # `tests/test_a_curated_row_is_refused_for_what_is_wrong_with_it.py`.
    return all(v is None or isinstance(v, str) or _bilingual(v) for v in text.values())


def _ladder_reason(p: Dict[str, Any], risk: Optional[str]) -> Optional[str]:
    ladder = p.get("ladder")
    if ladder is None:
        return None
    if ladder == "refused":
        # The author declined to grade the genotypes; a «risk genotype» kept
        # beside that refusal is a grading after all.
        return "refusal_with_risk_genotype" if p.get("risk_genotype") else None
    top = str((ladder or {}).get("hom") or "").upper() if isinstance(ladder, dict) else ""
    if not risk or top != str(risk).upper() * 2:
        return "ladder_top_mismatch"
    return None


#: The chain a position sits on, for a system that declares links (task 200).
#: One shift arrives from different links, and the link decides which correction
#: routes can mean anything at all — so a position in such a system without one
#: is refused rather than shown under no heading.
LINKS = ("absorb", "transport", "utilize", "renal")


def refusal(p: Any, markers, sys_source: str, source: str,
            levels: Optional[Dict[str, Any]] = None,
            links: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Why this row may not be printed — or None when it may.

    `markers` is the system's laboratory panel (an expectation must name one of
    them), `source` the row's own or the system's, `levels` the legend of
    evidence levels when rows carry them.
    """
    from .panel_form import KINDS
    if not isinstance(p, dict):
        return "not_a_row"
    mode, kind = p.get("mode"), p.get("kind")
    exp = p.get("expect") if isinstance(p.get("expect"), dict) else None
    if not source:
        return "no_source"
    if not p.get("rsid"):
        return "no_rsid"
    if mode not in MODES:
        return "no_mode"
    if kind is not None and kind not in KINDS:
        return "bad_kind"
    at = locus(p)
    if at is None:
        return "no_coordinate"
    risk = risk_on_plus(p)
    if risk and risk not in at:
        return "risk_allele_not_at_locus"
    ladder = _ladder_reason(p, p.get("risk_allele"))
    if ladder:
        return ladder
    if not _texts_bilingual(p.get("text")):
        return "text_not_bilingual"
    if not _impersonal(p):
        return "personal_name_in_package"
    ev = p.get("evidence")
    if isinstance(ev, dict) and levels is not None:
        level = ev.get("level")
        if level not in levels:
            return "level_not_in_legend"
        if level == "E" and p.get("text"):
            return "level_e_with_text"
    if mode == "monogenic" and not (p.get("classification") and p.get("moi")):
        return "monogenic_without_classification_or_moi"
    level_e = isinstance(ev, dict) and ev.get("level") == "E"
    if mode == "common_variant" and not level_e and not (p.get("effect_size") and (p.get("study") or source)):
        # Level E is «no source at all»: such a row carries no effect size by
        # definition and prints a genotype with that reason (task 199 D).
        return "common_variant_without_effect"
    if exp is not None and str(exp.get("marker") or "") not in markers:
        return "expect_marker_not_in_panel"
    route = p.get("route")
    if route is not None:
        if not isinstance(route, dict):
            return "route_not_a_block"
        if route.get("basis") not in ("source", "mechanism"):
            return "route_basis_not_declared"
        if route.get("basis") == "source" and not route.get("source"):
            return "route_source_missing"
        for name in ("food", "oral_free", "iv"):
            if route.get(name) not in ("matters", "bypassed", "sharper"):
                return "route_state_unknown"
    if links:
        link = p.get("link")
        if not link:
            return "link_missing"
        if link not in links or link not in LINKS:
            return "link_not_in_legend"
    return None


def _impersonal(p: Dict[str, Any]) -> bool:
    """The row names a batch and a role, never a person."""
    sub = p.get("submitter")
    if sub is not None and not BATCH.match(str(sub)):
        return False
    rev = p.get("review")
    if rev is not None:
        if not isinstance(rev, dict) or rev.get("by_role") not in REVIEWERS:
            return False
    return "signed_by" not in p


#: Below this population frequency a variant read off a narrow input is a signal
#: to confirm, not a finding (task 2). A chip's positive predictive value for rare
#: pathogenic variants is 4.2 % for BRCA1/2 (Weedon, BMJ 2021), and 40 % of
#: variants from raw consumer data sent for confirmation were false (Moscarello
#: 2019). A monogenic row is rare by construction; one that is not says so with
#: `population_af`.
CONFIRM_BELOW_AF = 0.001


def needs_confirmation(p: Dict[str, Any], input_profile: Optional[str]) -> bool:
    """A monogenic row read off a chip or another narrow input, below the floor."""
    from .genomics import NARROW_INPUTS
    if p.get("mode") != "monogenic" or input_profile not in NARROW_INPUTS:
        return False
    af = p.get("population_af")
    return not isinstance(af, (int, float)) or af < CONFIRM_BELOW_AF


def ladder(p: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """The three genotypes of a common variant, base to top, on the row's strand.

    The author's ladder when the row carries one (the gate has held its top to
    the risk allele); otherwise the one the locus and the risk allele give, so
    the card can mark the person's own rung. None for other modes, or when the
    allele is not named.
    """
    if p.get("mode") != "common_variant":
        return None
    if isinstance(p.get("ladder"), dict):
        return {k: str(p["ladder"].get(k) or "") for k in ("base", "het", "hom")}
    at, risk = locus(p), p.get("risk_allele")
    if not at or not risk:
        return None
    risk = str(risk).upper()
    other = at[0] if risk_on_plus(p) == at[1] else at[1]
    if str(p.get("strand") or "+") == "-":
        other = _COMPLEMENT.get(other, other)
    return {"base": other * 2, "het": "".join(sorted(other + risk)), "hom": risk * 2}


def level_of(p: Dict[str, Any], levels: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The row's level, its short name, and whether a conclusion may be printed."""
    ev = p.get("evidence") if isinstance(p.get("evidence"), dict) else {}
    level = ev.get("level")
    entry = (levels or {}).get(level) or {}
    return {"level": level, "level_short": entry.get("short"),
            "verdict_allowed": bool(entry.get("verdict_allowed"))}


def legend() -> Dict[str, Any]:
    """The legend of evidence levels A–E, in the reader's language (task 199).

    One source for every surface: the page, the command line, the answers that
    carry a level, and the docs page, which a test holds to the same words.
    """
    from .. import core
    from ._helpers import DISCLAIMER
    try:
        book = core._read_knowledge("evidence_levels.json") or {}
    except Exception:                                                # noqa: BLE001
        book = {}
    meta = book.get("_meta") or {}
    levels = [x for x in book.get("levels") or [] if isinstance(x, dict) and x.get("level")]
    if not levels:
        return {"status": "unavailable", "levels": [], "disclaimer": DISCLAIMER()}
    return {"status": "ok", "key": "evidence_levels", "levels": levels,
            "verdict_levels": [x["level"] for x in levels if x.get("verdict_allowed")],
            "boundary": meta.get("boundary"), "updated": meta.get("updated"),
            "disclaimer": DISCLAIMER()}


def review_state(p: Dict[str, Any]) -> Optional[str]:
    """Who reviewed the row's sentence against its source: `author`, `clinician`, `open`."""
    rev = p.get("review") if isinstance(p.get("review"), dict) else None
    if rev:
        return REVIEWERS.get(str(rev.get("by_role") or "")) or "open"
    return "open" if p.get("note_on_review") else None


def reviewed_on(p: Dict[str, Any]) -> Optional[str]:
    rev = p.get("review") if isinstance(p.get("review"), dict) else None
    return (rev or {}).get("on")


def copies(genotype: str, allele: str, at: Optional[Tuple[str, str]]) -> Optional[int]:
    """Copies of `allele` in `genotype`, or None when the genotype is not of this locus.

    The count is refused, not zeroed, when the genotype holds a letter that is
    not one of the two at the position: a zero there would read as «absent».
    """
    g = str(genotype or "").replace("|", "").replace("/", "").strip().upper()
    if not g or not allele or set(g) - set("ACGT"):
        return None
    if at is not None and set(g) - set(at):
        return None
    return g.count(str(allele).upper())
