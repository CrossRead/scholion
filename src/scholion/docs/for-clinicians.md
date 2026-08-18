# Scholion — a one-page description for clinicians and researchers

Scholion is an open-source program that a person runs on their own computer. It
reads that person's own medical data — a genomic file, laboratory results
collected over years, prescriptions, wearable exports — holds them in one
profile, and answers questions about them. Nothing is uploaded: the profile is a
folder of files on their machine.

It is **not a diagnostic tool and not a medical device.** It does not diagnose,
does not start or stop therapy, and every statement it makes is material for a
conversation with a physician.

---

## What it takes as input

| Layer | Format | State |
|---|---|---|
| Genome | VCF (from whole-genome sequencing) | works |
| Genome | consumer array export (23andMe and the like) | not yet — deliberately, see below |
| Laboratory results | PDF forms (Russian laboratories), CSV, or values typed in one at a time | works |
| Prescriptions | entered by the person, with doses and dates | works |
| Wearables | Garmin and Apple Health exports | works |

Roughly four hundred laboratory markers are recognised. Reference intervals are
taken **from that person's own printed forms** — never from a table inside the
program — because they depend on method, units, sex and age. Where a form gives
no interval, the value is shown without a flag rather than judged against a
borrowed norm.

---

## What computes what

This is the design decision the whole thing rests on.

**Code computes.** Flags, trends, thresholds, genotypes, diplotypes, polygenic
scores, coverage, drug interactions — all deterministic, all from files, all with
the source recorded next to the number.

**A language model only puts it into words.** It is given computed facts and
their provenance; it is not asked to infer anything from raw data. Where the
facts are absent, it is required to say so rather than fill the gap.

The practical consequence: the failure mode of a general-purpose model on medical
data — a fluent statement about something it never saw — is structurally
unavailable here, because the statement has to come from a computed object.

---

## What it can and cannot answer, by class of question

The pipeline differs by input class and by the genetic architecture of the trait,
and the program says which cell an answer sits in before answering.

**Monogenic traits** (one variant decides). ClinVar and the ACMG secondary
findings list (v3.3, 84 genes). Reported as a reason for a clinical test, never
as a substitute for one. Short reads do not call large deletions at all, so
"no pathogenic variant found" is qualified accordingly.

**Oligogenic traits.** Partially: the catalogued loci are read; interaction
between them is not modelled, and that is stated rather than hidden.

**Polygenic traits.** A score from the PGS Catalog, plus what is actually
measured in the person's laboratory history. **Where a direct measurement
exists, it outweighs the score** — a computed percentile for ferritin level is
withdrawn from trust when serum ferritin has been measured three times. Ancestry
is verified by computation against 1000 Genomes rather than assumed, and the
sensitivity of the percentile to the choice of reference population is measured
(median spread across populations: 26.7 percentage points).

**Consumer arrays are not read yet, on purpose.** Positive predictive value of a
chip for BRCA1/2 is 4.2% (BMJ 2021), and 40% of variants taken from raw
direct-to-consumer data and sent for clinical confirmation are false positives
(Moscarello 2019). Support is being built with a frequency floor, so that rare
findings from a chip are reported as a signal requiring confirmation and not as a
finding.

---

## The part that is unusual

Alongside every report the program produces a second artefact: **what cannot be
said from this data, and what would close each gap.**

Coverage is measured per gene from the aligned reads. A gene read at 88% of its
bases at sufficient depth returns the same "nothing found" as a gene read at
100% — so until coverage is known, "no findings" is not treated as a statement.
The criterion for declining to answer is therefore a physical measurement rather
than a model's confidence.

The same layer withdraws polygenic scores from trust with the reason given —
insufficient model coverage, near-zero effect size, no agreement between
published models, or a direct measurement that supersedes the score — and says,
for each, whether anything in the person's own data could fix it.

---

## What it deliberately does not do

- It does not assert causation. "Ferritin rose after the course" is a fact it
  will state; "the course raised ferritin" is a claim it is not permitted to
  make, outside a pre-registered n-of-1 design with its statistical limits
  computed in advance.
- It does not impute rare clinically significant variants (r² of 0.2–0.5 there
  is a coin toss).
- It does not substitute a "generally accepted" reference range for a missing
  one.
- It does not carry a number without provenance: database version, read depth,
  model, and the primary source for the direction of an effect.
- It does not send the profile anywhere. Two lookups leave the machine when
  asked for by name — a drug name and an rsID — and the program prints the full
  list of hosts it can reach so the claim can be checked rather than believed.

---

## Current state, honestly

Published as version 0.1.x. **No external clinical validation and no benchmark
against existing systems** — nobody outside the author has run it on their own
data yet. That is the next thing needed, and it is the reason this page exists.

What would be most useful from a clinical side, in order: twenty to thirty
de-identified cases with a genome and at least two laboratory panels, to run a
pilot; a clinician co-author for the first paper; and — least obvious, most
valuable — two or three specialists marking up, by hand, **what cannot be said**
on a dozen cases. That last one is the ground truth against which the central
claim of this project can be tested at all. Everything else can be computed.

---

## How to take part

**scholion.dev@proton.me**

The code is at **github.com/CrossRead/scholion** and takes issues and pull
requests. The address above is for what does not belong in a public tracker.
Three things would be more useful than anything else, in this order:

1. **De-identified cases for a pilot** — twenty to thirty profiles with a genome
   and at least two laboratory panels. Nothing here has been run on anyone's data
   but the author's, and until that changes no claim in this document is worth
   more than the code behind it.
2. **A clinician co-author** for the first paper. The subject is the artefact of
   the unsayable: formalising what may not be claimed from a given set of data,
   and measuring whether a language model with this layer fabricates less than
   the same model without it.
3. **Hand-marked boundaries.** Two or three specialists writing down, on a dozen
   cases, what cannot be said from them. An hour of expert time per case. This is
   the ground truth for the central claim of the project, and there is nowhere
   else to get it — everything else in the benchmark can be computed.

Corrections are welcome at the same address and are worth as much: a wrong
threshold, a direction of effect taken from the wrong primary source, a
laboratory whose forms are not parsed, a formulation that reads as a clinical
claim when it should not.

**Please send no patient data of any kind** — not in an attachment, not as an
example. Describe the shape of the problem. For de-identified material, agree
the procedure by e-mail first.

---

## Sixty seconds, on nobody's data

```bash
pip install scholion
scholion init --demo     # a fictional person, not anybody's real data
scholion overview
scholion limits          # what cannot be said from that profile, and why
```

Licence: Apache-2.0, knowledge base CC BY 4.0. Contributions to the knowledge
base are accepted under evidence rules: a source, the population it was
established in, the direction of the effect and the action it implies.
