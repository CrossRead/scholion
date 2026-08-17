#!/usr/bin/env bash
# Re-calling variants with DeepVariant from merged.bam — more accurate than bcftools,
# especially on indels.
#
# TWO MODES (the MODE variable):
#   MODE=clinical (THE DEFAULT) — the clinical regions only (~0.2 % of the genome:
#     the ACMG SF genes + the pharmacogenes + the locus catalogue + MHC; the BED is
#     built by build_clinical_bed.py). Hours, even under emulation. The result is an
#     OVERLAY, genome/<SAMPLE>.dv_clinical.vcf.gz; the main VCF is not touched.
#   MODE=full — the whole genome. On Apple Silicon only with Rosetta enabled
#     (see below), a night or two. The result is genome/<SAMPLE>.dv.vcf.gz; the
#     decision to replace the main VCF comes AFTER a comparison
#     (vcf_concordance.py), not automatically.
#
# APPLE SILICON: the DeepVariant images are x86_64 only. Rosetta MUST be enabled in
# Docker Desktop: Settings → General → "Use Rosetta for x86_64/amd64 emulation"
# (otherwise QEMU emulation is 5–20× slower and the full mode stretches into weeks).
#
# A CAVEAT ABOUT DUPLICATES: merged.bam may have been assembled without markdup
# (resume_merge_call.sh merges without deduplication when a run had to be salvaged).
# Deduplicating afterwards needs roughly as much free space again for the re-sort,
# which is risky on a tight disk. The bcftools call was made from the same BAM, so
# the comparison is fair; on DNBSEQ the duplicate fraction is low. Keep it in mind
# when interpreting borderline calls.
set -euo pipefail
. "$(dirname "$0")/_sample.sh"
MODE="${MODE:-clinical}"
WORKDIR="${WORKDIR:-$HOME/genomic_work/$SAMPLE}"
REF="${REF_FASTA:-$HOME/genomic_work/reference/GRCh38_no_alt.fa}"
BAM="${BAM:-$WORKDIR/$SAMPLE.merged.bam}"
DV_IMAGE="${DV_IMAGE:-google/deepvariant:1.10.0}"
THREADS="${THREADS:-$(sysctl -n hw.ncpu 2>/dev/null || echo 8)}"
PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
REF_DIR="$(dirname "$REF")"

echo "== Pre-flight check =="
command -v docker >/dev/null || { echo "❌ docker is missing (Docker Desktop not installed/not running)"; exit 1; }
docker info >/dev/null 2>&1 || { echo "❌ docker is present but the daemon does not respond — start Docker Desktop"; exit 1; }
[ -f "$BAM" ] || { echo "❌ no BAM: $BAM"; exit 1; }
[ -f "$BAM.bai" ] || { echo "→ indexing the BAM…"; samtools index "$BAM"; }
[ -f "$REF" ] && [ -f "$REF.fai" ] || { echo "❌ no reference or .fai: $REF"; exit 1; }
FREE_GB=$(df -g "$WORKDIR" | awk 'NR==2{print $4}')
echo "free disk space: ${FREE_GB} GB (clinical needs ~5, full — ~30)"
[ "$MODE" = full ] && [ "$FREE_GB" -lt 30 ] && { echo "❌ not enough space for full"; exit 1; }
if [ "$(uname -m)" = arm64 ]; then
  echo "⚠ Apple Silicon: the x86 image will run under emulation (--platform linux/amd64)."
  echo "  Check that Rosetta is enabled in Docker Desktop (Settings → General)."
fi

EXTRA=()
OUT_BASE="$SAMPLE.dv"
if [ "$MODE" = clinical ]; then
  BED="$WORKDIR/clinical_regions.bed"
  echo "== Building the clinical BED =="
  python3 "$PROJECT_DIR/src/ingest/build_clinical_bed.py" "$BED"
  EXTRA+=(--regions "/work/$(basename "$BED")")
  OUT_BASE="$SAMPLE.dv_clinical"
fi
RAW="$WORKDIR/$OUT_BASE.raw.vcf.gz"
NORM="$WORKDIR/$OUT_BASE.vcf.gz"

echo "== DeepVariant ($DV_IMAGE, $MODE, shards: $THREADS) =="
echo "   start: $(date '+%F %T'); clinical ≈ hours, full ≈ a night or two (with Rosetta)"
docker run --rm --platform linux/amd64 \
  -v "$REF_DIR":/ref -v "$WORKDIR":/work \
  "$DV_IMAGE" run_deepvariant \
  --model_type=WGS \
  --ref="/ref/$(basename "$REF")" \
  --reads="/work/$(basename "$BAM")" \
  --output_vcf="/work/$(basename "$RAW")" \
  --num_shards="$THREADS" \
  "${EXTRA[@]}"

echo "== Normalisation (the same as for the main VCF: norm -m -both) =="
bcftools norm -f "$REF" -m -both "$RAW" -Oz -o "$NORM"
bcftools index -t "$NORM"
mkdir -p "$PROJECT_DIR/genome"
cp "$NORM" "$NORM.tbi" "$PROJECT_DIR/genome/"
echo "✓ $PROJECT_DIR/genome/$(basename "$NORM")"
echo "   records: $(bcftools view -H "$NORM" | wc -l | tr -d ' ')"
echo
echo "Next — a comparison against the bcftools call (the replacement decision follows only from that):"
echo "  python3 src/ingest/vcf_concordance.py genome/$SAMPLE.full.vcf.gz genome/$(basename "$NORM")"
