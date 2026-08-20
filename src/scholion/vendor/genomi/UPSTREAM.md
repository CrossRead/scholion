# Vendored from Genomi — what was taken, what changed, how to update

**Upstream:** https://github.com/exon-research/genomi
**Commit:** `07a255e` (branch `master`, 2026-08-17)
**Licence:** Apache License 2.0 — the same licence this project uses, so the two
are compatible directly. Apache-2.0 asks that notices be retained, that the
origin be stated, and that modified files say they were modified. All three are
done in the header of every file here and in the table below.

## Why vendored rather than depended on

Genomi is not on PyPI: a required dependency is declared as a direct git URL,
which PyPI rejects, so `pip install genomi` cannot work today. Depending on a git
URL ourselves would push that same problem onto everyone installing Scholion.
Their detector is also self-contained — standard library only, no clinical
claims, no thresholds, no model calls — which is what makes copying it
reasonable rather than a liability.

## What was taken

| Our file | Upstream path | Lines | sha256 of the upstream original |
|---|---|---|---|
| `detection.py` | `src/genomi/active_genome_index/source_intake/detection.py` | 451 | `18916520e824bab2b5ad754753802addc5b14af3b208cb2854bfab76af313411` |
| `text_io.py` | `src/genomi/active_genome_index/source_intake/text_io.py` | 285 | `bc597fe770c3644d9ef134aa6edcc75742d08f2d5962d8db2c225f4615190aa1` |
| `alignment_helpers.py` | extract of `src/genomi/active_genome_index/alignment.py` | 15 of 479 | — (extract, see below) |
| `../../../../tests/test_genomi_source_detection.py` | `tests/test_source_detection.py` | 316 | `814a8142132c1989827bc832e3aded6c7080857a79579df8a43050187ff2bc35` |

The sha256 values are of the files EXACTLY as fetched, before our headers were
added. `src/tools/check_vendor.py` re-fetches them and compares.

**What it gives us.** Recognition by content rather than by name: BAM (the
`BAM\x01` magic inside its BGZF), CRAM, VCF, **gVCF told apart from VCF**, paired
FASTQ, and the consumer array exports of 23andMe, AncestryDNA, MyHeritage,
FamilyTreeDNA and Living DNA. Wrappers — gzip, bzip2, xz, zip, tar — are peeled
by magic bytes, and README, PDF, JSON and macOS resource forks inside a provider
archive are discarded rather than mistaken for the payload.

**What was NOT taken:** everything else in their tree. Their analysis layer runs
on the opposite principle to ours (a model computes, retrieval grounds it), and
their `lab/` layer pulls cloud dependencies. This is bytes, not interpretation.

## Changes from upstream

Every change is marked `SCHOLION CHANGE` at the line it affects.

1. **`detection.py` — `_array_reference_build` no longer asserts a build nobody
   declared.** Upstream computes whether the header states build 37 and then
   returns `"GRCh37"` from *both* branches, commented «consumer arrays are GRCh37
   unless a future export says otherwise». That is the one shape this project
   exists to remove: the file states its build in prose, the code reads the
   statement, and answers from a default regardless — and a build asserted where
   none was declared cannot be told from one that was read. Ours returns `None`
   when nothing was declared. Behaviour is identical for every export that does
   declare a build, which is nearly all of them.
2. **`detection.py` — the import of the two FASTQ pair helpers** points at
   `alignment_helpers.py` instead of the 479-line `alignment.py`.
3. **`alignment_helpers.py`** is an extraction: four objects copied verbatim.
4. **The test file** imports from our package, and its two BAM tests are skipped
   rather than deleted — they build their fixture with `pysam`, which we do not
   depend on. The failure is in the test's setup, not in the module, and deleting
   them would hide that two of twenty-three assertions are not being made.

## How to update

```
python3 src/tools/check_vendor.py            # is our copy still upstream's?
python3 src/tools/check_vendor.py --refresh  # re-fetch, keeping our headers
```

`check_vendor.py` fetches each file at the pinned commit — and at `master` — and
reports three things: whether our copy still matches what we pinned, whether
upstream has moved since, and which of our marked changes would have to be
re-applied. It never overwrites without `--refresh`.

Updating is a decision, not a chore: their change may be a fix worth taking or a
default worth refusing, as change 1 above was. Re-apply the marked changes, run
`python3 -m unittest tests.test_genomi_source_detection`, and record the new
commit and checksums in this file.

## Courtesy

Apache-2.0 permits taking this silently. A short note to the authors saying what
was taken, where the attribution sits and what was changed costs ten minutes and
is the difference between borrowing and helping yourself.
