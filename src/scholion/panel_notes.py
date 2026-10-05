"""Shared author wording, separate from evidence and from a person's local notes.

The bilingual source registry is keyed by an intake rsID, not by a patient's
genotype. Its wording never grants a finding or a higher evidence level.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any, Dict, Optional

from . import core
from .i18n import lang, t


def validate(notes: Any, intake: Dict[str, Any]) -> None:
    """Refuse the entire import on an unknown position or incomplete provenance."""
    known = {p["rsid"] for spec in intake.get("lists", {}).values()
             for p in spec.get("positions", [])}
    if not isinstance(notes, dict) or not notes:
        raise ValueError("notes must be a nonempty rsID mapping")
    for rsid, note in notes.items():
        if rsid not in known:
            raise ValueError("author note is not in the intake ledger: " + str(rsid))
        if not isinstance(note, dict) or set(note) != {"ru", "en", "review", "provenance"}:
            raise ValueError("invalid author note fields: " + rsid)
        if any(not isinstance(note[k], str) or not note[k].strip() for k in ("ru", "en")):
            raise ValueError("both original and translation are required: " + rsid)
        review = note["review"]
        if (not isinstance(review, dict) or set(review) != {"by_role", "on", "scope"}
                or review["by_role"] != "panel_author" or review["scope"] != "author_wording"):
            raise ValueError("anonymous author-wording review required: " + rsid)
        try:
            if date.fromisoformat(review["on"]).isoformat() != review["on"]:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValueError("exact review date required: " + rsid) from None
        src = note["provenance"]
        if (not isinstance(src, dict) or set(src) != {"document_id", "sha256", "cells"}
                or not re.fullmatch(r"[a-z0-9_]+", str(src.get("document_id", "")))
                or not re.fullmatch(r"[0-9a-f]{64}", str(src.get("sha256", "")))
                or not isinstance(src.get("cells"), list) or not src["cells"]
                or any(not isinstance(c, str) or not re.fullmatch(r"[A-Z]+[1-9][0-9]*", c)
                       for c in src["cells"])):
            raise ValueError("source digest and exact cells required: " + rsid)


def author_note(rsid: str, level: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the original and labelled translation on every machine-readable face."""
    notes = core._read_knowledge_raw("panel_author_notes.json").get("notes", {})
    note = notes.get(rsid)
    if note is None:
        return None
    validate({rsid: note}, core._read_knowledge_raw("panel_intake.json"))
    translated = lang() != "ru"
    return {**note, "text": note["en" if translated else "ru"],
            "translated": translated, "original_language": "ru", "level": level,
            "interpretation": "author_opinion_not_a_conclusion",
            "label": t("panel.author_note", level=level or "—"),
            "translation_label": t("panel.author_translation") if translated else None,
            "caveat": t("panel.author_opinion")}


def note_lines(note: Optional[Dict[str, Any]]) -> str:
    """One shared label for CLI panel books and patient-specific system cards."""
    if not note:
        return ""
    heading = note["label"]
    if note.get("translation_label"):
        heading += " — " + note["translation_label"]
    return heading + "\n" + note["text"] + "\n" + note["caveat"]
