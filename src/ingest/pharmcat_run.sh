#!/usr/bin/env bash
# Pharmacogenetics, stage 2: PharmCAT 3.2.0 — a full CPIC report from the VCF + CYP2D6 from outside.
#
# Input: the full VCF (genome/<SAMPLE>.full.vcf.gz) + outside_calls.tsv from stage 1
# (PyPGx diplotypes for 11 genes: PharmCAT does not call CYP2D6 itself (structural
# variants), and the rest suffer from the VCF being variants-only — it holds no
# reference genotypes, so the matcher sees «no data»).
# Output: profile/pharmcat/ — the report (HTML to read, JSON for the engine):
# gene → diplotype → phenotype → CPIC/DPWG recommendations per drug.
#
# The network is needed: the first run downloads the jar (~30 MB), the preprocessor
# and its reference files (the PGx position list + the reference FASTA ~800 MB, once).
# Java 17+ is required (java -version; if absent — brew install openjdk).
# The flags were checked against the real v3.2.0 binaries, not from memory.
set -euo pipefail
. "$(dirname "$0")/_sample.sh"
REF="${REF_FASTA:-$HOME/genomic_work/reference/GRCh38_no_alt.fa}"
PC="${PHARMCAT_DIR:-$HOME/genomic_work/pharmcat}"
PGX="${PGX_DIR:-$HOME/genomic_work/pgx}"
PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
VCF="${SCHOLION_GENOME_VCF:-$PROJECT/genome/$SAMPLE.full.vcf.gz}"
VER="3.2.0"
BASE="https://github.com/PharmGKB/PharmCAT/releases/download/v$VER"

echo "== Pre-flight check =="
command -v java >/dev/null || { echo "❌ java is missing: brew install openjdk (17+ required)"; exit 1; }
JV=$(java -version 2>&1 | head -1); echo "java: $JV"
command -v bcftools >/dev/null && command -v bgzip >/dev/null || { echo "❌ bcftools and bgzip are required"; exit 1; }
[ -f "$VCF" ] || { echo "❌ no VCF: $VCF"; exit 1; }
OC="$PGX/outside_calls.tsv"
[ -f "$OC" ] || echo "⚠ no $OC — without the PyPGx diplotypes the report will be incomplete; run bash src/ingest/pgx_star_alleles.sh first"
mkdir -p "$PC"

JAR="$PC/pharmcat-$VER-all.jar"
[ -f "$JAR" ] || { echo "== Downloading PharmCAT $VER =="; curl -fL --retry 3 -o "$JAR" "$BASE/pharmcat-$VER-all.jar"; }
if [ ! -d "$PC/preprocessor" ]; then
  echo "== Downloading the preprocessor =="
  curl -fL --retry 3 -o "$PC/prep.tar.gz" "$BASE/pharmcat-preprocessor-$VER.tar.gz"
  tar xzf "$PC/prep.tar.gz" -C "$PC"
  pip3 install --user -q -r "$PC/preprocessor/requirements.txt"
fi

echo "== Preprocessor (normalisation to the PharmCAT positions) =="
# the reference is passed in locally (-refFna): it is the same GRCh38 as for the
# alignment, and that avoids an ~800 MB download that tends to break mid-way.
# Leftovers of an earlier partial download are removed — a truncated tar breaks unpacking.
rm -f "$PC/preprocessor"/*.tar "$PC/preprocessor"/*.tar.gz 2>/dev/null || true
[ -f "$REF" ] || { echo "❌ no local reference: $REF"; exit 1; }
OUTDIR="$PC/preprocessed"
mkdir -p "$OUTDIR"
python3 "$PC/preprocessor/pharmcat_vcf_preprocessor" \
  -vcf "$VCF" -refFna "$REF" -o "$OUTDIR" -bf "$SAMPLE" -G -v

# strictly the preprocessed file: a glob over $SAMPLE*.vcf* once picked up the
# catalogue of MISSING positions (missing_pgx_var.vcf) — and the report was then
# computed from the wrong input
PREP=$(ls "$OUTDIR"/$SAMPLE.preprocessed.vcf.* 2>/dev/null | grep -v tbi | head -1)
[ -n "$PREP" ] || { echo "❌ no $OUTDIR/$SAMPLE.preprocessed.vcf.* — see the preprocessor output above"; exit 1; }
echo "preprocessed VCF: $PREP"

echo "== PharmCAT =="
REPORT="$PROJECT/profile/pharmcat"
mkdir -p "$REPORT"
PO=()
[ -f "$OC" ] && PO=(-po "$OC")
# -reporterJson produces a machine-readable report.json; -del was removed so that the
# intermediate match.json/phenotype.json are kept too — the application engine reads them.
# -reporterHtml is mandatory alongside -reporterJson: by PharmCAT's rule «if a format is
# given explicitly, only the given ones are saved», without it no HTML is written and the
# report of the previous run stays on disk.
java -jar "$JAR" -vcf "$PREP" ${PO[@]+"${PO[@]}"} -o "$REPORT" -bf "$SAMPLE" -re -reporterJson -reporterHtml

echo
echo "✓ Reports in $REPORT:"
ls -la "$REPORT" | awk '{print "   "$9}' | grep -v '^   $'
echo
echo "To read: open $REPORT/$SAMPLE.report.html in a browser."
echo "Next, the assistant parses the JSON and reconciles it with profile/pharmacogenomics.json."
