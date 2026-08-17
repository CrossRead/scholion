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
python3 -m unittest discover -s tests -t . "$@"
echo "▶ backward compatibility of the public contract"
python3 src/tools/check_compat.py
# These steps run only if the tool is present in this build: the anonymised
# package does not carry every internal tool, and a run at the recipient's end
# must not fail over the absence of something they were never given.
if [ -f src/tools/sync_rules.py ]; then
  echo "▶ the assistant rules are in sync with ASSISTANT-RULES.md"
  python3 src/tools/sync_rules.py
fi
if [ -f src/tools/check_language.py ]; then
  echo "▶ Russian has not been added to what ships"
  python3 src/tools/check_language.py --strict > /dev/null || {
    python3 src/tools/check_language.py --strict
    exit 1
  }
  echo "  ✓ the remainder did not grow"
fi
