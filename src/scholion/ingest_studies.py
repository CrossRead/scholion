"""Automatic ingest of doctors' CONCLUSIONS and instrumental studies → profile/studies.json.

Why a separate loader. `ingest_labs` takes NUMBERS out of a PDF by the marker dictionary.
Conclusions of an ECG, echocardiography, ultrasound, MRI and consultation protocols hold no
numbers from that dictionary at all — so they passed the profile by entirely and lived only
as prose in labs.md. The consequence was not theoretical: the assistant called a study that
had in fact been done «not done», and wrote that into the questions for the doctor.

What it does: walks the folder, picks out files that look like a conclusion (rather than a
form with markers), extracts the date, the kind of study, the doctor, the text of the
conclusion and the block of recommendations — and puts them into studies.json. Incremental
by the manifest (path+mtime), idempotent: the record of the same file is replaced.

What it does NOT do: it does not interpret. The fields `answers`/`does_not_answer` — which
questions the study answers and which it does not — are filled in by the assistant by hand,
because that is a judgement, not an extraction.
"""
from __future__ import annotations
import json
import os
import re
import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core
from .i18n import t as _t
from .ingest_labs import _read_pdf, _ensure_extractor

# Signs of a doctor's conclusion / an instrumental study.
_CONCL = re.compile(r"ЗАКЛЮЧЕНИЕ|ПРОТОКОЛ\s+(?:УЛЬТРАЗВУКОВОГО\s+)?ИССЛЕДОВАНИЯ|"
                    r"ПРОТОКОЛ\s+ИССЛЕДОВАНИЯ|Заключение\s+врача|консультаци", re.I)
# Signs of an ordinary lab form — such files are handled by ingest_labs, here they are extra.
_LAB = re.compile(r"референсн|единиц[аы]\s+измерени|биоматериал|результат\s+исследовани[йя]\s*$",
                  re.I | re.M)
# «Дата: DD.MM.YYYY», «Дата обследования: DD.MM.YYYY», «Дата исследования …».
# The birth date is excluded explicitly — it stands higher up and used to match first.
_DATE = re.compile(r"Дата(?!\s+рождения)(?:\s+\w+)?\s*:?\s*(\d{2})[.\-/](\d{2})[.\-/](\d{4})")
# The kind of study is looked for BY KEYWORDS in the header, not as «the first row in caps»:
# the fallback «first row in upper case» caught the radiographer's signature and the row
# «Консультация невролога» out of the block of recommendations.
_KIND = re.compile(r"^\s*(ЭКГ|ЭХОКАРДИОГРАФИЯ[^\n]*|ПРОТОКОЛ\s+УЛЬТРАЗВУКОВОГО[^\n]*|"
                   r"Магнитно-резонансная томографи[^\n]*|Компьютерная томографи[^\n]*|"
                   r"МРТ[^\n]*|КТ\s[^\n]*|Рентгеногра[^\n]*|Денситометри[^\n]*|"
                   r"Спирометри[^\n]*|Холтер[^\n]*|Консультация\s+врача[^\n]*|"
                   r"АНАЛИЗ\s+ЛАБОРАТОРНЫХ[^\n]*)\s*$", re.I | re.M)
_AREA = re.compile(r"Область\s+исследовани[яй]\s*:?\s*([^\n]{2,60})", re.I)
_DOCTOR = re.compile(r"Врач[^:\n]*:?\s*([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?)")
_REC = re.compile(r"РЕКОМЕНДОВАНО[:\s]*(.{0,400}?)(?:ПОДПИСИ|Врач|$)", re.I | re.S)
_TAIL = re.compile(r"(?:ПОДПИСИ|Данное заключение не является диагнозом).*$", re.I | re.S)


def _manifest_file() -> Path:
    p = core.mkdir_private(core.cache_dir())
    return p / "ingest_studies_manifest.json"


def _load_manifest() -> Dict[str, float]:
    f = _manifest_file()
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except Exception:                                                # noqa: BLE001
        return {}


def _save_manifest(d: Dict[str, float]) -> None:
    try:
        core.write_json(_manifest_file(), d, indent=1)
    except Exception:                                                # noqa: BLE001
        pass


def _clean(s: str) -> str:
    return " ".join((s or "").split())


def looks_like_conclusion(text: str) -> bool:
    """Is this a doctor's conclusion rather than a lab form?

    The order of the checks matters: some forms carry the word «ЗАКЛЮЧЕНИЕ» in their header
    as well, which is why the laboratory signs outweigh it.
    """
    if not text or len(text) < 200:
        return False
    if _LAB.search(text) and not _KIND.search(text):
        return False
    return bool(_CONCL.search(text))


def parse_study(text: str, source: str = "") -> Optional[Dict[str, Any]]:
    """Extract the date, the kind, the doctor, the conclusion and the recommendations."""
    if not looks_like_conclusion(text):
        return None
    m = _DATE.search(text)
    date = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None
    k = _KIND.search(text)
    kind = _clean(k.group(1)) if k else ""
    area = _AREA.search(text)
    if not area:
        # In ultrasound protocols the organ stands on the NEXT row after the heading, in caps
        # («ПРОТОКОЛ УЛЬТРАЗВУКОВОГО ИССЛЕДОВАНИЯ / ЩИТОВИДНОЙ ЖЕЛЕЗЫ …»). Without it every
        # ultrasound study looks the same and they cannot be told apart.
        m2 = re.search(r"(?:ПРОТОКОЛ\s+УЛЬТРАЗВУКОВОГО\s+ИССЛЕДОВАНИЯ|О\s+ИССЛЕДОВАНИЯ)\s*\n"
                       r"\s*([А-ЯЁ][А-ЯЁ\s,\-()]{4,80})\s*\n", text)
        if m2:
            kind = f"{kind} — {_clean(m2.group(1)).capitalize()}" if kind else _clean(m2.group(1))
    elif kind:
        kind = f"{kind} — {_clean(area.group(1))}"
    body = ""
    mm = re.search(r"ЗАКЛЮЧЕНИЕ[^\n]*\n(.+)", text, re.S)
    if mm:
        body = _clean(_TAIL.sub("", mm.group(1)))[:1200]
    rec = _REC.search(text)
    recs: List[str] = []
    if rec:
        for part in re.split(r"[.\n]", _clean(rec.group(1))):
            part = part.strip(" .;")
            if len(part) > 4:
                recs.append(part)
    # The kind of study is text lifted OUT OF the Russian form; the substitutions below
    # shorten it in the language it was written in. Only the fallback below is ours.
    kind = re.sub(r"^ПРОТОКОЛ\s+УЛЬТРАЗВУКОВОГО\s+ИССЛЕДОВАНИЯ\s*(?:—\s*)?", "УЗИ — ", kind or "",
                  flags=re.I).strip(" —")
    kind = re.sub(r"^УЗИ\s+—\s+Ультразвуковое исследование\s+", "УЗИ — ", kind, flags=re.I)
    doc = _DOCTOR.search(text)
    return {"date": date, "kind": kind or _t("studies.kind_default"), "source": source,
            "conclusion": body, "recommendations": recs[:6],
            "doctor": _clean(doc.group(1)) if doc else None,
            "ingested": _dt.date.today().isoformat(),
            "answers": [], "does_not_answer": [],
            "open": [{"what": r, "note": _t("studies.from_conclusion")} for r in recs[:6]]}


def _sid(path: Path, date: Optional[str]) -> str:
    """A stable id out of the file name. Cyrillic is NOT thrown away: Russian names used to
    collapse into an empty string, and different files ended up with one and the same id."""
    import hashlib
    stem = re.sub(r"[^A-Za-zА-Яа-яЁё0-9]+", "", path.stem).lower()
    if len(stem) < 3:
        stem = "study"
    if len(stem) > 28:
        stem = stem[:24] + hashlib.md5(path.stem.encode("utf-8")).hexdigest()[:4]
    return f"{stem}_{(date or 'nodate').replace('-', '')}"


def ingest(folder: str, force: bool = False) -> Dict[str, Any]:
    """Walk the folder of PDFs and update profile/studies.json with conclusions. Incremental."""
    if not _ensure_extractor():
        return {"ok": False, "error": _t("studies.no_pdf_reader")}
    root = Path(folder).expanduser()
    if not root.exists() or not root.is_dir():
        return {"ok": False, "error": _t("studies.folder_not_found", path=root)}
    p = core.profile_dir() / "studies.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {
        "_meta": {"what": _t("studies.meta_what")},
        "studies": []}
    by_id = {s.get("id"): s for s in data.get("studies") or []}
    manifest = _load_manifest()
    files = sorted(root.rglob("*.pdf"))
    added, updated, skipped = [], [], 0
    for f in files:
        key = str(f)
        mtime = f.stat().st_mtime
        if not force and manifest.get(key) == mtime:
            skipped += 1
            continue
        text = _read_pdf(f) or ""
        st = parse_study(text, source=f.name)
        manifest[key] = mtime
        if not st or not st.get("conclusion"):
            continue                      # an empty conclusion means a form, not a report
        sid = _sid(f, st["date"])
        st["id"] = sid
        if sid in by_id:
            prev = by_id[sid]
            # The assistant's judgements are not overwritten — a PDF cannot restore them.
            for keep in ("answers", "does_not_answer", "note"):
                if prev.get(keep):
                    st[keep] = prev[keep]
            if prev.get("open"):
                st["open"] = prev["open"]
            by_id[sid] = st
            updated.append(sid)
        else:
            by_id[sid] = st
            added.append(sid)
    data["studies"] = sorted(by_id.values(), key=lambda s: (s.get("date") or "", s.get("id") or ""))
    (data.setdefault("_meta", {}))["updated"] = _dt.date.today().isoformat()
    core.write_json(p, data, indent=1)
    _save_manifest(manifest)
    core.reset_cache()
    return {"ok": True, "files_seen": len(files), "skipped_unchanged": skipped,
            "added": len(added), "updated": len(updated), "total": len(data["studies"]),
            "new_ids": added[:20],
            "hint": _t("studies.hint") if added else ""}
