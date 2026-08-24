#!/usr/bin/env bash
# The full test run. Installs nothing: the standard library only.
# The tests work on a synthetic fixture (tests/fixtures/profile) — they neither
# read nor change anyone's real profile.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="src:tests${PYTHONPATH:+:$PYTHONPATH}"
export SCHOLION_PROFILE_DIR="$ROOT/tests/fixtures/profile"
export SCHOLION_OFFLINE=1
# The output language is pinned rather than inherited: with SCHOLION_LANG=ru in
# the shell a developer would otherwise get a different run from CI, and a test
# about language would pass or fail by accident of the terminal.
export SCHOLION_LANG=en
# The genome is switched off explicitly: otherwise, on the owner's machine, the
# run would reach for a real VCF of tens of gigabytes (in iCloud that also means
# downloading the file), and the result would depend on whose genome happens to
# lie next to it. The tests are obliged to check the BEHAVIOUR of "the database
# is not connected", which is the same for everybody.
export SCHOLION_GENOME_VCF="$ROOT/tests/fixtures/no-such-file.vcf.gz"
export SCHOLION_GENOME_DIR="$ROOT/tests/fixtures/no-genome"
# Guard against the usual "command + comment on one line" paste: in interactive
# zsh a `#` does NOT start a comment, and the words after the hash arrive here as
# arguments. unittest answers with its usage text, which does not look like "the
# tests never ran at all" and is easily mistaken for a successful run. So the
# refusal is spelled out in words.
for a in "$@"; do
  case "$a" in
    -*|tests.*|tests/*) ;;
    *) echo "⚠ the argument «$a» does not look like a unittest flag."
       echo "  It looks like the command was pasted together with its comment: in"
       echo "  interactive zsh the hash does not start a comment. Run it without"
       echo "  the tail after #."
       exit 2 ;;
  esac
done

echo "▶ tests (SCHOLION_OFFLINE=1 — the network is off: the result must not depend on whether some external reference answers today)"
# `< /dev/null`: no test may read the terminal. One that does passes on CI,
# where stdin is closed, and hangs for whoever runs the suite by hand.
python3 -m unittest discover -s tests -t . "$@" < /dev/null
echo "▶ backward compatibility of the public contract"
python3 src/tools/check_compat.py
# These steps run only if the tool is present in this build: the anonymised
# package does not carry every internal tool, and a run at the recipient's end
# must not fail over the absence of something they were never given.
if [ -f src/tools/sync_docs.py ]; then
  echo "▶ the documents inside the package match their sources"
  python3 src/tools/sync_docs.py || exit 1
fi

if [ -f src/tools/sync_manifest.py ]; then
  echo "▶ the host manifest matches the build"
  python3 src/tools/sync_manifest.py || exit 1
fi

if [ -f src/tools/sync_rules.py ]; then
  echo "▶ the assistant rules are in sync with ASSISTANT-RULES.md"
  python3 src/tools/sync_rules.py
fi
# The suite on the OLDEST Python the package promises, run BEFORE a tag instead
# of after one.
#
# `requires-python = ">=3.10"` is a promise to everyone who installs this, and
# until now nothing on this machine checked it: the matrix that does lives in the
# public repository and is reached only through publication. It answered twice in
# two days, both times about a tag that was already out — once with a failed
# release build, once with a red matrix on a published version. Both were the
# same shape: verified on one interpreter, promised about four.
#
# The floor is read from pyproject.toml rather than written here. Three places
# already name it — the promise, the matrix, and this — and a number typed into
# each is three numbers.
#
# `uv` fetches the interpreter and caches it; a second run costs half a second
# plus the suite. Where uv is absent the step says so and does not pretend: a
# check that cannot run is not a check that passed.
if [ "$#" -gt 0 ]; then
  :
elif [ "${SCHOLION_SKIP_OLDEST:-}" = "1" ] || [ "${SCHOLION_SKIP_OLDEST:-}" = "true" ]; then
  echo "▶ the oldest supported Python — skipped by SCHOLION_SKIP_OLDEST"
elif [ "${CI:-}" = "true" ]; then
  echo "▶ the oldest supported Python — not here: the matrix runs every version it promises"
elif [ ! -f pyproject.toml ]; then
  echo "▶ the oldest supported Python — not asked: no pyproject.toml here to read the floor from"
else
  FLOOR="$(sed -n 's/^requires-python[^0-9]*\([0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' pyproject.toml | head -1)"
  HERE="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
  case "$FLOOR" in [0-9]*.[0-9]*) ;; *) FLOOR="" ;; esac
  if [ -z "$FLOOR" ]; then
    echo "▶ the oldest supported Python — not asked: pyproject.toml names no floor"
  elif [ "$FLOOR" = "$HERE" ]; then
    echo "▶ the oldest supported Python — this IS $FLOOR, already covered by the run above"
  elif ! command -v uv >/dev/null 2>&1; then
    echo "⚠ the oldest supported Python ($FLOOR) was NOT run: uv is not installed, and there is"
    echo "  nothing else here to fetch that interpreter with. This machine runs $HERE, so"
    echo '  requires-python is unverified until the matrix answers — after a tag.'
  else
    echo "▶ the suite on Python $FLOOR, the oldest this package promises (uv fetches it; SCHOLION_SKIP_OLDEST=1 skips)"
    uv run --python "$FLOOR" --no-project -- python -m unittest discover -s tests -t . < /dev/null || exit 1
  fi
fi

# The reach of the suite over the code, measured rather than assumed. It runs the
# whole suite a second time under the interpreter's coverage hook, which costs
# about a minute and a half — so it is the LAST step, after everything that can
# fail cheaply has already had its say.
#
# Why it is here at all and not in CI: the matrix in .github/workflows/tests.yml
# runs in the PUBLIC repository, which this tree reaches only through
# publish_share.sh. A gate there answers after publication. This is the only
# place that answers before it.
#
# A narrowed run is skipped rather than measured: `./run_tests.sh tests.test_x`
# executes a fraction of the suite, and comparing that fraction's reach against a
# baseline taken from the whole would fail for the one reason that is not a
# defect.
if [ -f src/tools/check_test_reach.py ]; then
  if [ "$#" -gt 0 ]; then
    echo "▶ reach of the suite — not measured: this run was narrowed to $*"
  elif [ "${SCHOLION_SKIP_REACH:-}" = "1" ] || [ "${SCHOLION_SKIP_REACH:-}" = "true" ] || [ "${SCHOLION_SKIP_REACH:-}" = "yes" ]; then
    echo "▶ reach of the suite — skipped by SCHOLION_SKIP_REACH"
  else
    echo "▶ no module lost reach over the code (~90s; SCHOLION_SKIP_REACH=1 skips it)"
    python3 src/tools/check_test_reach.py --strict || exit 1
  fi
fi

if [ -f src/tools/check_language.py ]; then
  echo "▶ Russian has not been added to what ships"
  python3 src/tools/check_language.py --strict > /dev/null || {
    python3 src/tools/check_language.py --strict
    exit 1
  }
  echo "  ✓ the remainder did not grow"
fi
