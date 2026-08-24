#!/usr/bin/env python3
"""Build profile/prs_results.json from the raw output of `prs report` — with validation.

Why this step exists. The raw output of `python3 -m scholion.prs report` is
a nested structure (traits[].chosen{...}), while the application and the skill read
a flat one: traits[] with percentile/match_rate/reliable at the top level. Redirecting
the output straight into prs_results.json produces a file in which the engine will find
not a single percentile and will show "no model" for every trait.

Validation rules (identical for all traits):
  · match_rate > 1 — an impossible coverage, the trait is marked unreliable:
    positions in the input VCF have been counted twice (see prs_verify.py --all);
  · the percentile is absent (the model has no 1000G reference distribution) —
    the value is unusable: there is a score but no position in the population;
  · reliable = the percentile exists AND percentile_reliable AND 0.9 ≤ match_rate ≤ 1.

Merging with the old file (when there is one):
  · the new value is usable AND the model matches the one pinned in
    knowledge/prs_models.json → the new one is taken;
  · the model CHANGED relative to the registry → without --accept-model-changes the
    value is NOT accepted (the old one is kept with a note). The reason: a percentile
    has meaning only inside a specific model, while the server's rating changes over
    time — without pinning, one genome receives different percentiles from run to
    run, by tens of points on traits with a weak architecture.
    With the flag the change is accepted and the registry is updated with a date;
  · the new value is unusable, the old one usable → the old one stays, with a note;
  · the trait is absent from the raw output (a run with --only) → the old record
    is kept as it is.
The old file moves to prs_results.json.bak-<date>, and decisions are printed as a table.

    PYTHONPATH=src python3 -m scholion.prs report --vcf genome/scoring_sites.vcf.gz \\
      > profile/prs_report_raw.json
    python3 src/ingest/prs_results_build.py profile/prs_report_raw.json
"""
import datetime as _dt
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "profile" / "prs_results.json"
REGISTRY = ROOT / "src" / "scholion" / "knowledge" / "prs_models.json"
KEEP = ("percentile", "quality_label", "match_rate", "weight_mass_coverage",
        "percentile_reliable", "effect_size")


def _num(x):
    return x if isinstance(x, (int, float)) else None


def _chosen(t):
    ch = t.get("chosen")
    if not ch and t.get("status") == "ok_fallback":
        fb = t.get("fallback") or {}
        ch = fb.get("result") or fb.get("chosen")
    return ch or {}


def _pgs_id(row):
    for k in ("pgs_id", "id", "score_id"):
        v = row.get(k)
        if isinstance(v, str) and v.startswith("PGS"):
            return v
    return None


def _record_candidate(pin, row, today):
    """Record the non-matching model as a registry candidate — a dossier instead of a refusal.

    IMPORTANT: the owner's percentile is not written here — the registry lives in
    knowledge/ and travels out in the distributable package. Only public facts about
    the model and the technical coverage of our file are stored.
    """
    cands = pin.setdefault("candidates", {})
    c = cands.get(row["pgs_id"])
    if c:
        c["seen_count"] = c.get("seen_count", 1) + 1
        c["last_seen"] = today
    else:
        c = cands[row["pgs_id"]] = {"first_seen": today, "last_seen": today, "seen_count": 1}
    c["quality_label"] = row.get("quality_label")
    c["match_rate"] = row.get("match_rate")
    c["has_percentile"] = _num(row.get("percentile")) is not None
    c["percentile_reliable"] = row.get("percentile_reliable")


def build_row(t, today):
    ch = _chosen(t)
    row = {"label": t.get("label"), "category": t.get("category"), "term": t.get("term")}
    for k in KEEP:
        if k in ch:
            row[k] = ch[k]
    row["pgs_id"] = _pgs_id(ch)
    p, mr = _num(row.get("percentile")), _num(row.get("match_rate"))
    problems = []
    if t.get("status") not in ("ok", "ok_fallback"):
        problems.append(f"status={t.get('status')}")
    if p is None:
        problems.append("no percentile (the model has no reference distribution)")
    if mr is not None and mr > 1.0001:
        problems.append("coverage >1 — positions double-counted in the input VCF")
    row["reliable"] = (not problems and row.get("percentile_reliable") is True
                       and mr is not None and 0.9 <= mr <= 1.0001)
    if problems:
        row["integrity_note"] = "; ".join(problems)
    row["source"] = f"rebuild-{today}"
    return row, (p is not None and not any("coverage" in x or "status" in x for x in problems))


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    accept_changes = "--accept-model-changes" in argv
    accept_terms, filtered, i = set(), [], 0
    while i < len(argv):
        if argv[i] == "--accept-model" and i + 1 < len(argv):
            accept_terms.add(argv[i + 1].lower()); i += 2; continue
        if argv[i] != "--accept-model-changes":
            filtered.append(argv[i])
        i += 1
    argv = filtered
    raw = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    new_traits = raw.get("traits") or []
    if not new_traits:
        sys.exit("the input file has no traits[] — is this the raw output of prs report?")
    today = _dt.date.today().isoformat()

    registry = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {}
    pinned = registry.get("models", {})
    old_doc = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    old_by_term = {t.get("term"): t for t in old_doc.get("traits", [])}
    order = [t.get("term") for t in old_doc.get("traits", [])] or [t.get("term") for t in new_traits]

    decisions, merged = [], {}
    for t in new_traits:
        term = t.get("term")
        row, usable = build_row(t, today)
        old = old_by_term.get(term)
        old_usable = old is not None and _num(old.get("percentile")) is not None
        pin = pinned.get(term)
        model_changed = (pin and row.get("pgs_id") and row["pgs_id"] != pin.get("pgs_id"))
        accepted_here = accept_changes or any(a in (term or "").lower() for a in accept_terms)
        if usable and model_changed and not accepted_here and old_usable:
            _record_candidate(pin, row, today)
            kept = dict(old)
            kept["integrity_note"] = (f"recomputation {today}: the server picked {row['pgs_id']} instead "
                                      f"of the pinned {pin['pgs_id']} — the value was not replaced, the "
                                      f"candidate was recorded in the registry. Review: python3 src/ingest/prs_model_review.py")
            merged[term] = kept
            decisions.append((row.get("label") or term or "?",
                              f"candidate {row['pgs_id']} recorded (pinned {pin['pgs_id']}), the value is the old one"))
            continue
        if usable and model_changed and accepted_here:
            pin.setdefault("history", []).append(
                {"pgs_id": pin.get("pgs_id"), "unpinned": today,
                 "reason": "replaced deliberately (--accept-model / --accept-model-changes)"})
            row["model_changed_from"] = {"pgs_id": pin.get("pgs_id"),
                                         "percentile": _num((old or {}).get("percentile")),
                                         "note": "the percentile series before this date is not comparable: a different model"}
            pin.update({"pgs_id": row["pgs_id"], "pinned": today,
                        "quality_label": row.get("quality_label"),
                        "reason": f"the change was accepted on {today}"})
            pin.pop("candidates", None)
        if usable and pin is None and row.get("pgs_id"):
            pinned[term] = {"pgs_id": row["pgs_id"], "label": row.get("label"),
                            "quality_label": row.get("quality_label"), "pinned": today,
                            "reason": "pinned at the first usable computation"}
        if usable:
            merged[term] = row
            d = "new"
            if old_usable and _num(old.get("percentile")) is not None and _num(row.get("percentile")) is not None:
                d += f" (P {old['percentile']}→{row['percentile']})"
        elif old_usable:
            kept = dict(old)
            kept["integrity_note"] = (f"recomputation {today}: {row.get('integrity_note','an unusable result')} "
                                      f"(model {row.get('pgs_id')}); the previous value was kept")
            merged[term] = kept
            d = "kept the old one: " + (row.get("integrity_note") or "?")
        else:
            merged[term] = row
            d = "new, but unreliable: " + (row.get("integrity_note") or "?")
        decisions.append((row.get("label") or term or "?", d))
    for term, old in old_by_term.items():
        if term not in merged:
            merged[term] = old
            decisions.append((old.get("label") or term, "not recomputed — left as it was"))

    traits = [merged[t] for t in order if t in merged]
    traits += [v for k, v in merged.items() if k not in order]
    rel = sum(1 for t in traits if t.get("reliable"))
    meta = dict(old_doc.get("_meta") or {})
    meta.update({
        "updated": today,
        "superpopulation": raw.get("superpopulation", meta.get("superpopulation", "EUR")),
        # Carried beside the panel for the whole life of the file. «EUR» chosen
        # by a default and «EUR» measured from this person's DNA are the same
        # letters and not the same claim, and everything downstream prints the
        # letters. A file written before this field existed has no source, and
        # that reads as «unknown» rather than as «chosen».
        "superpopulation_source": raw.get("superpopulation_source",
                                          meta.get("superpopulation_source")),
        "reliable_count": rel, "total": len(traits),
        "built_by": "src/ingest/prs_results_build.py",
        "input_vcf": raw.get("vcf"),
        "validation": ("match_rate>1 → unreliable (the input was double-counted); a percentile must "
                       "exist; if the new value is unusable, the old one is kept with a note"),
    })
    meta.setdefault("purpose", "Computed polygenic scores (PGS Catalog) — read by the application. PERSONAL.")
    meta.setdefault("disclaimer", "A polygenic score is a statistical proxy, not a diagnosis. The models are "
                    "trained predominantly on European samples; a percentile is a position in a "
                    "population, NOT a probability of disease. Discuss it with a doctor.")

    if RESULTS.exists():
        bak = RESULTS.with_name(f"prs_results.json.bak-{today}")
        shutil.copy2(RESULTS, bak)
        print(f"backup: {bak.name}")
    RESULTS.parent.mkdir(exist_ok=True)
    RESULTS.write_text(json.dumps({"_meta": meta, "traits": traits}, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    if registry:
        registry["models"] = pinned
        REGISTRY.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    w = max(len(n) for n, _ in decisions)
    for n, d in decisions:
        print(f"  {n:<{w}}  {d}")
    print(f"\n✓ {RESULTS}  (traits: {len(traits)}, reliable: {rel})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
