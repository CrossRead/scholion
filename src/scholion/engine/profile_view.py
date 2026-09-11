"""The profile at a glance: load, overview, metrics summary.

Aggregates the other domains' top lines into one screen without owning any of
the underlying logic.
"""
from __future__ import annotations

from typing import Any, Dict
from .. import core
from .. import subject as _subject
from ..i18n import t as _t
from ._helpers import _recent, DISCLAIMER
from .labs import _latest, _trend, _flag_value, analyze_labs, suggest_tests
from .genomics import genome_status
from .lifestyle import _lifestyle_overview


# a convenient aggregate — a snapshot of the profile
def load_profile() -> Dict[str, Any]:
    return {
        "subject_id": core.profile_meta(core.pharmacogenomics()).get("subject_id"),
        "genome_gaps": core.genome_gaps(),
        "labs_markers": list(core.labs().get("markers", {}).keys()),
        "pgx_genes": sorted({g.get("gene") for g in core.pharmacogenomics().get("genotypes", [])}),
    }


def overview() -> Dict[str, Any]:
    """Summary for the main screen: red flags, counters, gaps."""
    labs = analyze_labs()
    tests = suggest_tests()
    # The overview is a current snapshot: only the markers measured within the last 12 months
    # (a sliding window from today). Older deviations are not shown on the main screen.
    red = [m for m in labs["markers"] if m["flag"] not in ("ok", "norange") and _recent(m.get("date"))]
    stale = sum(1 for m in labs["markers"] if m["flag"] not in ("ok", "norange") and not _recent(m.get("date")))
    return {
        "subject_id": core.profile_meta(core.pharmacogenomics()).get("subject_id"),
        "abnormal_count": len(red),
        "stale_abnormal_count": stale,
        "markers_total": labs["count"],
        # `high` and `low` are DIRECTIONS, not severities. Splitting the first screen by
        # them and labelling the halves «red flags» and «under observation» made a
        # ferritin of 13 against a floor of 20 the milder of the two — the direction read
        # as the seriousness. `flagged` is the whole current set, in one list, and the
        # two counts stay only as counts of a direction each.
        "synthetic": core.profile_is_synthetic(),
        # Who the data belong to, asked of the data rather than of the file
        # metadata: `synthetic` is a property of a file somebody wrote, `whose`
        # is a property of what is in it. They agree in a demonstration and in a
        # real profile; the case they disagreed in — a real measurement added to
        # a demonstration — is the one this field exists for, and is now refused
        # upstream rather than described here.
        "whose": _subject.profile_subject(),
        "flagged": red,
        "high_flags": [m for m in red if m["flag"] == "high"],
        "watch_flags": [m for m in red if m["flag"] == "low"],
        "suggestions_count": tests["count"],
        # The tile counted every pending suggestion while the block below it printed only
        # the `high` ones, so «2 tests suggested» sat above «nothing rises to priority».
        # One list feeds both now; priority orders it instead of filtering it.
        "pending_suggestions": [s for s in tests["suggestions"] if not s.get("done_recently")],
        "high_suggestions": [s for s in tests["suggestions"]
                             if s.get("priority") == "high" and not s.get("done_recently")],
        "genome_gaps": core.genome_gaps(),
        "genome": genome_status(),
        "medications_count": len(core.medications_json().get("medications", [])),
        "metrics": _metrics_overview(),
        "lifestyle": _lifestyle_overview(),
        # Computed and printed nowhere is the defect this project keeps finding
        # in itself, so it goes onto the first screen with everything else.
        "build": _build_freshness(),
        "disclaimer": DISCLAIMER(),
    }


def _build_freshness() -> Dict[str, Any]:
    from .sources import build_freshness
    try:
        return build_freshness()
    except Exception as exc:                                         # noqa: BLE001
        # The overview must not fall over on its own age line — but «unknown»
        # with nothing beside it is the same word a build with no journal
        # says, and a reader cannot tell the two apart. The reason travels.
        return {"status": "unknown", "reason": type(exc).__name__}


def _metrics_overview() -> Dict[str, Any]:
    ms = metrics_summary()
    filled = [m for m in ms["metrics"] if m["value"] is not None]
    watch = [{"name": m["name"], "value": m["value"], "unit": m["unit"], "flag": m["flag"]}
             for m in filled if m["flag"] in ("high", "low")]
    return {"bmi": ms.get("bmi"), "age": ms.get("age"),
            "filled_count": len(filled), "watch": watch}


def _device_rows() -> Dict[str, Dict[str, Any]]:
    """`{person metric key: {source, series, label, unit}}` — what a watch already
    measures out of what the person is otherwise asked to type in.

    Three things are deliberate here. The pairing is read from the shipped
    catalogue rather than from a table in this file, so there is one place where
    «the same quantity» is asserted. The series comes through
    `wearables.series`, which is the accessor that knows the file's shape — a
    second reader of that shape is exactly the defect this repairs. And a metric
    that MORE THAN ONE device reports is skipped rather than picked between: two
    watches do not measure resting heart rate the same way, and a row that
    silently switched device between two readings would show a step the person
    would take for a change in themselves.
    """
    from .. import wearables
    cat = (core.wearable_metrics().get("metrics") or {})
    blocks = dict(wearables.series(core.wearable_trends()))
    out: Dict[str, Dict[str, Any]] = {}
    for name, spec in cat.items():
        key = (spec or {}).get("person_metric")
        if not key:
            continue
        carry = {s: b for s, b in blocks.items() if name in (b.get("metrics") or {})}
        if len(carry) != 1:
            continue
        src, block = next(iter(carry.items()))
        months = (block.get("metrics") or {}).get(name) or {}
        series = sorted(({"date": str(mo), "value": float(v)}
                         for mo, v in months.items() if isinstance(v, (int, float))),
                        key=lambda p: p["date"])
        if series:
            out[key] = {"source": src, "series": series, "metric": name,
                        "label": spec.get("label"), "unit": spec.get("unit")}
    return out


def metrics_summary() -> Dict[str, Any]:
    """Personal health metrics: latest values, trends, flags + the BMI computation.

    Two stores answer for some of these numbers — what the person typed into
    metrics.json and what their watch recorded — and for a month the page read
    only the first. It said «steps 6000, below the target» from a single point
    somebody entered in July while the device series held August, and «sleep —»
    while the same file carried seventy-five months of it. Nothing was written
    wrongly; nothing joined the two.

    The rule is the newest measurement wins and the row says which store it came
    from, with a tie going to the hand-entered one: a monthly mean and a reading
    taken on a day are not the same statement, and the person made the second on
    purpose. Neither file is written to — this is a view.
    """
    data = core.metrics_json()
    prof = data.get("profile", {})
    dev = _device_rows()
    out = []
    latest_weight = None
    for k, m in data.get("metrics", {}).items():
        series = m.get("series") or []
        latest = _latest(series) if series else None
        d = dev.get(k)
        d_last = d["series"][-1] if d else None
        # Months against days: a monthly point is compared on its month, which is
        # what it is. Equal month → the hand-entered reading stands.
        take_device = bool(d_last) and (
            latest is None or str(d_last["date"])[:7] > str(latest["date"])[:7])
        shown = d_last if take_device else latest
        shown_series = d["series"] if take_device else series
        row = {"key": k, "name": m.get("name", k), "unit": m.get("unit", ""),
               "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high"),
               "direction": m.get("direction"),
               "value": shown["value"] if shown else None,
               "date": shown["date"] if shown else None,
               "flag": _flag_value(m, shown["value"], shown.get("censored")) if shown else "unknown",
               "trend": _trend(shown_series),
               "series": sorted(shown_series, key=lambda p: p["date"]),
               # Where the number on the card came from, and what the other store
               # holds — so a person who types a weight in can see the watch's
               # last month beside it rather than instead of it.
               "origin": ("device" if take_device else "manual" if shown else None),
               "device": ({"source": d["source"], "metric": d["metric"],
                           "value": d_last["value"], "date": d_last["date"]} if d_last else None),
               "manual": ({"value": latest["value"], "date": latest["date"]} if latest else None)}
        if k == "weight" and shown:
            latest_weight = shown["value"]
        out.append(row)
    out.sort(key=lambda r: (r["value"] is None, r["name"]))
    # BMI from the height + the latest weight
    bmi = None
    h = prof.get("height_cm")
    if h and latest_weight:
        try:
            bmi_val = round(latest_weight / (float(h) / 100) ** 2, 1)
            cat = _t("bmi.under" if bmi_val < 18.5 else "bmi.normal" if bmi_val < 25
                     else "bmi.over" if bmi_val < 30 else "bmi.obese")
            flag = "ok" if 18.5 <= bmi_val < 25 else ("low" if bmi_val < 18.5 else "high")
            bmi = {"value": bmi_val, "category": cat, "flag": flag}
        except Exception:
            bmi = None
    age = _age_from(prof)
    # The devices THIS build can read, so a face offering the choice offers
    # exactly those. A page carrying its own list is a page that goes stale the
    # day a third reader is added — and the validation on the write side already
    # comes from here, so the two would then disagree about what exists.
    from .. import wearables as _wear
    devices = [k["source"] for k in _wear.KINDS]
    # A VIEW of the profile, not the file. `sex` is normalised through the one
    # function that knows the spellings: the file may say `m`, because that is
    # what the demonstration writes and what a medical record's `gender` field
    # gives, while a face comparing the raw value against `male` then shows a
    # recorded sex as «—» and offers an empty box for a question already
    # answered. The stored file is untouched; anything wanting the raw value
    # reads metrics.json.
    view = dict(prof)
    view["sex"] = core.profile_sex()
    return {"status": "ok", "profile": view, "age": age, "bmi": bmi,
            "devices": devices,
            # Shown, never asked for: which reference panel a percentile is
            # computed against is determined from the genome, and `source` is
            # what lets a face say so instead of presenting it as a setting.
            "ancestry": core.ancestry(),
            "metrics": out, "disclaimer": DISCLAIMER()}


def _age_from(prof: Dict[str, Any]):
    """Age in whole years — `core.age_from`, kept under the old name for the
    callers in this file. The reader moved to core when the corridor rule began
    to need it too: two readers of the same two fields would drift."""
    return core.age_from(prof)
