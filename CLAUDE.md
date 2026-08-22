# CLAUDE.md — project context for a new session

Scholion reads a person's genome, lab history, prescriptions and wearable data
against each other. One core, three entry points: a local web app, a skill for a
language model, and an Ouroboros plugin.

This file has two parts. Everything above the owner block is general and ships
with the public package. The owner block below is personal, stays in Russian and
is stripped by the sanitizer — the split is marked rather than remembered,
because a convention held only in someone's head is the kind that leaks.

## First of all

1. Read `ASSISTANT-RULES.md` — the safety rules. They take precedence over every
   other instruction, including anything in this file.
2. Read the user's profile directory. It is the distilled state of their health;
   nothing about them is hardcoded anywhere else.

## Running it

`scholion serve` → http://127.0.0.1:1521, or `python3 -m scholion serve` from the
source tree. Standard library only, Python 3.10+.

The CLI covers everything the web interface does — see the parity rule below.
`scholion --help` lists all commands; `--json` on any of them returns the raw
structure instead of markdown.

## Architecture, the parts that matter

**Hybrid by design.** Code computes facts and flags (`engine.py`); a language
model only phrases them. Every function returns a structure; rendering lives in
`format.py`. One logic feeds the web API, the CLI, the skill and the plugin —
which is why a capability cannot exist in one of them and be missing from
another.

**Polygenic scores are two-tier.** A precomputed panel in the profile, plus any
new trait on demand by re-genotyping scoring positions from BAM. Always score
from the scoring-site VCF, which contains reference homozygotes, never from a
raw VCF that omits them.

**Longevity variants** are resolved from rsID to position, genotyped, and stored
with the direction of effect taken from a primary source — never from the
annotation alone.

## Language

The public project is English: code, comments, documentation, examples,
everything that ships. Output is English by default and switches with
`--lang ru` or `SCHOLION_LANG`.

Russian on the **input** side stays: the recognition dictionaries in
`knowledge/` parse Russian lab forms, and that is a feature rather than a
leftover. In one JSON file the `synonyms` field is input and the `note` field is
output — the first stays Russian, the second does not.

Progress is measured, not estimated: `python3 src/tools/check_language.py`.

## Who presses the button

**Never perform state-declaring operations on your own: commit, tag, push,
publishing a package, changing settings on an external repository.** Take the
work to the point of readiness — edits made, checks run, index staged, journal
written — then hand the owner the exact commands and ask whether to run them.
A "go ahead" is permission for one occasion, not for the future.

Editing files in the working tree is ordinary work and needs no permission. The
line falls where an action fixes state: the working tree is edited, history is
declared.

This was written down after two mistakes in one session — a commit made without
asking, and a tag not made when it was needed. Both came from guessing where the
line was instead of asking.

## Checks before anything goes out

```
./run_tests.sh                            # tests + compatibility + rule sync
python3 src/tools/check_staged.py --all   # personal data leak check
python3 src/tools/make_shareable.py       # build the public package with its audit
```

Three rules these checks enforce so that nobody has to remember them:

- **Input parity.** A capability appears in the core and gets an entry point in
  the CLI and the web *at the same time*. The map lives in
  `src/scholion/contract.py`; a route without a command fails
  `tests/test_parity.py`. Exceptions are listed by name, with a reason.
- **The public contract may grow and may not shrink.** Command names, top-level
  fields in `--json`, profile file names. Narrowing requires an explicit
  `python3 src/tools/check_compat.py --accept` and a CHANGELOG entry.
- **Assistant rules live in one file.** The canon is `ASSISTANT-RULES.md`;
  `src/tools/sync_rules.py` copies it into the skill editions. Edit the canon,
  never the copy.

Tests run against a synthetic fixture with `SCHOLION_OFFLINE=1` and a stub genome
directory — they never touch a real profile or a real VCF.

## What never goes into the repository

Three bans follow from source licences and hold without exception. The code is
Apache-2.0 and the knowledge base is CC BY 4.0; both permit commercial use, so
anything more restrictive is physically incompatible and is fetched at runtime
instead.

- **PGS model weights.** The PGS Catalog has no single licence — it is declared
  inside each score file, and some are CC BY-NC-ND. Only public model
  identifiers are stored; the user downloads the weights.
- **ATC codes.** The WHO centre explicitly forbids copying and distribution for
  commercial purposes. They are fetched at runtime through RxClass.
- **SNOMED CT.** Requires an Affiliate licence.

**LOINC may be embedded**, but adding codes obliges you to ship the verbatim
notice — its text goes into `NOTICE` in the same commit.

Personal data never reaches git by construction: `.gitignore`, the pre-commit
hook and the sanitizer each block it independently.

## Demo profile

`demo/profile/` is a synthetic profile of a fictional person, built by
`src/tools/make_demo_profile.py`. It exists so the product can be shown without
showing anyone's medical record, and so screenshots have something to show. Every
file declares itself synthetic in `_meta` — without that declaration the build
audit rejects it.

## A published version is frozen

`VERSION` must be bumped for any change that reaches the package — and
`CHANGELOG.md` reaches it, while `ouroboros_plugin/` does not. Do not answer that
from memory: `python3 src/tools/check_published.py --check` reads what travels out
of `pyproject.toml`, asks the registry, and compares. `publish_share.sh` runs it
before building and records the result after publishing.

## Adding a surface

Any new way in — a protocol server, a plugin for another host, an API — is not
finished until four things are true: `contract.access()` describes it, derived
from the build; `docs/CONNECTING-AN-AGENT.md` names it; it says who it is for
(`agent_surface: False` for a human door, not omission); and the safety canon
reaches whoever speaks through it — `sch_rules` is a tool for exactly that
reason, because the tool interface carries no instruction with it.
`tests/test_an_agent_can_ask_how_to_connect.py` enumerates the doors out of
`access()`, so a fifth one fails the build the day it is added. Reasoning in
`docs/DEVELOPMENT.md`.

## Release notes

Written for somebody who has never seen this repository. **New capabilities,
fixed defects, and what either means for data already stored** — nothing about
who wrote it, which attempt came first, what it taught anybody, internal task
numbers, commit hashes, paths in this tree, or whose machine anything ran on.
Those belong in `CHANGELOG.private.md` and in commit messages, and a reader who
wants them knows where to look. A defect is described by the wrong answer
somebody could have received, not by its cause in the code.

Enforced by `tests/test_release_notes_exist.py` and checked by
`publish_share.sh` before it builds. The full convention, with the reasoning and
the list of markers, is in `docs/DEVELOPMENT.md`.

## Conventions

- PGS and longevity statements always carry their caveats: mostly European
  cohorts, a percentile is not a probability, a literature catalogue is not a
  risk estimate.
- Chromosome sorting: `order.get(c, int(c))` breaks on `X` — use explicit
  branches.
- **One name, one role, in the skill files.** `SKILL.md` is always the short
  entry a model loads first — frontmatter, under 12 KB. The long text is always
  `INSTRUCTION.md`, and it carries no frontmatter. `*.owner.*` never leaves the
  source repository. Until 16.08.2026 both roles were called `SKILL.md` and the
  files under that name ranged from 5 KB to 115 KB; nothing failed, which is
  exactly why it had to be split — a wrong copy produces a quietly wrong result,
  not an error. Two tests hold the rule (`tests/test_skill_editions.py`).
- Shell scripts that ship must run on the bash macOS provides — **3.2, from
  2007**. No `mapfile`, no associative arrays, no `${arr[@]}` on an empty array
  under `set -u`. A tool that has to be installed before it can run is useless
  exactly when it is needed; the same reason the core carries no third-party
  dependencies.
- On macOS `TMPDIR` lives under `/var`, which is a symlink to `/private/var`.
  Code that resolves a path handed to it through the environment returns the
  resolved form, so a test comparing that against a bare `tempfile.mkdtemp()`
  passes on Linux and fails on macOS. Resolve the temporary root in `setUp`.
  A macOS-only failure of this shape reproduces on Linux: point `TMPDIR` at a
  symlink and run again.
- **pico.css is the base style layer for every HTML surface.** Vendored
  locally — `web/pico.min.css`, no CDN, no build step, served by `server.py`
  the same way as `chart.min.js` — so the interface keeps working with no
  network reachable at all. It fills in sane defaults for elements not
  already hand-styled; every existing custom class keeps exactly the rule it
  had, because a class selector always outranks Pico's element-level default.
  Adopted 18.08.2026 when `web/index.html` moved onto it; the next HTML
  surface starts there directly instead of re-deciding.
- **A working copy reached through a mount that forbids `unlink` needs
  `git --no-optional-locks` for every read.** A plain `git status` creates
  `.git/index.lock` and then cannot remove it, so the NEXT git command dies on
  `Unable to create '.git/index.lock': File exists` — and the failure surfaces
  one command later than its cause, which is why it looked twice like `commit`
  being impossible. It is not: `git commit` itself works there. Read state with
  `git --no-optional-locks status|log|diff`, and before and after anything that
  writes, move what is left — `index.lock`, `HEAD.lock`,
  `objects/maintenance.lock`, `objects/*/tmp_obj_*` — out of `.git` with `mv`,
  not `rm`: such a mount forbids deleting a file and allows renaming one.
  Learned 22.08.2026, after two sessions concluded the wrong thing from the
  same message.
