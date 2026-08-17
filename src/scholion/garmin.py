"""Rebuilding lifestyle data from a Garmin export — with safe defaults and a backup.

A thin wrapper over `src/ingest/ingest_garmin.py` (all the parsing logic is there). The
difference from the bare script: (1) auto-discovery of the `garmin_export` folder;
(2) the canonical output `profile/wearable_trends.json`; (3) a BACKUP of the previous file
before overwriting; (4) resetting the core cache so the application picks up the new data
without a restart.

Idempotent: a full re-build from the export (it rebuilds entirely, it does not append) —
which is why it is safe to run after every fresh Garmin GDPR export.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, Optional

from . import core
from .i18n import t as _t


def _load_builder():
    """Load build() from src/ingest/ingest_garmin.py (it lives outside the package)."""
    p = core.repo_dir() / "src" / "ingest" / "ingest_garmin.py"
    if not p.exists():
        raise FileNotFoundError(_t("garmin.builder_missing", path=p))
    spec = importlib.util.spec_from_file_location("_sch_ingest_garmin", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _is_export(c: Path) -> bool:
    """The folder looks like garmin_export (contains DI_CONNECT) or is DI_CONNECT itself."""
    try:
        if (c / "DI_CONNECT").is_dir():
            return True
        return c.is_dir() and any(c.glob("DI-Connect-Aggregator"))
    except Exception:
        return False


def find_export() -> Optional[Path]:
    """Where the wearable export is, when nobody said. Never outside the data directory.

    The same defect as the one `reconcile._default_lab_dir` carried, and reaching
    one level further: the search ran over `base`, `base.parent` AND
    `base.parent.parent`. From a delivered package that is the folder the package
    was unpacked into and the folder above it — somebody's documents, by
    construction. Verified from the built package: it resolved to a real
    `garmin_export` two directories away, and `ingest-garmin` would have written
    the trends and the per-night file into the package's own profile.

    Years of a person's sleep and heart rate are not less private than a lab
    form, so the rule is the same one and for the same reason: an automatic
    search may look where the data layout says data lives, and nowhere else.

      1. `profile/sources.json` — the person's own permanent setting;
      2. `raw/wearables/` — the declared slot, wherever that slot points;
      3. a folder by name INSIDE the data directory.

    Anything else has to be passed as an argument. `nearby_candidate` names what
    it can see without opening it.
    """
    cands = []
    folder = core.source_config().get("garmin")
    if folder:
        cands.append(Path(folder).expanduser())
    slot = core.raw_dir("wearables")
    cands += [slot, slot / "DI_CONNECT", slot / "garmin_export",
              slot / "garmin_export" / "DI_CONNECT"]
    base = core.repo_dir()
    cands += [base / "garmin_export", base / "garmin_export" / "DI_CONNECT"]
    for c in cands:
        if c and _is_export(c):
            return c
    return None


def nearby_candidate() -> Optional[Path]:
    """An export that is visible but will NOT be read without being named.

    Deliberately separate from `find_export`: this one only ever produces a
    sentence for a person to read, never a path the code opens.
    """
    base = core.repo_dir()
    for d in (base.parent, base.parent.parent):
        for c in (d / "garmin_export", d / "garmin_export" / "DI_CONNECT"):
            if _is_export(c):
                return c
    return None


def _merge_metrics(fresh: Dict[str, Any], prev_path: Path) -> int:
    """Merge a fresh build with the previous file.

    The rule: a month's value from the FRESH build always wins (the export is the
    source of truth), but months that are absent from the fresh build are preserved
    from the previous file. This way an incomplete export, or one that did not download
    in full, cannot silently erase history — which has already happened in practice.

    Returns the number of preserved data points.
    """
    if not prev_path.exists():
        return 0
    try:
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return 0
    # Markers of a break in the series survive a rebuild. They are not derived from the
    # export (it holds no device history) — a human sets them, and silently losing them on
    # the next ingest means bringing back a conclusion that is an artefact of a device change.
    cf = (prev.get("_meta") or {}).get("comparable_from")
    if cf:
        fresh.setdefault("_meta", {})["comparable_from"] = cf

    kept = 0
    fm = fresh.setdefault("metrics", {})
    for key, months in (prev.get("metrics") or {}).items():
        cur = fm.setdefault(key, {})
        for month, val in (months or {}).items():
            if month not in cur:
                cur[month] = val
                kept += 1
        fm[key] = {m: cur[m] for m in sorted(cur)}
    return kept


def reingest(folder: Optional[str] = None) -> Dict[str, Any]:
    """Rebuild wearable_trends.json from the export. Makes a backup of the previous file."""
    gdir = Path(folder).expanduser() if folder else find_export()
    if not gdir or not gdir.exists():
        # An export that is visible but was not named is reported, not opened.
        hint = nearby_candidate()
        return {"ok": False, "error": _t("garmin.no_export"),
                "candidate": str(hint) if hint else None,
                "candidate_hint": _t("garmin.candidate_hint", path=hint) if hint else None}
    try:
        data = _load_builder().build(str(gdir))
    except Exception as e:  # noqa
        return {"ok": False, "error": _t("garmin.parse_failed", error=e)}
    if not data.get("metrics"):
        return {"ok": False, "error": _t("garmin.nothing_recognised", path=gdir)}
    out = core.profile_dir() / "wearable_trends.json"
    backup = None
    if out.exists():
        bpath = out.with_name("wearable_trends.json.bak")
        try:
            bpath.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
            backup = bpath.name
        except Exception:
            backup = None
    preserved = _merge_metrics(data, out)
    nightly = data.pop("nightly_sleep", None)
    core.write_json(out, data, indent=2)
    nights = 0
    if nightly:
        # Per-night data goes into a separate file: it is needed for n-of-1 analyses
        # (experiments with coffee, schedule, load), not for month-by-month trends.
        np_ = core.profile_dir() / "sleep_nightly.json"
        core.write_json(np_, {
            "_meta": {"source": _t("garmin.nightly_source"),
                      "granularity": "nightly",
                      "note": _t("garmin.nightly_note"),
                      "nights": len(nightly),
                      "range": f"{nightly[0]['date']}–{nightly[-1]['date']}"},
            "nights": nightly}, indent=None)
        nights = len(nightly)
    core.reset_cache()
    m = data.get("_meta", {})
    return {"ok": True, "metrics": len(data.get("metrics", {})), "nights": nights,
            "preserved": preserved,
            "range": m.get("range"),
            "out": str(out), "backup": backup, "source": str(gdir)}
