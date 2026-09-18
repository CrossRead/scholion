"""«If a decision to correct has been made» — what the genotype says about the ROUTE (task 200).

The most dangerous surface in the product, because it stands closest to a
prescription. So the rules here are narrower than anywhere else:

* a deviation is a fact, the decision to correct is not the product's, and this
  module answers a decision somebody else has already made;
* a rule is printed only at evidence level A or B, only with a named source,
  only with a `recheck` — which marker, after how long, and what counts as a
  change rather than the scatter of the method — and only in the conditional;
* rules are GROUPED by what the genotype says (`bypasses`, `against`,
  `favours`, `dose_response_differs`, `route_fact`), never ranked: a ranking
  implies an optimum, and an optimum needs cost, availability, the clinical
  picture and the person's own preference, none of which a genotype knows;
* `adds_nothing` is printed explicitly. Silence on this screen is filled by
  whoever speaks to the reader next, and that sentence does not come from this
  build (the same rule `decision.py` follows).

Nothing here is derived: every rule is curated in `correction_routes.json` and
gated on the way out, the same way the panel positions are.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import core
from ..i18n import t as _t
from . import panel_form

ROUTE_CLASSES = ("bypasses", "against", "favours", "dose_response_differs", "adds_nothing", "route_fact")
#: Grouping order — by what the genotype says, and `adds_nothing` last because
#: it is the most common answer and the least actionable, not because it is the
#: least important.
ROUTE_ORDER = ("against", "favours", "bypasses", "dose_response_differs", "route_fact", "adds_nothing")
ROUTE_LEVELS = ("A", "B")
#: The sentence starts with the decision, not with the product. English and
#: Russian both have one opening, and a rule written any other way is refused
#: rather than quietly reworded.
ROUTE_CONDITIONAL = {"en": ("If ",), "ru": ("Если ",)}


def routes_book() -> Dict[str, Any]:
    return core._read_knowledge("correction_routes.json")


def route_refusal(rule: Dict[str, Any], markers: Dict[str, Any]) -> Optional[str]:
    """Why this rule may not be printed — or None when it may."""
    if not isinstance(rule, dict):
        return "not_a_rule"
    if rule.get("says") not in ROUTE_CLASSES:
        return "unknown_class"
    if rule.get("route") not in (routes_book().get("routes") or {}):
        return "unknown_route"
    ev = rule.get("evidence") or {}
    if not ev.get("source"):
        return "no_source"
    if not rule.get("system"):
        return "no_system"
    rc = rule.get("recheck") or {}
    if not rc.get("marker") or not rc.get("after_weeks") or not rc.get("what_counts_as_change"):
        return "no_recheck"
    if rc["marker"] not in markers:
        return "recheck_marker_not_in_base"
    for key in (rule.get("trigger") or {}).get("markers") or []:
        if key not in markers:
            return "trigger_marker_not_in_base"
    # The catalogue reaches the engine ALREADY in the reader's language, so the
    # sentence here is a string and the bilingual half of this rule is checked
    # against the raw file by a test — the same split the panel gate uses.
    because = rule.get("because")
    if isinstance(because, dict):
        if not all(because.get(l) for l in ("en", "ru")):
            return "text_not_bilingual"
        pairs = [(because[l], ROUTE_CONDITIONAL[l]) for l in ("en", "ru")]
    elif isinstance(because, str) and because:
        pairs = [(because, tuple(o for ops in ROUTE_CONDITIONAL.values() for o in ops))]
    else:
        return "text_not_bilingual"
    for text, openings in pairs:
        if not str(text).startswith(openings):
            return "phrasing_not_conditional"
    rev = rule.get("review")
    if not isinstance(rev, dict) or rev.get("by_role") not in ("panel_author", "clinician"):
        return "no_review"
    # Last on purpose: a rule below B still prints — as «adds nothing», with its
    # own sentence as the reason — so everything above must hold for it too.
    if ev.get("level") not in ROUTE_LEVELS:
        return "level_below_b"
    return None


def _deviating(trigger: Dict[str, Any], by_key: Dict[str, Any]) -> List[str]:
    """The markers of the trigger that are actually off, in this person's file."""
    want = str(trigger.get("direction") or "")
    out = []
    for key in trigger.get("markers") or []:
        row = by_key.get(key) or {}
        flag = str(row.get("flag") or "")
        if want == "low" and flag in ("low", "critical_low"):
            out.append(key)
        elif want == "high" and flag in ("high", "critical_high"):
            out.append(key)
    return out


def _genotype_holds(dep: Optional[Dict[str, Any]], rows: List[Dict[str, Any]]) -> List[str]:
    """The genes or positions the rule stands on, when the person has them —
    read, never assumed. Empty for a `route_fact`, which depends on nothing."""
    if not dep:
        return []
    state = dep.get("state") or "carrier"
    held = []
    for r in rows:
        if r.get("read") is not True or r.get("presumed"):
            # A value the reference implies, or a gene nobody read, is not a
            # genotype a route may stand on (review, 18.09.2026).
            continue
        if r.get("gene") in (dep.get("genes") or []) and r.get("unit") != "position":
            if state == "carrier" and r.get("carrier"):
                held.append(r["gene"])
            elif state in ("het", "hom") and r.get("state") == state:
                held.append(r["gene"])
        if r.get("rsid") and r.get("rsid") in (dep.get("positions") or []):
            want = "het" if state == "carrier" else state
            if r.get("state") == want:
                held.append(r["rsid"])
    return held


def _row(rule: Dict[str, Any], routes: Dict[str, Any], classes: Dict[str, Any],
         markers: List[str], held: List[str]) -> Dict[str, Any]:
    rc = rule["recheck"]
    return {
        "key": rule["key"],
        "route": rule["route"],
        "route_text": panel_form.one_language(routes.get(rule["route"]) or {}),
        "says": rule["says"],
        "says_text": panel_form.one_language(classes.get(rule["says"]) or {}),
        "because": panel_form.one_language(rule["because"]),
        "on": markers,
        "positions": held,
        "evidence": rule["evidence"],
        "recheck": {"marker": rc["marker"],
                    "marker_name": _marker_name(rc["marker"]),
                    "after_weeks": rc["after_weeks"],
                    "what_counts_as_change": panel_form.one_language(rc["what_counts_as_change"])},
    }


def _marker_name(key: str) -> str:
    from .system_panels import _marker_name as name
    return name(key)


def correction_routes_for(key: str, by_key: Dict[str, Any],
                          rows: List[Dict[str, Any]], deviating: bool) -> Optional[Dict[str, Any]]:
    """The block «if a decision to correct has been made», or None for a system with no rules.

    `deviating` says whether this system has anything off at all: with nothing
    off there is no decision to answer, and the block does not appear. With
    something off and no rule matching it, the block appears and says that the
    genotype adds nothing — with the reason.
    """
    data = routes_book()
    rules = [r for r in (data.get("rules") or []) if r.get("system") == key]
    if not rules:
        return None
    known = core.lab_markers().get("markers") or {}
    routes, classes = data.get("routes") or {}, data.get("route_classes") or {}
    meds = [m.lower() for m in core.medication_names()]
    printed: List[Dict[str, Any]] = []
    refused: Dict[str, int] = {}
    quiet: List[Dict[str, Any]] = []
    for rule in rules:
        why = route_refusal(rule, known)
        if why and why != "level_below_b":
            refused[why] = refused.get(why, 0) + 1
            continue
        trigger = rule.get("trigger") or {}
        on = _deviating(trigger, by_key)
        if trigger.get("medications"):
            if not any(q in m for q in trigger["medications"] for m in meds):
                continue
        elif not on:
            continue
        held = _genotype_holds(rule.get("depends_on"), rows)
        if rule.get("depends_on") and not held:
            continue
        row = _row(rule, routes, classes, on, held)
        if why == "level_below_b":
            # The statement's rule: at C, D and E the route is not printed —
            # what is printed is «adds nothing», with the reason. The rule's own
            # sentence is that reason, so the reader learns WHY the genotype is
            # silent here instead of meeting a generic line.
            row["says"] = "adds_nothing"
            row["says_text"] = panel_form.one_language(classes.get("adds_nothing") or {})
            row["because"] = _t("system.routes.below_b", level=str((rule.get("evidence") or {}).get("level") or "—"),
                                because=row["because"])
            row["route"], row["route_text"] = None, None
            quiet.append(row)
            continue
        (quiet if rule["says"] == "adds_nothing" else printed).append(row)
    groups = [{"says": c, "says_text": panel_form.one_language(classes.get(c) or {}),
               "rows": [r for r in printed if r["says"] == c]}
              for c in ROUTE_ORDER if any(r["says"] == c for r in printed)]
    if not groups and not quiet and deviating:
        quiet.append({"key": "no_rule", "says": "adds_nothing",
                      "says_text": panel_form.one_language(classes.get("adds_nothing") or {}),
                      "because": _t("system.routes.no_rule"), "on": [], "positions": [],
                      "route": None, "route_text": None, "evidence": None, "recheck": None})
    if not groups and not quiet:
        return {"status": "nothing_deviates", "groups": [], "adds_nothing": [],
                "refused": {"total": sum(refused.values()), "by_reason": refused},
                "head": _t("system.routes.head"), "caveat": _t("system.routes.caveat")}
    return {"status": "ok", "groups": groups, "adds_nothing": quiet,
            "refused": {"total": sum(refused.values()), "by_reason": refused},
            "head": _t("system.routes.head"), "caveat": _t("system.routes.caveat")}
