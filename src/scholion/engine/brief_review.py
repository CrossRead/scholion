"""The review of a block of the lifestyle brief: what changed since its wording was last read.

A block of the brief watches markers, and once a measurement newer than the
block's `reviewed` date arrives the page marks it «needs a review». Until
14.09.2026 that mark was a label: the page said a review was due and offered no
way to do one, so the labels piled up (21 of them on one tab of a real profile).

What a review IS decides what a button may do. The numbers inside a block are
substituted by the engine every time the brief is opened, so they are never
stale; what can go stale is the CONCLUSION the wording draws from them. Judging
a conclusion is a person's or a model's act, and this program calls no model. So
the review composed here is everything that can be computed for that judgement:
for every watched marker, the value at the review date and every point since,
where each point stands against its range, and whether that position moved. A
person reads that and either records that the wording still holds, or hands the
block to the assistant with a request built from the same facts.

The request carries the block's raw text with its `{{lab:…}}` tokens, so what
comes back keeps the numbers live.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import core
from ..i18n import t as _t
from .lifestyle import lifestyle_brief
from .labs import _flag_value
from .corridor import point_corridor


def _status(value: Any, lo: Any, hi: Any, censored: Optional[str] = None) -> str:
    try:
        v = float(value)
        bounds = {"ref_low": float(lo) if lo is not None else None,
                  "ref_high": float(hi) if hi is not None else None}
    except (TypeError, ValueError):
        return "unknown"
    flag = _flag_value(bounds, v, censored)
    return "unknown" if flag == "norange" else flag


def _point(p: Dict[str, Any], lo: Any, hi: Any) -> Dict[str, Any]:
    low = p.get("ref_low") if p.get("ref_low") is not None else lo
    high = p.get("ref_high") if p.get("ref_high") is not None else hi
    return {"date": str(p.get("date") or ""), "value": p.get("value"),
            **({"censored": p["censored"]} if p.get("censored") else {}),
            "status": _status(p.get("value"), low, high, p.get("censored"))}


def _marker_changes(key: str, reviewed: str) -> Dict[str, Any]:
    m = (core.labs().get("markers") or {}).get(key) or {}
    lo, hi = m.get("ref_low"), m.get("ref_high")
    def qualified_point(point: Dict[str, Any]) -> Dict[str, Any]:
        corridor = point_corridor(key, m, point)
        result = _point({**point, "ref_low": corridor["ref_low"],
                         "ref_high": corridor["ref_high"]}, None, None)
        if (core.lab_markers().get("markers", {}).get(key) or {}).get("status") == "proposed":
            result["status"] = "unknown"
        return result

    series = sorted((p for p in (m.get("series") or []) if isinstance(p, dict) and p.get("date")),
                    key=lambda p: str(p.get("date")))
    before = [p for p in series if str(p["date"])[:10] <= reviewed]
    after = [qualified_point(p) for p in series if str(p["date"])[:10] > reviewed]
    last_before = qualified_point(before[-1]) if before else None
    direction = None
    if last_before and after and not (last_before.get("censored") or after[-1].get("censored")):
        try:
            a, b = float(last_before["value"]), float(after[-1]["value"])
            direction = "up" if b > a else "down" if b < a else "same"
        except (TypeError, ValueError):
            direction = None
    return {"key": key, "name": m.get("name") or key, "unit": m.get("unit") or "",
            "ref_low": lo, "ref_high": hi, "before": last_before, "after": after,
            "direction": direction,
            "status_changed": bool(last_before and after
                                   and last_before["status"] != after[-1]["status"])}


def _num(v: Any) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f.is_integer() else f"{f:g}"


def _change_line(c: Dict[str, Any]) -> str:
    unit = f" {c['unit']}" if c["unit"] else ""
    before = (_t("brief.review.value", value=(c["before"].get("censored") or "") + _num(c["before"]["value"]), unit=unit, date=c["before"]["date"][:10],
                 status=_t("brief.review.status." + c["before"]["status"]))
              if c["before"] else _t("brief.review.no_before"))
    after = "; ".join(_t("brief.review.value", value=(p.get("censored") or "") + _num(p["value"]), unit=unit, date=p["date"][:10],
                         status=_t("brief.review.status." + p["status"])) for p in c["after"])
    return _t("brief.review.row", name=c["name"], before=before, after=after or "—")


def _request(block: Dict[str, Any], review: Dict[str, Any]) -> str:
    changes = "\n".join("- " + _change_line(c) for c in review["markers"] if c["after"])
    return _t("brief.review.request", block=review["id"], title=review["title"],
              reviewed=review["reviewed"] or "—", body=block.get("body") or "",
              hint=review["review_hint"] or "—", changes=changes or "—")


def brief_review(block: Optional[str] = None) -> Dict[str, Any]:
    """One block's review, or every block that needs one when no block is named."""
    brief = lifestyle_brief()
    if not brief.get("available"):
        return {"ok": False, "reason": "no_brief", "message": _t("brief.review.no_brief")}
    raw = {str(b.get("id")): b for b in (core.lifestyle_brief_src() or {}).get("blocks") or []}
    shown = {str(x.get("id")): x for s in brief.get("sections") or [] for x in s.get("blocks") or []}
    if block and str(block) not in raw:
        return {"ok": False, "reason": "no_block", "message": _t("brief.review.no_block", block=block)}
    ids = [str(block)] if block else [str(s.get("id")) for s in brief.get("stale_blocks") or []]
    out: List[Dict[str, Any]] = []
    for bid in ids:
        src, item = raw[bid], shown.get(bid) or {}
        reviewed = str(src.get("reviewed") or "")[:10]
        review = {"id": bid, "title": src.get("title") or bid, "reviewed": reviewed or None,
                  "newest_data": item.get("newest_data"), "stale": bool(item.get("stale")),
                  "review_hint": src.get("review_hint") or "", "body": item.get("body") or "",
                  "markers": [_marker_changes(str(w.get("key")), reviewed)
                              for w in src.get("watch") or [] if w.get("kind") in (None, "lab")]}
        review["request"] = _request(src, review)
        out.append(review)
    return {"ok": True, "blocks": out, "stale": len(brief.get("stale_blocks") or [])}
