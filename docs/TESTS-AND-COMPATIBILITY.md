# Automated tests and backward compatibility

_Introduced 14.08.2026, when the project stopped being personal. A short runbook:
what is checked, what holds it together, and what to do when a check fails._

## Why this appeared

While a project is used by one person, a broken command is discovered the same
day. As soon as the package travels outside, what breaks is not "mine" but
someone else's, and that person does not know where to look and cannot tell "the
function was removed" from "I ran it wrong". On top of that a second class of
user appeared — the assistant: it parses `--json` by field name, and a renamed
field means a capability has disappeared.

Hence two checks: **tests** answer the question "does it work", and the
**contract check** answers "have we broken something already in use".

## Running them

```bash
./run_tests.sh                       # everything: tests + the compatibility contract
python3 src/tools/check_compat.py    # compatibility only
python3 -m unittest discover -s tests -t . -v   # tests only, verbose
```

Nothing needs installing for the tests themselves: they run on the Python
standard library. (The package has one declared dependency, `pdfplumber`,
for reading laboratory PDFs — the suite does not need it.)
A run takes about twenty seconds.

**The tests do not read the personal profile.** `SCHOLION_PROFILE_DIR` is forced to
point at `tests/fixtures/profile` — synthetic data chosen so that the checks
trigger. Writing commands are tested on a copy of the fixture in a temporary
folder, so even the fixture itself is not modified.

## What is checked

**1. Input parity** (`tests/test_parity.py`). Everything the web can do, the
command line can do too. The map "API route → CLI command" lives in
`src/scholion/contract.py`; the test fails if the server gained a route that is
in neither the map nor the exclusion list. Exclusions are named and carry a
reason — there are no silent ones.

The rule this holds up: **a capability appears in the core and gets an entry point
in the CLI and in the web at the same time.** While the rule lived only in a
document, it was violated silently: the summary, "Second opinion" and the
by-system health index existed only in the tabs, and the assistant could not see
them.

**2. Smoke run** (`tests/test_cli_smoke.py`). For every command: exit code 0,
`--json` parses, no traceback. Separately — the same sweep on an **empty
profile**: a new user has no data, and the application is obliged to answer in
words "there is no data" rather than crash.

**3. Safety rules for conclusions** (`tests/test_safety_rules.py`). The promises
the system makes to the user are pinned down by machine: an indicator with no
reference range in the report form cannot become a "deviation"; biological age is
not computed from an incomplete panel; the PhenoAge formula has no sex term, so
changing sex in the profile has no right to move the result; the signs of the
coefficients are not swapped (inflammation ages, albumin rejuvenates); a clinical
conclusion comes with a caveat.

**4. Arithmetic** (`tests/test_math.py`). Quantities with an externally
verifiable answer: the combinatorial sensitivity bound for n-of-1 (4 blocks →
minimum 0.167, significance unreachable in principle), the behaviour of the
permutation test, the rule that excludes a protocol-violation day together with
the next one.

**5. Backward compatibility** (`tests/test_compat.py` + `check_compat.py`).

**6. How far the suite reaches into the code** (`check_test_reach.py` +
`test_reach_baseline.json`). Not the same question as any of the above, and not
the same question as `check_coverage.py` next to it — that one asks what the
build KNOWS, this one asks which lines of `src/scholion` the suite actually
EXECUTES.

It exists because a review counted a thousand green tests and concluded the code
was well covered. The number that had never been taken was 69.9%, and the modules
at the bottom of it were not peripheral: `provenance.py`, which implements the
sentence the product is sold on, stood at 12.8%; `tabixlite.py`, the VCF reader
used whenever `pysam` is absent and therefore the one most installations run,
stood at 35.4%. Nothing in the suite could have said so, because nothing was
counting.

The measurement is built out of the standard library — this project has no
dependencies, and `coverage` is one. It uses the interpreter's own coverage hook
on Python 3.12 and later and `sys.settrace` below that, and it collects the
twenty-one test files that run the CLI in a real SUBPROCESS: measured without
them the answer is 54.3% rather than 69.9%, which is the difference between
believing `reconcile.py` is dead code and knowing it is half exercised.

The gate is a baseline rather than a target, for the same reason as the language
one: a threshold set at 90% fails on Monday and is switched off on Tuesday, and a
gate that is off looks exactly like a guarantee. `--strict` fails when a module
falls below its accepted line, or when a module appears that nobody has reviewed.
Raising it is `--accept`, and the diff is then somebody's to justify.

Two properties of the tool are themselves tested
(`tests/test_the_reach_tool_and_the_runner_agree.py`), because a measurement's
failure mode is a confident zero: that it measures the same run `run_tests.sh`
performs — the two spellings of that environment are compared mechanically — and
that its line counter is right about the cases that are easy to get wrong, such
as a module docstring being executable and a function docstring not being.

## The public contract

Three things count as the contract:

1. **CLI command names** — a command that disappears breaks a shortcut and the
   skill;
2. **top-level fields in `--json`** — a field that disappears breaks parsing;
3. **the names of profile files** that the core reads.

The rule is one-directional: **adding is allowed, removing is not.** A new command
and a new field do not break compatibility and require nothing. Removal and
renaming always do.

The reference is `tests/contracts/public_contract.json`. It is not edited by
hand:

```bash
python3 src/tools/check_compat.py --accept
```

`--accept` prints exactly what is being accepted and rewrites the reference. This
is a deliberate act: an accepted narrowing must land in `CHANGELOG.md` in the
"what is retracted" section and must raise the major version (see
`docs/VERSIONING.md`).

## When the checks run

- **By hand** — `./run_tests.sh` before handing anything outside.
- **Automatically** — the `pre-push` hook (after the personal-data leak check).
  Installed by `bash src/tools/install_hooks.sh`.
- Emergency bypass — `SCHOLION_SKIP_TESTS=1 git push`. Deliberately and rarely: the
  personal-data leak check still runs regardless.
- The reach measurement is the last step of `./run_tests.sh` and runs the suite a
  second time under the coverage hook, which costs about a minute and a half.
  `SCHOLION_SKIP_REACH=1` skips it for a tight edit loop; a run narrowed to one
  module (`./run_tests.sh tests.test_x`) skips it on its own, because the reach of
  a fraction of the suite cannot be compared against a baseline taken from all of
  it.

  It runs here rather than in CI on purpose. The matrix in
  `.github/workflows/tests.yml` lives in the public repository and is reached only
  through `publish_share.sh`, so a gate there would answer after publication. This
  is the only place that answers before it.

The tests travel into the public package together with the code. The recipient
must be able to verify their own build without access to our repository —
otherwise "verified" stays an internal claim of ours.

## What to do when it fails

| What failed | What it means |
|---|---|
| `test_every_route_is_described` | The web gained a capability unavailable from the CLI. Add the command and a line to `PARITY` — or record the reason in `NO_CLI`. |
| `test_nothing_went_missing` | The public contract narrowed. Restore the field/command, or accept it deliberately via `--accept` plus an entry in the CHANGELOG. |
| `test_no_range_means_no_flag` | Someone substituted a "generally accepted norm". That manufactures false deviations — the reference range is taken only from the user's own report form. |
| `test_sex_does_not_influence_the_result` | The PhenoAge formula was edited. Levine 2018 has no sex term. |
| `test_empty_profile_answers_honestly` | A command crashes for a new user. Empty data is a legitimate state, not an error. |
| `check_test_reach.py --strict` | A module lost reach, or a new one arrived with none. Add the tests, or accept the number deliberately with `--accept` and say why in the commit. |
| `test_every_module_in_the_tree_has_an_accepted_number` | A module was added to `src/scholion` and nobody decided how well it is tested. |
| `test_the_copyright_line_passes` and its neighbours | The single exception to the personal-data check — the authorship line in the licence — was touched. It must not be widened: see below. |

## Legal conditions are checked by machine

`tests/test_licensing.py` closes a class of error that the next release does not
fix: a package that shipped without `LICENSE` has already shipped without rights,
and a verbatim source notice lost during the build has already been violated at
the recipient's side.

Three things are checked:

- **the legal files exist and are non-empty** — `LICENSE`, `LICENSE-DATA`,
  `NOTICE`, `ATTRIBUTION.md`, `DISCLAIMER.md`;
- **every path named in them actually exists.** That is how a defect was found:
  the files had been prepared for a future package name and referred to
  `src/scholion/`, which was not in the repository;
- **verbatim conditions are present exactly when the data is used.** The check
  runs from the fact in the repository to the text: if the knowledge base
  contains LOINC codes, `NOTICE` must contain the Regenstrief notice word for
  word. That is precisely how it was discovered that the codes had appeared
  before the notice.

Separately, the machine checks the PROHIBITIONS declared in `ATTRIBUTION.md`: the
knowledge base must contain no ATC codes (WHO centre terms) and no PGS model
weights (some scores are under CC BY-NC-ND). The claim "we do not store this" is
worth exactly as much as the check that verifies it.

## The single exception to the personal-data check

The `src/tools/check_staged.py` check treats the owner's name as personal data
and stops the commit. For medical files that is correct; for a licence it is not:
authorship in `NOTICE` is published on purpose, and Apache-2.0 requires it.

The exception is made **at the level of a line, not a file**, and is held up by
the test `tests/test_privacy_guard.py`:

- only a line containing `Copyright` / `©` / `(c)` passes;
- the name in any other line of the same file still blocks the commit — one
  lawful line does not justify the rest of the text;
- a line where the name sits next to an email, a phone number, a sample number or
  a date is not treated as an exception: that is no longer authorship alone;
- the exception function is not given the file name at all, so bypassing the
  check by naming a file `LICENSE` is impossible by construction, not by
  agreement.

This concession should not be widened. Everything else personal — numbers,
emails, sample identifiers — blocks the commit without exception.

## What these tests do not do

They do not check the clinical correctness of the conclusions and they do not
replace a doctor. They check that the system behaves the way it promised: it does
not invent what is missing, it does not lose an interface, and it answers the
same way through any entry point.
