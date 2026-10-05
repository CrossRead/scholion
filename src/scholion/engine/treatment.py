"""Recorded treatment events and explicitly dated monitoring plans."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from .. import core


def _day(value: Any) -> Optional[date]:
    """Only a recorded calendar day; a month is not the first of that month."""
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def treatment_timeline(today: Optional[date] = None) -> Dict[str, Any]:
    """Recorded starts beside observations, never a claim about treatment effect.

    A control is timed only by an explicit profile `monitoring_schedule` entry:
    `{marker, from, due, source}`. Free-text monitoring advice stays unparsed:
    converting it into a deadline would invent a prescription. A matching draw
    is recorded, not clinically assessed; an overdue row means only that this
    profile has no matching observation in the recorded window.
    """
    from .. import store
    now = today or date.today()
    markers = core.labs().get("markers") or {}
    known = core.lab_markers().get("markers") or {}
    events: List[Dict[str, Any]] = []
    undated: List[Dict[str, Any]] = []
    controls: List[Dict[str, Any]] = []
    for key, block in markers.items():
        label = core.marker_name({**block, "key": key})
        for point in block.get("series") or []:
            stamp = str(point.get("date") or "")
            if store.date_resolution(stamp) is None:
                continue
            events.append({"kind": "measurement", "date": stamp, "marker": key,
                           "name": label, "value": point.get("value"),
                           "comparator": point.get("comparator"),
                           "unit": point.get("unit") or block.get("unit"),
                           "source": point.get("source"),
                           "date_source": point.get("date_source")})
    for index, med in enumerate(store.list_medications()):
        base = {"medication_index": index, "name": med.get("name"),
                "dose": med.get("dose"), "current": med["current"],
                "source": "medications.json"}
        start = str(med.get("start_date") or "")
        event = {**base, "kind": "prescription_start", "date": start or None}
        if store.date_resolution(start) is not None:
            events.append(event)
        else:
            undated.append({**event, "reason": "start_not_recorded" if not start else "invalid_start"})
        schedule = med.get("monitoring_schedule")
        if schedule is None:
            if med.get("monitoring"):
                controls.append({**base, "status": "unresolved", "reason": "unstructured_plan"})
            continue
        if not isinstance(schedule, list):
            controls.append({**base, "status": "unresolved", "reason": "invalid_plan"})
            continue
        for item in schedule:
            plan = item if isinstance(item, dict) else {}
            marker = plan.get("marker")
            begin, due = _day(plan.get("from")), _day(plan.get("due"))
            control = {**base, "marker": marker, "from": plan.get("from"),
                       "due": plan.get("due"), "plan_source": plan.get("source"),
                       "status": "unresolved", "reason": "invalid_plan"}
            if (not isinstance(marker, str) or marker not in known or not begin or not due
                    or begin > due or not isinstance(plan.get("source"), str)
                    or not plan["source"].strip()):
                controls.append(control)
                continue
            observed = sorted({str(p.get("date")) for p in (markers.get(marker) or {}).get("series") or []
                               if store.date_resolution(str(p.get("date") or "")) in ("day", "stamp")
                               and p.get("date_source") == "form"
                               and begin <= date.fromisoformat(str(p["date"])[:10]) <= now
                               and p.get("value") is not None})
            control.update({"reason": None, "observed_dates": observed,
                            "status": ("inactive" if not med["current"] else "recorded" if observed
                                       else "overdue" if due < now else "scheduled")})
            controls.append(control)
    return {"as_of": now.isoformat(), "events": sorted(events, key=lambda e: (e["date"], e["kind"])),
            "undated": undated, "controls": controls,
            "overdue": [c for c in controls if c["status"] == "overdue"],
            "interpretation": "recorded_events_only", "response_assessed": False}
