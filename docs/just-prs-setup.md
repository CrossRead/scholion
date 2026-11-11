# Polygenic scores (PGS)

Scholion uses the local **just-prs-mcp** sidecar to obtain public model files and
reference calibration. Scholion counts the called effect alleles itself. The
sidecar's raw score and reliability flag do not establish a verified percentile.

## Privacy and dependencies

Scoring is local. The single-sample VCF path is passed to a local stdio process;
genotypes are not uploaded. Public model identifiers and trait names may be sent
to PGS Catalog, and public model files and reference data are downloaded. Model
weights remain in the user's runtime cache and are not distributed with Scholion.

Install `uv`/`uvx`; the sidecar runs in its own isolated Python environment. The
client pins the audited sidecar and reference-library versions. A custom dependency
resolution cannot silently establish reference-quality provenance.

## Inputs and matching

Use a **scoring-site VCF**, including called reference homozygotes. An ordinary
variants-only VCF is insufficient: absent positions are not reference genotypes.
The input must contain exactly one sample and have a verified GRCh37 or GRCh38
coordinate build. The effective harmonized model build must match that input;
a model's original publication build can differ.

Scholion reads GT by its FORMAT name, counts the actual alleles at multi-allelic
sites and accepts lower-case reference bases. Partial calls, conflicting records,
symbolic alleles and unresolved representations reduce coverage. Missing sites
are never imputed as zero dose. Strand matching requires a resolved,
non-palindromic SNP pair. Indels require an exact allele representation.

## Model and population selection

The precomputed trait list is a manually assembled starting panel, not a complete
catalogue or a ranking of the best scores. Its historical composition has gaps,
including female-specific cancer traits. Additional endpoints require their own
model assessment; the number of listed traits is not a software limit.

Recalculation uses the model pinned for the trait. A different model requires an
explicitly accepted series change. When trait search cannot resolve an endpoint,
an exact trait-name fallback may select a small candidate with verified reference
calibration; related endpoints are not interchangeable.

The reference population is determined from available genome evidence. An unresolved
assignment stops scoring; there is no silent EUR default. An explicit panel override
is retained as such. Reference calibration, genome/model coordinates, position
coverage and absolute-weight coverage are checked separately. AUROC-only and
unverified fallbacks remain diagnostic values. A verified percentile is a population
position, not a probability of disease; model transfer across populations still
requires care.

## Recheck after a scoring correction

A UI-only update does not require PGS recalculation. The application proposes a
check when stored scores lack the corrected allele-scoring witness. An already
checked report does not get the same proposal merely because a version changes.
The update never starts a BAM operation automatically.

The installed package provides the complete operation:

```sh
scholion prs --recalculate
scholion prs --recalculate --yes
scholion recompute --status
scholion recompute --stop
```

A supplied scoring-site VCF can be selected with `--scoring-vcf /path/to/calls.vcf.gz`
on `prs --recalculate`. Otherwise the selected profile's accessible recorded input
or connected genome is used. The operation downloads only pinned public model
weights, reuses called genotypes and reads BAM only for missing model positions.
A variant-only VCF does not supply missing reference homozygotes. Without BAM,
coverage remains as actually measured; a percentile failing coverage or calibration
remains unverified. With BAM, matching assembly, an indexed reference FASTA,
BAM index and bcftools are required. A copied report without its local input is
readable history and cannot reconstruct those inputs.

The operation validates the flat result schema, preserves a unique backup and
replaces the saved report atomically only after the complete calculation succeeds.
Failure or cancellation preserves the original report. No source checkout or
source-only helper is needed; no model or personal decision is written into
installed package knowledge. Missing references remain unavailable after scoring;
repeating BAM cannot repair calibration. CLI, web and `sch_recompute` use this
same runner, confirmation boundary and progress file.

Inspect the saved results with `scholion prs --json`, or Genome → PGS. The CLI,
web and assistant read the same validation result and recalculation proposal.

## Independently checked calibration

Scholion can calibrate PGS000646 using a separately checked aggregate from the
fixed IGSR 1000 Genomes Phase 3 EUR cohort (503 samples). All 32 original GRCh37
scoring positions were directly called for every reference sample with exact
forward alleles, without absence imputation. The original sites, alleles and
weights agree between the supported GRCh37 and GRCh38 harmonized model files.
Only aggregate statistics, hashes and provenance ship; weights and individual
reference genotypes or scores do not.

This reference is accepted only with a corrected called-allele scoring witness,
the exact checked model-file hash, matching effective coordinate builds and the
EUR population. Position and weight coverage remain independent checks.
Changing a file, model or population does not inherit that calibration.
Other upstream-quarantined references are not restored by this exception.
The percentile uses the reference mean and sample standard deviation and is an
approximation, not an empirical rank or a validated absolute-risk estimate.
Its clinical predictive accuracy remains a separate model property. Stored
results retain their old calibration in the backup; a calibration change alone
does not justify another BAM operation.

A host that exits after each tool call starts confirmed PGS recalculation in a
separate installed worker. The worker retains the captured container and checks
its identity before writes; progress and cancellation use the same job files.
It does not require a source checkout or a persistent chat process.
