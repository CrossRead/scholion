"""One lifestyle layer, more than one device — and never the two mixed up.

Until now the layer had a single supplier, so «the resting heart rate» was a
sentence that could be finished. With a second one it cannot: a Garmin and a
WHOOP both report resting heart rate, HRV, respiration and sleep, and they do
not measure them the same way — different window, different algorithm, different
place on the body. Put both into one series and the chart shows a step on the
month the second export was loaded, which a reader will take for a change in
themselves. That is this project's own signature defect, printed on a graph.

So a measurement is stored together with the device that made it:

    {"_meta": {"shape": "...", "comparable_from": {...}},
     "sources": {"garmin": {"_meta": ..., "metrics": {...}, "workouts": {...}},
                 "whoop":  {"_meta": ..., "metrics": {...}, "workouts": {...}}}}

For somebody with one device this changes nothing they can see. For somebody
with two, every number carries the name of what produced it, and where both
measured the same thing, the engine does not average them and does not silently
pick — see `engine.lifestyle`.

**A file written by an older version is migrated on read**, and the source it is
filed under is taken from what that file says about itself rather than assumed:
a profile whose journal does not name a device is filed under `unspecified` and
the report says so. Guessing «it was probably Garmin» would put somebody else's
watch under a name they never chose, and nothing downstream could tell.

The discovery rules are the ones the Garmin path arrived at the hard way and are
not relaxed here: an automatic search looks where the data layout says data
lives and nowhere else; anything further away is named in a sentence and opened
only when a person passes it as an argument.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import core
from .i18n import t as _t

#: There is no version number of our own here, and that is deliberate: `_meta.schema`
#: already means something else in this project — the version of the PROFILE file
#: format, which the core refuses to read when it is newer than the build. A second
#: counter under the same name would make every reader declare this file written by
#: a version from the future. The shape says what it is instead: a file with
#: `sources` is the current one, a file without it is older and is migrated on read.
SHAPE = ("one block per device: sources.<device>.metrics/workouts. A metric is stored "
         "together with the device that measured it, because two devices do not measure "
         "the same thing the same way.")

#: Every supported export: the module that reads it, the folder names worth
#: trying, and how to recognise one by its contents. Adding a third device is an
#: entry here plus a reader — not a new command, not a new endpoint, not a new
#: line in four faces.
KINDS: Tuple[Dict[str, Any], ...] = (
    {"source": "garmin", "builder": "ingest_garmin.py",
     "folders": ("garmin_export", "DI_CONNECT", "garmin_export/DI_CONNECT")},
    {"source": "whoop", "builder": "ingest_whoop.py",
     "folders": ("whoop", "whoop_export", "my_whoop_data")},
)
_BY_SOURCE = {k["source"]: k for k in KINDS}


def device_label(name: Optional[str]) -> str:
    """What to call a device on screen.

    `unspecified` is a real answer and gets a sentence rather than a blank: it
    means the file predates the device being recorded, and a reader deserves to
    know that the name is missing rather than to see a name that was invented.
    """
    if not name:
        return ""
    known = {"garmin": "Garmin", "whoop": "WHOOP", "apple_health": "Apple Health"}
    if name in known:
        return known[name]
    if name == "unspecified":
        return _t("wearables.unspecified")
    return name


def _builder(name: str):
    """Load a reader from `src/ingest/` — they live outside the package."""
    p = core.repo_dir() / "src" / "ingest" / name
    if not p.exists():
        raise FileNotFoundError(_t("wearables.builder_missing", path=p))
    spec = importlib.util.spec_from_file_location(f"_sch_{Path(name).stem}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── recognising an export ─────────────────────────────────────────────────────

def _is_garmin(c: Path) -> bool:
    try:
        if (c / "DI_CONNECT").is_dir():
            return True
        return c.is_dir() and any(c.glob("DI-Connect-Aggregator"))
    except Exception:                                            # noqa: BLE001
        return False


def detect(path: Path) -> Optional[str]:
    """Which device wrote this, judged by what is inside it.

    Names decide nothing: a folder somebody called `whoop` is not evidence, and
    an archive called `export.zip` may well be one. This is the same rule the
    genome side arrived at — ask the bytes before the file name.
    """
    p = Path(path).expanduser()
    if not p.exists():
        return None
    if _is_garmin(p):
        return "garmin"
    try:
        if _builder("ingest_whoop.py").looks_like_export(p):
            return "whoop"
    except Exception:                                            # noqa: BLE001
        return None
    return None


def find_export(source: Optional[str] = None) -> Optional[Tuple[Path, str]]:
    """Where an export is, when nobody said. Never outside the data directory.

    1. `profile/sources.json` — the person's own permanent setting, per device;
    2. `raw/wearables/` — the declared slot, wherever that slot points;
    3. a folder by one of the known names INSIDE the data directory.

    Anything else has to be passed as an argument. Returns the path together
    with the device it was recognised as, so the caller never has to assume.
    """
    cfg = core.source_config()
    cands: List[Path] = []
    for kind in KINDS:
        if source and kind["source"] != source:
            continue
        folder = cfg.get(kind["source"])
        if folder:
            cands.append(Path(folder).expanduser())
    slot = core.raw_dir("wearables")
    base = core.repo_dir()
    for parent in (slot, base):
        cands.append(parent)
        for kind in KINDS:
            if source and kind["source"] != source:
                continue
            for name in kind["folders"]:
                cands.append(parent / name)
    for c in cands:
        if not c:
            continue
        found = detect(c)
        if found and (not source or found == source):
            return c, found
        if c.is_dir():                       # an archive sitting in the slot
            for f in sorted(c.glob("*.zip")):
                found = detect(f)
                if found and (not source or found == source):
                    return f, found
    return None


def nearby_candidate() -> Optional[Tuple[Path, str]]:
    """An export that is visible but will NOT be read without being named.

    Deliberately separate from `find_export`: this one only ever produces a
    sentence for a person to read, never a path the code opens.
    """
    base = core.repo_dir()
    for d in (base.parent, base.parent.parent):
        for kind in KINDS:
            for name in kind["folders"]:
                c = d / name
                found = detect(c) if c.exists() else None
                if found:
                    return c, found
    return None


# ── the file: one shape, whatever wrote it ────────────────────────────────────

def migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    """A file from an older version, brought to the current shape on read.

    The device is read out of what the file says about itself. When it says
    nothing, the source is `unspecified` — which is a fact the report can print,
    unlike a guess, which it could not.
    """
    if not data or data.get("sources"):
        return data
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else None
    if metrics is None:
        # the oldest shape of all: the metrics sat flat at the top level
        metrics = {k: v for k, v in data.items()
                   if isinstance(v, dict) and k not in ("_meta", "workouts", "Workouts")}
    said = json.dumps(data.get("_meta") or {}, ensure_ascii=False).lower()
    name = ("garmin" if "garmin" in said else
            "apple_health" if "apple" in said else "unspecified")
    meta = dict(data.get("_meta") or {})
    cmp_from = meta.pop("comparable_from", None)
    out: Dict[str, Any] = {
        "_meta": {"shape": SHAPE, "migrated": True},
        "sources": {name: {"_meta": meta, "metrics": metrics or {},
                           "workouts": data.get("workouts") or data.get("Workouts") or {}}},
    }
    if cmp_from:
        out["_meta"]["comparable_from"] = cmp_from
    return out


def series(data: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """`[(source, block)]` in a stable order, whatever schema the file is in."""
    d = migrate(data or {})
    return sorted((d.get("sources") or {}).items())


def shared_metrics(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Metrics more than one device reports here — the ones nothing may merge."""
    seen: Dict[str, List[str]] = {}
    for src, block in series(data):
        for key in (block.get("metrics") or {}):
            seen.setdefault(key, []).append(src)
    return {k: v for k, v in seen.items() if len(v) > 1}


def _merge(fresh: Dict[str, Any], previous: Dict[str, Any], source: str) -> int:
    """A fresh build wins per month; months it does not carry survive.

    The rule the Garmin path already had, now applied inside one device rather
    than across the file: an export that did not download in full cannot quietly
    erase history — which has happened in practice — and an export from one
    device cannot touch another's series at all.
    """
    prev = migrate(previous or {})
    block = (prev.get("sources") or {}).get(source) or {}
    kept = 0
    fm = fresh.setdefault("metrics", {})
    for key, months in (block.get("metrics") or {}).items():
        cur = fm.setdefault(key, {})
        for month, val in (months or {}).items():
            if month not in cur:
                cur[month] = val
                kept += 1
        fm[key] = {m: cur[m] for m in sorted(cur)}
    return kept


OVERLAY = "wearable_metrics.local.json"


def knowledge() -> Dict[str, Any]:
    """The wearable reference, with the person's own additions merged over it.

    The report names every column it does not know, and a name without a way to
    act on it is a complaint. This is the way to act on it: a file of the same
    shape in the profile, holding only what the shipped table is missing. It is
    merged per column rather than wholesale, so an addition cannot quietly
    delete the sixteen columns that already work, and it lives in the profile
    because it is a fact about one person's export rather than about the format.

        {"sources": {"whoop": {"columns": {"Fatigue score %": {"metric": "Recovery"}}}},
         "metrics": {"MyOwnThing": {"label": "...", "group": "recovery"}}}
    """
    base = core.wearable_metrics()
    p = core.profile_dir() / OVERLAY
    if not p.exists():
        return base
    try:
        extra = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return base
    merged = json.loads(json.dumps(base))
    for key, spec in (extra.get("metrics") or {}).items():
        merged.setdefault("metrics", {})[key] = spec
        if key not in (merged.get("order") or []):
            merged.setdefault("order", []).append(key)
    for dev, block in (extra.get("sources") or {}).items():
        tgt = merged.setdefault("sources", {}).setdefault(dev, {})
        tgt.setdefault("columns", {}).update(block.get("columns") or {})
        if block.get("structural"):
            tgt["structural"] = list(tgt.get("structural") or []) + list(block["structural"])
    return merged


def reingest(folder: Optional[str] = None, source: Optional[str] = None) -> Dict[str, Any]:
    """Rebuild one device's part of the lifestyle layer. Backs up the file first."""
    if folder:
        path = Path(folder).expanduser()
        found = detect(path)
        if not found:
            return {"ok": False, "error": _t("wearables.not_an_export", path=path)}
        if source and found != source:
            return {"ok": False, "error": _t("wearables.wrong_device", path=path,
                                             found=found, asked=source)}
        source = found
    else:
        hit = find_export(source)
        if not hit:
            near = nearby_candidate()
            return {"ok": False, "error": _t("wearables.no_export"),
                    "candidate": str(near[0]) if near else None,
                    "candidate_hint": (_t("wearables.candidate_hint", path=near[0], device=near[1])
                                       if near else None)}
        path, source = hit

    kind = _BY_SOURCE[source]
    try:
        mod = _builder(kind["builder"])
        built = (mod.build(str(path), knowledge())
                 if source == "whoop" else mod.build(str(path)))
    except Exception as e:                                       # noqa: BLE001
        return {"ok": False, "error": _t("wearables.parse_failed", error=e)}
    if built.get("ok") is False or not built.get("metrics"):
        return {"ok": False, "error": _t("wearables.nothing_recognised", path=path, device=source)}

    # An export off the person's own wrist is a measurement of theirs, so it
    # claims the profile the same way a lab point does: a demonstration lying
    # here is erased before anything is written, rather than gaining a second
    # person's months of sleep beside a fictional one's. The erase is read
    # BEFORE `previous`, or the merge below would carry the demonstration's own
    # generated series forward into the file that replaced it.
    from . import subject as _subject
    claimed = _subject.claim_for_owner()
    claimed = claimed if claimed.get("claimed") else None

    out = core.profile_dir() / "wearable_trends.json"
    previous = {}
    backup = None
    if out.exists():
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
            bpath = out.with_name("wearable_trends.json.bak")
            bpath.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")
            backup = bpath.name
        except Exception:                                        # noqa: BLE001
            backup = None

    nightly = built.pop("nightly_sleep", None)
    built.pop("ok", None)
    preserved = _merge(built, previous, source)

    data = migrate(previous) if previous else {"_meta": {}, "sources": {}}
    data.setdefault("_meta", {})["shape"] = SHAPE
    data.setdefault("sources", {})[source] = built
    core.write_json(out, data, indent=2)

    nights = 0
    if nightly:
        # Per-night data lives apart: it feeds n-of-1 experiments, not monthly trends.
        np_ = core.profile_dir() / f"sleep_nightly.{source}.json" if source != "garmin" \
            else core.profile_dir() / "sleep_nightly.json"
        core.write_json(np_, {
            "_meta": {"source": source, "granularity": "nightly",
                      "note": _t("wearables.nightly_note", device=source),
                      "nights": len(nightly),
                      "range": f"{nightly[0]['date']}–{nightly[-1]['date']}"},
            "nights": nightly}, indent=None)
        nights = len(nightly)

    core.reset_cache()
    m = built.get("_meta", {})
    shared = shared_metrics(data)
    return {"ok": True, "source": source, "claimed": claimed,
            "metrics": len(built.get("metrics", {})),
            "nights": nights, "preserved": preserved, "range": m.get("range"),
            "unrecognised_columns": m.get("unrecognised_columns") or [],
            "shared_metrics": sorted(shared),
            "sources_present": sorted(data.get("sources") or {}),
            "out": str(out), "backup": backup, "path": str(path)}
