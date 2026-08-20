"""On what fraction of objects did each flag fire — the project's own rule, run.

README, ASSISTANT-RULES and the model instruction all carry the same sentence:

    «A threshold that fires on almost everything gets fixed, not explained. A
     cheap check before any interpretation: what fraction of objects did the
     flag hit? A flag that marks nearly every object carries no information,
     however plausible its formula.»

The colleagues' audit found that sentence in four markdown files and no function
anywhere. The rule was applied by hand, comments record that it was, and the
README promises enforcement in the word «gets fixed» — a promise nothing kept.
A rule stated four times and checked zero times is worse than an unstated one:
it reads as a property of the build.

WHAT THIS DOES NOT DO. It does not decide that a flag is wrong. A high hit rate
is a question, not a verdict — a person whose thyroid panel is genuinely all
abnormal should see every marker flagged, and a rule that suppressed those flags
because there were many of them would be worse than the defect it fixed. So the
number is COMPUTED and SHOWN, and the one thing it asserts is arithmetic: this
flag fired on this share of the objects it looked at.

The reference points below are not clinical thresholds and no source is claimed
for them. They are the shape of the sentence in the README — «almost
everything» — turned into two words a reader can act on.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .i18n import t as _t

#: Above this share, a flag is describing the ruler rather than the person often
#: enough to be worth asking about. Not a clinical threshold: an arithmetic
#: reading of «marks nearly every object».
NOTABLE_SHARE = 0.60


def _rate(hit: int, total: int) -> float:
    return round(hit / total, 3) if total else 0.0


def lab_flags() -> Dict[str, Any]:
    """Hit rate of every laboratory flag, over the markers it actually looked at.

    The denominator is deliberately per-flag. «Out of range» looked at every
    marker with a corridor; «at the edge» looked only at the ones inside theirs.
    Dividing both by the same total would understate the second and make the
    check useless where it matters most.
    """
    from .engine import labs
    r = labs.analyze_labs()
    markers = r.get("markers") or []
    if not markers:
        return {"available": False}
    with_range = [m for m in markers if m.get("ref_low") is not None
                  or m.get("ref_high") is not None]
    inside = [m for m in with_range if not m.get("abnormal")]
    rows = [
        {"flag": "abnormal", "hit": sum(1 for m in with_range if m.get("abnormal")),
         "looked_at": len(with_range), "what": _t("prevalence.flag.abnormal")},
        {"flag": "near_limit", "hit": sum(1 for m in inside if m.get("near_limit")),
         "looked_at": len(inside), "what": _t("prevalence.flag.near_limit")},
        {"flag": "norange", "hit": sum(1 for m in markers if m.get("flag") == "norange"),
         "looked_at": len(markers), "what": _t("prevalence.flag.norange")},
        {"flag": "threshold_crossed",
         "hit": sum(1 for m in markers if m.get("decisions")
                    and any(d.get("crossed") for d in m["decisions"])),
         "looked_at": len(markers), "what": _t("prevalence.flag.threshold")},
    ]
    for row in rows:
        row["rate"] = _rate(row["hit"], row["looked_at"])
        row["notable"] = bool(row["looked_at"] and row["rate"] >= NOTABLE_SHARE)
    return {"available": True, "rows": rows, "markers": len(markers)}


def report() -> Dict[str, Any]:
    """Every flag the build can raise, with the share of objects it fired on."""
    out: List[Dict[str, Any]] = []
    labs_part = lab_flags()
    if labs_part.get("available"):
        for row in labs_part["rows"]:
            out.append(dict(row, layer="labs"))
    return {"ok": True, "rows": out,
            "notable": [r for r in out if r.get("notable")],
            "threshold": NOTABLE_SHARE}
