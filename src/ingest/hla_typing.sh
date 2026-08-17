#!/usr/bin/env bash
# Task #5: HLA typing from WGS (T1K) — class I and II at allele level.
#
# Why: four pharmaco-alleles of drug hypersensitivity that neither the tag-SNP
# catalogue nor PyPGx/PharmCAT provides:
#   HLA-B*57:01 — abacavir;  HLA-B*15:02 and HLA-A*31:01 — carbamazepine;
#   HLA-B*58:01 — allopurinol (an open item from future_flags).
# As a bonus: HLA-C*06:02 (psoriasis — cross-checked against the rs10484554 tag and
# the PGS control), DQA1/DQB1 (cross-checked against any earlier allele-level typing
# from a laboratory report).
#
# Tool: T1K (github.com/mourisl/T1K) — builds with make on Apple Silicon and reads
# WGS. The allele reference is built from a fresh IPD-IMGT/HLA database (downloads
# ~2–3 GB). The reads are extracted here: the chr6 MHC region plus fully unmapped
# pairs (the reference used here is no-alt, so the HLA reads sit on chr6 of the
# primary assembly, not on alt contigs).
#
# Time: build+reference ~10–20 min (network), read extraction ~10–20 min,
# typing ~20–40 min. The script is resumable: completed steps are skipped.
set -euo pipefail
. "$(dirname "$0")/_sample.sh"
BAM="${BAM:-$HOME/genomic_work/$SAMPLE/$SAMPLE.merged.bam}"
HLA="${HLA_DIR:-$HOME/genomic_work/hla}"
PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
THREADS="$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"
# MHC with a margin: chr6:28,000,000–34,000,000 (GRCh38)
MHC_REGION="chr6:28000000-34000000"

echo "== Pre-flight check =="
command -v git >/dev/null || { echo "❌ git is missing"; exit 1; }
command -v make >/dev/null || { echo "❌ make is missing (xcode-select --install)"; exit 1; }
command -v perl >/dev/null || { echo "❌ perl is missing"; exit 1; }
command -v samtools >/dev/null || { echo "❌ samtools is missing: brew install samtools"; exit 1; }
[ -f "$BAM" ] || { echo "❌ no BAM: $BAM"; exit 1; }
[ -f "$BAM.bai" ] || [ -f "${BAM%.bam}.bai" ] || { echo "❌ no BAM index (.bai): samtools index \"$BAM\""; exit 1; }
mkdir -p "$HLA"
echo "OK; work directory $HLA, threads: $THREADS"

T1K="$HLA/T1K"
if [ ! -x "$T1K/run-t1k" ]; then
  echo "== Step 1/4: building T1K =="
  [ -d "$T1K" ] || git clone https://github.com/mourisl/T1K.git "$T1K"
  ( cd "$T1K" && make )
else echo "== Step 1/4: T1K is built — skipping =="; fi

IDX="$HLA/hlaidx"
# A T1K trap: without --prefix it takes «the first component of the -o path», and for
# an absolute path that is an empty string — so the files come out as "_dna_seq.fa".
# Such files from an earlier run are picked up (the build was valid, only the name
# differed) and from then on the index is always built with an explicit --prefix hlaidx.
[ -s "$IDX/_dna_seq.fa" ] && [ ! -s "$IDX/hlaidx_dna_seq.fa" ] && mv "$IDX/_dna_seq.fa" "$IDX/hlaidx_dna_seq.fa"
[ -s "$IDX/_rna_seq.fa" ] && [ ! -s "$IDX/hlaidx_rna_seq.fa" ] && mv "$IDX/_rna_seq.fa" "$IDX/hlaidx_rna_seq.fa"
if [ ! -s "$IDX/hlaidx_dna_seq.fa" ]; then
  echo "== Step 2/4: allele reference from IPD-IMGT/HLA (downloads ~2–3 GB) =="
  ( cd "$T1K" && perl t1k-build.pl -o "$IDX" --prefix hlaidx --download IPD-IMGT/HLA )
else echo "== Step 2/4: reference present — skipping =="; fi

R1="$HLA/${SAMPLE}_hla_1.fq.gz"; R2="$HLA/${SAMPLE}_hla_2.fq.gz"
if [ ! -s "$R1" ] || [ ! -s "$R2" ]; then
  echo "== Step 3/4: read extraction (MHC + unmapped pairs) =="
  # the MHC region plus fully unmapped pairs (flag 12 = read+mate unmapped);
  # collate groups the pairs, fastq splits them by mate. Singletons are dropped (-s /dev/null).
  samtools view -u -@ "$THREADS" "$BAM" "$MHC_REGION" > "$HLA/mhc.bam"
  echo "  … unmapped pairs: a full pass over the BAM (tens of GB) — the longest part of this step"
  samtools view -u -@ "$THREADS" -f 12 "$BAM" > "$HLA/unmapped.bam"
  samtools cat -o "$HLA/hla_cand.bam" "$HLA/mhc.bam" "$HLA/unmapped.bam"
  samtools collate -@ "$THREADS" -u -O "$HLA/hla_cand.bam" | \
    samtools fastq -@ "$THREADS" -1 "$R1" -2 "$R2" -s /dev/null -0 /dev/null -n -
  rm -f "$HLA/mhc.bam" "$HLA/unmapped.bam" "$HLA/hla_cand.bam"
  echo "  read pairs: $(( $(gzcat "$R1" | wc -l) / 4 ))"
else echo "== Step 3/4: reads already extracted — skipping =="; fi

OUT="$HLA/out"
if [ ! -s "$OUT/${SAMPLE}_genotype.tsv" ]; then
  echo "== Step 4/4: T1K typing (the WGS preset) =="
  mkdir -p "$OUT"
  "$T1K/run-t1k" -1 "$R1" -2 "$R2" --preset hla-wgs \
    -f "$IDX/hlaidx_dna_seq.fa" -t "$THREADS" -o "$SAMPLE" --od "$OUT"
else echo "== Step 4/4: result present — skipping =="; fi

echo "== Collecting the results =="
python3 - "$OUT/${SAMPLE}_genotype.tsv" "$PROJECT" <<'PY'
import sys
from pathlib import Path

src, project = Path(sys.argv[1]), Path(sys.argv[2])
rows = []
for line in src.read_text().splitlines():
    f = line.rstrip("\n").split("\t")
    if len(f) < 8:
        continue
    gene, n = f[0], f[1]
    def allele(i):
        # triples (allele, abundance, quality); T1K advises ignoring quality<=0
        if len(f) <= i or f[i] in (".", "", "-"):
            return None
        try: q = float(f[i+2])
        except (ValueError, IndexError): q = 0.0
        return (f[i], q)
    rows.append((gene, allele(2), allele(5)))

def two_field(name):
    # HLA-B*57:01:01:02 -> B*57:01
    if not name or "*" not in name: return name or ""
    g, rest = name.split("*", 1)
    return g.replace("HLA-", "") + "*" + ":".join(rest.split(":")[:2])

tsv = project / "profile" / "hla_typing.tsv"
carried = set()
with tsv.open("w", encoding="utf-8") as fh:
    fh.write("gene\tallele1\tquality1\tallele2\tquality2\n")
    for gene, a1, a2 in rows:
        c1 = (two_field(a1[0]), a1[1]) if a1 else ("", 0.0)
        c2 = (two_field(a2[0]), a2[1]) if a2 else ("", 0.0)
        for al, q in (c1, c2):
            if al and q > 0: carried.add(al)
        fh.write(f"{gene}\t{c1[0]}\t{c1[1]:g}\t{c2[0]}\t{c2[1]:g}\n")
        print(f"  {gene:10} {c1[0]:16} q={c1[1]:g}\t{c2[0]:16} q={c2[1]:g}")
print(f"\n✓ {tsv}")

print("\n== Hypersensitivity pharmaco-alleles ==")
targets = [
    ("B*57:01",  "abacavir: contraindicated in carriers (CPIC strong)"),
    ("B*15:02",  "carbamazepine/oxcarbazepine: SJS/TEN (clinically relevant mainly in South-East Asia)"),
    ("A*31:01",  "carbamazepine: DRESS/SJS in Europeans"),
    ("B*58:01",  "allopurinol: SCAR — closes the open item in future_flags"),
    ("C*06:02",  "psoriasis: cross-check against the rs10484554 tag and the PGS control"),
]
for al, note in targets:
    status = "CARRIER" if al in carried else "not a carrier"
    print(f"  {al:9} {status:13} — {note}")
print("\nCompare class II against any earlier allele-level typing from a laboratory report — by eye, from the table above.")
print("Next, the assistant folds this into profile/pharmacogenomics.json (the hla section) and updates future_flags.")
PY
