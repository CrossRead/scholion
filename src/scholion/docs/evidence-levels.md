# Evidence levels A–E

Every statement Scholion makes about a genetic position carries a letter from A
to E. The letter says what stands behind the statement, and the confidence with which it should be read. It appears everywhere the statement does: on the page, in
the command line, in a tool's JSON, in a printed report, and in what an
assistant retells from these tools.

The words below are printed from the product's own legend
(`knowledge/evidence_levels.json`), so this page and the program cannot say
different things.

| Level | What stands behind it | What the product says |
|---|---|---|
| **A** | A clinical practice guideline, or a gene–disease link GenCC rates Definitive or Strong. | What follows, with the source. |
| **B** | An association replicated in independent cohorts, with a measured effect size. | What follows, with the effect size and the source. |
| **C** | Single studies, or studies that contradict each other. | Your reading and the available interpretation, with confidence, sources and limitations. |
| **D** | A candidate gene whose association has not been replicated. | Your reading and the available interpretation, with confidence, sources and limitations. |
| **E** | No source at all: the position came from a laboratory report and nothing published stands behind it. | Your reading, known gene function and any recorded interpretation labelled unestablished; missing variant evidence stays explicit. |

## Confidence and clinical eligibility

Available catalogue interpretations are shown at every level A–E. Confidence
qualifies an interpretation rather than suppressing its wording. The reader can
inspect the source, mechanism and support gaps, and the clinician decides what
weight to give the statement.

- **C** — studies are isolated or disagree;
- **D** — evidence is limited and the association has not been replicated;
- **E** — variant evidence is absent. A recorded interpretation is unestablished;
  known gene function does not supply a missing variant effect.

Showing an interpretation does not establish a diagnosis or a treatment rule.
Automatic clinical findings and decision routes still require their own support;
`verdict_allowed` describes that eligibility, not permission to display text.
Gene function and GenCC gene–disease validity retain their own source and scope.

## Who assigns the letter

A curator assigns the letter when a position is added, from the source the
position names. The program never assigns one. A position without a source can
only be E.

## Who checked the sentence

Next to the letter, each position says who checked its sentence against the
source, by role and never by name: the panel's author or a clinician. The package
names no person.

## For assistants

When you relay a statement from these tools, name its level with it. Retain its confidence, source and limitations. Do not promote a low-confidence
interpretation to an established clinical finding, and do not invent missing
facts or clinical support.

In the command line, `scholion doc evidence-levels` prints this page.
