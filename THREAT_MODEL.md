# Threat model

Scholion is local-first software that one person runs on their own machine over
their own medical data. This document describes the security boundary of a
release. It is not a promise that software can protect a compromised computer,
an unencrypted backup, or data the user deliberately hands to someone else.

The model applies to the released source archive, the wheel, and the application
started from that wheel. Every claim below is meant to be checkable against a
specific release tag — where a claim is not yet backed by a check, it says so.

## What is being protected

- Laboratory results, prescriptions, clinical reports, notes, wearable exports.
- Genetic files and everything derived from them: VCF, BAM, FASTQ, genotype
  reports, callability, polygenic scores, pharmacogenomic diplotypes.
- Identifiers: name, date of birth, addresses, sample and accession numbers,
  device identifiers, file paths, metadata.
- Text derived from the data: an assistant context bundle, a summary for a
  physician.
- **The integrity of a long series.** A lost or silently altered historical
  value changes later interpretation. Corruption is a confidentiality-grade
  problem here, not a mere inconvenience.

## Trust boundaries

```text
files the user chose  ──read──►  Scholion process  ──write──►  profile directory
                                      │
                                      ├── loopback HTTP UI, only while `scholion serve` runs
                                      │
                                      └── outbound lookups, only on an explicit command
```

Nothing runs in the background. There is no scheduler, no daemon, no telemetry
and no update check that fires on its own.

## Network: what actually leaves the machine

The application scans its own source on request and prints the inventory below
on the Assistant screen. The numbers come from that scan, not from this
document, so they cannot quietly go stale.

**Two separate claims, deliberately not merged:**

| Claim | Status |
|---|---|
| The core makes no calls to language models | **checked** — scan of every core file finds no model endpoint, client import or key variable |
| The core makes no network calls at all | **false, and never claimed** — see the table below |

What the running application can contact, and only when the user invokes the
command that needs it:

| Destination | What is sent | Triggered by |
|---|---|---|
| `rxnav.nlm.nih.gov`, `mor.nlm.nih.gov` | the drug name | a drug missing from the local knowledge base |
| `api.mymemory.translated.net`, `translate.googleapis.com` | the drug name, for a Russian brand name | the same lookup |
| `rest.ensembl.org` | an rsID | an rsID not present locally |
| `api.cpicpgx.org` | a gene or drug identifier | pharmacogenomic lookup |

The profile, the genome and laboratory values are never part of a request. But a
drug name **is** a statement about the person asking, and the honest framing is
that this is a small, explicit, user-triggered disclosure — not "no data leaves
the machine".

Data-preparation scripts, which the user runs by hand to build a genome or
refresh reference data, download from a further set of hosts (NCBI, Ensembl FTP,
UCSC, HAGR, GitHub, PyPI). They are listed separately in the same report,
because attributing ClinVar downloads to the application would be as wrong as
omitting them.

`SCHOLION_OFFLINE=1` refuses every outbound request; local analysis continues to
work and any feature that needs the network says so instead of failing silently.

**Coverage is part of the claim.** The scan reports how many files and which
directories it read. A negative result over an unstated set of files is not a
statement — the same rule this project applies to genomic findings.

## Threats and controls

| Threat | Control | Status |
|---|---|---|
| Shell injection through an imported path or file name | No `shell=True` anywhere; the Apple Health export is filtered in-process with no external command and no temporary file | done |
| Symlink/race in temporary files | `mktemp` removed; no predictable name in a shared directory | done |
| Profile corrupted by an interrupted write | Write to a temporary file in the same directory → `fsync` → `os.replace`; the target is always either the whole old version or the whole new one | done, covered by tests |
| Another OS account reads the health data | Profile, genome and cache directories are created `0700`; profile files `0600` for new files, existing modes preserved | done, covered by tests |
| A page in the browser mutates the profile over loopback | `Host` must be a loopback name (also blocks DNS rebinding); a cross-site `Origin` on a state-changing request is rejected | done, covered by tests |
| Memory exhaustion through a large request | Request body capped at 1 MiB; a malformed `Content-Length` is rejected before reading | done, covered by tests |
| Filesystem paths disclosed through API errors | Details go to the owner's console; the HTTP response carries a generic message | done, covered by tests |
| Lost update from concurrent CLI and UI writes | **not addressed.** Each write is atomic, so no file is torn, but two overlapping read-modify-write cycles can still drop one change. Residual risk, accepted for a single-user tool | open |
| Data leaked through a bug report | `SECURITY.md` forbids real profiles, genomes, PDFs, screenshots and logs; `scholion init --demo` provides a synthetic person for reproductions | done |
| Published artifact does not match the tagged source | Build from the tag, unpack the artifact and run the tests inside it, install the wheel into a clean environment, publish from CI via PyPI Trusted Publishing | in progress |
| A stale claim in the documentation | Network inventory and scan coverage are produced by code and asserted by tests, so a new outbound call cannot silently contradict the README | done |

## Out of scope

- A machine already compromised: malware, a hostile administrator, a browser
  extension with local file access.
- Unencrypted disks, backups, cloud-synchronised folders, screenshots.
- The user voluntarily pasting their context into an external model, an issue or
  an email. The application warns that the bundle contains personal data; it
  cannot follow it afterwards.
- Medical correctness beyond the documented sources and their stated limits.
  That belongs to `DISCLAIMER.md`, not here.

## Release evidence

A release publishes or retains:

- the source tag and the artifact checksums;
- the output of the privacy audit **run on the final artifact**, not on the
  repository;
- the test run performed after unpacking that artifact;
- the wheel installed into a clean environment, with `init`, `demo` and first
  launch exercised there;
- the outbound-host inventory for that version;
- known limitations and supported input formats.

If one of these is missing, the corresponding claim is **unverified** — which is
not the same as true.
