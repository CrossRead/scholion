#!/usr/bin/env bash
# =============================================================================
# Track 2: FASTQ → VCF for the Genomic App
# =============================================================================
# Run it LOCALLY on the owner's machine (a Mac), in an ordinary terminal or through
# Claude Code — NOT through the Cowork bridge (a 45-second sandbox without the tools)
# and NOT in the cloud (tens of gigabytes of data, and the privacy of the genome).
#
# Platform: MGI / DNBSEQ, paired reads *_1.fq.gz / *_2.fq.gz.
#
# TWO MODES (the MODE variable):
#   MODE=targeted (THE DEFAULT) — fast and without Docker:
#       bwa-mem2 → markdup → bcftools mpileup over the TARGET LOCI ONLY
#       (APOE, CYP2C9, SLCO1B1, DPYD, CYP2C19, VKORC1, TPMT, MTHFR…).
#       Disk ~90–120 GB, less time (only the alignment phase is heavy).
#   MODE=wgs — a full genomic VCF through DeepVariant (Docker needed, ~250 GB, longer).
#
# Requirements: ~16+ GB RAM, 8+ cores. Disk: targeted ~120 GB, wgs ~250 GB free
#   (check the free space before starting a wgs run — it is tight).
# -----------------------------------------------------------------------------
set -euo pipefail
. "$(dirname "$0")/_sample.sh"

# ---------- SETTINGS ---------------------------------------------------------
# The default FASTQ_DIR ends in a Russian folder name because that is the name
# Evogen ships the raw data under — a path on disk, not a message to a reader.
# Translating it would point the script at a directory that does not exist.
FASTQ_DIR="${FASTQ_DIR:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/!Scholion/EvogenGenomeApp/EvogemRawData/Первичные данные полногеномного секвенирования_$SAMPLE}"
WORKDIR="${WORKDIR:-$HOME/genomic_work/$SAMPLE}"   # a LOCAL disk, NOT iCloud
REF_DIR="${REF_DIR:-$HOME/genomic_work/reference}"
REF_FASTA="$REF_DIR/GRCh38_no_alt.fa"
# Reference: GRCh38 analysis set (no-alt, chr notation). The UCSC mirror is usually faster than NCBI.
REF_URL="${REF_URL:-https://hgdownload.soe.ucsc.edu/goldenPath/hg38/bigZips/analysisSet/hg38.analysisSet.fa.gz}"
# Fallback mirror (NCBI, slower): https://ftp.ncbi.nlm.nih.gov/genomes/all/GCA/000/001/405/GCA_000001405.15_GRCh38/seqs_for_alignment_pipelines.ucsc_ids/GCA_000001405.15_GRCh38_no_alt_analysis_set.fna.gz
THREADS="${THREADS:-$(getconf _NPROCESSORS_ONLN)}"
MODE="${MODE:-targeted}"           # targeted | wgs
CLEANUP="${CLEANUP:-1}"            # 1 = delete the intermediate BAMs (saves disk)
BED="$WORKDIR/pgx_targets.bed"

# A LOCAL scratch area for samtools' temporary files. CRITICAL: NOT in iCloud —
# otherwise samtools sort/markdup fail with «Operation timed out» (iCloud hangs on
# writing multi-gigabyte tmp BAMs). TMPDIR plus an explicit -T guarantee locality.
SCRATCH="${SCRATCH:-$HOME/genomic_work/scratch}"
mkdir -p "$WORKDIR" "$REF_DIR" "$SCRATCH"
export TMPDIR="$SCRATCH"
cd "$SCRATCH"                       # any default ./tmp then also lands locally
log(){ echo -e "\n[$(date '+%H:%M:%S')] $*"; }
# a safeguard: abort if WORKDIR/SCRATCH turn out to be inside iCloud
case "$WORKDIR$SCRATCH" in *Mobile\ Documents*|*CloudDocs*|*iCloud*)
  echo "❌ WORKDIR/SCRATCH is inside iCloud — move it to a local disk (~/genomic_work)"; exit 1;; esac

# ---------- 0. Tools ---------------------------------------------------------
need(){ command -v "$1" >/dev/null 2>&1 || { echo "❌ missing: $1 — install it: $2"; MISS=1; }; }
MISS=0
# Aligner: bwa-mem2 (faster) or bwa (more portable on Apple Silicon) — whichever is installed
if command -v bwa-mem2 >/dev/null 2>&1; then ALIGNER=bwa-mem2
elif command -v bwa >/dev/null 2>&1; then ALIGNER=bwa
else echo "❌ no aligner. Install one: brew tap brewsci/bio && brew install bwa   (or bwa-mem2)"; MISS=1; fi
need samtools "brew install samtools"
need bcftools "brew install bcftools"
[ "$MODE" = wgs ] && need docker "needed for DeepVariant; or use MODE=targeted"
[ "$MISS" = 1 ] && { echo "Install what is missing and run again."; exit 1; }
log "Aligner: $ALIGNER"

# ---------- BED of the target regions — GENERATED, not written by hand -------
# The second table this script used to carry. Five markers of the interpretation
# panel were missed by it, and none of the five looked like an error to anyone
# downstream: `bcftools` finds no row outside the target and the marker comes out
# `./. (ref/not covered)` — the same output a position the sequencing genuinely
# missed produces. A person following the documented route was told nothing was
# found where their genotype was.
#
#   rs4244285  CYP2C19 *2    written on chr19; the gene is on chr10
#   rs12248560 CYP2C19 *17   the same
#   rs3918290  DPYD *2A      interval 373 kb away from the locus
#   rs67376798 DPYD          interval 899 kb away
#   rs1142345  TPMT *3C      31 bp outside the left edge — the commonest
#                            deficient allele in Europeans, off by a rounding
#
# `extract_pgx_loci.sh` was repaired the same way in v2.19.0 and this file kept
# its table, so the class came back. The repair is not "correct the five": it is
# that there is no second table left to drift.
PGX_PAD="${PGX_PAD:-200}"
CATALOGUE="${SCHOLION_LOCI_JSON:-$(cd "$(dirname "$0")/../.." && pwd)/src/scholion/knowledge/loci.json}"
[ -s "$CATALOGUE" ] || { echo "❌ the locus catalogue was not found: $CATALOGUE"; exit 1; }
python3 - "$CATALOGUE" "$PGX_PAD" > "$BED" <<'BED_PY'
import json, sys
from pathlib import Path

cat = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
pad = int(sys.argv[2])
rows = []

# Point loci: the coordinate plus a margin on both sides. The margin is what the
# TPMT case cost — an interval that starts exactly at the locus is one rounding
# away from starting after it.
for rs, e in (cat.get("loci") or {}).items():
    pos, chrom, gene = e.get("pos"), e.get("chrom"), e.get("gene") or "?"
    if pos is None or chrom is None:
        continue
    rows.append((str(chrom), max(0, int(pos) - pad), int(pos) + pad, f"{gene}_{rs}"))

# Whole-gene windows, for the genes a point cannot answer.
for gene, r in (cat.get("regions") or {}).items():
    rows.append((str(r["chrom"]), int(r["start"]), int(r["end"]), f"{gene}_region"))

def key(r):
    c = r[0]
    return (int(c) if c.isdigit() else 99, c, r[1])

for chrom, s, e, name in sorted(rows, key=key):
    print(f"chr{chrom}\t{s}\t{e}\t{name}")
BED_PY
[ -s "$BED" ] || { echo "❌ the target BED came out empty — check $CATALOGUE"; exit 1; }
log "Target regions from the catalogue: $(wc -l < "$BED" | tr -d ' ') ($CATALOGUE, ±${PGX_PAD} bp)"

# ---------- 1. Reference + indexes -------------------------------------------
if [ ! -f "$REF_FASTA" ]; then
  log "Downloading the GRCh38 reference…"; curl -L "$REF_URL" -o "$REF_FASTA.gz"; gunzip "$REF_FASTA.gz"
fi
[ -f "$REF_FASTA.fai" ] || { log "faidx…"; samtools faidx "$REF_FASTA"; }
if [ "$ALIGNER" = bwa-mem2 ]; then
  [ -f "$REF_FASTA.bwt.2bit.64" ] || { log "bwa-mem2 index (~1 h, ~10 GB)…"; bwa-mem2 index "$REF_FASTA"; }
else
  [ -f "$REF_FASTA.bwt" ] || { log "bwa index (~1 h, ~5 GB)…"; bwa index "$REF_FASTA"; }
fi

# ---------- 2. Alignment of all pairs ----------------------------------------
# portable for the system bash 3.2 on macOS (no mapfile there)
R1S=()
while IFS= read -r _f; do R1S+=("$_f"); done < <(find "$FASTQ_DIR" -name '*_1.fq.gz' | sort)
[ "${#R1S[@]}" -gt 0 ] || { echo "❌ no *_1.fq.gz in $FASTQ_DIR"; exit 1; }
log "FASTQ pairs: ${#R1S[@]}"
BAMS=()
for R1 in "${R1S[@]}"; do
  R2="${R1/_1.fq.gz/_2.fq.gz}"; [ -f "$R2" ] || { echo "❌ no mate for $R1"; exit 1; }
  base="$(basename "$R1" _1.fq.gz)"; out="$WORKDIR/${base}.sorted.bam"
  if [ -f "$out" ]; then BAMS+=("$out"); continue; fi
  log "Aligning $base ($ALIGNER)…"
  "$ALIGNER" mem -t "$THREADS" -R "@RG\tID:${base}\tSM:${SAMPLE}\tPL:DNBSEQ\tLB:${SAMPLE}" \
    "$REF_FASTA" "$R1" "$R2" | samtools sort -@ "$THREADS" -T "$SCRATCH/srt.$base" -o "$out" -
  BAMS+=("$out")
done

# ---------- 3. Merge + markdup -----------------------------------------------
MARKED="$WORKDIR/${SAMPLE}.markdup.bam"
if [ ! -f "$MARKED" ]; then
  log "Merging and marking duplicates…"
  samtools cat "${BAMS[@]}" \
    | samtools sort -n -@ "$THREADS" -m 1G -T "$SCRATCH/nsort" - \
    | samtools fixmate -m -@ "$THREADS" - - \
    | samtools sort -@ "$THREADS" -m 1G -T "$SCRATCH/csort" - \
    | samtools markdup -@ "$THREADS" -T "$SCRATCH/mdup" - "$MARKED"
  samtools index -@ "$THREADS" "$MARKED"
  [ "$CLEANUP" = 1 ] && rm -f "${BAMS[@]}" && log "Intermediate per-lane BAMs deleted (saves disk)."
fi

# ---------- 4. Variant calling -----------------------------------------------
if [ "$MODE" = targeted ]; then
  OUT="$WORKDIR/${SAMPLE}.targets.vcf.gz"
  log "Targeted calling (bcftools mpileup over the BED)…"
  bcftools mpileup -f "$REF_FASTA" -R "$BED" -a AD,DP -Ou "$MARKED" \
    | bcftools call -m -Oz -o "$OUT"
  bcftools index -t "$OUT"
  log "✅ Done (targeted): $OUT"
  echo "Next:  bash extract_pgx_loci.sh \"$OUT\""
else
  VCF="$WORKDIR/${SAMPLE}.deepvariant.vcf.gz"
  log "DeepVariant WGS (docker)…"
  docker run --rm -v "$REF_DIR":/ref -v "$WORKDIR":/work google/deepvariant:1.6.1 \
    run_deepvariant --model_type=WGS --ref=/ref/$(basename "$REF_FASTA") \
    --reads=/work/$(basename "$MARKED") --output_vcf=/work/$(basename "$VCF") --num_shards="$THREADS"
  NORM="$WORKDIR/${SAMPLE}.norm.vcf.gz"
  bcftools norm -f "$REF_FASTA" -m -both "$VCF" -Oz -o "$NORM"; bcftools index -t "$NORM"
  log "✅ Done (wgs): $NORM"
  echo "Next:  bash extract_pgx_loci.sh \"$NORM\""
fi
