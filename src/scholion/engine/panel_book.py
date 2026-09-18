"""What the panel book holds beyond its rows (task 199): groups, panels on demand, the local note, the marker index.

Split out of `system_panels.py` on 18.09.2026, when that module passed its
budget for the second time in a day. Everything here reads the curated book or
the profile and returns structure; the card assembles it, the faces print it.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .. import core
from ..i18n import t as _t
from . import panel_form, panel_gate


def _curated() -> Dict[str, Any]:
    from .system_panels import _curated as book
    return book()


def _levels():
    from .system_panels import _levels as levels
    return levels()


def _position_state(r: Dict[str, Any]) -> Dict[str, Any]:
    from .system_panels import _position_state as state
    return state(r)


def _curated_rows(*a, **k):
    from .system_panels import _curated_rows as rows
    return rows(*a, **k)


def _level_counts(rows):
    from .system_panels import _level_counts as counts
    return counts(rows)


def _project(gen, register):
    from .system_panels import _project as project
    return project(gen, register)


def DISCLAIMER():
    from .system_panels import DISCLAIMER as d
    return d()


def _on_demand() -> Dict[str, Any]:
    """The panels WITHOUT a radar domain (task 199 F): dental, behaviour."""
    return core._read_knowledge("on_demand_panels.json") or {}


def on_demand_panels() -> List[Dict[str, Any]]:
    """The panels on demand, as an index: key, label, why they are not on the radar."""
    out = []
    for key, spec in (_on_demand().get("panels") or {}).items():
        if isinstance(spec, dict):
            out.append({"key": key, "label": panel_form.one_language(spec.get("label")) or key,
                        "why_no_domain": panel_form.one_language(spec.get("why_no_domain")),
                        "positions": len(spec.get("positions") or []), "on_demand": True})
    return out


def positions_by_marker() -> Dict[str, List[Dict[str, Any]]]:
    """marker key → the curated positions whose expectation names it (task 199 G).

    The third entry: a laboratory marker with positions behind it shows «the
    genetics of this marker». Static — what the book says, no genotype — so the
    labs analysis can carry it without reading the genome fifteen times; the
    page joins the person's state from the system card it already holds.
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    levels = _levels()
    for key, spec in (_curated().get("systems") or {}).items():
        for p in spec.get("positions") or []:
            exp = p.get("expect") if isinstance(p.get("expect"), dict) else None
            if not exp or not exp.get("marker"):
                continue
            lv = panel_gate.level_of(p, levels)
            out.setdefault(str(exp["marker"]), []).append({
                "gene": p.get("gene"), "rsid": p.get("rsid"), "kind": p.get("kind"),
                "level": lv.get("level"), "level_short": lv.get("level_short"),
                "direction": exp.get("direction"), "system": key,
                "system_label": _t("radar.domain." + key)})
    return out


def _local_notes() -> Dict[str, Dict[str, Any]]:
    """The clinician's own notes on positions, from the PROFILE (task 199 H).

    `profile/local_notes.json` is the person's, never the package's: a note here
    may name whoever wrote it, and it prints in its own voice on the row it is
    about. It is keyed by rsID, or by gene for a note about a whole gene. A
    missing or broken file is no note at all — never an error on the card.
    """
    try:
        path = core.profile_dir() / "local_notes.json"
        data = core.read_profile_json(path) if path.exists() else {}
    except Exception:                                                # noqa: BLE001
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for n in (data.get("notes") or []) if isinstance(data, dict) else []:
        if not isinstance(n, dict) or not n.get("text"):
            continue
        key = str(n.get("rsid") or n.get("gene") or "").strip()
        if key:
            is_rs = bool(re.fullmatch(r"rs\d+", key, re.I))
            out[key.lower() if is_rs else key.upper()] = {
                "text": str(n["text"]), "by_role": n.get("by_role") or "clinician", "on": n.get("on")}
    return out


def _attach_local_notes(rows: List[Dict[str, Any]]) -> None:
    notes = _local_notes()
    # The field is always there, so the shape of a row does not depend on
    # whether a notes file exists beside this profile (review, 18.09.2026).
    for r in rows:
        r["local_note"] = (notes.get(str(r.get("rsid") or "").lower()) or notes.get(str(r.get("gene") or "").upper())) if notes else None


def _groups(key: str, spec: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """A system's groups: one row for N positions (task 199, decision 3).

    A group prints its name, its count, one sentence, one level and one source,
    and opens into the ladders of its positions. A group that names a position
    the system does not hold, or lacks a sentence in either language, is
    refused whole and counted — never shown half-empty.
    """
    by_rs = {r.get("rsid"): r for r in rows if r.get("unit") == "position"}
    levels = _levels()
    out = []
    for g in spec.get("groups") or []:
        if not isinstance(g, dict) or not g.get("key"):
            continue
        members = [rs for rs in (g.get("positions") or []) if rs in by_rs]
        why = None
        if len(members) != len(g.get("positions") or []) or not members:
            why = "group_position_not_in_system"
        elif not panel_gate._texts_bilingual({"het": g.get("text")}) and not isinstance(g.get("text"), str):
            why = "group_text_not_bilingual"
        elif not g.get("source"):
            why = "group_without_source"
        lv = panel_gate.level_of(g, levels)
        if not lv.get("level"):
            why = why or "group_level_missing"
        if why:
            out.append({"key": g["key"], "refused": why})
            continue
        states: Dict[str, int] = {}
        for rs in members:
            by_rs[rs]["group"] = g["key"]
            st = by_rs[rs].get("state") or "unread"
            states[st] = states.get(st, 0) + 1
        out.append({"key": g["key"], "label": panel_form.one_language(g.get("label")) or g["key"],
                    "text": panel_form.one_language(g.get("text")), "source": g.get("source"),
                    "level": lv.get("level"), "level_short": lv.get("level_short"),
                    "positions": members, "count": len(members), "states": states,
                    "members": [_position_state(by_rs[rs]) for rs in members]})
    return out


def _on_demand_card(key: str, spec: Dict[str, Any], register: str) -> Dict[str, Any]:
    """A panel without a radar domain, as a card: the same rows through the
    same gate, no score, no figure, and the sentence that says why (task 199 F).

    The radar has two halves; a panel with no laboratory half shown there
    would teach a reader that an empty half means a clean one. So the card
    says at the top that it is not on the radar and why, and prints its
    positions the way a system's genetic half is printed.
    """
    scan = panel_form.scan_for(sorted({str(p.get("gene") or "").upper()
                                       for p in spec.get("positions") or [] if isinstance(p, dict)}))
    cur = _curated_rows(key, spec, [], scan, {})
    rows = cur["rows"]
    _attach_local_notes(rows)
    groups = _groups(key, spec, rows)
    v = panel_form.verdict(rows, scan)
    gen = {"status": "composed", "rows": rows, "scan": scan,
           "groups": [g for g in groups if not g.get("refused")],
           "groups_refused": {g["key"]: g["refused"] for g in groups if g.get("refused")},
           "positions": [_position_state(r) for r in rows],
           "base": {"status": "none", "source": None, "version": None, "downloaded": None,
                    "filter_version": None, "genes": 0, "source_text": None},
           "curated": {"status": "ok" if rows else "empty", "source": panel_form.one_language(spec.get("source")),
                       "positions": len(rows),
                       "why_empty": None if rows else panel_form.one_language((_on_demand().get("_meta") or {}).get("why_empty"))},
           "excluded": [], "unreadable": cur["unreadable"],
           "refused": {"total": sum(cur["refused"].values()), "by_reason": cur["refused"]},
           "read_count": sum(1 for r in rows if r.get("read") is True),
           "unread_count": sum(1 for r in rows if r.get("read") is False),
           "read_positions": sum(1 for r in rows if r.get("read") is True),
           "finding_count": sum(int(r.get("findings") or 0) for r in rows),
           "carrier_count": sum(1 for r in rows if r.get("carrier")),
           "pending_count": sum(1 for r in rows if r.get("pending")),
           "level_counts": _level_counts(rows), "verdict": v, "verdict_line": panel_form.verdict_line(v)}
    label = panel_form.one_language(spec.get("label")) or key
    raw = spec.get("label")
    labels = {c: raw.get(c, key) for c in ("en", "ru")} if isinstance(raw, dict) else {c: label for c in ("en", "ru")}
    return {"status": "ok", "key": key, "label": label, "labels": labels,
            "register": register, "on_demand": True,
            "why_no_domain": panel_form.one_language(spec.get("why_no_domain")),
            "source": panel_form.one_language(spec.get("source")), "genetic_half": True, "markers": [],
            "labs": {"status": "no_laboratory_half", "markers": [], "measured": 0, "total": 0},
            "dynamics": {"status": "no_laboratory_half"},
            "genetics": _project(gen, register), "medications": {"rows": [], "unmapped": [], "unclassified": []},
            "target": {"rows": []}, "tests": {"rows": []}, "questions": {"rows": [], "empty_why": "no_laboratory_half"},
            "correction_routes": None,
            "verdict": v, "verdict_line": gen["verdict_line"], "unread_line": panel_form.unread_line(v),
            "unread": panel_form.unread_block(v),
            "next": {"lab": {"rows": [], "empty_why": "no_laboratory_half"},
                     "genome": {"rows": [], "empty_why": None if rows else "no_rows"},
                     "ask": {"rows": [], "empty_why": "no_laboratory_half"}},
            "disclaimer": DISCLAIMER()}
