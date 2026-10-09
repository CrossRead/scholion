"""Source-bound indices, separate from Scholion's display heuristics."""
from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict

from .. import core, store
from ..i18n import lang, t


@core.in_reading
def fib4() -> Dict[str, Any]:
    """Latest complete collection stamp; never combine each analyte's latest value.

    A formula value is not a diagnosis. No cut-off is applied without the
    clinical context that the laboratory series cannot establish.
    """
    from pathlib import Path
    import json
    spec = json.loads((Path(__file__).resolve().parents[1] / "knowledge" /
                       "validated_indices.json").read_text(encoding="utf-8"))["fib4"]
    out: Dict[str, Any] = {"key": "fib4", "name": "FIB-4", "value": None, "date": None,
        "status": "missing", "inputs": [], "missing": [], "issues": [],
        "formula": spec["formula"], "sources": spec["sources"], "retrieved": spec["retrieved"],
        "population": t("fib4.population"), "endpoint": t("fib4.endpoint"),
        "horizon": t("fib4.horizon"), "scope_note": t("fib4.scope"),
        "interpretation": {"status": "withheld", "reason": t("fib4.context_missing")}}
    units = spec["units"]
    markers = core.labs().get("markers") or {}
    draws: Dict[str, Dict[str, list[Dict[str, Any]]]] = {}
    ignored = []
    for key in units:
        block = markers.get(key) or {}
        for point in block.get("series") or []:
            stamp = point.get("date")
            if not isinstance(stamp, str) or store.date_resolution(stamp) not in ("day", "stamp"):
                ignored.append(key)
                continue
            if point.get("date_source") not in ("form", "manual"):
                ignored.append(key)
                continue
            draws.setdefault(stamp, {}).setdefault(key, []).append(
                {**point, "unit": point.get("unit") or block.get("unit")})
    complete = [stamp for stamp, values in draws.items() if set(values) == set(units)]
    stamp = max(complete or draws, default=None)
    if stamp is None:
        out["missing"] = list(units)
        out["issues"] = [t("fib4.no_draw")]
        return out
    out["date"] = stamp
    selected = draws[stamp]
    if max(draws) != stamp:
        out["issues"].append(t("fib4.newer_partial", date=max(draws)))
    values: Dict[str, float] = {}
    invalid = False
    origins = {json.dumps(p.get("source"), sort_keys=True) for rows in selected.values()
               for p in rows if p.get("source")}
    if len(origins) > 1:
        invalid = True
        out["issues"].append(t("fib4.different_sources"))
    catalogue = core.lab_markers()["markers"]
    for key, required_unit in units.items():
        rows = selected.get(key) or []
        if not rows:
            out["missing"].append(key)
            continue
        row = rows[0]
        item = {"key": key, "name": core.marker_display(catalogue[key], lang()), "date": stamp,
                "value": row.get("value"), "unit": row.get("unit"), "source": row.get("source"),
                "date_source": row.get("date_source"), "required_unit": required_unit}
        out["inputs"].append(item)
        origin = row.get("source")
        wrong_source = isinstance(origin, dict) and (
            origin.get("specimen") not in (None, "blood", "serum", "plasma")
            or origin.get("draw_date") not in (None, stamp))
        if len(rows) != 1 or row.get("censored") or row.get("comparator") or wrong_source:
            invalid = True
            out["issues"].append(t("fib4.invalid_observation", marker=item["name"]))
            continue
        try:
            value = float(row["value"])
        except (ValueError, TypeError, KeyError):
            value = float("nan")
        if isinstance(row.get("value"), bool) or not math.isfinite(value) or value <= 0:
            invalid = True
            out["issues"].append(t("fib4.invalid_observation", marker=item["name"]))
            continue
        # All unit arithmetic uses the project's one conversion gateway.
        converted = core.convert_to_canonical(catalogue[key], row.get("unit") or "", value)
        if (not row.get("unit") or not converted.get("ok") or catalogue[key]["unit"] != required_unit
                or not math.isfinite(converted.get("value", float("nan")))
                or converted.get("value", 0) <= 0):
            invalid = True
            out["issues"].append(t("fib4.unit_unavailable", marker=item["name"]))
            continue
        values[key] = converted["value"]
        item["canonical_value"] = values[key]
        item["canonical_unit"] = required_unit
    profile = core.metrics_json().get("profile") or {}
    bad_age = False
    if profile.get("birth_date"):
        try:
            born = date.fromisoformat(str(profile["birth_date"]))
            bad_age = born.isoformat() != profile["birth_date"] or born.isoformat() > stamp[:10]
        except ValueError:
            bad_age = True
    elif profile.get("birth_year") is not None:
        year = profile["birth_year"]
        bad_age = (isinstance(year, bool) or not str(year).isdigit()
                   or not 1 <= int(year) <= int(stamp[:4]))
    age = core.age_from(profile, on=stamp) if not bad_age else None
    if bad_age:
        invalid = True
        out["issues"].append(t("fib4.invalid_age"))
    if age is None or age <= 0:
        out["missing"].append("age")
    else:
        out["age"] = age
        out["age_basis"] = "birth_date" if profile.get("birth_date") else "birth_year"
        if out["age_basis"] == "birth_year":
            out["issues"].append(t("fib4.age_estimated"))
        if age < spec["minimum_age_for_display"]:
            out["status"] = "not_applicable"
            out["issues"].append(t("fib4.too_young"))
            return out
        if age > 65:
            out["issues"].append(t("fib4.older_age"))
    if stamp[:10] > date.today().isoformat():
        invalid = True
        out["issues"].append(t("fib4.future_draw"))
    if ignored:
        out["issues"].append(t("fib4.ignored_dates"))
    if invalid or out["missing"]:
        out["status"] = "invalid" if invalid else "missing"
        return out
    assert age is not None
    try:
        value = age * values["ast"] / (values["platelets"] * math.sqrt(values["alt"]))
    except (ZeroDivisionError, OverflowError):
        value = float("nan")
    if not math.isfinite(value):
        out["status"] = "invalid"
        out["issues"].append(t("fib4.invalid_result"))
        return out
    out.update(status="computed", value=round(value, 3))
    return out
