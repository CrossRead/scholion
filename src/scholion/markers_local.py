"""Growing the marker dictionary without letting a model near a number.

When a row on a lab form matches no marker, there are three things the tool can
do and only one of them is acceptable.

It can DROP the row. That is what it used to do, silently, for nineteen files out
of forty-seven — and a row dropped without a word is indistinguishable from a row
that was never printed.

It can ASK A MODEL TO READ THE VALUE. That breaks the one property the product is
built on: the number in the profile comes from deterministic code. A value
extracted by a model is a probabilistic number in a place where everything else
is reproducible, and no amount of confidence scoring makes it checkable a year
later.

Or it can ASK A MODEL TO PROPOSE A RULE. The model sees the printed LABEL and the
UNIT — never the patient's value, never the whole form — and proposes a
dictionary entry: a canonical key, the synonyms that recognise it, the unit, the
direction. The entry lands here as `proposed`. The next parse then reads the row
with ordinary deterministic code that simply knows one rule more, and the number
is as reproducible as every other number in the file.

What that buys, beyond the row:

  · the rule is a FILE — one line of JSON a person can check, not a value that
    would have to be re-read from the form to be verified;
  · it works for everyone, forever, and a good entry travels upstream;
  · the confidence attaches to the RULE, not to the number: «this row was read by
    a rule a model proposed and nobody has confirmed» is a statement that can be
    acted on, unlike «the model was 0.8 sure».

While an entry is `proposed` the marker is read, stored, charted — and carries no
flag. Withholding the claim while keeping the data is the same choice the project
made for an unknown sex, and for the same reason: the value is real, the corridor
is a guess.
"""
from __future__ import annotations

import datetime
import json
from typing import Any, Dict, List, Optional

from . import core
from .i18n import t as _t

_ALLOWED = ("key", "unit", "direction", "loinc", "labels", "specimen", "note")


def _load() -> Dict[str, Any]:
    p = core.markers_overlay_path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"_meta": {"purpose": "locally added marker entries; see markers_local.py",
                          "source_tier": "user_contributed"},
                "markers": {}}


def _save(data: Dict[str, Any]) -> None:
    core.write_json(core.markers_overlay_path(), data)
    core.reset_cache()


def propose(key: str, *, unit: str = "", names_ru: Optional[List[str]] = None,
            names_en: Optional[List[str]] = None, direction: str = "",
            loinc: str = "", note: str = "", by: str = "model") -> Dict[str, Any]:
    """Add a PROPOSED dictionary entry. No values, no reference range.

    Deliberately unable to carry a corridor. A reference interval is a clinical
    claim, and `CONTRIBUTING.md` is explicit that a language model is not a source
    for one; a range read off a single form is that form's, not the marker's. So a
    proposal describes what the row IS CALLED and in what unit it is printed —
    facts visible on the paper — and the corridor comes later from the form itself
    or from a reviewed source.
    """
    key = (key or "").strip().lower().replace(" ", "_")
    if not key:
        return {"ok": False, "error": _t("markers.need_key")}
    if key in (core.lab_markers().get("markers") or {}) and key not in (_load().get("markers") or {}):
        return {"ok": False, "error": _t("markers.already_shipped", key=key)}
    if not (names_ru or names_en):
        return {"ok": False, "error": _t("markers.need_names")}
    data = _load()
    spec: Dict[str, Any] = {"status": "proposed", "proposed_by": by,
                            "proposed_on": datetime.date.today().isoformat()}
    if unit:
        spec["unit"] = unit
    if direction:
        spec["direction"] = direction
    if loinc:
        spec["loinc"] = loinc
    if note:
        spec["note"] = note
    labels: Dict[str, Any] = {}
    if names_ru:
        labels["ru"] = {"names": [x.strip().lower() for x in names_ru if x.strip()]}
    if names_en:
        labels["en"] = {"names": [x.strip().lower() for x in names_en if x.strip()]}
    spec["labels"] = labels
    data.setdefault("markers", {})[key] = spec
    _save(data)
    return {"ok": True, "key": key, "status": "proposed", "spec": spec}


def confirm(key: str) -> Dict[str, Any]:
    """A person vouches for an entry. From here it takes effect.

    What «takes effect» means differs by kind, and that is the point: a marker
    starts flagging, a unit starts converting, a row rule starts choosing a
    corridor. Until this call none of the three touches a number or makes a
    claim.
    """
    data = _load()
    bucket = _bucket_of(key) or "markers"
    spec = (data.get(bucket) or {}).get(key)
    if not spec:
        return {"ok": False, "error": _t("markers.no_such_proposal", key=key)}
    spec["status"] = "confirmed"
    spec["confirmed_on"] = datetime.date.today().isoformat()
    _save(data)
    return {"ok": True, "key": key, "kind": bucket, "status": "confirmed"}


def drop(key: str) -> Dict[str, Any]:
    data = _load()
    bucket = _bucket_of(key)
    if not bucket:
        return {"ok": False, "error": _t("markers.no_such_proposal", key=key)}
    del data[bucket][key]
    _save(data)
    return {"ok": True, "key": key, "status": "dropped"}


def listing() -> Dict[str, Any]:
    data = _load()
    out = []
    for key, spec in sorted((data.get("markers") or {}).items()):
        out.append({"kind": "marker", "key": key, "status": spec.get("status", "proposed"),
                    "unit": spec.get("unit", ""), "by": spec.get("proposed_by", ""),
                    "on": spec.get("proposed_on", ""),
                    "names": core.marker_rules(spec, "names")})
    for key, spec in sorted((data.get("units") or {}).items()):
        what = (f"× {spec['factor']}" if spec.get("factor") is not None
                else "refuse: " + str(spec.get("refuse_reason", ""))[:40])
        out.append({"kind": "unit", "key": key, "status": spec.get("status", "proposed"),
                    "unit": spec.get("surface", ""), "by": spec.get("proposed_by", ""),
                    "on": spec.get("proposed_on", ""), "names": [what]})
    for key, spec in sorted((data.get("row_rules") or {}).items()):
        out.append({"kind": f"row/{spec.get('kind')}", "key": key,
                    "status": spec.get("status", "proposed"), "unit": "",
                    "by": spec.get("proposed_by", ""), "on": spec.get("proposed_on", ""),
                    "names": [spec.get("example", "")[:50]]})
    return {"ok": True, "entries": out, "path": str(core.markers_overlay_path())}


# ═══════════════════════════════════════════════════════════════════════════
# The same mechanism, for the two other kinds of entry the task names.
#
# One rule governs all three, and its consequence differs because what the
# entries CONTROL differs:
#
#   a MARKER entry decides what a row is called. An unconfirmed one does not
#   change the number, so the value is read and shown — and no claim about the
#   norm is made until a person vouches for it.
#
#   a UNIT entry decides what the number IS. An unconfirmed factor would rewrite
#   the value itself, so it is NOT applied: the point stays refused exactly as it
#   is today, and the refusal now carries a concrete proposal the person can
#   confirm in one command instead of a dead end.
#
#   a ROW RULE decides which corridor is chosen from a multi-line reference
#   block. An unconfirmed one would pick a corridor, so it does not run: no
#   corridor, as when the form is ambiguous.
#
# The rule underneath is one sentence — a proposal never changes a number and
# never produces a claim — and it is the same sentence as «the model proposes a
# rule, never a value», applied one layer down.
# ═══════════════════════════════════════════════════════════════════════════

def propose_unit(marker: str, surface: str, *, factor: Optional[float] = None,
                 refuse_reason: str = "", note: str = "", by: str = "model") -> Dict[str, Any]:
    """Propose that a printed unit form belongs to a marker.

    A factor is accepted but NOT applied while the entry is `proposed`: a wrong
    multiplier does not produce a wrong corridor, it produces a wrong NUMBER, and
    a number nobody vouched for must not enter the profile. `refuse_reason`
    proposes the opposite — that this form cannot be converted at all, the way
    Lp(a) in mg/dL cannot — which is a proposal too, and often the right one.
    """
    marker = (marker or "").strip().lower()
    surface = (surface or "").strip()
    if not marker or not surface:
        return {"ok": False, "error": _t("markers.need_marker_and_unit")}
    if factor is None and not refuse_reason:
        return {"ok": False, "error": _t("markers.need_factor_or_reason")}
    data = _load()
    entry = {"status": "proposed", "proposed_by": by,
             "proposed_on": datetime.date.today().isoformat(), "marker": marker,
             "surface": surface}
    if factor is not None:
        entry["factor"] = float(factor)
    if refuse_reason:
        entry["refuse_reason"] = refuse_reason
    if note:
        entry["note"] = note
    data.setdefault("units", {})[f"{marker}|{surface}"] = entry
    _save(data)
    return {"ok": True, "key": f"{marker}|{surface}", "status": "proposed", "spec": entry}


def propose_row_rule(pattern: str, *, kind: str = "alien", note: str = "",
                     example: str = "", by: str = "model") -> Dict[str, Any]:
    """Propose a rule for reading a multi-line reference block.

    `kind` is `alien` (this row belongs to somebody else — a pubertal stage, a
    trimester, a paediatric band) or `label` (this row IS a labelled row, so the
    descent should not stop at it). Those two were the whole of defects 65 and
    66, and they are the third thing a person meeting an unreadable form has to
    be able to contribute.

    `example` is required and is the point: a pattern without the line that
    produced it cannot be reviewed, and cannot become a regression fixture. It
    is stored redacted — the caller passes the SHAPE of the row, not a patient's.
    """
    pattern = (pattern or "").strip()
    if not pattern:
        return {"ok": False, "error": _t("markers.need_pattern")}
    if kind not in ("alien", "label"):
        return {"ok": False, "error": _t("markers.bad_rule_kind", kind=kind)}
    if not example.strip():
        return {"ok": False, "error": _t("markers.need_example")}
    try:
        import re as _re
        _re.compile(pattern)
    except _re.error as e:
        return {"ok": False, "error": _t("markers.bad_pattern", why=str(e))}
    data = _load()
    data.setdefault("row_rules", {})[pattern] = {
        "status": "proposed", "kind": kind, "note": note, "example": example.strip(),
        "proposed_by": by, "proposed_on": datetime.date.today().isoformat()}
    _save(data)
    return {"ok": True, "key": pattern, "status": "proposed", "kind": kind}


def _bucket_of(key: str) -> Optional[str]:
    data = _load()
    for bucket in ("markers", "units", "row_rules"):
        if key in (data.get(bucket) or {}):
            return bucket
    return None


def confirmed_units(marker: str) -> Dict[str, float]:
    """CONFIRMED unit forms for a marker. Proposed ones deliberately absent."""
    out = {}
    for key, e in (_load().get("units") or {}).items():
        if e.get("status") == "confirmed" and e.get("marker") == (marker or "").lower():
            if e.get("factor") is not None:
                out[e["surface"]] = float(e["factor"])
    return out


def proposed_units(marker: str) -> List[Dict[str, Any]]:
    """Proposals for a marker's units — shown in the refusal, never applied."""
    return [e for e in (_load().get("units") or {}).values()
            if e.get("status") == "proposed" and e.get("marker") == (marker or "").lower()]


def confirmed_row_rules(kind: str) -> List[str]:
    """CONFIRMED row patterns of one kind, ready to extend the parser's own."""
    return [p for p, e in (_load().get("row_rules") or {}).items()
            if e.get("status") == "confirmed" and e.get("kind") == kind]


def confirmed_markers() -> Dict[str, Any]:
    """Locally added marker entries a person has vouched for."""
    return {k: v for k, v in (_load().get("markers") or {}).items()
            if v.get("status") == "confirmed"}
