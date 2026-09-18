# Evidence levels A–E

Every statement Scholion makes about a genetic position carries a letter from A
to E. The letter says what stands behind the statement, and so what the product
allows itself to say. It appears everywhere the statement does: on the page, in
the command line, in a tool's JSON, in a printed report, and in what an
assistant retells from these tools.

The words below are printed from the product's own legend
(`knowledge/evidence_levels.json`), so this page and the program cannot say
different things.

| Level | What stands behind it | What the product says |
|---|---|---|
| **A** | A clinical practice guideline, or a gene–disease link GenCC rates Definitive or Strong. | What follows, with the source. |
| **B** | An association replicated in independent cohorts, with a measured effect size. | What follows, with the effect size and the source. |
| **C** | Single studies, or studies that contradict each other. | Your genotype, and why no conclusion follows. |
| **D** | A candidate gene whose association has not been replicated. | Your genotype, and why no conclusion follows. |
| **E** | No source at all: the position came from a laboratory report and nothing published stands behind it. | Your genotype only, with no interpretation. |

## Where the line falls

A conclusion ("this means something for you") is printed at **A** and **B**
only. The line between B and C does not move.

C, D and E are not degrees of caution. They are three different reasons for
printing a value without a conclusion, and they tell you different things:

- **C** — the data disagree;
- **D** — there are too few data;
- **E** — there are no data.

A position at E carries no sentence of the product's own. If a sentence could be
written, there would be a source to write it from, and the position would not be
at E.

## Who assigns the letter

A curator assigns the letter when a position is added, from the source the
position names. The program never assigns one. A position without a source can
only be E.

## Who checked the sentence

Next to the letter, each position says who checked its sentence against the
source, by role and never by name: the panel's author or a clinician. The package
names no person.

## For assistants

When you relay a statement from these tools, name its level with it. Do not
retell a C, D or E position as a conclusion: say what the genotype is and why
nothing follows from it.

In the command line, `scholion doc evidence-levels` prints this page.
