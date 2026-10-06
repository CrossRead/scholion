"""A position below B is a hypothesis, and it travels with its passport (0.6.0, U2).

The rule since task 199: a conclusion is printed at A and B only. Until 0.6.0
the sentence the panel author wrote for a C or D position still rode in the
row's `text`, and every face printed it the way it printed a conclusion — the
level beside it was the only difference, and a level is the first thing a
retelling drops.

From 0.6.0 (owner, 27.09.2026) the data layer is one for every face and the
personalised hypotheses remain separate from reference context; every screen
may show reference biology at any level, and an assistant
receives the passport with the rule for retelling it. So the sentence leaves
`text` and moves here, beside what the hypothesis rests on and — named, not
silently absent — what it still lacks.

E is not a variant-effect hypothesis. `value_only` excludes a personalised
sentence, while the independent reference card can still describe gene biology.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

_LOWER = ("C", "D")

#: What a passport can hold beyond the level and the source. The texts are ours,
#: written against a source (U1); until one is written it is listed as missing.
_PARTS = ("reported", "mechanism", "effect", "population", "replication",
          "would_confirm", "would_refute")


def _one(raw: Any) -> Optional[str]:
    from .panel_form import one_language
    return one_language(raw) or None if raw else None


def hypothesis_passport(spec: Dict[str, Any], lv: Dict[str, Any],
                        reported: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The passport of a C or D position or group; None at any other level.

    `reported` is the author's sentence for this person's genotype — what the
    literature reports, retold as a hypothesis — or None when the position was
    not read or has no sentence for the state."""
    level = lv.get("level")
    if level not in _LOWER:
        return None
    raw = spec.get("evidence")
    ev: Dict[str, Any] = raw if isinstance(raw, dict) else {}
    out: Dict[str, Any] = {
        "level": level, "level_short": lv.get("level_short"),
        "why_this_level": ev.get("judged") or ev.get("by_rule"), "basis": ev.get("basis"),
        "reported": reported,
        "mechanism": _one(spec.get("mechanism")),
        "effect": _one(spec.get("effect_size")),
        "population": _one(spec.get("population")),
        "study": spec.get("study"),
        "replication": _one(spec.get("replication")),
        "would_confirm": _one(spec.get("would_confirm")),
        "would_refute": _one(spec.get("would_refute")),
        "source": spec.get("source") or ev.get("source"),
    }
    out["missing"] = [k for k in _PARTS if not out.get(k)]
    return out


def is_value_only(level: Optional[str]) -> bool:
    """E: a value without a personalised variant-effect statement."""
    return level == "E"
