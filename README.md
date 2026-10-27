# Scholion

**Understand changes in your health by reading the evidence together.**

Scholion connects laboratory history, a person's genome, prescriptions and wearable
measurements in one local workspace. It helps a patient see what deserves attention
and helps a clinician review the facts behind a question: what changed, which
mechanisms may be relevant, and what the available data can actually support.

Use the local web application, the command line, or an assistant connected through
MCP, a skill or an Ouroboros plugin. They share the same analysis core and selected
profile. English and Russian interfaces are included.

**Current source version: 0.7.3.** See [published releases](https://github.com/CrossRead/scholion/releases)
and [PyPI](https://pypi.org/project/scholion/) for the version available to install.
Scholion is not a medical device, does not diagnose and does not change treatment.

[English presentation](https://crossread.github.io/scholion/presentation.html)
· [Russian presentation](https://crossread.github.io/scholion/presentation.ru.html)
· [For clinicians](https://github.com/CrossRead/scholion/blob/main/docs/FOR-CLINICIANS.md)
· [Changes and update instructions](https://github.com/CrossRead/scholion/blob/main/CHANGELOG.md)

## Sixty seconds: try the demo

Start with a fictional person. No genome, medical record or Scholion account is
required:

```bash
pip install scholion
scholion init --demo
scholion overview
scholion limits
scholion phenoage --panels
```

To open the same profile in the local web application:

```bash
scholion serve
```

Open the address printed in the terminal; the default is
[http://127.0.0.1:1521](http://127.0.0.1:1521). The demo includes incomplete data so
that you can also see how an unavailable calculation is explained.

Use an empty data directory for your first demo. When you add a real observation
to a demo profile, Scholion removes the marked synthetic history before saving
your data; fictional and real records must not be mixed. This does not erase an
ordinary real profile. `scholion demo` is the alternative that builds a demo in a
separate directory and prints how to open it.

## Why

A laboratory result answers one question at one moment. A useful review also asks
how it relates to earlier results, the treatment timeline, known genetic findings
and everyday observations. Those records often live in different files and use
different dates, units and names.

Scholion brings them into a source-labelled history and organises the review by
body system. Its core computes facts, comparisons and qualified findings without a
language model. An optional assistant can explain those results and help prepare
questions for the treating clinician.

## What you can do

| For a patient | For a clinician |
|---|---|
| See which body systems deserve attention and follow annual direction | Review dated values, meaningful changes and their supporting records |
| Keep manual measurements and wearable observations in one history | Compare applicable genetic findings with the person's laboratory results |
| Record symptoms, everyday function and tolerability alongside measurements | Distinguish reported response, measured change and an unproven treatment explanation |
| Understand the purpose and limits of a clinical estimate | Inspect the method, required inputs, applicability and original sources |
| Prepare a focused visit brief | Open the relevant systems and gene panels without a full catalogue dump |
| Retain access through a local application or an assistant | Use separate containers for different people, with explicit selection |

### Today and body systems

The first screen combines a human figure, system-level attention cards and
phenotype dynamics. Annual direction remains visible; forming changes and dated
reports of response have their own context. A normal recent result does not
trigger a request for extra tests merely because there are too few points for a
trend.

The fifteen body systems retain their laboratory and genetic views; Fitness adds
wearable context. A system brings together current measurements, their history,
relevant read variants and recorded prescriptions. Laboratory status and genetic
reading coverage remain separate. Genetics is not added to the system's 0–100
laboratory score.

Manual and wearable weight use one source-labelled timeline, including derived
BMI. Completed prescriptions stay in treatment history. The detailed Labs,
Treatment, Genome and Lifestyle screens remain available behind the summary.

### Genetics: function, actual reading, then interpretation

A gene card starts with what is known about the gene, followed by the person's
actual genotype and reading quality, the known influence of the specific variant,
and applicable comparisons with laboratory data. Confidence and source details
can be expanded.

The reference contains **1469 genes across the fifteen systems** in the main
GenCC catalogue, with sourced English and Russian function descriptions.
**525 distinct genes** also appear in thematic panels; the sets overlap. A
separately labelled HHEX–IDE region is not counted as another gene. These are
reference sizes, not a claim that every base of those genes was read in a person.
Each thematic gene card can also read the gene's available variants and coverage
on request, even when no individual catalogue position has been selected. Other
regional variants stay folded. The same reading is available through
`scholion genome --gene SYMBOL` and the `sch_genome_lookup` assistant tool.

Thematic views include vitamins and micronutrients, amino-acid pathways, liver and
bile, kidneys and urate, cardiovascular biology and hemostasis, bone and minerals,
methylation, steroid synthesis, thyroid biology and glucose metabolism. Research
associations involving neurotransmitters and stress are separate from clinical
neurogenetic disease reference. Existing body systems and radar axes are retained.

Three different kinds of evidence remain distinct:

- **Scholion A–E** qualifies a catalogue interpretation and its support. Limited
  confidence does not hide a sourced gene function or an existing interpretation.
- **GenCC** describes gene–disease validity, preserving submitters, inheritance,
  source dates and disagreeing assertions.
- **ClinVar** describes a specific variant's classification and review status;
  the ACMG secondary-findings layer has its own versioned reporting rules.

Known gene function alone does not establish a personal variant effect. The
curated system layer contains **221 authored positions**; the broader coordinate
reference and literal SNP readings do not inherit an effect allele from it.
Newly verified SNPs can show the actual reading in GRCh37 or GRCh38 without
inventing a risk direction. Indels, repeats, unresolved phase and difficult loci
retain their specific limitations.

**Findings distinguish inheritance from diagnosis.** Cards show the actual
zygosity, sourced inheritance and personal interpretation separately from the
ClinVar classification. A single heterozygous finding under a supported
recessive model is shown as carrier context. Multiple variants with unknown
phase, mixed inheritance and incomplete readings remain explicitly unresolved.
Known gene biology appears before these qualifications.

**A consumer array is read directly** through `scholion array`. A locus can be
called, a no-call, or *not on this chip*. A missing position is not a reference
homozygote. ClinVar screening, ACMG secondary findings and PGS paths that the
input cannot support refuse with a reason.

**Pharmacogenetics** uses available variant or prepared diplotype evidence and
keeps the two distinct. Prepared PyPGx/PharmCAT results can supply star alleles,
phase and copy-number context where measured; a single SNP cannot stand in for
that work. Drug-specific CPIC support is not turned into a general prescription.

**Polygenic scores** retain model identity, genome build, coverage and reference
calibration. A confirmed percentile is a position in a reference population,
not a probability of disease. Unverified saved values remain visible with their
reason and a recalculation recommendation until a successful replacement is saved.
PGS model weights are downloaded when required, not bundled with the project.

**Longevity** separates sourced variant associations from the literature
catalogue. APOE's paired sites, linked FOXO3 signals and population-dependent
findings are not counted as independent benefits or a forecast of years of life.

### Clinical estimates

A compact block below the human figure links to a detailed **Clinical estimates**
panel. It brings together FIB-4 and PhenoAge, each with its own scale, dates,
inputs, applicability and method sources.

These results are not combined into one health score. Missing inputs are shown
explicitly and are not silently borrowed from unrelated blood draws. No clinical
questionnaire is required for this panel.

### Laboratory and wearable history

Import laboratory PDFs, delimited tables or FHIR R4 bundles; add individual values
manually when needed. Recognised PDF layouts are primarily Russian laboratory
forms; support depends on the source layout. CSV and explicit values can carry
results from other languages.

Compound documents retain each recognised laboratory section's own date and
source. FHIR imports preserve specimen, assay method, units and resource identity;
vital signs and blood-pressure components enter the shared metrics history.
An unrecognised or ambiguous result is reported rather than guessed into a known
series. Preview, reconciliation and provenance help distinguish a missing record
from a file that has not been read successfully.

Garmin and WHOOP imports provide activity, body composition and sleep observations.
Available per-night intervals support dated comparisons rather than comparisons
based only on monthly averages.

**Lumiflex application PDFs** can be previewed and explicitly imported. Printed
statistics, recorded food/activity events and approximate readings from supported
chart segments remain distinct. They do not become fasting laboratory glucose or
HbA1c. Sleep comparisons require usable time intervals and timezone information;
retrospective agreement does not prove causation. Cloud and spreadsheet exports
are not part of this integration.

### A short brief for the appointment

Open **Visit sheet → Choose the visit focus**. Select body systems, relevant
reference panels and the question for that appointment. The compact view brings
together dated measurements, qualified insights, relevant recorded prescriptions
and actual genetic readings without listing the entire reference catalogue.
Important safety warnings are retained outside a narrow selection.

The full recorded view is still available. The same selection is accessible from
the command line and assistant tools:

```bash
scholion overview --visit-sheet --compact --visit-system lipids --visit-system glucose
scholion overview --visit-sheet --compact --visit-panel methylation
```

Selecting the focus does not run a new genome scan. A selected reference panel
shows the supported catalogue readings; it is not a complete clinical gene test.

## What makes this different

**One result across interfaces.** The web application, CLI and assistant tools
call the same core. `scholion capabilities --json` describes the available
interfaces from the current build; [connecting an assistant](https://github.com/CrossRead/scholion/blob/main/docs/CONNECTING-AN-AGENT.md)
explains how to use them.

**Sources travel with the result.** A measurement retains its date, units and
origin. A genetic interpretation retains its variant, relevant reading quality,
reference version, confidence and source. Open `scholion provenance` to inspect
how stored laboratory observations trace back to their inputs.

**Absence is qualified.** An unread position is not a reference genotype, and no
findings in a partially read gene do not exclude disease. `scholion limits` and
`scholion genome-status` explain what the connected input can support.

**Changes in conclusions are reviewable.** Explicitly save a review and compare it
later. Changed or withdrawn interpretations retain the facts, knowledge sources
and rule versions that explain the difference.

**Flags have to distinguish.** A basic check asks: what fraction of objects did the flag hit?
A flag that fires almost everywhere needs a correction to its rule, not a more
persuasive explanation. The source tests include `tests/test_flag_prevalence.py`.

## Boundaries

- Scholion does not diagnose, prescribe, stop treatment or change doses. A
  proposed mechanism or association remains a question for clinical review.
- A reference gene list does not establish complete gene coverage. Short-read
  pipelines here do not provide a general CNV, structural-variant, repeat, HLA or
  mitochondrial disease analysis. An unclassified variant is not assigned a new
  ACMG/AMP classification by the assistant.
- Most PGS models are based largely on European cohorts. An unsuitable reference,
  unknown calibration or mismatched coordinates prevents a confirmed percentile.
  A literature association is not a personal risk estimate.
- A change after starting a treatment, or agreement between genetics and labs,
  does not prove causation. A report of improved symptoms remains the person's
  report; a measured trend is described separately.
- Missing trend points are not themselves an indication for more tests. Any
  monitoring recommendation needs its own clinical basis.
- Clinical estimates have different outcomes, time horizons and eligibility.
  They do not substitute for a clinical assessment.

See [the assistant rules](https://github.com/CrossRead/scholion/blob/main/ASSISTANT-RULES.md), [the disclaimer](https://github.com/CrossRead/scholion/blob/main/DISCLAIMER.md) and
[the clinician reference](https://github.com/CrossRead/scholion/blob/main/docs/FOR-CLINICIANS-DETAILS.md).

## Bring what you have

You can start below the genome layer and add other sources later.

| You have | Entry point | What it adds |
|---|---|---|
| Nothing at all | `scholion init --demo` | A synthetic profile to explore |
| A few values | `scholion add-lab "Ferritin" 2026-08 41 --unit ng/mL` | A dated, source-labelled laboratory series |
| A laboratory table | `scholion import-labs panel.csv` | CSV/TSV/TXT observations |
| Supported laboratory PDFs | `scholion ingest-labs "<folder>"` | Recognised results with dates and printed ranges |
| A FHIR bundle | `scholion import-fhir bundle.json` | Code-matched results and supported vital signs |
| Garmin or WHOOP exports | `scholion ingest-wearable "<folder>"` | Activity, sleep and body metrics |
| Prescriptions | `scholion add-med "name" --dose "…"` | A recorded regimen for comparison and monitoring review |
| A VCF, BAM or consumer array | [Genome preparation](https://github.com/CrossRead/scholion/blob/main/docs/PREPARING-THE-GENOME.md) | The analyses supported by that input and its preparation |
| A Lumiflex application PDF | `scholion ingest-studies "<folder>" --dry-run` | Preview and explicit import of a sensor report |

## Five ways to install

Python 3.10+ is required for the engine. macOS, Linux and Windows are supported;
external genome tools and host-specific plugin launchers have their own platform
requirements. The analysis core uses the standard library; the pip package also
installs `pdfplumber` for PDF extraction and `tzdata` on Windows. `pysam` is an
optional acceleration for VCF access.

### 1. A folder you unpack and run

Download the source distribution or clone the repository. The wrapper locates its
own source tree:

```bash
./bin/crossread --help
SCHOLION_PROFILE_DIR=demo/profile ./bin/crossread overview
```

The folder's PDF workflows also need `pdfplumber`. The pip installation below
resolves this dependency automatically. On Windows, use the installed command or
follow the source setup in [development documentation](https://github.com/CrossRead/scholion/blob/main/docs/DEVELOPMENT.md).

### 2. A pip package

```bash
pip install scholion
scholion init
scholion serve
```

Optional accelerated genome access:

```bash
pip install "scholion[genome]"
```

`scholion` and `crossread` are equivalent command names. External bioinformatics
tools are separate from Python packages:

```bash
scholion tools
```

The result explains which tools are available and which an operation requires.
Installation is explicit; `scholion tools --install` is the confirmation to
install the supported base set. The application does not silently install a
missing PDF library or request administrator rights.

### 3. A skill for a language model

Use the [short skill entry](https://crossread.github.io/scholion/scholion-skill.md)
or the [complete skill bundle](https://crossread.github.io/scholion/scholion.skill).
With the engine installed, obtain the same instruction locally:

```bash
scholion skill
scholion skill --full
scholion skill --rules
scholion skill --path
```

A host that reads skill folders can use `scholion skill --install`, or a named
host directory such as `scholion skill --install ~/.claude/skills/scholion`.
The short entry loads the detailed instruction and safety rules when needed.
A skill does not itself grant disk or command access; what the assistant can run
depends on its host. A host without execution access can guide you through local
commands.

### 4. A plugin for Ouroboros

The Hub skill provides a profile connection flow and the embedded **Scholion** web
interface on the Widgets page. The visual panel and assistant tools use the same
selected profile. The host's own model setup is separate from the local engine.
See [the connection guide](https://github.com/CrossRead/scholion/blob/main/docs/CONNECTING-AN-AGENT.md#the-embedded-ouroboros-interface)
and the [plugin setup guide](https://github.com/CrossRead/scholion/blob/main/ouroboros_plugin/README.md).

For a classic checkout, `scholion/ouroboros_tools.py` registers 40 `sch_*` tools. Install
the engine in the interpreter used by Ouroboros, then place this import shim in
its tools package, replacing `<ouroboros>` with the checkout path:

```bash
pip install scholion
```

```bash
echo 'from scholion.ouroboros_tools import get_tools' > <ouroboros>/ouroboros/tools/scholion_tools.py
```

Point `SCHOLION_REPO_DIR` at the data directory in the host environment. Keep the
import shim rather than copying `ouroboros_tools.py`: it must import its neighbours
from the installed package. Upgrade that package in the same interpreter and
restart the host to load the new engine.

### 5. A plugin package for ChatGPT, Codex, Cursor and others

The repository's `agent-plugin/` folder contains an Agent Plugins manifest, the
skill and a local MCP launcher. Import it into a compatible desktop host after
installing the engine. The shell launcher is for macOS/Linux; on Windows a client
can start the MCP server directly.

For an MCP client, use its local server configuration:

```json
{ "mcpServers": { "scholion": { "command": "scholion", "args": ["mcp"] } } }
```

Use an absolute executable path if the host cannot find the installed command.
MCP uses standard input/output and does not need a Scholion API key or an open
network port. The host's own account or model subscription is separate.
[Connection instructions](https://github.com/CrossRead/scholion/blob/main/docs/CONNECTING-AN-AGENT.md) and
`scholion capabilities --json` describe the interfaces of the installed build.

## Updating and existing data

Upgrade the engine in the same environment that runs it:

```bash
pip install --upgrade scholion
scholion version
scholion recompute
```

`scholion recompute` first shows the applicable operations and required inputs.
Use `scholion recompute --yes` only after reviewing that plan. A version change
alone does not require whole-genome preparation or a PGS rerun. Failed or stopped
replacement work keeps the previous report; an unverified result stays labelled
until a valid replacement is saved.

The 0.7.2 reference descriptions and clinical estimates are available when read.
New unread catalogue SNPs may need an explicit `genotype-sites` operation with the
required BAM and reference. Re-import affected compound PDFs or FHIR bundles
through preview if you need the repaired parsing. Old stored values are retained;
a previously misclassified series is not silently removed from history. Re-import
wearable sleep only where the older record lacks intervals needed for a comparison.
The [release journal](https://github.com/CrossRead/scholion/blob/main/CHANGELOG.md) gives the conditions for each update.

When using an unpacked folder, keep the data directory outside the replaceable
application folder or preserve `profile/`, `genome/`, `raw/`, `work/` and `archive/`
before replacing it. `SCHOLION_REPO_DIR` selects the data directory.

After an engine upgrade, replace a separately copied skill with
`scholion skill --install` and restart the assistant host. Hub and Agent Plugins
packages are separate deliveries; check both the host package and engine version.

`scholion update` checks available versions and explains the installation method;
`scholion update --yes` requires your explicit confirmation to install. The same
operation through a model tool requires confirmation as well.

### What the installed package contains

The wheel includes the local web app, CLI, MCP server, shared reference knowledge,
PDF readers, wearable readers and the application operations for supported
recalculation workflows. An installed recalculation still requires the actual
input files, appropriate external tools and valid model/reference information.
It must not rely on helpers found only in a developer's private checkout.

Building a genome from FASTQ, broad preparation pipelines and release tooling
belong to the source toolkit in `src/ingest/` and `src/tools/`. See
[preparing the genome](https://github.com/CrossRead/scholion/blob/main/docs/PREPARING-THE-GENOME.md) for the operation you need.
A VCF alone does not supply alignment depth or reference-homozygous scoring calls
that it does not contain.

### CLI exit codes

`0` means the command completed, including a documented refusal or unavailable
result; inspect the result's status. `1` means an operation failed, `2` invalid
arguments, `3` a profile schema newer than the build, `4` a busy profile, `5` an
unreadable source configuration and `6` a container-selection error. A multi-file
import can complete earlier files before a later failure; inspect its report.
An exit code never establishes a medical conclusion.

## Privacy and data location

Records are read from your data directory rather than embedded in code. By
default it is `~/Library/Application Support/Scholion` on macOS,
`%USERPROFILE%\.scholion` on Windows, and `$XDG_DATA_HOME/scholion` or the platform's
fallback on Linux. `SCHOLION_REPO_DIR` overrides it. Heavy inputs can be located
elsewhere through the source configuration.

One container holds one person. Clinicians can keep several containers with
explicit selection; Personal and Visit modes are not patient switches. Agent
answers carry the selected technical container ID. Export and erasure are human
operations. See [container lifecycle](https://github.com/CrossRead/scholion/blob/main/docs/CONTAINER-LIFECYCLE.md).

Analysis runs locally without a language model. The web server binds to loopback.
Reference lookups and downloads have narrower, explicit network behaviour:

- Drug lookups use `rxnav.nlm.nih.gov`, `mor.nlm.nih.gov` and `api.cpicpgx.org`;
  translating a requested Russian drug name uses `api.mymemory.translated.net`.
  A drug name can itself reveal personal information.
- Public rsID/reference queries can use `rest.ensembl.org` or
  `grch37.rest.ensembl.org`. PGS discovery uses `www.pgscatalog.org`; consented
  downloads of pinned public weights use `ftp.ebi.ac.uk`. These requests do not
  send a person's genotype or computed score.
- The version check can contact `pypi.org` with the package name, at most once a
  day unless explicitly requested again. Installing an update requires permission.
- Explicit method links include `doi.org` and `www8.garmin.com`.
  Laboratory reference entries also link to LOINC. Opening a source link is
  separate from local calculation.
- Source preparation tools can download public inputs from NCBI, Ensembl, UCSC,
  HAGR, GitHub and package registries. The Assistant screen inventories application
  and preparation hosts separately.

`SCHOLION_OFFLINE=1` disables Scholion's outbound requests. **It does not control
an assistant host:** if the host uses a remote model, tool answers containing
medical values, genotypes, dates and a technical container ID may reach that
provider. Review the host's privacy policy before connecting real data.

[PRIVACY.md](https://github.com/CrossRead/scholion/blob/main/PRIVACY.md) describes containers, journals, export, erasure and copies
outside the application. Personal data is excluded from the public source and
package by path checks, content checks and the sanitizer.

## Language

English is the default. Select Russian in the web application or run:

```bash
scholion overview --lang ru
```

`SCHOLION_LANG=ru` selects Russian for command output. Input recognition dictionaries
support the laboratory names and forms they describe independently of the output
language. Source data and quotations retain their provenance.

## Development and provenance

The public contract is checked for CLI/web/tool parity and compatibility. The
release gates test synthetic fixtures with networking disabled, validate the
knowledge and documentation, and audit the sanitized package. Real input-format
checks use a separate consented corpus; personal files and findings do not ship.

[Development guide](https://github.com/CrossRead/scholion/blob/main/docs/DEVELOPMENT.md)
· [Versioning](https://github.com/CrossRead/scholion/blob/main/docs/VERSIONING.md)
· [Contributing](https://github.com/CrossRead/scholion/blob/main/CONTRIBUTING.md)
· [Security reporting](https://github.com/CrossRead/scholion/blob/main/SECURITY.md)
· [Threat model](https://github.com/CrossRead/scholion/blob/main/THREAT_MODEL.md)

Thanks to the **Personal Genome Project** participants for open-consent format
validation, **Synthea** for synthetic FHIR input and **Genomi** for the vendored
input detector. Sources, licences and required citations are recorded in
[ATTRIBUTION.md](https://github.com/CrossRead/scholion/blob/main/ATTRIBUTION.md).

## Licences

- Code: [Apache-2.0](https://github.com/CrossRead/scholion/blob/main/LICENSE).
- Curated knowledge: [CC BY 4.0](https://github.com/CrossRead/scholion/blob/main/LICENSE-DATA), with source-specific notices in
  [NOTICE](https://github.com/CrossRead/scholion/blob/main/NOTICE) and provenance in [ATTRIBUTION.md](https://github.com/CrossRead/scholion/blob/main/ATTRIBUTION.md).
- PGS weights and other materials with incompatible redistribution terms are
  not bundled. Runtime availability does not change their source licences.
- Purpose and limitations: [DISCLAIMER.md](https://github.com/CrossRead/scholion/blob/main/DISCLAIMER.md).

## Contact

[scholion.dev@proton.me](mailto:scholion.dev@proton.me)

Use [GitHub Issues](https://github.com/CrossRead/scholion/issues) for reproducible
problems or suggestions. Do not post personal health data, sample identifiers,
credentials or medical attachments. Describe the input format and behaviour;
`scholion redact` can help prepare a structural example but still requires your
review before sharing.
