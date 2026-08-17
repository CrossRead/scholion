#!/usr/bin/env bash
# Search for protein-breaking (LoF) variants in clinical genes — a local Ensembl VEP.
#
# Why this exists alongside annotate_clinvar.sh. The ClinVar layer is an
# intersection of coordinates with a database: it sees only what humanity has
# already described and submitted. A frameshifting variant in BRCA1 found for the
# first time would slip past, because it is not in ClinVar. VEP answers a different
# question: not "what is known about this variant" but "what does this variant do
# to the protein" — and it answers that independently of the databases. This is a
# different class of findings, not a recount of the same ones.
#
# Why not the VEP web form: a whole genome cannot be uploaded there because of its
# size, and it would mean sending the genome to a third party. Here everything is
# local, --offline, no network.
#
# Why not the whole genome at once: on Apple Silicon the VEP image runs through x86
# emulation, while the entire clinical interpretation lives on ~0.5 % of the genome.
# The script first slices the VCF by the clinical BED (the same one as for
# DeepVariant) — that is minutes instead of hours. A whole-genome run if wanted:
# SCHOLION_VEP_WHOLE_GENOME=1.
#
# Preparation (once, ~25 GB on disk):
#   # Docker Desktop must be running
#   CACHE="$HOME/genomic_work/vep_cache"; mkdir -p "$CACHE"
#   docker run --platform linux/amd64 --rm -v "$CACHE":/opt/vep/.vep \
#     ensemblorg/ensembl-vep INSTALL.pl -a cf -s homo_sapiens -y GRCh38 -c /opt/vep/.vep
#
# Run from the project root:
#   bash src/ingest/vep_lof_scan.sh
#
# Resumable: intermediate files that are already built are skipped.
set -euo pipefail
. "$(dirname "$0")/_sample.sh"

PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
VCF="${SCHOLION_GENOME_VCF:-$PROJECT/genome/$SAMPLE.full.vcf.gz}"
CACHE="${VEP_CACHE:-$HOME/genomic_work/vep_cache}"
WORK="${VEP_DIR:-$HOME/genomic_work/vep}"
BED="${SCHOLION_CLINICAL_BED:-$WORK/clinical.bed}"
IMAGE="${VEP_IMAGE:-ensemblorg/ensembl-vep}"
WHOLE="${SCHOLION_VEP_WHOLE_GENOME:-0}"

echo "== Pre-flight check =="
command -v docker >/dev/null || { echo "❌ docker is missing (Docker Desktop is not installed)"; exit 1; }
docker info >/dev/null 2>&1 || { echo "❌ docker is not responding — start Docker Desktop"; exit 1; }
command -v bcftools >/dev/null || { echo "❌ bcftools is missing"; exit 1; }
[ -f "$VCF" ] || { echo "❌ no VCF: $VCF"; exit 1; }
[ -d "$CACHE/homo_sapiens" ] || {
  echo "❌ no VEP cache in $CACHE — see the «Preparation» block in the script header"; exit 1; }
mkdir -p "$WORK"
echo "OK: docker + bcftools + VEP cache; work directory $WORK"

if [ ! -s "$BED" ]; then
  echo "== Step 1/5: clinical BED =="
  python3 "$PROJECT/src/ingest/build_clinical_bed.py" "$BED"
else
  echo "== Step 1/5: BED present ($BED) — skipping =="
fi

IN="$WORK/input.vcf.gz"
if [ ! -s "$IN" ]; then
  if [ "$WHOLE" = "1" ]; then
    echo "== Step 2/5: whole-genome input (SCHOLION_VEP_WHOLE_GENOME=1) =="
    cp "$VCF" "$IN"; cp "$VCF.tbi" "$IN.tbi" 2>/dev/null || bcftools index -t "$IN"
  else
    echo "== Step 2/5: slicing the VCF by the clinical BED =="
    bcftools view -R "$BED" -Oz -o "$IN" "$VCF"
    bcftools index -t "$IN"
  fi
  echo "  input variants: $(bcftools index -n "$IN")"
else
  echo "== Step 2/5: input present — skipping ($(bcftools index -n "$IN") variants) =="
fi

OUT="$WORK/vep.tsv"
if [ ! -s "$OUT" ]; then
  echo "== Step 3/5: VEP (offline, no network) =="
  # --pick_allele_gene: one row per allele×gene, otherwise every transcript gets its
  # own row and the table swells by an order of magnitude
  # --check_existing + --af_gnomade/g: known variants get a frequency, new ones stay
  # without it — which is informative in itself
  docker run --platform linux/amd64 --rm \
    -v "$CACHE":/opt/vep/.vep -v "$WORK":/data \
    "$IMAGE" vep \
      --offline --cache --dir_cache /opt/vep/.vep --assembly GRCh38 \
      --input_file /data/"$(basename "$IN")" --output_file /data/"$(basename "$OUT")" \
      --tab --force_overwrite --no_stats \
      --symbol --canonical --biotype --pick_allele_gene \
      --check_existing --af_gnomade --af_gnomadg \
      --fields "Uploaded_variation,Location,Allele,Consequence,IMPACT,SYMBOL,Gene,BIOTYPE,CANONICAL,Existing_variation,gnomADe_AF,gnomADg_AF,CLIN_SIG"
else
  echo "== Step 3/5: VEP output present — skipping =="
fi

GT="$WORK/genotypes.tsv"
if [ ! -s "$GT" ]; then
  echo "== Step 4/5: zygosity and depth from the VCF =="
  # Without this a finding cannot be read: the rule here is «Pathogenic applies to
  # the variant, not to the person», and the first thing that decides is whether it
  # is a heterozygote or not
  bcftools query -f '%CHROM\t%POS\t%REF\t%ALT[\t%GT\t%DP]\n' "$IN" > "$GT"
else
  echo "== Step 4/5: genotypes present — skipping =="
fi

echo "== Step 5/5: LoF filter and cross-check against ACMG SF =="
python3 - "$OUT" "$GT" "$PROJECT" <<'PY'
import json, sys
from pathlib import Path

vep, gtf, project = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
K = project / "src" / "scholion" / "knowledge"
acmg_meta = json.loads((K / "acmg_sf.json").read_text(encoding="utf-8"))
acmg = set(acmg_meta["genes"])

# Consequences that are highly likely to destroy the protein. Missense is
# deliberately NOT included: without predictors (dbNSFP/CADD) it gives noise, not signal.
LOF = {
    "transcript_ablation", "splice_acceptor_variant", "splice_donor_variant",
    "stop_gained", "frameshift_variant", "start_lost", "stop_lost",
}
# Frequency threshold: a pathogenic variant with a population frequency above 0.1 %
# is almost always either an annotation error or a benign polymorphism
AF_MAX = 0.001

gt = {}
for line in gtf.read_text(encoding="utf-8").splitlines():
    f = line.split("\t")
    if len(f) < 6:
        continue
    gt[(f[0].removeprefix("chr"), f[1])] = (f[4], f[5])

def zygosity(g):
    a = g.replace("|", "/").split("/")
    if len(a) != 2 or "." in a:
        return "?"
    if a[0] == a[1]:
        return "homozygote" if a[0] != "0" else "reference"
    return "heterozygote"

rows, header = [], None
for line in vep.read_text(encoding="utf-8").splitlines():
    if line.startswith("##"):
        continue
    if line.startswith("#"):
        header = line[1:].split("\t")
        continue
    if header is None:
        continue
    r = dict(zip(header, line.split("\t")))
    cons = set(r.get("Consequence", "").split(","))
    if not (cons & LOF):
        continue
    if r.get("BIOTYPE") != "protein_coding":
        continue
    def af(key):
        v = r.get(key, "-")
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    freqs = [x for x in (af("gnomADe_AF"), af("gnomADg_AF")) if x is not None]
    if freqs and max(freqs) > AF_MAX:
        continue
    loc = r.get("Location", "")
    chrom, _, rest = loc.partition(":")
    pos = rest.split("-")[0]
    g, dp = gt.get((chrom.removeprefix("chr"), pos), ("./.", "?"))
    rows.append({
        "gene": r.get("SYMBOL", "?"),
        "panel": "ACMG SF" if r.get("SYMBOL") in acmg else "",
        "loc": loc,
        "cons": r.get("Consequence", ""),
        "zyg": zygosity(g),
        "dp": dp,
        "known": r.get("Existing_variation", "-"),
        "af": f"{max(freqs):.2e}" if freqs else "not in gnomAD",
        "clin": r.get("CLIN_SIG", "-"),
        "canon": r.get("CANONICAL", ""),
    })

rows.sort(key=lambda r: (r["panel"] == "", r["gene"], r["loc"]))
out = project / "genome" / "vep_lof_hits.tsv"
with out.open("w", encoding="utf-8") as fh:
    fh.write("gene\tpanel\tlocation\tconsequence\tzygosity\tdepth\t"
             "canonical\tknown\tmax_af\tclinvar\n")
    for r in rows:
        fh.write(f"{r['gene']}\t{r['panel']}\t{r['loc']}\t{r['cons']}\t{r['zyg']}\t"
                 f"{r['dp']}\t{r['canon']}\t{r['known']}\t{r['af']}\t{r['clin']}\n")

in_acmg = [r for r in rows if r["panel"]]
novel = [r for r in rows if r["af"] == "not in gnomAD"]
print(f"  LoF variants after the filter: {len(rows)}")
print(f"  of them in ACMG SF genes: {len(in_acmg)}")
print(f"  of them absent from gnomAD (candidates for «new»): {len(novel)}")
if in_acmg:
    print("\n  ACMG SF genes — review one by one, the same way as ClinVar findings:")
    for r in in_acmg:
        print(f"    {r['gene']:10} {r['loc']:22} {r['cons'][:28]:28} "
              f"{r['zyg']:12} DP={r['dp']:>3} canon={r['canon'] or '-'}")
print(f"\n✓ {out}")
print("""
How to read this. It is NOT a list of diagnoses and not even a list of pathogenic
variants — it is a list of variants that are predicted to break the protein. To each
of them apply the same layer as to ClinVar findings: zygosity, the gene's mode of
inheritance, applicability by sex, penetrance, presence of a phenotype. Plus the
technical filters specific to LoF:
  · the last exon / the last 50 bp — NMD does not fire, and the protein may stay
    functional (this is what the LOFTEE plugin does automatically);
  · a non-canonical transcript — the variant may not touch the main isoform;
  · an indel called through bcftools — the chance of an artefact is higher than for
    a SNP; such positions are worth re-checking through DeepVariant
    (deepvariant_call.sh).
The next step for higher precision is the LOFTEE plugin (--plugin LoF); it needs a
separate installation: the loftee repository, grch38 branch, plus the file
human_ancestor.fa.gz (~1 GB).
""")
PY
