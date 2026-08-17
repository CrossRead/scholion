#!/usr/bin/env bash
# Recovering Track 2 after markdup failed for lack of disk space.
# The alignment is NOT repeated: the surviving *.sorted.bam files are taken, the stuck
# temp files are cleaned up, they are merged WITHOUT markdup (cheap on space; justified
# for DNBSEQ, where duplication is low) and the full VCF is computed. All temp files go
# to the local scratch area.
#   bash resume_merge_call.sh
set -euo pipefail
. "$(dirname "$0")/_sample.sh"
WORKDIR="$HOME/genomic_work/$SAMPLE"
SCRATCH="$HOME/genomic_work/scratch"; mkdir -p "$SCRATCH"
export TMPDIR="$SCRATCH"
N="$(getconf _NPROCESSORS_ONLN)"
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$HERE/../.." && pwd)"
MERGED="$WORKDIR/$SAMPLE.merged.bam"
log(){ echo -e "\n[$(date '+%H:%M:%S')] $*"; }
command -v samtools >/dev/null || { echo "❌ samtools is missing (brew install samtools)"; exit 1; }

log "1/3 Cleaning up the stuck temp files and the empty markdup stub…"
rm -f "$WORKDIR"/samtools.*.tmp.*.bam
if [ -f "$WORKDIR/$SAMPLE.markdup.bam" ] && [ "$(stat -f%z "$WORKDIR/$SAMPLE.markdup.bam" 2>/dev/null || echo 0)" -lt 1048576 ]; then
  rm -f "$WORKDIR/$SAMPLE.markdup.bam"
fi
df -h "$WORKDIR" | tail -1

if [ ! -s "$MERGED" ]; then
  shopt -s nullglob; BAMS=( "$WORKDIR"/*.sorted.bam ); shopt -u nullglob
  echo "Per-file BAMs found: ${#BAMS[@]}"
  [ "${#BAMS[@]}" -gt 0 ] || { echo "❌ no *.sorted.bam in $WORKDIR"; exit 1; }
  log "2/3 Merging (by coordinate, without markdup) → $MERGED"
  samtools merge -f -@ "$N" "$MERGED" "${BAMS[@]}"
  samtools index -@ "$N" "$MERGED"
else
  log "2/3 merged.bam already exists — skipping the merge"
fi
log "merged: $(ls -lh "$MERGED" | awk '{print $5}')"

log "3/3 The full VCF by windows (call_full_vcf.sh)…"
BAM="$MERGED" PROJECT_DIR="$PROJ" bash "$HERE/call_full_vcf.sh"

echo ""
echo "✅ Done. Next — the ClinVar annotation:"
echo "   bash \"$HERE/annotate_clinvar.sh\""
echo "The surviving per-lane BAMs (tens of GB) can be deleted to free space:"
echo "   rm -f \"$WORKDIR\"/*.sorted.bam"
