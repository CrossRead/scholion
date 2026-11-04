"""Mitochondrial observations in the shared System contract, without a health score."""
from __future__ import annotations

from datetime import date, timedelta

from . import core, mitochondria
from .i18n import t
from .trend_qualification import observation_day


def _observation(row: dict) -> dict:
    keys = ("key", "name", "value", "unit", "unit_display", "date", "flag", "abnormal",
            "censored", "ref_low", "ref_high", "ref_origin", "trend", "display_recency")
    out = {k: row.get(k) for k in keys}
    out["record"] = "labs.json"
    cutoff = date.today() - timedelta(days=365)
    out["series"] = [p for p in row.get("series") or []
                     if (day := observation_day(p.get("date"))) is not None and cutoff <= day <= date.today()]
    return out


@core.memo_in_reading
def review() -> dict:
    """Read saved results and canonical clinical inputs; never run a BAM job."""
    from .engine.labs import analyze_labs
    from .engine.lifestyle import lifestyle
    from .engine.goals import goal_dashboard
    from .engine.system_panels import _medications_layer
    from .insight_context import _lifestyle_context
    from .reported_response import events
    labs = {m["key"]: m for m in analyze_labs().get("markers") or []}
    saved = mitochondria.report()
    result = saved.get("result") or {}
    available = result.get("variants") or []
    testimony = events()
    rows = []
    for path in core._read_knowledge("mitochondrial_context.json").get("pathways") or []:
        alleles = {(a["position"], a["ref"], a["alt"]) for a in path["alleles"]}
        for variant in available:
            if (variant.get("position"), variant.get("ref"), variant.get("alt")) not in alleles:
                continue
            supported = bool(saved.get("current") and result.get("reference") == mitochondria.RCRS
                             and variant.get("status") == "supported")
            observations = [_observation(labs[k]) for k in path["markers"] if k in labs]
            recent = [m for m in observations if m.get("display_recency") is not False]
            state = "unconfirmed" if not supported else "observations" if recent else "reference"
            abnormal = [m for m in recent if m.get("abnormal")]
            normal = [m for m in recent if m.get("flag") == "ok"]
            pattern = "unconfirmed" if not supported else "abnormal" if abnormal else "normal" if normal else "reference"
            medications: list[dict] = []
            for system_key in path["systems"]:
                for medication in _medications_layer(system_key)["rows"]:
                    if not any(m["name"] == medication["name"] for m in medications):
                        medications.append({**medication, "context_system": system_key})
            rows.append({"key": path["key"], "gene": path["gene"], "variant": variant,
                         "title": t("mt.system.path." + path["key"]),
                         "level": path["level"], "level_scope": t("mt.system.evidence_scope"),
                         "summary": t("mt.system.meaning." + path["key"]),
                         "status": state, "status_text": t("mt.system.match." + state),
                         "causal": False, "observations": observations,
                         "clinical_context": pattern, "clinical_context_text": t("mt.system.join." + pattern),
                         "medications": medications,
                         "provenance": {"record": mitochondria.RESULT, "analyzed_at": result.get("created_at"),
                                        "reference": result.get("reference"), "current": saved.get("current", False)},
                         "reported_responses": [e for e in testimony if e["facts"][0].get("system") in path["systems"]],
                         "sources": path["sources"], "related_systems": path["systems"],
                         "contrary_observations": [m for m in recent if m.get("flag") == "ok"],
                         "abnormal_observations": [m for m in recent if m.get("abnormal")]})
    return {"status": "available" if result else "not_analyzed", "current": saved.get("current", False),
            "message": t("mt.system.saved" if result else "mt.system.not_analyzed"),
            "haplogroup": result.get("haplogroup"), "quality": result.get("quality"),
            "variants": available, "pathways": rows,
            "medications": _medications_layer("mitochondria"),
            "lifestyle": _lifestyle_context(goal_dashboard().get("phenotype") or [], lifestyle(), "mitochondria"),
            "responses": [e for e in testimony if e["facts"][0].get("system") == "mitochondria"],
            "scope": "recorded_context", "causal": False,
            "limitations": [t("mt.system.limit"), t("mt.system.anamnesis")],
            "detail_destination": "genome/mito"}


def attach(system: dict, by_key: dict) -> None:
    """Keep the usual seven layers and expose one shared contextual review."""
    context = review()
    system["mitochondrial_context"] = context
    system["medications"] = context["medications"]
    system["labs"]["missing"] = []
    system["labs"]["missing_names"] = []
    system["labs"]["current_markers"] = [
        {**m, "series": _observation(m)["series"]} for m in system["labs"].get("current_markers", [])]
    system["dynamics"] = {"status": "context", "period": 365,
                          "rows": [_observation(by_key[k]) for k in system["markers"] if k in by_key]}
    system["verdict_line"] = ""
    system["unread_line"] = ""
    system["genetics"].update(status="mitochondrial", why_empty=None, verdict_line="", positions=[])
    system["questions"] = {"status": "ok", "rows": [], "empty_why": "nothing_open"}
    system["next"]["ask"] = {"rows": [], "empty_why": "nothing_open", "empty_reason": t("system.why.nothing_open")}
    if not system["next"]["lab"].get("rows"):
        system["next"]["lab"].update(empty_why="no_rule_fired", empty_reason=t("web.tests.none_supported"))
    # Missing routine observations do not establish an indication for new tests.
    system["next"]["genome"] = {"rows": [], "empty_why": "saved_mitochondrial_context", "empty_reason": context["message"]}
    system["genetics"]["summary"] = context["message"]


def lines(context: dict) -> list[str]:
    """The assistant and CLI get the same reference context and observations."""
    out = [context["message"]]
    for p in context["pathways"]:
        v = p["variant"]
        out += [f"{p['gene']} m.{v['position']}{v['ref']}>{v['alt']} — {v['fraction'] * 100:.2f}%",
                p["title"], p["summary"], p["status_text"], p["clinical_context_text"],
                "Scholion " + p["level"] + ": " + p["level_scope"]]
        if p["medications"]:
            out.append(t("mt.system.related_treatment") + ": " + ", ".join(m["name"] for m in p["medications"]))
        for m in p["observations"]:
            out.append(f"{m['name']}: {m['value']} {m['unit_display'] or m['unit']} ({m['date']})")
        out += [e["detail"]["summary"] for e in p["reported_responses"]]
        out += p["sources"]
    out += [e["detail"]["summary"] for e in context["responses"]]
    for row in context["lifestyle"]:
        if row.get("note"):
            out.append(str(row["note"]))
        elif row.get("value") is not None:
            out.append(f"{row.get('label') or row.get('key')}: {row['value']} {row.get('unit_display', '')} ({row.get('date')})")
    return out + context["limitations"]
