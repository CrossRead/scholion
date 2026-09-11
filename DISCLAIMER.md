# Disclaimer and intended purpose

## Intended purpose

Scholion is a **research and educational tool**. It reads a person's own
genomic, laboratory, prescription and wearable data, reconciles those layers
against each other, and presents the result together with the source behind
every statement, so that the person and their clinician can examine it.

Scholion is **not a medical device**. It is not intended to diagnose, treat,
cure, mitigate or prevent any disease or condition, it does not provide
individualised medical advice, and it does not replace consultation with a
qualified health professional. Any output is material for a conversation with
a clinician, never a substitute for one.

Scholion is **not a clinical decision support system** and is not positioned as
one. Several of its features carry clinical-sounding names — "second opinion",
"clinical action thresholds", drug interactions, pharmacogenomics — and those
names describe *what is being read*, not a role the software takes. Nothing in it
ranks treatments, computes a recommendation, or is designed to be relied upon in
the moment a clinical decision is made. The nearest true description is a
local-first workbench for a person's own longitudinal data, with explicit limits
on what those data support: its most characteristic output is the list of things
that **cannot** be concluded, and the conclusions it does draw are traceable to
the source that produced them.

Scholion does not issue prescriptions and does not select doses. Where the
software surfaces published clinical guidance — for example a CPIC
pharmacogenomic recommendation — it reproduces that guidance with its source
so it can be verified, and it is the reader's and the clinician's decision what
follows from it.

## Which genetic questions this answers, and which it does not

The boundary is not the seriousness of the disease. It is who made the
classification.

**Answered: a known variant that somebody has already classified.** ClinVar
pathogenic and likely-pathogenic entries, the 84 genes of the ACMG
secondary-findings list — 28 of which are hereditary-cancer genes — and CPIC
star alleles for pharmacogenetics. A finding here is reported with its source and
remains a reason to seek confirmation in a clinical laboratory, never a diagnosis.

**Answered as a position, not as a verdict: the polygenic layer.** A score places
a person in a distribution built on a reference population. It is not a syndrome
and does not answer a question about one; a polygenic score for a cancer and a
hereditary cancer syndrome are different objects, and this software does not
offer one as an answer about the other.

**Not answered: a variant nobody has classified, in an undiagnosed patient.**
This build does not classify a novel variant under ACMG/AMP, does not perform
trio analysis, does not detect copy-number or structural variants, and does not
prioritise candidates by phenotype terms. A diagnostic search for the cause of an
undiagnosed condition is outside it, and the honest output in that situation is a
refusal that names what would be required — which is what the software produces.

## Limitations you must assume are present

- **A negative result is only as good as the coverage behind it.** A gene read
  at 70 % returns the same "nothing found" as a gene read at 100 %. Unless
  callability has been measured and shown, "no finding" is not a statement.
- **Annotation carries no direction.** "Pathogenic", "stop_gained" or a warning
  flag describe a variant's relationship to the reference sequence, not to the
  person in front of you.
- **Polygenic scores are population statistics.** A percentile depends on the
  model, on the reference population and on the variants that were actually
  callable; it is not a diagnosis and often not even stable between models of
  the same trait.
- **Reference intervals are not thresholds for action.** They come from the
  reporting laboratory; clinical decision thresholds are a separate thing and
  may lie inside or far outside them.
- **The knowledge base is curated by volunteers and may be wrong or out of
  date.** Every entry carries a source. Check the source.

## Privacy

Scholion runs locally and binds to 127.0.0.1 only. Personal data — genome,
laboratory reports, prescriptions, wearable exports — stays on the user's
machine, is never part of this repository, and is never uploaded: no analysis
needs a network, and nothing runs in the background.

Two lookups do leave the machine, and only when the user asks for them by name.
Resolving a drug that is missing from the local knowledge base sends **the drug
name** — to a translation service first if the name is Russian, then to the NLM
RxNorm and RxClass APIs, then to CPIC for the gene–drug pair. Looking up an
unknown rsID sends **that rsID** to Ensembl. Nothing from the profile travels
with either. This is stated as a small, explicit, user-triggered disclosure
rather than as "no data leaves the machine", because a drug name is itself a
statement about the person asking. `SCHOLION_OFFLINE=1` forbids both. Users are responsible for their own backups, disk encryption and for
whatever they choose to paste into third-party services, including issue
trackers and language models.

## No warranty

This software and this knowledge base are provided "as is", without warranty of
any kind, express or implied, as set out in the Apache License 2.0. The authors
and contributors accept no liability for any decision taken on the basis of its
output.
