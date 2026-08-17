#!/usr/bin/env python3
"""Review of the candidates for a PGS model change — a quarterly ritual, not a reflex.

Life cycle of a trait's model:
  1. The model is pinned in knowledge/prs_models.json. Percentiles are computed with it alone.
  2. A run in which the server preferred a different model does NOT change the values —
     prs_results_build.py records the non-matching model as a CANDIDATE (a dossier:
     when it was first seen, how many runs in a row, quality, coverage,
     whether a reference percentile exists).
  3. This script reads the dossier and gives a recommendation by objective rules.
  4. A human accepts a change one trait at a time: prs_results_build.py <raw>
     --accept-model <substring of the trait>. The old model moves to history,
     and a mark about the break in the series stays in the trait's record: percentiles
     before and after the change are NOT COMPARABLE (a different model = a different scale).

Recommendation rules (in the order they are checked):
  · no reference percentile           → REJECT (a score without a position in the population is useless);
  · coverage of our file < 0.95       → REJECT (the model fits our data poorly);
  · quality above the pinned one       → MAY BE ACCEPTED now (High > Moderate > Low);
  · seen in ≥ 2 runs, quality not lower → MAY BE ACCEPTED (stable, not a rating fluctuation);
  · otherwise                          → WAIT for the next run.
A percentile shift on its own is never a reason.

    python3 src/ingest/prs_model_review.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "src" / "scholion" / "knowledge" / "prs_models.json"
_QRANK = {"High": 3, "Moderate": 2, "Low": 1, None: 0}


def recommend(pin, cand):
    if not cand.get("has_percentile"):
        return "REJECT", "no reference percentile"
    mr = cand.get("match_rate")
    if isinstance(mr, (int, float)) and mr < 0.95:
        return "REJECT", f"coverage {mr:.2f} < 0.95"
    q_new, q_old = _QRANK.get(cand.get("quality_label"), 0), _QRANK.get(pin.get("quality_label"), 0)
    if q_new > q_old:
        return "MAY BE ACCEPTED", f"higher quality ({cand.get('quality_label')} > {pin.get('quality_label')})"
    if cand.get("seen_count", 0) >= 2 and q_new >= q_old:
        return "MAY BE ACCEPTED", f"stable: {cand['seen_count']} runs in a row, quality not lower"
    return "WAIT", f"seen {cand.get('seen_count', 1)} time(s) — confirm on the next run"


def main() -> int:
    if not REGISTRY.exists():
        sys.exit(f"no registry: {REGISTRY}")
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    models = reg.get("models", {})
    with_cands = {t: e for t, e in models.items() if e.get("candidates")}
    print(f"models pinned: {len(models)}; traits with candidates: {len(with_cands)}\n")
    if not with_cands:
        print("No candidates — every run agrees with the registry. Nothing to decide.")
        return 0
    accept_cmds = []
    for term, e in sorted(with_cands.items()):
        print(f"— {e.get('label') or term}")
        print(f"    pinned:     {e.get('pgs_id')} ({e.get('quality_label')}), since {e.get('pinned')}")
        for pid, c in e["candidates"].items():
            verdict, why = recommend(e, c)
            mr = c.get("match_rate")
            print(f"    candidate:  {pid} ({c.get('quality_label')}), "
                  f"coverage {mr if mr is not None else '?'}, "
                  f"percentile {'present' if c.get('has_percentile') else 'ABSENT'}, "
                  f"seen {c.get('seen_count')}×, {c.get('first_seen')} → {c.get('last_seen')}")
            print(f"    → {verdict}: {why}")
            if verdict == "MAY BE ACCEPTED":
                accept_cmds.append(term)
        print()
    if accept_cmds:
        args = " ".join(f'--accept-model "{t}"' for t in accept_cmds)
        print("Accept the recommended ones (after a fresh report run):")
        print(f"  python3 src/ingest/prs_results_build.py profile/prs_report_raw.json {args}")
        print("Remember: after a change the trait's percentile series starts over — the old values are not comparable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
