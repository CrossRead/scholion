#!/usr/bin/env bash
# Callability of the clinical genes: how many bases were actually read, and at what depth.
#
# Why. The claim "zero pathogenic findings across the ACMG SF genes" is honest
# exactly to the extent that those genes were read. A gene covered at 70 % yields
# the same zero as a gene covered at 100 % — and only measurement tells them apart.
# The script turns "zero findings" into "zero findings across N % of bases at depth X".
#
# What it does:
#   1) builds a PER-GENE BED (one interval per gene, no merging — otherwise per-gene
#      statistics are impossible). The coordinates are obtained the same way as in
#      build_clinical_bed.py: min/max of the positions of the gene's variants in the
#      local NCBI ClinVar VCF via the GENEINFO field, ±10 kb. Not from memory;
#   2) computes the depth for each gene. By default — through samtools with
#      per-interval access via the index: NOTHING HAS TO BE INSTALLED, and only a
#      fraction of a percent of the BAM is read instead of the whole file. If
#      mosdepth is present in the system it is used automatically (it also gives
#      the whole-genome mean);
#   3) writes the summary to profile/callability.tsv plus an explicit list of "weak" genes.
#
# Run from the project root:
#   bash src/ingest/qc_callability.sh
#
# Time: minutes with samtools, tens of minutes with mosdepth (that one reads the whole BAM).
# To force the engine: ENGINE=samtools or ENGINE=mosdepth.
# Resumable: to wipe the cache — rm -rf ~/genomic_work/callability
set -euo pipefail
. "$(dirname "$0")/_sample.sh"
# IMPORTANT: without this, awk under a locale that uses a comma as the decimal
# separator prints fractional numbers as "24,9834", and the Python parsing step
# fails. This only shows up on live data.
export LC_ALL=C

BAM="${BAM:-$HOME/genomic_work/$SAMPLE/$SAMPLE.merged.bam}"
CLINVAR="${SCHOLION_CLINVAR_VCF:-$HOME/genomic_work/clinvar/clinvar.vcf.gz}"
WORK="${CALLABILITY_DIR:-$HOME/genomic_work/callability}"
PROJECT="$(cd "$(dirname "$0")/../.." && pwd)"
MINMAPQ="${MINMAPQ:-20}"          # reads with a lower MAPQ do not count as read
THRESHOLDS="1,10,20,30"           # 10× — the minimum for a heterozygote, 20× — the working
                                  # clinical threshold, 30× — the WGS standard

echo "== Pre-flight check =="
command -v samtools >/dev/null || { echo "❌ samtools is missing"; exit 1; }
[ -f "$BAM" ] || { echo "❌ no BAM: $BAM"; exit 1; }
[ -f "$BAM.bai" ] || [ -f "${BAM%.bam}.bai" ] || { echo "❌ no .bai index next to the BAM"; exit 1; }
[ -f "$CLINVAR" ] || { echo "❌ no ClinVar VCF: $CLINVAR (SCHOLION_CLINVAR_VCF=...)"; exit 1; }
mkdir -p "$WORK"

if [ -z "${ENGINE:-}" ]; then
  if command -v mosdepth >/dev/null; then ENGINE=mosdepth; else ENGINE=samtools; fi
fi
echo "OK: samtools + BAM + ClinVar; depth engine: $ENGINE; directory $WORK"

BED="$WORK/genes.bed"
if [ ! -s "$BED" ]; then
  echo "== Step 1/3: per-gene BED from ClinVar GENEINFO =="
  python3 - "$PROJECT" "$CLINVAR" "$BED" <<'PY'
import gzip, json, re, sys
from pathlib import Path

project, clinvar, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
K = project / "src" / "scholion" / "knowledge"
PAD = 10_000
# GENEINFO may be the FIRST INFO field — in that case it is preceded by a tab, not a ';'
GI_RE = re.compile(r"[;\t]GENEINFO=([^;\s]*)")

acmg = set(json.loads((K / "acmg_sf.json").read_text(encoding="utf-8"))["genes"])
genes = set(acmg)
cpic_path = K / "cpic_drug_gene.json"
cpic_genes = set()
if cpic_path.exists():
    cpic = json.loads(cpic_path.read_text(encoding="utf-8"))
    cpic_genes |= set(cpic.get("genes", {}) or {})
    cpic_genes |= set(cpic.get("genes_of_interest", []) or [])
genes |= cpic_genes

span = {}
with gzip.open(clinvar, "rt", errors="replace") as fh:
    for line in fh:
        if line[0] == "#":
            continue
        m = GI_RE.search(line)
        if not m:
            continue
        hit = {p.split(":")[0] for p in m.group(1).split("|")} & genes
        if not hit:
            continue
        f = line.split("\t", 3)
        chrom, pos = f[0], int(f[1])
        for g in hit:
            c, lo, hi = span.get(g, (chrom, pos, pos))
            if c == chrom:
                span[g] = (c, min(lo, pos), max(hi, pos))

missing = sorted(genes - set(span))
rows = []
for g, (c, lo, hi) in span.items():
    tag = "ACMG" if g in acmg else "CPIC"
    rows.append((c, max(0, lo - PAD), hi + PAD, f"{g}|{tag}"))

def key(c):
    return (0, int(c)) if c.isdigit() else (1, {"X": 0, "Y": 1}.get(c, 2))

rows.sort(key=lambda r: (key(r[0]), r[1]))
with out.open("w", encoding="utf-8") as fh:
    for c, lo, hi, name in rows:
        fh.write(f"chr{c}\t{lo}\t{hi}\t{name}\n")
total = sum(hi - lo for _, lo, hi, _ in rows)
print(f"  genes in the list: {len(genes)} (ACMG SF {len(acmg)} + CPIC {len(cpic_genes)})")
print(f"  intervals in the BED: {len(rows)}, {total/1e6:.1f} Mb in total")
if missing:
    print(f"  ⚠ no ClinVar records, so not in the BED: {', '.join(missing)}")
PY
else
  echo "== Step 1/3: BED present ($BED) — skipping =="
fi

DEPTH="$WORK/per_gene.tsv"
if [ ! -s "$DEPTH" ]; then
  echo "== Step 2/3: depth per gene ($ENGINE) =="
  if [ "$ENGINE" = "mosdepth" ]; then
    PREFIX="$WORK/$SAMPLE"
    [ -s "$PREFIX.regions.bed.gz" ] || \
      mosdepth --by "$BED" --thresholds "$THRESHOLDS" --no-per-base \
               --mapq "$MINMAPQ" "$PREFIX" "$BAM"
    python3 - "$PREFIX" "$DEPTH" <<'PY'
import gzip, sys
from pathlib import Path
prefix, out = Path(sys.argv[1]), Path(sys.argv[2])
means = {}
with gzip.open(str(prefix) + ".regions.bed.gz", "rt") as fh:
    for line in fh:
        f = line.rstrip("\n").split("\t")
        means[f[3]] = float(f[4])
with gzip.open(str(prefix) + ".thresholds.bed.gz", "rt") as fh, \
     out.open("w", encoding="utf-8") as o:
    header = fh.readline().rstrip("\n").split("\t")
    idx = {n: i for i, n in enumerate(header)}
    o.write("name\tlength\tmean\tb1\tb10\tb20\tb30\n")
    for line in fh:
        f = line.rstrip("\n").split("\t")
        ln = int(f[2]) - int(f[1])
        if not ln:
            continue
        g = lambda c: f[idx[c]] if c in idx else "0"
        o.write(f"{f[3]}\t{ln}\t{means.get(f[3],0.0):.4f}\t"
                f"{g('1X')}\t{g('10X')}\t{g('20X')}\t{g('30X')}\n")
PY
  else
    # samtools depth one interval at a time: access goes through the .bai, so only
    # the needed slice of the BAM is read. -a — including positions with zero
    # coverage, otherwise unread bases simply vanish from the output and the
    # fraction comes out overstated
    : > "$DEPTH.part"
    printf 'name\tlength\tmean\tb1\tb10\tb20\tb30\n' > "$DEPTH.part"
    TOTAL=$(wc -l < "$BED" | tr -d ' ')
    N=0
    while IFS=$'\t' read -r CHROM START END NAME; do
      N=$((N + 1))
      printf '\r  %s/%s %-24s' "$N" "$TOTAL" "${NAME%%|*}" >&2
      samtools depth -a -Q "$MINMAPQ" -r "$CHROM:$((START + 1))-$END" "$BAM" \
        | awk -v name="$NAME" -v len="$((END - START))" '
            { s += $3; n++; if ($3 >= 1) b1++; if ($3 >= 10) b10++;
              if ($3 >= 20) b20++; if ($3 >= 30) b30++ }
            END { printf "%s\t%d\t%.4f\t%d\t%d\t%d\t%d\n",
                   name, len, (len ? s / len : 0), b1+0, b10+0, b20+0, b30+0 }' \
        >> "$DEPTH.part"
    done < "$BED"
    printf '\r%-60s\r' '' >&2
    mv "$DEPTH.part" "$DEPTH"
  fi
else
  echo "== Step 2/3: depth already computed — skipping =="
fi

echo "== Step 3/3: summary =="
python3 - "$DEPTH" "$PROJECT" "$WORK/$SAMPLE.mosdepth.summary.txt" "$BED" <<'PY'
import statistics as st
import sys
from pathlib import Path

depth, project = Path(sys.argv[1]), Path(sys.argv[2])
summary, bedfile = Path(sys.argv[3]), Path(sys.argv[4])

genome_mean = None
if summary.exists():
    for line in summary.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if f and f[0] == "total":
            genome_mean = float(f[3])

# the chromosome is needed so as not to raise an alarm on chrX in a male: there is
# one copy there, i.e. half the depth — that is expected biology, not a coverage gap
chrom_of = {}
span_of = {}
if bedfile.exists():
    for line in bedfile.read_text(encoding="utf-8").splitlines():
        f = line.split("\t")
        if len(f) >= 4:
            g = f[3].partition("|")[0]
            chrom_of[g] = f[0]
            # The interval each percentage was measured over. It was already in
            # hand here and thrown away one line later, so the engine knew WHICH
            # genes were under-read and could hand the list to nobody: a
            # laboratory asked to re-read something needs coordinates, and a gene
            # name is not one.
            try:
                span_of[g] = (int(f[1]), int(f[2]))
            except (ValueError, IndexError):
                pass

rows = []
for i, line in enumerate(depth.read_text(encoding="utf-8").splitlines()):
    if i == 0:
        continue
    f = line.split("\t")
    if len(f) < 7:
        continue
    name, ln = f[0], int(f[1])
    if not ln:
        continue
    gene, _, tag = name.partition("|")
    chrom = chrom_of.get(gene, "")
    rows.append({
        # a comma as the decimal separator — a legacy of runs made before LC_ALL=C;
        # both forms are read so that the depth does not have to be recomputed
        "gene": gene, "tag": tag or "?", "len": ln, "chrom": chrom,
        "start": span_of.get(gene, ("", ""))[0], "end": span_of.get(gene, ("", ""))[1],
        "hemi": chrom in ("chrX", "chrY"),   # one copy in a male
        "mean": float(f[2].replace(",", ".")),
        "p1": 100.0 * int(f[3]) / ln, "p10": 100.0 * int(f[4]) / ln,
        "p20": 100.0 * int(f[5]) / ln, "p30": 100.0 * int(f[6]) / ln,
    })

# THE REFERENCE POINT is the panel median, not an absolute threshold. A lesson from
# the project's history: a threshold that fires on almost everything carries no
# information. When the genome-wide mean depth sits below 30×, the fraction of bases
# at ≥30× cannot be high for ANY gene — that is arithmetic, not a defect. So the
# judgement rests on TWO things:
#   · ≥10× — the real threshold for a confident heterozygote call;
#   · the ratio of the gene's depth to the panel median — "is this gene worse than its neighbours?".
med = st.median(r["mean"] for r in rows) if rows else 0.0
for r in rows:
    # for a hemizygous locus in a male the expectation is half the median
    expected = med / 2 if r["hemi"] else med
    r["rel"] = r["mean"] / expected if expected else 0.0

rows.sort(key=lambda r: (r["p10"], r["rel"]))
out = project / "profile" / "callability.tsv"
with out.open("w", encoding="utf-8") as fh:
    # `start` and `end` are appended rather than inserted, so a reader that
    # indexes by header name keeps working and one that counted columns is not
    # silently shifted. They are what makes the weak list exportable at all: a
    # percentage names a gene, and a laboratory asked to re-read something needs
    # coordinates. Until they were written down the engine had the list and could
    # hand it to nobody.
    fh.write("gene\tpanel\tchrom\tlength_bp\tmean_depth\trel_to_panel\t"
             "pct_1x\tpct_10x\tpct_20x\tpct_30x\tstart\tend\n")
    for r in rows:
        fh.write(f"{r['gene']}\t{r['tag']}\t{r['chrom']}\t{r['len']}\t{r['mean']:.1f}\t"
                 f"{r['rel']:.2f}\t{r['p1']:.1f}\t{r['p10']:.1f}\t"
                 f"{r['p20']:.1f}\t{r['p30']:.1f}\t{r.get('start','')}\t{r.get('end','')}\n")

acmg = [r for r in rows if r["tag"] == "ACMG"]
if genome_mean is not None:
    print(f"  mean depth across the genome: {genome_mean:.1f}×")
print(f"  median depth across the panel: {med:.1f}× — that is the sequencing level")
for label, sel in (("ACMG SF", acmg), ("whole panel", rows)):
    if sel:
        w = sum(r["len"] for r in sel)
        p10 = sum(r["p10"] * r["len"] for r in sel) / w
        p20 = sum(r["p20"] * r["len"] for r in sel) / w
        print(f"  {label}: genes {len(sel)}, ≥10× {p10:.1f} %, ≥20× {p20:.1f} %")

# Flag 1: too few bases are usable for calling a heterozygote
weak = [r for r in rows if r["p10"] < 90.0]
# Flag 2: the gene is noticeably worse than its neighbours in the panel — a sign of a
# difficult zone (pseudogene, high GC), even if the absolute percentages look decent
odd = [r for r in rows if r["rel"] < 0.85 and r not in weak]

print(f"\n  ⚠ Genes with less than 90 % covered at ≥10× — {len(weak)} of {len(rows)}:")
for r in weak:
    note = " (chrX, one copy in a male — half the depth is expected)" if r["hemi"] else ""
    print(f"    {r['gene']:10} {r['tag']:5} {r['mean']:5.1f}×  rel.{r['rel']:4.2f}  "
          f"≥10× {r['p10']:5.1f} %  ≥1× {r['p1']:5.1f} %{note}")
if not weak:
    print("    none")
if odd:
    print(f"\n  Below their panel neighbours (rel. < 0.85) but above the ≥10× threshold — {len(odd)}:")
    for r in odd:
        print(f"    {r['gene']:10} {r['tag']:5} {r['mean']:5.1f}×  rel.{r['rel']:4.2f}  "
              f"≥10× {r['p10']:5.1f} %")
print(f"\n✓ {out}")
print("""
How to read this.
  · When the mean depth is below 30×, the fraction at ≥30× is low for ALL genes —
    that is the arithmetic of sequencing depth, not a gap. Absolute thresholds are
    useless here.
  · The working threshold is ≥10×: below it a heterozygote may be indistinguishable
    from the reference, and "no findings" stops meaning anything.
  · chrX in a male comes at half depth by construction. That is not a gap: a
    hemizygous locus is called more confidently than a diploid one at the same depth.
  · Genes with a ratio below 0.85 but a normal ≥10× are usually known difficult
    zones (pseudogenes, high GC), not a defect of that particular run.
A negative result of the ACMG scan applies to the genes OUTSIDE both lists.""")
PY
