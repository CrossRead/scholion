#!/usr/bin/env bash
# Re-genotype the PGS scoring positions from merged.bam — ALL sites, including 0/0.
# This fixes PGS coverage: in the main VCF (variants only) the reference-homozygous
# scoring positions are absent → just-prs counts them as «not covered». Here bcftools
# is called over the position list WITHOUT -v → the output contains 0/0 as well.
#   bash prs_genotype_sites.sh <scoring_sites.bed>
set -euo pipefail
. "$(dirname "$0")/_sample.sh"
BED="${1:?a BED with the scoring positions}"
WORKDIR="${WORKDIR:-$HOME/genomic_work/$SAMPLE}"
REF="${REF_FASTA:-$HOME/genomic_work/reference/GRCh38_no_alt.fa}"
BAM="${BAM:-$WORKDIR/$SAMPLE.merged.bam}"
OUTDIR="$(cd "$(dirname "$0")/../.." && pwd)/genome"
OUT="${OUT:-$OUTDIR/scoring_sites.vcf.gz}"
for t in bcftools samtools; do command -v "$t" >/dev/null || { echo "$t is missing"; exit 1; }; done
[ -f "$BAM" ] || { echo "❌ no BAM: $BAM"; exit 1; }
[ -f "$BAM.bai" ] || { echo "→ indexing the BAM…"; samtools index "$BAM"; }
mkdir -p "$OUTDIR"
N=$(wc -l < "$BED" | tr -d ' ')
echo "→ re-genotyping $N scoring positions from $(basename "$BAM") (all sites, incl. 0/0)…"
bcftools mpileup -R "$BED" -f "$REF" -a FORMAT/DP -Ou "$BAM" \
  | bcftools call -m -Oz -o "$OUT"
bcftools index -t "$OUT"
# Collapse the contested positions: at one coordinate mpileup can emit both an
# SNP-level row AND an indel row. Naive PGS counters (just-prs) count EVERY row of a
# position — the weight is counted twice and coverage comes out >1. The choice of row
# is allele-dependent, driven by the cached models (SNP models — the SNP row, indels —
# the indel row).
CACHE_DIR="${SCHOLION_PRS_CACHE:-$HOME/Library/Caches/just-prs/scores}"
if [ -d "$CACHE_DIR" ] && ls "$CACHE_DIR"/*.txt.gz >/dev/null 2>&1; then
  TMPFIX="${OUT%.vcf.gz}.fixing.vcf"
  python3 "$(cd "$(dirname "$0")" && pwd)/prs_verify.py" --emit-fixed "$TMPFIX" --vcf "$OUT"
  bgzip -f "$TMPFIX"
  mv "$TMPFIX.gz" "$OUT"
  bcftools index -f -t "$OUT"
  echo "✓ contested positions collapsed (one row per coordinate, allele-dependent)"
else
  echo "⚠ the model cache is empty ($CACHE_DIR): the contested positions were NOT collapsed."
  echo "  After the first 'prs report' (which fills the cache) rerun this script."
fi
echo "✓ $OUT"
echo "  records: $(bcftools view -H "$OUT" | wc -l | tr -d ' ')"
echo "Next: PYTHONPATH=src python3 -m scholion.prs report --vcf \"$OUT\" > profile/prs_report_raw.json"
echo "        python3 src/ingest/prs_results_build.py profile/prs_report_raw.json"
