#!/usr/bin/env python3
"""BED of every position from knowledge/loci.json — to re-genotype them from the BAM.

Why: the full VCF was called with -v, so it holds only positions with a variant. If a
locus is absent there, the engine marks the genotype assumed_ref — and that is "reference
OR no coverage", two different things. Running this BED through prs_genotype_sites.sh (a
call WITHOUT -v) yields real 0/0 with depth, and "reference" stops being an assumption.

    python3 src/ingest/loci_sites_bed.py /tmp/loci_sites.bed
    OUT=genome/loci_sites.vcf.gz bash src/ingest/prs_genotype_sites.sh /tmp/loci_sites.bed

Coordinates come from the catalog (GRCh38, 1-based) and are written to BED (0-based,
half-open interval) in chr notation — the same way prs_extract_sites.py does it. This is
mandatory: the GRCh38_no_alt reference and the BAM use contigs chr1..chr22/chrX, and
bcftools mpileup -R with a bare "1" will find nothing.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "src" / "scholion" / "knowledge" / "loci.json"
CANON = {str(i) for i in range(1, 23)} | {"X", "Y", "M", "MT"}


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/loci_sites.bed")
    loci = json.loads(CATALOG.read_text(encoding="utf-8")).get("loci", {})
    rows = []
    for rsid, l in loci.items():
        chrom, pos = l.get("chrom"), l.get("pos")
        if not chrom or not pos:
            print(f"skipping {rsid}: no coordinate", file=sys.stderr)
            continue
        c = str(chrom)
        c = c[3:] if c.startswith("chr") else c
        if c not in CANON:
            print(f"skipping {rsid}: non-canonical chromosome {chrom}", file=sys.stderr)
            continue
        rows.append((c, int(pos), rsid, l.get("gene", "")))

    def key(r):
        c = r[0]
        return (0, int(c)) if c.isdigit() else (1, 0 if c == "X" else 1 if c == "Y" else 2)

    rows.sort(key=lambda r: (key(r), r[1]))
    with out.open("w", encoding="utf-8") as fh:
        for chrom, pos, rsid, gene in rows:
            fh.write(f"chr{chrom}\t{pos - 1}\t{pos}\t{rsid}|{gene}\n")
    print(f"{out}: {len(rows)} positions from {CATALOG.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
