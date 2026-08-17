#!/usr/bin/env bash
# =============================================================================
# Extraction of the target markers from a VCF (Track 2) for the Genomic App profile
# =============================================================================
# Pulls out of a normalised VCF the markers that are ABSENT from the laboratory report
# but matter for longevity/QoL and pharmacogenetics (see genome_extended.md → «Gaps»).
#
# Usage:  bash extract_pgx_loci.sh <sample.norm.vcf.gz>
# The coordinates are GRCh38 (chr notation). If the VCF has no 'chr' — the script copes.
#
# WHERE THE COORDINATES COME FROM. From `src/scholion/knowledge/loci.json`, and from
# nowhere else. This file used to carry its own table of seventeen rsID-position
# pairs, and by the time it was checked eight of them disagreed with the catalogue:
# both CYP2C19 markers sat on chromosome 19 (the gene is on 10), both TPMT markers
# and one DPYD marker carried GRCh37 positions under a GRCh38 heading, and the two
# CYP2D6 markers had swapped places. A wrong position is not an error anybody sees --
# bcftools finds no row there and the marker is written out as `./. (ref/not
# covered)`, which is indistinguishable from a position the sequencing genuinely
# missed. The person then follows a documented route and gets silence where their
# genotype was.
#
# A second copy of a coordinate table is guaranteed to drift; the only fix that
# holds is not having one. `tests/test_pgx_script_coordinates.py` refuses to let it
# come back.
# -----------------------------------------------------------------------------
set -euo pipefail
VCF="${1:?Give the path to the normalised VCF: bash extract_pgx_loci.sh sample.norm.vcf.gz}"
command -v bcftools >/dev/null || { echo "❌ bcftools is required"; exit 1; }
PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
CATALOGUE="${SCHOLION_LOCI_JSON:-$PROJECT/src/scholion/knowledge/loci.json}"
[ -s "$CATALOGUE" ] || { echo "❌ the locus catalogue was not found: $CATALOGUE"; exit 1; }

# The genes this pass covers. A gene NAME is a scope decision and may live here;
# a coordinate may not.
GENES="${PGX_GENES:-APOE CYP2C9 CYP2C19 CYP2D6 DPYD MTHFR SLCO1B1 TPMT VKORC1}"

# Detect whether the VCF uses the chr prefix
if bcftools view -h "$VCF" | grep -q "contig=<ID=chr"; then P="chr"; else P=""; fi

# Target SNPs: rsID | GRCh38 chr:pos | gene | why -- read out of the catalogue
LOCI="$(python3 - "$CATALOGUE" $GENES <<'LOCI_PY'
import json, sys
from pathlib import Path

cat = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
want = {g.upper() for g in sys.argv[2:]}
rows = []
for rs, e in (cat.get("loci") or {}).items():
    gene = (e.get("gene") or "").upper()
    if gene not in want:
        continue
    note = e.get("note")
    if isinstance(note, dict):
        note = note.get("en") or next(iter(note.values()), "")
    rows.append((rs, str(e.get("chrom")), str(e.get("pos")), e.get("gene"), note or ""))
rows.sort(key=lambda r: (r[3], r[0]))
for rs, chrom, pos, gene, note in rows:
    print("\t".join((rs, chrom + ":" + pos, gene, note)))
seen = {(e.get("gene") or "").upper() for e in (cat.get("loci") or {}).values()}
if want - seen:
    print("no locus in the catalogue for: " + ", ".join(sorted(want - seen)), file=sys.stderr)
LOCI_PY
)"
[ -n "$LOCI" ] || { echo "❌ the catalogue holds no loci for: $GENES"; exit 1; }
echo "Loci taken from the catalogue: $(echo "$LOCI" | wc -l | tr -d ' ') ($CATALOGUE)"
OUT="$(dirname "$VCF")/pgx_target_loci.tsv"
echo -e "rsid\tchrom\tpos\tref\talt\tgenotype\tgene\twhy" > "$OUT"

echo "$LOCI" | while IFS=$'\t' read -r rs coord gene why; do
  [ -z "${rs:-}" ] && continue
  chr="${coord%%:*}"; pos="${coord##*:}"
  region="${P}${chr}:${pos}-${pos}"
  line="$(bcftools view -H -r "$region" "$VCF" 2>/dev/null | head -1 || true)"
  if [ -n "$line" ]; then
    ref="$(echo "$line" | cut -f4)"; alt="$(echo "$line" | cut -f5)"
    gt="$(echo "$line" | cut -f10 | cut -d: -f1)"
    echo -e "${rs}\t${chr}\t${pos}\t${ref}\t${alt}\t${gt}\t${gene}\t${why}" >> "$OUT"
  else
    echo -e "${rs}\t${chr}\t${pos}\t.\t.\t./. (ref/not covered)\t${gene}\t${why}" >> "$OUT"
  fi
done

echo "✅ Done: $OUT"
echo
column -t -s$'\t' "$OUT"
echo
echo "Note: full star alleles of CYP2D6/CYP2C9 are more reliably computed with a dedicated"
echo "tool — PyPGx or Stargazer (they account for CNV and phasing). This script is a quick first pass."
echo "Transfer the result into profile/pharmacogenomics.json and genome_extended.md."
