"""Import a panel of lab results from a CSV or TSV file.

A blood panel is thirty rows. Entering it as thirty commands is not an import
path, it is a reason not to start — and the person who does start gets it half
done, which is worse than not at all, because a profile with a third of a panel
in it looks like a profile.

Columns: `marker,date,value,unit,ref_low,ref_high,note`. Only the first four are
required; the header may be in any order and the file may use commas, semicolons
or tabs — a European spreadsheet exports semicolons, and refusing that file would
mean the person has to know why.

**All or nothing.** A file with one bad row writes nothing at all. The alternative
— write what parsed, report the rest — leaves the profile in a state nobody chose:
half a panel, of one date, with no record of which half. Re-running the corrected
file would then double up the good rows or silently skip them, and both outcomes
are indistinguishable from having imported correctly.

**The report names the row and the reason**, every time. «3 rows rejected» is not
a report, it is a notification that something is wrong somewhere.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core, store
from .i18n import t as _t

REQUIRED = ("marker", "date", "value")
#: Recognised header spellings → the canonical column name. Both languages,
#: because the file is typed by a person and not produced by this program.
HEADERS = {
    "marker": "marker", "key": "marker", "test": "marker", "analyte": "marker",
    "показатель": "marker", "маркер": "marker", "анализ": "marker",
    "date": "date", "дата": "date",
    "value": "value", "result": "value", "значение": "value", "результат": "value",
    "unit": "unit", "units": "unit", "единица": "unit", "ед": "unit", "ед.изм.": "unit",
    "ref_low": "ref_low", "low": "ref_low", "min": "ref_low", "норма_от": "ref_low",
    "ref_high": "ref_high", "high": "ref_high", "max": "ref_high", "норма_до": "ref_high",
    "note": "note", "comment": "note", "примечание": "note",
}


def _sniff(text: str) -> str:
    """The delimiter, decided by counting rather than by guessing at a locale."""
    head = text.splitlines()[0] if text.splitlines() else ""
    return max((";", "\t", ","), key=head.count) if head else ","


def _num(raw: str) -> Optional[float]:
    """A number as a person writes it: a comma may be the decimal mark."""
    s = (raw or "").strip().replace(" ", "").replace(" ", "")
    if not s:
        return None
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def preview(text: str) -> Dict[str, Any]:
    """Parse and validate without writing. The same work as the import, minus the write."""
    rows: List[Dict[str, Any]] = []
    problems: List[Dict[str, Any]] = []

    # Comment rows: the shipped template explains its own columns in them, and a
    # person editing that template should not have to delete the instructions
    # before the file will load.
    text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    reader = csv.DictReader(io.StringIO(text), delimiter=_sniff(text))
    if not reader.fieldnames:
        return {"ok": False, "error": _t("import_csv.empty"), "rows": [], "problems": []}
    mapping = {}
    for raw in reader.fieldnames:
        canon = HEADERS.get((raw or "").strip().casefold())
        if canon:
            mapping[raw] = canon
    missing = [c for c in REQUIRED if c not in mapping.values()]
    if missing:
        return {"ok": False, "rows": [], "problems": [],
                "error": _t("import_csv.missing_columns", columns=", ".join(missing),
                            seen=", ".join(f for f in reader.fieldnames if f))}

    for i, raw_row in enumerate(reader, start=2):          # row 1 is the header
        row = {canon: (raw_row.get(src) or "").strip() for src, canon in mapping.items()}
        marker, date = row.get("marker", ""), row.get("date", "")
        value = _num(row.get("value", ""))
        if not marker or not date:
            problems.append({"row": i, "reason": _t("import_csv.need_marker_date")})
            continue
        if value is None:
            problems.append({"row": i, "marker": marker,
                             "reason": _t("import_csv.value_not_number",
                                          value=row.get("value", ""))})
            continue
        res = core.resolve_marker(marker)
        if not res.get("key"):
            cands = ", ".join(c["key"] for c in res.get("candidates") or [])
            problems.append({"row": i, "marker": marker,
                             "reason": _t("import_csv.unknown_marker",
                                          did_you_mean=cands or _t("store.no_candidates"))})
            continue
        key = res["key"]
        spec = core.lab_markers().get("markers", {}).get(key) or {}
        unit = row.get("unit", "")
        if spec.get("unit"):
            u = core.resolve_unit(spec, unit)
            if not u.get("ok"):
                # The unit is checked HERE and not at write time on purpose: a
                # dry run that says «looks fine» and an import that then refuses
                # half the file is a check nobody can rely on.
                problems.append({"row": i, "marker": key,
                                 "reason": _t("import_csv.bad_unit", unit=unit or "—",
                                              accepted=", ".join(u.get("accepted") or []))})
                continue
        rows.append({"row": i, "key": key, "date": date, "value": value, "unit": unit,
                     "ref_low": _num(row.get("ref_low", "")),
                     "ref_high": _num(row.get("ref_high", "")),
                     "note": row.get("note", "")})
    return {"ok": not problems, "rows": rows, "problems": problems}


def run(path: str, dry_run: bool = False) -> Dict[str, Any]:
    """Import a file. Writes only when every row is good."""
    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        return {"ok": False, "error": _t("import_csv.file_not_found", path=str(p))}
    try:
        text = p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:                    # noqa: BLE001
        return {"ok": False, "error": _t("import_csv.unreadable", path=str(p), error=str(e))}

    res = preview(text)
    if res.get("error"):
        return {"ok": False, "error": res["error"]}
    out = {"ok": res["ok"], "file": str(p), "accepted": len(res["rows"]),
           "rejected": len(res["problems"]), "problems": res["problems"],
           "dry_run": bool(dry_run), "written": 0, "markers": []}
    if res["problems"]:
        out["error"] = _t("import_csv.nothing_written", n=len(res["problems"]))
        return out
    if dry_run:
        out["markers"] = sorted({r["key"] for r in res["rows"]})
        return out

    for r in res["rows"]:
        w = store.add_lab_point(r["key"], r["date"], r["value"], unit=r["unit"] or None,
                                ref_low=r["ref_low"], ref_high=r["ref_high"],
                                date_source="manual", subject="owner")
        if not w.get("ok"):
            # Should be unreachable — preview ran the same gates. If it happens,
            # it is a divergence between the check and the write, and saying so is
            # more useful than a partial success reported as success.
            out["ok"] = False
            out["error"] = _t("import_csv.write_failed", row=r["row"], detail=w.get("error", ""))
            return out
        out["written"] += 1
    out["markers"] = sorted({r["key"] for r in res["rows"]})
    return out
