"""Readable facts from the shared feed, for CLI and agent transports."""
from .i18n import t


def basis_lines(item: dict) -> list[str]:
    basis = (item.get("provenance") or {}).get("basis") or {}
    if not basis:
        return []
    lines = [t("insight.basis.title")]
    seen = set()
    for fact in basis.get("facts") or []:
        source = fact.get("source") or t("insight.basis.source_unknown")
        key = (str(source), fact.get("date"))
        if key in seen:
            continue
        seen.add(key)
        lines.append(str(fact.get("date") or "—") + " · " + str(source))
        if fact.get("availability") == "unavailable":
            lines.append(t("insight.basis.unavailable"))
    for witness in (basis.get("knowledge") or []) + (basis.get("rule_sources") or []):
        lines.append(str(witness.get("source") or t("insight.basis.source_unknown")) + " · " +
                     str(witness.get("checked_on") or "—") + " · " + str(witness.get("version") or "—"))
    lines += [t("insight.basis.recorded"), t("insight.basis.refresh")]
    return lines


def review_change_lines(comparison: dict) -> list[str]:
    items = comparison.get("display_items", comparison.get("items")) or []
    changed = [i for i in items if i["status"] != "unchanged"]
    lines = [] if changed else [t("insight.no_changes")]
    for item in changed:
        row = item.get("current") or item.get("previous") or {}
        lines.append(f"{item['label']}: {row.get('name', '')} · {item['reason_label']}")
    unchanged = [i for i in items if i["status"] == "unchanged"]
    if unchanged:
        lines.append(t("insight.unchanged") + ": " + ", ".join(
            str((i.get("current") or i.get("previous") or {}).get("name") or "") for i in unchanged))
    return lines


def review_report(result: dict) -> str:
    if result.get("error"):
        return result["error"]
    if result.get("saved"):
        return result["message"]
    comparison = result.get("comparison") or {}
    lines = [t("insight.history")]
    if not comparison.get("available"):
        lines.append(t("insight.no_history"))
    else:
        lines.extend(review_change_lines(comparison))
    lines.append("scholion insight-snapshot --confirm " + result["confirmation"])
    return "\n".join(lines)


def comparison_lines(comparison: dict) -> list[str]:
    lines = []
    if comparison.get("statistic") in ("mean", "median"):
        lines.append(t("insight.stat." + comparison["statistic"]))
    if comparison.get("delta") is not None:
        lines.append(t("insight.delta") + ": " + str(comparison["delta"]))
    if comparison.get("mdd") is not None:
        lines.append(t("insight.mdd", value=comparison["mdd"]))
    if comparison.get("before_dates"):
        lines.append(t("insight.period_dates", a=" — ".join(comparison["before_dates"]),
                       b=" — ".join(comparison["after_dates"])))
    if comparison.get("before_range"):
        lines.append(t("insight.period_ranges", a=comparison["before_range"], b=comparison["after_range"],
                       na=comparison["before_n"], nb=comparison["after_n"]))
    for field in ("before", "after"):
        point = comparison.get(field) or {}
        stats = (point.get("stats") or {}) if isinstance(point, dict) else {}
        if stats:
            lines.append(t("insight.coverage", date=point.get("date"), n=stats.get("n"),
                           days=stats.get("days"), sd=stats.get("sd")))
    if comparison.get("method_recorded") is False or (comparison.get("comparison") or {}).get("method_recorded") is False:
        lines.append(t("insight.method_unknown"))
    return lines


def attention_report(feed: dict, clinician: bool = False) -> str:
    lines = [feed["title"]]
    displayed = feed.get("highlights", feed["items"])
    if not displayed:
        lines.append(t("insight.highlights_empty"))
    for item in displayed:
        lines += ["", ("🔴 " if item["priority"] == 0 else "") + item["title"] + " · " + item["date"], item["reason"]]
        lines.extend(item.get("summaries") or [])
        from .insight_context import context_lines
        lines.extend(context_lines(item, clinician))
        for event in item["events"][1:]:
            lines.append(event["title"])
        if item.get("level"):
            lines.append("Scholion: " + item["level"])
        for fact in item["facts"]:
            if fact.get("target"):
                target = fact["target"]
                bounds = str(target["value"]) if target.get("value") is not None else str(target.get("low") if target.get("low") is not None else "—") + "–" + str(target.get("high") if target.get("high") is not None else "—")
                lines.append(t("insight.target", value=bounds, unit=target.get("unit") or ""))
            if fact.get("genotype"):
                lines.append(f"{fact.get('gene') or ''} {fact.get('rsid') or ''}: {fact['genotype']}")
            if fact.get("percentile") is not None:
                lines.append(t("insight.pgs", model=fact["pgs_id"], value=fact["percentile"],
                               population=fact["reference_panel_ancestry"]))
            if fact.get("value") is not None:
                lines.append(f"  {fact.get('date') or '—'}: {fact.get('censored') or ''}{fact['value']} "
                             f"{fact.get('unit_display') or fact.get('unit') or ''} · "
                             f"{fact.get('source') or fact.get('record') or '—'}")
            if fact.get("ref_low") is not None or fact.get("ref_high") is not None:
                lines.append(t("insight.reference", low=fact.get("ref_low") if fact.get("ref_low") is not None else "—",
                               high=fact.get("ref_high") if fact.get("ref_high") is not None else "—"))
        for event in item["events"]:
            detail = event.get("detail") or {}
            for key in ("action", "factor", "why_it_matters", "mechanism", "why", "source", "plan_source", "study_limitations"):
                if detail.get(key):
                    lines.append(str(detail[key]))
            comparison = detail if detail.get("before_range") else detail.get("trend") or detail.get("comparison") or detail
            lines.extend(comparison_lines(comparison))
            if detail.get("trend") and detail.get("comparison"):
                lines.extend(comparison_lines(detail["comparison"]))
            for limit in event.get("limitations") or []:
                lines.append(t("insight.limit." + limit))
        if clinician:
            lines.extend(basis_lines(item))
    if "highlights" in feed and feed["items"]:
        lines += ["", t("insight.observations", n=len(feed["items"]))]
        lines.extend(item["title"] + " · " + item["date"] for item in feed["items"])
    return "\n".join(lines)


def summary_report(feed: dict) -> str:
    lines = [t("web.phenotype.title"), t("insight.period", n=feed["period"])]
    for row in feed.get("summary") or []:
        for part in row.get("components") or []:
            lines.append(f"{row['label']}: {part.get('value', '—')} "
                         f"{part.get('unit_display') or part.get('unit') or ''} · {part.get('date') or '—'}")
            window = part.get("period") or {}
            if window.get("delta") is not None:
                label = t("insight.stat.mean") if window.get("statistic") == "mean" else t("insight.period_observations")
                lines.append(f"  {label}: {window['from']} → {window['to']} · {window['delta']:+g}")
            else:
                lines.append(t("insight.latest_within") if part.get("reading_status") == "within"
                             else t("insight.one_reading") if len(window.get("series") or []) == 1
                             else t("insight.no_change_estimate"))
    return "\n".join(lines)
