#!/usr/bin/env python3
"""Compare recomputed PGS against the current profile/prs_results.json — BEFORE replacing.

Reads the raw output of `python3 -m scholion.prs report ...` (JSON with a list of
traits[], where every trait carries chosen — the row the model selected) and prints
a table: old percentile → new, shift, coverage, model change.

    python3 src/ingest/prs_diff.py profile/prs_recheck.json
    python3 src/ingest/prs_diff.py profile/prs_results.fixed.json

Writes nothing. The decision to replace is taken by eye from this table.

What to look at:
  · the match_rate of the new computation must be ≤ 1 — if it is above that again, the
    cleaning of the input did not work and replacement is not allowed;
  · traits untouched by the cleaning (no duplicates in the old computation) must
    reproduce the old percentile up to noise — that is a built-in control;
  · a change of pgs_id is flagged: for such traits the shift mixes "a different model"
    with "a clean input", and they cannot be compared head to head.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _num(x):
    return x if isinstance(x, (int, float)) else None


def _chosen(t):
    """The model row selected, taken from the raw output of report()."""
    ch = t.get("chosen")
    if not ch and t.get("status") == "ok_fallback":
        fb = t.get("fallback") or {}
        ch = fb.get("result") or fb.get("chosen")
    return ch or {}


def _pgs_id(row):
    for k in ("pgs_id", "id", "score_id", "pgs"):
        v = row.get(k)
        if isinstance(v, str) and v.startswith("PGS"):
            return v
    return ""


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    new_path = Path(argv[1])
    old_path = ROOT / "profile" / "prs_results.json"
    old = {t.get("term"): t for t in json.loads(old_path.read_text(encoding="utf-8")).get("traits", [])}
    new = json.loads(new_path.read_text(encoding="utf-8"))
    rows = []
    for t in new.get("traits", []):
        ch = _chosen(t)
        rows.append({
            "term": t.get("term"), "label": t.get("label") or t.get("term"),
            "status": t.get("status"),
            "p_new": _num(ch.get("percentile")),
            "mr_new": _num(ch.get("match_rate")),
            "pgs_new": _pgs_id(ch),
        })
    if not rows:
        sys.exit(f"{new_path} has no traits[] — is this really the raw output of report?")

    bad_mr, controls_moved, changed_model = [], [], []
    print(f"{'trait':34} {'P old':>7} {'P new':>7} {'ΔP':>7} {'mr old':>8} {'mr new':>7}  model")
    for r in sorted(rows, key=lambda r: -(abs((r["p_new"] or 0) - (_num((old.get(r["term"]) or {}).get("percentile")) or 0)))):
        o = old.get(r["term"]) or {}
        p_old, mr_old, pgs_old = _num(o.get("percentile")), _num(o.get("match_rate")), o.get("pgs_id") or ""
        dp = (r["p_new"] - p_old) if (r["p_new"] is not None and p_old is not None) else None
        flags = []
        if r["mr_new"] is not None and r["mr_new"] > 1.0001:
            flags.append("‼ mr>1"); bad_mr.append(r["label"])
        if r["pgs_new"] and pgs_old and r["pgs_new"] != pgs_old:
            flags.append(f"model {pgs_old}→{r['pgs_new']}"); changed_model.append(r["label"])
        was_clean = mr_old is not None and mr_old <= 1.0001
        if was_clean and dp is not None and abs(dp) > 3 and not (r["pgs_new"] and pgs_old and r["pgs_new"] != pgs_old):
            flags.append("⚠ control moved"); controls_moved.append(r["label"])
        if r["status"] not in ("ok", "ok_fallback"):
            flags.append(f"status={r['status']}")
        print(f"{(r['label'] or '')[:34]:34} "
              f"{p_old if p_old is not None else '—':>7} "
              f"{r['p_new'] if r['p_new'] is not None else '—':>7} "
              f"{f'{dp:+.1f}' if dp is not None else '—':>7} "
              f"{mr_old if mr_old is not None else '—':>8} "
              f"{r['mr_new'] if r['mr_new'] is not None else '—':>7}  "
              f"{r['pgs_new'] or pgs_old}  {' '.join(flags)}")

    print()
    verdict_bad = bool(bad_mr or controls_moved)
    if bad_mr:
        print(f"‼ match_rate > 1 is still there: {bad_mr} — the input is still dirty, do NOT replace")
    if controls_moved:
        print(f"⚠ control traits moved by >3 percentiles: {controls_moved} — investigate before replacing")
    if changed_model:
        print(f"ℹ the model changed: {changed_model} — their shift is not directly comparable")
    if not verdict_bad:
        print("✅ The controls hold, coverage ≤ 1. The replacement of the values can be discussed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
