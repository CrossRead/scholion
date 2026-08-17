#!/usr/bin/env bash
# Pharmacogenetics, stage 1: star alleles of 18 genes from a BAM through PyPGx 0.27.
#
# What it adds over the tag-SNP approach used here: real diplotypes that account for
# structural variants (CYP2D6, CYP2B6, CYP4F2, G6PD, CYP2A6 — deletions/duplications/
# hybrids), statistical phasing against the 1KGP panel (which resolves cis/trans for
# CYP2C19 *2/*17), UGT1A1*28 (the promoter TA repeat, which the bcftools catalogue
# does not pick up) and the correct hemizygosity of G6PD in a male.
#
# Preparation (once):
#   pip3 install --user pypgx 'pandas<3'   # pandas 3.x is incompatible with pypgx 0.27
#   cd ~ && git clone --branch 0.27.0 --depth 1 https://github.com/sbslee/pypgx-bundle
#   java -version   # any Java 8+ will do; if absent — brew install openjdk
#
# The script is resumable: completed steps are skipped. Total time: ~30–60 min.
set -euo pipefail
. "$(dirname "$0")/_sample.sh"
BAM="${BAM:-$HOME/genomic_work/$SAMPLE/$SAMPLE.merged.bam}"
REF="${REF_FASTA:-$HOME/genomic_work/reference/GRCh38_no_alt.fa}"
PGX="${PGX_DIR:-$HOME/genomic_work/pgx}"
PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
GENES=(CYP2D6 CYP2C19 CYP2C9 CYP2B6 CYP3A4 CYP3A5 CYP1A2 CYP4F2 CYP2A6 \
       SLCO1B1 ABCG2 TPMT NUDT15 DPYD UGT1A1 G6PD VKORC1 NAT2)
SV_GENES=(CYP2D6 CYP2B6 CYP4F2 G6PD CYP2A6)   # these need depth + control statistics

echo "== Pre-flight check =="
python3 -c "import pypgx" 2>/dev/null || { echo "❌ pypgx is missing: pip3 install --user pypgx"; exit 1; }
python3 - <<'PYCHK' || exit 1
import pandas
major = int(pandas.__version__.split(".")[0])
if major >= 3:
    print(f"❌ pandas {pandas.__version__} is incompatible with pypgx 0.27 (it breaks the CNV computation).")
    print("   Roll back: pip3 install --user 'pandas<3'  — and rerun the script")
    raise SystemExit(1)
PYCHK
# pip --user puts the commands into ~/Library/Python/X.Y/bin, which is not on PATH by default
PYBIN="$HOME/Library/Python/$(python3 -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')/bin"
[ -d "$PYBIN" ] && export PATH="$PYBIN:$PATH"
command -v pypgx >/dev/null || { echo "❌ the pypgx command was not found even in $PYBIN"; exit 1; }
BUNDLE="${PYPGX_BUNDLE:-$HOME/pypgx-bundle}"
[ -d "$BUNDLE/1kgp/GRCh38" ] || { echo "❌ no data bundle ($BUNDLE/1kgp/GRCh38)."; \
  echo "   cd ~ && git clone --branch 0.27.0 --depth 1 https://github.com/sbslee/pypgx-bundle"; exit 1; }
command -v java >/dev/null || { echo "❌ java is missing (needed for Beagle phasing): brew install openjdk"; exit 1; }
command -v bcftools >/dev/null || { echo "❌ bcftools is missing"; exit 1; }
[ -f "$BAM" ] || { echo "❌ no BAM: $BAM"; exit 1; }
[ -f "$REF" ] || { echo "❌ no reference: $REF"; exit 1; }
mkdir -p "$PGX"
echo "OK: pypgx + bundle + java + bcftools; work directory $PGX"

VARIANTS="$PGX/variants.vcf.gz"
if [ ! -f "$VARIANTS" ]; then
  echo "== Step 1/4: SNVs/indels over the regions of all genes (create-input-vcf) =="
  pypgx create-input-vcf "$VARIANTS" "$REF" "$BAM" --assembly GRCh38 --genes "${GENES[@]}"
else echo "== Step 1/4: present ($VARIANTS) — skipping =="; fi

DEPTH="$PGX/depth-of-coverage.zip"
if [ ! -f "$DEPTH" ]; then
  echo "== Step 2/4: coverage depth of the SV genes =="
  pypgx prepare-depth-of-coverage "$DEPTH" "$BAM" --assembly GRCh38 --genes "${SV_GENES[@]}"
else echo "== Step 2/4: present — skipping =="; fi

CONTROL="$PGX/control-statistics-VDR.zip"
if [ ! -f "$CONTROL" ]; then
  echo "== Step 3/4: control statistics (the VDR gene) =="
  pypgx compute-control-statistics VDR "$CONTROL" "$BAM" --assembly GRCh38
else echo "== Step 3/4: present — skipping =="; fi

echo "== Step 4/4: per-gene pipeline =="
for g in "${GENES[@]}"; do
  OUT="$PGX/$g-pipeline"
  # only a gene with results.zip counts as done: a folder without it is the wreckage of
  # an interrupted run and has to be wiped and recomputed
  if [ -f "$OUT/results.zip" ]; then echo "  $g: done — skipping"; continue; fi
  [ -d "$OUT" ] && { echo "  $g: unfinished — recomputing"; rm -rf "$OUT"; }
  EXTRA=()
  case " ${SV_GENES[*]} " in *" $g "*) EXTRA=(--depth-of-coverage "$DEPTH" --control-statistics "$CONTROL");; esac
  echo "  → $g"
  # ${EXTRA[@]+...} — on macOS bash 3.2 an empty array under set -u would otherwise kill the script
  pypgx run-ngs-pipeline "$g" "$OUT" --variants "$VARIANTS" --assembly GRCh38 \
    --do-not-plot-copy-number --do-not-plot-allele-fraction ${EXTRA[@]+"${EXTRA[@]}"} \
    || echo "  ⚠ $g did not finish — continuing (to be reviewed from the log)"
done

echo "== Collecting the results =="
python3 - "$PGX" "$PROJECT" <<'PY'
import sys
from pathlib import Path
from pypgx import sdk

pgx, project = Path(sys.argv[1]), Path(sys.argv[2])
rows = []
for d in sorted(pgx.glob('*-pipeline')):
    gene = d.name.replace('-pipeline', '')
    res = d / 'results.zip'
    if not res.exists():
        rows.append((gene, 'NO RESULT', '', '')); continue
    try:
        # Archive.from_file — pypgx's own loader: columns by name,
        # no drifting text tables
        df = sdk.utils.Archive.from_file(str(res)).data
        r = df.iloc[0]
        def col(name):
            return str(r[name]) if name in df.columns else ''
        rows.append((gene, col('Genotype'), col('Phenotype'), col('CNV')))
    except Exception as e:
        rows.append((gene, 'ERROR', '', str(e)[:60]))

tsv = project / 'profile' / 'pgx_star_alleles.tsv'
with tsv.open('w', encoding='utf-8') as fh:
    fh.write('gene\tdiplotype\tphenotype\tcnv\n')
    for g, dt, ph, cnv in rows:
        fh.write(f'{g}\t{dt}\t{ph}\t{cnv}\n')
        print(f'  {g:10} {dt:22} {ph:28} {cnv}')
print(f'\n✓ {tsv}')
# Outside calls for PharmCAT. A full VCF built here is variants-only: it holds no
# reference genotypes, so PharmCAT cannot tell «*1/*1» from «no data»
# (SLCO1B1/CYP2C9/TPMT... come out as No call data), and without phasing it gets
# confused about the diplotype (for CYP2C19 it can report both *2/*17 and *2/*4-PM).
# So the PyPGx diplotypes are handed over instead (BAM: full pileup + CNV + 1KGP
# phasing); by PharmCAT's rule an outside call takes priority over the VCF data.
# Genes that the matcher calls correctly from the VCF on its own are NOT passed:
# ABCG2, CYP3A5, CYP4F2, VKORC1 and DPYD (there PharmCAT even sees c.2194G>A (*6),
# which PyPGx did not show). PharmCAT does not know CYP1A2 and CYP2A6 — not passed.
OUTSIDE = {'CYP2D6', 'CYP2C19', 'CYP2B6', 'CYP2C9', 'CYP3A4',
           'SLCO1B1', 'TPMT', 'NUDT15', 'UGT1A1', 'NAT2'}
oc = pgx / 'outside_calls.tsv'
with oc.open('w', encoding='utf-8') as fh:
    for g, dt, ph, cnv in rows:
        if g in OUTSIDE and dt.startswith('*'):
            fh.write(f'{g}\t{dt}\n')
        elif g == 'G6PD' and 'Normal' in ph:
            # male hemizygote: it is safer to hand over the phenotype (3rd column), not the diplotype
            fh.write('G6PD\t\tNormal\n')
print(f'✓ {oc} (for PharmCAT -po)')
PY
echo
echo "Next: bash src/ingest/pharmcat_run.sh"
