"""Apply canonical measurement histories to the existing lifestyle card contract."""
from __future__ import annotations
from . import core
from .measurements import history, bmi_history, streams


def combine_lifestyle(out: list[dict], catalogue: dict) -> list[dict]:
    # Shared current values and histories, with source-specific comparisons.
    for name, spec in catalogue.items():
        person_key = spec.get("person_metric")
        if not person_key and name != "BMI":
            continue
        combined = bmi_history() if name == "BMI" else history(person_key)
        points, latest = combined["series"], combined["latest"]
        if not points:
            continue
        old = [m for m in out if m["key"] in (name, person_key)]
        source = latest["measurement_source"] if latest else None
        selected = next((m for m in old if m["source"] == source), None)
        # A current manually entered value must not inherit an older device's
        # score, smoothing, coverage or claim of a statistically qualified change.
        selected = dict(selected or {"key": name, "label": spec.get("label") or name,
            "group": spec.get("group") or "anthro", "direction": spec.get("direction"),
            "target_low": spec.get("target_low"), "target_high": spec.get("target_high"), "why": ""})
        if not latest or source == "recorded" or combined.get("derived"):
            selected.update(output_kind="derived_measurement" if combined.get("derived") else "recorded_measurement", first=None, first_date=None, value_smooth=None, status="none", score=None, trend=None,
                overall_delta=None, improving=None, trend_good=None, smooth=[], coverage=None,
                comparison={"eligible": False, "distinguishable": None, "reasons": ["source_specific_comparison_required"]})
        selected.update(key=name, value=latest["value"] if latest else None,
            date=latest["date"] if latest else None, source=None if source == "recorded" else source,
            unit=core.unit_label(combined["unit"]), series=points, combined_history=True,
            current_observation=latest, counts_toward_conclusions=bool(latest),
            aggregation=latest["aggregation"] if latest else None,
            record=latest["record"] if latest else None,
            also_measured_by=sorted({p["measurement_source"] for p in points} - {source, "recorded"}),
            measurement_series=[{"source": None if group[0]["measurement_source"] == "recorded" else group[0]["measurement_source"],
                "unit": core.unit_label(combined["unit"]), "aggregation": "measurement" if group[0]["aggregation"] == "observation" else group[0]["aggregation"],
                "series": group} for group in streams(points)])
        out = [m for m in out if m["key"] not in (name, person_key)]
        out.append(selected)
    for row in out:
        if row.get("source") is not None or row.get("combined_history"):
            continue
        observed = history(row["key"])
        latest = observed["latest"]
        if latest:
            row.update(series=observed["series"], value=latest["value"], date=latest["date"],
                       current_observation=latest, record=latest["record"], aggregation=latest["aggregation"],
                       combined_history=True, value_smooth=None, first=None, first_date=None,
                       score=None, status="none", trend=None, trend_good=None, improving=None, overall_delta=None)
    return out
