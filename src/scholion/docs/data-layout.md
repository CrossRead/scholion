# Data layout

The layout of personal data in Scholion. The same one for the project owner and
for a person who installed the package via `pip` — otherwise the instructions,
the scripts and the assistant's advice have to be translated onto someone else's
folder every time.

---

## Why this needs describing at all

Clutter in the project folder kept growing not because the folder was poorly
maintained, but because **the repository was also the data directory**. As long
as that holds, any cleanup lasts until the following week: caches, backups, logs,
intermediate files and incoming report forms appear in the same place as the
code, and at a glance they do not look different from code. A person opens the
folder and sees `src/`, `README.md`, `_to_delete/`, `inbox/`, a period-summary
PDF and `pharmcat.log` in one list — and cannot tell which of these is the
project and which is their own medical record.

Separation fixes this at the root: the code has its own root, the data has its
own.

---

## The data directory

```
<data>/
  profile/                  what the application reads and the assistant edits
  genome/                   what the application reads from the genome
  raw/                      sources: arrived from outside, never modified
    lab/                      lab report forms, laboratory reports
    sequencing/               FASTQ, BAM and indexes
    wearables/                Garmin, Apple Health, CGM exports
    reference/                reference genome, ClinVar snapshots
  work/                     intermediate — all of it can be recomputed
  archive/                  retired versions of profile files
  reports/                  what was made for a person to read: summaries,
                            briefs for a doctor, generated documents
```

Where it lives:

| Who | Data directory |
|---|---|
| Installed via `pip` | `$XDG_DATA_HOME/scholion`, on macOS `~/Library/Application Support/Scholion`, otherwise `~/.scholion` |
| Run from the source tree | the root of the tree (historical behaviour, preserved) |
| Set explicitly | `SCHOLION_REPO_DIR` — overrides everything |

Individual directories are overridden one by one: `SCHOLION_PROFILE_DIR`,
`SCHOLION_GENOME_DIR`, `SCHOLION_CACHE_DIR`. They exist for tests and for someone
else's profile; in ordinary work a single root is enough.

---

## Five rules that everything follows from

**1. Every folder answers one question.**
`profile/` and `genome/` — what the application knows. `raw/` — what was sent to
me. `work/` — what can be recomputed. `archive/` — what used to be.
`reports/` — what was made to be read by a person. A file for
which the question cannot be chosen unambiguously is in the wrong place.

The last slot exists because its absence had a cost: with nowhere to put them,
six documents produced for the owner sat loose at the repository root for three
weeks, held out of git by a file-extension rule rather than by a decision.

**2. `work/` can be deleted whole.**
That is a definition, not a wish. If something in `work/` cannot be restored by a
command, it is in the wrong place and must move to `raw/` or `profile/`.

**3. `raw/` is never modified, only added to.**
A report form that arrived, a device export, raw reads — these are sources.
Rewriting a source is not allowed: then there is no way to find out that the
interpretation was wrong.

**4. Code does not write into the code directory. Ever.**
No cache, no backups, no logs, no temporary files. This is checked automatically
— `tests/test_repo_hygiene.py` requires that, given a data root, **no** path
leads inside the code tree.

**5. There are no "I'll sort it out later" directories.**
`inbox/`, `_to_delete/`, `tmp/` are not created. A file that has done its job is
deleted immediately: once such a directory exists it accumulates, because there
is nobody whose job it is to empty it. By August the project had two of them,
5.5 MB, with files like `lock.pre.5`.

---

## External storage

The layout describes **logical places**, not necessarily one disk. A full BAM is
60 GB, raw reads are another 65 GB, the reference genome is 8 GB. Demanding that
this sit on the system disk next to the profile means demanding the impossible
from half the users.

**What can be moved out:** `raw/`, `work/`, and `genome/` if you want. They are
read rarely and on command.
**What cannot:** `profile/`. It is small, the application writes to it
constantly, and it is what makes the data directory a data directory.

**The mechanism already exists in the project** — `profile/sources.json`, a map
of "domain → folder". Today it defines `labs_docs`, `garmin` and `genome`; the
keys `raw` and `work` are being added. Empty = everything lives in the data
directory, and the overwhelming majority of users will never see this file.

```json
{ "folders": { "raw": "/Volumes/Genome/raw", "work": "/Volumes/Genome/work" } }
```

**Why a file and not an environment variable.** The application is launched by
double-clicking a shortcut, and `SCHOLION_*` from `.zshrc` does not reach there:
the terminal sees the variables and the GUI does not. A setting that only works
when launched from a terminal is worse than no setting at all — it works some of
the time and it is unclear why. Variables remain for tests and one-off runs, and
they override the file.

**What must happen when the disk is absent.** An external disk gets
disconnected — that is a normal state, not a failure. The application answers
"source not connected, expected `<path>`" and keeps working on what is
available. The answer for a missing genome database is already built this way;
the rule extends to `raw/` and `work/`. Silent zeros instead of an honest "not
connected" are the one genuinely bad outcome: a person draws conclusions about
their own health from them.

**Privacy.** `sources.json` contains absolute paths, and those contain the user
name. That is personal data, and it sits where it belongs: inside `profile/`,
that is, outside version control and outside the package by construction, rather
than by a separate rule that can be forgotten. The paths do not enter the context
sent to an external model.

This case arrives as soon as whole-genome data is on disk: a working directory
such as `~/genomic_work` (raw reads, BAM, the reference, intermediate
PharmCAT/HLA/PGx computations) stays where it is and is declared external storage
for `raw/` and `work/`. There is no need to move 125 GB anywhere — it is enough
to name them in one line of configuration.

---

## What sits where: now → where to

The migration has **not been done** — this is a map, not a log. By agreement the
genome is left alone for now.

| Now | Where to | Note |
|---|---|---|
| `<repository>/profile/` | `profile/` | the layout is already correct, only the root changes |
| `<repository>/genome/` | `genome/` | same |
| `<repository>/_backups/` (137 files) | `archive/` | thin it out while you are there: 11 versions of one `SKILL.md` |
| `<repository>/.cache/` | `work/cache/` | moves by itself, following the data root |
| `<repository>/pharmcat.log` | `work/` | |
| `<repository>/inbox/` | — | one-off patches, the work is done |
| `<repository>/_to_delete/` | — | delete |
| Top-level DOCX and PDF written by the assistant | `reports/` | done 17.08.2026 |
| Top-level DOCX and PDF that arrived from outside | `raw/lab/` | |
| Lab-results folder | `raw/lab/` | |
| `EvogenGenomeApp/*.pdf` | `raw/lab/` | laboratory reports |
| `EvogenGenomeApp/…/FASTQ` (65 GB) | `raw/sequencing/` | |
| `genomic_work/<SAMPLE>/*.bam` (60 GB) | stays in place | external storage for `raw/`; **must not be deleted**: diplotypes, coverage and PGS positions are computed from it |
| `genomic_work/reference/`, `clinvar/` | stays in place | external storage for `raw/` |
| `genomic_work/{hla,pgx,pharmcat,csq,callability}/` | stays in place | external storage for `work/`, all of it reproducible |
| `apple_health_export/`, `garmin_export/`, CGM screenshots | `raw/wearables/` | |

Duplicates that will disappear on their own: `<SAMPLE>.full.vcf.gz` sitting in two
places at 185 MB each. After the move one copy remains — in `genome/`.

---

## What is already fixed in the code

- **The data directory is separated from the code** — `core.repo_dir()`
  distinguishes a source tree from an installed package, and
  `SCHOLION_REPO_DIR` overrides it.
- **The cache follows the data directory** — `SCHOLION_CACHE_DIR` falling back to
  `<data>/.cache`, not to the folder with the code.
- **`tests/test_repo_hygiene.py`** — under version control there are no data
  directories and no "for later" directories, no files of personal types (PDF,
  DOCX, VCF, BAM, logs), and every data path leads into the data directory.
- **`scholion init` lays out the whole directory** — `profile/`, `genome/`,
  `raw/{lab,sequencing,wearables,reference}`, `work/`, `archive/`, each folder
  with a note saying what goes into it, all `0700`. A slot moved to another disk
  is not silently replaced with an empty stub.
- **The `raw` and `work` keys in `profile/sources.json`** — external storage; on
  the "Assistant" tab a disconnected source is named out loud: "source not
  connected, expected <path>".
- **The cache is one function, `core.cache_dir()`**, instead of an expression
  written out in five files.

## What is not done yet

- The data migration itself.
