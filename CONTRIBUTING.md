# Contributing to Scholion

Two things make this project useful: an engine that refuses to overstate what
it knows, and a knowledge base that is right. You can improve the second
without touching the first, and that is the contribution we most need.

_This is the short version, sufficient for a first pull request. It will be
expanded before the public launch._

## The shape of a contribution

The engine and the knowledge are deliberately separate. To teach the system a
new drug, marker, interaction, monitoring rule or clinical threshold you do
**not** need to read `engine.py` or `core.py` — you add entries to the JSON
files in `src/scholion/knowledge/`.

## Evidence rules for `knowledge/`

A pull request that adds or changes a clinical statement is merged only if the
entry carries, in the entry itself:

1. **A source.** A peer-reviewed publication (PMID or DOI) or a named clinical
   guideline with its version — CPIC, DPWG, ADA, ESC, KDIGO, ACMG and the like.
   "Commonly known", a blog, a supplement vendor and a language model are not
   sources.
2. **A population.** In whom was this established. A threshold derived in one
   population is not a universal constant.
3. **A direction and an action.** What the finding means and what one is
   supposed to do with it — including "nothing, this is navigational".
4. **Units and material** for anything laboratory-related, taken from a printed
   report rather than from memory.

Standard identifiers — RxNorm RXCUI, ATC, LOINC — are welcome where you have
them from an official table. Do not write a code from memory: an invented
identifier looks like a standard and silently corrupts exchange. Absent is
better than wrong.

Where a contribution retracts an earlier statement, say so explicitly. In this
project a retraction is worth more than a new finding, because the old wording
lives on in documents and in people's heads until it is withdrawn.

## What must never enter this repository

* **Personal data of any kind** — your genome, your VCF, your laboratory
  reports, your prescriptions, your wearable exports, screenshots of your
  profile. Not in commits, not in issues, not in pull request comments. If you
  need to demonstrate a bug, use the synthetic demo profile.
* **PGS scoring weights** — licence varies per score, some forbid commercial
  use.
* **ATC code tables** — the WHO Collaborating Centre forbids commercial
  redistribution. The software fetches them at run time instead.
* **SNOMED CT content** — requires an Affiliate licence.
* Any data whose licence forbids commercial use, modification, or
  redistribution. See ATTRIBUTION.md.

## Sign your work — Developer Certificate of Origin

This project uses the DCO rather than a contributor licence agreement. You keep
your copyright; you certify that you have the right to submit what you submit.

Add a sign-off line to each commit:

    git commit -s -m "knowledge: add ABCG2 monitoring rule"

which appends:

    Signed-off-by: Your Name <your.email@example.com>

By doing so you certify the Developer Certificate of Origin 1.1
(https://developercertificate.org/).

## Licence of contributions

* Code contributions are licensed under the Apache License 2.0 (LICENSE).
* Contributions to `src/scholion/knowledge/` are licensed under
  CC BY 4.0 (LICENSE-DATA).

## Before you open a pull request

* `python3 -m compileall src` passes.
* Every JSON file you touched still parses.
* The engine runs against the synthetic demo profile without errors.
* You have not added a dependency. The engine is standard library only, and
  that is a feature, not an oversight.

## Where to write

Issues and pull requests are the main way in. **scholion.dev@proton.me** is for
what does not fit a public tracker: an offer of a de-identified case for
validation, a co-authorship, a security matter, or anything you would rather not
say in the open.

One request that holds regardless of the channel: **no personal health data**,
not in an issue, not in an e-mail, not in an attachment. Describe the shape of
the problem, not your results — `scholion redact` strips the structural parts of
a file, and what it cannot decide for you it says so about.

## Scope

Scholion is a research and educational tool, not a medical device — see
DISCLAIMER.md. Contributions that turn output into individualised medical
advice, prescriptions or dose selection are out of scope regardless of how well
they are evidenced.
