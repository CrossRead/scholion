# Version control and the changelog — how this is built

_Introduced 14.08.2026. A short runbook: what is versioned, how a version is
released, and what must not be done._

## What is under version control and what is not

Under git — the **portable layer**: `src/` (the engine, the knowledge base,
processing scripts, tools, the skill), `ouroboros_plugin/`, `share/`, `docs/`,
`tests/`, the top-level `*.md`. This repository can be shown to anyone.

Outside git — the **personal layer**: `profile/` (lab results, prescriptions,
genotypes), `genome/` (the VCF and everything derived from it), `_backups/`,
PDF/DOCX report forms, run logs. No edit history is kept for personal data, and
that is a deliberate choice: the cost of a mistake is asymmetric. A code leak is
an annoyance; a leaked medical record is irreversible, and deleting the file
does not clean it out of git history.

**Why this is written down in such detail.** Before 14.08.2026 there was **no
`profile/` entry** in `.gitignore`. There was no repository either, so nothing
happened — but a single `git init` plus `git add -A` would have put everything
into history.

## Two repositories: private and public

**The private one is private, always.** Besides the code it holds
`src/skill/SKILL.md` with the owner's clinical key: diplotypes, phenotypes,
caveats about particular drugs. That is neither "lab results" nor a VCF, but it
is personal genetic data. The repository is safe in the sense that personal data
will not leak by accident, but it is not de-identified and it cannot be public.

**The public one is a separate folder with its own history.** It is built from
the private one by the `make_shareable.py` sanitiser and passes an automatic
audit. It is exactly the artifact that was already being handed to colleagues,
now with versions and a history.

```
Scholion-project-files/   ← private repository
Scholion-SHARE/           ← public repository (generated)
```

Publishing takes one command:

```bash
bash src/tools/publish_share.sh              # build → audit → commit → push
bash src/tools/publish_share.sh --dry-run    # show the plan, change nothing
bash src/tools/publish_share.sh --no-push    # stop at the local commit
```

The addresses live in `.publish.conf` next to the project (the file is in
`.gitignore`):

```
PUBLIC_REMOTE=git@github.com:<you>/scholion.git
PUBLIC_REMOTE_MIRROR=git@gitverse.ru:<you>/scholion.git
```

Two addresses — a push goes to both at once. The alternative, if you would
rather not keep both keys, is to set up mirroring with auto-sync on GitVerse and
push to one address only.

**Where a build that cannot delete puts the old one.** On a filesystem that
refuses `unlink` — the bridge to a remote session, a network volume, or (before
the move recorded under Caveats below) iCloud mid-eviction — the builder cannot
empty the delivery folder. It does not overwrite in
place, because overwriting cannot say «this file is no longer part of the
package»: a file dropped from the copy list would survive under its old name and
travel to the recipient. Instead the previous build is moved to a single
directory **beside** the package —

```
Scholion-SHARE/          ← the package
Scholion-SHARE._stale/   ← the previous build, only if it could not be deleted
```

— and the next build begins by trying to delete that directory. Nothing
accumulates unless the refusal is permanent. It used to be moved aside *inside*
the delivery folder, which meant zipping the folder shipped two versions and the
package's own ignore rules — all anchored to the delivery folder's name — did not
cover `profile._stale3/` with the recipient's filled-in templates. Ninety-one such
directories had piled up before it was noticed.

If you see `Scholion-SHARE._stale/` next to the package, the build could not
remove the previous one and said so in its output. Delete it by hand; nothing in
it is needed.

**What makes publishing reproducible.** The package is rebuilt from scratch: the
target folder is cleared (except `.git`), and the contents of the repository
become EXACTLY what the sanitiser emitted. This cures a long-standing trap — the
builder overwrites files but deletes nothing, so a file that had been dropped
from the copy list used to sit there silently and travel to the recipient
anyway. Now it disappears, and git shows that as a deletion. On top of that, the
script refuses to publish from a dirty working tree: otherwise the package
carries edits that exist in no version at all, and reproducing it later becomes
impossible.

The public repository gets its own `.gitignore` excluding
`profile/*` and `genome/*` at the delivery root: the recipient fills the templates
with their own data in the same places, and a single `git add -A` would carry
**their** lab results into history. The mistake we caught on our own side must
not be repeated on theirs.

## Three lines of defence

1. **`.gitignore`** — against carelessness.
2. **The `pre-commit` hook** — against `git add -f` and against a file that ended
   up in the wrong folder. It blocks by path (profile directories from the root,
   genomic formats, PDF/DOCX/logs) and by content — if `.personal_patterns` is
   filled in.
3. **The `pre-push` hook** — against `--no-verify` and against history. It checks
   paths in **all commits that are actually going out** to this remote, not only
   in the last one: a file that was added and later deleted has not gone anywhere
   from history and will travel out with it.

Both hooks are installed by one command: `bash src/tools/install_hooks.sh`

`.personal_patterns` lives next to the project, contains the owner's identifiers
(sample number, surname, email) and **never enters git** itself — otherwise the
point is lost. If the file is absent, the content check is skipped with a
warning, not silently.

To check without waiting for a commit:

```bash
python3 src/tools/check_staged.py --all     # the whole tree
python3 src/tools/check_push.py --remote origin
```

`.git/hooks/` is not versioned, so after cloning onto another machine
`install_hooks.sh` has to be run again. The hook sources are in the repository,
so there is nothing that can drift apart.

## The numbering was reset at publication — read this before touching a tag

On 16.08.2026 the project was published for the first time, as **`0.1.0`**. By
that day the internal numbering had reached `2.24.0`.

**Why it was reset.** A version number is a promise about compatibility: a person
holding the previous version knows what moving to this one does to their data and
their commands. Nobody outside had run any version before publication, so the
promise had nothing behind it, and `2.24.0` was measuring something else — how
much had been built. That is not what the number is for.

**What that leaves behind, and why it matters.** 32 tags naming versions that will
be named again. The published numbering will grow, and one day there will be a
second `v2.24.0` — a different commit, a different system, the same string. A tag
is precisely what a person reaches for to reproduce a state, so two commits under
one name is not cosmetic.

**How it is kept apart.** Git refs are paths. The pre-publication tags live in a
namespace of their own:

```
pre-0.1.0/v1.0.0 … pre-0.1.0/v2.24.0
```

`refs/tags/pre-0.1.0/v2.24.0` and `refs/tags/v2.24.0` are different refs and
cannot collide however far the numbering climbs. Nothing was rewritten and no
commit was deleted.

Three rules follow, and they hold without exception:

1. **Never create a bare tag named `pre-0.1.0`.** Git cannot hold a ref that is
   both a file and a directory; that one tag would make the whole namespace
   unwritable.
2. **A plain `vX.Y.Z` tag belongs only on a commit at or after `v0.1.0`.** Checked
   by `tests/test_repo_hygiene.py`, which can only fail on the actual mistake — a
   legitimate future `v2.24.0` sits after `v0.1.0` and passes.
3. **Nothing from before `0.1.0` is published.** This costs nothing to hold,
   because the public repository is not a copy of this one: it is generated from
   the sanitised package by `publish_share.sh`, which runs `git init` in the
   delivery folder and makes exactly one commit and one tag. The private history
   has never had a route into it. The development journal stays in
   `CHANGELOG.pre-0.1.0.md`, on the builder's private list; `CHANGELOG.md` is the
   published one and starts at `v0.1.0`.

The same applies to PyPI, where the consequence is worse than confusion: pip
installs the highest version it finds, so a `2.24.0` uploaded once would shadow
`0.1.0` forever — and PyPI does not allow a version number to be reused after a
release is deleted, which would make a future, real `2.24.0` unpublishable.
**Only `0.1.0` and what follows it is ever uploaded.**

**What `1.0.0` will mean here.** Not a count of finished capabilities — a number
of people who have run this on their own medical data and reported what happened.
Until then the rule that the public contract may grow and may not shrink
(`check_compat.py`) is internal discipline, and the README says so in those words
rather than implying a promise to outsiders.

## Release policy

A number of the form `X.Y.Z`, with the date in the changelog entry heading:
`## v1.0.0 — 14.08.2026`. **The unique key of an entry is the number; the date is
for reference.** Work happens unevenly: one day several versions ship, another
day none, so the date cannot be the key — though it still stitches entries to
dated documents and to the profile.

### What counts as a version at all

**A tag is not placed on every commit.** You can commit as often and as finely as
you like. A version appears when what you can **refer to** changes: a package is
published, a layer is added, a conclusion changes or is retracted. Edits made
along the way — script drafts, intermediate states — live as commits and get no
version.

A tag is a promise that the state is reproducible. That is why only a clean tree
that passes the package audit can be tagged.

### How to choose the number

| Digit | When | Examples |
|---|---|---|
| **PATCH** `1.0.x` | No conclusion changes, or a fix — including one that finally surfaces something that already existed but was not read out anywhere | Parser fix, wording clarified, a new script with no new conclusions, documentation edit, a hand-curated field that existed and is now rendered |
| **MINOR** `1.x.0` | An important new functional capability arrives; the previous conclusions remain true | Sleep-phase layer, callability, LoF scan, an extension of the locus catalogue |
| **MAJOR** `x.0.0` | Previous conclusions can no longer be read the old way | Genome build change, incompatible profile schema, a method that overrides what has already been said |

**A fix stays PATCH even when it changes what one particular record shows.**
Reading and finally rendering a field that already existed — `safety_flags`,
`v0.1.3` — is a fix to a gap, not a new capability, even though it can move a
specific verdict from `moderate` to `high` for whoever has filled the field in.
MINOR is for when what the system can even *represent* grows — a new data
source, a new layer, a new class of finding — not for every change that could,
for someone, change an output. The bar is the size of the capability, not
whether a conclusion can technically move.

**A rule specific to this project — a break in the series.** An edit to
`src/scholion/knowledge/` that changes values on the same input data is
**MINOR at minimum**, even if physically it is one line in a JSON file. A PRS
model changed, a clinical threshold was corrected, the catalogue was refined —
the numbers before and after are not comparable, and bumping PATCH silently is
not allowed. If the broken series belongs to an indicator that has already been
used in a clinical decision, it is **MAJOR**.

The practical consequence: `--bump patch` is the default, but if the generator
emitted a "break in the series" section, the default is not the way to go —
`--bump minor` at minimum.

**Accepting a new form of an INPUT is not a break in the series.** Added
17.08.2026, on `v0.2.2`, because the rule above read as though it covered a case
it should not. Teaching the unit gateway that an American laboratory writes
`ng/dL` changes what the system will accept; it changes no value already stored
and no answer already given, because a refused import wrote nothing. The two
directions are not alike and were being counted alike:

* a coefficient, a threshold, a PRS model, a reference range, a locus and its
  coordinates — **MINOR at minimum, and MAJOR if a clinical decision already
  rests on it**. These make the numbers before and after incomparable. The DPYD
  panel going from two variants to seven (`v0.2.0`) is this case, and was
  numbered so;
* a new spelling, unit form, alias or synonym that the layer will now recognise
  — **PATCH**, provided the test that proves it also shows nothing previously
  stored moved.

The discriminator is one question, and it is worth asking out loud rather than
guessing from the diff: **does any answer this system has already given read
differently now?** If yes, it is a break in the series whatever the change looks
like in the file. If no, it is a wider door.

The same reading applies below `1.0.0` to a command that adds no new kind of
conclusion. `scholion doc` prints a document that already shipped; it draws
nothing, decides nothing, and its absence was a broken road rather than a missing
capability. Above `1.0.0` this would still be MINOR — there the contract is a
promise about what exists, not only about what it concludes.

### The pre-release check and one writing session

Two rules, both derived from mistakes made on 14.08.2026.

**Before tagging, look at the full list of files, not only at your own edits.**
`git add -A` sweeps up whatever parallel work has put there too. That is how an
unfinished module travelled silently into a release, and the only way it was
noticed was the file list in the output of `git commit`. The minimum is
`git status --short` and `git diff --stat <previous tag>` before writing the
changelog entry.

**Release files are written by one session at a time.** `VERSION`, both
`CHANGELOG` files and the tags all answer one question — "what version is this
now". Code can be edited in parallel as much as you like, git will merge it;
these four entities, written in parallel, are guaranteed to give four different
answers. That is exactly what happened: the tags said `v1.0.1`, `VERSION` said
`1.1.0`, the public changelog said `v1.0.2`, and the private one said "Not
released". Reconciling that is manual and takes time; not creating it is easier.

**If the work is not finished, there is no tag.** There is a commit, there is no
version. For that case the changelog gets a `## Not released` section, which is
renamed to a number at release time. A version is a promise that the state is
reproducible and described in full.

### Several versions in one day

Normal and expected. `v1.1.0 — 14.08.2026` followed by `v1.1.1 — 14.08.2026` is a
correct pair. The digit is chosen per version, not for the day as a whole: three
fixes in a row give `1.0.1`, `1.0.2`, `1.0.3`, and a new layer wedged between
them gives `1.1.0`.

The reverse is normal too: a week of work with no new conclusion yields no
version at all. The number of versions measures change, not effort.

## How to release a version

```bash
cd /path/to/Scholion-project-files

# 1. See what has accumulated, without writing anything
python3 src/tools/release_notes.py

# 2. Choose the digit from the table above and write the draft.
#    If the output has a "break in the series" section — patch is not allowed.
python3 src/tools/release_notes.py --bump minor --write
#    or the full number:  --version 1.2.0

# 3. Fill in the three sections in CHANGELOG.md marked FILL IN:
#    "what this changes in the conclusions", "what is retracted",
#    "what needs recomputing".
#    That is the substance of the entry; the file list is the reference tail.

# 4. Commit and tag
git add -A
git commit -m "release v1.1.0"        # the hook will check nothing personal is there
git tag v1.1.0

# 5. Publish the de-identified package (see the two-repositories section)
bash src/tools/publish_share.sh
```

To compare against something other than the last tag: `--from v1.0.0 --to HEAD`

`--write` updates both `CHANGELOG.md` and the `VERSION` file, from which the next
number is computed and which `publish_share.sh` picks up for the public
repository's tag.

## What must be in a changelog entry

**The three curated sections matter more than the whole file list.** The
changelog answers the question "what became known and what changed in the
interpretation", not "which files were touched". If a version changes nothing in
the conclusions, write exactly that.

**Do not skip the "what is retracted" section.** Retracting an earlier statement
is worth more than a new finding: the old conclusion keeps living in the
documents and in people's heads until it is explicitly withdrawn. The order is
the same as in the list of recorded corrections in the project index.

**Edits to `src/scholion/knowledge/` are a break in the series.** They change the
result on the same input data: a PRS model changed, the locus catalogue grew, a
clinical threshold was corrected. Values before and after cannot be put on the
same chart without a caveat. `release_notes.py` moves such files into a separate
section automatically and shows what exactly grew (`loci: 38 → 44 (+6)`).

## Caveats

- **The repository no longer lives in iCloud Drive.** It moved to a plain local
  disk (`~/Projects`) on 17.08.2026: the package build was failing there with
  `OSError: Resource deadlock avoided`, and identical `(mtime, size)` after a
  reverted file made Python reuse the mutated version's stale bytecode. The
  former iCloud copy is kept, marked archival, and is not used — see `CLAUDE.md`.
  Source data folders (raw sequencing, lab exports) can still live in iCloud;
  only the two git repositories moved, and each is named in
  `profile/sources.json` rather than hard-coded, so a future move does not
  require hunting down the path in prose.
- **Writing git operations from a Claude cloud session are impossible, and not
  just "sometimes".** The bridge to the device cannot delete files, and git
  creates `.git/index.lock` and is obliged to remove it on completion. It cannot
  remove it — you get `unable to unlink index.lock: Operation not permitted`, the
  lock stays, and it breaks the next command. Verified 14.08.2026. Hence the
  rule: `add`, `commit`, `tag`, `merge` are run by the owner in a terminal, and
  the assistant prepares the text of the command. Reading (`git log`, `git show`,
  `git diff` without refreshing the index) works over the bridge.
- If a lock is left behind after a failed attempt anyway: `rm -f .git/index.lock`
  in a terminal, and from a Claude session only `mv .git/index.lock _to_delete/`.
- **Do not pipe git output into `head` over the bridge.** `head` closes the pipe,
  git receives SIGPIPE and dies without removing the lock. Write to a file in
  full, then read it.
- The de-identified package (`make_shareable.py`) is built from the working tree,
  not from a tag. A release package has to be built on a clean tree — otherwise
  uncommitted edits that exist in no version travel into it.
