#!/usr/bin/env python3
"""Extract scoring positions from the just-prs cache → BED for re-genotyping.

Reads ~/Library/Caches/just-prs/scores/*_hmPOS_GRCh38.txt.gz (PGS Catalog harmonised
to GRCh38), collects the union of positions (hm_chr/hm_pos), excludes genome-wide
models (>MAX_VARIANTS), writes a BED (chr notation). stdlib only.

    python3 prs_extract_sites.py [out.bed]
    MAX_VARIANTS=50000 python3 prs_extract_sites.py out.bed
"""
import csv, glob, gzip, os, sys

CACHE = os.path.expanduser("~/Library/Caches/just-prs/scores")
OUT = sys.argv[1] if len(sys.argv) > 1 else "scoring_sites.bed"
MAX_VARIANTS = int(os.environ.get("MAX_VARIANTS", "50000"))

# The reference is GRCh38_no_alt (without alt/patch contigs), so only canonical
# chromosomes are let into the BED. Positions on chrN_..._alt/_random/chrUn_* are not
# found in the BAM by mpileup and break the pipe. MT is folded to M (as in the no-alt set).
CANON = {str(i) for i in range(1, 23)} | {"X", "Y", "M"}


def _canon(chrom):
    """Return the canonical 'chrN', or None if the contig is not in the primary set."""
    c = str(chrom)
    c = c[3:] if c.startswith("chr") else c
    if c == "MT":
        c = "M"
    return "chr" + c if c in CANON else None


def _cols(header):
    idx = {c: i for i, c in enumerate(header)}
    ci = idx.get("hm_chr", idx.get("chr_name"))
    pi = idx.get("hm_pos", idx.get("chr_position"))
    return ci, pi


def main():
    files = sorted(glob.glob(os.path.join(CACHE, "*_hmPOS_GRCh38.txt.gz")))
    positions = set()
    skipped = []
    used = 0
    noncanon = 0  # positions dropped as belonging to non-canonical contigs
    for f in files:
        pgs = os.path.basename(f).split("_")[0]
        try:
            fh = gzip.open(f, "rt")
        except Exception as e:
            skipped.append((pgs, f"open: {e}")); continue
        with fh:
            header = None
            for line in fh:
                if line.startswith("#"):
                    continue
                header = line.rstrip("\n").split("\t"); break
            if not header:
                skipped.append((pgs, "no header")); continue
            ci, pi = _cols(header)
            if ci is None or pi is None:
                skipped.append((pgs, "no position columns")); continue
            local = []
            for line in fh:
                p = line.rstrip("\n").split("\t")
                if len(p) <= max(ci, pi):
                    continue
                chrom, pos = p[ci], p[pi]
                if not chrom or not pos or not pos.lstrip("-").isdigit():
                    continue
                local.append((chrom, int(pos)))
        if len(local) > MAX_VARIANTS:
            skipped.append((pgs, f"genome-wide ({len(local)} variants)")); continue
        used += 1
        for chrom, pos in local:
            c = _canon(chrom)
            if c is None:
                noncanon += 1
                continue
            positions.add((c, pos))

    def key(x):
        c = x[0][3:]
        order = {"X": 23, "Y": 24, "M": 25, "MT": 25}
        if c in order:
            return (order[c], x[1])
        if c.isdigit():
            return (int(c), x[1])
        return (99, x[1])

    rows = sorted(positions, key=key)
    with open(OUT, "w") as o:
        for c, pos in rows:
            o.write(f"{c}\t{pos - 1}\t{pos}\n")
    print(f"scoring files: {len(files)}; models used: {used}; "
          f"unique positions: {len(rows)}")
    if noncanon:
        print(f"positions dropped on non-canonical contigs (alt/random/Un): {noncanon}")
    print(f"BED: {OUT}")
    if skipped:
        gw = [s for s in skipped if "genome-wide" in s[1]]
        print(f"models skipped: {len(skipped)} (including genome-wide: {len(gw)})")
        for pgs, why in skipped[:15]:
            print(f"  {pgs}: {why}")


if __name__ == "__main__":
    main()
