#!/usr/bin/env python3
"""n-of-1 experiments: pre-registration, progress, honest analysis.

Why a separate module. The temptation in self-experimentation is to take the days of
phase A and phase B and run a t-test or Mann-Whitney over days. On daily series of
sleep and stress this gives false confidence: the observations are autocorrelated
(yesterday predicts today), so 28 days are not 28 independent points but essentially
as many as there were PHASES. The naive p is then systematically understated:
"p = 0.02" comes out of noise. The project has already caught this class of error twice
(terciles on a variable with a mass of zeros; a threshold that fires on every object),
so here it is closed off by construction.

What the module does:
  · register  — pre-registration BEFORE the start: hypothesis, ONE primary metric,
                direction, phase length, washout, number of blocks. It immediately
                prints the smallest p achievable for that design — if it is larger
                than alpha, starting the experiment in that shape is pointless.
                The order of the blocks is randomised (the seed is stored — replaying
                it after looking at the data is not allowed).
  · log       — a per-day mark of protocol compliance. An unmarked day counts as
                UNKNOWN, not as compliant; a violated day and the one following it
                are cut out of the analysis. A single hidden violation in a small
                sample destroys the effect size — hence the layer is mandatory.
  · status    — where we are now: which phase is running, how many days are collected.
  · analyze   — a permutation test AT THE LEVEL OF BLOCKS (the phase labels of blocks
                are permuted, not the days), effect size, month-by-month drift, and —
                on a separate line with a warning — the naive p over days, to make
                visible how much it lies.

Data: profile/sleep_nightly.json (per-night metrics). The metric is given as
`sleep.<field>`: deep_min, rem_min, light_min, total_min, awake_min, awake_count,
sleep_stress, score, bedtime_min_from_20.

Experiment file: profile/experiments.json (PERSONAL — stays in profile/).
Protocol templates: knowledge/experiment_templates.json (portable).

Examples:
    python3 src/ingest/nof1.py register --id caffeine_timing \\
        --hypothesis "moving caffeine to the morning will increase deep sleep" \\
        --metric sleep.deep_min --direction increase \\
        --phase-days 14 --blocks 6 --washout 3 --start 2026-09-01
    python3 src/ingest/nof1.py status
    python3 src/ingest/nof1.py analyze caffeine_timing
    python3 src/ingest/nof1.py analyze --retrospective \\
        --metric sleep.deep_min --split-field bedtime_min_from_20 --split-at 420

Not a prescription and not a diagnosis: a tool for testing one's own lifestyle hypotheses.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics as st
import sys
from datetime import date, timedelta
from itertools import combinations
from math import comb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    from scholion import core
    PROFILE = Path(core.profile_dir())
except Exception:                                          # noqa: BLE001
    PROFILE = ROOT / "profile"

EXPERIMENTS = PROFILE / "experiments.json"
NIGHTLY = PROFILE / "sleep_nightly.json"
MAX_EXACT_PERM = 20000          # above that — switch to a sampled permutation
# Sleep phases before 2022 are not comparable: the older device labelled an implausibly
# large share of the night as "deep sleep" (the boundary was fixed while parsing the
# Garmin export). For phase metrics the historical nights are dropped, otherwise the
# exploratory analysis compares devices rather than interventions.
PHASE_METRICS = {"deep_min", "light_min", "rem_min"}
PHASES_VALID_FROM = "2022-01-01"


# ----------------------------------------------------------------------- data
def load_nightly() -> dict:
    """{'YYYY-MM-DD': {field: value}} from the per-night file."""
    if not NIGHTLY.exists():
        sys.exit(f"❌ no {NIGHTLY} — parse the Garmin export first")
    raw = json.loads(NIGHTLY.read_text(encoding="utf-8"))
    nights = raw.get("nights", raw) if isinstance(raw, dict) else raw
    out = {}
    for n in nights:
        d = str(n.get("date", ""))[:10]
        if d:
            out[d] = n
    return out


def series_for(metric: str, nights: dict) -> dict:
    """metric='sleep.deep_min' -> {'YYYY-MM-DD': float}"""
    src, _, field = metric.partition(".")
    if src != "sleep":
        sys.exit(f"❌ only the sleep.* source is supported, got: {metric}")
    out, dropped = {}, 0
    for d, n in nights.items():
        v = n.get(field)
        if not isinstance(v, (int, float)):
            continue
        if field in PHASE_METRICS and d < PHASES_VALID_FROM:
            dropped += 1
            continue
        out[d] = float(v)
    if not out:
        sys.exit(f"❌ field {field} not found in the per-night data")
    if dropped:
        print(f"  ({dropped} nights before {PHASES_VALID_FROM} dropped: the sleep phases of the"
              f" older device are not comparable with the current ones)")
    return out


def read_experiments() -> dict:
    if EXPERIMENTS.exists():
        return json.loads(EXPERIMENTS.read_text(encoding="utf-8"))
    return {"_meta": {"purpose": "the owner's n-of-1 experiments: pre-registration and "
                                 "results. PERSONAL.",
                      "rule": "edits to the protocol after the start are forbidden — register "
                              "a new experiment referring to the previous one"},
            "experiments": []}


def write_experiments(data: dict) -> None:
    EXPERIMENTS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------------------ statistics
def min_achievable_p(n_blocks: int, n_a: int | None = None) -> float:
    """The smallest possible one-sided p under a permutation of the block labels.

    This is a property of the DESIGN, not of the data: with 4 blocks (ABAB) there are only
    6 distinguishable splits, so p<0.05 is unreachable in principle, however strong the effect.
    """
    if n_a is None:
        n_a = n_blocks // 2
    total = comb(n_blocks, n_a)
    return 1.0 / total if total else 1.0


def block_permutation_test(a_means, b_means, direction="increase", seed=20260814):
    """Permutation test at the block level. Returns (observed difference, p, n_perm)."""
    values = list(a_means) + list(b_means)
    n, k = len(values), len(a_means)
    obs = st.mean(b_means) - st.mean(a_means)
    idx = range(n)
    total = comb(n, k)
    if total <= MAX_EXACT_PERM:
        splits = list(combinations(idx, k))
        exact = True
    else:
        rnd = random.Random(seed)
        splits = [tuple(rnd.sample(list(idx), k)) for _ in range(MAX_EXACT_PERM)]
        exact = False
    hits = 0
    for s in splits:
        a = [values[i] for i in s]
        b = [values[i] for i in idx if i not in s]
        diff = st.mean(b) - st.mean(a)
        if direction == "increase":
            hits += diff >= obs - 1e-12
        elif direction == "decrease":
            hits += diff <= obs + 1e-12
        else:
            hits += abs(diff) >= abs(obs) - 1e-12
    return obs, hits / len(splits), (len(splits), exact)


def naive_day_p(a_days, b_days, direction="increase", seed=20260814, n=5000):
    """The naive permutation OVER DAYS — kept only to show how much it lies."""
    vals = list(a_days) + list(b_days)
    k = len(a_days)
    obs = st.mean(b_days) - st.mean(a_days)
    rnd = random.Random(seed)
    hits = 0
    for _ in range(n):
        rnd.shuffle(vals)
        diff = st.mean(vals[k:]) - st.mean(vals[:k])
        if direction == "increase":
            hits += diff >= obs - 1e-12
        elif direction == "decrease":
            hits += diff <= obs + 1e-12
        else:
            hits += abs(diff) >= abs(obs) - 1e-12
    return hits / n


# ------------------------------------------------------------------- commands
def cmd_register(args) -> int:
    data = read_experiments()
    if any(e["id"] == args.id for e in data["experiments"]):
        sys.exit(f"❌ experiment {args.id} already registered — the protocol is not edited after the start")
    if args.blocks < 2 or args.blocks % 2:
        sys.exit("❌ the number of blocks must be even and ≥2 (equal counts of A and B)")

    seed = args.seed or int(date.today().strftime("%Y%m%d"))
    rnd = random.Random(seed)
    order = ["A"] * (args.blocks // 2) + ["B"] * (args.blocks // 2)
    rnd.shuffle(order)                    # order randomised instead of a rigid ABAB
    start = date.fromisoformat(args.start)
    blocks = []
    for i, lab in enumerate(order):
        b0 = start + timedelta(days=i * args.phase_days)
        blocks.append({"n": i + 1, "label": lab,
                       "start": str(b0), "end": str(b0 + timedelta(days=args.phase_days - 1))})
    pmin = min_achievable_p(args.blocks)

    exp = {
        "id": args.id, "registered": str(date.today()), "status": "registered",
        "hypothesis": args.hypothesis,
        "primary_metric": args.metric, "direction": args.direction,
        "secondary_metrics": args.secondary or [],
        "phase_days": args.phase_days, "blocks": args.blocks,
        "washout_days": args.washout, "alpha": args.alpha,
        "randomization_seed": seed, "schedule": blocks,
        "analysis": "permutation test at the block level (phase labels are permuted for "
                    "blocks, not for days); one primary metric, the rest are exploratory",
        "min_achievable_p": round(pmin, 4),
        "feasible": pmin <= args.alpha,
    }
    data["experiments"].append(exp)
    write_experiments(data)

    print(f"✓ pre-registration written: {EXPERIMENTS}")
    print(f"\nHypothesis: {args.hypothesis}")
    print(f"Primary metric: {args.metric} ({args.direction}); alpha={args.alpha}")
    print(f"Design: {args.blocks} blocks of {args.phase_days} d., washout {args.washout} d.")
    print("Block order (randomised, seed {}): {}".format(seed, " ".join(order)))
    for b in blocks:
        print(f"   {b['n']}. {b['label']}  {b['start']} … {b['end']}")
    print(f"\nSmallest achievable p for this number of blocks: {pmin:.3f}")
    if not exp["feasible"]:
        need = 2
        while min_achievable_p(need) > args.alpha:
            need += 2
        print(f"⚠ THIS DESIGN CANNOT REACH SIGNIFICANCE at alpha={args.alpha}: "
              f"however strong the effect, p will not drop below {pmin:.3f}.")
        print(f"  To make significance possible, at least {need} blocks are needed "
              f"({need * args.phase_days} d.). Or accept that the result will be "
              f"descriptive, and say so in advance.")
    else:
        print("✓ the design can reach significance given a large enough effect")
    print("\nRule: the protocol does not change after the start. If you want to change the metric "
          "or the duration — that is a new experiment, the old one is closed as it stands.")
    return 0


def cmd_log(args) -> int:
    """A per-day mark of protocol compliance. An unmarked day is NOT a compliant one
    but an UNKNOWN one: the same rule as "not found in the archive" ≠ "was never taken"."""
    data = read_experiments()
    exp = next((e for e in data["experiments"] if e["id"] == args.id), None)
    if not exp:
        sys.exit(f"❌ experiment {args.id} not found")
    log = exp.setdefault("compliance_log", {})
    d = args.date or str(date.today())
    log[d] = {"ok": args.ok, "note": args.note or ""}
    write_experiments(data)
    print(f"✓ {args.id}: {d} — protocol {'complied with' if args.ok else 'VIOLATED'}"
          + (f" ({args.note})" if args.note else ""))
    if not args.ok:
        print("  this day and the one after it are excluded from the analysis (carry-over of the effect)")
    return 0


def cmd_status(_args) -> int:
    data = read_experiments()
    if not data["experiments"]:
        print("No experiments registered.")
        return 0
    today = date.today()
    for e in data["experiments"]:
        print(f"\n[{e['id']}] {e['hypothesis']}")
        print(f"  metric {e['primary_metric']} ({e['direction']}), "
              f"{e['blocks']} blocks × {e['phase_days']} d., alpha={e['alpha']}, "
              f"floor p={e['min_achievable_p']}")
        cur = None
        for b in e["schedule"]:
            if date.fromisoformat(b["start"]) <= today <= date.fromisoformat(b["end"]):
                cur = b
        if cur:
            left = (date.fromisoformat(cur["end"]) - today).days
            print(f"  current block {cur['n']} ({cur['label']}), days left: {left}")
        elif today < date.fromisoformat(e["schedule"][0]["start"]):
            print(f"  not started yet (start {e['schedule'][0]['start']})")
        else:
            print("  all blocks are done — analyze can be run")
    return 0


def _excluded_days(exp):
    """Days thrown out of the analysis: protocol violations and the day after them
    (carry-over of the effect). One hidden violation breaks the mathematics of small
    samples, so violations are not "averaged in" but cut out."""
    log = exp.get("compliance_log", {}) or {}
    out = set()
    for d, rec in log.items():
        if not rec.get("ok", True):
            try:
                d0 = date.fromisoformat(d)
            except ValueError:
                continue
            out.add(str(d0))
            out.add(str(d0 + timedelta(days=1)))
    return out


def _collect_blocks(exp, series):
    """Per-block means: washout, protocol violations and the day after them are removed.

    It also returns per-block compliance statistics — without them a "clean phase A"
    may in fact contain violations, and the effect size would be false.
    """
    log = exp.get("compliance_log", {}) or {}
    bad = _excluded_days(exp)
    a_means, b_means, a_days, b_days, per_block = [], [], [], [], []
    for b in exp["schedule"]:
        s = date.fromisoformat(b["start"]) + timedelta(days=exp["washout_days"])
        e = date.fromisoformat(b["end"])
        in_block = [(d, v) for d, v in series.items()
                    if s <= date.fromisoformat(d) <= e]
        kept = [v for d, v in in_block if d not in bad]
        n_all = len(in_block)
        n_logged = sum(1 for d, _ in in_block if d in log)
        n_bad = sum(1 for d, _ in in_block if d in bad)
        stats = {"days": n_all, "logged": n_logged, "excluded": n_bad,
                 "unknown": n_all - n_logged}
        if not kept:
            per_block.append((b, None, 0, stats))
            continue
        m = st.mean(kept)
        per_block.append((b, m, len(kept), stats))
        (a_means if b["label"] == "A" else b_means).append(m)
        (a_days if b["label"] == "A" else b_days).extend(kept)
    return a_means, b_means, a_days, b_days, per_block


def _report(name, direction, alpha, a_means, b_means, a_days, b_days, per_block,
            registered=True, min_p=None):
    if len(a_means) < 2 or len(b_means) < 2:
        print("⚠ fewer than two blocks in a group — the permutation test is impossible. "
              "Showing descriptive means only.")
    print("\nBlocks (in chronological order — that is how drift becomes visible):")
    shown = per_block if len(per_block) <= 14 else per_block[:7] + [None] + per_block[-6:]
    for row in shown:
        if row is None:
            print(f"  … {len(per_block) - 13} blocks omitted (all of them are in the JSON/data)")
            continue
        b, m, n, sd = row
        line = (f"  {b['n']}. {b['label']}  {b['start']}…{b['end']}  "
                + (f"mean {m:.1f} (nights {n})" if m is not None else "no data"))
        if sd and sd["days"]:
            if sd["excluded"]:
                line += f"  ⚠ {sd['excluded']} d. dropped (violations)"
            if sd["unknown"] and registered:
                line += f"  · unmarked: {sd['unknown']}"
        print(line)
    if not a_means or not b_means:
        return
    obs = st.mean(b_means) - st.mean(a_means)
    print(f"\nEffect (B − A) over block means: {obs:+.2f}")
    print(f"  A: {', '.join(f'{m:.1f}' for m in a_means)}   "
          f"B: {', '.join(f'{m:.1f}' for m in b_means)}")

    if len(a_means) >= 2 and len(b_means) >= 2:
        _, p, (nperm, exact) = block_permutation_test(a_means, b_means, direction)
        kind = "exhaustive" if exact else "sampled permutation"
        print(f"\nBlock permutation test: p = {p:.3f} "
              f"({kind}, {nperm} splits)")
        floor = min_p if min_p is not None else min_achievable_p(len(a_means) + len(b_means))
        print(f"  smallest achievable p for this design: {floor:.3f}")
        if p <= alpha:
            print(f"  → the difference survives a permutation of the blocks (alpha={alpha})")
        elif floor > alpha:
            print(f"  → significance is unreachable by design; the conclusion is descriptive only")
        else:
            print(f"  → not shown at alpha={alpha}")

    if a_days and b_days:
        pn = naive_day_p(a_days, b_days, direction)
        print(f"\n  for comparison — the naive test OVER DAYS: p = {pn:.3f}. "
              f"NOT to be used for a decision:")
        print(f"  days within a block are autocorrelated, so it understates p and creates "
              f"confidence out of nothing.")

    # drift: the difference "first half against second" regardless of the labels
    mids = [row[1] for row in per_block if row[1] is not None]
    if len(mids) >= 4:
        h = len(mids) // 2
        drift = st.mean(mids[h:]) - st.mean(mids[:h])
        print(f"\nDrift (second half − first, labels ignored): {drift:+.2f}")
        if abs(drift) >= abs(obs) * 0.7:
            print("  ⚠ comparable with the effect itself — this may be a trend/season "
                  "rather than the action of the intervention")
    # compliance: an unmarked day is not "complied" but "unknown"
    if registered:
        tot = sum(sd["days"] for _, _, _, sd in per_block if sd)
        logged = sum(sd["logged"] for _, _, _, sd in per_block if sd)
        excl = sum(sd["excluded"] for _, _, _, sd in per_block if sd)
        if tot:
            cover = logged / tot
            print(f"\nProtocol compliance: {logged} of {tot} days marked "
                  f"({cover:.0%}), {excl} dropped for violations")
            if cover < 0.8:
                print("  ⚠ fewer than 80 % of days are marked — an unmarked day is NOT «complied», "
                      "it is «unknown». The verdict is downgraded to descriptive: a hidden "
                      "violation in a small sample breaks the effect size.")
            elif excl / max(tot, 1) > 0.3:
                print("  ⚠ more than 30 % of days dropped — it is wiser to replay the phase "
                      "than to finish counting on the leftovers.")

    if not registered:
        print("\n⚠ EXPLORATORY analysis on historical data: the hypothesis was chosen after "
              "the data had been seen, so p confirms nothing here. "
              "It is good for deciding what to test prospectively.")


def cmd_analyze(args) -> int:
    nights = load_nightly()
    if args.retrospective:
        series = series_for(args.metric, nights)
        field = args.split_field
        vals = {d: n.get(field) for d, n in nights.items()
                if isinstance(n.get(field), (int, float)) and d in series}
        if not vals:
            sys.exit(f"❌ split field {field} not found")
        if args.split_at is None:
            args.split_at = st.median(vals.values())
            print(f"  no split threshold given — using the personal median of {field}: "
                  f"{args.split_at:.0f}")
        # blocks are calendar months, a block's label comes from the field's monthly median
        months: dict[str, list[str]] = {}
        for d in sorted(vals):
            months.setdefault(d[:7], []).append(d)
        schedule, series_local = [], {}
        for i, (mo, days) in enumerate(sorted(months.items())):
            if len(days) < 5:
                continue
            med = st.median(vals[d] for d in days)
            lab = "B" if med < args.split_at else "A"     # below the threshold = "earlier"
            schedule.append({"n": i + 1, "label": lab, "start": days[0], "end": days[-1]})
            for d in days:
                series_local[d] = series[d]
        if len(schedule) < 4:
            sys.exit("❌ too few months with data for an exploratory split")
        exp = {"schedule": schedule, "washout_days": 0, "compliance_log": {}}
        a_m, b_m, a_d, b_d, per = _collect_blocks(exp, series_local)
        print(f"EXPLORATORY: {args.metric} at {field} < {args.split_at} (label B) "
              f"against ≥ (label A); a block is a calendar month")
        _report(args.metric, args.direction, args.alpha, a_m, b_m, a_d, b_d, per,
                registered=False)
        return 0

    data = read_experiments()
    exp = next((e for e in data["experiments"] if e["id"] == args.id), None)
    if not exp:
        sys.exit(f"❌ experiment {args.id} not found — run register first")
    series = series_for(exp["primary_metric"], nights)
    a_m, b_m, a_d, b_d, per = _collect_blocks(exp, series)
    print(f"[{exp['id']}] {exp['hypothesis']}")
    print(f"Primary metric: {exp['primary_metric']} ({exp['direction']}), "
          f"alpha={exp['alpha']}, washout {exp['washout_days']} d.")
    _report(exp["primary_metric"], exp["direction"], exp["alpha"],
            a_m, b_m, a_d, b_d, per, registered=True, min_p=exp["min_achievable_p"])
    if exp.get("secondary_metrics"):
        print("\n— Secondary metrics (exploratory, they do not affect the verdict, "
              "no multiplicity correction is applied) —")
        for m in exp["secondary_metrics"]:
            s2 = series_for(m, nights)
            a2, b2, _, _, _ = _collect_blocks(exp, s2)
            if a2 and b2:
                print(f"  {m}: B−A = {st.mean(b2) - st.mean(a2):+.2f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="n-of-1 experiments: an honest loop")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="pre-registration of the protocol BEFORE the start")
    r.add_argument("--id", required=True)
    r.add_argument("--hypothesis", required=True)
    r.add_argument("--metric", required=True, help="e.g. sleep.deep_min")
    r.add_argument("--direction", default="increase", choices=["increase", "decrease", "any"])
    r.add_argument("--secondary", nargs="*", default=[])
    r.add_argument("--phase-days", type=int, default=14)
    r.add_argument("--blocks", type=int, default=4)
    r.add_argument("--washout", type=int, default=2)
    r.add_argument("--alpha", type=float, default=0.05)
    r.add_argument("--start", default=str(date.today() + timedelta(days=1)))
    r.add_argument("--seed", type=int, default=0)
    r.set_defaults(func=cmd_register)

    s = sub.add_parser("status", help="progress of the experiments")
    s.set_defaults(func=cmd_status)

    lg = sub.add_parser("log", help="mark protocol compliance for a day")
    lg.add_argument("id")
    lg.add_argument("--date", default=None, help="YYYY-MM-DD, today by default")
    g = lg.add_mutually_exclusive_group(required=True)
    g.add_argument("--ok", dest="ok", action="store_true", help="the protocol was complied with")
    g.add_argument("--violated", dest="ok", action="store_false", help="the protocol was violated")
    lg.add_argument("--note", default="")
    lg.set_defaults(func=cmd_log)

    a = sub.add_parser("analyze", help="analysis (of a registered experiment, or exploratory)")
    a.add_argument("id", nargs="?")
    a.add_argument("--retrospective", action="store_true")
    a.add_argument("--metric", default="sleep.deep_min")
    a.add_argument("--split-field", default="bedtime_min_from_20")
    a.add_argument("--split-at", type=float, default=None,
               help="split threshold; by default — the personal median of the field")
    a.add_argument("--direction", default="increase", choices=["increase", "decrease", "any"])
    a.add_argument("--alpha", type=float, default=0.05)
    a.set_defaults(func=cmd_analyze)

    args = ap.parse_args()
    if args.cmd == "analyze" and not args.retrospective and not args.id:
        ap.error("an experiment id or --retrospective is required")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
