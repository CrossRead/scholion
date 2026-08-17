#!/usr/bin/env bash
# Search for protein-breaking (LoF) variants in clinical genes — WITHOUT the 25 GB VEP cache.
#
# Why this exists alongside annotate_clinvar.sh. The ClinVar layer is an
# intersection of coordinates with a database: it sees only what humanity has
# already described and submitted. A frameshifting variant in BRCA1 found for the
# first time would slip past. The question asked here is a different one: not
# "what is known about this variant" but "what does it do to the protein" — and
# the answer does not depend on whether it is in the databases.
#
# How this differs from vep_lof_scan.sh. The same question, a lighter tool:
# `bcftools csq` predicts consequences from the Ensembl GFF3 transcript model.
# It needs ~100 MB downloaded instead of ~25 GB, no Docker and no x86 emulation,
# and bcftools is already installed. The author is the same as for
# bcftools/samtools (Danecek & McCarthy, Bioinformatics 2017), and on coding
# consequences it is comparable with VEP.
#
# TWO FILTERS ADDED AFTER THE FIRST RUNS:
#
#   1. Canonical transcripts only. Ensembl carries hundreds of thousands of
#      transcripts, including tens of thousands of new models from havana_tagene
#      (long reads). Without the filter, csq computes a consequence for EVERY
#      model, and a "homozygous stop_gained in PTEN" turns out to be a stop codon
#      in an alternative transcript that does not touch the main isoform. In
#      practice most such hits are false. Transcripts tagged
#      tag=Ensembl_canonical / MANE_Select are kept. To get all of them back:
#      SCHOLION_CSQ_ALL_TX=1.
#
#   2. The MHC region is flagged separately. chr6:28.48–33.45 Mb is
#      hyperpolymorphic, the reference is one haplotype out of many, and "LoF"
#      there usually means "a different HLA allele" rather than a broken protein.
#      Unfiltered, HLA genes can take up half of the list.
#
# Run from the project root (the network is only needed on the first run):
#   bash src/ingest/csq_lof_scan.sh
#
# Resumable: intermediate files that are already built are skipped.
set -euo pipefail
. "$(dirname "$0")/_sample.sh"
export LC_ALL=C

PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
VCF="${SCHOLION_GENOME_VCF:-$PROJECT/genome/$SAMPLE.full.vcf.gz}"
REF="${REF_FASTA:-$HOME/genomic_work/reference/GRCh38_no_alt.fa}"
WORK="${CSQ_DIR:-$HOME/genomic_work/csq}"
BED="${SCHOLION_CLINICAL_BED:-$WORK/clinical.bed}"
ALL_TX="${SCHOLION_CSQ_ALL_TX:-0}"
FTP="https://ftp.ensembl.org/pub/current_gff3/homo_sapiens"

echo "== Pre-flight check =="
command -v bcftools >/dev/null || { echo "❌ bcftools is missing"; exit 1; }
[ -f "$VCF" ] || { echo "❌ no VCF: $VCF"; exit 1; }
[ -f "$REF" ] || { echo "❌ no reference: $REF"; exit 1; }
mkdir -p "$WORK"
echo "OK: bcftools + VCF + reference; work directory $WORK"

GFF="$WORK/ensembl.chr.gff3.gz"
if [ ! -s "$GFF" ]; then
  echo "== Step 1/6: Ensembl GFF3 annotation (~100 MB, once) =="
  RAW="$WORK/ensembl.raw.gff3.gz"
  if [ ! -s "$RAW" ]; then
    # the file name contains the release number — it is pulled out of the listing
    # so that the version is not hard-coded and the script does not break on the next release
    NAME="$(curl -sSL "$FTP/" \
      | grep -o 'Homo_sapiens\.GRCh38\.[0-9]\+\.gff3\.gz' | sort -u | head -1)"
    [ -n "$NAME" ] || { echo "❌ could not find the GFF3 name in the listing $FTP/"; exit 1; }
    echo "  downloading $NAME"
    curl -fSL --progress-bar -o "$RAW" "$FTP/$NAME"
  fi
  echo "  renaming chromosomes to chr notation (Ensembl gives 1/2/X/MT)"
  # the reference here is GRCh38_no_alt with a chr prefix; without the renaming
  # bcftools csq silently finds no transcripts at all
  gzip -cd "$RAW" | awk 'BEGIN{OFS="\t"}
      /^##sequence-region/ { if ($2=="MT") $2="chrM"; else $2="chr"$2; print; next }
      /^#/ { print; next }
      { if ($1=="MT") $1="chrM"; else $1="chr"$1; print }' \
    | bgzip -c > "$GFF"
else
  echo "== Step 1/6: GFF3 present ($GFF) — skipping =="
fi

CANON="$WORK/ensembl.canon.gff3.gz"
if [ "$ALL_TX" = "1" ]; then
  echo "== Step 2/6: SCHOLION_CSQ_ALL_TX=1 — taking ALL transcripts (noisy) =="
  USE_GFF="$GFF"
elif [ ! -s "$CANON" ]; then
  echo "== Step 2/6: keeping canonical transcripts only =="
  # two passes: first collect the IDs of the canonical transcripts, then keep the
  # genes, those transcripts and their child exons/CDS/UTRs
  gzip -cd "$GFF" | awk -F'\t' '
      $9 ~ /tag=[^;]*(Ensembl_canonical|MANE_Select)/ {
        if (match($9, /ID=transcript:[^;]+/))
          print substr($9, RSTART+14, RLENGTH-14)
      }' > "$WORK/canon_ids.txt"
  echo "  canonical transcripts: $(wc -l < "$WORK/canon_ids.txt" | tr -d ' ')"
  gzip -cd "$GFF" | awk -F'\t' -v OFS='\t' '
      NR==FNR { keep[$0]=1; next }
      /^#/ { print; next }
      {
        id=""; par=""
        if (match($9, /ID=transcript:[^;]+/))     id  = substr($9, RSTART+14, RLENGTH-14)
        if (match($9, /Parent=transcript:[^;]+/)) par = substr($9, RSTART+18, RLENGTH-18)
        if ($3=="gene" || $3=="ncRNA_gene") { print; next }
        if (id  != "" && (id  in keep)) { print; next }
        if (par != "" && (par in keep)) { print; next }
      }' "$WORK/canon_ids.txt" - | bgzip -c > "$CANON"
  USE_GFF="$CANON"
else
  echo "== Step 2/6: canonical GFF3 present — skipping =="
  USE_GFF="$CANON"
fi

if [ ! -s "$BED" ]; then
  echo "== Step 3/6: clinical BED =="
  python3 "$PROJECT/src/ingest/build_clinical_bed.py" "$BED"
else
  echo "== Step 3/6: BED present — skipping =="
fi

IN="$WORK/input.vcf.gz"
if [ ! -s "$IN" ]; then
  echo "== Step 4/6: slicing the VCF by the clinical BED =="
  bcftools view -R "$BED" -Oz -o "$IN" "$VCF"
  bcftools index -t "$IN"
  echo "  input variants: $(bcftools index -n "$IN")"
else
  echo "== Step 4/6: input present — skipping ($(bcftools index -n "$IN") variants) =="
fi

CSQ="$WORK/csq.vcf.gz"
if [ ! -s "$CSQ" ]; then
  echo "== Step 5/6: consequence prediction =="
  # -l (local predictions) instead of the haplotype-aware mode: the sample is not
  # phased, and the question "does this variant break the protein" does not need
  # the joint effect of neighbouring variants
  bcftools csq -f "$REF" -g "$USE_GFF" -l -Oz -o "$CSQ" "$IN"
  bcftools index -t "$CSQ"
else
  echo "== Step 5/6: annotation present — skipping (to wipe: rm $CSQ*) =="
fi

echo "== Step 6/6: LoF filter and cross-check against ACMG SF =="
bcftools query -f '%CHROM\t%POS\t%REF\t%ALT\t%INFO/BCSQ[\t%GT\t%DP]\n' "$CSQ" \
  > "$WORK/flat.tsv"

python3 - "$WORK/flat.tsv" "$PROJECT" <<'PY'
import json, sys
from pathlib import Path

flat, project = Path(sys.argv[1]), Path(sys.argv[2])
K = project / "src" / "scholion" / "knowledge"
acmg = set(json.loads((K / "acmg_sf.json").read_text(encoding="utf-8"))["genes"])

# Consequences that are highly likely to destroy the protein. Missense is
# deliberately NOT included: without predictors (dbNSFP/CADD) it gives noise, not signal.
LOF = {"stop_gained", "frameshift", "splice_acceptor", "splice_donor",
       "start_lost", "stop_lost", "transcript_ablation"}
MHC = ("chr6", 28477797, 33448354)
MIN_DP = 10          # the threshold from qc_callability.sh: below it the genotype is not decided

def zygosity(g):
    a = g.replace("|", "/").split("/")
    if len(a) != 2 or "." in a:
        return "?"
    if a[0] == a[1]:
        return "homozygote" if a[0] != "0" else "reference"
    return "heterozygote"

rows = []
for line in flat.read_text(encoding="utf-8").splitlines():
    f = line.split("\t")
    if len(f) < 7:
        continue
    chrom, pos, ref, alt, bcsq, gt, dp = f[0], f[1], f[2], f[3], f[4], f[5], f[6]
    if bcsq in (".", ""):
        continue
    for entry in bcsq.split(","):
        p = entry.lstrip("*@").split("|")
        # a leading '*' — a consequence inherited from a stop codon upstream;
        # '@pos' — a reference to another record of a compound variant, not a finding
        if entry.startswith("@") or len(p) < 4:
            continue
        cons = set(p[0].split("&"))
        if not (cons & LOF):
            continue
        gene, transcript, biotype = p[1], p[2], p[3]
        if biotype != "protein_coding":
            continue
        try:
            dp_i = int(dp)
        except ValueError:
            dp_i = 0
        in_mhc = chrom == MHC[0] and MHC[1] <= int(pos) <= MHC[2]
        rows.append({
            "gene": gene,
            "panel": "ACMG SF" if gene in acmg else "",
            "loc": f"{chrom}:{pos}",
            "change": f"{ref}>{alt}",
            "cons": p[0],
            "zyg": zygosity(gt),
            "dp": dp_i,
            "tr": transcript,
            "dna": p[6] if len(p) > 6 else "",
            "aa": p[5] if len(p) > 5 else "",
            "indel": "indel" if len(ref) != len(alt) else "SNP",
            "mhc": in_mhc,
        })

seen, uniq = set(), []
for r in rows:
    k = (r["loc"], r["gene"], r["cons"])
    if k in seen:
        continue
    seen.add(k)
    uniq.append(r)

# The reason a finding is NOT treated as a candidate. The order matters:
# the first rule that fires is the one recorded.
def dismissal(r):
    if r["mhc"]:
        return "MHC — a hyperpolymorphic region, «LoF» there usually = a different HLA allele"
    if r["dp"] < MIN_DP:
        return f"depth {r['dp']}× below the {MIN_DP}× threshold — the genotype is not decided"
    if r["zyg"] == "homozygote" and r["panel"]:
        return "homozygous LoF in an ACMG gene with no lifelong phenotype — check the gnomAD frequency"
    return ""

for r in uniq:
    r["dismiss"] = dismissal(r)

uniq.sort(key=lambda r: (r["dismiss"] != "", r["panel"] == "", r["gene"], r["loc"]))
out = project / "genome" / "csq_lof_hits.tsv"
with out.open("w", encoding="utf-8") as fh:
    fh.write("gene\tpanel\tlocation\tchange\ttype\tconsequence\tzygosity\tdepth\t"
             "region\ttranscript\taa_change\tdna_change\tdismissed_because\n")
    for r in uniq:
        fh.write(f"{r['gene']}\t{r['panel']}\t{r['loc']}\t{r['change']}\t{r['indel']}\t"
                 f"{r['cons']}\t{r['zyg']}\t{r['dp']}\t{'MHC' if r['mhc'] else ''}\t"
                 f"{r['tr']}\t{r['aa']}\t{r['dna']}\t{r['dismiss']}\n")

live = [r for r in uniq if not r["dismiss"]]
dead = [r for r in uniq if r["dismiss"]]
print(f"  LoF rows in total: {len(uniq)}")
print(f"  dismissed automatically: {len(dead)}"
      f"  (MHC {sum(1 for r in dead if r['mhc'])}, "
      f"low depth {sum(1 for r in dead if not r['mhc'] and r['dp'] < MIN_DP)}, "
      f"homozygotes in ACMG {sum(1 for r in dead if r['dismiss'].startswith('homozygous'))})")
print(f"  left to review by hand: {len(live)}")
if live:
    print("\n  Candidates:")
    for r in live:
        mark = "★" if r["panel"] else " "
        print(f"   {mark} {r['gene']:10} {r['loc']:18} {r['cons'][:22]:22} "
              f"{r['zyg']:12} {r['indel']:5} DP={r['dp']:>3} {r['tr']}")
print(f"\n✓ {out}  (the dismissed_because column explains every dismissal)")
print("""
How to read this. It is NOT a list of diagnoses and not even a list of pathogenic
variants — these are variants that are predicted to break the protein. To each
remaining one apply the same layer as to ClinVar findings: zygosity, mode of
inheritance, applicability by sex, penetrance, presence of a phenotype. Plus three
checks that are not automated here:
  · the last exon / the last 50 bp — NMD does not fire, and the truncated protein
    may still work (this is what the LOFTEE plugin in VEP does);
  · a gnomAD frequency above ~0.1 % — almost certainly a benign polymorphism;
    check them one by one at gnomad.broadinstitute.org;
  · an «indel» — with bcftools the chance of an artefact is higher than for a SNP;
    re-call such positions through DeepVariant (deepvariant_call.sh).
If something is still left after that — only then does it make sense to install the
full VEP with LOFTEE and gnomAD (vep_lof_scan.sh) and run it on those positions.""")
PY
