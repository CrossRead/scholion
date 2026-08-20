#!/usr/bin/env python3
"""BED of the clinically significant regions — for re-calling variants with DeepVariant.

Why: a whole genome on Apple Silicon under x86 emulation takes a day or two, while the
entire clinical interpretation (ACMG SF, pharmacogenes, the locus catalog, MHC) lives
on ~0.5% of the genome. This BED lets the variants be re-called exactly there in hours.

Where the coordinates come from. NOT from memory: a gene's boundaries are taken as the
min/max of the positions of its variants in the local NCBI ClinVar VCF (the GENEINFO
field) with a ±10 kb margin. That is data, not recollection, and for genes with many
records (all 84 ACMG genes, the pharmacogenes) it covers the gene fully. Plus: catalog
positions from loci.json ±1 kb and the whole MHC region (chr6:28.48–33.45 Mb).

    python3 src/ingest/build_clinical_bed.py /tmp/clinical.bed
    SCHOLION_CLINVAR_VCF=~/genomic_work/clinvar/clinvar.vcf.gz  # override the source
"""
import gzip
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
K = ROOT / "src" / "scholion" / "knowledge"
MHC = ("6", 28477797, 33448354)
PAD_GENE, PAD_LOCUS = 10_000, 1_000
# GENEINFO can be the FIRST INFO field — then it is preceded by a tab, not ';'.
GI_RE = re.compile(r"[;\t]GENEINFO=([^;\s]*)")


def gene_list():
    genes = set(json.loads((K / "acmg_sf.json").read_text(encoding="utf-8"))["genes"])
    cpic = json.loads((K / "cpic_drug_gene.json").read_text(encoding="utf-8"))
    genes |= set(cpic.get("genes", {}) or {})
    genes |= set(cpic.get("genes_of_interest", []) or [])
    loci = json.loads((K / "loci.json").read_text(encoding="utf-8"))["loci"]
    genes |= {l.get("gene") for l in loci.values() if l.get("gene")}
    return genes, loci


def main(argv):
    out = Path(argv[1] if len(argv) > 1 else "/tmp/clinical.bed")
    cv = Path(os.environ.get("SCHOLION_CLINVAR_VCF", "~/genomic_work/clinvar/clinvar.vcf.gz")).expanduser()
    if not cv.exists():
        sys.exit(f"no ClinVar VCF: {cv} (SCHOLION_CLINVAR_VCF=...)")
    genes, loci = gene_list()
    print(f"genes in the list: {len(genes)} (ACMG SF + the CPIC pharmacogenes + the locus catalogue)")
    span = {}
    scanned = 0
    with gzip.open(cv, "rt", errors="replace") as fh:
        for line in fh:
            if line[0] == "#":
                continue
            scanned += 1
            m = GI_RE.search(line)
            if not m:
                continue
            hit = {p.split(":")[0] for p in m.group(1).split("|")} & genes
            if not hit:
                continue
            f = line.split("\t", 3)
            chrom, pos = f[0], int(f[1])
            for g in hit:
                c, lo, hi = span.get(g, (chrom, pos, pos))
                if c == chrom:
                    span[g] = (c, min(lo, pos), max(hi, pos))
    print(f"ClinVar records scanned: {scanned}; genes with coordinates: {len(span)}")
    missing = sorted(genes - set(span))
    if missing:
        print(f"⚠ genes with no ClinVar records (not in the BED via a span): {missing}")

    ivals = []
    for g, (c, lo, hi) in span.items():
        ivals.append((c, max(0, lo - PAD_GENE), hi + PAD_GENE, g))
    for rs, l in loci.items():
        c, p = str(l.get("chrom", "")), l.get("pos")
        if c and p:
            ivals.append((c, max(0, p - PAD_LOCUS), p + PAD_LOCUS, rs))
    ivals.append((MHC[0], MHC[1], MHC[2], "MHC"))

    # merge overlapping intervals within each chromosome
    def key(c):
        return (0, int(c)) if c.isdigit() else (1, {"X": 0, "Y": 1}.get(c, 2))
    ivals.sort(key=lambda r: (key(r[0]), r[1]))
    merged = []
    for c, lo, hi, name in ivals:
        if merged and merged[-1][0] == c and lo <= merged[-1][2]:
            pc, plo, phi, pn = merged[-1]
            merged[-1] = (c, plo, max(phi, hi), pn if name in pn else f"{pn},{name}")
        else:
            merged.append((c, lo, hi, name))
    total = sum(hi - lo for _, lo, hi, _ in merged)
    with out.open("w", encoding="utf-8") as fh:
        for c, lo, hi, name in merged:
            fh.write(f"chr{c}\t{lo}\t{hi}\t{name[:200]}\n")
    # WHAT THE PERCENTAGE WILL MEAN. Written beside the BED so that whatever
    # reads the coverage later can say what it was computed over, instead of
    # letting the reader assume it was the coding sequence. It was not: these
    # are gene LOCI with a 10 kb margin, so a 200 bp dropout inside a large gene
    # moves the number by a rounding error — in TTN, about 0.07 % — while being
    # exactly the thing the number is consulted about. Moving onto MANE Select
    # CDS plus splice sites is a pipeline change (`scholion sources` carries
    # MANE and the reason it is not a background refresh).
    meta = out.with_name("callability_meta.json")
    try:
        meta.write_text(json.dumps({
            "interval_basis": "gene_locus_plus_10kb",
            "pad_locus": PAD_LOCUS,
            "bounds_from": "ClinVar GENEINFO min/max per gene (local VCF)",
            "intervals": len(merged), "bases": total,
            "known_limitation": "a percentage over a whole locus is insensitive to a small "
                                "dropout inside the coding sequence, which is the case it is "
                                "usually consulted about",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✓ {meta}: what the coverage percentage is computed over")
    except OSError as e:
        print(f"! could not write {meta}: {e}")
    print(f"✓ {out}: intervals {len(merged)}, {total/1e6:.1f} Mb in total "
          f"({100*total/3.1e9:.2f}% of the genome)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
