# Targeted checks and candidate evidence

The five levels in [DEVELOPMENT.md](DEVELOPMENT.md) remain separate. A fast
component check does not certify a browser session, an installed wheel or the
CLI/MCP/Plugin/Web paths. The default `run_tests.sh` and CI still discover every
test. No test is removed, disabled or deduplicated by this selector.

## Selecting a development check

```sh
python3 src/tools/test_plan.py --changed src/scholion/web/measurements.js --out /tmp/measurement-plan.json
python3 src/tools/test_plan.py --changed src/scholion/web/measurements.js --run
python3 src/tools/test_plan.py --since HEAD --run --out /tmp/working-tree-check.json
```

`--since` includes tracked changes relative to that revision, the staging area,
working edits and untracked files in the actual Git checkout. In an archive or
an isolated snapshot without Git, pass repository-relative paths with
`--changed`. With several unpublished stages, those paths describe the current
edit only.

The narrow boundary is the shared gene, measurement, system-view and lifecycle
assets, reviewed result producers listed below, plus Python tests and their helpers. Dependencies include direct and
relative imports, inherited test modules, literal file references and transitive
helpers. Shared assets also select all tests referring to the containing page,
so links, delegation and styles remain covered. Dynamic test imports are always
included. The plan explains each selected dependency.

This is deliberately conservative, not a general static proof of every Python or
JavaScript dependency. Unclassified core code, catalogues, build configuration, fixtures,
unknown assets, removed files or a change with no matching test require full
discovery. Syntax errors stop planning. Adding a new narrow boundary requires
reviewing its consumers and a selection regression first. Runtime imports or
new nonliteral file dependencies must not be assumed detectable from text.

Run this check at the end of each development block that changes a registered
result, its inputs or one of its consumers. `--run` verifies the registry,
runs semantic tests and runs the affected interface scenarios in one command.
The checks use synthetic data, offline mode and a stub genome. A failure
returns a nonzero status. An unknown dependency selects full test discovery
and all shared interface scenarios. The JSON records which steps ran and their
results. Browser and installed-package acceptance are separate checks.

## Reviewed result paths

Run `python3 src/tools/check_registry.py` to see the producer files, semantic
tests and executable interface scenarios across the eleven reviewed result
families. Every CLI/HTTP parity route has a coverage disposition. A new route
without a disposition fails the check. Shared scenarios compare the supported
entry points. Dedicated tests cover stored outcomes and operation-specific
failures. Boundary checks identify operations that depend on an external
service or a native dialog. Run the listed semantic test modules and the
interface driver to collect results. Registry membership alone says nothing
about a run, the installed wheel, or native host acceptance.

Changes to the exact variant resolution, PGS validation and review-history
modules have reviewed development selections. A registered producer outside
that narrow list still requests full discovery. The selector includes named
family tests and Python imports of reviewed producers, then walks test
dependencies. The report's `interface_commands` lists the affected shared scenarios by CLI
command. The GitHub test workflow also runs all shared interface scenarios on
pull requests alongside the test matrix, so development review catches
regressions even if a contributor skips the local command. For example:

```sh
python3 src/tools/test_plan.py --changed src/scholion/variant_readings.py --run --out /tmp/reading-check.json
```

Use `candidate_evidence.py` when reusing a previous result. Bind installed
checks to the actual wheel. Keep the full source and built-package gates for
release acceptance.

## Recording and checking evidence

```sh
python3 src/tools/candidate_evidence.py record --out /tmp/component-check.json --level 2 -- python3 src/tools/run_tests.py --suite-only tests.test_view_lifecycle
python3 src/tools/candidate_evidence.py verify /tmp/component-check.json
```

Recording captures the exact command, level, interpreter and available tool
binaries, installed Python distribution versions and metadata digests, platform,
UTC day, known execution switches, elapsed time, exit code,
a digest of the test-related inherited environment (values are not disclosed),
the invoked executable, and a hashed log. It inventories development inputs before and after the run:
source, tests, fixtures, knowledge, documentation, demo data, public skill and
plugin files, workflows, backlog, privacy-pattern digests and root metadata. File additions, deletions and executable
bits count; unchanged size or modification time is insufficient. Personal profile
and generated report directories are excluded. An explicit `--artifact` binds a
wheel or other external file by SHA-256 before and after the check.

Evidence files are append-only. A failed, interrupted or changed-input run cannot
be reused. Verification also refuses a different root, day, interpreter, tool,
execution setting, artifact or altered/missing log. This strict default may rerun
more than necessary; it cannot quietly turn an old green result into a new pass.
Records are local engineering evidence, not cryptographically signed attestations.
They contain no test output in JSON; the adjacent local log may contain output.
Do not record commands containing credentials or personal arguments.

The verifier never bypasses `run_tests.sh`, CI or publication. It reports only the
recorded scope and its existing skips. A source result is not an installed-package
result; use a separate record from the sanitized tree and explicit wheel identity.
For externally performed browser/native checks, retain their original reports and
input/artifact manifests; do not relabel a file comparison as an executed scenario.
A release ledger must name evidence or an explicit limitation at each of the five
levels. Missing Windows, native printing or AI-host checks remain missing.

## Measuring cost without removing coverage

Compare targeted and full unittest runs on the same frozen tree, interpreter and
synthetic inputs. Report test counts and skip counts with durations. Separately
report the complete acceptance gate, which also includes preflight, compatibility,
metadata, lint, types, oldest Python and statement reach. Do not compare an
ordinary targeted run to an instrumented full run as a like-for-like speedup.

The inventory tool reports duplicate bodies as review candidates, never as proof
of duplicate scenarios. Preserve distinct fixtures, public interfaces, failure
modes and portability checks. The full suite remains the authority for unique
checks and module reach.
