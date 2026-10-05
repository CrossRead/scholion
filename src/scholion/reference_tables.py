"""Keep a form's grading scale separate from a normal reference interval.

These are input labels, not medical claims authored by Scholion. Unknown
conditions do not license borrowing a different interval from the dictionary.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

_GRADE = re.compile(r"риск|дефицит|недостаточн|адекватн|избыток|благоприят|отрицательн|"
                    r"положительн|сомнительн|оптимальн", re.I)
_CONDITION = re.compile(r"^(?:до\s+полудня|после\s+полудня|л[её]жа|стоя)", re.I)
_NUMBER = r"\d+(?:[.,]\d+)?"
_BOUND = re.compile(r"([<>≤≥])\s*(" + _NUMBER + r")|(" + _NUMBER + r")\s*[-–—]\s*(" + _NUMBER + r")")


def printed_context(rest: str, following: List[str], date: str, value: float, *, censored: Any = None) -> Dict[str, Any]:
    """Recognised scale/condition rows, with a unique printed grade when known."""
    rows = [s.strip() for s in rest.split(";") if _GRADE.search(s) and _BOUND.search(s)]
    conditions = []
    for line in following:
        raw = line.strip()
        if not raw:
            continue
        if _GRADE.search(raw) and _BOUND.search(raw):
            rows.extend(s.strip() for s in raw.split(";") if _BOUND.search(s))
        elif _CONDITION.match(raw) and _BOUND.search(raw):
            conditions.append(raw)
        else:
            break
    if not rows and not conditions:
        return {}
    table: List[Dict[str, Any]] = []
    for raw in rows or conditions:
        match = _BOUND.search(raw)
        assert match is not None  # rows were selected by this same immutable regex
        sign, bound, low, high = match.groups()
        lo = float(low.replace(",", ".")) if low else None
        hi = float(high.replace(",", ".")) if high else None
        if bound:
            number = float(bound.replace(",", "."))
            if sign in (">", "≥"):
                lo = number
                fits = value > lo if sign == ">" else value >= lo
            else:
                hi = number
                fits = value < hi if sign == "<" else value <= hi
        else:
            fits = lo is not None and hi is not None and lo <= value <= hi
        label = (raw[:match.start()] + " " + raw[match.end():]).strip(" :-–—%;")
        table.append({"raw": raw, "label": label, "ref_low": lo, "ref_high": hi,
                      "relation": sign or "range", "matches": None if censored else fits})
    out: Dict[str, Any] = {"reference_table": table, "reference_kind": "scale" if rows else "conditional"}
    if rows:
        matched = [r for r in table if r["matches"]]
        out["reference_grade"] = matched[0]["label"] if len(matched) == 1 else None
    elif len(date) >= 16:
        hour = int(date[11:13])
        fitting = [r for r in table if r["raw"].lower().startswith("до полудня" if hour < 12 else "после полудня")]
        if len(fitting) == 1:
            out["selected_range"] = (fitting[0]["ref_low"], fitting[0]["ref_high"])
    return out
