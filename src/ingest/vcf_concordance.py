#!/usr/bin/env python3
"""Comparison of two VCFs (bcftools against DeepVariant) — the basis of the replacement decision.

Computes for each file and for their intersection:
  · the number of SNVs and indels, Ts/Tv (a healthy WGS range is ≈ 2.0–2.1; below that is noise);
  · genotype concordance at the shared positions (restricted to the region of the second
    file if that one is regional — so the comparison is fair, not "whole against a fragment");
  · the genotypes of the loci.json catalog in both files side by side — a discrepancy here
    outweighs any statistic: these are the positions the conclusions were drawn from;
  · where they diverge: SNVs or indels (indel discrepancies are expected — DeepVariant
    was taken up precisely because of them).

    python3 src/ingest/vcf_concordance.py genome/<SAMPLE>.full.vcf.gz genome/<SAMPLE>.dv_clinical.vcf.gz

Changes nothing and decides nothing: it prints the data for the decision.
"""
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TS = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}


def _open(p):
    return gzip.open(p, "rt", errors="replace") if str(p).endswith(".gz") else open(p, encoding="utf-8")


def load(vcf, region_keys=None):
    """{(chrom,pos): [(ref,alt,gt), ...]}; counts snv/indel/ts/tv along the way."""
    data, snv, indel, ts, tv = {}, 0, 0, 0, 0
    with _open(vcf) as fh:
        for line in fh:
            if line[0] == "#":
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 10:
                continue
            chrom = f[0][3:] if f[0].startswith("chr") else f[0]
            key = (chrom, f[1])
            if region_keys is not None and key not in region_keys:
                continue
            gt = f[9].split(":")[0].replace("|", "/")
            if gt in ("./.", "."):
                continue
            for alt in f[4].split(","):
                if alt in (".", "<*>"):
                    continue
                if len(f[3]) == 1 and len(alt) == 1:
                    snv += 1
                    if (f[3].upper(), alt.upper()) in TS:
                        ts += 1
                    else:
                        tv += 1
                else:
                    indel += 1
                data.setdefault(key, []).append((f[3].upper(), alt.upper(), gt))
    return data, snv, indel, ts, tv


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    a_path, b_path = Path(argv[1]), Path(argv[2])
    print(f"A (baseline):    {a_path.name}")
    print(f"B (challenger):  {b_path.name}\n")

    b, b_snv, b_indel, b_ts, b_tv = load(b_path)
    # A is restricted to the positions B actually looked at (for a regional B)
    a, a_snv, a_indel, a_ts, a_tv = load(a_path, region_keys=None)
    keys_a, keys_b = set(a), set(b)

    def tstv(ts_, tv_):
        return ts_ / tv_ if tv_ else 0

    print(f"{'':22}{'SNV':>10}{'indels':>10}{'Ts/Tv':>8}")
    print(f"{'A in full':22}{a_snv:>10}{a_indel:>10}{tstv(a_ts, a_tv):>8.2f}")
    print(f"{'B in full':22}{b_snv:>10}{b_indel:>10}{tstv(b_ts, b_tv):>8.2f}")

    both = keys_a & keys_b
    only_a = keys_a - keys_b
    only_b = keys_b - keys_a
    agree = diff_gt = diff_allele = 0
    diff_snv = diff_indel = 0
    examples = []
    for k in both:
        va = {(r, alt) for r, alt, g in a[k]}
        vb = {(r, alt) for r, alt, g in b[k]}
        ga = sorted(g for _, _, g in a[k])
        gb = sorted(g for _, _, g in b[k])
        if va == vb and ga == gb:
            agree += 1
            continue
        is_indel = any(len(r) > 1 or len(x) > 1 for r, x in va | vb)
        if is_indel:
            diff_indel += 1
        else:
            diff_snv += 1
        if va != vb:
            diff_allele += 1
        else:
            diff_gt += 1
        if len(examples) < 8:
            examples.append((k, a[k], b[k]))

    print(f"\nshared variant positions: {len(both)}")
    print(f"  full agreement: {agree} ({100*agree/len(both) if both else 0:.1f}%)")
    print(f"  alleles differ: {diff_allele}; genotype differs: {diff_gt} "
          f"(of them SNVs {diff_snv}, indels {diff_indel})")
    print(f"only in A: {len(only_a)}; only in B: {len(only_b)} "
          f"(for a regional B, «only in A» outside its regions is normal)")
    if examples:
        print("\nexamples of discrepancies (the first 8):")
        for k, ra, rb in examples:
            print(f"  chr{k[0]}:{k[1]}  A={ra}  B={rb}")

    print("\n— The loci.json catalogue side by side —")
    loci = json.loads((ROOT / "src" / "scholion" / "knowledge" / "loci.json").read_text(encoding="utf-8"))["loci"]
    mism = 0
    for rs, l in sorted(loci.items(), key=lambda x: (str(x[1].get("chrom")), x[1].get("pos", 0))):
        k = (str(l["chrom"]), str(l["pos"]))
        ra = a.get(k, [("—", "—", "ref/absent")])
        rb = b.get(k, [("—", "—", "ref/absent")])
        sa = ",".join(f"{r}>{x}:{g}" for r, x, g in ra)
        sb = ",".join(f"{r}>{x}:{g}" for r, x, g in rb)
        mark = ""
        if sa != sb:
            mism += 1
            mark = "  ← DISCREPANCY"
        print(f"  {rs:13} {l.get('gene',''):9} A: {sa:24} B: {sb}{mark}")
    print(f"\ncatalogue discrepancies: {mism} "
          f"{'— review every one of them before any replacement decision' if mism else '— the catalogue is stable'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
