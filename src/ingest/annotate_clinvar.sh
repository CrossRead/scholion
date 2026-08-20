#!/usr/bin/env bash
# =============================================================================
# ClinVar annotation of a personal VCF → «all clinically significant SNPs»
# =============================================================================
# The loci.json catalogue is a CURATED hot list for pharmacogenetics (fast phenotype
# computation). Whereas «all clinically significant variants known to humanity» is the
# NCBI ClinVar database (updated WEEKLY). Keeping a copy of it inside the project is
# pointless and goes stale fast. The right way: pull a FRESH ClinVar every time and
# annotate YOUR VCF with it — then exactly your pathogenic/significant variants surface.
#
# Freshness: a repeat run downloads the newest ClinVar → new knowledge is taken into
# account. It can be put on a schedule (cron / launchd / scheduled task) once a week.
#
# Output:
#   genome/<sample>.clinvar.vcf.gz      — your VCF with ClinVar's CLNSIG/CLNDN/RS fields
#   genome/clinvar_hits.tsv             — the extracted SIGNIFICANT variants (patho/likely/risk/drug)
#   The application and the Skill read clinvar_hits.tsv (the «Genome» tab → «Significant findings»).
#
# Required: bcftools, tabix, curl. Personal data does NOT leave the machine
# (only the public ClinVar is downloaded; your genome is not sent anywhere).
# -----------------------------------------------------------------------------
set -euo pipefail

# --- paths (overridable through environment variables) -----------------------
REPO_DIR="${SCHOLION_REPO_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
GENOME_DIR="${SCHOLION_GENOME_DIR:-$REPO_DIR/genome}"
CACHE_DIR="${SCHOLION_CLINVAR_CACHE:-$HOME/genomic_work/clinvar}"
CLINVAR_URL="${CLINVAR_URL:-https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz}"

# your full VCF: env SCHOLION_GENOME_VCF, or the first *.vcf.gz in genome/ (excluding the already annotated one)
VCF="${SCHOLION_GENOME_VCF:-}"
if [[ -z "$VCF" ]]; then
  # IMPORTANT: genome/ holds not only the full genome but also DERIVED subsets
  # (longevity_sites, scoring_sites, loci_sites — hundreds or thousands of positions
  # instead of millions). This used to take simply the first file in alphabetical
  # order, and as soon as the subsets appeared next to it the annotation ran over a
  # subset instead: clinvar_hits.tsv was overwritten with a couple of dozen findings
  # instead of hundreds. The subsets are now excluded explicitly, and the full genome
  # takes priority.
  VCF="$(ls -1 "$GENOME_DIR"/*.vcf.gz 2>/dev/null \
        | grep -v '\.clinvar\.vcf\.gz$' \
        | grep -vE '/(longevity_sites|scoring_sites|scoring_sites_ext|loci_sites)[^/]*\.vcf\.gz$' \
        | sort -r | head -n1 || true)"
  # sort -r: *.full.vcf.gz wins over the other candidates regardless of the ls locale
fi
if [[ -z "$VCF" || ! -f "$VCF" ]]; then
  echo "❌ No personal VCF found in $GENOME_DIR. Build it first (call_full_vcf.sh)." >&2
  exit 1
fi
SIZE=$(stat -f%z "$VCF" 2>/dev/null || stat -c%s "$VCF" 2>/dev/null || echo 0)
if [ "$SIZE" -lt 10000000 ]; then
  echo "❌ A suspiciously small VCF was picked ($VCF, $SIZE bytes) — this looks like a derived" >&2
  echo "   subset rather than the full genome. Set SCHOLION_GENOME_VCF explicitly and retry." >&2
  exit 2
fi
SAMPLE="$(basename "$VCF" | sed 's/\..*//')"
OUT_VCF="$GENOME_DIR/$SAMPLE.clinvar.vcf.gz"
OUT_TSV="$GENOME_DIR/clinvar_hits.tsv"

for tool in bcftools tabix curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "❌ $tool is required (brew install bcftools htslib curl)"; exit 1; }
done

mkdir -p "$CACHE_DIR" "$GENOME_DIR"
CLINVAR_VCF="$CACHE_DIR/clinvar.vcf.gz"

# --- 1. a fresh ClinVar (re-downloaded only if the server copy is newer) ------
echo "→ Checking/downloading a fresh ClinVar (GRCh38) …"
curl -fsSL -z "$CLINVAR_VCF" -o "$CLINVAR_VCF" "$CLINVAR_URL"
curl -fsSL -z "$CLINVAR_VCF.tbi" -o "$CLINVAR_VCF.tbi" "$CLINVAR_URL.tbi" || tabix -f -p vcf "$CLINVAR_VCF"
CLINVAR_DATE="$(bcftools view -h "$CLINVAR_VCF" | grep -m1 -o 'fileDate=[0-9-]*' | cut -d= -f2 || echo '?')"
echo "  ClinVar version (fileDate): $CLINVAR_DATE"

# --- 2. reconcile the chromosome names (ClinVar: '1'; a UCSC-based VCF: 'chr1') -
PREF=""
if bcftools view -h "$VCF" | grep -q '##contig=<ID=chr'; then PREF="chr"; fi
ANNOT="$CLINVAR_VCF"
if [[ "$PREF" == "chr" ]]; then
  echo "→ The personal VCF uses the 'chr' prefix — renaming the ClinVar contigs to match…"
  MAP="$CACHE_DIR/chr_map.txt"
  { for c in $(seq 1 22) X Y; do echo "$c chr$c"; done; echo "MT chrM"; } > "$MAP"
  ANNOT="$CACHE_DIR/clinvar.chr.vcf.gz"
  if [[ ! -f "$ANNOT" || "$CLINVAR_VCF" -nt "$ANNOT" ]]; then
    bcftools annotate --rename-chrs "$MAP" "$CLINVAR_VCF" -Oz -o "$ANNOT"
    tabix -f -p vcf "$ANNOT"
  fi
fi

# --- 3. annotate your VCF with the ClinVar fields -----------------------------
# --- 3a. normalise before matching -------------------------------------------
#
# `bcftools annotate` matches on CHROM+POS+REF+ALT. An indel has many equally
# valid spellings — a deletion can be written with different padding and at
# different anchor positions — so the same variant in your file and in ClinVar
# can fail to meet. The miss is SILENT: the annotation simply finds nothing, and
# a pathogenic indel comes out looking like a locus with no finding.
#
# Two steps fix it, and they need different things:
#   -m -any        splits multiallelic sites, so a site where only one ALT is
#                  pathogenic still matches. Needs no reference.
#   -f REFERENCE   left-aligns and trims, which is what actually makes two
#                  spellings of one indel identical. Needs the reference FASTA.
#
# When the reference is not on this machine the first step still runs and the
# second cannot. That is recorded rather than glossed over: `genome/
# clinvar_norm.json` says whether indels were left-aligned, and the engine
# qualifies indel findings when they were not. An unreliable match presented as a
# clean one is the failure this whole layer exists to prevent.
REF_FASTA="${SCHOLION_REFERENCE_FASTA:-}"
if [ -z "$REF_FASTA" ]; then
  for cand in "$GEN"/*.fa "$GEN"/*.fasta "$GEN"/*.fa.gz "$GEN"/*.fasta.gz; do
    [ -f "$cand" ] && { REF_FASTA="$cand"; break; }
  done
fi
NORM_VCF="$GEN/.normalised.vcf.gz"
if [ -n "$REF_FASTA" ] && [ -f "$REF_FASTA" ]; then
  echo "→ Normalising (split multiallelics, left-align indels) against $(basename "$REF_FASTA")…"
  bcftools norm -m -any -f "$REF_FASTA" "$VCF" -Oz -o "$NORM_VCF"
  LEFT_ALIGNED=true
else
  echo "⚠ No reference FASTA found — splitting multiallelics only. Indels will NOT be"
  echo "  left-aligned, so an indel spelled differently from ClinVar's copy may be missed."
  echo "  Set SCHOLION_REFERENCE_FASTA to the FASTA to close this."
  bcftools norm -m -any "$VCF" -Oz -o "$NORM_VCF"
  LEFT_ALIGNED=false
fi
tabix -f -p vcf "$NORM_VCF"
printf '{"left_aligned": %s, "reference": "%s", "normalised": true}\n' \
  "$LEFT_ALIGNED" "${REF_FASTA:-}" > "$GEN/clinvar_norm.json"

echo "→ Annotating your VCF with the ClinVar fields (CLNSIG, CLNDN, CLNREVSTAT, RS)…"
bcftools annotate -a "$ANNOT" \
  -c INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT,INFO/RS \
  "$NORM_VCF" -Oz -o "$OUT_VCF"
tabix -f -p vcf "$OUT_VCF"

# --- 4. extract the clinically SIGNIFICANT findings ---------------------------
echo "→ Extracting the significant variants (Pathogenic / Likely_pathogenic / risk / drug_response)…"
{
  echo -e "chrom\tpos\tref\talt\tgenotype\trsid\tclnsig\tclndn\treview"
  bcftools view -i 'INFO/CLNSIG!="."' "$OUT_VCF" \
    | bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t[%GT]\trs%INFO/RS\t%INFO/CLNSIG\t%INFO/CLNDN\t%INFO/CLNREVSTAT\n' \
    | awk -F'\t' 'tolower($7) ~ /pathogenic|risk_factor|drug_response|association|protective/ && $7 !~ /^Benign/'
} > "$OUT_TSV"

N=$(( $(wc -l < "$OUT_TSV") - 1 ))

# --- 5. write the source metadata (for the «source/updated» marks in the app) ---
TODAY="$(date +%Y-%m-%d)"
printf '{\n  "clinvar_date": "%s",\n  "synced": "%s",\n  "hits": %s,\n  "url": "%s"\n}\n' \
  "$CLINVAR_DATE" "$TODAY" "$N" "$CLINVAR_URL" > "$GENOME_DIR/clinvar_meta.json"

echo ""
echo "✅ Done."
echo "   Annotated VCF:      $OUT_VCF"
echo "   Significant hits:   $N  →  $OUT_TSV"
echo "   ClinVar dated:      $CLINVAR_DATE (a repeat run will pull a newer one)"
echo ""
echo "The application: the «Genome» tab will show the findings. Skill: the genome/clinvar tool."
