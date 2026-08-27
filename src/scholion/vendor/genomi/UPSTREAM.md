# Vendored from Genomi — what was taken, what changed, how to update

**Upstream:** https://github.com/exon-research/genomi
**Commit:** `3860a23` (branch `master`, 2026-08-25)
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
| `detection.py` | `src/genomi/active_genome_index/source_intake/detection.py` | 462 | `01c4aedccd021a7b564ecdcb29e41830981ccf7eb8b0d1c547adfa53dc6dffe4` |
| `text_io.py` | `src/genomi/active_genome_index/source_intake/text_io.py` | 285 | `bc597fe770c3644d9ef134aa6edcc75742d08f2d5962d8db2c225f4615190aa1` |
| `alignment_helpers.py` | extract of `src/genomi/active_genome_index/alignment.py` | 15 of 479 | — (extract, see below) |
| `../../../../tests/test_genomi_source_detection.py` | `tests/test_source_detection.py` | 354 | `567a5f8ac92658a5d478620c3b01b4d59b326e304ac1792aba3ed66596797aa6` |

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

1. **`detection.py` — the import of the two FASTQ pair helpers** points at
   `alignment_helpers.py` instead of the 479-line `alignment.py`.
2. **`alignment_helpers.py`** is an extraction: four objects copied verbatim.
3. **The test file** imports from our package, and its two BAM tests are skipped
   rather than deleted — they build their fixture with `pysam`, which we do not
   depend on. The failure is in the test's setup, not in the module, and deleting
   them would hide that two of the assertions are not being made.

## What went back

**The one behavioural change this copy carried is upstream now, and so is gone
from the list above.** Until 25.08.2026 it read: `_array_reference_build`
computes whether the header declares build 37 and then returns `"GRCh37"` from
*both* branches, so a build nobody wrote down cannot be told from one that was
read — and FamilyTreeDNA exports, which are recognised by having no comment block
at all, could never declare one and were reported as GRCh37 on an assumption.
Ours returned `None` instead, leaving the default where it already lived, in
`_effective_array_build`.

It was offered as [`exon-research/genomi#5`](https://github.com/exon-research/genomi/pull/5)
with four tests and merged the same day, which is the commit this file now pins.
The divergence is not carried any more: the code here is theirs, and nobody has
to re-apply anything at the next refresh. When that is worth doing at all is a
rule, not a mood — `CLAUDE.md`, «Contributing upstream».

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
default worth refusing. Re-apply the marked changes, run
`python3 -m unittest tests.test_genomi_source_detection`, and record the new
commit and checksums in this file.

## Courtesy

Apache-2.0 permits taking this silently. A short note to the authors saying what
was taken, where the attribution sits and what was changed costs ten minutes and
is the difference between borrowing and helping yourself. Here it became the
disclosure paragraph of the pull request above, which is better: it arrived
attached to something useful.
