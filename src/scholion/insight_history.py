"""Explicit local review snapshots. Read and diff never write the profile."""
from __future__ import annotations

import hmac
from datetime import datetime, timezone

from . import core, container
from .engine.insight_events import _digest
from .i18n import t

FILENAME = "insight_reviews.json"


def _read() -> dict:
    path = core.profile_dir() / FILENAME
    data = core.read_profile_json(path) if path.exists() else {"reviews": []}
    if not isinstance(data.get("reviews"), list):
        raise ValueError("Invalid insight review history")
    return data


def _snapshot(feed: dict) -> dict:
    # No duplicate measurement store: references and fingerprints are sufficient
    # for the diff. The source records remain in their existing profile files.
    return {"policy": feed["policy"], "as_of": feed["as_of"],
            "container": container.named().get("id"),
            "profile_identity": _digest(str(core.profile_dir().resolve())),
            "items": [{"id": i["id"], "name": i["name"], "title": i["title"],
                       "date": i["date"], "level": i.get("level"),
                       "kinds": [e["kind"] for e in i["events"]],
                       "provenance": i["provenance"]} for i in feed["items"]] + _reference_reviews(),
            "states": {k: {f: v.get(f) for f in ("flag", "date", "current", "proposed",
                                                "method", "unit", "ref_low", "ref_high",
                                                "data_digest", "rules_digest")}
                       for k, v in feed.get("states", {}).items()}}


def _reference_reviews() -> list[dict]:
    """Version the curated reference alongside reviews, outside personal attention."""
    entries = core._read_knowledge_raw("longevity_directions.json").get("directions") or {}
    return [{"id": "reference:longevity:" + rsid, "name": spec["gene"] + " " + rsid,
             "title": spec["gene"] + " " + rsid, "date": spec.get("curated_on"),
             "level": spec["level"], "kinds": ["reference_only"],
             "provenance": {"facts_digest": _digest("reference_only"), "rules_digest": _digest(spec)}}
            for rsid, spec in entries.items() if spec.get("level")]


def compare_review(feed: dict, previous: dict | None = None) -> dict:
    if previous is None:
        reviews = _read()["reviews"]
        previous = reviews[-1] if reviews else None
    if previous is None:
        return {"available": False, "items": [], "note": t("insight.no_history")}
    same_profile = previous.get("profile_identity") == _digest(str(core.profile_dir().resolve()))
    # The first confirmed write lazily names a legacy container. Its unchanged
    # resolved profile identity, not a missing old ID, proves continuity.
    if (previous.get("container") != container.named().get("id")
            and not (previous.get("container") is None and same_profile)):
        raise ValueError("Review belongs to another container")
    # A named container is portable. The resolved path binds a pending write,
    # but does not invalidate its saved history when the whole container moves.
    if (not previous.get("container") and previous.get("profile_identity")
            and not same_profile):
        raise ValueError("Review belongs to another profile")
    now = {i["id"]: i for i in _snapshot(feed)["items"]}
    before = {i["id"]: i for i in previous["items"]}
    diffs = []
    for key in sorted(set(now) | set(before)):
        old, new = before.get(key), now.get(key)
        status, reason = "unchanged", "unknown"
        if not old:
            status, reason = "new", "rules" if (new or {}).get("kinds") == ["reference_only"] else "data"
        elif not new:
            # Disappearance alone cannot say resolved or retracted.
            state = feed.get("states", {}).get(key) or {}
            old_state = previous.get("states", {}).get(key) or {}
            comparable = bool(state.get("method") and old_state.get("method")) and all(
                state.get(f) == old_state.get(f) for f in ("method", "unit", "ref_low", "ref_high"))
            only_deviation = set(old.get("kinds") or []) <= {"abnormal", "repeated_abnormal"}
            status = "resolved" if (only_deviation and comparable and state.get("flag") == "ok"
                and state.get("current") is True and not state.get("proposed")
                and str(state.get("date") or "") > old.get("date", "")) else "unavailable"
            reason = "data" if state else "unknown"
            if old.get("kinds") == ["reference_only"]:
                status, reason = "withdrawn", "rules"
            if (state.get("current") is True and old_state.get("data_digest")
                    and state.get("data_digest") == old_state["data_digest"]
                    and old_state.get("rules_digest")
                    and state.get("rules_digest") != old_state["rules_digest"]):
                status, reason = "withdrawn", "rules"
        else:
            a, b = old.get("provenance") or {}, new.get("provenance") or {}
            data = a.get("facts_digest") != b.get("facts_digest")
            rules = a.get("rules_digest") != b.get("rules_digest")
            if data or rules:
                status = "changed"
                reason = "both" if data and rules else "data" if data else "rules"
            if old.get("level") in ("A", "B") and new.get("level") not in ("A", "B", None):
                status, reason = "withdrawn", "rules"
        diffs.append({"id": key, "status": status, "reason": reason,
                      "label": t("insight.diff." + status), "reason_label": t("insight.reason." + reason),
                      "previous": old, "current": new})
    diffs.sort(key=lambda d: (d["status"] != "withdrawn", d["status"] == "unchanged", d["id"]))
    return {"available": True, "saved_at": previous.get("saved_at"), "items": diffs}


def _identity(snap: dict) -> str:
    """A translation or a save timestamp is not a new clinical review."""
    return _digest({**snap, "saved_at": None, "container": None,
                    "items": [{k: v for k, v in item.items() if k not in ("name", "title")}
                              for item in snap["items"]]})


def review_snapshot(confirm: str = "") -> dict:
    """Preview a fingerprint, or save precisely that view after confirmation."""
    from .engine import overview
    if not confirm:
        feed = overview()["attention"]
        snap = _snapshot(feed)
        # Bind confirmation to the resolved profile even without a container ID.
        token = _identity(snap)
        return {"ok": True, "saved": False, "confirmation": token,
                "count": len(snap["items"]), "comparison": compare_review(feed)}
    with core.profile_write_lock():
        core.reset_cache()
        feed = overview()["attention"]
        snap = _snapshot(feed)
        token = _identity(snap)
        if not hmac.compare_digest(str(confirm).encode("utf-8"), token.encode("ascii")):
            return {"ok": False, "saved": False, "error": t("insight.changed")}
        history = _read()
        if history["reviews"] and _identity(history["reviews"][-1]) == token:
            return {"ok": True, "saved": True, "saved_at": history["reviews"][-1]["saved_at"],
                    "count": len(snap["items"]), "message": t("insight.saved")}
        # Naming is part of the confirmed first write. Record that stable ID
        # before persisting, so the very first review can travel with its data.
        snap["container"] = container.ensure()["id"]
        snap["saved_at"] = datetime.now(timezone.utc).isoformat()
        history["reviews"].append(snap)
        core.write_json(core.profile_dir() / FILENAME, history)
        return {"ok": True, "saved": True, "saved_at": snap["saved_at"],
                "count": len(snap["items"]), "message": t("insight.saved")}
