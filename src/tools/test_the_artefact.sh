#!/bin/bash
# Run a built package's own suite the way a person who downloaded it runs it.
#
# Usage: src/tools/test_the_artefact.sh <package-dir>
#
# The package directory the publisher builds is also the public repository's
# working tree, so it carries `.git`. A release archive does not. A test that
# depends on whether `.git` is there passed here and failed for the recipient:
# on 25.09.2026 an outside reviewer ran the suite of 0.5.8 in a copy without
# `.git` and got a failure the in-package gate had never seen (task 210). The
# gate now runs in a copy of the package without `.git`, in a temporary folder
# outside every repository — what the release archive unpacks into.
#
# Exit status: the suite's own; 5 when the package cannot be tested at all.
# Written for the bash macOS ships (3.2): no mapfile, no associative arrays.
set -u

PKG="${1:-}"
if [ -z "$PKG" ] || [ ! -d "$PKG" ]; then
  echo "❌ test_the_artefact.sh: no package directory given (or it does not exist): '$PKG'" >&2
  exit 5
fi
if [ ! -f "$PKG/run_tests.sh" ]; then
  echo "❌ $PKG/run_tests.sh is missing — the artefact cannot be verified." >&2
  exit 5
fi

# `cd -P` resolves the macOS /var -> /private/var symlink up front, so the copy
# lives at the one spelling every path inside the suite will agree on.
BASE="$(mktemp -d "${TMPDIR:-/tmp}/scholion-artefact.XXXXXX")" || { echo "❌ no temporary folder" >&2; exit 5; }
BASE="$(cd -P "$BASE" && pwd)"
COPY="$BASE/scholion"
cleanup() { rm -rf "$BASE"; }
trap cleanup EXIT

mkdir -p "$COPY"
# tar rather than cp: it keeps modes (run_tests.sh stays executable) on both
# BSD and GNU, and --exclude is understood by both.
( cd "$PKG" && tar -cf - --exclude=./.git --exclude=.git . ) | ( cd "$COPY" && tar -xf - ) || {
  echo "❌ could not copy the package to $COPY" >&2; exit 5; }
if [ -e "$COPY/.git" ]; then
  echo "❌ the copy still has .git — refusing to call it the downloaded artefact" >&2
  exit 5
fi

echo "  the suite runs in a copy without .git: $COPY"
( cd "$COPY" && bash ./run_tests.sh )
