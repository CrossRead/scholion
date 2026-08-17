#!/usr/bin/env python3
"""Audit of the tail PGS percentiles: technical validity of the models on OUR data.

For every trait with an extreme percentile it computes, using the pinned model:
  · coverage and the number of allele misses (a model's variant is described by no
    row of the position — at multi-allelic sites this is the main source of errors);
  · the share of |contribution| from the MHC region (chr6:28.5–33.4 Mb): HLA-driven
    models (coeliac disease, lupus, psoriasis) are sensitive to errors exactly there;
  · the top contributions — which loci in particular produced the percentile.

Run on the Mac (the cache ~/Library/Caches/just-prs/scores is required):
    python3 src/ingest/prs_top_audit.py            # the tails P>=80 and P<=5
    python3 src/ingest/prs_top_audit.py PGS000040  # specific models
"""
import gzip
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MHC = (28477797, 33448354)

spec = importlib.util.spec_from_file_location("prs_verify", ROOT / "src" / "ingest" / "prs_verify.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def main(argv):
    prof = json.loads((ROOT / "profile" / "prs_results.json").read_text(encoding="utf-8"))
    cache = Path.home() / "Library" / "Caches" / "just-prs" / "scores"
    files = {p.name.split("_")[0]: p for p in cache.glob("*.txt.gz")}
    if not files:
        sys.exit(f"the model cache is empty: {cache} — run this on the owner's machine")
    want_ids = set(argv[1:])
    traits = []
    for t in prof.get("traits", []):
        p = t.get("percentile")
        if want_ids and t.get("pgs_id") in want_ids:
            traits.append(t)
        elif not want_ids and isinstance(p, (int, float)) and (p >= 80 or p <= 5):
            traits.append(t)
    vcf = ROOT / "genome" / "scoring_sites_ext.fixed.vcf.gz"
    if not vcf.exists():
        vcf = ROOT / "genome" / "scoring_sites_ext.vcf.gz"
    geno, dup, dp = v.load_target(vcf)
    print(f"target: {vcf.name}, positions {len(geno)}\n")
    print(f"{'trait':34}{'P':>7} {'model':11}{'vars':>7}{'cov':>6}{'miss':>5}{'MHC%':>6}{'MHCmiss':>8}  top contributions")
    for t in sorted(traits, key=lambda x: -(x.get("percentile") or 0)):
        pid = t.get("pgs_id")
        p = files.get(pid)
        if not p:
            print(f"{t['label'][:34]:34}{t.get('percentile')!s:>7} {pid} — model not in the cache")
            continue
        tot = mhc = 0.0
        n = matched = mism = mhc_mism = 0
        top = []
        with gzip.open(p, "rt", errors="replace") as fh:
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
                try:
                    chrom = f[ci][3:] if f[ci].startswith("chr") else f[ci]
                    rec = geno.get((chrom, f[pi]))
                    w = float(f[wi])
                except Exception:
                    continue
                in_mhc = chrom == "6" and MHC[0] <= int(f[pi]) <= MHC[1]
                if not rec:
                    continue
                oth = f[oi] if oi is not None and oi < len(f) else ""
                d, st = v.dosage(f[ei], oth, rec)
                if d is None:
                    mism += 1
                    mhc_mism += 1 if in_mhc else 0
                    continue
                matched += 1
                c = d * w
                tot += abs(c)
                if in_mhc:
                    mhc += abs(c)
                if c:
                    top.append((abs(c), f"chr{chrom}:{f[pi]} w={w:+.2f}×{d}"))
        top.sort(reverse=True)
        share = 100 * mhc / tot if tot else 0
        print(f"{t['label'][:34]:34}{t.get('percentile')!s:>7} {pid:11}{n:>7}{(matched/n if n else 0):>6.2f}"
              f"{mism:>5}{share:>5.0f}%{mhc_mism:>8}  {'; '.join(x[1] for x in top[:3])}")
    print("\nHow to read this: a high MHC% + misses in MHC = the percentile leans on a region where short")
    print("reads and multi-allelic sites are unreliable; few variants = a coarse, stepped percentile scale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
