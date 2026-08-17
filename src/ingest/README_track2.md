# Track 2 — variant calling from FASTQ (locally, on a Mac)

Goal: get from the raw FASTQ (Evogen <SAMPLE>) the genotypes of the markers that are missing from the Evogen PDF report — for longevity/QoL and for pharmacogenomics: **`APOE`, `CYP2C9`, `SLCO1B1` (statins!), `DPYD`, the full `CYP2D6`** — and to cross-check the ones already known (`CYP2C19`, `VKORC1`, `TPMT`, `MTHFR`).

## Why this cannot be run from the chat
The Cowork bridge to the computer (`device_bash`) is an isolated sandbox with a 45-second limit, without bwa/samtools and without a network. Aligning tens of gigabytes of reads takes hours → it has to be started in an **ordinary terminal on the Mac** (or through Claude Code on your own machine). FASTQ is not uploaded to the cloud (volume plus the privacy of a genome).

## Input
`EvogenGenomeApp/EvogemRawData/Первичные данные…/` (the Russian folder name is the one
Evogen ships the raw data under — it is a path, not a caption) — the `*_1.fq.gz`/`*_2.fq.gz` files (one pair per lane, MGI/DNBSEQ), tens of gigabytes in total. Check first that the files are valid and that the free space on the disk covers the mode you are about to run (see the table below).

## Running it (Mac)
```bash
# 1) tools. samtools/bcftools — mostly from Homebrew; the aligner — from brewsci/bio.
brew install samtools bcftools
brew tap brewsci/bio
brew install bwa            # reliable on Apple Silicon; if you want speed: brew install bwa-mem2
#   (the script picks up bwa-mem2 itself if it is there, otherwise bwa)
#   (the full WGS mode additionally needs Docker Desktop)

# 2) GO TO THE PROJECT FOLDER. NOTE: in zsh the "!" character must not be put inside
#    double quotes (it is treated as history expansion). Escape the space and the "!" with a backslash:
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/\!Scholion/Scholion-project-files

# 3) FASTQ → genotypes of the target loci (RECOMMENDED, faster, no Docker)
bash src/ingest/fastq_to_vcf.sh                 # MODE=targeted by default

# 4) turn the result into a readable TSV
bash src/ingest/extract_pgx_loci.sh "$HOME/genomic_work/<SAMPLE>/<SAMPLE>.targets.vcf.gz"
```

If `brew tap brewsci/bio` does not go through, the alternative is conda/bioconda:
`conda create -n geno -c bioconda -c conda-forge bwa samtools bcftools -y && conda activate geno`

The full genomic VCF (should it be needed later): `MODE=wgs bash src/ingest/fastq_to_vcf.sh` (needs Docker, ~250 GB, takes longer).
Variables: `FASTQ_DIR`, `WORKDIR`, `REF_DIR`, `THREADS`, `MODE` (`targeted`|`wgs`), `CLEANUP`.

## The two modes
| | targeted (default) | wgs |
|---|---|---|
| Tools | bwa-mem2, samtools, bcftools | + Docker (DeepVariant) |
| What it gives | genotypes of ~15 target loci | a full genomic VCF (~4–5 million variants) |
| Disk / time | ~120 GB / less | ~250 GB / longer |
| When | now, for the profile and the application | later, for completeness and polygenic scores |

The bottleneck in both is the alignment phase (bwa-mem2 over all the reads). The targeted mode saves on the variant-calling step (mpileup over the BED only) and does not require Docker.

## Important
- **Build: GRCh38** (no-alt). The Evogen report does not state the build explicitly — take that into account when reconciling positions.
- `CYP2D6`/`CYP2C9` (CNV and phasing matter here): after the VCF, run **PyPGx** (`pip install pypgx`) for reliable star alleles — the targeted script gives a first cut over single SNPs.
- `WORKDIR=~/genomic_work` — outside iCloud; the intermediate BAMs are large and private, do not sync them. `CLEANUP=1` deletes the per-lane BAMs after the merge.

## What to do with the result (→ profile)
1. The genotypes from `pgx_target_loci.tsv` → new entries in `profile/pharmacogenomics.json`.
2. **`APOE` ε-status** (rs429358 + rs7412) → `profile/genome_extended.md` (longevity/cardiovascular/cognition, with the caveats).
3. **`SLCO1B1` rs4149056** → the safety of **statins** (relevant in dyslipidaemia — see `labs.md`).
4. Update the "Gaps" section in `genome_extended.md`; git-commit the profile.

> I can walk you through the run step by step and go through the output — send whatever the terminal shows (or run it through Claude Code on the Mac, giving it this folder).
