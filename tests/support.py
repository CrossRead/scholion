"""Shared test scaffolding: running the CLI against a synthetic profile.

The tests NEVER read the real profile: `SCHOLION_PROFILE_DIR` is forced to point
at `tests/fixtures/profile`, and the commands are run in a separate process —
exactly the way the assistant or the user runs them. Checking internal functions
and bypassing the CLI is easier, but then a broken argument or a render that
crashed would go unnoticed: it is the command line that faces outward.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
FIXTURE_PROFILE = Path(__file__).resolve().parent / "fixtures" / "profile"

# Can this tree BUILD a package, or is it one?
#
# The two questions are not the same, and the difference is a release blocker.
# `make_shareable.py` ships inside the package — it IS the build procedure, so
# it has to travel with what it built. But `share/`, the folder it builds FROM,
# does not ship. A test guarded by "the tool imported" therefore runs on a
# public runner and dies on build()'s first line, and publish.yml runs
# ./run_tests.sh BEFORE it publishes: red suite, nothing reaches PyPI.
#
# This has now cost two releases — v2.23.0 fixed one such test by passing
# --no-personal-patterns, and v2.21.0 introduced another that nobody noticed
# because the package's own suite was not run again until 17.08.2026. Hence a
# shared predicate rather than a third bespoke guard.
IN_SOURCE_REPO = (ROOT / "share").is_dir()


def env(profile_dir: Path | None = None, lang: str | None = None) -> dict:
    e = dict(os.environ)
    e["PYTHONPATH"] = str(SRC) + os.pathsep + e.get("PYTHONPATH", "")
    e["SCHOLION_PROFILE_DIR"] = str(profile_dir or FIXTURE_PROFILE)
    # The language is pinned rather than inherited: a developer with
    # SCHOLION_LANG=ru in their shell would otherwise get a different run from
    # CI, and a language test would pass or fail by accident of the terminal.
    e["SCHOLION_LANG"] = lang or "en"
    e["SCHOLION_REPO_DIR"] = str(ROOT)
    e["SCHOLION_OFFLINE"] = "1"          # the tests do not go to the network: the result must not depend on it
    # and they do not open the real genome: for the owner that is a file of tens of gigabytes
    e["SCHOLION_GENOME_VCF"] = str(Path(__file__).resolve().parent / "fixtures" / "no-such-file.vcf.gz")
    e["SCHOLION_GENOME_DIR"] = str(Path(__file__).resolve().parent / "fixtures" / "no-genome")
    e.setdefault("LC_ALL", "C.UTF-8")
    return e


def run(args, profile_dir: Path | None = None, timeout: int = 120,
        lang: str | None = None):
    """Run a CLI command. Returns (return code, stdout, stderr)."""
    p = subprocess.run([sys.executable, "-m", "scholion", *args],
                       cwd=str(ROOT), env=env(profile_dir, lang), capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def run_json(args, profile_dir: Path | None = None, lang: str | None = None):
    """A command with --json → the parsed object. A parse failure = a failed test."""
    code, out, err = run([*args, "--json"], profile_dir, lang=lang)
    assert code == 0, f"{args}: return code {code}\nstderr:\n{err}"
    try:
        return json.loads(out)
    except json.JSONDecodeError as e:                       # noqa: BLE001
        raise AssertionError(f"{args}: the --json output does not parse ({e})\n{out[:500]}") from e


# Commands that need arguments in order to run: in the smoke pass we substitute
# knowingly harmless ones. An absence of data is a legitimate answer, a crash is not.
ARGS_FOR = {
    "drug": ["atorvastatin"],
    "prescription": ["atorvastatin"],
    "genome": ["rs4149056"],
    "labs": [],
    "ingest-labs": None,          # touches the user's file system
    # Reads a path from the command line: nothing sensible to pass in a smoke
    # sweep, and passing a real file would make the sweep write into a profile.
    # Covered in full by tests/test_marker_resolution.py, on a temporary profile.
    "import-labs": None,
    "redact": None,               # reads stdin; covered by tests/test_redact.py
    "ingest-studies": None,
    "ingest-garmin": None,
    "add-lab": None,              # the writing ones are checked separately, on a copy of the profile
    "add-med": None,
    "add-metric": None,
    "remove-med": None,
    "focus-log": None,
    "set-folder": None,
    "serve": None,                # a blocking server
    "reconcile": None,            # reads the folder with the PDF forms
    "provenance": None,
    # The ones that create files: run their smoke pass "as is" and `init` will
    # lay the templates out right inside the fixture, while `demo` will overwrite
    # the demo profile in the repository. A test that changes the very thing it
    # checks against is useless: the second run already goes over different data.
    # Both are checked separately — in a temporary directory, in TestFirstRun.
    "init": None,
    "demo": None,
    "assistant": [],
    # Without --path the command prints the entire instruction (~100 KB) — in the
    # smoke sweep that is needless noise; the file itself is checked in
    # test_skill_editions.
    "skill": ["--path"],
}
