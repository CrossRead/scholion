"""Writing into the profile (editing from the UI): adding lab points and prescriptions.

Writes ONLY into profile/ (labs.json, medications.json) — patient data. The code and the
knowledge base are left untouched. After a write it resets the core cache.
"""
from __future__ import annotations
import datetime as _dt
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import core
from . import subject as _subj
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
def mark_brief_reviewed(block: str) -> Dict[str, Any]:
    """Record that the wording of one brief block was read against today's data.

    `reviewed` is a date a person put there, and the engine compares it with the
    newest measurement the block watches. The comparison worked; the date had no
    way to be written from anywhere in the product, so the flag it drives could
    only ever go up. A signal that cannot be lowered stops being read at all —
    and this one sat at the top of the tab.

    Nothing about the TEXT changes here. The claim being recorded is exactly the
    one the button makes: somebody looked at this wording beside the newer numbers
    and it still says what they mean.
    """
    block = (block or "").strip()
    src = core.profile_dir() / "lifestyle_brief.json"
    if not src.exists():
        return {"ok": False, "error": _t("store.brief_absent")}
    data = json.loads(src.read_text(encoding="utf-8"))
    blocks = data.get("blocks") or []
    hit = next((b for b in blocks if str(b.get("id")) == block), None)
    if hit is None:
        return {"ok": False, "error": _t("store.brief_no_block", id=block)}
    from datetime import date as _date
    hit["reviewed"] = _date.today().isoformat()
    _write_json(src, data)
    core.reset_cache()
    return {"ok": True, "block": block, "reviewed": hit["reviewed"]}


@_serialized
def set_genome_vcf(path: str) -> Dict[str, Any]:
    """Record WHICH file in the genome folder is the person's own reads.

    Only ever asked when the folder holds more than one candidate, and only the
    person can answer it: the files are all theirs, all called from their reads,
    and which one is the genome rather than an extraction from it is not
    something a program may decide by size or by name. Passing an empty path
    clears the choice.

    The file is checked for existence and for being a `.vcf.gz`, and nothing
    else: a stricter check here would be this module deciding the very question
    it is recording somebody else's answer to.
    """
    cfgp = core.profile_dir() / "sources.json"
    cfg = json.loads(cfgp.read_text(encoding="utf-8")) if cfgp.exists() else {}
    cfg.setdefault("_meta", {"purpose": _t("store.sources_purpose")})
    raw = (path or "").strip()
    if not raw:
        # Clearing a choice nobody made writes nothing. A settings file that
        # appears the first time somebody asks a question is a file the next
        # reader has to explain, and the demo profile grew one from a test.
        if not cfgp.exists() and "genome_vcf" not in cfg:
            return {"ok": True, "genome_vcf": None}
        cfg.pop("genome_vcf", None)
        _write_json(cfgp, cfg)
        core.reset_cache()
        return {"ok": True, "genome_vcf": None}
    fp = Path(raw).expanduser()
    if not fp.exists() or not fp.is_file():
        return {"ok": False, "error": _t("store.genome_file_not_found", path=fp)}
    if not str(fp).endswith(".vcf.gz"):
        return {"ok": False, "error": _t("store.genome_not_a_vcf", path=fp.name)}
    cfg["genome_vcf"] = str(fp)
    _write_json(cfgp, cfg)
    core.reset_cache()
    return {"ok": True, "genome_vcf": str(fp)}


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


def _subject_gate(subject: Optional[str]) -> tuple:
    """Check whose datum this is, and let the person's own take the profile.

    Task 102. Two answers come back: the refusal, if the word is not one of
    `subject.SUBJECTS`, and the report of an erase, if a demonstration profile
    has just been claimed by its first real measurement.

    The order matters and is the whole point: the erase happens BEFORE the file
    is read, so the new datum is written into an empty profile rather than
    appended to a fictional person's series. Doing it the other way round is the
    defect this was written after — a real glucose value joining a generated
    series, in a file that went on declaring itself synthetic.
    """
    if subject is not None and not _subj.valid(subject):
        return _subj.unknown_error(subject), None
    if subject != "owner":
        return None, None
    claim = _subj.claim_for_owner()
    return None, (claim if claim.get("claimed") else None)


#: Where the DATE of a point came from. A closed vocabulary, because an open one
#: is not a vocabulary: a value nobody declared would read as «we know», which is
#: the assumption this field exists to remove.
#:
#: Task 100. Task 84 taught the reader to take a date from three places — the
#: page, an «Ordered Date» four lipid panels print INSTEAD of a draw date, and
#: the file name — and printed its caveat once, at ingest, after which it was
#: gone. In the series a point dated by the day the tests were ordered was then
#: indistinguishable from one dated by the draw. The project's own argument for
#: refusing an ambiguous date is that a point filed under the wrong month joins a
#: series and moves a trend; having refused the ambiguous ones, it went on to
#: accept the approximate ones in silence.
#: The three resolutions a point of a series may carry, and why there are three.
#:
#: `YYYY-MM` is a month; `YYYY-MM-DD` is a day; `YYYY-MM-DDTHH:MM` is a draw at a
#: named time. The third is not sloppiness and must not be «unified away»: blood
#: drawn before a procedure and again after it is TWO measurements on one day, and
#: with a key no finer than the day the second one could only be recorded as a
#: discrepancy with the first. `ingest_labs` keeps the clock time deliberately for
#: exactly that reason, and `set_draw_context` finds such a pair by looking for
#: stamps longer than a day.
#:
#: What was missing was not a format. It was a GATE: this docstring promised two
#: resolutions while the loader wrote three, and nothing at all checked the string,
#: so «вчера», an empty string or `2026-13-45` would have become a key of the
#: series and been sorted and charted alongside real dates.
DATE_SHAPES = ("YYYY-MM", "YYYY-MM-DD", "YYYY-MM-DDTHH:MM")

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


def date_resolution(date: str) -> Optional[str]:
    """`month`, `day`, `stamp` — or ``None`` when this is not a date at all.

    The shape is checked AND the value: `2026-13-45` has the shape of a day and is
    not one. A calendar is the only thing that can answer that, so one is asked.
    """
    d = (date or "").strip()
    try:
        if _MONTH_RE.match(d):
            _dt.date(int(d[:4]), int(d[5:7]), 1)
            return "month"
        if _DAY_RE.match(d):
            _dt.date(int(d[:4]), int(d[5:7]), int(d[8:10]))
            return "day"
        if _STAMP_RE.match(d):
            _dt.datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), int(d[11:13]), int(d[14:16]))
            return "stamp"
    except ValueError:
        return None
    return None


def _holds(outer: str, inner: str) -> bool:
    """Whether the period of `outer` holds the period of `inner` — or is it.

    THE one comparison of periods, for every resolution the series can carry.
    A month holds its days and their draws, a day holds its draws, and a period
    holds itself. Every date the gate lets through is canonical and fixed-width,
    so one period holds another exactly when its string is a prefix of the
    other's: `2025-12` of `2025-12-20` of `2025-12-20T07:30`. Two days of one
    month, or two draws of one day, are not nested — neither is a prefix of the
    other — and that is what makes them two measurements.

    Task 144. Task 128 wrote the same-draw rule for a day and its stamp and
    compared the first ten characters; a month has seven, so the shape older
    imports wrote — `2025-12` — was the same period as nothing, and a re-import
    of one monthly folder added 254 points where it should have replaced them.
    Written once, so that a fourth resolution cannot be half-covered the same
    way. Anything that is not a date holds nothing and is held by nothing.
    """
    a, b = (outer or "").strip(), (inner or "").strip()
    if date_resolution(a) is None or date_resolution(b) is None:
        return False
    return b.startswith(a)


def _mixed_resolution(series: List[Dict[str, Any]], date: str) -> List[str]:
    """Points already in this series that cover the same period at another resolution.

    This is the harm the mixed granularity actually does, and it is not the
    granularity itself: a month point and a dated point for the same month are ONE
    measurement standing in the series twice. Both may be legitimate — a
    hand-entered month from years ago and a form loaded today — so this is
    reported, not refused. What must not happen is that it happens quietly.

    Since `_points_this_write_replaces` resolves such a pair at every resolution,
    what reaches this list is only the pair it cannot resolve: a bare month or
    day arriving against two draws inside it — two measurements, and a point
    that names neither.
    """
    if date_resolution(date) is None:
        return []
    same = []
    for pt in series or []:
        other = str(pt.get("date") or "")
        if other != date and (_holds(other, date) or _holds(date, other)):
            same.append(other)
    return sorted(same)


def _points_this_write_replaces(series: List[Dict[str, Any]], date: str) -> List[Dict[str, Any]]:
    """The points a write dated `date` stands in for — the same period, at any resolution.

    Task 128. A panel entered by hand as `2026-09-03` and then re-imported from
    the form, which prints the draw hour, arrived as `2026-09-03T08:22`. The
    store replaced a point only on an exact match of the string, so the second
    write joined the series beside the first: 54 markers, each with two points
    of one draw, values identical. Nothing failed. The series grew, the engine's
    «previous point» became the same draw, and the mixed-resolution report —
    which did see it — was a report, not a rule.

    Task 144. The rule written for that pair compared days, and a month is not
    a day: `2025-12` against `2025-12-20T07:30` — the shape older imports wrote
    against the shape a form prints — went back to the exact-string rule, and
    one re-imported folder gave 251 markers two points of one draw. Closed green
    the first time because the guard covered only the day.

    So the rule, in one place for every path that writes a point: the write
    stands in for every point whose period holds its own — the month or the day
    its draw belongs to — and, when it is the coarser one, for the finer points
    inside its period provided they are ONE draw: a day and its stamp, a month
    and the one day in it. The finer date wins whichever order the two writes
    came in (the caller applies that — this only says WHICH points go). The
    closest match goes first in the list, so a caller carrying fields over takes
    them from it.

    What this deliberately does not do: a bare day arriving against two draws of
    that day, or a bare month against two days of that month, cannot say which
    of them it is, and choosing one would be a guess about somebody's results.
    Those stay, and `_mixed_resolution` reports them.
    """
    exact = [pt for pt in series or [] if pt.get("date") == date]
    if date_resolution(date) is None:
        return exact
    holding, inside = [], []
    for pt in series or []:
        other = str(pt.get("date") or "")
        if other == date:
            continue
        if _holds(other, date):
            holding.append(pt)
        elif _holds(date, other):
            inside.append(pt)
    # The finer points inside this period are one draw only when each holds the
    # next — so the finest of them holds every other. Two that neither holds
    # are two draws, and the write names neither: it replaces none of them.
    finest = max((str(pt.get("date") or "") for pt in inside), key=len, default="")
    if any(not _holds(str(pt.get("date") or ""), finest) for pt in inside):
        inside = []
    # Stable: the exact match has distance zero and stays first.
    return sorted(exact + holding + inside,
                  key=lambda pt: abs(len(str(pt.get("date") or "")) - len(date)))


DATE_SOURCES = {
    "form":       "the draw date printed on the form itself",
    "ordered":    "a date the form prints for the ORDER or the receipt, not the draw",
    "filename":   "the file name — what somebody called the file, not what the form says",
    "manual":     "entered by the person",
    "unrecorded": "written before the source of the date was recorded",
}
#: The two that are not the draw and not the person's own word. Everything shown
#: about such a point carries the caveat.
DATE_APPROXIMATE = ("ordered", "filename")


def add_lab_point(marker: str, date: str, value: float, *, name: Optional[str] = None,
                  unit: Optional[str] = None, ref_low: Optional[float] = None,
                  ref_high: Optional[float] = None, direction: Optional[str] = None,
                  censored: Optional[str] = None, new: bool = False,
                  date_source: Optional[str] = None,
                  subject: Optional[str] = None) -> Dict[str, Any]:
    """Add/update a marker point in labs.json.

    The date is one of `DATE_SHAPES` — a month, a day, or a day with the clock
    time of the draw — and anything else is refused rather than stored as written.
    This docstring used to promise two of the three while the laboratory loader
    deliberately wrote the third, and nothing checked the string at all.

    censored — the censoring sign of the result, if the lab printed not a number but a
    boundary: "<" for «less than 10^4» / «<0.4 U/mL», ">" for «more than 10^8». The value
    itself is stored AT THE BOUNDARY (otherwise there is nothing to build the series from),
    while the engine needs the sign so that «less than 10^5» against a lower limit of 10^5
    reads as BELOW the reference range, not as «exactly at the edge, all is well».

    subject — whose measurement this is, one of `subject.SUBJECTS`. `"owner"`
    means the person whose profile this is, and it CLAIMS the profile: a
    demonstration lying in it is erased first, because two people in one profile
    give conclusions about neither. Omitting it writes no mark at all, and the
    point is then read as belonging to whoever the file belongs to —
    `tests/test_a_datum_says_whose_it_is.py` walks every call in the tree and
    requires the argument outright, so silence is a safety net rather than a
    habit.

    date_source — where the DATE came from, one of `DATE_SOURCES`. Omitting it is
    not «the form»: it is stored as `unrecorded`, because a caller that did not
    say cannot be assumed to have known. `tests/test_a_point_says_where_its_date_came_from.py`
    walks every call in the tree and requires the argument outright, so the honest
    default is a safety net rather than a habit.
    """
    err, claimed = _subject_gate(subject)
    if err:
        return err
    if date_source is not None and date_source not in DATE_SOURCES:
        # An unknown value would travel into the series and be rendered as if it
        # meant something. Refusing here is cheaper than deciding later what an
        # undeclared word was supposed to say.
        return {"ok": False, "error": _t("store.date_source_unknown",
                                         value=str(date_source),
                                         accepted=", ".join(sorted(DATE_SOURCES)))}
    if not marker or not date:
        return {"ok": False, "error": _t("store.need_marker_date")}
    if date_resolution(date) is None:
        # Refused rather than stored as written. A string that is not a date still
        # sorts, still charts and still reads as a point — which is worse than a
        # rejected write, because nothing downstream can tell it from a real one.
        return {"ok": False, "error": _t("store.date_not_a_date", date=str(date),
                                         accepted=", ".join(DATE_SHAPES))}
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
    # ── one point per draw ───────────────────────────────────────────────────
    # Replacing by the exact string was the rule, and it let a hand-entered day
    # and the same form's stamped re-import stand side by side; the rule that
    # followed compared days, and let a monthly point and the same form's stamp
    # do the same. The write now stands in for every point of the same period
    # at any resolution, and the finer date wins: the clock time on the form is
    # knowledge, and a month or a day entered before the form was read is not a
    # reason to throw it away.
    gone = _points_this_write_replaces(series, date)
    requested = date
    finest = max((str(pt.get("date") or "") for pt in gone), key=len, default=date)
    date_kept_from_old = len(finest) > len(date)
    if date_kept_from_old:
        date = finest
    series[:] = [pt for pt in series if not any(pt is g for g in gone)]
    mixed = _mixed_resolution(series, date)
    pt: Dict[str, Any] = {"date": date, "value": value,
                          "date_source": date_source or "unrecorded"}
    if subject:
        pt[_subj.FIELD] = subject
    if censored in ("<", ">"):
        pt["censored"] = censored
    # The corridor PRINTED ON THIS FORM travels with the point (task 142). It
    # used to live only on the marker, which keeps the FIRST range it met and
    # is not rewritten by later forms: a September draw was then judged by a
    # range recorded in December, or by one entered by hand. A draw's own
    # reference interval is a fact about that draw. The marker-level range
    # stays as it is — the first known — for display and for the callers that
    # read it.
    if ref_low is not None:
        pt["ref_low"] = ref_low
    if ref_high is not None:
        pt["ref_high"] = ref_high
    # What the old point knew and this write did not say travels with the
    # replacement: `context`, `source`, `draw_context` — provenance somebody
    # wrote down once. Every re-import used to erase it, because a replacement
    # was a fresh dict. The date's own source follows the date: when the old
    # stamp is the one kept, the old point is where that stamp came from. The
    # censoring sign is NOT carried: it describes the number, and the number is
    # this write's — a «<0.4» re-entered as a measured 0.35 must not keep the «<».
    for old in gone:
        for field, kept in old.items():
            # …nor the old point's corridor: a form that printed no range must
            # not be shown as having printed the previous form's.
            if field not in ("date_source", "censored", "ref_low", "ref_high"):
                pt.setdefault(field, kept)
    if date_kept_from_old:
        pt["date_source"] = next((old.get("date_source") for old in gone
                                  if str(old.get("date")) == date), None) or pt["date_source"]
    series.append(pt)
    series.sort(key=lambda pt: pt["date"])
    _write_json(p, data)
    core.reset_cache()
    out = {"ok": True, "marker": marker, "points": len(series)}
    # Every date this write folded into one point that is not the date the point
    # now carries — the old points' dates, and the caller's own when the finer
    # one already in the series won.
    replaced = ({str(g.get("date") or "") for g in gone} | {requested}) - {date}
    if replaced:
        # Named in the result: a re-import that quietly swallowed a hand entry
        # would be the mirror image of the defect above.
        out["replaced"] = sorted(replaced)
        out["date"] = date
    if mixed:
        # Named in the result, so the loader that wrote the point can print it and
        # the person can decide which of the two is the measurement.
        out["resolution_mixed"] = mixed
    if claimed:
        out["claimed"] = claimed
    return out


#: What a re-add keeps from the entry already there unless the caller gives
#: it. `status` is the one that matters: a stopped drug re-added for its dose
#: used to come back current, silently, and the interaction check compared
#: against it again. The other two are history the writers here cannot set.
MEDICATION_FIELDS_KEPT = ("status", "start_date", "monitoring")


@_serialized
def add_medication(name: str, dose: str = "", note: str = "", *,
                   status: Optional[str] = None,
                   subject: Optional[str] = None) -> Dict[str, Any]:
    """Add a prescription to medications.json (an editable list).

    `status` is written only when given: an entry with no status is «no status
    recorded», which the checks treat as current and say so. Re-adding a name
    MERGES into the entry that is there — dose and note replaced when given,
    the fields in `MEDICATION_FIELDS_KEPT` kept when not — and the answer says
    the entry was replaced and what it kept, so that a re-add is never a quiet
    reset.

    `subject` as in `add_lab_point`: a prescription is a fact about a person too,
    and a real one written into the demonstration would be read beside invented
    laboratory values.
    """
    if not name:
        return {"ok": False, "error": _t("store.need_name")}
    err, claimed = _subject_gate(subject)
    if err:
        return err
    p = _path("medications.json")
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"medications": []}
    meds: List[Dict[str, str]] = data.setdefault("medications", [])
    entry: Dict[str, Any] = {"name": name.strip(), "dose": dose.strip(), "note": note.strip()}
    if status is not None and str(status).strip():
        entry["status"] = str(status).strip()
    if subject:
        entry[_subj.FIELD] = subject
    # dedup by name (case-insensitive): adding again UPDATES the entry rather than
    # breeding duplicates — otherwise the interaction/class logic over prescriptions breaks
    replaced, kept = False, []
    for i, m in enumerate(meds):
        if m.get("name", "").strip().lower() == entry["name"].lower():
            merged = dict(m)
            merged["name"] = entry["name"]
            for field in ("dose", "note"):
                if entry[field]:
                    merged[field] = entry[field]
            if "status" in entry:
                merged["status"] = entry["status"]
            if subject:
                merged[_subj.FIELD] = subject
            kept = [f for f in MEDICATION_FIELDS_KEPT if f in m and f not in entry]
            meds[i] = merged
            replaced = True
            break
    if not replaced:
        meds.append(entry)
    _write_json(p, data)
    core.reset_cache()
    out: Dict[str, Any] = {"ok": True, "count": len(meds), "updated": replaced}
    if replaced:
        out["replaced"] = entry["name"]
        if kept:
            out["kept"] = ", ".join(kept)
    if claimed:
        out["claimed"] = claimed
    return out


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


def list_medications() -> List[Dict[str, Any]]:
    """The regimen as written, and beside each entry whether the checks USE it.

    `current` is computed here, by the one rule in `core`, so that every listing
    — the command, the page, the assistant's context — marks a stopped entry
    the same way instead of each deciding, or not deciding, on its own.
    """
    return [{**m, "current": core.is_active_medication(m)}
            for m in core.medications_json().get("medications", [])]


# ---- personal health metrics (metrics.json) ------------------------------
@_serialized
def add_metric_point(metric: str, date: str, value: float, *, name: Optional[str] = None,
                     unit: Optional[str] = None, ref_low: Optional[float] = None,
                     ref_high: Optional[float] = None, direction: Optional[str] = None,
                     subject: Optional[str] = None) -> Dict[str, Any]:
    """Add/update a health metric point in metrics.json (replacing the point of the same date).

    `subject` as in `add_lab_point`.
    """
    if not metric or not date:
        return {"ok": False, "error": _t("store.need_metric_date")}
    err, claimed = _subject_gate(subject)
    if err:
        return err
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
    point: Dict[str, Any] = {"date": date, "value": value}
    if subject:
        point[_subj.FIELD] = subject
    series.append(point)
    series.sort(key=lambda pt: pt["date"])
    _write_json(p, data)
    core.reset_cache()
    out = {"ok": True, "metric": metric, "points": len(series)}
    if claimed:
        out["claimed"] = claimed
    return out


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
    # `wearable_primary` is the same kind of fact again: which device answers
    # where two of them measured the same thing. The engine cannot derive it, and
    # choosing for the person would make a chart depend on which export was
    # loaded last rather than on them.
    # A value that cannot mean anything is refused rather than stored. Until now
    # this wrote whatever it was handed: `--ancestry EURO` went in, and every
    # polygenic percentile afterwards was computed against a reference
    # population that does not exist — printed as an ordinary number, with the
    # caveat about a DEFAULT population suppressed, because a value was set.
    # Nothing downstream could tell. The web face validated the device and
    # nothing else, so the two faces disagreed about what was acceptable.
    from . import wearables as _wear
    if fields.get("ancestry") and fields["ancestry"] not in core.ANCESTRIES:
        return {"ok": False, "error": _t("store.unknown_ancestry",
                                         value=fields["ancestry"],
                                         accepted=", ".join(core.ANCESTRIES))}
    known_devices = {k["source"] for k in _wear.KINDS} | {core.NO_WEARABLE}
    if fields.get("wearable_primary") and fields["wearable_primary"] not in known_devices:
        return {"ok": False, "error": _t("wearables.unknown_device",
                                         name=fields["wearable_primary"])}
    # A sex that is BEING WRITTEN is written in the spelling the rest of the
    # project reads. The file has always been allowed to say `m` — a medical
    # record's `gender` and the demonstration both do, and `profile_sex()`
    # accepts it; what nothing accepted was a third spelling arriving from a
    # face and matching neither list.
    #
    # Only the value being written. Normalising whatever the file already held
    # would rewrite a field nobody touched: set a height, and the sex recorded
    # years ago silently changes its spelling. A writer that edits what it was
    # not asked about is the shape of defect this project keeps finding.
    fields = dict(fields)
    if fields.get("sex"):
        normalised = core.profile_sex_of(fields["sex"])
        if not normalised:
            return {"ok": False, "error": _t("store.unknown_sex", value=fields["sex"])}
        fields["sex"] = normalised
    for k in ("sex", "birth_year", "height_cm", "ancestry", "wearable_primary"):
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


# ---- targets set by a clinician (clinician_targets.json) -----------------
#
# Task 170. The product knew two kinds of «normal»: the corridor printed on the
# form, which travels with each point, and the person's own goal for their
# metrics. A third kind had nowhere to live — the figure a treating clinician
# is steering toward at this stage of treatment, which sits INSIDE the
# laboratory corridor more often than not. On the thyroid axis four markers out
# of four were in range, the system printed calm, and the clinician was at the
# same time leading toward TSH 1–2 while the person's 18.6 stood above their
# free-T4 target of 16.7. The product was not wrong; it was silent about the
# one number the treatment is run by.
#
# A target is ENTERED, never derived: this module proposes no figure and the
# engine computes none. Provenance is mandatory rather than polite — who set it
# and when — because a target without an author reads back later as the
# product's own, which is the one thing it must never be.

TARGET_SOURCE = "clinician"


def _target_spec(marker: str) -> Dict[str, Any]:
    return core.lab_markers().get("markers", {}).get(marker) or {}


@_serialized
def set_clinician_target(marker: str, *, low: Optional[float] = None,
                         high: Optional[float] = None, value: Optional[float] = None,
                         unit: Optional[str] = None, set_by: str = "", set_on: str = "",
                         note: str = "", subject: Optional[str] = None) -> Dict[str, Any]:
    """Record the target a clinician set for one marker; a second call replaces it.

    `low`/`high` are the bounds the clinician named, `value` the single figure
    when that is what was said («free T3 5.0»). At least one of the three is
    required, and a figure is stored as given: whether 16.8 counts as «at 16.7»
    is the clinician's tolerance to state as bounds, not this function's to
    assume. `set_by` and `set_on` are refused when absent, each by name.

    The unit is converted to the marker's canonical one exactly as
    `add_lab_point` converts a value, and for the same reason: the number is
    later compared with a series stored in that unit, and a target of 95 mg/dL
    beside a glucose series in mmol/L would read as far above every point.

    `subject` as in `add_lab_point`: a target relayed by the owner claims the
    profile, so a demonstration is erased before a real person's frame of
    treatment is written into it.
    """
    err, claimed = _subject_gate(subject)
    if err:
        return err
    if not (marker or "").strip():
        return {"ok": False, "error": _t("store.target_need_marker")}
    set_by = (set_by or "").strip()
    if not set_by:
        return {"ok": False, "error": _t("store.target_needs_set_by")}
    if date_resolution(set_on or "") != "day":
        return {"ok": False, "error": _t("store.target_needs_set_on", value=str(set_on or ""))}
    bounds: Dict[str, Optional[float]] = {}
    for name, raw in (("low", low), ("high", high), ("value", value)):
        if raw is None or raw == "":
            continue
        try:
            bounds[name] = float(raw)
        except (TypeError, ValueError):
            return {"ok": False, "error": _t("store.value_not_number")}
    if not bounds:
        return {"ok": False, "error": _t("store.target_needs_bound")}
    if "low" in bounds and "high" in bounds and bounds["low"] > bounds["high"]:
        return {"ok": False, "error": _t("store.target_low_above_high",
                                         low=f"{bounds['low']:g}", high=f"{bounds['high']:g}")}

    # The same name gate as a lab point: a target filed under a spelling the
    # dictionary does not know would stand beside no series at all, and nothing
    # would ever say so.
    res = core.resolve_marker(marker)
    if not res.get("key"):
        cands = ", ".join(f'{c["key"]} ({c["name"]})' for c in res.get("candidates") or [])
        return {"ok": False,
                "error": _t("store.target_marker_unknown", marker=marker,
                            did_you_mean=cands or _t("store.no_candidates")),
                "candidates": res.get("candidates") or []}
    marker = res["key"]

    spec = _target_spec(marker)
    known = bool(spec.get("unit"))
    if known:
        if not unit:
            return {"ok": False, "error": _t("store.target_unit_required", marker=marker,
                                             accepted=", ".join(core._accepted_units(spec)))}
        # Every figure converts by the unit it was GIVEN in; the canonical name
        # replaces it only once all of them have. Switching after the first
        # bound converted the second by a factor of one — 72–90 mg/dL became
        # 3.99–90 — which is exactly the mixed-scale corridor this gate exists
        # to refuse.
        canonical = unit
        for name, raw in list(bounds.items()):
            r = core.convert_to_canonical(spec, unit, raw)
            if not r.get("ok"):
                return {"ok": False, "error": _t("store.unit_not_accepted", marker=marker,
                                                 unit=unit,
                                                 accepted=", ".join(r.get("accepted") or []))}
            bounds[name] = r["value"]
            canonical = r.get("canonical") or unit
        unit = canonical

    p = core.profile_dir() / "clinician_targets.json"
    data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {
        "_meta": {"what": _t("store.targets_what")}, "targets": []}
    before = [tg for tg in (data.get("targets") or []) if tg.get("marker") == marker]
    entry: Dict[str, Any] = {"marker": marker, **bounds, "unit": unit or "",
                             "set_by": set_by, "set_on": set_on,
                             "source": TARGET_SOURCE}
    if (note or "").strip():
        entry["note"] = note.strip()
    if subject:
        entry[_subj.FIELD] = subject
    data["targets"] = [tg for tg in (data.get("targets") or []) if tg.get("marker") != marker]
    data["targets"].append(entry)
    data["targets"].sort(key=lambda tg: tg.get("marker") or "")
    _write_json(p, data)
    core.reset_cache()
    out: Dict[str, Any] = {"ok": True, "marker": marker, "target": entry,
                           "replaced": bool(before)}
    if claimed:
        out["claimed"] = claimed
    return out


@_serialized
def remove_clinician_target(marker: str) -> Dict[str, Any]:
    """Withdraw the target recorded for a marker. The series and its corridor stay."""
    p = core.profile_dir() / "clinician_targets.json"
    if not p.exists():
        return {"ok": False, "error": _t("store.no_targets_file")}
    res = core.resolve_marker(marker or "")
    key = res.get("key") or (marker or "").strip()
    data = json.loads(p.read_text(encoding="utf-8"))
    kept = [tg for tg in (data.get("targets") or []) if tg.get("marker") != key]
    removed = len(data.get("targets") or []) - len(kept)
    if not removed:
        return {"ok": False, "error": _t("store.target_none_for", marker=key)}
    data["targets"] = kept
    _write_json(p, data)
    core.reset_cache()
    return {"ok": True, "marker": key, "removed": removed}


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
                 demo: bool = False, subject: Optional[str] = None) -> Dict[str, Any]:
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
    if subject and subject != "owner":
        # A profile laid out FOR a published reference sample says so in every
        # file, or the subject gate reads the empty templates as the owner's
        # and refuses the reference genome beside them — which is what the
        # demo fetcher's own recipe ran into on 13.09.2026.
        if not _subj.valid(subject):
            return _subj.unknown_error(subject)
        for name in written:
            fp = out / name
            if fp.suffix != ".json":
                continue
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                meta = data.get("_meta")
                if not isinstance(meta, dict):
                    meta = {}
                    data = {"_meta": meta, **data}
                meta[_subj.FIELD] = subject
                _write_private(fp, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

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

    return {"ok": True, "dir": str(out), "mode": "templates", "subject": subject or "owner",
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
