#!/usr/bin/env bash
# =============================================================================
# Track 2 (full): an aligned BAM → a FULL genomic VCF (bcftools, no Docker)
# =============================================================================
# Run it AFTER fastq_to_vcf.sh has built the markdup BAM. It uses the same BAM — the
# alignment is NOT redone. It calls variants across the whole genome, in parallel by
# chromosome, and puts the finished database (VCF + index) into the project folder.
#
# This is the «cold» full database (~4–5 million variants, ~100–150 MB). The
# application/skill pull any locus out of it. The hot distillate stays in profile/.
#
# SNP accuracy is good (enough for pharmacogenetics). For reference-grade accuracy on
# indels it can later be recomputed with DeepVariant: MODE=wgs bash fastq_to_vcf.sh
# -----------------------------------------------------------------------------
set -euo pipefail
. "$(dirname "$0")/_sample.sh"

WORKDIR="${WORKDIR:-$HOME/genomic_work/$SAMPLE}"
REF_FASTA="${REF_FASTA:-$HOME/genomic_work/reference/GRCh38_no_alt.fa}"
# BAM: markdup is taken by default; if it is missing/empty — the merged merged.bam
# (a pipeline without markdup — justified for DNBSEQ, where duplication is low).
if [ -z "${BAM:-}" ]; then
  if [ -s "$WORKDIR/$SAMPLE.markdup.bam" ] && [ "$(stat -f%z "$WORKDIR/$SAMPLE.markdup.bam" 2>/dev/null || stat -c%s "$WORKDIR/$SAMPLE.markdup.bam" 2>/dev/null || echo 0)" -gt 1048576 ]; then
    BAM="$WORKDIR/$SAMPLE.markdup.bam"
  elif [ -f "$WORKDIR/$SAMPLE.merged.bam" ]; then
    BAM="$WORKDIR/$SAMPLE.merged.bam"
  else
    BAM="$WORKDIR/$SAMPLE.markdup.bam"
  fi
fi
THREADS="${THREADS:-$(getconf _NPROCESSORS_ONLN)}"
# The project folder to put the finished database into (the current one by default).
PROJECT_DIR="${PROJECT_DIR:-$PWD}"
GENOME_DIR="$PROJECT_DIR/genome"
OUT="$WORKDIR/${SAMPLE}.full.vcf.gz"
CHRDIR="$WORKDIR/_chr"

log(){ echo -e "\n[$(date '+%H:%M:%S')] $*"; }
for t in bcftools bgzip tabix; do command -v "$t" >/dev/null || { echo "❌ $t is missing — brew install bcftools htslib"; exit 1; }; done
[ -f "$BAM" ] || { echo "❌ no BAM: $BAM (run fastq_to_vcf.sh first)"; exit 1; }
[ -f "$REF_FASTA.fai" ] || samtools faidx "$REF_FASTA"

# The genome is split into WINDOWS (chr1..22,X,Y,M) so that every core stays busy to the
# end: computing by whole chromosomes leaves a «tail» stuck on one huge chr1 on a single
# core while the rest idle. Windows of ~20 Mb even out the load → noticeably faster.
WINDOW="${WINDOW:-20000000}"
REGIONS=()
while IFS=$'\t' read -r chrom length _rest; do
  case "$chrom" in
    chr[0-9]|chr[0-9][0-9]|chrX|chrY|chrM) ;;
    *) continue ;;
  esac
  start=1
  while [ "$start" -le "$length" ]; do
    end=$(( start + WINDOW - 1 )); [ "$end" -gt "$length" ] && end="$length"
    REGIONS+=("$chrom:$start-$end")
    start=$(( end + 1 ))
  done
done < "$REF_FASTA.fai"
[ "${#REGIONS[@]}" -gt 0 ] || { echo "❌ no chr contigs in $REF_FASTA.fai"; exit 1; }
mkdir -p "$CHRDIR" "$GENOME_DIR"

log "Calling variants over ${#REGIONS[@]} windows (in parallel, $THREADS threads)…"
printf '%s\n' "${REGIONS[@]}" | xargs -P "$THREADS" -I{} bash -c '
  reg="$1"; ref="'"$REF_FASTA"'"; bam="'"$BAM"'"; dir="'"$CHRDIR"'"
  name="$(echo "$reg" | tr ":-" "__")"
  out="$dir/$name.vcf.gz"
  [ -f "$out" ] && [ -f "$out.tbi" ] && exit 0
  bcftools mpileup -f "$ref" -r "$reg" -a AD,DP -Ou "$bam" \
    | bcftools call -mv -Oz -o "$out"
  bcftools index -t "$out"
' _ {}

log "Merging and normalising (${#REGIONS[@]} windows)…"
LIST=""
for reg in "${REGIONS[@]}"; do name="$(echo "$reg" | tr ':-' '__')"; LIST="$LIST $CHRDIR/$name.vcf.gz"; done
bcftools concat -Oz $LIST | bcftools norm -f "$REF_FASTA" -m -both -Oz -o "$OUT"
bcftools index -t "$OUT"

log "Copying the finished database into the project…"
cp "$OUT" "$OUT.tbi" "$GENOME_DIR/"

N=$(bcftools view -H "$OUT" | wc -l | tr -d ' ')
SZ=$(du -h "$OUT" | cut -f1)
echo ""
echo "✅ The full genomic database is ready:"
echo "   $GENOME_DIR/$(basename "$OUT")  (variants: $N, size: $SZ)"
echo "   + a .tbi index (for instant lookup by position)"
echo ""
echo "The intermediate per-chromosome VCFs can be deleted: rm -rf \"$CHRDIR\""
echo "Next: the application/skill look up any locus in the database (command: python3 -m scholion genome <rsID>)."
