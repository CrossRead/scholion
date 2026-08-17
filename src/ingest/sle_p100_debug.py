#!/usr/bin/env python3
"""Analysis of a top-of-scale percentile for lupus (PGS000328) — three questions in one run. Task #7.

Question 1. WHAT THE MODEL IS: the full header of the harmonised file — name, citation,
publication. If the GWAS is East Asian (the hypothesis about GTF2I dominance), a percentile
against the EUR reference may be biased.

Question 2. WHAT THE ALLELE MISSES ARE: every variant of the model that failed to match on
alleles, by name — with the rows of our VCF at that position alongside. It shows whether
these are multi-allelic sites and what exactly fails to match.

Question 3. WHERE THE EXTREME PERCENTILE COMES FROM: the 1000G reference distribution is read
from the just-prs cache and the percentile is computed for the HONEST (allele-aware) score —
and for the score with "phantom" doses (misses counted positionally, the way a naive matcher
counts them). Whichever of the two lands at the top is the mechanism at work.

Run on the Mac (needs the just-prs cache and, for question 3, pyarrow):
    python3 src/ingest/sle_p100_debug.py
    pip3 install --user pyarrow    # if it asks for it
"""
import gzip
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PID = "PGS000328"
CACHE = Path.home() / "Library" / "Caches" / "just-prs"

spec = importlib.util.spec_from_file_location("prs_verify", ROOT / "src" / "ingest" / "prs_verify.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def main():
    model = CACHE / "scores" / f"{PID}_hmPOS_GRCh38.txt.gz"
    if not model.exists():
        sys.exit(f"model not in the cache: {model} — run this on the owner's machine")

    print("=" * 70)
    print("QUESTION 1 — what the model is (the full file header)")
    print("=" * 70)
    with gzip.open(model, "rt", errors="replace") as fh:
        for line in fh:
            if not line.startswith("#"):
                break
            print("  " + line.rstrip())

    print()
    print("=" * 70)
    print("QUESTION 2 — the misses one by one (the model's alleles against the rows of our VCF)")
    print("=" * 70)
    vcf = ROOT / "genome" / "scoring_sites_ext.fixed.vcf.gz"
    geno, dup, dp = v.load_target(vcf)
    mism, contrib_honest, contrib_phantom = [], 0.0, 0.0
    n = matched = 0
    with gzip.open(model, "rt", errors="replace") as fh:
        hdr = None
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if hdr is None:
                hdr = {c: i for i, c in enumerate(f)}
                continue
            n += 1
            ci = hdr.get("hm_chr", hdr.get("chr_name")); pi = hdr.get("hm_pos", hdr.get("chr_position"))
            ei = hdr.get("effect_allele"); oi = hdr.get("other_allele", hdr.get("hm_inferOtherAllele"))
            wi = hdr.get("effect_weight")
            chrom = f[ci][3:] if f[ci].startswith("chr") else f[ci]
            key = (chrom, f[pi])
            rec = geno.get(key)
            w = float(f[wi])
            if not rec:
                print(f"  chr{chrom}:{f[pi]}  position not in the VCF  (eff={f[ei]} oth={f[oi] if oi else '?'} w={w:+.3f})")
                continue
            oth = f[oi] if oi is not None and oi < len(f) else ""
            d, st = v.dosage(f[ei], oth, rec)
            if d is None:
                # phantom dose: how many NON-reference alleles stand in the row's GT — this
                # is how a positional matcher counts, without looking at the alleles
                rows_txt = []
                ph = 0
                for ref, alts, idx in rec:
                    ph = max(ph, sum(1 for i in idx if i > 0))
                    rows_txt.append(f"{ref}>{','.join(alts) or '.'} GT={'/'.join(map(str, idx))}")
                mism.append((chrom, f[pi], f[ei], oth, w, ph, "; ".join(rows_txt)))
                contrib_phantom += ph * w
                continue
            matched += 1
            contrib_honest += d * w
    print(f"\n  variants {n}, matched {matched}, misses {len(mism)}")
    for chrom, pos, eff, oth, w, ph, rows_txt in mism:
        print(f"  chr{chrom}:{pos}  model: eff={eff} oth={oth} w={w:+.3f} | our VCF: {rows_txt} | phantom dose {ph}")
    print(f"\n  honest score (allele-aware):               {contrib_honest:+.4f}")
    print(f"  contribution of misses under positional matching: {contrib_phantom:+.4f}")
    print(f"  score with the phantoms:                   {contrib_honest + contrib_phantom:+.4f}")

    print()
    print("=" * 70)
    print("QUESTION 3 — percentiles of both scores against the cached 1000G reference")
    print("=" * 70)
    try:
        import pyarrow.parquet as pq
    except ImportError:
        print("  pyarrow is missing: pip3 install --user pyarrow  — then rerun")
        return 0
    pf = CACHE / "percentiles" / "1000g_distributions.parquet"
    if not pf.exists():
        print(f"  no distribution file: {pf}")
        return 0
    tbl = pq.read_table(pf)
    cols = tbl.column_names
    print(f"  distribution columns: {cols}")
    rows = tbl.to_pylist()
    ours = [r for r in rows if str(r.get("pgs_id", r.get("id", ""))) == PID]
    print(f"  rows for {PID}: {len(ours)}")
    if not ours:
        print("  … the structure is unfamiliar — showing the first row for inspection:")
        print(" ", rows[0] if rows else "empty")
        return 0
    sample = ours[0]
    print(f"  sample row: { {k: sample[k] for k in list(sample)[:8]} }")
    # work out the format: either raw per-sample scores or a grid of quantiles
    num_keys = [k for k in sample if isinstance(sample[k], (int, float))]
    scores = None
    if "score" in sample:
        scores = sorted(r["score"] for r in ours if isinstance(r.get("score"), (int, float)))
    elif "value" in sample and ("percentile" in sample or "quantile" in sample):
        grid = sorted((r.get("percentile", r.get("quantile")), r["value"]) for r in ours)
        def pct(x):
            below = [p for p, val in grid if val <= x]
            return below[-1] if below else 0.0
        for name, s in (("honest", contrib_honest), ("phantom-inflated", contrib_honest + contrib_phantom)):
            print(f"  percentile of the {name} score ≈ {pct(s)}")
        return 0
    if scores:
        import bisect
        for name, s in (("honest", contrib_honest), ("phantom-inflated", contrib_honest + contrib_phantom)):
            p = 100.0 * bisect.bisect_left(scores, s) / len(scores)
            print(f"  percentile of the {name} score among {len(scores)} reference ones: {p:.2f}")
    else:
        print(f"  numeric fields of the row: {num_keys} — send the output over and the format can be worked out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
