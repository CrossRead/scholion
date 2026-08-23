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
        "disclaimer": DISCLAIMER(),
    }


def _metrics_overview() -> Dict[str, Any]:
    ms = metrics_summary()
    filled = [m for m in ms["metrics"] if m["value"] is not None]
    watch = [{"name": m["name"], "value": m["value"], "unit": m["unit"], "flag": m["flag"]}
             for m in filled if m["flag"] in ("high", "low")]
    return {"bmi": ms.get("bmi"), "age": ms.get("age"),
            "filled_count": len(filled), "watch": watch}


def metrics_summary() -> Dict[str, Any]:
    """Personal health metrics: latest values, trends, flags + the BMI computation."""
    data = core.metrics_json()
    prof = data.get("profile", {})
    out = []
    latest_weight = None
    for k, m in data.get("metrics", {}).items():
        series = m.get("series") or []
        latest = _latest(series) if series else None
        row = {"key": k, "name": m.get("name", k), "unit": m.get("unit", ""),
               "ref_low": m.get("ref_low"), "ref_high": m.get("ref_high"),
               "direction": m.get("direction"),
               "value": latest["value"] if latest else None,
               "date": latest["date"] if latest else None,
               "flag": _flag_value(m, latest["value"], latest.get("censored")) if latest else "unknown",
               "trend": _trend(series), "series": sorted(series, key=lambda p: p["date"])}
        if k == "weight" and latest:
            latest_weight = latest["value"]
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
    """Age in whole years, from whichever birth field the profile carries.

    Both are real. `birth_year` is what the command line and the page write;
    `birth_date` is what the demonstration profile and an imported medical
    record write, and reading only the first reported no age at all for either
    of those — the interface said «—» while the file held a date. Every other
    reader in this project already accepted both, which is precisely why the one
    that did not went unnoticed.
    """
    from datetime import date
    bd = str(prof.get("birth_date") or "").strip()
    today = date.today()
    if bd:
        try:
            y, m, d = (int(x) for x in bd.split("-")[:3])
            return today.year - y - ((today.month, today.day) < (m, d))
        except (ValueError, TypeError):
            pass
    try:
        return today.year - int(prof["birth_year"]) if prof.get("birth_year") else None
    except (ValueError, TypeError):
        return None
