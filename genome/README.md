# Genome — how to prepare it and connect it (PERSONAL)

The application reads genotypes from a **full VCF** (`genome/*.vcf.gz` plus the `.tbi` index) aligned to **GRCh38**. The VCF itself is NOT part of the package and is not handed to anyone — everyone prepares their own.

Put here:
```
genome/
  <sample>.full.vcf.gz        # your full genome (GRCh38), bgzip
  <sample>.full.vcf.gz.tbi    # index (tabix)
```
After that the `genome` and `clinvar` commands, PGS and the longevity layer start taking genotypes from your VCF automatically.

---

## Path A — you have full sequencing (WGS/WES): FASTQ or BAM (recommended)
This is the main scenario (the project was built around it). **The detailed step-by-step instruction is `PREPARING-THE-GENOME.md`** in the project root: it covers the whole route FASTQ → BAM → full VCF → `genome/` with commands, modes, time and disk estimates, an account of the typical failures and a check of the result. Below is the short outline. You need the tools `bwa-mem2`/`minimap2`, `samtools`, `bcftools` (macOS: `brew install bwa-mem2 samtools bcftools`).

1. The GRCh38 reference **without alt contigs** (`GRCh38_no_alt`) plus indexes.
2. If you have FASTQ — alignment → sorting → (merge across lanes) → BAM. The scaffold: `src/ingest/fastq_to_vcf.sh` (set `FASTQ_DIR`, `WORKDIR`, `SAMPLE`, `REF`).
3. If you already have a BAM — variant calling: `src/ingest/call_full_vcf.sh` (`bcftools mpileup | call`), then `bgzip` and `tabix`.
4. The finished `*.full.vcf.gz` (plus `.tbi`) → into this `genome/` folder.

Orders of magnitude: a whole-genome call is CPU hours and tens of gigabytes of disk (keep the BAM on a local disk, not in the cloud). All the scripts are parameterised by the variables `SAMPLE`/`WORKDIR`/`REF` — set your own.

> IMPORTANT: PGS and the longevity layer use positions re-genotyped from the BAM (`scoring_sites*.vcf.gz`, `longevity_sites.vcf.gz`) — generating those also requires a BAM (`src/ingest/prs_*`, `build_longevity_sites.py`). Without a BAM the basic functions are available (ClinVar × VCF, locus lookup), but not the full PGS.

## Path B — you have a consumer test (23andMe / AncestryDNA / MyHeritage)
This is a microarray (~600 thousand SNPs), not a full genome — coverage is smaller, but APOE, pharmacogenomics and ClinVar findings are mostly available.

1. Export the "raw data" from your account (23andMe: Account → Browse Raw Data → Download; AncestryDNA: Settings → Download DNA Data). You get a text file (rsID, chromosome, position, genotype).
2. Convert it to VCF on **GRCh38**. Raw data usually comes on GRCh37/hg19, so a lift to GRCh38 is needed:
   - `bcftools convert --tsv2vcf` (with a reference) or utilities such as `plink`/`snps` (python) to read raw → VCF;
   - then lift over GRCh37→GRCh38 (`CrossMap`/`Picard LiftoverVcf` plus the `hg19ToHg38` chain);
   - `bgzip` and `tabix`.
3. The finished `*.full.vcf.gz` (plus `.tbi`) → into `genome/`.

Limitation: many positions are absent on a microarray — "the variant is not present" here does NOT equal "reference" (unlike WGS). The full PGS from BAM is unavailable; individual loci, APOE and ClinVar findings across the covered positions do work.

---

If there is no VCF at all, the application still works on labs, prescriptions and lifestyle; the genomic functions honestly return the status "database not connected".
