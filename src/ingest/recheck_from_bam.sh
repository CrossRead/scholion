#!/bin/bash
# Re-checking contested positions straight from the BAM.
# It is needed because the absence of a record in a VCF means EITHER a reference
# homozygote OR no coverage — from the VCF alone the two cases are indistinguishable.
# Run it from the project folder. The BAM and the reference live in ~/genomic_work.
set -euo pipefail
. "$(dirname "$0")/_sample.sh"
BAM="${BAM:-$HOME/genomic_work/$SAMPLE/$SAMPLE.merged.bam}"
REF="${REF:-$HOME/genomic_work/reference/GRCh38_no_alt.fa}"
BED="${1:-inbox/evogen_recheck.bed}"
OUT="${2:-genome/evogen_recheck_bam.tsv}"

[ -f "$BAM" ] || { echo "BAM not found: $BAM"; echo "give the path: BAM=/path/to.bam bash $0"; exit 1; }
[ -f "$REF" ] || { echo "reference not found: $REF"; exit 1; }
echo "BAM: $BAM"; echo "REF: $REF"; echo "BED: $BED"
printf 'chrom\tpos\tref\talt\tgt\tdepth\tad\n' > "$OUT"
bcftools mpileup -f "$REF" -R "$BED" -a FORMAT/DP,FORMAT/AD -q 20 -Q 20 -Ou "$BAM" \
  | bcftools call -m -Ov \
  | bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t[%GT]\t[%DP]\t[%AD]\n' >> "$OUT"
echo "done → $OUT"
wc -l < "$OUT"
