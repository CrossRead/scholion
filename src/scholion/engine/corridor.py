"""Which corridor a laboratory point may be judged by, and why.

One question, asked of every point: «may this number be compared with that
corridor». It grew inside `analyze_labs` over one day in three steps — the sex
of a corridor, its age band and the words `unreviewed` and `applies_to_sex`,
then the corridor printed on the point's own form — and raised that module's
budget three times on the same subject. That is a domain, not a paragraph.

Two answers live here. `point_corridor` says which bounds apply to one point
and where they came from: the form that carried the draw, the range recorded on
the marker, or the reference base — and, when the base's corridor is withheld,
the one nearer reason it is withheld. `flags_comparable` says whether the flags
of a series still share one ruler. Both return structures; `labs.analyze_labs`
places them, and the renderers read the flag names unchanged.

Every profile fact is read through `core` at call time, never cached at import,
so that a test which patches `core.profile_sex` or `core.lab_markers` sees its
patch take effect here as it did when this code lived in `labs`.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from .. import core
from ..i18n import t as _t


def _sex_adjusted_bounds(k: str, m: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return sex-corrected {ref_low, ref_high, ref_sex} for a marker, or None.

    The rule is «a form-read range wins, a defaulted range gets corrected». The
    reference on a marker in the profile is usually the interval PRINTED on the
    person's own lab form, and that is already sex-appropriate — it must be left
    alone. Only when the stored range equals the knowledge-base DEFAULT (the
    historical male range) do we know it was filled in rather than read, and only
    then do we swap in the sex-specific bounds. Sex unknown → no correction and a
    caveat is raised by the caller, never a silent guess.
    """
    kb = core.lab_markers().get("markers", {}).get(k) or {}
    by_sex = kb.get("ref_by_sex")
    if not by_sex:
        return None
    default = (kb.get("ref_low"), kb.get("ref_high"))
    if (m.get("ref_low"), m.get("ref_high")) != default:
        return None                       # a form-specific range — trust it
    sex = core.profile_sex()
    if sex not in ("male", "female"):
        return {"ref_low": m.get("ref_low"), "ref_high": m.get("ref_high"),
                "ref_sex": None, "ref_sex_unknown": True}
    b = by_sex.get(sex) or {}
    return {"ref_low": b.get("ref_low"), "ref_high": b.get("ref_high"), "ref_sex": sex}


def point_corridor(k: str, m: Dict[str, Any], point: Dict[str, Any]) -> Dict[str, Any]:
    """The corridor one point of marker `k` is judged by, and why that one.

    `m` is the marker as stored in the profile (its recorded `ref_low`/`ref_high`
    are the latest known range); `point` is the draw being judged. Precedence:
    the range printed on the point's own form, then the marker's recorded range,
    then the reference base — and the base is lent only when nothing about the
    person refuses it. The result carries the bounds, `ref_origin` (`form`,
    `profile`, `reference_base`, or None), and every refusal flag the renderers
    read, each False unless it is the reason.
    """
    # The corridor this draw was judged by on its own form, if it printed one
    # (task 142). It beats the marker's recorded range and the reference base
    # alike: those are «the latest known» and «the general population», and
    # neither is a statement about this draw. An ionised calcium of 1.09
    # read as deeply low against a range recorded months earlier, while the
    # form that carried it printed 1.10–1.35 and called it a hair under.
    own = {f: point.get(f) for f in ("ref_low", "ref_high") if point.get(f) is not None}
    ref_origin: Optional[str] = None
    if own:
        m = {**m, "ref_low": own.get("ref_low"), "ref_high": own.get("ref_high")}
        ref_origin = "form"
    elif m.get("ref_low") is not None or m.get("ref_high") is not None:
        ref_origin = "profile"
    # A value with NO corridor at all, for a marker the reference base has an
    # interval for: two facts held and never compared. The person's own form
    # is always preferred — this only fills a hole, never overrides — and the
    # borrowed interval is LABELLED, because a general population range is a
    # weaker statement than the range the person's own laboratory printed and
    # must not be shown as if it were the same thing.
    borrowed = False
    sex_unknown_no_range = False
    sex_other = False
    age_other = age_unknown = age_unbanded = False
    sex_unreviewed = sex_not_applicable = False
    if m.get("ref_low") is None and m.get("ref_high") is None:
        kb = core.lab_markers().get("markers", {}).get(k) or {}
        # The same rule that stops ingest substituting a sex-specific default
        # applies to borrowing one. Six markers in this base keep the MALE
        # range as their top-level default; lending it to a person whose sex
        # was never asked for is the defect, whichever code does the lending.
        sex_blocked = bool(kb.get("ref_by_sex")) and core.profile_sex() not in ("male", "female")
        # And the same defect one step further out. A marker with only ONE
        # corridor is the commoner case, and that corridor was transcribed
        # from the forms of one person: `ref_sex` says whose. Lending a man's
        # ceiling for GGT or a man's floor for HDL to a woman does not fail —
        # it produces a verdict, and the wrong one, with a green tick beside
        # it. The remedy the person can act on is their own form, so the
        # corridor is withheld and the reason is printed.
        owner = kb.get("ref_sex")
        if owner == "unreviewed":
            # Declared, and declared unknown: the corridor could not be
            # checked against a form or a standard interval. Lent to nobody
            # — an unchecked claim is the thing this whole rule refuses.
            sex_blocked = sex_unreviewed = True
        elif owner and owner != "any" and core.profile_sex() != owner:
            sex_blocked = sex_other = True
        # A test that exists for one sex only is a different fact from a
        # corridor that belongs to one sex: PSA does not apply to a woman at
        # all, and «the interval is a man's» would be the wrong sentence.
        only = kb.get("applies_to_sex")
        if only and core.profile_sex() in ("male", "female") and core.profile_sex() != only:
            sex_blocked = sex_not_applicable = True
            sex_other = False
        # Age is the same class as sex, one axis over. IGF-1 and DHEA-S
        # depend on age more than on sex, and every laboratory bands them;
        # the dictionary held ONE corridor for each, transcribed from one
        # person's form at one age, and lent it to everybody. `ref_age` now
        # says whether the corridor is age-independent, banded with the band
        # unrecorded (lent to nobody — the person's own form is the remedy),
        # or a band in years (lent inside it; an unknown age is not lent a
        # band, because a plausible default is the defect, not the fix).
        rule = kb.get("ref_age")
        age_blocked = False
        if rule and rule != "any":
            if rule == "banded":
                age_blocked = age_unbanded = True
            elif isinstance(rule, dict):
                age = core.profile_age()
                if age is None:
                    age_blocked = age_unknown = True
                elif not (float(rule.get("min", 0)) <= age <= float(rule.get("max", 200))):
                    age_blocked = age_other = True
        if sex_blocked or age_blocked:
            # Say WHY the corridor is missing. «No range» and «a range exists
            # but we may not use it for you» look identical on screen and are
            # different facts; the second one has a remedy the person can act
            # on, and printing nothing hides it.
            sex_unknown_no_range = True
        elif kb.get("ref_low") is not None or kb.get("ref_high") is not None:
            m = {**m, "ref_low": kb.get("ref_low"), "ref_high": kb.get("ref_high")}
            borrowed = True
            ref_origin = "reference_base"
    _sx = _sex_adjusted_bounds(k, m)
    if _sx and not _sx.get("ref_sex_unknown"):
        m = {**m, "ref_low": _sx["ref_low"], "ref_high": _sx["ref_high"]}
    return {
        "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high"),
        "ref_reference_base": borrowed,
        # Whose corridor the flag stands on: this draw's own form, the range
        # recorded for the marker, or the reference base — three different
        # strengths of claim, and a verdict is only as strong as its ruler.
        "ref_origin": ref_origin,
        "ref_sex": (_sx or {}).get("ref_sex"),
        "ref_sex_unknown": bool((_sx and _sx.get("ref_sex_unknown")) or sex_unknown_no_range),
        # «No corridor» and «a corridor exists and is not yours» are different
        # facts with different remedies, and the second one is not about a
        # missing profile field.
        "ref_sex_other": bool(sex_other),
        "ref_sex_unreviewed": bool(sex_unreviewed),
        "sex_not_applicable": bool(sex_not_applicable),
        # The age axis, three facts apart: outside the corridor's band, band
        # known and age unrecorded, band never recorded at all.
        "ref_age_other": bool(age_other),
        "ref_age_unknown": bool(age_unknown),
        "ref_age_unbanded": bool(age_unbanded),
    }


def flags_comparable(series: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Whether the flags of one series were all set against one corridor.

    Returns {flags_comparable, corridor_note}; the note is None when they were.
    """
    # When the corridor differs between draws, the values remain one series
    # and the FLAGS do not: a point «low» against 1.16 and a point «ok»
    # against 1.10 did not move — the ruler did. Said, rather than left for
    # the reader to notice from two flags that disagree about one number.
    corridors = sorted({(pt.get("ref_low"), pt.get("ref_high")) for pt in series
                        if pt.get("ref_low") is not None or pt.get("ref_high") is not None},
                       key=lambda c: (c[0] if c[0] is not None else -1e18, c[1] if c[1] is not None else 1e18))
    comparable = len(corridors) <= 1
    return {
        "flags_comparable": comparable,
        "corridor_note": (None if comparable else _t(
            "labs.corridors_differ",
            spans=" · ".join(f"{'' if lo is None else lo}–{'' if hi is None else hi}"
                             for lo, hi in corridors))),
    }
