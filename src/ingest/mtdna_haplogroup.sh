#!/usr/bin/env bash
#
# Step 3 — determining the mtDNA haplogroup from WGS (GRCh38 assembly, chrM = rCRS).
#
# The logic:
#   1) pull the chrM/MT contig out of the full VCF -> chrM.vcf.gz
#   2) if there are too few variants and REF+BAM were given — call chrM variants from the BAM
#   3) Haplogrep3 classify -> haplogroup + quality
#   4) parse it into profile/mtdna_haplogroup.json
#
# PREREQUISITES (on a Mac):
#   - bcftools, tabix (htslib)
#   - Haplogrep3: download the binary from github.com/genepi/haplogrep3 (or the Haplogrep2 jar)
#       curl -sL https://github.com/genepi/haplogrep3/releases/latest/download/haplogrep3.zip -o hg3.zip
#       unzip hg3.zip -d haplogrep3 && chmod +x haplogrep3/haplogrep3
#
# RUN:
#   bash mtdna_haplogroup.sh \
#       ~/.../genome/$SAMPLE.full.vcf.gz \
#       profile/mtdna \
#       [REF.fa] [merged.bam]     # the last two are optional, for the call-from-BAM fallback
#
# WARNING: not tested against real data. Review it before running. The link
# «haplogroup <-> longevity» is population-dependent and contradictory — treat it as
# background context, not as a result.

set -euo pipefail
. "$(dirname "$0")/_sample.sh"

VCF="${1:?give the path to full.vcf.gz}"
OUT="${2:-profile/mtdna}"
REF="${3:-}"
BAM="${4:-}"
HAPLOGREP="${HAPLOGREP:-haplogrep3}"   # or: java -jar haplogrep-2.4.0.jar

mkdir -p "$(dirname "$OUT")"

# --- 1. determine the name of the mitochondrial contig ---
CONTIG="$(tabix -l "$VCF" | grep -iE '^(chrM|chrMT|MT|M)$' | head -1 || true)"
if [ -z "$CONTIG" ]; then
  echo "[!] The chrM/MT contig was not found in the VCF. Contig list:"; tabix -l "$VCF" | head -50
  exit 1
fi
echo "[*] Mitochondrial contig: $CONTIG"

CHRM_VCF="${OUT}_chrM.vcf.gz"
bcftools view -r "$CONTIG" "$VCF" -Oz -o "$CHRM_VCF"
tabix -f -p vcf "$CHRM_VCF"
N="$(bcftools view -H "$CHRM_VCF" | wc -l | tr -d ' ')"
echo "[*] chrM variants in the VCF: $N"

# --- 2. recalling from the BAM — the MAIN path for mtDNA ---
# IMPORTANT: a diploid whole-genome VCF UNDERCALLS mtDNA — a full VCF may contain
# only a handful of chrM rows, and some of them artefacts. A reliable haplogroup
# needs a mitochondria-specific recall from the BAM. Mutserve is better (recommended
# by Haplogrep): github.com/seppinho/mutserve ; below is the quick bcftools --ploidy 1 path.
if [ -n "$BAM" ] && [ -n "$REF" ]; then
  echo "[*] Recalling chrM from the BAM (mitochondria-specific, ploidy=1)"
  bcftools mpileup -r "$CONTIG" -f "$REF" "$BAM" \
    | bcftools call -mv --ploidy 1 -Oz -o "$CHRM_VCF"
  tabix -f -p vcf "$CHRM_VCF"
  N="$(bcftools view -H "$CHRM_VCF" | wc -l | tr -d ' ')"
  echo "[*] chrM variants from the BAM: $N"
elif [ "$N" -lt 10 ]; then
  echo "[!] Only $N chrM variants in the VCF — too few for a reliable haplogroup."
  echo "[!] A whole-genome VCF undercalls mtDNA: pass REF.fa and merged.bam (args 3 and 4)"
  echo "[!] or use Mutserve (github.com/seppinho/mutserve). Aborting."
  exit 2
fi

# --- 2b. Haplogrep expects an rCRS contig; rename chrM->MT if needed ---
CHRM_VCF_HG="$CHRM_VCF"
if [ "$CONTIG" != "MT" ]; then
  echo "[*] Renaming contig $CONTIG -> MT for Haplogrep"
  printf '%s\tMT\n' "$CONTIG" > "${OUT}_rename.txt"
  bcftools annotate --rename-chrs "${OUT}_rename.txt" "$CHRM_VCF" -Oz -o "${OUT}_chrM.MT.vcf.gz"
  tabix -f -p vcf "${OUT}_chrM.MT.vcf.gz"
  CHRM_VCF_HG="${OUT}_chrM.MT.vcf.gz"
fi

# --- 3. classification ---
HG_OUT="${OUT}_haplogroup.txt"
echo "[*] Haplogrep classify..."
$HAPLOGREP classify --tree phylotree-rcrs@17.2 --in "$CHRM_VCF_HG" --out "$HG_OUT" --extend-report
echo "[*] Haplogrep result:"; cat "$HG_OUT"

# --- 4. parse into JSON ---
python3 - "$HG_OUT" "${OUT}_haplogroup.json" "$N" <<'PY'
import sys, csv, json, os
hg_out, json_out, nvar = sys.argv[1], sys.argv[2], sys.argv[3]
with open(hg_out, newline="") as f:
    # Haplogrep emits TSV; the key columns are SampleID, Haplogroup, Quality/Rank
    rows = list(csv.DictReader(f, delimiter="\t"))
r = rows[0] if rows else {}
def pick(*names):
    for n in names:
        for k in r:
            if k.strip().lower() == n.lower():
                return r[k]
    return None
res = {
    "haplogroup": pick("Haplogroup"),
    "quality": pick("Quality", "Rank"),
    "n_chrM_variants": int(nvar),
    "source": os.path.basename(hg_out),
    "caveat": ("The link between the haplogroup and longevity is population-dependent and "
               "inconsistent across studies. Background context, not a diagnosis."),
}
with open(json_out, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=2)
print("\n=== mtDNA haplogroup ===")
print("Haplogroup:", res["haplogroup"], "| quality:", res["quality"])
print("Written to:", json_out)
PY

echo "[✓] Done. JSON: ${OUT}_haplogroup.json"
