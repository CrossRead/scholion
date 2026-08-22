#!/usr/bin/env python3
"""WHOOP data export (the zip that arrives by email) → the lifestyle layer.

    python3 ingest_whoop.py <folder-or-zip> [<out_wearable_trends.json>]

Input: the export WHOOP builds from «More → App Settings → Data Export» — four
CSV files (`physiological_cycles`, `sleeps`, `workouts`, `journal_entries`),
delivered as a link to a zip. Either the zip or the folder it was unpacked into
works; nothing is downloaded and no account is contacted.

**Why the export and not the API.** WHOOP has one, and it would give fresher
data. It also requires an account, an OAuth client and a round trip to somebody
else's server for every reading, and this product has no credential of any kind
by construction. A file the person already owns costs them one request a day and
costs their privacy nothing.

**The column names are read, never assumed.** WHOOP does not publish the schema
of this export, and a schema nobody published is a schema that can change without
telling anyone. So the header row decides what is read: each column is looked up
in a table that ships as DATA (`knowledge/wearable_metrics.json`, `sources.whoop`)
rather than as code, a column that is not in the table is **listed by its own
name** in the report, and nothing is inferred from a column's position or from a
name that merely looks familiar. A person whose export carries a column we have
never seen gets told about it and can add one line to the local overlay; the
alternative — matching on «looks like a heart rate» — is how a number ends up
under the wrong label and is never questioned again.

Output has the same shape the Garmin builder produces, so the layer above does
not care which device it came from: monthly means per metric, workouts by year
and a per-night list. It is written under the source name rather than merged
into whatever was there before — see `wearables.py` for why that matters.

Standard library only.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SOURCE = "whoop"

#: The files worth opening, by the stem WHOOP gives them. Anything else in the
#: archive is left alone: `journal_entries` is the person's own free-text log of
#: behaviours, which is not a measurement and does not belong in a trend.
WANTED = ("physiological_cycles", "sleeps", "workouts")


def _norm(header: str) -> str:
    """Case and spacing are noise; meaning is not.

    Lowercasing and collapsing whitespace absorbs the difference between
    `Recovery score %` and `recovery  score %`. Nothing else is normalised on
    purpose: stripping the parenthesised unit would make `Duration (min)` and
    `Duration (hours)` the same column, which is exactly the kind of quiet
    equivalence this file exists to avoid.
    """
    return " ".join((header or "").strip().lower().split())


def _num(raw: str) -> Optional[float]:
    """A number, or nothing. An empty cell is missing data, not a zero."""
    s = (raw or "").strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _month(raw: str) -> Optional[str]:
    """`YYYY-MM` out of a WHOOP timestamp, or nothing.

    The export writes local time as `YYYY-MM-DD HH:MM:SS` and carries the zone in
    its own column. Only the calendar month is taken, so the zone changes nothing
    — and a cell that does not begin with a date is not repaired by guessing.
    """
    s = (raw or "").strip()
    if len(s) >= 7 and s[:4].isdigit() and s[4] == "-" and s[5:7].isdigit():
        return s[:7]
    return None


def _date(raw: str) -> Optional[str]:
    s = (raw or "").strip()
    return s[:10] if _month(s) and len(s) >= 10 and s[7] == "-" else None


def _minutes_after_2000(raw: str) -> Optional[float]:
    """Bedtime as minutes from 20:00 local — the convention the layer already uses."""
    s = (raw or "").strip()
    if len(s) < 16 or s[10] != " " or s[13] != ":":
        return None
    try:
        h, m = int(s[11:13]), int(s[14:16])
    except ValueError:
        return None
    mins = h * 60 + m - 20 * 60
    return mins + 24 * 60 if mins < -12 * 60 else mins


#: How a raw cell becomes the value the dictionary promises. Named in the data
#: table by key, so a new column needs a line of JSON and not a line of code.
CONVERTERS = {
    "number": _num,
    "minutes_to_hours": lambda raw: (lambda v: None if v is None else round(v / 60.0, 3))(_num(raw)),
    "clock_to_minutes_after_2000": _minutes_after_2000,
}


def _structural(knowledge: Optional[Dict[str, Any]]) -> set:
    """Headers that are known and are NOT measurements.

    Without this the report would name every timestamp as «a column I do not
    know», and a list that long is a list nobody reads — which would quietly
    undo the one thing the list is for.
    """
    src = ((knowledge or {}).get("sources") or {}).get(SOURCE) or {}
    return {_norm(h) for h in (src.get("structural") or ())}


def _columns_table(knowledge: Optional[Dict[str, Any]]) -> Dict[str, Tuple[str, str]]:
    """`normalised header → (metric key, converter)`, out of the knowledge base.

    Taking it from the knowledge base rather than from a constant here is what
    lets somebody whose export differs fix their own case without waiting for a
    release: the local overlay is merged into this table by the caller.
    """
    src = ((knowledge or {}).get("sources") or {}).get(SOURCE) or {}
    out: Dict[str, Tuple[str, str]] = {}
    for header, spec in (src.get("columns") or {}).items():
        if isinstance(spec, dict) and spec.get("metric"):
            out[_norm(header)] = (spec["metric"], spec.get("read", "number"))
    return out


def _is_nap(row: Dict[str, str]) -> bool:
    """A nap is a sleep, and it is not a night.

    The sleep file marks them in a column of its own. Averaging a forty-minute
    nap into a month of nights would report sleep getting shorter, which is a
    statement about the file rather than about the person.
    """
    for k, v in row.items():
        if _norm(k) == "nap":
            return (v or "").strip().lower() in ("true", "yes", "1")
    return False


def _open_csvs(root: Path) -> Tuple[Dict[str, List[Dict[str, str]]], List[str]]:
    """The three files that carry measurements, from a folder or from the zip.

    Returns what was read and what was seen but not opened, because a file
    present and silently ignored is indistinguishable from a file that was
    missing — and only one of those is the person's problem to fix.
    """
    tables: Dict[str, List[Dict[str, str]]] = {}
    seen: List[str] = []

    def take(name: str, text: str) -> None:
        stem = Path(name).stem.lower()
        seen.append(Path(name).name)
        if stem in WANTED and stem not in tables:
            tables[stem] = list(csv.DictReader(io.StringIO(text)))

    if root.is_file() and zipfile.is_zipfile(root):
        with zipfile.ZipFile(root) as z:
            for info in z.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".csv"):
                    continue
                if Path(info.filename).name.startswith("._"):   # a macOS resource fork
                    continue
                take(info.filename, z.read(info).decode("utf-8-sig", "replace"))
    elif root.is_dir():
        # The export is AT this folder, or inside the single folder a zip
        # unpacks into. Nothing deeper, and nothing beside other folders: a
        # search that walked the tree would call any ancestor of an export an
        # export, which is how the genome side once reached into a stranger's
        # documents. One subfolder is a wrapper; several are somebody's disk.
        found = sorted(root.glob("*.csv"))
        if not found:
            subdirs = [d for d in sorted(root.iterdir()) if d.is_dir()
                       and not d.name.startswith((".", "__"))]
            if len(subdirs) == 1:
                found = sorted(subdirs[0].glob("*.csv"))
        for p in found:
            if p.name.startswith("._"):
                continue
            take(p.name, p.read_text(encoding="utf-8-sig", errors="replace"))
    return tables, seen


def looks_like_export(path: Path) -> bool:
    """Is this a WHOOP export? Decided by what is inside, not by what it is called.

    A folder somebody renamed `whoop` is not evidence, and a zip named
    `my_whoop_data.zip` need not be one. Two of the three measurement files have
    to actually be there.
    """
    try:
        tables, _ = _open_csvs(Path(path))
    except Exception:                                            # noqa: BLE001
        return False
    return len(tables) >= 2


def build(source: str, knowledge: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The export → monthly metrics, workouts by year, and a night-by-night list."""
    root = Path(source).expanduser()
    tables, seen = _open_csvs(root)
    if not tables:
        return {"ok": False, "reason": "no_csv", "files_seen": seen}

    table = _columns_table(knowledge)
    structural = _structural(knowledge)
    monthly: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    unrecognised: Dict[str, int] = defaultdict(int)
    undated = 0
    rows_read = 0

    # Monthly means come from the CYCLE file and not from both. Two reasons, and
    # the second is the one a synthetic fixture could never have shown: the cycle
    # file already carries that night's sleep in its own columns, so reading both
    # counts the same night twice; and the sleep file also holds NAPS, which are
    # rows of forty minutes that would drag a month of nightly sleep downwards.
    # Where an export has no cycle file, the sleep file answers instead — with
    # naps left out, and the report says which file it read.
    primary = "physiological_cycles" if tables.get("physiological_cycles") else "sleeps"
    naps_skipped = 0
    for stem in (primary,):
        for row in tables.get(stem, []):
            if _is_nap(row):
                naps_skipped += 1
                continue
            month = None
            for k, v in row.items():
                if _norm(k) in ("cycle start time", "sleep onset", "start time"):
                    month = _month(v)
                    if month:
                        break
            if not month:
                undated += 1
                continue
            rows_read += 1
            for header, raw in row.items():
                hit = table.get(_norm(header))
                if not hit:
                    if (raw or "").strip() and _norm(header) not in structural:
                        unrecognised[header.strip()] += 1
                    continue
                key, how = hit
                val = CONVERTERS.get(how, _num)(raw)
                if val is not None:
                    monthly[key][month].append(val)

    metrics = {k: {m: round(sum(v) / len(v), 2) for m, v in sorted(months.items()) if v}
               for k, months in monthly.items()}
    metrics = {k: v for k, v in metrics.items() if v}

    workouts: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for row in tables.get("workouts", []):
        month = None
        for k, v in row.items():
            if _norm(k) in ("workout start time", "cycle start time"):
                month = _month(v)
                if month:
                    break
        if not month:
            continue
        label = None
        minutes = None
        for k, v in row.items():
            n = _norm(k)
            if n == "activity name":
                label = (v or "").strip() or None
            elif n == "duration (min)":
                minutes = _num(v)
        if not label:
            continue
        y = workouts.setdefault(month[:4], {}).setdefault(label, {"count": 0, "hours": 0.0})
        y["count"] += 1
        y["hours"] = round(y["hours"] + (minutes or 0) / 60.0, 2)

    nightly = []
    for row in tables.get("sleeps", []):
        if _is_nap(row):
            continue
        d = None
        for k, v in row.items():
            if _norm(k) in ("sleep onset", "cycle start time"):
                d = _date(v)
                if d:
                    break
        if not d:
            continue
        night: Dict[str, Any] = {"date": d}
        for header, raw in row.items():
            hit = table.get(_norm(header))
            if not hit:
                continue
            key, how = hit
            val = CONVERTERS.get(how, _num)(raw)
            if val is not None:
                night[key] = val
        if len(night) > 1:
            nightly.append(night)
    nightly.sort(key=lambda n: n["date"])

    months_all = sorted({m for v in metrics.values() for m in v})
    return {
        "ok": True,
        "source": SOURCE,
        "_meta": {
            "source": "WHOOP data export (physiological cycles, sleeps, workouts)",
            "range": f"{months_all[0]}–{months_all[-1]}" if months_all else None,
            "rows_read": rows_read,
            "metrics_from": primary,
            "naps_left_out": naps_skipped,
            "rows_without_a_date": undated,
            "files_read": sorted(tables),
            "unrecognised_columns": sorted(unrecognised),
            "note": ("MONTHLY averages of the WHOOP daily cycles (key YYYY-MM). Columns are "
                     "matched by the header row against a published table; a column that is "
                     "not in the table is listed above rather than guessed at."),
        },
        "metrics": metrics,
        "workouts": workouts,
        "nightly_sleep": nightly,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    here = Path(__file__).resolve().parents[1] / "scholion" / "knowledge" / "wearable_metrics.json"
    knowledge = json.loads(here.read_text(encoding="utf-8")) if here.exists() else {}
    data = build(sys.argv[1], knowledge)
    if not data.get("ok"):
        print(f"✗ {data.get('reason')}; files seen: {', '.join(data.get('files_seen') or []) or '—'}")
        return 1
    out = sys.argv[2] if len(sys.argv) > 2 else "wearable_trends.whoop.json"
    Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    m = data["_meta"]
    print(f"✓ {out}")
    print(f"  range: {m['range']}; metrics: {len(data['metrics'])}; nights: {len(data['nightly_sleep'])}")
    if m["unrecognised_columns"]:
        print("  columns not in the table (nothing was read from them):")
        for c in m["unrecognised_columns"]:
            print(f"    · {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
