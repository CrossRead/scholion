"""A CPIC phenotype phrase in the reader's language.

A star-allele call carried by the profile — from PyPGx, PharmCAT or a laboratory
report — states its phenotype as CPIC prints it: «Intermediate Metabolizer»,
«Normal Function». That phrase was shown as the label, so a Russian page printed
English at exactly the line a person reads about a drug. The phrase is worded
from what it names instead; a «likely» or «possible» qualifier is kept, because
dropping it would turn a hedged call into a firm one; a phrase this table does
not know is shown as it came rather than guessed at.
"""
from __future__ import annotations

from ..i18n import t as _t

#: The metaboliser phenotypes, by the word CPIC uses (either spelling).
_METABOLISER = {"normal": "NM", "intermediate": "IM", "poor": "PM", "rapid": "RM", "ultrarapid": "UM"}

#: The transporter and enzyme function phenotypes (SLCO1B1, ABCG2, DPYD and the like).
_FUNCTION = {"normal": "normal", "decreased": "decreased", "poor": "poor", "increased": "increased"}

_QUALIFIERS = ("likely", "possible")


def phenotype_words(text: str) -> str:
    """The phrase for a CPIC phenotype string, qualifier kept; the string itself if unknown."""
    raw = str(text or "").strip()
    words = raw.lower().split()
    qualifier = words[0] if words and words[0] in _QUALIFIERS else None
    core_words = words[1:] if qualifier else words
    label = None
    if len(core_words) == 2 and core_words[1] in ("metabolizer", "metaboliser") and core_words[0] in _METABOLISER:
        label = _t("phenotype.label." + _METABOLISER[core_words[0]])
    elif len(core_words) == 2 and core_words[1] == "function" and core_words[0] in _FUNCTION:
        label = _t("phenotype.function." + _FUNCTION[core_words[0]])
    if label is None:
        return raw
    return _t("phenotype.qualifier." + qualifier, label=label) if qualifier else label
