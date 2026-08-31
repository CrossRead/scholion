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
#: The text of the conclusion itself. Two things this had wrong, and both were
#: silent: the recogniser above accepts «Заключение врача» case-insensitively while
#: this pattern demanded the word in CAPITALS, so a document writing it in mixed
#: case was accepted as a study and then yielded an empty body; and the word had to
#: be followed by a newline, so «Заключение: синусовый ритм» — the text on the SAME
#: line, which is how a discharge summary writes it — matched nothing.
#:
#: Anchored to the start of a line on purpose. Unanchored and case-insensitive, it
#: would also match the printed disclaimer «Данное заключение не является
#: диагнозом» and lift the small print out as the finding.
_BODY = re.compile(r"^[ \t]*ЗАКЛЮЧЕНИЕ(?:\s+врача)?[ \t]*:?[ \t]*\n?(.+)",
                   re.S | re.I | re.M)

#: Why a file yielded no record. Every file that produced nothing lands in exactly
#: one of these, and the result names it — because the counts alone are what let a
#: ten-page discharge summary pass in silence for six years. `ingest_labs` learned
#: this first (see `ingest_labs_report`); this loader is where the lesson was not
#: applied.
#:
#: The four are not equal. A lab form here is EXPECTED — the other loader owns it,
#: and saying so is bookkeeping, not an alarm. The last two are the alarming ones:
#: a file that reads like a study but gave up no conclusion, and a file this loader
#: cannot place at all.
REASON_SEVERAL = "several_documents_in_one_file"
#: A file that WAS split, where some pieces still gave up nothing.
REASON_PART_NOT_READ = "part_of_a_split_file_not_read"
REASON_NO_TEXT = "no_text"
REASON_LAB_FORM = "looks_like_a_lab_form"
REASON_NOT_EXTRACTED = "conclusion_not_extracted"
REASON_UNCLASSIFIED = "unclassified"

#: The two that mean something was probably lost, as opposed to handed on.
ALARMING = (REASON_SEVERAL, REASON_PART_NOT_READ, REASON_NO_TEXT, REASON_NOT_EXTRACTED, REASON_UNCLASSIFIED)


#: A section heading inside a multi-document file: a title, then the date of THAT
#: section, alone on the line. Structural on purpose — a list of study names typed
#: here would be a vocabulary out of memory, and it would go stale the first time a
#: clinic renamed a section. What is recognised is the SHAPE «title + date + end of
#: line», and a title ending in a colon is excluded because that is a field label
#: («Дата рождения: 01.01.1970»), not a heading.
_SECTION = re.compile(r"^[ \t]*([А-ЯЁ][^\n:]{3,70}?)[ \t]+"
                      r"(\d{2})[.\-/](\d{2})[.\-/](\d{4})[ \t]*$", re.M)


def sections_in(text: str) -> List[Dict[str, str]]:
    """The study sections of a multi-document file: «what» and «when», in order.

    Two or more of these mean one PDF is carrying several studies. This loader
    cannot split such a file yet — but a file it cannot split must SAY SO, with the
    count, instead of being handed to the laboratory loader as somebody else's
    problem. That handoff is how a ten-page discharge summary fell between the two
    loaders and stayed out of the profile for six years.
    """
    out: List[Dict[str, str]] = []
    for m in _SECTION.finditer(text or ""):
        out.append({"what": _clean(m.group(1)),
                    "date": f"{m.group(4)}-{m.group(3)}-{m.group(2)}"})
    return out


def split_documents(text: str) -> List[Dict[str, str]]:
    """One PDF holding several studies → one slice per study, in order.

    A section runs from its heading to the next heading; the tail runs to the end
    of the file. Measured on a real ten-page discharge summary: fifteen headings,
    of which four are laboratory panels the other loader owns, one is the clinic's
    own letterhead line, and ten are studies each followed by its conclusion.

    Nothing here decides which slice is a study — the ordinary parser does, on
    each slice in turn. A slice it cannot make a study of is reported as such, and
    that is how the letterhead sorts itself out: no vocabulary of clinic names is
    kept, because a vocabulary of names is the thing that goes stale the first
    time a clinic renames itself.

    An empty list means this is not a multi-document file, and the caller reads it
    whole as before.
    """
    hits = list(_SECTION.finditer(text or ""))
    if len(hits) < 2:
        return []
    out: List[Dict[str, str]] = []
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        out.append({"what": _clean(m.group(1)),
                    "date": f"{m.group(4)}-{m.group(3)}-{m.group(2)}",
                    "text": text[m.start():end]})
    # The prologue: whatever stood before the first heading. Kept so that nothing
    # of the file is unaccounted for — the accounting invariant this loader now
    # keeps is about files, and a file read in pieces owes the same of its pieces.
    if hits[0].start() > 0:
        head = text[:hits[0].start()]
        if head.strip():
            out.insert(0, {"what": "", "date": "", "text": head})
    return out


def decline_reason(text: str, study: Optional[Dict[str, Any]]) -> Optional[str]:
    """Why this file produced no study — or ``None`` when it produced one.

    Kept apart from `parse_study` on purpose: the parser answers «what is in this
    file», and this answers «what happened to it». A parser that returns ``None``
    for four different situations cannot be reported on, and an unreportable
    refusal is the same as no refusal at all.
    """
    if not (text or "").strip():
        return REASON_NO_TEXT
    if len(sections_in(text)) >= 2:
        # BEFORE the conclusion is accepted, and this order was the whole lesson
        # of the real file. Its first section carries a conclusion of its own, so
        # the parser lifted THAT one, the file passed as a single study, and the
        # other nine went into the profile as a fragment of one record's text.
        # A file that holds ten studies is not one study with a long conclusion,
        # however well the first one parses.
        # Checked BEFORE the laboratory handoff: a file carrying both a lab panel
        # and several studies would otherwise be declared somebody else's, and the
        # other loader drops it for a reason of its own. Neither report would then
        # hold a line about it.
        return REASON_SEVERAL
    if study and study.get("conclusion"):
        return None
    if _LAB.search(text) and not _KIND.search(text):
        return REASON_LAB_FORM
    if _CONCL.search(text) or _KIND.search(text):
        return REASON_NOT_EXTRACTED
    return REASON_UNCLASSIFIED


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
    mm = _BODY.search(text)
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
    missed: List[Dict[str, Any]] = []
    for f in files:
        key = str(f)
        mtime = f.stat().st_mtime
        if not force and manifest.get(key) == mtime:
            skipped += 1
            continue
        text = _read_pdf(f) or ""
        st = parse_study(text, source=f.name)
        manifest[key] = mtime
        # ── a file that holds several studies is read as several ─────────────
        if decline_reason(text, st) == REASON_SEVERAL:
            kept, lost = 0, []
            for n, part in enumerate(split_documents(text)):
                sub = parse_study(part["text"], source=f.name)
                if not sub or not sub.get("conclusion"):
                    lost.append(part["what"] or _t("studies.part_before_the_first_heading"))
                    continue
                # The section heading is the better name and the better date: the
                # parser reads what a single form looks like, and inside a summary
                # the heading is what says which study this is and when.
                sub["kind"] = part["what"] or sub.get("kind")
                sub["date"] = part["date"] or sub.get("date")
                sub["part_of"] = f.name
                sid = f"{_sid(f, sub['date'])}_{n:02d}"
                sub["id"] = sid
                prev = by_id.get(sid)
                if prev:
                    for keep in ("answers", "does_not_answer", "note"):
                        if prev.get(keep):
                            sub[keep] = prev[keep]
                    if prev.get("open"):
                        sub["open"] = prev["open"]
                    by_id[sid] = sub
                    updated.append(sid)
                else:
                    by_id[sid] = sub
                    added.append(sid)
                kept += 1
            if kept:
                # Named even when it worked: a file read in pieces owes the same
                # accounting as one read whole, and the pieces nothing came of are
                # the ones a person would want to look at by hand.
                if lost:
                    missed.append({"file": f.name, "reason": REASON_PART_NOT_READ,
                                   "detail": _t("studies.reason_part_not_read",
                                                n=len(lost), kept=kept),
                                   "parts": lost})
                continue

        reason = decline_reason(text, st)
        if reason:
            # Named, not dropped. Which file, and what happened to it — so that a
            # document nobody parsed is a line in the report rather than an absence.
            item = {"file": f.name, "reason": reason,
                    "detail": _t("studies.reason_" + reason)}
            if reason == REASON_SEVERAL:
                found = sections_in(text)
                item["sections"] = found
                item["detail"] = _t("studies.reason_several_documents_in_one_file",
                                    n=len(found))
            missed.append(item)
            continue
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
            # Every file seen is accounted for: taken, unchanged, or named below.
            # The invariant is asserted by a test, not trusted to this line.
            "not_ingested": missed,
            "alarming": sum(1 for m in missed if m["reason"] in ALARMING),
            "hint": _t("studies.hint") if added else ""}
