"""Writing into the profile (editing from the UI): adding lab points and prescriptions.

Writes ONLY into profile/ (labs.json, medications.json) — patient data. The code and the
knowledge base are left untouched. After a write it resets the core cache.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core
from .i18n import t as _t


_NAME_DOMAIN = {"labs.json": "labs", "medications.json": "medications", "metrics.json": "metrics"}


import functools as _functools


def _serialized(fn):
    """Every profile mutator holds the profile write-lock for its whole
    read-modify-write, so concurrent writes from the server's threads or a
    parallel CLI cannot lose each other's changes (core.profile_write_lock)."""
    @_functools.wraps(fn)
    def _w(*a, **k):
        with core.profile_write_lock():
            return fn(*a, **k)
    return _w


def _path(name: str) -> Path:
    """The path to write to: if a folder is chosen for the domain we write there, otherwise
    into the profile. Reading and writing use the same folder (consistency)."""
    dom = _NAME_DOMAIN.get(name)
    if dom:
        return core.source_path(dom)
    return core.profile_dir() / name


# Domains the project itself knows the shape of — a JSON data file it writes (labs,
# medications, metrics), a folder of documents it reads on command (labs_docs, med_docs),
# or a wearable/genome export a built-in command ingests (garmin, genome). "apple_health"
# is here too even though nothing parses it yet: the project already documents it as a
# standard, supported source type (see layout.readme.raw_wearables), not a personal one-off.
#
# These eight are guaranteed to land in "folders" rather than "external_sources" below.
# That is the only thing this list buys: it is NOT a spelling check. "grmin" is simply an
# unrecognised name like any other, so it becomes a new external_sources entry rather than
# an error — "garmin" itself is left exactly as it was, not overwritten and not corrected.
# A fuzzy "did you mean garmin?" guess was deliberately left out: unlike the marker-name
# gate in add_lab_point (guarding a case that silently corrupted real lab history), nothing
# reads external_sources programmatically today, so a typo here is inert — a stray key a
# person notices by eye in sources.json, not silently-wrong data.
_KNOWN_SOURCE_DOMAINS = ("labs", "medications", "metrics", "genome",
                        "labs_docs", "med_docs", "garmin", "apple_health")


@_serialized
def set_source_folder(domain: str, folder: str) -> Dict[str, Any]:
    """Bind a data domain to a chosen folder on disk.

    A known domain (labs/medications/metrics/genome/labs_docs/med_docs/garmin/apple_health)
    is saved under profile/sources.json → "folders", protected by the whitelist above.
    Anything else is a personal, user-defined source — a CGM app's screenshots, a specific
    sequencing provider's export folder, whatever the next person's device happens to be
    called — and is saved under "external_sources" instead of being refused: every person's
    raw data differs, so there is nothing to whitelist against. `core.source_config()` reads
    both sections the same way, so the split only matters here, at the point of setting it.

    For JSON domains, if the folder has no file yet, it moves the current data there from
    the profile (so that nothing is lost)."""
    domain = (domain or "").strip()
    if not domain:
        return {"ok": False, "error": _t("store.unknown_source")}
    fp = Path((folder or "").strip()).expanduser()
    if not fp.exists() or not fp.is_dir():
        return {"ok": False, "error": _t("store.folder_not_found", path=fp)}
    cfgp = core.profile_dir() / "sources.json"
    cfg = json.loads(cfgp.read_text(encoding="utf-8")) if cfgp.exists() else {}
    cfg.setdefault("_meta", {"purpose": _t("store.sources_purpose")})
    section = "folders" if domain in _KNOWN_SOURCE_DOMAINS else "external_sources"
    cfg.setdefault(section, {})[domain] = str(fp)
    _write_json(cfgp, cfg)
    core.reset_cache()
    # move the data into the new folder if there is no file there yet
    fname = core._DOMAIN_FILE.get(domain)
    if fname:
        target = fp / fname
        if not target.exists():
            src = core.profile_dir() / fname
            if src.exists():
                target.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        core.reset_cache()
    return {"ok": True, "domain": domain, "folder": str(fp), "section": section}


@_serialized
def clear_source_folder(domain: str) -> Dict[str, Any]:
    """Return the domain to the default profile folder (whichever section it was set under)."""
    cfgp = core.profile_dir() / "sources.json"
    if cfgp.exists():
        cfg = json.loads(cfgp.read_text(encoding="utf-8"))
        cfg.get("folders", {}).pop(domain, None)
        cfg.get("external_sources", {}).pop(domain, None)
        _write_json(cfgp, cfg)
        core.reset_cache()
    return {"ok": True, "domain": domain, "folder": None}


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    core.write_json(path, data, indent=2)


@_serialized
def set_draw_context(day: str, reason: str = "", between: str = "",
                     marker: Optional[str] = None) -> Dict[str, Any]:
    """Record why a day holds two draws and what stood between them.

    Attached to the LATER point of the day, because that is the measurement the
    context explains — the first one is the baseline it is being compared against.
    Applied to every marker measured twice that day unless one is named: the
    procedure or the dose happened once, not once per analyte, and making the
    person repeat themselves for each line of a panel is how a useful field ends
    up empty.
    """
    if not day or not (reason or between):
        return {"ok": False, "error": _t("store.need_day_and_context")}
    p = _path("labs.json")
    if not p.exists():
        return {"ok": False, "error": _t("store.no_labs")}
    data = json.loads(p.read_text(encoding="utf-8"))
    ctx = " · ".join(x for x in (reason.strip(), between.strip()) if x)
    touched = []
    for key, m in (data.get("markers") or {}).items():
        if marker and key != marker:
            continue
        pts = [pt for pt in (m.get("series") or [])
               if str(pt.get("date", "")).startswith(day) and len(str(pt.get("date", ""))) > 10]
        if len(pts) < 2:
            continue
        latest = sorted(pts, key=lambda x: str(x["date"]))[-1]
        latest["draw_context"] = ctx
        touched.append(key)
    if not touched:
        return {"ok": False, "error": _t("store.no_repeat_that_day", day=day)}
    _write_json(p, data)
    return {"ok": True, "day": day, "markers": sorted(touched), "context": ctx}


def add_lab_point(marker: str, date: str, value: float, *, name: Optional[str] = None,
                  unit: Optional[str] = None, ref_low: Optional[float] = None,
                  ref_high: Optional[float] = None, direction: Optional[str] = None,
                  censored: Optional[str] = None, new: bool = False) -> Dict[str, Any]:
    """Add/update a marker point in labs.json (by date YYYY-MM or YYYY-MM-DD).

    censored — the censoring sign of the result, if the lab printed not a number but a
    boundary: "<" for «less than 10^4» / «<0.4 U/mL», ">" for «more than 10^8». The value
    itself is stored AT THE BOUNDARY (otherwise there is nothing to build the series from),
    while the engine needs the sign so that «less than 10^5» against a lower limit of 10^5
    reads as BELOW the reference range, not as «exactly at the edge, all is well».
    """
    if not marker or not date:
        return {"ok": False, "error": _t("store.need_marker_date")}
    try:
        value = float(value)
    except (TypeError, ValueError):
        return {"ok": False, "error": _t("store.value_not_number")}
    p = _path("labs.json")
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"markers": {}}
    markers = data.setdefault("markers", {})

    # ── the name gate ────────────────────────────────────────────────────────
    # A marker the dictionary does not know and the profile does not hold is a
    # typo far more often than it is a new analyte. Creating it silently is what
    # produced two series of one test under two spellings, each looking ordinary.
    # So: resolve the name, and create only when asked to in as many words.
    if marker not in markers:
        res = core.resolve_marker(marker)
        if res.get("key"):
            marker = res["key"]
        elif not new:
            cands = ", ".join(f'{c["key"]} ({c["name"]})' for c in res.get("candidates") or [])
            return {"ok": False,
                    "error": _t("store.marker_unknown", marker=marker,
                                did_you_mean=cands or _t("store.no_candidates")),
                    "candidates": res.get("candidates") or []}

    m = markers.get(marker)

    # ── the unit gate ────────────────────────────────────────────────────────
    # Thresholds are stored in the canonical unit and do not name it: glucose ≥ 5.6
    # means mmol/L. A value of 95 arriving as mg/dL and written down as 95 is then
    # compared against 5.6 and reported as far above the action threshold. Nothing
    # fails, nothing warns, and the sentence ends up in a document for a doctor.
    #
    # So a unit is either recognised and CONVERTED, or the point is refused. The
    # third option — storing it as written and hoping — is the one that produced
    # the defect.
    spec = core.lab_markers().get("markers", {}).get(marker) or {}
    known = bool(spec.get("unit"))
    if unit:
        res = (core.convert_to_canonical(spec, unit, value) if known
               else {"ok": True, "value": value})
        if not res.get("ok"):
            # The refusal names what would be accepted. Without the list the next
            # attempt is a guess at spelling, and a guess that happens to match a
            # DIFFERENT unit is worse than the original error.
            return {"ok": False, "error": _t("store.unit_not_accepted", marker=marker,
                                             unit=unit,
                                             accepted=", ".join(res.get("accepted") or []))}
        value = res["value"]
        # The corridor converts with the value, by the same law. The reference
        # range is printed on the form in the SAME unit as the result, so
        # converting one and not the other reproduces the defect this gateway was
        # built after, one level down: 5.27 mmol/L against a corridor of 70–99,
        # every point reading as far below normal. Found by running the CSV import
        # on a real American panel layout, not by reading this function.
        #
        # Each end goes through `convert_to_canonical` rather than through a
        # multiplier kept here. With HbA1c that difference is the whole answer:
        # the mmol/mol scale converts by a formula, and a bound multiplied instead
        # of transformed lands somewhere else entirely.
        if known:
            # `bound_name`, not `name`: a `for` target is not scoped to the loop,
            # so calling it `name` left the function's own `name` parameter — the
            # marker's printed label — equal to "ref_high" for every point that
            # arrived with a unit. Every marker in a real ingest was renamed to
            # "ref_high" on screen. The loop runs before the None check, so even
            # an empty range did it.
            for bound_name, bound in (("ref_low", ref_low), ("ref_high", ref_high)):
                if bound is None:
                    continue
                r = core.convert_to_canonical(spec, unit, float(bound))
                if r.get("ok"):
                    if bound_name == "ref_low":
                        ref_low = r["value"]
                    else:
                        ref_high = r["value"]
        unit = res.get("canonical") or unit
    elif m is None and known:
        # A new series with no unit: there is nothing to interpret the number
        # against, and «probably the canonical one» is exactly the assumption this
        # gate exists to refuse. An existing series is a different case — it
        # already declares its unit, and the point joins it.
        return {"ok": False, "error": _t("store.unit_required", marker=marker,
                                         accepted=", ".join(core._accepted_units(spec)))}
    if not m:
        # The label comes from the dictionary when it knows the marker: what the
        # person typed may be «glucose», «глюкоза» or the bare key, and none of
        # those is what a report should print. The key alone used to end up on
        # screen for every value entered by hand.
        from .i18n import lang as _lang
        shown = name or core.marker_display(spec, _lang()) or marker
        m = {"name": shown, "unit": unit or "", "series": []}
        if ref_low is not None:
            m["ref_low"] = ref_low
        if ref_high is not None:
            m["ref_high"] = ref_high
        if direction:
            m["direction"] = direction
        markers[marker] = m
    series: List[Dict[str, Any]] = m.setdefault("series", [])
    series[:] = [pt for pt in series if pt.get("date") != date]  # replacing the point of the same date
    pt: Dict[str, Any] = {"date": date, "value": value}
    if censored in ("<", ">"):
        pt["censored"] = censored
    series.append(pt)
    series.sort(key=lambda pt: pt["date"])
    _write_json(p, data)
    core.reset_cache()
    return {"ok": True, "marker": marker, "points": len(series)}


@_serialized
def add_medication(name: str, dose: str = "", note: str = "") -> Dict[str, Any]:
    """Add a prescription to medications.json (an editable list)."""
    if not name:
        return {"ok": False, "error": _t("store.need_name")}
    p = _path("medications.json")
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"medications": []}
    meds: List[Dict[str, str]] = data.setdefault("medications", [])
    entry = {"name": name.strip(), "dose": dose.strip(), "note": note.strip()}
    # dedup by name (case-insensitive): adding again UPDATES the entry rather than
    # breeding duplicates — otherwise the interaction/class logic over prescriptions breaks
    replaced = False
    for i, m in enumerate(meds):
        if m.get("name", "").strip().lower() == entry["name"].lower():
            meds[i] = entry
            replaced = True
            break
    if not replaced:
        meds.append(entry)
    _write_json(p, data)
    core.reset_cache()
    return {"ok": True, "count": len(meds), "updated": replaced}


@_serialized
def remove_medication(name: str) -> Dict[str, Any]:
    """Remove a prescription by name (from medications.json; medications.md is untouched)."""
    p = _path("medications.json")
    if not p.exists():
        return {"ok": False, "error": _t("store.no_medications_file")}
    data = json.loads(p.read_text(encoding="utf-8"))
    before = len(data.get("medications", []))
    data["medications"] = [m for m in data.get("medications", []) if m.get("name", "").lower() != name.lower()]
    _write_json(p, data)
    core.reset_cache()
    return {"ok": True, "removed": before - len(data["medications"])}


def list_medications() -> List[Dict[str, str]]:
    return core.medications_json().get("medications", [])


# ---- personal health metrics (metrics.json) ------------------------------
@_serialized
def add_metric_point(metric: str, date: str, value: float, *, name: Optional[str] = None,
                     unit: Optional[str] = None, ref_low: Optional[float] = None,
                     ref_high: Optional[float] = None, direction: Optional[str] = None) -> Dict[str, Any]:
    """Add/update a health metric point in metrics.json (replacing the point of the same date)."""
    if not metric or not date:
        return {"ok": False, "error": _t("store.need_metric_date")}
    try:
        value = float(value)
    except (TypeError, ValueError):
        return {"ok": False, "error": _t("store.value_not_number")}
    p = _path("metrics.json")
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"profile": {}, "metrics": {}}
    metrics = data.setdefault("metrics", {})
    m = metrics.get(metric)
    if not m:
        m = {"name": name or metric, "unit": unit or "", "series": []}
        if ref_low is not None:
            m["ref_low"] = ref_low
        if ref_high is not None:
            m["ref_high"] = ref_high
        if direction:
            m["direction"] = direction
        metrics[metric] = m
    series: List[Dict[str, Any]] = m.setdefault("series", [])
    series[:] = [pt for pt in series if pt.get("date") != date]
    series.append({"date": date, "value": value})
    series.sort(key=lambda pt: pt["date"])
    _write_json(p, data)
    core.reset_cache()
    return {"ok": True, "metric": metric, "points": len(series)}


@_serialized
def update_metric_profile(fields: Dict[str, Any]) -> Dict[str, Any]:
    """Update the static fields of the health profile.

    `ancestry` joins sex and year of birth because it is the same kind of fact:
    a precondition the engine cannot derive and must not invent. Without it a
    polygenic percentile is computed against a default reference population and
    printed as an ordinary number — the same silent substitution that gave a
    woman a male reference interval.
    """
    p = _path("metrics.json")
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"profile": {}, "metrics": {}}
    prof = data.setdefault("profile", {})
    for k in ("sex", "birth_year", "height_cm", "ancestry"):
        if k in fields and fields[k] not in (None, ""):
            prof[k] = fields[k]
    _write_json(p, data)
    core.reset_cache()
    return {"ok": True, "profile": prof}


@_serialized
def add_focus_entry(date: str, *, alcohol: str = "", atenolol: bool = False,
                    late_meal: bool = False, note: str = "") -> Dict[str, Any]:
    """Add/replace an entry in the episode log (profile/focus_log.json).

    An entry of the same date is replaced — as lab points are. An empty entry (nothing
    happened and there is no note) DELETES the date: that is how an accidental tick is undone.
    """
    date = (date or "").strip()
    if not date:
        return {"ok": False, "error": _t("store.need_date")}
    p = core.profile_dir() / "focus_log.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {
        "_meta": {"what": _t("store.focus_log_what")}, "entries": []}
    entries = [e for e in (data.get("entries") or []) if e.get("date") != date]
    empty = not (alcohol or atenolol or late_meal or (note or "").strip())
    if not empty:
        entries.append({"date": date, "alcohol": alcohol or "", "atenolol": bool(atenolol),
                        "late_meal": bool(late_meal), "note": (note or "").strip()})
    entries.sort(key=lambda e: e.get("date") or "")
    data["entries"] = entries
    core.write_json(p, data, indent=1)
    core.reset_cache()
    return {"ok": True, "date": date, "removed": empty, "entries": len(entries)}


# ---- initial set-up of the data directory --------------------------------


def _write_private(path: Path, text: str) -> None:
    """Create a profile file closed (0600).

    The directory is already 0700, and that is almost always enough. Almost — because a
    person can weaken the directory's permissions themselves, the file can be copied into a
    shared place, and a backup will preserve the mode. It costs one line, which is why it is
    done. An existing file keeps its mode: it is not the business of initialisation to change
    permissions that were set by hand.
    """
    exists = path.exists()
    path.write_text(text, encoding="utf-8")
    if os.name == "posix" and not exists:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass





def init_profile(target: Optional[str] = None, force: bool = False,
                 demo: bool = False) -> Dict[str, Any]:
    """Create the data directory and lay the profile templates into it.

    Idempotent: existing files are not touched unless `force` is given. This matters
    more than convenience — an initialisation command capable of overwriting someone's
    data is more dangerous than the absence of that command.

    `demo=True` puts a synthetic demo profile in place of the empty templates, so that a
    person sees a working product before loading their own files.
    """
    out = Path(target).expanduser().resolve() if target else core.profile_dir()
    core.mkdir_private(out)

    if demo:
        from . import demo as _demo
        if _demo.occupied_by_real_profile(out) and not force:
            return {"ok": False, "dir": str(out),
                    "error": _t("store.demo_occupied")}
        files = _demo.build_all()
        for name, data in files.items():
            _write_private(out / name,
                           json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + "\n")
        _write_private(out / "index.md", _demo.INDEX_MD)
        core.invalidate_cache() if hasattr(core, "invalidate_cache") else None
        return {"ok": True, "dir": str(out), "mode": "demo",
                "written": sorted(list(files) + ["index.md"]), "skipped": []}

    tpl = core.templates_dir() / "profile"
    if not tpl.is_dir():
        return {"ok": False, "dir": str(out),
                "error": _t("store.templates_missing", path=tpl)}

    written, skipped = [], []
    for srcf in sorted(tpl.iterdir()):
        if not srcf.is_file() or srcf.name.startswith("."):
            continue
        dst = out / srcf.name
        if dst.exists() and not force:
            skipped.append(srcf.name)
            continue
        _write_private(dst, srcf.read_text(encoding="utf-8"))
        written.append(srcf.name)

    # The genome/ directory is a neighbour of the profile, and we create it ONLY when
    # the directory was taken by default. If a person gave their own path, climbing up
    # from it is not allowed: with `--dir /tmp/x` that would create /tmp/genome, and when
    # running from the source tree it would touch a repository nobody asked about.
    explicit = bool(target) or bool(os.environ.get("SCHOLION_PROFILE_DIR"))
    gsrc = core.templates_dir() / "genome" / "README.md"
    if gsrc.exists() and not explicit:
        gdir = core.repo_dir() / "genome"
        core.mkdir_private(gdir)
        gdst = gdir / "README.md"
        if not gdst.exists() or force:
            _write_private(gdst, gsrc.read_text(encoding="utf-8"))
            written.append("genome/README.md")
        else:
            skipped.append("genome/README.md")

    if not explicit:
        w, s = _ensure_layout(force)
        written += w
        skipped += s

    return {"ok": True, "dir": str(out), "mode": "templates",
            "written": written, "skipped": skipped}


# A short note in every folder of the layout. Not decoration: a person who opens an
# empty directory named `work` puts anything at all into it — and a month later there
# is no telling which of it is recomputable and which is the only copy.
# The layout is described in full in `docs/DATA-LAYOUT.md`.
_LAYOUT_README = ("raw", "raw/lab", "raw/sequencing", "raw/wearables", "raw/reference",
                  "work", "archive")


def _layout_readme(rel: str) -> str:
    """The note for one folder of the layout, in the language the command is running in."""
    return _t("layout.readme." + rel.replace("/", "_"))


def _ensure_layout(force: bool = False):
    """Create the data directory layout and put a note into every folder.

    Called only when the profile directory was taken by default: with an explicit
    `--dir` an outside directory must not be littered.

    External slots are left alone: if a person pointed `raw` at a disk that is
    currently disconnected, creating an empty folder at that path would silently
    «fix» the missing source — and the next run would report that there is no data
    instead of the honest «the source is not connected».
    """
    written, skipped = [], []
    cfg = core.source_config() or {}
    for rel in _LAYOUT_README:
        slot = rel.split("/")[0]
        if cfg.get(slot) or os.environ.get(f"SCHOLION_{slot.upper()}_DIR"):
            skipped.append(_t("store.slot_external", slot=rel))
            continue
        d = core.repo_dir() / rel
        core.mkdir_private(d)
        dst = d / "README.md"
        if dst.exists() and not force:
            skipped.append(f"{rel}/README.md")
            continue
        _write_private(dst, _layout_readme(rel))
        written.append(f"{rel}/README.md")
    return written, skipped


@_serialized
def write_goal_targets(proposals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Write proposed targets into `profile/health_goals.json`, keeping what is there.

    Three things this deliberately does NOT do.

    It does not overwrite a goal somebody has already written. A target the person
    set by hand is the strongest source there is — stronger than any guideline,
    because it is theirs — and a command that silently replaced it would be the
    same defect this whole feature exists to remove, only pointed the other way.
    Existing keys survive; only new ones are added, and the result says which.

    It does not invent a headline. The goal's wording is the person's to write,
    and a generated sentence in the first person («my goal is…») put into their
    file without asking is a small forgery.

    It records where each number came from, in the file. Six months later the
    reader has to be able to tell «my own best from 2023» from «what a cardiology
    society publishes», and a bare number cannot say which it is.
    """
    path = core.profile_dir() / "health_goals.json"
    data = core.read_profile_json(path) if path.exists() else {}
    existing = {t.get("label") or t.get("key"): t for t in (data.get("targets") or [])}

    added, kept = [], []
    for p in proposals or []:
        label = p.get("name") or p.get("key")
        if label in existing:
            kept.append(label)
            continue
        tgt = p.get("target") or {}
        cand = next((c for c in (p.get("candidates") or [])
                     if c.get("source") == p.get("proposed")), {})
        entry = {
            "label": label,
            "source": f"lab:{p['key']}",
            "target": f"{tgt.get('comparator', '')}{tgt.get('value', '')}",
            "best": (str(cand.get("observed", {}).get("date", "")) if cand.get("observed") else ""),
            # The provenance of the target, kept beside it rather than in a log.
            "_from": {"source": p.get("proposed"), "why": cand.get("why"),
                      "citation": cand.get("citation"), "caveat": p.get("caveat")},
        }
        (data.setdefault("targets", [])).append(entry)
        added.append(label)

    meta = data.setdefault("_meta", {})
    meta.setdefault("schema", core.PROFILE_SCHEMA)
    meta["written_by"] = "scholion goal-suggest"
    _write_private(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return {"path": str(path), "added": added, "kept": kept}
