"""Preview self-contained laboratory forms without borrowing dates across pages.

A page without a draw header is a continuation only when its order identifier
and consecutive page number agree with the preceding form. A preview token binds
source bytes, parsed observations, knowledge and the destination profile. Nothing
is written until that exact preview is explicitly applied.
"""
from __future__ import annotations

import hashlib
import json
import re
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, Optional

from . import core, i18n, ingest_labs as reader, store
from .i18n import t

_PAGE = re.compile(r"(?:Page|Страница)\s*(\d+)\s*(?:of|из|/)\s*(\d+)", re.I)
_ORDER = re.compile(r"(?:Order(?:\s+(?:ID|number))?|Номер\s+заказа|Заказ)\s*[:#№]\s*([\w-]+)", re.I)
_BLOOD = ("blood", "serum", "plasma", "кров", "сыворот", "плазм")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "absent"


def _specimen(text: str) -> Optional[str]:
    labels = list(reader._BIOMAT.finditer(text))
    if not labels:
        return None
    kinds = set()
    for match in labels:
        value = match.group(1).lower()
        found = {kind for words, kind in reader._MAT_WORDS
                 if any(word in value for word in words)}
        if any(word in value for word in _BLOOD):
            found.add("blood")
        if len(found) != 1:
            return None
        kinds.update(found)
    return next(iter(kinds)) if len(kinds) == 1 else None


def _identity(text: str):
    order = _ORDER.search(text)
    page = _PAGE.search(text)
    return (order.group(1) if order else None,
            tuple(map(int, page.groups())) if page else None)


def _stamp(text: str) -> Optional[str]:
    stamps = set(reader._form_stamps(text))
    found = [m for m in reader._DATE_EN.finditer(text)
             if "report" not in m.group(0).lower() and "service" not in m.group(0).lower()]
    if len(list(reader._DATE.finditer(text))) + len(found) > 1:
        return None
    for match in found:
        date = "-".join(match.groups())
        clock = reader._TIME_AFTER.match(text[match.end():match.end() + 24])
        if clock:
            date += f"T{int(clock.group(1)):02d}:{int(clock.group(2)):02d}"
        stamps.add(date)
    if len(stamps) != 1:
        return None
    date = next(iter(stamps))
    return date if store.date_resolution(date) else None


def split_forms(text: str) -> Dict[str, Any]:
    """Conservative page grouping; an orphan or inconsistent page rejects a file."""
    pages = text.split("\f")
    while pages and not pages[-1].strip():
        pages.pop()
    forms: list[Dict[str, Any]] = []
    for number, page in enumerate(pages, 1):
        if not page.strip() or reader._DERIVED.search(page):
            return {"ok": False, "reason": "unreadable_or_derived_page", "page": number}
        stamp, specimen = _stamp(page), _specimen(page)
        if ((reader._BIOMAT.search(page) and specimen is None)
                or ((reader._DATE.search(page) or reader._DATE_EN.search(page)) and stamp is None)):
            return {"ok": False, "reason": "ambiguous_form_header", "page": number}
        if len({m.group(1) for m in _ORDER.finditer(page)}) > 1:
            return {"ok": False, "reason": "ambiguous_form_header", "page": number}
        identity, pagination = _identity(page)
        if pagination and not 1 <= pagination[0] <= pagination[1]:
            return {"ok": False, "reason": "ambiguous_form_header", "page": number}
        previous = forms[-1] if forms else None
        continuation = bool(previous and identity and identity == previous["order"]
                            and pagination and previous["pagination"]
                            and pagination == (previous["pagination"][0] + 1,
                                               previous["pagination"][1]))
        if continuation:
            assert previous is not None
            if ((stamp and stamp != previous["date"])
                    or (specimen and specimen != previous["specimen"])
                    or len(reader._form_stamps(page)) > 1):
                return {"ok": False, "reason": "conflicting_continuation", "page": number}
            previous["text"] += "\n" + page
            previous["pages"].append(number)
            previous["pagination"] = pagination
        elif stamp and specimen and (not pagination or pagination[0] == 1):
            if previous and previous["pagination"] and previous["pagination"][0] != previous["pagination"][1]:
                return {"ok": False, "reason": "incomplete_form", "page": number}
            forms.append({"date": stamp, "specimen": specimen, "pages": [number],
                          "order": identity, "pagination": pagination, "text": page})
        else:
            return {"ok": False, "reason": "ambiguous_form_boundary", "page": number}
    if not forms:
        return {"ok": False, "reason": "no_text"}
    last = forms[-1]["pagination"]
    if last and last[0] != last[1]:
        return {"ok": False, "reason": "incomplete_form", "page": len(pages)}
    return {"ok": True, "forms": forms}


def preview(folder: str) -> Dict[str, Any]:
    """Read-only plan. Unknown boundaries never produce an approval token."""
    inputs = reader._inputs(folder)
    if not inputs["ok"]:
        return inputs
    rows: list[Dict[str, Any]] = []
    forms: list[Dict[str, Any]] = []
    refused: list[Dict[str, Any]] = []
    sources: Dict[str, str] = {}
    markers = core.lab_markers().get("markers", {})
    seen: Dict[tuple, Dict[str, Any]] = {}
    for path in inputs["files"]:
        try:
            before = _digest(path)
            text = reader._read_any(path) or ""
            if _digest(path) != before:
                raise ValueError("source_changed_during_read")
            sources[str(path.resolve())] = before
            if path.suffix.lower() != ".pdf":
                refused.append({"file": path.name, "reason": "archive_requires_pdf"})
                continue
            split = split_forms(text)
            if not split["ok"]:
                refused.append({"file": path.name, **split})
                continue
            for form in split["forms"]:
                _, values = reader.parse_report(form["text"], markers, source=str(path))
                if not values:
                    refused.append({"file": path.name, "pages": form["pages"], "reason": "no_known_marker"})
                    continue
                keys, readings = [], []
                for key, value in values.items():
                    spec = markers[key]
                    fingerprint = (key, form["date"])
                    observation = {"value": value["value"], "unit": value.get("unit") or spec.get("unit"),
                                   "censored": value.get("censored"), "ref_low": value["ref_low"],
                                   "ref_high": value["ref_high"]}
                    if fingerprint in seen and seen[fingerprint] != observation:
                        refused.append({"file": path.name, "pages": form["pages"],
                                        "reason": "conflicting_observations", "marker": key})
                    seen[fingerprint] = observation
                    context = {**value, "source": {"path": str(path.resolve()), "sha256": before,
                               "pages": form["pages"], "specimen": form["specimen"], "draw_date": form["date"]}}
                    rl, rh = value["ref_low"], value["ref_high"]
                    if spec.get("ref_locked") and not value.get("reference_table"):
                        rl, rh = spec.get("ref_low"), spec.get("ref_high")
                    rows.append({"key": key, "date": form["date"], **observation, "ref_low": rl,
                                 "ref_high": rh, "name": core.marker_display(spec, i18n.lang()),
                                 "direction": spec.get("direction"), "reference_context": context})
                    keys.append(key)
                    readings.append({"marker": key, "name": core.marker_display(spec, i18n.lang()),
                                     **observation})
                forms.append({"file": path.name, "pages": form["pages"], "date": form["date"],
                              "specimen": form["specimen"], "markers": keys, "readings": readings})
        except (OSError, ValueError, reader.PdfUnreadable) as exc:
            refused.append({"file": path.name, "reason": "read_error", "detail": str(exc)})
    destination = store._path("labs.json").resolve()
    destination_hash = _digest(destination)
    payload = {"profile": str(core.profile_dir().resolve()), "destination": str(destination),
               "destination_sha256": destination_hash, "sources": sources, "rows": rows}
    token = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {"ok": True, "status": "refused" if refused else "preview", "preview": True,
            "forms": forms, "not_ingested": refused, "points_added": 0,
            "approval_token": None if refused or not rows else token,
            "message": t("archive.preview_note"), "folder": str(Path(folder).expanduser().resolve()), "_payload": payload}


def run(folder: str, approval: str = "") -> Dict[str, Any]:
    """Preview, or apply a still-matching plan atomically to the pinned profile."""
    from . import container
    with container.pinned(), core.profile_write_lock() if approval else nullcontext():
        plan = preview(folder)
        payload = plan.pop("_payload", None)
        if not approval:
            return plan
        if not payload or not plan.get("approval_token") or approval != plan["approval_token"]:
            return {**plan, "ok": False, "error": t("archive.changed"), "points_added": 0}
        try:
            if any(_digest(Path(path)) != digest for path, digest in payload["sources"].items()):
                return {**plan, "ok": False, "error": t("archive.changed"), "points_added": 0}
        except OSError:
            return {**plan, "ok": False, "error": t("archive.changed"), "points_added": 0}
        result = store.add_lab_batch(payload["rows"], from_forms=True,
                                     expected_profile_hash=payload["destination_sha256"])
        return {**plan, **result, "preview": False, "status": "applied" if result["ok"] else "refused",
                "points_added": result.get("written", 0), "approval_token": None,
                "files_processed": len(payload["sources"]) if result["ok"] else 0,
                "per_file": [{"file": form["file"], "date": form["date"],
                              "pages": form["pages"], "markers": form["markers"]}
                             for form in plan["forms"]] if result["ok"] else []}
