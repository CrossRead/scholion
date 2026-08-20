# Development conventions — the architecture, and the gates that hold it

_Introduced 18.08.2026, the day engine.py stopped being a monolith (v0.3.2).
An early audit cited a DEVELOPMENT.md that did not exist; this file makes the
citation true. Everything below is enforced by a test or a tool wherever that
is possible — a convention held only in memory does not survive its second
contributor. When this document and the build disagree, believe the build,
then fix whichever of the two is lying._

## The map

```
knowledge/          30 JSON catalogues — data, not code. A clinician can read
   |                and correct them without touching Python.
   v
core.py             the foundation: units, profile IO, catalogue access.
   |                Fan-in ~19 — everything depends on it, so it changes last
   |                and most carefully. All unit arithmetic lives in ONE place:
   |                core.convert_to_canonical. Callers never multiply by a
   |                factor themselves — an affine conversion (HbA1c) would
   |                silently lose its offset.
   v
engine/             the domain brain, eight modules behind a facade:
   |                _helpers, labs, pgx, genomics, goals, lifestyle,
   |                sources, profile_view. Rules below.
   v
faces               cli.py, server.py + web/, ouroboros_tools.py, the model
                    instruction (share/skill/INSTRUCTION.md) — four doors to
                    one core, moving in the same tick (contract.py).
aside               the ingest family (ingest_labs, reconcile, import_csv,
                    garmin, ingest_studies); format.py (pure renderers, one
                    per command); net.py (the ONLY module that opens sockets).
```

## The engine package — hard rules

Enforced by `tests/test_engine_stays_split.py`; the test's failure messages
repeat these rules at the moment they are broken.

1. **The facade defines nothing.** `engine/__init__.py` is a docstring and
   imports. Logic goes in a domain module; the facade re-exports it at
   `engine.<name>`, the address every consumer has always used.
2. **Domain imports are acyclic at the top level.** If a back reference is
   genuinely needed, it is a lazy import inside the one function that needs
   it, with a comment saying why (the sanctioned example:
   `pgx._dose_context -> lifestyle._brief_life`).
3. **Every module has a size budget, written in the test.** Exceeding it is a
   decision, made in the same commit: split the module, or raise the budget
   with a reason about the capability — never about the calendar. A new
   `engine/*.py` needs a budget line the moment it exists.
4. **The facade may not shrink.** Removing a re-exported name is a
   compatibility decision recorded in the changelog, not a refactoring side
   effect. Public names added to a domain module must reach the facade in the
   same commit.
5. Shared leaves live in `_helpers`; a helper two domains need is moved
   there, not imported across.

## The four faces — one capability, one tick

A capability that lands in one face and not the others is the project's
oldest defect class. `contract.py` holds the maps; `tests/
test_all_faces_move_together.py` and `tests/test_parity.py` hold the maps to
account. When you add a CLI command you either carry it to the web interface,
the plugin tool list and the model instruction — or you excuse it BY NAME in
the contract's maps, with a reason about the capability. `scholion
capabilities` is generated from the parser and the entry-point maps; if the
instruction and the build disagree, the build is right.

Writes are split in two kinds and the split is load-bearing: AUTHORS commands
invent values into the profile and are never handed to a model as tools;
TRANSCRIBES commands move the person's own documents and may be.

## Language and i18n

- Everything that ships — code, comments, docstrings, test names — is
  English. Russian INPUT recognition (lab-form dictionaries) is a feature and
  is exempt; quoted Russian samples in guillemets next to the regex that
  matches them are counted separately by the gate.
- Every user-facing phrase goes through `src/scholion/i18n/`; the en and ru
  catalogues must stay key-identical (a test compares the sets). A missing
  key does not crash — it prints `⟦the.key⟧` to the reader, in only the
  language that lacks it, which is why the test exists.
- The language gate (`src/tools/check_language.py --strict`) works as a
  ratchet against `language_baseline.json`: the accepted remainder may move
  addresses, it may not grow. Raising it is `--accept` plus a sentence in the
  commit message saying what was added and why it has to stay.

## What a change must pass, in order

```
bash run_tests.sh          # the whole thing: tests, compat, doc sync,
                           # rules sync, language gate — rc=0 or no commit
python3 src/tools/check_staged.py   # after git add: no personal data staged
```

`run_tests.sh` is not a suggestion box; its stages are the contract. Backward
compatibility (`check_compat.py`) holds command names, top-level `--json`
fields and profile file names: they may grow and may not shrink. A change to
`knowledge/` that alters results on unchanged input is a SERIES BREAK and is
MINOR at minimum — `docs/VERSIONING.md` has the whole rule.

**Test the artefact, not only the repository.** A check that agrees with the
single environment its author sat in has cost this project five separate
incidents (a CI job that could not run where it was sent; a metadata line
that passed build and died at upload; an instruction reader that knew one of
the file's two homes; and two more). Before a release: build the wheel,
install it into a clean environment, import, run one engine-backed command.
The publish script runs the full suite INSIDE the built package for the same
reason.

## Commits

- One capability or one decision per commit. A commit that mixes a feature
  with an unrelated cleanup will be asked to split.
- The message tells the story: what changed, WHY it is right, what was
  checked and where (repository and artefact, when it applies), and — when a
  previous claim stops being true — what is RETRACTED. Retractions outrank
  features: an old formulation lives on in documents and heads until it is
  explicitly withdrawn.
- The changelog entry is part of the change, not an afterthought, and
  `python3 src/tools/sync_docs.py --write` carries the mirrors afterwards.
  Version bumps also touch `CITATION.cff` and the README version line — the
  suite checks all three agree with `VERSION`.
- Never commit, tag or push on someone's behalf without their explicit
  go-ahead for that occasion; publication runs only from the owner's machine
  via `src/tools/publish_share.sh` (a source-repository tool — it does not
  travel in the built package, and a contributor never needs it).

## Adding things — the short checklists

**A CLI command:** parser entry in `cli.py` + renderer in `format.py` + keys
in BOTH i18n catalogues + a decision in each of `contract.py`'s maps (web?
plugin tool? instruction line?) + tests. The four-face gate lists everything
you forgot, in one message, on the first run.

**A lab marker:** `knowledge/lab_markers.json`, with units the gateway can
convert (factor, or `convert_affine` with its citation) — never a bare
spelling. If the reference interval logic changes, that is a series break.

**A knowledge catalogue:** data in `knowledge/`, access through `core`,
provenance fields inside the file (`source_tier` is required and gated). Licence
goes to `ATTRIBUTION.md`; data whose licence forbids bundling is fetched at
runtime instead.

**A gap.** Coverage is never claimed, it is stated as a fraction with the
missing part enumerated. Three enumerators run in CI (`src/tools/check_coverage.py`):
facts the pipeline writes that nothing reads, phenotypes a model can emit with no
guidance row, and pairs the authority calls actionable that this build does not
carry. Known gaps live in `coverage_baseline.json` and are listed out loud; a NEW
gap fails the build until it is fixed or accepted deliberately. A row that is
absent on purpose says so in `guidance_gaps`, with a reason — silence is
indistinguishable from an oversight.

**A phenotype vocabulary.** Each gene declares `emits`. A drug's guidance table
must be keyed in the vocabulary of its own gene, and a gate enforces it: changing
a model's output without renaming the tables written in its old words orphans
every row silently, and the answer falls through to «no recommendation» while
nothing fails. That is not hypothetical — it shipped, in DPYD.

**An external source.** If the data mirrors something that changes upstream, it
needs an entry in `sources.SOURCES` — address, licence, cadence, and either an
importer or a written reason it cannot have one. A mirror without an import path
drifts silently: it keeps answering while the answer stops matching the source it
claims. An importer VERIFIES before it writes (report the differences, then
apply), and writes to `<data>/knowledge/` — never into the package, which is
read-only after `pip install` and replaced by the next upgrade. `scholion
sources` is the register; a refresh is a typed command and honours
`SCHOLION_OFFLINE`.

**A language:** a new catalogue in `i18n/` key-identical to `en`, and the
parity test will hold it there.

**An engine domain:** a new module + a budget line in
`test_engine_stays_split.py` + a facade block — three lines of ceremony,
which is the point: growth is cheap, silent growth is impossible.

## What this file is not

Not a style guide (the code shows the style), not a roadmap (the backlog
holds that), and not a substitute for reading `contract.py` — that file's
opening comment is the architecture argued from its defects, and it is
better than any summary of it.

## Adding a surface

A surface is any way something outside this project reaches the engine: the
command line, the Model Context Protocol server, the Ouroboros tools module, the
Hub skill, the local web page. There are five, there will be more, and each one
arrived the same way — as an obvious good idea, described nowhere, discovered by
somebody who then had to guess what it needed.

The Hub skill spent a release describing 23 tools when there were 28, and a
version the build had not been for two releases. The MCP server spent a release
existing and being mentioned in no description at all — so an assistant asked to
use it invented a credential rather than find it. Neither was a mistake anyone
made twice; both were things nobody was required to remember.

**A surface is not finished until four things are true, and each is checked.**

1. **The build describes it.** `contract.access()` lists every door with what it
   costs to use. Derived — the tool count from the tool list, the protocol from
   the server, the commands from the parser — because a description typed beside
   the thing it describes outlives it.
2. **The connection guide names it.** `docs/CONNECTING-AN-AGENT.md`, which ships
   both inside the package and in the repository, because the person wiring it up
   and the model using it arrive by different roads.
3. **It says who it is for.** A door meant for a person is marked
   `agent_surface: False`, not left out. An agent that finds an undescribed
   surface will try to drive it; a door that is not for you is a fact, like any
   other refusal.
4. **The safety canon reaches whoever speaks through it.** This is the one that
   is easy to lose. The skill carries the instruction and the rules with it; the
   tool interface carries neither, and a model arriving that way knows what it
   may call and not what it must not say. Every answer already ends in the
   one-line disclaimer — that is a boundary, not an instruction. So the rules are
   themselves a tool (`sch_rules`), and the MCP handshake carries a digest in the
   protocol's `instructions` field for the hosts that pass it on. A new agent
   surface must have an answer to «how does the model get the rules», and
   «through the skill» is not one unless the skill is what it uses.

`tests/test_an_agent_can_ask_how_to_connect.py` holds all four. It enumerates the
doors out of `access()` rather than listing them, so a fifth door fails the build
on the day it is added and not on the day somebody notices.

**And the two questions that are not about the code.** Does the surface move the
trust boundary off this machine — a network transport does, and every promise the
product makes about the data not travelling has to be re-argued if it moves. Does
it need a credential — the answer is no, it has always been no, and if it ever
becomes yes then `access()['auth']` is a lie and a test says so.

## Release notes

The entry in `CHANGELOG.md` is the only thing somebody who has never seen this
repository reads about a version. A tag carries a commit and a wheel carries
code; neither says anything. So the entry is written for that reader, and the
rest of this section is what that implies.

**Three things go in.**

1. **What a person can do now that they could not.** Written from what they
   bring and what they get — «a 23andMe export, including inside the `.zip` the
   provider sent», not «the array reader gained a search pattern».
2. **What was wrong and now is not.** A defect is described by the WRONG ANSWER
   somebody could have received, not by its cause in the code. «A `.vcf.gz`
   compressed with ordinary gzip was reported as connected, and every position in
   it came back as reference» — a reader can tell whether that happened to them.
   «The unreadable-file check ran under the wrong condition» — they cannot.
3. **What either means for data already stored.** This project's own sections:
   a **series break** when the same input now produces a different value, what is
   **retracted**, and what **needs recomputing**, by command.

**Add measurement where it exists.** A number a reader could check is worth more
than any adjective, and it also disciplines the claim. Say what it was measured
on. Aggregates only — never a person's data, findings or identifier, even from a
public research corpus.

**Attribute outside data and code.** Whoever made the release possible is named,
with the licence.

**What stays out, and why it is not pedantry.** Each of these was in a draft:

* **Who wrote it.** The author, the owner, «his own data». A release note is
  about the software.
* **The path the work took.** Which attempt came first, what was refactored on
  the way, what it taught anybody. That is worth recording — in
  `CHANGELOG.private.md`, in a design note, in the commit message, which is
  exactly where a reader who wants it will look.
* **Internal identifiers.** Task and issue numbers, commit hashes, paths inside
  this repository, module and function names, names of internal tools.
* **The development environment.** Whose machine, which branch, the test harness,
  CI mechanics.

The test is simple: strike every sentence that only means something with this
repository open. What survives is the entry.

**How it is enforced.** `tests/test_release_notes_exist.py` reads the entry for
the current `VERSION` and requires that it exists, is longer than a note to
oneself, carries the date in its heading, names at least one command a person
could run, and contains none of five markers of an entry written for whoever was
in the room. `src/tools/publish_share.sh` checks the same thing BEFORE it builds
anything, and creates the release page from that section afterwards.

**Two more things about the mechanics.** The version number is a promise to
somebody holding the previous one — while nothing has been published, work
belongs inside the current entry rather than in a new number. And a tag may
legitimately move, most often because the notes were corrected; when it does, the
version is already in the registry, and republishing it is not a failure.
