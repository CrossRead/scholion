# Changelog

Semantic versions with the date in the heading: `v0.2.0 — 20.08.2026`. The number
is the unique key of an entry, the date is informative: a working day may produce
several versions or none. Rules for choosing a number — `docs/VERSIONING.md`.

**The numbering starts here.** This journal opens at the first public release. The
development that produced it ran under its own numbering, up to `2.24.0`, and that
numbering was retired at publication: it measured how much had been built, and a
version number is meant to promise something else — that a person holding the
previous version knows what moving to this one does to their data and their
commands. Nobody outside had run any of those versions, so there was nothing to
promise. They are kept privately, in `CHANGELOG.pre-0.1.0.md`, and their tags live
in a namespace of their own (`pre-0.1.0/v2.24.0`), so that if the published
numbering ever reaches `2.24.0` it is a different tag on a different commit and
cannot be mistaken for one of them.

**How to read it.** The main sections of an entry are not the file list but three
curated ones: **what this changes in the conclusions**, **what is retracted**,
**what needs recomputing**. The file list at the bottom is generated from git
(`python3 src/tools/release_notes.py`). A **series break** is marked separately —
a change to `src/scholion/knowledge/` that alters the result on unchanged input.
Values from before and after such a change cannot go on the same chart without a
note.

**What is not here.** Personal data and one person's findings: no genotypes, no
lab values, no dates of anyone's tests. This journal records what changed in the
**system**, not what was found in somebody.

---

<!-- NEW ENTRIES GO HERE -->

## v0.3.3 — 19.08.2026

The release where the project explains itself twice over: to a visitor, and
to a contributor. No knowledge changes, no series break; the analysis answers
exactly what v0.3.2 answered.

### The presentation catches up with the product, and gets a front door

`share/presentation.html` and `share/presentation.ru.html` are rebuilt
against the living 0.3.2 — checked by running the product, not by memory:
553 tests, 48 commands, the Assistant tab's self-audit at 39 files / 18,194
lines (read from `_audit_core()` directly, not off a screenshot), six
outbound hosts by name. All screenshots are fresh, a tenth was added (the
Guide tab), and the Russian edition carries REAL Russian screenshots for the
first time — the apologetic note about English ones is gone. An Installation
section now mirrors the README's four ways in, and says plainly that the
genome-preparation workshop lives in the source tree only. Two wordings were
corrected on the way: «not one external dependency» (pdfplumber is required)
and the locality card now names the translation services next to the
reference APIs, because the application's own self-report does.

The pages get an entry point: `share/index.html` redirects to the
presentation (with a manual fallback naming both languages) and
`share/.nojekyll` keeps GitHub Pages from mangling the folder. The publish
gate carries both into the built package's `docs/`, so
`crossread.github.io/scholion` starts answering at the root instead of 404.
The screenshot allowlist in `make_shareable.py` was replaced wholesale —
twenty hashes, ten per language — following the file's own precedent. One
accepted line joins the language baseline: the «Russian» link label on the
entry page is a language switch, which is the one place a language's own
name belongs.

### The conventions get a file, and the split gets a gate

`docs/DEVELOPMENT.md` — the architecture and the development rules, written
for an outside contributor to assemble a structured commit without reading
the tests first: the layer map, the engine-package rules, the four-face
tick, language and i18n discipline, the gate order, what a commit message
carries, and short checklists for the common additions. An early audit cited
a DEVELOPMENT.md that did not exist; the citation is now true.

`tests/test_engine_stays_split.py` holds the refactoring's shape the way the
four faces are held — as a red test, not a memory: the facade defines
nothing; domain imports stay acyclic at the top level (the one sanctioned
back edge is lazy inside a function, which is exactly what makes it
sanctioned); every module has a size budget recorded in the test, and
exceeding it is a same-commit decision — split, or raise the budget with a
reason about the capability; the facade may not shrink below the hundred
names the flat file exposed. Seven mutations were tried against the gate;
seven came back red.

## v0.3.2 — 18.08.2026

A refactoring release: not one answer changes on unchanged input. The full
suite, the compatibility snapshots, both language catalogues and every command
are byte-for-byte the same claims as v0.3.1 — that sameness IS the release
gate, recorded here as the thing that was checked rather than assumed.

### engine.py becomes a package of eight domain modules

The 2800-line flat file — five domains that had grown into one another for a
year — is now `engine/`: `_helpers`, `labs`, `pgx`, `genomics`, `goals`,
`lifestyle`, `sources`, `profile_view`, with `__init__.py` as a facade that
re-exports EVERY name, private ones included, at the address the tree has
always used. Six consumers (`__init__`, `cli`, `server`, `ouroboros_tools`,
`assistant`, `limits`) and the tests needed zero edits: five of the six always
called `engine.<name>(...)`, and the sixth's explicit imports resolve through
the facade identically. Two module names differ from the auditor's proposal
for a reason recorded in the plan: `genomics` (a `genome.py` already exists —
the VCF backend) and `sources` (a `provenance.py` already exists and means the
reverse check; `engine.provenance()` keeps its public name, only its file
changed).

The mechanical work was governed by a call-graph analysis the original audit
did not do, and the graph had teeth: two cycles (labs↔pgx and lifestyle↔pgx).
They were broken by MOVING two leaves into `_helpers` — `_active_names_by_class`
and `_brief_num` invoke nothing and belong to everyone — and by ONE deliberate
lazy import: `pgx._dose_context` reaches for `lifestyle._brief_life` inside
the function body, the same pattern the file already used for `drugsource`.
Everything else imports one way, top-level, two dots up for the package
neighbours exactly as the plan required.

The extraction tool refused to write a module with an unresolved name, and
that refusal caught three edges no analysis had listed: `DISCLAIMER` is called
by `goals` and `genomics` (the call-graph pass had skipped the two constant-
like functions), and `_OPS` — the comparison-operator table — is shared by
`_helpers._match_count` and `labs._eval_condition`. All three now live in
`_helpers`, imported by name where used. The audit's other prediction was
confirmed the hard way: `_WATCHLIST` sits in `profile_view`'s line range and
belongs to `lifestyle.second_opinion` — cutting by line ranges would have
shipped a NameError that only fires when somebody asks for a second opinion.

One collision existed and is now tested: `lifestyle` is both a submodule and a
function. The facade binds the function last, and a test-adjacent check
confirms `engine.lifestyle` stays callable even after a direct submodule
import.

### Removed: the monitoring list nobody calls

`_monitoring_for` returned monitoring hints for eight drug classes hard-coded
in the source, through sixteen `monitor.*` keys in both catalogues. The only
place needing such hints — `check_new_prescription` — has long read them from
`knowledge/drug_lab_monitoring.json` via `core.drug_lab_monitoring()`. The
code list lost that argument and stayed anyway; found by the refactoring
audit, deleted with its keys (catalogues stay identical: 1334 = 1334).

### What was checked, where

`run_tests.sh` end to end in the repository: 553 tests, 48 commands, 20
snapshots, docs and rules in sync, the language remainder unchanged at 352
(the seven accepted places that lived in `engine.py` moved to their new
addresses; the baseline records the move, not growth). And — because a check
that agrees only with the repository it was written in has now cost this
project five times — the artefact itself: a wheel built from this tree,
installed into a clean environment, imports the facade, resolves the private
names the tests use, and answers `scholion capabilities` and
`scholion second-opinion` from the installed package. All nine `engine/`
files travel in the wheel.

## v0.3.1 — 18.08.2026

_MINOR by the letter of `docs/VERSIONING.md`: `lab_markers.json` changes what a
value means on unchanged input — an HbA1c that used to be refused is now stored.
Nothing already stored moves; a refusal has no stored value to move._

_Backlog 36 and 41, and the answer to both was mostly «check before you build»._

### What this changes in the conclusions

**HbA1c in mmol/mol is read now instead of refused.** The IFCC scale and the
NGSP scale are related by the master equation `% = 0.09148 × mmol/mol + 2.152` —
affine, not proportional — and the gateway had one law: a multiplier per spelling.
Refusing was the honest answer while that was the only tool, and it was also a
refusal of the commonest unit on a European report. A person met «unknown unit»
about a unit that plainly exists, went looking for a typo, found none, and typed
the number bare — the outcome the refusal existed to prevent.

The gateway carries a second law: `convert_affine`, with the constants and the
NGSP citation beside them. 48 mmol/mol comes out as 6.5 %, which is what the
published table says, and the test checks the table rather than the arithmetic.

**The corridor travels with the value, by the same law.** A range printed in
mmol/mol beside a value converted to % is the mg/dL-glucose defect one level
down, and with an affine law a bound multiplied instead of transformed lands
somewhere else entirely. Both ends now go through the conversion, and a test
adds a value inside its own corridor and checks it is not flagged.

**Nothing converts on its own any more.** The arithmetic used to live in the
caller. That was safe with one law and dangerous with two: a caller reading only
`factor` would apply 1.0 to 48 mmol/mol and store 48 % — not an error, a
catastrophic diabetic reading, silently. `core.convert_to_canonical` is the one
place the law lives, both entry points go through it, and a test refuses any
module that multiplies by the gateway's factor itself. Verified by putting the
multiplication back and watching two tests go red.

**Lp(a) in mg/dL stays refused,** and that is what keeps the refusal path
honest. Mass and molar concentration there depend on the size of the person's
apo(a) isoform: no factor, no formula, and a second law is not a licence to
convert everything.

### What was already done, and is now closed by checking rather than by memory

**Task 41 — the test matrix — was already in the tree.** `tests.yml` runs
ubuntu × macOS against Python 3.10, 3.11, 3.12 and 3.13 with `fail-fast: false`,
plus a Linux job with `TMPDIR` behind a symlink (the macOS `/var` →
`/private/var` shape, reproduced where it is cheap), plus the package job. The
backlog line said «not started» as of 16.08 and was two days stale. It is closed
with what proves it: the file, the cells it declares, and a green run on GitHub.

**Task 36 was five-sevenths done and the entry knew it.** The five factor
conversions — free T4, free T3, TIBC, zinc, DHT — shipped earlier, each with its
molar mass written next to the constant. What remained were the two the entry
itself called hard, and they turned out to be one piece of work and one correct
refusal, which is the paragraph above.

### The frame: one capability, four faces, one tick

`contract.py` opens by naming three faces of one core and describes the defect it
was written after — «Second opinion», the summary and the health index living in
the web tabs alone for half a year, because a capability added quickly to one
face stays there. It closed the first two faces against each other and left the
others open, and both drifted.

There are four doors, not two, and they are not equal:

| | who walks through it | who notices it is shut |
|---|---|---|
| web interface | a person clicking | the person — a missing tab is visible |
| command line | a MODEL with a shell, first; a person typing, second | the person — the model works from what it was told exists |
| plugin tool list | a model deciding what it can call | **nobody** |
| the model's instruction | a model deciding what exists at all | **nobody** |

A person can see that something is absent and go looking. A model cannot see a
capability it was never shown: it answers from what it has instead of saying it
cannot, and that answer looks exactly like a good one. So the two model-facing
doors now carry the higher bar — an omission must be written down with a reason,
and the reason must be about the capability rather than about the week.

**Measured before the guard was written**, which is the only reason to trust that
it was needed: the plugin lacked nine capabilities (see above), and the shared
instruction named 40 commands of 47. Three of the seven absent were real —
`acmg`, `goal-suggest`, `lipid-genetics` — and two of the three had been added
that same week. Each of those two drifts had been found by somebody noticing
months later, not by a test.

`check_all_faces()` answers for all four at once, and `tests/test_all_faces_move_
together.py` prints them in one message. That is deliberate: the question an
author has after adding something is «what did I forget», and four separate red
runs answer it a quarter at a time — a run per face, a fix per run, and the
fourth found an hour later.

The fourth face is CHECKED and not generated. The command block in the
instruction carries curated invocations — `genome rs0000000`, `phenoage
--panels`, `tools --set NAME` — worth more to a reader than a line per bare
command, and a generator would flatten them. What must not happen is silent
absence, and that is what is now impossible.

A fifth check went in beside them, of a different kind: every phrase the
interface reaches for exists in **both** catalogues. A missing key does not
crash — the page prints `⟦web.some.key⟧` where a sentence should be, in front of
the reader and nowhere else, in only the language that lacks it, so it is
invisible to whoever wrote the other one.

**The guard's first catch was its author.** `init` was excused as «not named in
the instruction» and is named there; the excuse was wrong and the check said so
on the first run. Its second was a stale sentence in both instruction editions
telling a model that HbA1c in mmol/mol is refused — true until earlier the same
day, and exactly the sort of statement that outlives the thing it describes.

**The command line was misnamed in the first draft of this table.** It said «a
person typing, every script» — and the owner corrected it: the CLI's
completeness is noticed not only by a person but by the AI agent that works
with Scholion as a tool, and the CLI is for that agent first. A person can
browse `--help`; a model with a shell runs what its instruction names and
nothing else — the instruction is the discovery mechanism of the main surface.
That correction forced two things that were not in the plan.

The first is a second route to the truth: `scholion capabilities` (also
`--json`) — a manifest GENERATED from the command parser and the entry-point
map, listing every command, what it does, whether it writes, and which faces
carry it. The instruction now ends its command list with the rule «if this
list and the build disagree, believe the build». A curated instruction can go
stale — this release found it stale twice — so the model gets one door that
cannot: the build describing itself.

The second the new gate class found on its own first run
(`TestTheManifestCannotFallBehindTheBuild`): the claim «no tool handed to a
model writes», printed in the writes heading and asserted from a hand-written
list, had been false from the beginning — `sch_ingest_labs` is a tool and
writes `labs.json`. The earlier test happened not to contain the one command
that broke its premise: a check agreeing with its author, the same class that
has cost this project four times. The fix is a distinction, not a deletion:
WRITES splits into AUTHORS (creates values from nobody's document — `add-lab`,
`add-med`, `demo`… — never a model's tool) and TRANSCRIBES (moves the person's
own documents into the profile — `ingest-labs`, `ingest-garmin`… — a model may
hold these, because they invent nothing). The manifest marks every write with
its kind, the gate holds AUTHORS out of the tool list by name, and every
transcriber must be recorded as admitted or refused — silence is the one state
the contract no longer allows.

**And the manifest's own reader carried the disease it was built against.**
`instruction_text()` read the instruction at its source-repository address
alone, passed every test in the repository it was written in, and failed inside
the built package on the owner's publish run — the package does not carry
`share/`, it carries the identical copy beside the module. A check agreeing
with the single environment its author sat in: the same class, caught by the
publish gate doing exactly what it is for — nothing was committed or pushed to
the public repository. The function now knows both homes and says so when it
finds neither.

### The third face of the core had fallen behind, and nothing was watching it

`contract.py` opens by naming three faces of one core — the web interface, the
CLI and the Ouroboros plugin — and by describing the defect it was written after:
«Second opinion», the summary and the health index by body system lived only in
the web tabs for half a year, because a capability added quickly to one face
stays there. The map it enforces covered two faces of the three.

So the plugin drifted exactly the way the web had. Nine capabilities had a route
and a command and no tool: the overview, the second opinion, the radar, the
focus, the lifestyle brief, the ACMG scan, the two added this week — and
`limits`, which is the answer to «what can this data NOT tell you».

`limits` is the one that matters. The reader who needs it most is a language
model about to make a negative statement, and it was the one face that could not
ask for it. A missing tool is worse than a missing tab for a reason worth
stating: a person looking at a page can see that something is absent. A model
cannot see a capability it was never shown — it answers from what it has instead
of saying it cannot.

Fourteen tools became twenty-three, each checked by calling it. `PLUGIN` maps
command → tool and `NO_PLUGIN` records a reason for every command that has none,
and the bar there is deliberately higher than for the web. Every write command is
in that list marked «a write», with a test that keeps it so: the canon handed to
a model says it does not change the profile, and the absence of a write tool is
what makes that more than a promise.

### The seven small things the stranger's run left behind

None of them changes an answer; all seven were things a reader had to work
around.

**Labs listed twenty-seven markers alphabetically under a heading that said
«8 out of range of 27».** The eight the sentence was about were scattered among
the nineteen it was not, and counting them by eye was work the page could have
done. Out of range first, furthest outside its corridor leading, then a divider
and the rest in the order they had.

**Overview came to 11 400 px on a 390 px screen** — the goal board is most of
that, and the four numbers a reader opens the page for sat underneath it. The
board folds on a narrow screen and stays open on a wide one: 5 200 px now, one
tap instead of a minute of scrolling. Built with `<details>` rather than a
script, so it survives a half-loaded page and a screen reader already knows how
to announce it.

**Polygenic scores sat a centimetre below «Full genome (VCF): no data».** Both
true — a score is a stored result, computed once from a file that need not still
be attached — and read as a contradiction with no way to tell which half to
believe. The block now says when it was computed and that the file is not
attached now.

**The disclaimer was printed four times on one screen** and after the fourth it
reads as legal cover rather than as care. It was repeated for a real reason:
Overview is thousands of pixels tall and the header scrolled away. The header is
pinned now, which answers the reason instead of arguing with it, and the copy
inside the focus card is gone.

**«P94», a phenotype code and a confidence mark carried no explanation** where a
reader first meets them; the Guide has all three, a tab away. They now carry the
Guide's own wording as a tooltip — the Guide's, not a second text written beside
them, because two texts for one term drift and the one on the badge is the one
nobody maintains.

**A traceback in the middle of the release log.** `test_server_guard.py` provokes
a failure to prove the server does not leak a filesystem path into an HTTP
response; the server prints the details to the owner's console, which is the
other half of that design. Read as a crash three times in one day. Swallowed in
the test that causes it — and the test now also asserts the traceback still
reaches the console, because silencing it in the server would delete half the
guard.

**One tool description still described the owner's shelf** («from Garmin
wearables and smart scales») in text written for every profile.

### Also

`LICENSE-DATA` attributed the knowledge base to `https://scholion.dev`, which
does not exist. It points at the repository now. The edit arrived in the built
package rather than the source tree, where the next publication would have wiped
it without a word — the hazard the two-repository model carries, and worth
recording next to the fix.


#### Also, on the unit gateway

`tests/test_unit_gate_second_law.py`. Among its assertions: that the published
pairs do NOT share a ratio — which is the reason the second law has to exist at
all, stated as something that fails if it ever stops being true.

---

## v0.3.0 — 18.08.2026

_Tagged three times before it left the building. `v0.3.0` and `v0.3.1` were pushed
to GitHub and rejected by PyPI — see «the metadata line» below — so neither was
ever installable, and both tags were withdrawn rather than left standing as
versions nobody could get. What follows is everything those three tags contained,
under the number the release was always meant to carry. If you have a checkout
pinned to `v0.3.1`, it is gone; `v0.3.0` is the same code and more._

_MINOR, and a **series break** in two places. `test_rules.json` rewrote three
rules, so a suggestion list printed before this version and one printed after it
are not the same document even from an unchanged profile. `loci.json` and
`longevity_directions.json` gained PCSK9, so a genome that resolved nothing there
now resolves four positions. Separately, a profile carrying BOTH a laboratory
report and a VCF can answer differently at a position where the two disagree: the
reads win now, and the disagreement is printed._

_Written from a run of the product as a stranger: the package built by
`make_shareable.py`, installed with `pip install` into a clean machine, opened in
a browser as two people — one with the demo, one an hour after installing with
nothing loaded — and read by three reviewers with no knowledge of the project. The
findings are theirs; what follows is what was done about them._

### What this changes in the conclusions

**A new profile no longer says anything about the person who created it.** Every
file `scholion init` laid down carried data: one triglyceride measurement dated
2024-01, one prescription, a sex, a year of birth and a height. A minute after
installing — before loading anything — the first screen counted «0 red flags over
the last 12 months», the labs tab showed a value flagged «within range» with a
date on it, and the header counted a prescription. Both readers who met that state
said they would have repeated those numbers to a doctor. The templates now ship
empty, and each one says in `_meta.why_empty` that the emptiness is a decision.
`metrics.json` no longer assigns a sex, a birth year or a height: the panels that
need them refuse until they are filled in, which is the correct answer.

**The suggestion rules stopped asserting facts about the reader.** The CYP2C9
rule fires for anyone whose CYP2C9 is unread — that is, for everyone new — and its
reason read «Together with the **already known VKORC1**…». True of exactly one
profile, the one it was written on. The APOE rule justified a test with «a goal of
the project». Both rewritten. «Track 2», the project's internal name for the
FASTQ→VCF pipeline, left the three rules it appeared in: every reviewer stopped on
it, and a clinician read «The CYP2C9 genotype (\*2/\*3) — through Track 2» as the
patient's genotype rather than as a test being suggested.

**Direction stopped being read as severity.** The first screen split current
abnormalities into «red flags» (above a ceiling) and «under observation» (below a
floor), which made a ferritin of 13 against a floor of 20 the milder of the two —
while the same screen's focus card was about that ferritin. The block now shows
every current abnormality in one list; the two counts remain, labelled as the
directions they are, with a line saying how the four numbers relate.

**The pharmacogenetic section says how much of it is about you.** With no
genotypes on file the section is not empty — every watch-list drug comes back with
the general rule printed in place of a statement about the person — so it now
opens with «K of N could be judged from the genotypes on file», and each row shows
the phenotype LABEL (`ultrarapid metaboliser — ASSUMED, not every marker was
read`) instead of the machine code (`UM`, `normal_sensitivity`).

### What is retracted

**The command for installing the skill never worked for anybody but the owner, and
would have leaked his key if it had.** The «Assistant» tab built the path as
`REPO/src/skill/INSTRUCTION.owner.md`. `REPO` is the repository root only in a
source checkout — after `pip install` it is the parent of site-packages, naming
nothing — and `INSTRUCTION.owner.md` never ships, so every installed copy showed
«not found» and then printed a symlink command into empty space. In a checkout the
path did resolve, and it pointed at `src/skill/`, which holds the owner's 117 KB
clinical key: following it would have symlinked that key into `~/.claude/skills`
for a model to read. The entry now names the packaged skill directory, prints no
command when there is nothing to point at, and a test asserts that whatever
directory it names carries no `*.owner.*` file — the assertion that fails on the
owner's own machine, which the path-exists version did not.

**Four places sent the reader to scripts that are not in the package.**
`call_full_vcf.sh`, `annotate_clinvar.sh`, `acmg_sf_scan.py`,
`loci_sites_bed.py` — all of `src/ingest/`, none of it shipped. They now point at
`scholion doc preparing-the-genome`, which travels with the package.

**The version in the header was a changelog line frozen in 2026-07.** `server.py`
kept `VERSION = "2026-07-30 · radar dynamics + tab freshness"` by hand while the
package was 0.2.2. It reads the package version now, and a test ties the two
together.

### What needs recomputing

Nothing stored changes value. Suggestion lists and second-opinion sheets printed
before this version carry the retracted wording and should be reprinted if they
are still in circulation.

### Also

- The demo announces itself on every screen — an amber band saying it is a
  fictional person. Before, the only sign was «DEMO-0001» in the header, which
  reads like a laboratory accession number.
- «Guide» moved from tenth tab to second. It answers most of what a newcomer asks
  and was being handed over at the end of the journey.
- A print stylesheet: the navigation, the source chips, the language switch and
  the cross-tab links are stripped, and the sheet gains a header with fields for a
  name, a date of birth and a date — the first thing a general practitioner said
  was missing — and a footer saying where the numbers came from.
- Empty chart frames replaced by a line saying no series exists yet. Three framed
  rectangles with headings and nothing in them read as broken, not as empty.
- `scholion init` names the first useful command for whatever the person actually
  has, and says out loud that the four external programs listed after it are for
  the genome track alone.
- The owner's own goal left the product's vocabulary: the CLI help, the tool
  description, the chart legend («the optimum window 2021–2022») and the default
  heading («Goal — get back in shape») were one person's aim shown to everyone.
- `_goal_num` used a decimal comma regardless of language, so the English page
  showed «TSH 6,4» in the goal table above a card reading «6.42».
- «The internet is needed» on the drugs tab, three centimetres under a padlock
  reading «runs locally», now says what actually leaves: the drug name typed, and
  nothing else.
- Three new test files — `test_fresh_profile_is_empty.py`,
  `test_entrypoints_are_reachable.py`, `test_empty_state_honesty.py` — named after
  the failures rather than the functions.

### From the other branch, in the same release

**There is now an address.** `scholion.dev@proton.me`, in `README.md`,
`SECURITY.md`, `CITATION.cff`, `pyproject.toml` and the issue-template config —
with the instruction, in every one of them, to send no personal health data, and
a pointer to `scholion redact` for anyone who wants to send a file anyway. This
closes the last item of R1.1: until now a reader who found a defect, or wanted to
offer de-identified data for validation, had nowhere to write.

**A page for clinicians.** `docs/FOR-CLINICIANS.md` — what the program takes in,
what it will and will not claim, and where it refuses. It ships inside the
package like the other documents (`scholion doc for-clinicians`).

**`scholion limits` names the cell it is answering from.** Input class (whole
genome / exome / consumer array) × trait architecture (monogenic / oligogenic /
polygenic): the pipeline differs in each, and so does what may be claimed. A
percentile with no architecture beside it reads as a verdict; «no pathogenic
variant found» in a gene the file never covered reads as reassurance. Where a
polygenic number is on screen, a note on heritability goes with it.

**Fact, not cause.** Raised by a clinical geneticist reviewing the project on
17.08.2026 and the sharpest technical point in that review: «ferritin rose after
the course» is a fact, «the course raised ferritin» is a causal claim that a
series of two points cannot support. Rule 7 of the skill entry now says so to the
model, and `test_safety_rules.py` holds the message catalogue to it — the
catalogue is where a causal habit would start, because the model imitates the
wording it is given.

### Two capabilities, in the same release

**The goal is proposed now, not shipped.** Removing one person's targets from
`health_goals.json` left a hole where a goal used to be, and «write your own»
is not an answer for somebody who has just installed a program. `scholion
goal-suggest` reads what the person has actually measured and what the clinical
associations publish, and proposes a target for each marker there is enough to
propose one for. Three sources, and the whole design is in keeping them apart:

- **a guideline**, quoted with its citation — the strongest and the rarest;
- **the person's own best**, with the date and the number of readings behind it.
  Not a recommendation from anybody: a fact about them;
- **the wall of the laboratory corridor**, offered last, because «inside the
  range» is where most people already are and is not an aim.

A target already met is not offered as something to reach — it goes to a list of
its own, which is a different and true statement. A target written for people
with a condition (ADA's «under 7 %» is for somebody who HAS diabetes) is never
adopted on a condition nobody confirmed. And what was passed over is listed with
the reason, because five proposals with no account of the forty markers skipped
read as «these five are what matter».

`goal_targets.json` is new, and its hardest entries are the empty ones. The
Endocrine Society looked at 25(OH)D in 2024 and withdrew the target it had once
set; that refusal is recorded, quoted, and travels with anything else proposed
for that marker — otherwise the laboratory corridor quietly supplies the number
the society declined to write.

Nothing is written to the profile without `--write` or a press of «Save», and a
target the person set by hand is never replaced: it is the strongest source
there is, because it is theirs.

**The inherited side of the lipid profile (task 63).** PCSK9 carriage and Lp(a)
in one card on «Genome», because each is misread alone. A low LDL-C with a
loss-of-function variant behind it is a different fact from the same number
reached on a statin; and Lp(a) is invisible to the rest of a lipid panel — set
at birth, unmoved by what moves LDL-C, so a normal panel with a high Lp(a) is a
normal panel that has missed the finding.

Four PCSK9 positions entered `loci.json`, each coordinate read from the Ensembl
REST API rather than from memory — the one lost variant in this project's
history was lost to a coordinate written from memory. Two of them entered
`longevity_directions.json` with primary PMIDs (Cohen 2005, Cohen 2006); the
other two did not, and sit in `unresolved` saying why. The catalogue's own rule
asks for a primary source naming the favourable allele, and review-level sourcing
is not that.

Two limits are printed rather than implied. «Not a carrier» of C679X says almost
nothing outside populations of African descent, where the variant is close to
absent — so the caveat travels with the answer. And a polygenic score for Lp(a)
is an ESTIMATE: the level is driven mostly by the number of KIV-2 repeats inside
LPA, a copy-number variant short reads see poorly, which is what the catalogue's
«Moderate» mark on `PGS002101` has been saying in a place nobody looks. Where
Lp(a) has not been measured the card says so and asks for the test — once in a
lifetime, in nmol/L, and before a decision about therapy rather than after it.

One correction to the analysis this was built from: `rs28362286` is **C679X**,
not «near Y142X». Y142X is a different variant (`rs67608943`). The position
Ensembl returns, 1:55063542, is at the 3′ end of the gene and fits residue 679,
not 142.


**A laboratory's summary sheet no longer overrules your own reads (task 64).**
`core.genotype_status` returned the profile entry the moment it found one and
never reached the VCF. So `rs4988235`, `rs1801133` and `rs429358` came back as
`reported / profile / depth=None` — copied off an Evogen summary — while the
person's own aligned reads sat unread in a file on the same disk. `scholion
genome rs4988235` meanwhile DID read the VCF and answered «reference confirmed
by a call (0/0), coverage 32». Two routes to one fact, disagreeing, and nothing
in either saying so.

A genuine read now wins: it carries a depth, it can be re-examined, and it is
what the report was made from. But only a genuine one — `assumed_ref` means «the
reference, OR nothing was looked at there», and letting that overrule a
laboratory's positive finding would be this project's oldest defect wearing new
clothes. A disagreement is never resolved silently: both values travel in
`conflict`, and the CLI and the interface both print it, with the suggestion to
take it back to whoever issued the report. Agreement is printed too — two
independent routes to the same call is a stronger statement than either alone.

Why the seventeen known disagreements between that report and the reads never
tripped this: `genotype_status` answered `None` for every one of them, because
those rsIDs are not in the coordinate catalogue. The priority was never exercised
where it is dangerous, so the absence of an error there proved nothing — and the
tests build the collision by hand rather than waiting for one.


### What is retracted — the CI job that could not run where it was sent

**The job written to catch «a check that asks the artefact for something only the
repository has» was one.** `tests.yml` has a `package` job whose first step runs
`make_shareable.py` — the sanitiser, which builds the package FROM `share/`. But
`share/` does not ship: it is the folder the package is built out of, not part of
what is built. So on the public repository that step answered «Run this from the
ORIGINAL repository (there is no share/ folder with the templates)» and the build
went red on the first push after publication, six seconds in.

The author never saw it, because the author is in the source tree, where it
passes. That is the whole of the class: a check agreeing with the single
environment it was written in. It has now cost this project four times, and this
is the first time it cost a red badge on a public repository — the first thing a
stranger sees.

The two steps are conditional now, on the same predicate `tests/support.py`
already uses and calls `IN_SOURCE_REPO`: does `share/` exist. Where they are
skipped the job says so with a `::notice::`, because a green tick for having run
nothing is worse than a red one, and the matrix job above has in any case already
run the package's own suite on exactly the files a recipient gets.

#### Also

`tests/test_ci_runs_where_it_can.py` — a workflow step that runs a tool needing
the source tree must be conditional, and the condition must be the same question
Python asks. The check is textual, so it is narrow on purpose; its first version
read the workflow's own explanation of the guard as an unguarded call, which is
the failure mode of every textual check and is why it now drops comment lines
before looking. Verified by removing the guard and watching it go red.

### What is retracted — the metadata line that kept this release off PyPI

**Two releases reached GitHub and neither reached PyPI.** `v0.3.0` and `v0.3.1`
both died on the same line, added when the project got an address to write to:

    Contact = "mailto:scholion.dev@proton.me"

Every value under `[project.urls]` has to be a URL, and PyPI means it:
`400 'mailto:scholion.dev@proton.me' is not a valid url`. The index published
`0.2.2` and has been publishing it ever since; the tags on GitHub say otherwise.
Anyone who ran `pip install scholion` after 0.3.0 was tagged got 0.2.2 and had no
way to know.

**When it failed is the part worth keeping.** The build succeeded. `twine check`
printed PASSED on both artefacts — it validates the long description, not the URL
schemes. The signing, the attestations and the transparency-log entries all
completed. The refusal came from the index, in the last step of the last job,
after everything that could have caught it had said yes.

The address now lives in `authors`, which is the field the core-metadata
specification has for an e-mail and which PyPI accepts; the built wheel carries it
as `Author-email: CrossRead <scholion.dev@proton.me>`. `Contact` points at the
README's own contact section — the place that says what to write about and, more
importantly, what not to send.

#### Also

`tests/test_packaging_metadata.py` asks the questions the index asks, when the
suite runs rather than when the artefact is in flight: every `[project.urls]`
value begins with `http`, an address to write to still exists and is not a
`mailto:` in disguise, and the version still comes from the one file. Verified by
putting the `mailto:` back and watching it go red, and by dropping the address and
watching it go red for the other reason — the fix must not become «we removed the
contact», which is the task the address was added for.

It parses the file by hand instead of with `tomllib`. That library arrived in
Python 3.11; this project supports 3.10, and 3.10 is the interpreter the mistake
was authored on — so a test that skipped without a TOML reader would have skipped
on the one machine where it mattered and reported OK for checking nothing. This
project has been bitten by that shape four times.

---

## v0.2.2 — 17.08.2026

_PATCH, by the owner's judgement and against the first reading of this project's
own rule — which is why the rule was rewritten in the same breath rather than
quietly stepped over (`docs/VERSIONING.md`, «Accepting a new form of an input»).
Everything here is the road in: nothing already stored changes value, and no
answer already given reads differently. Five unit forms that used to be refused
are now accepted, and one command was added that draws no new kind of
conclusion._

### What this changes in the conclusions

**Five more of the units a US lab actually prints are accepted.** Free T4 in
ng/dL, free T3 in pg/mL, TIBC and zinc in µg/dL, DHT in ng/dL. The lab import is
transactional by design, so one unknown form used to drop a whole panel and leave
the person with an import that did nothing. Each factor is stored with the molar
mass it derives from, so a wrong one can be caught by reading rather than by
trusting whoever typed it, and `hba1c` (mmol/mol) and `lpa` (mg/dL) stay refused
on purpose — one relates by an affine formula rather than a multiplier, the other
depends on the person's apo(a) isoform.

**`scholion doc` prints the documents the output points at.** A `pip install`
gets `src/scholion` and nothing else, while the output sends the reader to README
nine times, to PREPARING-THE-GENOME four and to DATA-LAYOUT twice. Those files
were not on a PyPI user's disk, and with the repository private there was no
second place to read them: `limits` was advising people to open something they
could not reach. Seven documents now travel inside the package.

**The first screen works from an empty machine.** `scholion demo` writes into
`<data>/demo/profile` and `scholion overview` reads `<data>/profile`, so the
README's opening two commands produced an empty profile. The first line is now
`init --demo`. `demo` is unchanged and still right: building the profile away
from a real one is the correct default.

**A bare `scholion` answers instead of erroring,** and `init --demo` no longer
lists four external programs the demo does not use. After a real `init` the
offer stays — there the genome layer needs them.

**The skill loads a short entry instead of a thousand lines.** `SKILL.md` was
the whole instruction — around seventeen thousand tokens on every trigger before
the first useful word, and the one thing a newcomer needs, how to start, was not
in it. It is now a 5.5 KB entry plus `INSTRUCTION.md`, which the model opens when
the task calls for it, and `make_skill_package.py` builds the pair and its
references into a single `dist/scholion.skill`: for somebody whose only tool is a
language model, a folder is not a delivery and a file is.

**The local web interface got a design.** It is styled with Pico CSS, vendored
rather than fetched from a CDN: the interface binds to `127.0.0.1` and the claim
is that using it sends nothing anywhere, which a stylesheet loaded from somebody
else's server on every page would quietly make false. The bundled copy is now
recorded in `ATTRIBUTION.md` under a section that did not exist — the legal layer
covered tools the user installs and data redistributed here, but not code that
travels inside the package.

**A profile file now says which shape it is in.** Nothing to migrate yet; the
direction that matters is that a build refuses a file written by a newer one
rather than reading an unknown shape with rules that no longer apply. That
direction cannot be added later — by the time there is a version 2, the builds
that must refuse it are already installed.

### What is withdrawn

Nothing. Every previous result stands; what changed is what the system will now
accept as input and what it will now refuse.

### What needs recomputing

Nothing. A panel that failed to import because of one of those five units can be
imported again — it never wrote anything, so there is nothing to correct.

### Changes by file

**Knowledge — a break in the series**

- `src/scholion/knowledge/lab_markers.json` — five US unit forms, each with its derivation

**Web interface**

- `src/scholion/web/` — a design, styled with a vendored Pico CSS
- `ATTRIBUTION.md` — a section for code bundled in this repository

**Skill**

- `share/skill/` — the instruction splits into a short `SKILL.md` and `INSTRUCTION.md`
- `src/skill/INSTRUCTION.owner.md` — the owner's edition, renamed and still private
- `src/tools/make_skill_package.py` — the bundle as one file

**Engine and application**

- `src/scholion/cli.py` — `doc`; a bare call answers; no tool offer after a demo
- `src/scholion/core.py` — the profile schema layer: read, refuse, stamp
- `src/scholion/docs.py`, `src/scholion/docs/` — seven documents carried inside the package
- `src/scholion/contract.py`, `src/scholion/i18n/` — the new command and its wording
- `src/scholion/templates/profile/` — a version number, and the layout prose moved off that key

**Tools and build**

- `src/tools/sync_docs.py` — keeps the carried documents equal to their sources
- `src/tools/check_language.py` — copies are measured once, not twice

**CI**

- `.github/workflows/tests.yml` — ubuntu + macos × Python 3.10–3.13, a symlinked
  TMPDIR, and the package's own suite run inside the package


## v0.2.1 — 17.08.2026

_PATCH: nothing that ships behaves differently. `v0.2.0` could not be published —
its own test suite failed on a public runner, and the workflow runs that suite
before it publishes._

### What this changes in the conclusions

Nothing. This release exists because `v0.2.0` never reached anybody.

A test read `src/tools/check_push.py` — the private repository's pre-push hook,
which guards a history a recipient does not have and therefore does not ship.
Inside the package the file is absent, the test raised `FileNotFoundError`, the
suite went red and no version was published.

That is the third time in three days for the same shape: `.personal_patterns` in
v2.23.0, `share/` in v0.1.3, this one now. The first two were repaired by
guarding the one test that had failed — which is how a class survives being
fixed. The third is the one worth naming: `support.IN_SOURCE_REPO` already
existed, written for the second, and simply was not used.

So the repair is on the publication rather than on the test. `publish_share.sh`
now **runs the package's own suite inside the package**, before anything is
committed or pushed, and a red run stops the publication instead of announcing
it. `pyproject.toml` has stated that rule in prose since the sdist was defined —
«a green run at the author's end with a red one at the recipient's does not mean
verified, it means the state of the artefact is unknown» — and nothing enforced
it. The run leaves `__pycache__`, which the audit calls build junk, so the last
word belongs to a clean rebuild and a second audit.

A textual rule was tried first and abandoned, which is worth recording so nobody
tries it again: «a test module reading a repository-only path must name
IN_SOURCE_REPO» flagged `test_redact.py`, which correctly writes its own
`.personal_patterns` into a temporary directory, then missed the real defect, and
tightening it would have failed three modules that guard themselves differently
and correctly. A check wrong in both directions is worse than no check.

### What is withdrawn

Nothing. `v0.2.0` was tagged and pushed but never published — anyone who has it
has it from the repository, not from an index.

### What needs recomputing

Nothing.

### Changes by file

**Tools and build**

- `src/tools/publish_share.sh` — the artefact's own suite runs before the commit; a clean rebuild after it

**Tests**

- `tests/test_privacy_guard.py` — the push-gate test asks whether it is in the repository
- `tests/test_build_audit.py` — the publication is checked for running the suite it declares


## v0.2.0 — 17.08.2026

_Comparison base: v0.1.3 → HEAD. 13 files changed. **MINOR, not PATCH: this is a
break in the series** — `src/scholion/knowledge/` changed and the same input now
yields a different answer._

### What this changes in the conclusions

**The DPYD panel goes from two variants to seven.** The 2024 joint consensus of
AMP, ACMG, CPIC, CAP, DPWG, ESPT, PharmGKB and PharmVar names seven Tier 1 DPYD
alleles — the set a clinical panel is expected to carry. This one carried two:
`*2A` and `c.2846A>T`. Now it carries all seven: `*13`, HapB3 (both of its tags),
`c.557A>G`, `c.868A>G` and `c.2279C>T` are added, with their coordinates taken
one at a time from dbSNP and Ensembl rather than from anybody's memory. The gene
is on the minus strand, so the cDNA notation and the allele written in a VCF are
opposites; each was converted and checked.

A person who ran `drug capecitabine` before this release and was told the DPYD
markers looked normal was told that on the strength of two positions out of
seven. The same command now says «read 2 of 8 markers» and names the six it could
not read. **Nothing about that person changed; what the answer admits did.**

**A haplotype carried by two variants counted as two alleles.** DPYD HapB3 is one
allele described by `rs75017182` and `rs56038477`, which travel together. The
counter added copies per marker, so a single heterozygous carrier would have
produced two decreased-function alleles — CPIC activity score 1.0 read as 0.0, an
intermediate metaboliser reported as fully deficient. The direction is towards
caution, which is why it could have sat there; it is still a wrong statement
about a person. Markers may now declare a `haplotype`, and one is counted once.

**Five markers were outside the extraction target and nobody could have seen it.**
`fastq_to_vcf.sh` carried its own table of regions to align against. Two CYP2C19
markers were written on chromosome 19 — the gene is on 10. Two DPYD intervals
stood 373 kb and 899 kb from their loci. `rs1142345` — TPMT `*3C`, the commonest
deficient allele in Europeans — was 31 bases outside the left edge. None of that
surfaces as an error: `bcftools` finds no row outside the target and the marker
comes out `./. (ref/not covered)`, exactly what a position the sequencing
genuinely missed produces. Anyone following the documented route was told nothing
was found where their genotype was. The table is gone: the target is generated
from the catalogue at every run.

### What is withdrawn

**Any previous «DPYD looks normal» rests on two positions out of seven and does
not exclude a deficiency.** It was never phrased as an exclusion, but it was read
as one, and at full-dose fluoropyrimidine the difference is not academic.

**Any previous genotype for CYP2C19 `*2`/`*17`, TPMT `*3C` or the two DPYD
markers, obtained through `fastq_to_vcf.sh`, is not a result.** Those positions
were never in the alignment target; `./.` there means «not looked at», not
«reference».

### What needs recomputing

For anyone whose VCF came through `fastq_to_vcf.sh`: **re-run the extraction**,
because the target now reaches five markers it did not before. Genotypes read
from a full-genome VCF produced elsewhere are unaffected — only the targeted
route was narrow.

Nothing else needs recomputing. The wider DPYD panel does not change a stored
value; it changes how much of the panel an answer admits to having read.

### Changes by file

**Knowledge — a break in the series**

- `src/scholion/knowledge/cpic_drug_gene.json` — DPYD: 2 markers → 8, `haplotype` on the HapB3 pair
- `src/scholion/knowledge/loci.json` — 6 DPYD loci added; new `regions` section for whole-gene windows

**Engine and application**

- `src/scholion/engine.py` — a multi-tag haplotype counts once

**Data preparation**

- `src/ingest/fastq_to_vcf.sh` — the target BED is generated from the catalogue
- `src/ingest/update_check.sh` — the version of ClinVar is read by the name it is written under

**Tools and build**

- `src/tools/check_staged.py` — `in_forbidden_dir`: a personal-data folder under a neighbouring name
- `src/tools/check_push.py` — uses that predicate instead of its own copy

**Tests**

- `tests/test_answerability.py` — haplotype counting; the online drug route
- `tests/test_catalogue_integrity.py` — the DPYD panel against the external consensus
- `tests/test_pgx_script_coordinates.py` — BED-shaped coordinate tables; the margin invariant; note vs catalogue
- `tests/test_privacy_guard.py` — a renamed personal folder


## v0.1.3 — 17.08.2026

_Comparison base: v0.1.2 → HEAD. Commits: 6. 21 files changed, 356 insertions(+), 19 deletions(-)._

### What this changes in the conclusions

One new layer: `prescription` can now surface a hand-curated fact from the
patient's own record. `medications[].safety_flags[]` in `profile/medications.json`
holds entries the engine never invents — it only reads one a person wrote down: a
documented diagnosis, a documented event, a conflict with their own history. A
flag marked `red_flag` lifts the overall verdict to `high`, anything else to
`moderate`, and the renderer prints it first — above the genome, the labs and the
interactions, because a flag read last is a flag not read. The web view carries
the same block, and both skill editions now say when to raise one: as soon as a
new document yields a diagnosis that changes how a current prescription reads,
and in reverse — check any new document against the current drug list.

Nobody who has not written a `safety_flags` entry into their own profile sees any
difference in output; the layer is silent until a person fills it in.

Everything else in this release is process and safety-net, not a change to any
result: the shipped skill file is now checked against substitution at build time
(the package ships two editions of `SKILL.md` and a build error used to be able to
put the wrong one at a given path without anything noticing); the package's own
test suite is now verified to pass from *inside* the package it built, not only
inside the repository that builds it; a repository-hygiene test that mistakenly
flagged the package's own shipped profile/genome templates as personal data is
corrected; and a publication commit can now be signed with a real identity
instead of the anonymous one the tooling used before.

### What is withdrawn

Nothing.

### What needs recomputing

Nothing computed from existing data changes. `safety_flags` is something a person
adds by hand to their own `profile/medications.json`; it has no effect until they
do.

### Changes by file

**Tools and build**

- `src/tools/check_language.py` — changed
- `src/tools/check_staged.py` — changed
- `src/tools/install_hooks.sh` — changed
- `src/tools/make_shareable.py` — changed
- `src/tools/publish_share.sh` — changed

**Skill**

- `share/SKILL.shared.md` — changed
- `src/skill/SKILL.md` — changed

**Engine and application**

- `src/scholion/engine.py` — changed
- `src/scholion/format.py` — changed
- `src/scholion/i18n/en.py` — changed
- `src/scholion/i18n/ru.py` — changed
- `src/scholion/skill/SKILL.md` — changed
- `src/scholion/web/index.html` — changed

**Guides and documentation**

- `CLAUDE.md` — changed
- `README.md` — changed
- `docs/DATA-LAYOUT.md` — changed

**Tests**

- `tests/support.py` — changed
- `tests/test_build_audit.py` — changed
- `tests/test_licensing.py` — changed
- `tests/test_repo_hygiene.py` — changed

**Other**

- `.gitignore` — changed

<details><summary>Commits</summary>

- a diagnosis of the patient's own can now outrank a computed verdict
- the package's own template files no longer read as somebody's personal data
- readme: trim the versioning explanation to one sentence
- the publication commit can be signed by a person, and the setting that does it no longer kills the script
- the suite stops being red inside the package it was built from
- the shipped edition of the skill is checked, and the layout gains a slot for what was made to be read

</details>

## v0.1.2 — 17.08.2026

_Comparison base: v0.1.1 → the working tree (not committed yet). Commits: 0. 5 files changed, 79 insertions(+), 13 deletions(-)._

### What this changes in the conclusions

Nothing about anyone's health, and nothing in how a result is computed.
`set-folder` used to accept only a fixed list of eight domain names (labs,
medications, metrics, genome, labs_docs, med_docs, garmin, apple_health — the
last one newly recognised in this release, though nothing parses it yet) and
refused everything else outright. A source folder that is legitimately
personal — a CGM app's screenshots, a specific sequencing provider's export
folder, whatever the next such folder turns out to be called — had no way to
be recorded at all.

An unrecognised domain name is now accepted rather than refused, and filed
under a new `external_sources` section of `profile/sources.json` instead of
`folders`. `core.source_config()` — what every reader of a configured folder
actually calls — merges both sections, so the split matters only at the
moment a folder is set, never when one is read back.

The trade-off is explicit, not accidental: the old refusal also caught a typo
of one of the eight names as a side effect ("grmin" for "garmin"). Opening the
domain up removes that — a near-miss is now just an ordinary new
`external_sources` entry, and the intended domain is left untouched, not
corrected. Nothing reads `external_sources` programmatically yet, so today
that costs nothing silent.

### What is withdrawn

Nothing.

### What needs recomputing

Nothing. No stored value, no catalogue and no conclusion changed.

### Changes by file

**Engine and application**

- `src/scholion/cli.py` — changed
- `src/scholion/core.py` — changed
- `src/scholion/store.py` — changed

**Tests**

- `tests/test_external_sources.py` — added

**Other**

- `VERSION` — changed

## v0.1.1 — 16.08.2026

_Comparison base: v0.1.0 → the working tree (not committed yet). Commits: 0. 1 file changed, 53 insertions(+), 1 deletion(-)._

### What this changes in the conclusions

Nothing about anyone's health. Two defects in the gate that runs last — the
pre-push hook — one of which would have stopped the first push of this repository
anywhere.

**The pre-push check refused the synthetic genome fixture.** `tests/fixtures/genome/
tiny.vcf.gz` is the one genome file this project allows into its history, and it is
allowed by content rather than by name: the header has to declare it invented, and
the call set has to be small enough that nothing real fits through. Four gates ask
`synthetic_fixture` that question — the pre-commit hook, the build audit, the
repository-hygiene test, the `.gitignore` negation. `check_push.py` never did. It
saw a `.vcf.gz` in the history and blocked, which means every earlier gate could
approve the repository and the last one would refuse it at the moment of pushing,
over a file the project ships deliberately. The exception is now asked of the same
module the other four ask, so it cannot drift between them.

**The pre-publication tags could travel out with `git push --tags`.** 32 tags named
`v1.0.0` … `v2.24.0` live under `pre-0.1.0/` because the numbering was reset at
publication and those same numbers will be used again. `git push --tags` does not
ask which tags — it sends every tag it has. The CI filter (`tags: ["v*"]`) would
not have published them to PyPI, but by then they would already be in a public
history, and a pushed tag is not taken back by deleting it locally. The hook is the
only place that sees the refs and can still say no; it now refuses them by name and
prints what to push instead.

Neither would have fired today — the private repository has no remote, so there is
nowhere to push. Both would have fired the first time one was added.

### What is retracted

Nothing published. The claim being corrected is internal: that the five gates
guarding personal data all asked one predicate. Four did.

### What needs recomputing

Nothing. No stored value, no catalogue and no conclusion changed.

### Changes by file

**Tools and build**

- `src/tools/check_push.py` — changed

## v0.1.0 — 16.08.2026

_The first release anyone outside the project can install._

### What this changes in the conclusions

Nothing is retracted and nothing needs recomputing: there is no previous public
version to compare against. What follows is what the release contains and, more
importantly, what its number means.

### What the number means

**Below `1.0.0` the public contract may break.** Command names, the top-level
fields of `--json`, the file names inside a profile — the project's own rule is
that these may grow and may not shrink, and `python3 src/tools/check_compat.py`
enforces it on every run. Until `1.0.0` that rule is **internal discipline, not a
promise made to anyone outside**: it is stated here so that a person who builds on
`--json` knows precisely how much weight it carries, which is some, and not all.

**`1.0.0` arrives by use, not by features.** The condition is a number of people
who have run this on their own medical data and said what happened — not a count
of finished capabilities. Everything in this release was verified on invented
forms, an invented profile and one real record; the failure modes that matter for
a system like this appear in the second record and in the tenth, not in the first,
and no amount of building substitutes for that.

### What it does

Reads a person's genome, laboratory history, prescriptions, clinical conclusions
and wearable data against each other, locally, with the source shown behind every
statement. One core with three entry points — a local web app, a command line, and
a skill for a language model — and a rule, enforced by a test, that a capability
appears in all of them at once.

The part worth naming is what it refuses to do:

- **A value without a reference corridor is never shown as normal.** Green means
  «inside the corridor»; with no corridor there is no such claim to make.
- **A connected genome cannot make an answer less cautious.** A position with no
  row in a VCF is either the reference or no coverage at all, and the file does
  not say which — so it is carried as an explicit confidence level rather than
  collapsed into «reference». Before this was fixed, a person with a genome
  attached could get a calmer answer about a drug than the same person without one.
- **Units are a gate before they are a conversion table.** A value is admitted into
  a series only in a unit the marker declares, and the reference range is converted
  with it — the two travelling apart is a defect this project found in itself.
- **A source that was never reached makes no negative statement.** «No significant
  pharmacogenetics» and «the database did not answer» are different sentences.
- **What is not known is printed.** `scholion limits` states the coverage behind
  the genomic conclusions and names what cannot be concluded from the data present.

Everything it produces is material for a person's own decisions and for a
conversation with their physician. It is not a medical device, it is not a
clinical decision support system, and it does not diagnose.

### What is knowingly incomplete

- **Nobody outside has run this yet.** That is the single largest gap in the
  evidence behind everything above.
- **eGFR is not read from an English laboratory form.** Its value is printed on the
  line below its name, and relaxing that rule would take a wrong number on the very
  form the rule was written for. It needs a real English form to decide on, and
  there is not one — so it stays named rather than fitted.
- **175 markers are recognised in Russian only** — urine organic acids, the
  coprogram, the dysbacteriosis culture, the element panels. They are barely
  ordered outside Russia; their labels are work an outside contributor can do
  without touching any logic.
- **LOINC codes are absent.** The table is available from Regenstrief, and using it
  obliges the project to ship a verbatim notice in `NOTICE` in the same commit.
  Neither half could be done honestly on release day.
- **Pharmacogenetics covers seven genes** — the core with the strongest evidence,
  not a full panel. CYP2D6 as a whole needs a dedicated tool: structural variants
  and phasing.

### What holds it together

393 tests, run offline against synthetic fixtures and executed inside the built
package rather than only in the repository. A parsing baseline recorded *before*
the dictionary migration that followed it — the timing is the value: a baseline
recorded after a change states that the code equals itself and passes on any
behaviour. Every test written for a defect was re-run against the un-fixed code to
prove it catches it. A build audit that fails the package on any personal datum —
in plain text or encoded — and three independent barriers keeping personal data
out of git.

---
