# Scholion

A local analysis layer over your own medical data: genome, years of lab results,
prescriptions, wearables. Read them against each other, with the source shown
behind every statement.

Three ways in, one core: a local web app, a skill for a language model, and a
plugin for [Ouroboros](https://github.com/razzant/ouroboros).

**Version 0.3.4** — first published as `0.1.0` on 16.08.2026. Not a medical
device and not a doctor. Everything the system produces is material for your
own decisions and for a conversation with your physician.

---

## Sixty seconds, on nobody's data

Before you decide whether this is worth pointing at your own medical record, run
it on somebody who does not exist:

```bash
pip install scholion
scholion init --demo   # lay out a synthetic profile of a fictional person
scholion overview      # the main screen: flags, gaps, counters
scholion limits        # what CANNOT be said from that profile, and what would close it
scholion phenoage --panels   # the refusal, in full: which panel is short of what
```

`init --demo` writes the demo where every other command reads from, so the four
lines above work one after another. There is also `scholion demo`, which builds
the same profile in a directory of its own and touches nothing you already have —
useful once you have your own data and want to look at the demo beside it. It
prints the command to view it; the four lines here are the shorter road in.

The demo is deliberately imperfect. One panel is missing markers, so you can watch
the system refuse to compute a biological age instead of filling the gap in — that
refusal is the product, more than any number it prints. The fourth command is where
you see it: which panel it is, which markers are missing, and what would complete
it. Every file in the demo declares itself synthetic in its own `_meta`.

---

## Why

Your medical record is scattered and internally incomparable. The genome sits in
gigabytes you cannot open. Lab results are a stack of PDFs from different labs
with different reference ranges. Prescriptions are on paper. A wearable
accumulates years of measurements nobody has ever looked at as a whole.

Separately each layer is close to useless. Together they answer questions none of
them answers alone: why vitamin D does not rise on a high dose, whether a statin
is safe given this pharmacogenetics, what actually increases deep sleep *in this
particular person*.

The core idea is **distillation**. A raw genome will not fit into a language
model. But genome plus labs plus prescriptions plus wearables compress into a
compact profile that can be read in full, while the complete genomic database
stays alongside for pinpoint queries.

```
data → parsing → annotation → profile → reasoning → answer
```

---

## What already works

The list runs deepest layer first, which is the opposite of the order to start
in — see [Bring what you have](#bring-what-you-have). Nothing below requires
the layer above it.

**Genome.** A full VCF built from your own raw reads, annotated against a current
ClinVar snapshot with version provenance. A separate ACMG SF v3.3
secondary-findings layer across 84 genes, with reporting rules (recessive genes
only when biallelic, and so on). A curated catalogue of loci genotyped directly
from aligned reads. Plus measured **callability**: for every clinical gene you
know what fraction of bases was read deeply enough — without it, "no findings"
means nothing.

**Diplotype-level pharmacogenomics.** PyPGx across 18 genes from BAM — copy
number, phasing, star alleles — and PharmCAT with ready CPIC/DPWG/FDA
recommendations. This is a level above single SNPs: `CYP2C19 *2/*17` reads as an
intermediate metabolizer only because the phase is known, and `CYP2D6` copy
number cannot be determined from individual polymorphisms at all.

**Polygenic scores.** Traits from the PGS Catalog, each carrying an evidence
level and a validity note. Scoring positions are re-genotyped from BAM: an
ordinary VCF has no reference homozygotes, and without that step model coverage
lies. Models are pinned in a registry — otherwise a series silently changes under
a swapped model.

**Longevity.** LongevityMap with allele direction resolved against primary
sources: "carrier of a variant in gene X" instead of a false "risk".

**Labs.** Automatic ingest from PDF forms — **Russian ones today**; any language
goes in through a CSV panel or one command per value. Hundreds of recognised
markers, timelines and trends, reference ranges verified against the printed
line of the form. Three
levels of assessment instead of two: outside the interval, *near the boundary*
relative to your own history, and a separate layer of clinical action thresholds
— derived from outcomes, sometimes inside the reference interval and sometimes
far outside it.

**Prescriptions.** The full regimen with doses and statuses, interactions,
monitoring labs per drug class, open questions for the physician. Any new drug is
checked as a second opinion: pharmacogenetics, interactions with the current
regimen, and what to monitor.

**Lifestyle and sleep.** Multi-year wearable trends, body composition, workouts.
Sleep phases are parsed in full — deep sleep, REM, sleep stress, sleep score,
bedtime — monthly, plus a per-night file for n-of-1 analysis, where monthly
averages answer the wrong question.

---

## What makes this different

Everything listed above exists separately elsewhere. The difference is the layer
that separates a *finding* from a *conclusion*.

**Annotation carries no direction.** "Pathogenic", `stop_gained`, an orange flag
in a consumer nutrigenetics report — all describe the variant's relation to the
*reference*, not to the person. Zygosity, inheritance mode and sex routinely
dismiss most of what a pathogenic-tier list contains; an orange flag frequently
points in the favourable direction; a `frameshift` can mean a protein **appeared**
rather than broke. Hence five filters applied to every finding, with phenotype
plausibility checked first — before consulting any database.

**A negative result is qualified by coverage.** A gene read at 70 % yields the
same zero as a gene read at 100 %. Until it is measured, "no findings" is not a
statement — and the measurement is published in the report rather than kept as
an internal layer, which is also what ACMG 2013, EuroGentest and ISO 15189 ask
for. One command shows the whole of it:

```bash
scholion limits      # what cannot be said from this data, why, and what would close it
```

Every line of that report ends in an instruction. A limitation with no way out
is a shrug in the shape of a document.

**A threshold that fires on almost everything gets fixed, not explained.** A
cheap check before any interpretation: what fraction of objects did the flag hit?
A flag that marks nearly every object carries no information, however plausible
its formula.

**Retracting a previous conclusion matters more than a new finding.** An old
formulation lives on in documents and in your head until it is explicitly
withdrawn. That is why the changelog has a mandatory "what was retracted"
section.

**Provenance for everything.** Which database version, at what read depth, from
which model, with effect direction taken from which primary source. A number
without an origin does not enter the profile.

---

## Boundaries

An honest account of what the system does not do.

- **It does not diagnose and does not change therapy.** Statements are
  threshold-shaped: "factor X is present, discuss with your physician", never
  "take Y".
- **Short reads do not see structural variants.** Large exon deletions are not
  called at all — for some genes that is a substantial share of pathogenic
  alleles, so "a monogenic form is excluded" cannot be said without a separate
  test.
- **Polygenic scores are trained mostly on European cohorts, and a percentile is
  not a probability.** For research-tier traits, disagreement between models can
  exceed the signal.
- **A catalogue of published associations is not a risk estimate.** The existence
  of a paper does not make a variant a factor.
- **A consumer array (23andMe and the like) is not read directly.** A raw export
  has to be converted to a GRCh38 VCF with external tools first — `genome/README.md`
  describes the route — and from there everything works, minus the polygenic
  scores, which need a BAM. What the next wave adds is the import itself and the
  three-valued status of a locus: *called* / *not called* / *not on the chip*.
  Until then the third case is reported as the second, which is the safe direction
  but a coarse one: an array covers a fraction of the positions, and the absence
  of a variant there does not equal reference. A positive finding off an array
  will be reported as a signal to confirm rather than as a finding, for the same
  reason — the positive predictive value of a chip for BRCA1/2 has been measured
  at around 4 %.

---

## Bring what you have

The genome is the deepest layer, not the entrance. Every rung below works on its
own, and each one makes the ones above it sharper:

| You have | What to do | What you get |
|---|---|---|
| Nothing at all | `scholion demo` | The whole product on a fictional person, and its refusals |
| A few numbers off a form | `scholion add-lab "Ferritin" 2026-08 41 --unit ng/mL` | A series, a corridor, a flag — and a unit that is converted rather than believed |
| A whole panel | `scholion import-labs panel.csv` | Thirty results in one command; the file is imported whole or not at all |
| Russian lab PDFs | `scholion ingest-labs "<folder>"` | Years of forms parsed, with the reference range read off each printed line |
| A wearable export | `scholion ingest-garmin "<folder>"` | Sleep phases, load, body composition as trends rather than as a daily number |
| Prescriptions | `scholion add-med "name" --dose "…"` | Interactions, monitoring tests per class, a second opinion on anything new |
| A VCF or a BAM | see `PREPARING-THE-GENOME.md` | Pharmacogenetics, ClinVar findings, ACMG SF, polygenic scores, longevity |
| A consumer array | convert it to a GRCh38 VCF yourself (`genome/README.md`) | The same as a VCF, minus polygenic scores; positions the chip does not carry count as unread |

Whatever you skip, `scholion limits` says what that costs you and what would close
it. Nothing here silently degrades: a layer that is missing is named as missing.

---

## Four ways to install

The same core, four deliveries. They differ in what you must already have, not
in what they can do:

- **a terminal and Python** → the pip package (2), or the unpacked folder (1) if
  you would rather install nothing;
- **only a language model** → the skill bundle (3): one file, and the model does
  the rest;
- **Ouroboros already running** → the plugin (4), which adds 14 tools to an agent
  you are using anyway.

Analysis is the same core in all four. What changes is who types the commands.

### 1. A folder you unpack and run

No installation at all. Python 3.10+ is the only requirement: every line of
analysis runs on the standard library. Reading laboratory PDFs is the exception —
that needs `pdfplumber`, which the pip package brings with it and this delivery
does not. Everything else works from the unpacked folder as it stands.

```bash
./bin/crossread --help
SCHOLION_PROFILE_DIR=demo/profile ./bin/crossread overview
```

`crossread` — "read your sources against each other". The command name is
deliberately not the project name: a noun holds the brand, a verb explains itself
without documentation, the way `brew` does for Homebrew. It installs nothing —
it locates the project root relative to itself and passes the call on.
`python3 -m scholion …` is literally the same call.

### 2. A pip package

```bash
pip install scholion
scholion init            # lay out the data directory
scholion serve           # local web interface on 127.0.0.1
```

That is everything needed to read your laboratory PDFs — `pdfplumber` comes with
the package, because loading lab results is the first thing most people do and a
tool that cannot do it out of the box is not installed, it is half-installed.

One optional extra, for the genome path:

```bash
pip install "scholion[genome]"   # faster VCF access via pysam
```

`pysam` stays optional on purpose: it compiles, it is platform-specific, and
working with a genome needs external tools (bcftools, samtools) anyway. Without
it the built-in reader works — slower, on the standard library.

#### External tools for the genome path

Reading a VCF, indexing it and measuring coverage are done by separate programs —
`bcftools`, `htslib`, `samtools` and a few others depending on how far you go.
They are not Python packages and pip cannot bring them, so the application does
the next best thing: it says which ones are missing, why each is needed, and what
would install it.

```bash
scholion tools              # what is here, what is not, and the exact commands
scholion tools --install    # install the base set (the flag is the confirmation)
```

`scholion init` asks the same question once, at the end of the first run, and
does nothing if you say no. Two rules hold in both places: nothing is installed
without an explicit answer, and nothing asks for administrator rights — Homebrew
and conda install into your own home directory, and anything that would need
`sudo` is printed for you to run yourself.

Two entry points, `scholion` and `crossread`, run the same core; the help text
uses whichever name you called.

### 3. A skill for a language model

Three shapes, from the easiest inward.

**If terminals are not your thing at all** — download the skill straight from
the published page and attach it to your chat with Claude or ChatGPT, then say
«set this up». The model reads it and walks you through, one small step at a
time: [scholion-skill.md](https://crossread.github.io/scholion/scholion-skill.md)
(the entry, one file) or
[scholion.skill](https://crossread.github.io/scholion/scholion.skill) (the full
bundle with the reference texts and the safety rules). Both are generated by
the same build that publishes the page, so they cannot go stale.

**If you have the source tree**, the same bundle builds locally:

```bash
python3 src/tools/make_skill_package.py     # writes dist/scholion.skill
```

**If the package is already installed**, the same instruction is inside it:

```bash
scholion skill           # the short entry — what this is and how to start
scholion skill --full    # the full instruction (INSTRUCTION.md)
scholion skill --path    # just the path, to attach the file
scholion skill --rules   # the assistant rules alone (ASSISTANT-RULES.md)
```

The instruction is split in two on purpose. The full text runs past a thousand
lines and costs roughly seventeen thousand tokens if a model loads it on every
trigger — and the thing a newcomer needs, how to begin, is not in it. So the
entry is short and the model opens the reference when the task calls for it.

The model works through the command line: it asks you to run a command and reads
the output. It gets no access to your machine, and the safety rules in
`ASSISTANT-RULES.md` take precedence over every other instruction it is given.

### 4. A plugin for Ouroboros

`scholion/ouroboros_tools.py` registers 14 `sch_*` tools — second opinion on a
drug, lab analysis, locus lookup, polygenic scores, longevity, goals and more.
Ouroboros discovers tool modules by scanning its own tools package, so the file
is copied there once:

```bash
pip install scholion
cp "$(python3 -c 'import scholion.ouroboros_tools as m; print(m.__file__)')" \
   <ouroboros>/ouroboros/tools/
export SCHOLION_REPO_DIR=~/.local/share/scholion    # where your data lives
```

Self-check outside Ouroboros: `python3 -m scholion.ouroboros_tools` prints the
tool list.

---

## What each delivery promises

The four deliveries above are not the same thing in four wrappers. They make
different promises on purpose, and the difference is worth stating plainly before
you pick one — an instruction that assumes the wrong delivery fails at the moment
you try to run it.

| | `pip install scholion` | source checkout / sdist |
|---|---|---|
| CLI, local web app, the skill | yes | yes |
| `demo` and the whole first screen | yes | yes |
| Profile, labs, medications, studies, wearables | yes | yes |
| Reasoning, provenance, `limits`, the knowledge base | yes | yes |
| Reading laboratory PDFs | yes | yes |
| **Genome preparation** — FASTQ → VCF, BAM work, VCF QC, ClinVar annotation, PGS scoring, PharmCAT/PyPGx | no | yes, and it needs external tools |
| Release and maintenance tooling, the test suite | no | yes |

**The wheel carries the application; the source tree carries the workshop that
prepares data for it.** `src/ingest/` is not a missing part of the package. Those
scripts orchestrate `bcftools`, `samtools`, PharmCAT and PyPGx over reference
genomes and multi-gigabyte read files. Shipping the scripts would not make any of
that work after `pip install` — it would only make the wheel larger and blur the
line between the program and the pipeline. So the boundary is drawn where it
actually falls: the application consumes prepared data, the toolkit produces it,
and each says which it is.

What follows for you in practice:

- **If you already have a VCF** — `pip install scholion` is enough for everything
  this README shows.
- **If you are building a genome from raw reads** — clone the repository. You
  will need the external bioinformatics tools anyway; `scholion tools` tells you
  which are missing and how to get them.
- **If an instruction names a path like `src/ingest/…`** — it belongs to the
  source tree. The skill marks those workflows as such rather than assuming the
  files are present, and a test checks that every path the skill names is one the
  package actually carries.

## The demo profile, and why it is imperfect

It is generated, not collected: `src/tools/make_demo_profile.py` builds a
fictional person deterministically, and refuses to run over a real profile. Every
file declares itself synthetic in its own `_meta`, and the build audit rejects one
that does not — which is what lets screenshots and this README show a product
without showing anyone's medical record.

The gaps in it are deliberate. A demo where everything computes teaches the reader
that everything computes.

---

## Language

Output is English by default and switches to Russian on request:

```bash
scholion overview --lang ru
export SCHOLION_LANG=ru
```

Russian on the **input** side is not a setting but a feature: lab forms are
recognised in Russian as well as English, and the recognition dictionaries stay
Russian regardless of the output language.

---

## Where your data lives

One data directory, the same layout for everyone:

```
<data>/
  profile/      what the application knows: labs, prescriptions, metrics, goals
  genome/       what the application reads from the genome: VCF and derived slices
  raw/          what arrived from outside — lab/, sequencing/, wearables/, reference/
  work/         anything that can be recomputed
  archive/      previous versions of profile files
```

`scholion init` creates it with a short note in each folder. By default it sits in
`$XDG_DATA_HOME/scholion`, on macOS `~/Library/Application Support/Scholion`;
`SCHOLION_REPO_DIR` overrides it. Heavy directories — `raw/` and `work/` — can
live on another disk: name them in `profile/sources.json`. When that disk is
absent the application says so by name instead of showing zeros.

**Nothing personal ever enters the repository.** Genotypes, labs and
prescriptions are not baked into the code — they are read from your profile at
query time, which is why another person puts their own files in the same places
and gets their own analysis. The boundary is held by three barriers:
`.gitignore`, a `pre-commit` hook checking paths and contents, and a `pre-push`
hook checking the outgoing history.

---

## Privacy

The server binds to the loopback interface only, and **no analysis needs a
network**: labs, genome, pharmacogenomics, polygenic scores and every report are
computed locally, with no language model involved anywhere in the core.

Two lookups do go out, and only when you ask for them by name. Resolving a drug
missing from the local knowledge base sends **the drug name** — first to a free
translation service if the name is Russian, then to the NLM RxNorm and RxClass
APIs, then to the CPIC API for the gene–drug pair. Looking up an rsID queries
Ensembl. Six hosts, no analytics, nothing in the background, and never anything
from your profile.

Separately, the scripts that **prepare** data — building a genome from raw reads,
refreshing the knowledge bases — download from nine more: NCBI, Ensembl's FTP,
UCSC, HAGR, GitHub and PyPI among them. You run those by hand, they are not part
of any analysis command, and the Assistant screen lists them as their own layer
rather than mixing them into the six above. The application itself installs nothing: reading a
laboratory PDF used to run `pip install pdfplumber` on its own when the library
was missing, and that is gone — the library is declared as a dependency instead,
and if it is absent the tool says so and names the command rather than running
it.

The claim is falsifiable rather than rhetorical: the application scans its own
source and lists every host it can reach on the Assistant screen, so you check
the inventory instead of trusting this paragraph. `SCHOLION_OFFLINE=1` disables
outbound requests entirely.

---

## What is inside

```
ASSISTANT-RULES.md        safety rules — precedence over everything else
CHANGELOG.md              release journal
docs/                     versioning policy, data layout, tests and compatibility

src/scholion/             the core: engine, server, CLI, genome, PGS, wearables, web
src/scholion/knowledge/   public catalogues: loci, ACMG SF, thresholds,
                          pinned PGS models, interactions, marker recognition
src/scholion/i18n/        message catalogues, one file per language
src/scholion/skill/       the instruction for a language model
src/ingest/               pipelines: FASTQ→VCF, ClinVar, PGS, LongevityMap,
                          pharmacogenomics, callability, LoF scan, wearables
src/tools/                package sanitizer, hooks, release notes, publication
ouroboros_plugin/         tool registration for Ouroboros
tests/                    the whole test suite; runs on the standard library alone
```

---

## Licences

- **Code** — Apache License 2.0 (`LICENSE`). Free to use, modify and distribute,
  including commercially, with the notice preserved.
- **Curated knowledge base** (`scholion/knowledge/*.json`) — CC BY 4.0
  (`LICENSE-DATA`). Version 4.0 chosen deliberately: it is the first to
  explicitly license the European sui generis database right.
- **Required source notices** — `NOTICE`, including the verbatim LOINC notice
  required by the Regenstrief licence.
- **Provenance of every third-party file** — `ATTRIBUTION.md`: source, licence,
  required citation. Data whose licence forbids commercial use or demands
  ShareAlike is not bundled at all and is fetched at runtime instead.
- **Purpose and limits** — `DISCLAIMER.md`. Not a medical device.
- **How to contribute** — `CONTRIBUTING.md` (DCO, no CLA).
- **Reporting a vulnerability** — `SECURITY.md`; the threat model is in
  `THREAT_MODEL.md`.

---

## Versioning

Semantic versions with the date in the entry heading. The rules for choosing a
number, the release procedure and the two-repository model are described in
`docs/`.

**Publication began at `0.1.0`, not the `2.24.0` the project had reached
internally by then** — a version number is a promise to whoever already runs
the previous one, and nobody outside had run any of those yet, so the count
reset to where that promise begins.

**Below `1.0.0` the public contract may break.** The project's own rule is that
command names, the top-level fields of `--json` and the file names inside a
profile may grow and may not shrink, and `python3 src/tools/check_compat.py`
enforces it on every run. Until `1.0.0`, treat that as **internal discipline
rather than a promise to you**: it is said plainly so that anyone building on
`--json` knows how much weight it carries, which is some, and not all.

**`1.0.0` will be earned by use, not by features.** The condition is a number of
people who have run this on their own medical data and reported what happened —
not a count of finished capabilities. The failure modes that matter for a system
like this one appear in the second record and in the tenth, not in the first.

One entry type is specific to this project: a **series break** — a change to the
knowledge catalogues that alters the result on unchanged input. Values from
before and after such a change cannot go on the same chart without a note.

---

## Contact

**scholion.dev@proton.me**

For anything that fits a tracker — a defect, a text that is wrong, a laboratory
whose forms are not read — open an issue. The address is for what does not: an
offer of de-identified data for validation, co-authorship, a private word.

**Please send no personal health data** — not in an issue, not in an e-mail, not
in an attachment. Describe the shape of the problem, not your results;
`scholion redact` strips the structural parts of a file and says plainly what it
could not decide for you.

## Safety

The assistant supports decisions; it is not a physician. It does not diagnose,
does not change therapy, cites its sources, and never accepts or enters
credentials for external services. The full statement lives in
`ASSISTANT-RULES.md` and takes precedence over every other instruction.
