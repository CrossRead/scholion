# Preparing the genome: from raw sequencing data to the VCF the application reads

This guide describes **the whole path from what the laboratory hands you to a working genomic database for the project**: alignment to the reference, variant calling, indexing, placing the files into `genome/`, ClinVar annotation and verifying the result. The running example is whole-genome sequencing from **Evogen** (`evogenlab.ru`), but the steps are the same for any laboratory that gives you FASTQ.

The document is written so that **a person can carry it out by hand in a terminal**, and so that **Claude Cowork** can work from the same text — the assistant has its own section with the boundaries of what it may do and a machine-readable checklist (§11). There are no personal data in this document: wherever a sample identifier is needed, it is written as `<SAMPLE>`.

> This is an engineering guide to data processing, not a medical document. Any genetic conclusion is a "second opinion" and a reason to talk to a doctor — not a diagnosis and not a prescription.

---

## 0. Where we are heading: what the finished result looks like

The application and the skill read the genome from the `genome/` folder in the project root. The minimum sufficient set is two files:

```
genome/
  <SAMPLE>.full.vcf.gz        # full genomic VCF, GRCh38 build, bgzip compression
  <SAMPLE>.full.vcf.gz.tbi    # tabix index (without it, locus lookup does not work)
```

The rules by which the code finds this database (`src/scholion/genome.py`):

- the alphabetically first `genome/*.vcf.gz` is taken, **except** the derived `*.clinvar.vcf.gz`; the path can be set explicitly through the environment variable `SCHOLION_GENOME_VCF`;
- a `.tbi` next to it is mandatory — otherwise lookup by position is impossible;
- reading requires `bcftools` on the `PATH` (the best option), or the python package `pysam`, or — as a bare fallback — the built-in reader `tabixlite`, for which the `.tbi` is enough.

The complete set you end up with after all of the optional steps looks like this:

| File in `genome/` | Created by | What it gives you in the application |
|---|---|---|
| `<SAMPLE>.full.vcf.gz` + `.tbi` | §5 (`call_full_vcf.sh`) | lookup of any locus, APOE, pharmacogenetics, the Genome tab |
| `<SAMPLE>.clinvar.vcf.gz` + `.tbi` | §6 (`annotate_clinvar.sh`) | annotated VCF with the `CLNSIG`/`CLNDN` fields |
| `clinvar_hits.tsv` | §6 | "Significant findings", by tier |
| `clinvar_meta.json` | §6 | which ClinVar version was used (provenance) |
| `whats_new.json` | §6 (`update_check.sh`) | "what's new" when the databases are updated |
| `scoring_sites.vcf.gz` (+ `_ext`) | §7 | polygenic scores (PGS) with honest position coverage |
| `longevity_sites.vcf.gz`, `longevity_rsmap.json` | §7 | the longevity layer (LongevityMap × your genotypes) |

Without a VCF the application works fully in all its other parts (labs, prescriptions, lifestyle), and the genomic functions honestly answer "database not connected".

---

## 1. What the laboratory delivers and which of it is usable

**The Evogen case (whole-genome sequencing).** Through the personal account, or on physical media, you receive a folder of the form `EvogenGenomeApp/EvogemRawData/Первичные данные полногеномного секвенирования_<SAMPLE>/` ("Primary whole-genome sequencing data"), and inside it files in pairs: `*_1.fq.gz` and `*_2.fq.gz` — several pairs of forward and reverse reads, platform **MGI / DNBSEQ**, tens of gigabytes in total. Plus a separate PDF report from the laboratory — useful for cross-checking, but the application does not need it: the report covers only a small fraction of the loci, and the point of this guide is to obtain **the whole genome**, not a digest of it.

What to do if your input is something else:

- **BAM or CRAM** (the laboratory has already aligned the reads) — you skip the alignment phase (§4) entirely and start at §5, setting `BAM=/path/to/file.bam`. Just make sure the alignment was done against **GRCh38**; if it is on GRCh37/hg19, it is easier to realign from FASTQ than to lift over.
- **A ready-made VCF from the laboratory** — check the build and the completeness (`bcftools stats`); if it is GRCh38 and it is a whole genome, `bgzip` + `tabix` and placing it into `genome/` is enough (§5, the "put it into the project" step).
- **A consumer chip (23andMe, AncestryDNA, MyHeritage)** — this is not a whole genome but roughly 600 thousand positions, and almost always on GRCh37. The path is a different one (converting raw → VCF plus liftover to GRCh38) and is described in `genome/README.md`, route B. The key limitation: on a chip "no variant" is **not the same as** "reference", and polygenic scores from BAM are unavailable.

**Reference build.** We work on **GRCh38 without alt contigs** (`GRCh38_no_alt`, chr notation). The Evogen report does not state the build explicitly — worth keeping in mind when you cross-check coordinates from the report against coordinates from the VCF.

---

## 2. What this work demands, and where it must not be run

**Resources.** 8+ cores, 16+ GB RAM. Free disk: **~120 GB** for targeted mode, **~250 GB** for full WGS via DeepVariant. Time is measured in hours, and for the alignment phase in days rather than hours: tens of gigabytes of reads on 8–12 cores of a Mac take on the order of **12–30 hours** (`bwa-mem2` is roughly twice as fast as `bwa`, but needs more memory for the index); full variant calling by windows across all cores adds **several more hours**. This is a background job, not a sitting: you start it and leave it running.

**Where to run it — only on your own machine, in an ordinary terminal** (or through Claude Code started locally). Three reasons, each of them sufficient on its own:

1. Raw reads are the most private data you have, and there are tens of gigabytes of them. They do not go up into the cloud: neither by volume nor by privacy.
2. The Cowork bridge to your computer (`device_bash`) is an isolated sandbox with a **45-second** limit per call, without `bwa`/`samtools` and **without network access**. Downloading the reference or aligning the genome from there is physically impossible. A background process started inside such a call dies with the call.
3. Intermediate files (tens of gigabytes of BAM) must not end up in cloud sync — see the next point.

**Working folder — outside iCloud.** Keep `WORKDIR` and scratch on a local disk: `~/genomic_work/<SAMPLE>` and `~/genomic_work/scratch`. If temporary files end up in `iCloud Drive`, `samtools sort`/`markdup` fail with "Operation timed out" on multi-gigabyte temporary BAMs. The `fastq_to_vcf.sh` script deliberately checks the path and refuses to work if it sees `Mobile Documents`/`CloudDocs` in it. The project itself may perfectly well live in iCloud — only the heavy intermediate files are forbidden.

**About zsh.** In the macOS terminal the `!` character **cannot** be placed inside double quotes — it expands as history substitution. If the path to the project contains `!`, escape it and the spaces with a backslash, or use single quotes.

---

## 3. Installing the tools (once)

```bash
# the essentials: working with alignments and calling variants
brew install samtools bcftools

# aligner: bwa is reliable on Apple Silicon, bwa-mem2 is faster
brew tap brewsci/bio
brew install bwa                 # or: brew install bwa-mem2
# the script picks bwa-mem2 by itself if it is installed, otherwise bwa

# only for full WGS mode via DeepVariant:
# install Docker Desktop
```

If `brew tap brewsci/bio` does not go through, there is an equivalent alternative via conda:

```bash
conda create -n geno -c bioconda -c conda-forge bwa samtools bcftools -y
conda activate geno
```

To check that everything is in place: `bwa 2>&1 | head -3; samtools --version | head -1; bcftools --version | head -1`.

---

## 4. Step 1: aligning the reads to the reference (the longest phase)

The whole phase is done by a single script — `src/ingest/fastq_to_vcf.sh`. It downloads the GRCh38 no-alt reference, builds the indexes, aligns all the FASTQ pairs, merges the result and marks duplicates. Run it from the project root:

```bash
cd /path/to/Scholion-project-files

FASTQ_DIR="/path/to/Первичные данные полногеномного секвенирования_<SAMPLE>" \
WORKDIR="$HOME/genomic_work/<SAMPLE>" \
bash src/ingest/fastq_to_vcf.sh
```

What happens inside, step by step, so that it can be repeated by hand or followed in the log:

1. **Tool check** — if any of them is missing, the script stops and prints what to install.
2. **Reference.** `GRCh38_no_alt.fa` is downloaded into `REF_DIR` (by default `~/genomic_work/reference`) from the UCSC mirror (`hg38.analysisSet.fa.gz`; the fallback is NCBI), then `samtools faidx` and the aligner index. Indexing takes about an hour and 5–10 GB. It is done once per machine: repeat runs and other samples reuse the index.
3. **Aligning the pairs.** It finds all `*_1.fq.gz`, checks for the matching `*_2.fq.gz` for each of them, and aligns the pair into a sorted BAM, writing the read group (`SM:<SAMPLE>`, `PL:DNBSEQ`). BAMs that are already finished are skipped — **the run can be interrupted and resumed**, no work is lost.
4. **Merging and duplicates.** All the per-file BAMs are merged, then `fixmate` → sorting → `markdup` → `<SAMPLE>.markdup.bam` plus an index. With `CLEANUP=1` (the default) the intermediate per-file BAMs are deleted — that saves tens of gigabytes.
5. **Variant calling** — depends on the mode, see below.

**The variables that control the run:** `FASTQ_DIR`, `WORKDIR`, `REF_DIR`, `THREADS` (all cores by default), `MODE` (`targeted` | `wgs`), `CLEANUP`, `SCRATCH`.

### Two variant-calling modes

| | `targeted` (default) | `wgs` |
|---|---|---|
| Tools | bwa/bwa-mem2, samtools, bcftools | the same + Docker (DeepVariant) |
| What you get | genotypes at ~15 target loci (`<SAMPLE>.targets.vcf.gz`) | a full genomic VCF at reference-grade accuracy |
| Disk / time | ~120 GB / less | ~250 GB / longer |
| When to choose it | to get pharmacogenetics and APOE quickly | when you need maximum accuracy on indels |

The target BED of the targeted mode covers `APOE`, `CYP2C9`, `CYP2C19`, `CYP2D6`, `SLCO1B1`, `DPYD`, `VKORC1`, `TPMT`, `MTHFR`. To turn its result into a readable table:

```bash
bash src/ingest/extract_pgx_loci.sh "$HOME/genomic_work/<SAMPLE>/<SAMPLE>.targets.vcf.gz"
# → pgx_target_loci.tsv next to the VCF: rsid, position, genotype, gene, why it matters
```

**Important to understand:** the targeted mode is an accelerated slice, and it does **not** produce a database for the application. Full operation needs the full VCF (§5). The practical order is this: first run the alignment (it is needed in any case), get the targeted slice for quick answers, and then compute the full VCF on the same BAM — **the alignment is not repeated**.

---

## 5. Step 2: a full genomic VCF from a finished BAM

The script `src/ingest/call_full_vcf.sh` takes an already aligned BAM and calls variants across the whole genome without Docker: the genome is cut into windows of ~20 million bp (so that all cores stay busy to the end; otherwise the "tail" gets stuck on one huge chr1), `bcftools mpileup | call -mv` runs on each window in parallel, then `concat` + `norm` (splitting multiallelics) and indexing.

```bash
cd /path/to/Scholion-project-files
WORKDIR="$HOME/genomic_work/<SAMPLE>" bash src/ingest/call_full_vcf.sh
```

The script chooses the BAM itself: `<SAMPLE>.markdup.bam`, and if that is absent or empty — `<SAMPLE>.merged.bam`; it can be set explicitly through `BAM=`. It **copies the finished database into the project's `genome/`** by itself (the folder is set through `PROJECT_DIR`, the current directory by default). The output is on the order of **4–5 million variants**, a file of ~100–200 MB.

The fully automatic "start it and forget it" variant: `auto_full_vcf.sh` waits for the alignment to genuinely finish (no `bwa`/`samtools` processes and the size of `markdup.bam` has stopped changing — confirmed twice), then starts the full VCF computation and the ClinVar annotation itself, writes a log and sends system notifications:

```bash
nohup bash src/ingest/auto_full_vcf.sh >/dev/null 2>&1 &
tail -f "$HOME/genomic_work/<SAMPLE>/auto_full_vcf.log"   # progress
pkill -f auto_full_vcf.sh                                 # cancel the wait
```

**If something failed during the merge** (the typical case being that the disk ran out of space), there is a recovery path that **does not repeat the alignment**. `resume_merge_call.sh` cleans up stuck temp files and the empty stub of `markdup.bam`, merges the surviving `*.sorted.bam` files by coordinate **without markdup** (for DNBSEQ, with its low duplication rate, this is a justified compromise: markdup is expensive in disk space), and computes the full VCF on the merged `merged.bam`.

**Placing the files by hand**, if you computed the VCF your own way:

```bash
bgzip -c my.vcf > genome/<SAMPLE>.full.vcf.gz     # if it is not bgzip yet
tabix -p vcf genome/<SAMPLE>.full.vcf.gz          # or: bcftools index -t ...
```

The name can be anything, as long as it is the only (or alphabetically first) `*.vcf.gz` in `genome/` and there is a `.tbi` next to it.

---

## 6. Step 3: clinically significant findings (ClinVar) — recommended

The curated catalogue of loci inside the project is a "hot" list for pharmacogenetics. Whereas "all clinically significant variants known to mankind" is the **ClinVar** database from NCBI, which is updated weekly. Keeping a copy of it inside the project makes no sense: the right approach is to pull a fresh one each time and annotate **your** VCF with it.

```bash
bash src/ingest/annotate_clinvar.sh
```

The script finds your VCF in `genome/` (or takes `SCHOLION_GENOME_VCF`), downloads a fresh ClinVar for GRCh38, annotates and creates `genome/<SAMPLE>.clinvar.vcf.gz`, `genome/clinvar_hits.tsv` (the significant ones: pathogenic, likely pathogenic, risk factors, drug response) and `clinvar_meta.json` with the database version. The only thing that leaves your machine is the request to the public ClinVar — **your genome is not sent anywhere**.

Periodic updating (a button in the application, by hand or on a monthly schedule): `bash src/ingest/update_check.sh` — it takes a snapshot of the current findings, re-annotates with a fresh ClinVar, computes the difference and writes `genome/whats_new.json` ("what is new compared with last time"). It requires `bcftools` on the `PATH`; when started from the GUI application, the PATH is extended with the Homebrew directories.

---

## 7. Step 4: polygenic scores and the longevity layer — optional

Both layers require a **BAM**, not just a VCF, and here is why: an ordinary VCF contains only the positions where you differ from the reference. For a polygenic score this breaks coverage — reference-homozygous scoring positions are simply absent, and the calculator honestly counts them as "not covered". So the positions needed are **re-genotyped** from the BAM separately, with calling done without the `-v` filter so that `0/0` calls stay in the output.

**Polygenic scores (PGS Catalog).** The computation is done by a separate sidecar process, `just-prs-mcp`, which is given only the **local path** to your VCF; the only things that leave the machine are requests for public scoring files. The order is this:

```bash
bash src/ingest/setup_just_prs.sh          # install uv/uvx, warm up the package, selftest the transport

# first pass over the full VCF: it fills the cache of harmonised scoring files
# (~/Library/Caches/just-prs/scores). Coverage here will be understated — that is normal.
PYTHONPATH=src python3 -m scholion.prs report --vcf genome/<SAMPLE>.full.vcf.gz >/dev/null

python3 src/ingest/prs_extract_sites.py scoring_sites.bed        # cache → BED of the needed positions
bash src/ingest/prs_genotype_sites.sh scoring_sites.bed          # re-genotype from BAM → genome/scoring_sites.vcf.gz

# honest computation over the re-genotyped positions: the raw report goes to a separate file…
PYTHONPATH=src python3 -m scholion.prs report --vcf genome/scoring_sites.vcf.gz \
  > profile/prs_report_raw.json
# …and then the distillate for the application is built (schema + validation; see the explanation below)
python3 src/ingest/prs_results_build.py profile/prs_report_raw.json
```

Three pitfalls, all of them already handled in code, but you need to know about them.

*First*, the raw output of `prs report` is a nested structure, while the application reads
a flat one. Writing the raw output straight into `profile/prs_results.json` is not allowed — the tab
will show "no model" for every trait. The building is done by `prs_results_build.py`: it
converts the schema, checks each trait (coverage ≤ 1, a percentile exists),
marks the unusable ones, and on repeat runs merges the result with the old file
and leaves a backup.

*Second*, `bcftools mpileup` at one coordinate can emit two lines — one at SNP level
and one indel (this is normal for repeats). Naive PGS counters treat each line of a position
separately: the weight enters the sum twice, and "coverage" comes out above 1 — that is the
sign by which double counting is caught. `prs_genotype_sites.sh` now collapses such
positions itself (allele-aware, using the models from the cache). If the model cache is still empty, the script
warns you — in that case repeat it after the first `prs report`. Diagnostics at any
moment: `python3 src/ingest/prs_verify.py --all` (an independent recomputation of coverage;
`--compare` shows what the discrepancies cost in score points).

*Third*, the models are pinned by the registry `knowledge/prs_models.json` — because the server-side
ranking in just-prs changes over time, and without pinning the same genome gets different
percentiles from run to run (differences of up to ±68 percentiles have been observed: a percentile is meaningful only
within one specific model). New models are not rejected forever, though: a mismatch is
recorded as a candidate with a dossier, `prs_model_review.py` gives recommendations once a quarter by
objective rules (a reference percentile is mandatory, coverage ≥0.95, quality no lower, and
stability over ≥2 runs), and acceptance is done one at a time: `prs_results_build.py --accept-model <trait>`.
The change goes into the registry history, and the trait's percentile series is marked with a break —
values from before and after a model change must not be compared.

If a trait has only genome-wide models in the catalogue (which `prs_extract_sites.py` discards by a threshold), the positions of exactly those models are extracted separately and re-genotyped into an extended file:

```bash
python3 src/ingest/prs_extract_models.py scoring_sites_ext.bed PGS000000 PGS000001
OUT=genome/scoring_sites_ext.vcf.gz bash src/ingest/prs_genotype_sites.sh scoring_sites_ext.bed
```

**The longevity layer (LongevityMap).** The catalogue stores only rsIDs, so they first have to be resolved into GRCh38 coordinates through Ensembl (this needs network access — which again means the local machine, not the sandbox), and then re-genotyped from the BAM:

```bash
python3 src/ingest/build_longevity_sites.py \
  src/scholion/knowledge/longevitymap.json \
  /tmp/longevity_sites.bed genome/longevity_rsmap.json
OUT=genome/longevity_sites.vcf.gz bash src/ingest/prs_genotype_sites.sh /tmp/longevity_sites.bed
python3 src/ingest/longevity_report.py genome/longevity_sites.vcf.gz \
  genome/longevity_rsmap.json src/scholion/knowledge/longevitymap.json \
  /tmp/longevity_report.md
```

`ONLY_SIGNIFICANT=1` limits coordinate resolution to the statistically significant entries of the catalogue — faster, if you do not need a full pass over Ensembl.

Note the separation of layers: **`genome/`** is the cold database (the VCF and the re-genotyped positions), while the tabs of the application read **the distillate in `profile/`**: `profile/prs_results.json` and `profile/longevity_findings.json`. The first is built by the `prs_results_build.py` tool from the raw output of `prs report` (see above) — not by redirection. The second is built by the generator `src/ingest/longevity_findings_build.py`: it overlays the re-genotyped `longevity_sites.vcf.gz` onto the LongevityMap catalogue and onto the **curated catalogue of directions** `knowledge/longevity_directions.json` (which allele is "pro-longevity" according to the primary sources, with PMIDs). The key honesty of this layer lies in that separation: entries with a direction are shown with a verdict (favourable / mild plus / neutral / practical flag) and a short "what to do about it", whereas statistically significant carrier states WITHOUT a curated direction are marked as a navigator through the literature, not as "pluses" — for most LongevityMap entries the direction of the allele was never published at all (aggregate gene-based tests, multi-marker panels). `longevity_report.py` remains a human-readable markdown report.

The mandatory caveats that the project keeps in every output of this layer: polygenic scores are built predominantly on European cohorts; **a percentile is not a probability**; and the presence of a variant in a literature catalogue is not a "risk" but the fact of a publication.

---

## 7b. Step 4b: diplotype-level pharmacogenetics (PyPGx + PharmCAT) — recommended

Single SNPs from our catalogue give only a first-pass slice of star alleles. There are four things they cannot give in principle: **CYP2D6** (which needs copy-number analysis — deletions/duplications/hybrids with CYP2D7), **the phasing of CYP2C19** (\*2 and \*17 on the same chromosome or on different ones are different phenotypes), **UGT1A1\*28** (the TA repeat in the promoter, Gilbert's syndrome — the bcftools catalogue does not pick it up) and **correct hemizygosity of G6PD** in males. For those, there is a two-stage pipeline.

**Stage 1 — PyPGx (diplotypes from BAM):**

```bash
pip3 install --user pypgx 'pandas<3'   # pandas 3.x is incompatible with pypgx 0.27
cd ~ && git clone --branch 0.27.0 --depth 1 https://github.com/sbslee/pypgx-bundle
bash src/ingest/pgx_star_alleles.sh    # ~30–60 min, resumable
```

18 genes: SNVs/indels via a full pileup over the gene regions (including reference genotypes!), and for the SV genes (CYP2D6, CYP2B6, CYP4F2, G6PD, CYP2A6) — coverage depth and a CNV model, with statistical phasing by Beagle against the 1KGP panel. Output: `profile/pgx_star_alleles.tsv` + `outside_calls.tsv` for stage 2.

**Stage 2 — PharmCAT (ready-made CPIC/DPWG/FDA recommendations):**

```bash
bash src/ingest/pharmcat_run.sh        # seconds; the first run downloads the jar
```

Output: `profile/pharmcat/` — `report.html` (for reading), `report.json`/`phenotype.json` (for the assistant / the engine).

**Four pitfalls, every one of which we walked into:**

1. **A variants-only VCF.** The full VCF from step 2 contains only the differences from the reference, so PharmCAT cannot tell "\*1/\*1" from "no data" (genes drop out as *No call data*), and without phase it gets confused in diplotypes (in a real run it was prepared to call the same CYP2C19 both \*2/\*17-IM and \*2/\*4-PM — with opposite recommendations for clopidogrel). The cure: the PyPGx diplotypes are passed in as **outside calls** — by PharmCAT's rule they take priority over the VCF. The script does this by itself.
2. **`pandas` 3.x breaks the CNV computation in pypgx 0.27** (LossySetitemError). Keep `pandas<3` — the script's preflight check catches this.
3. **`-reporterHtml` is mandatory alongside `-reporterJson`**: if even one report format is stated explicitly, PharmCAT saves only the stated ones — without the flag, the HTML on disk silently stays the one from the previous run.
4. **`missing_pgx_var.vcf` is a catalogue of MISSING positions**, not an input for PharmCAT. Do not substitute it for `*.preprocessed.vcf.bgz` (we got burned on this: a "newest file" glob picked exactly that one).

The results are personal data: `profile/` is not passed on together with the project. And the usual caveat: all of this is material for a conversation with a doctor; doses are changed by the doctor alone.

---

## 8. Step 5: checking that it all came together

Quality control of the variant calling:

```bash
bash src/ingest/qc_tstv.sh genome/<SAMPLE>.full.vcf.gz
```

A Ts/Tv of about **2.0–2.1** is a healthy set for WGS. Noticeably below 1.8 means a lot of noise in the calling, which is an argument for recomputing through DeepVariant (`MODE=wgs`). The script also prints a summary: total variants, SNPs, indels.

Checking that the application sees the database:

```bash
PYTHONPATH=src python3 -m scholion genome rs429358    # any locus
PYTHONPATH=src python3 -m scholion clinvar            # significant findings
PYTHONPATH=src python3 -m scholion serve              # → http://127.0.0.1:1521
curl -s http://127.0.0.1:1521/api/genome-status             # ready: true + provenance
```

`/api/genome-status` is the fastest check: it shows whether the VCF was found, which engine reads it (`bcftools`/`pysam`/`tabixlite`) and whether the layer is ready (`ready`). If `ready: false` while the file is present, it is almost always a missing `.tbi` or a missing `bcftools` on the `PATH`.

Readiness checklist:

| Check | Expected |
|---|---|
| `ls -lh genome/*.vcf.gz*` | there is a `*.full.vcf.gz` **and** a `.tbi` |
| `bcftools view -H genome/<SAMPLE>.full.vcf.gz \| head -2` | variant lines, contigs of the form `chr1` |
| `qc_tstv.sh` | Ts/Tv ≈ 2.0; 4–5 million variants |
| `/api/genome-status` | `ready: true` |
| `genome rs429358` / `genome rs7412` | genotypes found (APOE ε status) |
| `clinvar` | findings sorted into tiers |

---

## 9. What may be deleted, and what may not

Once the full VCF is in hand, space is freed like this: `rm -rf "$WORKDIR/_chr"` (the per-window VCFs), `rm -f "$WORKDIR"/*.sorted.bam` (the per-file BAMs, if the merge has already gone through), and the ClinVar cache in `~/genomic_work/clinvar`.

**The merged BAM (`<SAMPLE>.merged.bam` / `<SAMPLE>.markdup.bam`, tens of gigabytes) should not be deleted.** It is needed for any future re-genotyping on demand: new polygenic scores, new longevity loci, recomputation against fresh catalogues. Without it, those operations require realignment — that is, another day of work from scratch. The FASTQ files themselves can be moved to cold storage (an archive or an external disk) after successful alignment, but it is better to keep them: they are the primary data, and everything else is reproducible from them.

---

## 10. Typical failures and what to do about them

| Symptom | Cause | Remedy |
|---|---|---|
| `Operation timed out` during sorting/markdup | temp files in iCloud | put `WORKDIR`/`SCRATCH` on a local disk (`~/genomic_work`); the script checks this |
| "no aligner" / "no samtools" | the tools are not installed | §3; with conda, do not forget `conda activate` |
| Failed at markdup, "no space left" | the disk ran out | `bash src/ingest/resume_merge_call.sh` — merging without markdup, the alignment is not repeated |
| `mpileup` breaks off at some positions | alt/random/Un contigs got into the BED that do not exist in the no-alt reference | keep only the canonical `chr1..22,X,Y,M` |
| A locus is "not found" although the variant should be there | a notation mismatch (`chr1` versus `1`), or it is a reference homozygote | the code determines the prefix itself; remember that a variants-only VCF has no `0/0` positions — those need re-genotyping (§7) |
| `ready: false` while the VCF is present | no `.tbi`, or `bcftools` is outside the `PATH` | `tabix -p vcf …`; `export PATH="/opt/homebrew/bin:$PATH"` |
| The application does not see the new files | the server is running with the old state | restart `Scholion.command` (there is no hot reload) |
| The run was interrupted in the middle of alignment | a normal situation | start `fastq_to_vcf.sh` again: the finished BAMs are skipped |

---

## 11. For Claude Cowork: boundaries and a machine-readable checklist

**What the assistant must NOT do, however the request is phrased:**

1. Do not start alignment, `mpileup`, DeepVariant or any multi-hour step through the `device_bash` bridge: there is a 45-second limit there, no bioinformatics tools and no network. The attempt will break off half-way and leave junk in `WORKDIR`.
2. Do not lift FASTQ, BAM, CRAM, the full VCF or any file containing genotypes into the cloud (and do not stage them into the container). The genome stays on the owner's machine. In the cloud it is acceptable to work only with de-identified code and public catalogues.
3. Do not delete `merged.bam`/`markdup.bam` (see §9) and do not propose "freeing up space" at their expense. Besides, the bridge cannot delete files at all — the operation is forbidden; at most it moves them into a separate folder.
4. Do not present genetic findings as a diagnosis and do not change therapy: the wording is "a second opinion, to be discussed with a doctor".

**What the assistant can and should do:** assemble the exact command with the paths filled in and hand it to the person to run in a terminal; explain what is happening at the current step; read the tail of the log and the statuses with short calls (`tail -50`, `ls -lh`, `df -h`, `bcftools stats` on a finished file) — those fit within the limit; determine from the set of files which step the pipeline is at, and name **one** next step; interpret output and errors; and once the VCF is ready — check `/api/genome-status`, `genome <rsID>`, `qc_tstv.sh` and refresh the profile layers.

**Determining the current state from the files** (check top to bottom; the first match is the current step):

```
genome/clinvar_hits.tsv exists                       → pipeline complete; next §7 (PGS/longevity) and updates
genome/*.full.vcf.gz + .tbi exist                    → next step: annotate_clinvar.sh (§6)
$WORKDIR/<SAMPLE>.markdup.bam or merged.bam exists   → next step: call_full_vcf.sh (§5)
$WORKDIR/*.sorted.bam exist, markdup absent          → merging; if it failed — resume_merge_call.sh
only FASTQ exists                                    → next step: fastq_to_vcf.sh (§4), started by the person
no FASTQ                                             → obtain the data from the laboratory (§1)
```

**Commands that are safe for diagnostics through the bridge** (short, no network, no writing to heavy files):

```bash
ls -lh "$HOME/genomic_work/<SAMPLE>" | tail -20
tail -50 "$HOME/genomic_work/<SAMPLE>/auto_full_vcf.log"
df -h "$HOME/genomic_work" | tail -1
pgrep -l 'bwa|bwa-mem2|samtools|bcftools' || echo "no pipeline processes"
ls -lh genome/
```

**Template of the command the assistant hands to the person** (with the real paths filled in; remind them to escape `!` in zsh):

```bash
cd /path/to/Scholion-project-files
FASTQ_DIR="/path/to/folder/with/fq.gz" WORKDIR="$HOME/genomic_work/<SAMPLE>" \
  nohup bash src/ingest/fastq_to_vcf.sh > "$HOME/genomic_work/fastq_to_vcf.log" 2>&1 &
# then send back: tail -30 "$HOME/genomic_work/fastq_to_vcf.log"
```

---

### Callability: what qualifies a negative result

Zero pathogenic findings in a gene panel is honest exactly to the extent that those genes were actually read. Compute the coverage for each gene (`qc_callability.sh`: a per-gene BED from the ClinVar spans + `samtools depth` with per-interval access through the index — about 0.5 % of the BAM is read, and nothing needs to be installed). Three rules for reading the result:

- **Calibrate the threshold to the sample's depth.** If mean depth is around 25–30×, the fraction of bases above 30× cannot be high for any gene — that is arithmetic, not a defect. The working threshold is **≥10×** (the boundary of confident heterozygote calling) plus the ratio of the gene's depth to the panel median.
- **chrX in a male comes at half depth by construction.** This is not a gap: a hemizygous locus is called more confidently than a diploid one at the same depth.
- **The gene average does not answer for a specific position.** The list of weak genes is a place to look; the verdict is passed on the depth at the position the conclusion rests on.

The known difficult zones for short reads, which will surface for almost everyone: pseudogenes (`PMS2`/PMS2CL, `CYP2D6`/CYP2D7, `FANCD2`) — reads are lost on the MAPQ filter; and high GC (`LDLR`, `STK11`, `APOE`) — coverage sags during library preparation.

### Searching for LoF variants that are not in ClinVar

ClinVar annotation is an intersection of coordinates with a database: a variant that breaks a protein but has not been described yet will not be seen by it. Consequence prediction closes this gap, and for a first pass `bcftools csq` is enough (the Ensembl GFF3 transcript model, ~100 MB) instead of a VEP cache (~25 GB): the tool is already installed, and neither Docker nor x86 emulation is needed. Three rakes that make false findings easy to step on:

1. **Filter by canonical transcripts** (`tag=Ensembl_canonical` / `MANE_Select`). Modern Ensembl releases contain hundreds of thousands of transcripts, most of them new models from long reads. Without the filter the consequence is computed against every model, and a stop codon in a side isoform looks like a stop codon in the gene. In a real run this produced four "homozygous lethal genotypes" out of five findings.
2. **Take the MHC region out separately** (chr6:28.48–33.45 Mb). The reference is one haplotype out of many, so "LoF" there usually means a different HLA allele. In that same run, 20 of the 23 lines fell in the MHC.
3. **Cut by depth** using the threshold from callability, and remember that indels from `bcftools` are less reliable than SNPs — recall disputed positions with DeepVariant.

After these three filters the list becomes short, and what remains is worked through by hand according to the rules for reading findings (zygosity, inheritance, direction of effect, frequency in gnomAD, position relative to the last exon).

### The composition of the laboratory's panel is a separate question from genotyping quality

If you are cross-checking your VCF against a commercial laboratory's report, keep two sources of discrepancy apart. The genotypes may match perfectly while the conclusions diverge, because the panel does not include a marker without which a configuration is fundamentally undetectable. The classic example is HLA-DQ2.5 in trans: without the DQ7.5 tag the report will state "haplotype absent", even though the molecule does assemble. Before arguing about data quality, check what the panel actually consists of.

## 12. Caveats that must not be lost along the way

The build is GRCh38 no-alt; when cross-checking coordinates against the laboratory's report, remember that the laboratory may not state the build at all. Variant calling through `bcftools` gives good accuracy on SNPs (enough for pharmacogenetics), but on indels it is inferior to DeepVariant — if an indel is in doubt, recompute with `MODE=wgs`. For `CYP2D6` and `CYP2C9`, single SNPs are no substitute for copy-number and phasing analysis — that needs PyPGx. Consumer chip data cover only a fraction of the positions, and the absence of a variant there does not mean reference. And the general one: everything obtained along this path is material for a conversation with a doctor, not a conclusion.
