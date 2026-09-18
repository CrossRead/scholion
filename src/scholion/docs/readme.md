# Scholion

A local analysis layer over your own medical data: genome, years of lab results,
prescriptions, wearables. Read them against each other, with the source shown
behind every statement.

Five ways in, one core: a local web app, a skill for a language model, a plugin
for [Ouroboros](https://github.com/razzant/ouroboros), an MCP server so any
model that speaks the protocol can call the same tools, and a plugin package in
the Agent Plugins format for ChatGPT desktop, Codex, Cursor, VS Code, GitHub
Copilot and Kiro.

**Version 0.5.4** — first published as `0.1.0` on 16.08.2026. Not a medical
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

When you bring the first value of your own — a lab point, a metric, a
prescription, an import, a wearable export — the demo is **erased** and your
datum is written into an empty profile. One profile holds one person: a real
number sitting inside a fictional history is a series nobody can untangle
afterwards, and the demo costs one command to build again. The command tells you
it happened and names every file it removed. An ordinary profile is never
touched by this — only data that carries the synthetic mark can be erased.

---


### A real genome, on nobody's privacy

The demo is a fictional person and it works end to end — except in the layer this
product is strongest in. Without a genome, `limits` answers «nothing can be said
about the genome at all», which is honest and leaves the argument undemonstrated.

There is a genome anybody may look at. The Genome in a Bottle samples exist to be
published: they were selected, sequenced and consented for it, and the trio below
is consented for commercial redistribution. Fetching one is a single command, and
it says what it is fetching before it does:

```
python3 src/tools/fetch_demo_genome.py --list     # what it would fetch, fetching nothing
python3 src/tools/fetch_demo_genome.py            # fetch it into genome-demo/
```

That genome belongs to a real, published person — not to you, and not to the
fictional one of the demo. So it gets a profile of its own, and the product
refuses to read it beside anybody else's history: one genotype under another
person's laboratory series is a case about nobody. Point it at an empty profile
and read the two screens that matter:

```
scholion init --dir genome-demo/profile
SCHOLION_PROFILE_DIR=genome-demo/profile SCHOLION_GENOME_DIR=genome-demo scholion genome-status
SCHOLION_PROFILE_DIR=genome-demo/profile SCHOLION_GENOME_DIR=genome-demo scholion limits
```

`genome-status` measures what the file actually is rather than trusting its
extension; `limits` turns from «nothing can be said» into a list of what this
particular file can and cannot answer. That pair is the product's argument, and
now it can be run by somebody who has brought nothing of their own.

The file name is not written down anywhere here: the benchmark is versioned, the
release directory moves, and the tool reads the listing and stops if the pick is
not unambiguous. `SCHOLION_OFFLINE=1` stops it before the network — it is the one
thing in this tree that goes out on purpose.


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

**A consumer array is a different class of input, not a weaker genome.** 23andMe,
AncestryDNA, MyHeritage, FamilyTreeDNA and Living DNA exports are read directly —
including inside the `.zip` or `.bz2` a provider hands you — and every locus
answers one of three ways: called, no-call, or *not on this chip at all*. The
third is the one that matters: on a chip an absent position was never
interrogated, so treating it as a reference call would turn «this instrument
cannot see that locus» into «you do not have that variant». Measured on a real
23andMe v5 export: 46 of the 54 loci the catalogue held that day present, none of
them no-call, and
the eight absent ones named. The paths that a chip cannot support — ClinVar
screening, ACMG SF, polygenic scores — refuse with the reason instead of
answering.

**Any assistant can reach it, and none of them needs a key.** Several doors onto
one engine: the command line, a Model Context Protocol server (`scholion mcp`),
a skill folder any host can read, a plugin package in the Agent Plugins format,
the Ouroboros tools module and the Ouroboros Hub skill. The server speaks the
July 2026 revision of the protocol and the handshake revisions before it, and
thirteen of its tools return structured answers. There is no account, no token
and no credential for any of them — the analysis runs on the machine that holds
the data, so there is nothing to authenticate to. The build answers this itself:
`scholion capabilities --json` carries every door and, scanned from its own
source, every environment variable it reads. Instructions:
`scholion doc connecting-an-agent`.

**Both reference builds.** A file called against GRCh37 is read at GRCh37
coordinates, because most of the files people actually hold are GRCh37 and
nobody is going to re-sequence for us. Every catalogue locus carries both
coordinates, each written only where at least two independent primary sources
agreed — NCBI dbSNP, the Ensembl GRCh37 endpoint, and real GRCh37 files for 30
of them. Nothing is converted between builds: the offset is not constant even
within one chromosome, so arithmetic would return a plausible position pointing
at the wrong base. A locus the catalogue carries in one build only says so
rather than falling through to a reference assumption.

**Diplotype-level pharmacogenomics.** PyPGx across 18 genes from BAM — copy
number, phasing, star alleles — run through PharmCAT, which maps diplotypes to
CPIC recommendations locally. This is a level above single SNPs: `CYP2C19 *2/*17`
reads as an intermediate metabolizer only because the phase is known, and
`CYP2D6` copy number cannot be determined from individual polymorphisms at all.
The DPWG and FDA guideline tables that some pipelines add come from PharmGKB,
whose licence (CC BY-SA, no commercial redistribution) is incompatible with this
project's, so they are not bundled — CPIC (CC0) is what travels here.

**Polygenic scores.** Traits from the PGS Catalog, each carrying an evidence
level and a validity note. Scoring positions are re-genotyped from BAM: an
ordinary VCF has no reference homozygotes, and without that step model coverage
lies. Models are pinned in a registry — otherwise a series silently changes under
a swapped model.

**Longevity.** LongevityMap with allele direction resolved against primary
sources: "carrier of a variant in gene X" instead of a false "risk".

**Labs.** Automatic ingest from PDF forms — **Russian ones today**, with American
date formats read as well; delimited exports (CSV, TSV, TXT) go in through a reader
of their own, because a table dates its rows rather than its header and a person's
export is usually years of them. A **FHIR R4 bundle** — a portal export, Apple
Health clinical records, an EHR download — is imported by LOINC code through
`scholion import-fhir`. Any language also goes in through a CSV panel or one
command per value. Hundreds of recognised
markers, timelines and trends, reference ranges verified against the printed
line of the form. Three
levels of assessment instead of two: outside the interval, *near the boundary*
relative to your own history, and a separate layer of clinical action thresholds
— derived from outcomes, sometimes inside the reference interval and sometimes
far outside it.

**Prescriptions.** The full regimen with doses and statuses, interactions,
monitoring labs per drug class, open questions for the physician. Any new drug is
checked as a second opinion: pharmacogenetics, interactions with the current
regimen, and what to monitor. The question can be asked from three directions
and gets the same shape of answer each time — from the prescription («before I
take this, what in the genome bears on it»), from a class of disease («nothing
is prescribed and the examination says I am well»), or from a body system («what
belongs to the working of the thyroid»). All three judge their gene list through
one gate: a sentence is printed only with a named source, the rest are counted,
and a list that was not read end to end is never called clear.

**Lifestyle and sleep.** Multi-year wearable trends, body composition, workouts.
Sleep phases are parsed in full — deep sleep, REM, sleep stress, sleep score,
bedtime — monthly, plus a per-night file for n-of-1 analysis, where monthly
averages answer the wrong question.

**And the layer that assembles the rest: fifteen body systems, each answering as
one card.** This is the last item because the list runs deepest first, and it is
the first thing to open. The body is laid out as the systems a laboratory
actually issues panels for — lipids, heart and vessels, carbohydrate
metabolism, inflammation, thyroid, adrenals, gonads, growth, pancreas, liver,
micronutrients, kidneys, immunity, the musculoskeletal system, amino acids and
protein — and a sixteenth built from wearables. Click a segment of the radar, an organ on
the figure, or run `scholion system thyroid`, and one card comes back: the
laboratory now and its movement since the previous draw, the genetic half of the
system and **how much of it was actually read**, the polygenic scores placed on
it, the prescriptions acting on it, a target your clinician set, what to test,
and the questions to bring to the appointment.

The genetic half is composed from a base with a version rather than from
somebody's memory: 1469 genes across the fifteen systems, taken from the Gene
Curation Coalition's export with every submitter's assertion kept side by side —
who asserted the gene–disease link, how strongly, under which mode of
inheritance, on what date. A weak or refuted assertion travels marked as such
instead of being quietly dropped or quietly promoted, and one copy of an allele
in a recessive gene is printed as carriership, never as a risk line.

**In front of that base stands the layer a base cannot supply: 214 positions
across fourteen of the systems, authored rather than generated, each with its
evidence level.** The unit of a row is
a position, not a gene — an rsID with its HGVS on a RefSeq accession, the allele
the author named, the kind of claim the link permits, and the phrase for one copy
and for two. Where the phrase for the state actually found has not been written,
the row is kept and printed as pending, because that is the most informative row
on the screen: somebody put the position here and what follows from that genotype
is still to be written. Every row that ships is signed — by the author of the
panel, and by no clinician — and the card says exactly that, with the count and
the date, rather than letting a reader assume a clinician stood behind it; a
clinician's counter-signature, a correction or a striking out is what is being
asked for. Where short reads cannot read a gene at all — a gene
beside its pseudogene, a triplet repeat — the panel names it as needing a separate
method, and it counts as neither read nor clear.

A position the genome file does not list is the reference only when the alignment
says so. Until the catalogue positions have been genotyped from the aligned reads,
such a position prints as not read rather than as the reference — and the panel
where the gap shows offers the step that closes it: `scholion recompute` finds it,
names what it still needs, and runs it.

Two things the card will not do. It will not call a system clear that it did not
read — «nothing found» over a gene nobody read is a statement about the file, so
the count of unread genes travels inside the verdict rather than in a footnote
under it. And genetics does not enter the 0–100 score: a genotype cannot be
refuted by the next blood draw, so it stands beside the score, never inside it.
Each system carries two rings — how much of its laboratory panel is measured,
how much of its genetic half is read — and they are never merged into one
number.

The next step comes in three baskets, because they are three different actions
by three different people: **test** (the laboratory), **read in the genome**
(something you run yourself), **ask the clinician**. A basket that is empty says
why it is empty — «nothing» without a reason reads as «all is well».

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
- **A consumer array (23andMe and the like) reads a fraction of the positions.**
  A position the chip does not carry is reported as *not on this chip*, never as
  the reference. A positive finding off an array is a signal to confirm rather
  than a finding — the positive predictive value of a chip for BRCA1/2 has been
  measured at around 4 %.

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
| A wearable export | `scholion ingest-wearable "<folder>"` (Garmin or WHOOP) | Sleep phases, load, body composition as trends rather than as a daily number |
| Prescriptions | `scholion add-med "name" --dose "…"` | Interactions, monitoring tests per class, a second opinion on anything new |
| A target your clinician set | `scholion target set tsh --low 1 --high 2 --unit mIU/L --set-by "Dr N" --set-on 2026-09-12` | Drawn beside the corridor off the form, in a different stroke; standing outside it is a question, never a flag |
| A VCF or a BAM | see `PREPARING-THE-GENOME.md` | Pharmacogenetics, ClinVar findings, ACMG SF, polygenic scores, longevity |
| A consumer array | `scholion array` — drop the export in the genome folder, `.zip` and all | The locus catalogue read straight off the chip, each position called, no-call or *not on this chip*; ClinVar, ACMG SF and polygenic scores refuse with the reason |
| A FHIR bundle | `scholion import-fhir bundle.json` | Results matched by LOINC code, units converted or refused; what the bundle claims about its patient is reported, not applied |

Whatever you skip, `scholion limits` says what that costs you and what would close
it. Nothing here silently degrades: a layer that is missing is named as missing.

---

## Five ways to install

The same core, five deliveries. They differ in what you must already have, not
in what they can do:

- **a terminal and Python** → the pip package (2), or the unpacked folder (1) if
  you would rather install nothing;
- **only a language model** → the skill bundle (3): one file, and the model does
  the rest;
- **Ouroboros already running** → the plugin (4), which adds the whole tool set to
  an agent you are using anyway;
- **ChatGPT desktop, Codex, Cursor, VS Code, GitHub Copilot or Kiro** → the plugin
  package (5): one import brings the tools and the instruction for them together.
  Any other client that speaks MCP can start the server on its own.

Analysis is the same core in all five. What changes is who types the commands.

### 1. A folder you unpack and run

No installation at all. Python 3.10+ is the only requirement: every line of
analysis runs on the standard library. Reading laboratory PDFs is the exception —
that needs `pdfplumber`, which the pip package brings with it and this delivery
does not. Everything else works from the unpacked folder as it stands.

macOS, Linux and Windows, each checked by its own cell of the test matrix. Two
things are Unix-only and both are optional: the `bin/crossread` wrapper is a
shell script — on Windows the installed `scholion` command is the same core —
and building a genome from raw reads drives `bwa`, `samtools` and `mosdepth`
through the scripts in `src/ingest`. Every external tool is looked for before it
is used, so where one is missing the answer says which, rather than failing.

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

**If your assistant reads skills from a folder**, put it where that host looks.
One file, no registry, no account and nobody's moderation in between:

```bash
mkdir -p ~/.agents/skills/scholion
cp "$(scholion skill --path)" ~/.agents/skills/scholion/SKILL.md
```

`~/.agents/skills/` is the shared path, and three runtimes read it as they are.
The others keep their own folder and take the same single file:

| Runtime | Where it looks |
|---|---|
| OpenAI Codex | `~/.agents/skills/scholion/` — read by default |
| Gemini CLI | `~/.agents/skills/scholion/` — read by default, ahead of `~/.gemini/skills/` |
| OpenClaw | `~/.agents/skills/scholion/` — read by default, unless `OPENCLAW_STATE_DIR` has been moved off its default; `openclaw skills install` is the other way |
| Claude Code | `~/.claude/skills/scholion/` |
| Hermes Agent | `~/.hermes/skills/scholion/`, or add `~/.agents/skills` to `skills.external_dirs` in `~/.hermes/config.yaml` |

**If your tool installs skills from a repository** — `npx skills add` and the
like — the published repository carries `skills/scholion/`, which is where such
a tool looks:

```bash
npx skills add CrossRead/scholion
```

**OpenClaw** also has its own registry, and that is the supported route there:
the skill is published to ClawHub and installed with `openclaw skills install`.
The `git:` form of that command is not supported — it expects a repository whose
ROOT is the skill, and this repository is a product with a skill inside it.

The folder must be called `scholion`: the format requires the directory name and
the `name` in the file to match. Checked against each product's own
documentation on 24.08.2026 — paths move, and this table is the kind of claim
that goes stale quietly, so it carries its date.

That single file is the whole installation. It says what this is, what to run for
the usual requests, and the safety rules that come before any answer — and it
names the tool server and the in-process module, because a host that reads only
this file would otherwise never learn they exist. The long instruction and the
canon of rules are deliberately NOT copied there: they are printed out of the
installed package on demand, so there is one copy of each and it is the one that
ships. `scholion doc connecting-an-agent` describes every door, and
`scholion capabilities --json` answers the same derived from the build.

### 4. A plugin for Ouroboros

`scholion/ouroboros_tools.py` registers 35 `sch_*` tools — a body system as one
card, second opinion on a drug, lab analysis, locus lookup, polygenic scores,
longevity, goals and more.
Ouroboros discovers tool modules by scanning its own tools package, so one line
is placed there once. The line imports the installed package, which means the
tools are always the build pip installed and nothing is copied again after an
upgrade:

```bash
pip install scholion
```

```bash
echo 'from scholion.ouroboros_tools import get_tools' > <ouroboros>/ouroboros/tools/scholion_tools.py
```

Point `SCHOLION_REPO_DIR` at the directory that holds your data, in the environment
Ouroboros runs in. Do not copy the module itself: it imports its neighbours inside
the package, and a copy placed in another package cannot find them.

Self-check outside Ouroboros: `python3 -m scholion.ouroboros_tools` prints the
tool list.

### 5. A plugin package for ChatGPT, Codex, Cursor and others

**New in 0.5.3.** The folder `agent-plugin/` in the repository holds
Scholion in the Agent Plugins format. Five vendors agreed on this format in
August 2026, and ChatGPT desktop, Codex, Cursor, VS Code, GitHub Copilot and
Kiro read it. The folder holds a manifest (`plugin.json`), the skill
(`skills/scholion/`) and the description of the local tool server
(`mcp.json`). A client imports the three in one step. The instruction arrives
with the tools, and the two cannot be installed apart.

The package runs the engine and installs nothing. Install the engine once:

```bash
pipx install scholion
```

Then import the folder into the client. Its launcher finds `scholion` on the
search path, and also in `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin`
and `~/Library/Python/3.*/bin`. That matters because an application started
from the Dock on macOS does not get a terminal's search path. When no engine is
found, the launcher refuses and prints the install command. ChatGPT marks such a
plugin *Desktop only*, which is correct: the engine reads files on your own
disk, and a cloud session has none of them. The launcher is a shell script for macOS
and Linux; on Windows, use the MCP server on its own, below. For ChatGPT
desktop the steps are in `scholion doc connecting-an-agent`.

**The MCP server on its own.** A client that speaks the Model Context Protocol
but not the plugin format can start the same server directly:

```json
{ "mcpServers": { "scholion": { "command": "scholion", "args": ["mcp"] } } }
```

The server works over standard input and output. It opens no port and needs no
key. It speaks the `2026-07-28` revision of the protocol, which has no
handshake, and answers `server/discover`. Clients that open with the older
handshake (`2025-11-25`, `2025-06-18`, `2025-03-26` and `2024-11-05`) are
served under the revision they ask for. From `2025-06-18` on, thirteen tools
also return their answer as a structure: the fields their command prints with
`--json`, plus the rendered report with its qualifications.

## Updating

An update is two steps, and the second is the one that gets forgotten: install the
newer build, then ask it what the releases in between want done with the data you
already have.

**1. Install the newer build** — the command depends on how you installed:

- **pip package:** `pip install --upgrade scholion` (and `"scholion[genome]"` if
  you use that extra).
- **Unpacked folder:** download the new folder. Your data lives INSIDE the old one
  unless `SCHOLION_REPO_DIR` points elsewhere, so copy the data directories —
  `profile/`, `genome/`, `raw/`, `work/`, `archive/` — into the new folder before
  you remove the old one. Pointing `SCHOLION_REPO_DIR` at a directory outside the
  folder makes every later update a plain replacement.
- **Skill copied into a folder:** the copy does not update itself. After upgrading
  the package, `scholion skill --install` replaces it and records the build beside
  it (`scholion skill --install ~/.claude/skills/scholion` for another host's
  folder); `scholion selfcheck` fails on a copy that differs from the installed
  build until it is replaced. A copy downloaded from the published page, or added with
  `npx skills add CrossRead/scholion`, is replaced the same way it was added.
- **Ouroboros tools module:** upgrade the package, and that is all: the one line
  placed in Ouroboros's tools package imports the installed build. A copy of the
  whole module, made by an earlier version of these instructions, never imported;
  replace it with that line.
- **Ouroboros hub:** the host installs the package named in the skill's install
  specification. Once the host has updated the skill,
  `python3 -m scholion version` in that environment reports which build it runs.

**2. Ask the new build what it wants done:**

```bash
scholion version            # this build, its age, and what to recompute since your data's version
scholion version --seen     # when you have done it or read it
```

```bash
scholion recompute          # the steps those releases ask for, and the genome steps your data lacks
scholion recompute --yes    # run the ready ones, with the step, the item and the time left shown
```

`scholion version` reads the journal the package carries: for every release
between the version your data was last used with and this one, it lists what that
release asks — a command to run and when it applies, or a step to take by hand.
The local web page shows the same note under its header until you press
«Understood». A profile that has never recorded its version says so; for an update
from a known version, `scholion version --since 0.4.8` lists everything after it.

**From the product itself.** `scholion update` says whether a newer build is out
and how it installs in this environment — pip, pipx or uv, as it was installed, or
`git pull` for a source checkout; `scholion update --yes` installs it. It asks PyPI
at most once a day, sends only the package's name, and asks nothing when
`SCHOLION_OFFLINE=1` is set. Through an assistant the same is `sch_version` and
`sch_update`: the first tool answer of a session mentions a newer build once, and
`sch_update` installs nothing without `confirm=true`, which is for your own yes.
The local page's ☰ menu checks on request and offers the install after a check.
`scholion version --check` asks PyPI once, now, whatever the day's check said.

What an update leaves alone: the data directory, and any reference file you
refreshed with `scholion sources --refresh`, which stays beside your data;
`scholion sources` shows which copy answers for each file.

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
`$XDG_DATA_HOME/scholion`, on macOS `~/Library/Application Support/Scholion`, on
Windows `%USERPROFILE%\.scholion`; `SCHOLION_REPO_DIR` overrides it. Heavy directories — `raw/` and `work/` — can
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
                          pinned PGS models, interactions, marker recognition,
                          the fifteen body systems and the gene lists composed
                          for them from the GenCC export
src/scholion/i18n/        message catalogues, one file per language
src/scholion/skill/       the instruction for a language model
src/ingest/               pipelines: FASTQ→VCF, ClinVar, PGS, LongevityMap,
                          pharmacogenomics, callability, LoF scan, wearables
src/tools/                package sanitizer, hooks, release notes, publication
ouroboros_plugin/         tool registration for Ouroboros
agent-plugin/             the Agent Plugins package: manifest, skill, tool server
tests/                    the whole test suite; runs on the standard library alone
```

---

## Thanks

**Personal Genome Project (Harvard)** and its participants. Their open-consent
data is what made it possible to test this on 27 real files from eleven
providers without a single user — and almost every defect fixed in 0.4.0 was
invisible on the author's own machine. Nothing of theirs is redistributed here:
no genotypes, no findings, no identifiers, no medical records, in any form. What
travels out of that work is the behaviour of the engine and aggregate numbers.

**Synthea** ([synthetichealth/synthea](https://github.com/synthetichealth/synthea),
Apache-2.0) for the synthetic FHIR bundle the import is tested against. A parser
tested only on input written by whoever wrote the parser passes its own tests and
fails on the world.

**Genomi** ([exon-research/genomi](https://github.com/exon-research/genomi),
Apache-2.0) for the input-format detector, vendored with a way to update it and
with our one change marked in place.

Full provenance for every third-party file: `ATTRIBUTION.md`.

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
