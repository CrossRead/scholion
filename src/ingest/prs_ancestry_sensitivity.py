#!/usr/bin/env python3
"""Task #10, step 2: sensitivity of the PGS percentiles to the choice of reference population.

For every pinned model (knowledge/prs_models.json) the HONEST score is computed
(allele-aware matching, the same path as in prs_verify/sle_p100_debug) together with
its percentile against EACH of the five 1000G superpopulations from the just-prs cache
(a normal approximation from the distribution's mean/std). The spread of the percentile
across populations = the trait's sensitivity to the choice of reference.

Reading the result:
  - if ancestry_check returned a confident EUR, the correct column is EUR (our current
    reference), while the spread shows WHAT WOULD HAPPEN if the reference were wrong;
  - a large spread with a confident EUR is not a problem but an argument that choosing
    the reference matters (and that we chose correctly);
  - a percentile from the normal approximation can diverge from the exact one in the tails —
    compare the columns with one another, not with the previous exact percentile.

Run on the Mac (needs the just-prs cache and pyarrow):
    python3 src/ingest/prs_ancestry_sensitivity.py
Output: profile/prs_ancestry_sensitivity.json + a table. PERSONAL — goes to profile/.
"""
from __future__ import annotations
import gzip, importlib.util, json, math, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path.home() / "Library" / "Caches" / "just-prs"
VCF = ROOT / "genome" / "scoring_sites_ext.fixed.vcf.gz"
MODELS = ROOT / "src" / "scholion" / "knowledge" / "prs_models.json"
OUT = ROOT / "profile" / "prs_ancestry_sensitivity.json"
SUPERPOPS = ("AFR", "AMR", "EAS", "EUR", "SAS")

try:
    import pandas as pd
except ImportError:
    sys.exit("❌ pandas is required:  pip3 install --user 'pandas<3' pyarrow")

spec = importlib.util.spec_from_file_location("prs_verify", ROOT / "src" / "ingest" / "prs_verify.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

for p in (VCF, MODELS):
    if not p.exists():
        sys.exit(f"❌ missing input: {p}")
PARQ = CACHE / "percentiles" / "1000g_distributions.parquet"
if not PARQ.exists():
    sys.exit(f"❌ no 1000G distributions: {PARQ}")


def phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def honest_score(model_path, geno):
    """Sum of w×dose under allele-aware matching; misses and absences are skipped."""
    total = 0.0
    n = used = 0
    with gzip.open(model_path, "rt", errors="replace") as fh:
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
            if ci is None or pi is None or ei is None or wi is None:
                return None, 0, 0
            chrom = f[ci][3:] if f[ci].startswith("chr") else f[ci]
            rec = geno.get((chrom, f[pi]))
            if not rec:
                continue
            oth = f[oi] if oi is not None and oi < len(f) else ""
            d, _st = v.dosage(f[ei], oth, rec)
            if d is None:
                continue
            try:
                total += d * float(f[wi])
            except ValueError:
                continue
            used += 1
    return total, n, used


def main():
    print("loading the re-genotyped VCF…")
    geno, _dup, _dp = v.load_target(VCF)
    df = pd.read_parquet(PARQ)
    models = json.loads(MODELS.read_text())["models"]

    rows, skipped = [], []
    for term, m in sorted(models.items()):
        pid = m["pgs_id"]
        mp = CACHE / "scores" / f"{pid}_hmPOS_GRCh38.txt.gz"
        if not mp.exists():
            skipped.append((term, pid, "model not in the cache"))
            continue
        s, n, used = honest_score(mp, geno)
        if s is None or used == 0:
            skipped.append((term, pid, "the score was not computed"))
            continue
        sub = df[df["pgs_id"] == pid]
        pcts = {}
        for sp in SUPERPOPS:
            r = sub[sub["superpopulation"] == sp]
            if len(r) != 1:
                continue
            mean, std = float(r["mean"].iloc[0]), float(r["std"].iloc[0])
            if std <= 0:
                continue
            pcts[sp] = round(100.0 * phi((s - mean) / std), 1)
        if len(pcts) < len(SUPERPOPS):
            skipped.append((term, pid, f"distributions are missing for some populations ({sorted(pcts)})"))
            continue
        spread = max(pcts.values()) - min(pcts.values())
        rows.append({"term": term, "label": m.get("label", term), "pgs_id": pid,
                     "score": round(s, 4), "variants_used": used,
                     "pct_by_pop": pcts, "eur": pcts["EUR"], "spread": round(spread, 1)})

    rows.sort(key=lambda r: -r["spread"])
    print(f"\nmodels computed: {len(rows)}, skipped: {len(skipped)}")
    print(f"{'trait':34} {'EUR':>6} " + " ".join(f"{p:>6}" for p in SUPERPOPS if p != 'EUR') + f" {'spread':>8}")
    for r in rows[:20]:
        others = " ".join(f"{r['pct_by_pop'][p]:6.1f}" for p in SUPERPOPS if p != "EUR")
        print(f"{r['label'][:34]:34} {r['eur']:6.1f} {others} {r['spread']:8.1f}")
    if len(rows) > 20:
        print(f"  … and {len(rows) - 20} more (in full — in the JSON)")

    spreads = sorted(r["spread"] for r in rows)
    med = spreads[len(spreads) // 2] if spreads else 0
    big = [r for r in rows if r["spread"] >= 30]
    print(f"\nmedian spread between populations: {med:.1f} pp; traits with a spread ≥30 pp: {len(big)}")
    for term, pid, why in skipped:
        print(f"  skipped: {term} ({pid}) — {why}")

    OUT.write_text(json.dumps({
        "date": pd.Timestamp.today().strftime("%Y-%m-%d"),
        "method": "the honest score (prs_verify.dosage) × a normal approximation of the 1000G "
                  "distributions from the just-prs cache; compare the percentiles BETWEEN the "
                  "columns, not against the exact ones in the profile",
        "median_spread": med,
        "traits": rows,
        "skipped": [{"term": t, "pgs_id": p, "why": w} for t, p, w in skipped],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ {OUT}")


if __name__ == "__main__":
    main()
