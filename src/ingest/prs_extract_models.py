#!/usr/bin/env python3
"""Extract the FULL positions of specific PGS models (for the genome-wide models that
prs_extract_sites.py drops on the threshold). Optionally merge with an existing BED.

Needed when a trait has only genome-wide models in the catalog: to obtain a
reliable score, EXACTLY their positions are re-genotyped from merged.bam (including 0/0).

    python3 prs_extract_models.py <out.bed> PGS004528 PGS002782 ...
    MERGE_BED=/tmp/scoring_sites.bed python3 prs_extract_models.py <out.bed> PGS000378 ...

stdlib only. Reads the cache ~/Library/Caches/just-prs/scores/*_hmPOS_GRCh38.txt.gz.
"""
import glob, gzip, os, sys

CACHE = os.path.expanduser("~/Library/Caches/just-prs/scores")
CANON = {str(i) for i in range(1, 23)} | {"X", "Y", "M"}


def _cols(header):
    idx = {c: i for i, c in enumerate(header)}
    return idx.get("hm_chr", idx.get("chr_name")), idx.get("hm_pos", idx.get("chr_position"))


def _canon(chrom):
    c = str(chrom)
    c = c[3:] if c.startswith("chr") else c
    if c == "MT":
        c = "M"
    return "chr" + c if c in CANON else None


def _positions_of(pgs):
    """All positions of model pgs taken from its scoring file in the cache."""
    hits = glob.glob(os.path.join(CACHE, f"{pgs}_*hmPOS_GRCh38.txt.gz"))
    if not hits:
        return None
    out = set()
    with gzip.open(hits[0], "rt") as fh:
        header = None
        for line in fh:
            if line.startswith("#"):
                continue
            header = line.rstrip("\n").split("\t"); break
        if not header:
            return set()
        ci, pi = _cols(header)
        if ci is None or pi is None:
            return set()
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) <= max(ci, pi):
                continue
            c = _canon(p[ci])
            if c and p[pi].lstrip("-").isdigit():
                out.add((c, int(p[pi])))
    return out


def _read_bed(path):
    out = set()
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 3 and parts[2].isdigit():
                out.add((parts[0], int(parts[2])))
    return out


def key(x):
    c = x[0][3:]
    order = {"X": 23, "Y": 24, "M": 25}
    if c in order:
        return (order[c], x[1])
    if c.isdigit():
        return (int(c), x[1])
    return (99, x[1])


def main():
    if len(sys.argv) < 3:
        print("usage: prs_extract_models.py <out.bed> PGS.... [PGS....]"); sys.exit(1)
    out_bed = sys.argv[1]
    pgs_ids = sys.argv[2:]
    positions = set()
    merge = os.environ.get("MERGE_BED")
    if merge and os.path.exists(merge):
        base = _read_bed(merge)
        positions |= base
        print(f"merged from {merge}: {len(base)} positions")
    for pgs in pgs_ids:
        pos = _positions_of(pgs)
        if pos is None:
            print(f"  ⚠ {pgs}: the scoring file was not found in the cache — skipped")
            continue
        print(f"  {pgs}: {len(pos)} positions")
        positions |= pos
    rows = sorted(positions, key=key)
    with open(out_bed, "w") as o:
        for c, p in rows:
            o.write(f"{c}\t{p-1}\t{p}\n")
    print(f"✓ unique positions in the union: {len(rows)}")
    print(f"BED: {out_bed}")
    print(f"Next: OUT=<project>/genome/scoring_sites_ext.vcf.gz caffeinate -imsu bash prs_genotype_sites.sh {out_bed}")


if __name__ == "__main__":
    main()
