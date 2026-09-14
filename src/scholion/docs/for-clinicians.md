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
| Genome | consumer array export (23andMe, AncestryDNA, MyHeritage, FamilyTreeDNA, Living DNA) | works, as a distinct class of input — see below |
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

**A consumer array is read as a different class of input, not as a weaker
genome.** Every catalogued position answers one of three ways — called, no-call,
or *not on this chip at all* — and the third is the one that matters: on an array
an absent position was never interrogated, so treating it as a reference call
would turn «this instrument cannot see that locus» into «you do not have that
variant». The paths a chip cannot support — ClinVar screening, ACMG secondary
findings, polygenic scores — refuse with the reason rather than answering.

**What is still missing there, and it matters clinically.** Positive predictive
value of a chip for BRCA1/2 is 4.2% (BMJ 2021), and 40% of variants taken from
raw direct-to-consumer data and sent for clinical confirmation are false
positives (Moscarello 2019). The frequency floor that would report a rare
array-derived finding as a signal requiring confirmation rather than as a finding
is **not implemented yet**. Until it is, the honest reading of an array here is
pharmacogenetics and the catalogued loci, not screening.

---

## A body system as one card

This is the shape most of the product now takes, and it is the part a clinician
is likeliest to want.

The body is laid out as the systems a laboratory actually issues panels for —
lipids, heart and vessels, carbohydrate metabolism, inflammation, thyroid,
adrenals, gonads, growth axis, pancreas, liver, micronutrients, kidneys — plus
a thirteenth built from wearable metrics. Asked about one of them, the program answers with a single
card: the laboratory now and its movement since the previous draw, the genetic
half of that system and how much of it was actually read, the polygenic scores
placed on it, the prescriptions acting on it, a target the treating clinician
set, what the test rules suggest, and the questions left open.

**The genetic half is composed from a base with a version, not from anybody's
memory.** 1203 genes across the twelve systems, taken from the Gene Curation
Coalition export, with every submitter's assertion kept side by side: who
asserted the gene–disease link, how strongly, under which mode of inheritance,
and on what date. Two groups disagreeing about one gene are shown disagreeing
rather than averaged. An assertion classified Limited, Disputed or Refuted is
never presented as a finding, and one copy of an allele in a recessive gene is
printed as carriership and raised as a question — never as a risk line.

**In front of that base stands what a base cannot supply: 92 authored positions
across the twelve systems.** The unit of a row is a position, not a gene: an rsID
with its HGVS on a RefSeq accession, the allele the author named, the mode of the
claim — monogenic, common variant, pharmacogenetic — and the phrase for one copy
and for two, each in both languages. The panel a clinician sent in September held
six rows for DIO1 alone, each with a different consequence, and a schema of «gene
→ one phrase» cannot express such a panel at all. A row whose phrase for the state
actually found has not been written is kept and printed as pending. Every row
that ships is signed by the author of the panel and by no clinician, and the card
says that in those words, with the count and the date: a reader is never left to
assume that a clinician stood behind a sentence. When a clinician signs a row,
that row says so instead — the mark is on the exception, the count on the rule. A row without a source, or without a
mode, is dropped and counted by reason rather than quietly omitted. Where short
reads cannot read a gene at all — a gene beside its pseudogene, a triplet repeat —
the panel names it as needing a separate method, and it is never counted as read
and never as clear.

A position the genome file does not list is the reference only when the alignment
says so: until the catalogue positions have been genotyped from the aligned reads,
such a position prints as not read, and the panel where the gap shows names the
step that closes it.

Three properties of the card are deliberate and are the reason it exists:

- **It will not call a system clear that it did not read.** «Nothing found» over
  a gene nobody read is a statement about the file. The count of unread genes
  travels inside the verdict, not in a footnote under it.
- **Genetics does not enter the 0–100 index.** A genotype cannot be refuted by
  the next blood draw; a score of laboratory deviation can. They stand side by
  side, and each system carries two rings — how much of its laboratory panel is
  measured and how much of its genetic half is read — which are never merged.
- **The next step comes in three baskets**, because they are three different
  actions by three different people: what to test, what to read in the genome,
  and what to ask the clinician. An empty basket says why it is empty.

The card has two densities, one for the patient and one for the clinician. They
differ in how much is said and **never in the verdict** — there is no reassuring
version. The clinician's density adds rsIDs and genotypes, coverage as a figure,
the class of each link, the source and its tier, the date and provenance of every
point, and the number of rows a gate dropped. The page prints as the sheet to
take to an appointment.

Where a curated statement is wanted — «this genotype means the following for this
drug» — the program does not write it. A curated layer takes such sentences from
a clinician, prints them only with a named source, counts what it dropped, and
until a sentence is written says plainly that it is not written. What has changed
since that arrangement was first offered is that the layer no longer ships empty:
92 positions are in the build, each with its source, the date it was curated, and
a signature — the panel author's, not a clinician's, which is what the card says.
Counter-signing a row, correcting it, or striking it out is the whole of what is
being asked of a clinician who wants to take part, and it is a smaller ask than
writing the list was.

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

This page ships with the build numbered 0.5.1. **There is still no clinical
validation study and no benchmark against existing systems.** What there is, is two external runs by
people who are not the author, and both are worth stating plainly because both
were useful and neither was flattering.

**A geneticist ran it blind on three clinical VCFs** with established diagnoses —
developmental delay, a suspected cancer syndrome, congenital short stature —
telling the program no phenotype. It found none of the three. By the criterion
this project sets itself it passed: it did not report «clear». It classified the
files as panel-class rather than whole-genome, declared the ClinVar and ACMG
paths closed before reading, and answered the direct question with «no — and this
is not a negative genetic result», listing what such an answer would require. By
the geneticist's criterion — find the causal variant — it failed.

The run produced one real defect and one real over-refusal, and both are fixed.
The defect: reading a locus took the first row at that coordinate without
checking its REF and ALT against the catalogue, so a clinically charged position
could return another variant's genotype carrying a confident label. It now
matches, and refuses by name when nothing matches. The over-refusal: an exome was
being classed as a narrow panel, which closed exactly the paths worth running on
an exome. It also produced four items of friction that a clinic would not
survive — missing index files, environment variables discovered by reading the
source, one profile per patient assembled by hand — and three of the four have
since been closed.

**A practising physician ran it on her own data** and asked it the questions she
asks in her own work: what to check before prescribing, and what to look at when
the examination says a person is well. Her answers reshaped the product — the
three entries, the curated gate, and the system card described above came out of
that exchange. The thing she asked for that the program still does not have is
a clinician's signature under the curated sentences. The mechanism that holds
them is no longer empty — 92 positions over the twelve systems, each signed by
the panel's author against the source it names — but a signature by the author of
a panel is not a clinical endorsement, and the card says whose it is rather than
letting the distinction blur.

What would be most useful from a clinical side is unchanged, in order: twenty to
thirty de-identified cases with a genome and at least two laboratory panels, to
run a pilot; a clinician co-author for the first paper; and — least obvious, most
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
