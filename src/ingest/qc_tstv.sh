#!/usr/bin/env bash
# Quality control of the full VCF: Ts/Tv, the number of variants, the SNP/indel split.
# Ts/Tv ~2.0–2.1 for WGS = a healthy set; noticeably below ~1.8 → a lot of noise
# (an argument for a DeepVariant recomputation, pipeline v2).
#   ./qc_tstv.sh genome/$SAMPLE.full.vcf.gz
set -uo pipefail
. "$(dirname "$0")/_sample.sh"
VCF="${1:?the path to the VCF}"
command -v bcftools >/dev/null || { echo "bcftools is required"; exit 1; }
echo "=== QC: $VCF ==="
STATS="$(bcftools stats "$VCF" 2>/dev/null)"
# The SN summary (tab → indent; works with both BSD and GNU sed via $'\t')
printf '%s\n' "$STATS" | awk -F'\t' '$1=="SN"{printf "  %s %s\n",$3,$4}'
# Ts/Tv without an early exit (otherwise SIGPIPE + pipefail kill the script)
TSTV="$(printf '%s\n' "$STATS" | awk -F'\t' '$1=="TSTV"{print $5}' | head -n1)"
echo "-----------------------------------------"
echo "  Ts/Tv = ${TSTV:-?}"
awk -v t="${TSTV:-0}" 'BEGIN{
  if(t+0>=1.95) print "  ✅ normal for WGS (~2.0–2.1)";
  else if(t+0>=1.8) print "  ⚠️  a bit low — acceptable, but worth a look";
  else print "  ❗ low Ts/Tv — a lot of noise in the calls; a reason for a DeepVariant recomputation";
}'
