"""The full run, startable where there is no shell.

`run_tests.sh` is the front door on the machines this was built on, and it is
bash. That matters more than it looks: the release gate requires the suite to be
run INSIDE the unpacked package rather than in the repository, and the package
carries `run_tests.sh` as the only way to do that. On a machine without bash the
gate is therefore not merely inconvenient — it cannot be performed at all, so
«this package works there» would be a claim nobody could check.

This is the same run, expressed in the language the package is written in. It
sets the same environment for the same reasons (they are given at each line), and
it calls the same checking tools. It deliberately does NOT reimplement the parts
of `run_tests.sh` that are about the machine the tree is BUILT on — the run on
the oldest promised interpreter, which needs `uv`, and the reach measurement,
which takes a minute and a half. Those belong to the build machine; this is what
a recipient runs to find out whether what they were given works where they are.

Usage:
    python3 src/tools/run_tests.py            # everything
    python3 src/tools/run_tests.py tests.test_x   # narrowed, like the shell one
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def environment() -> dict:
    """The same environment `run_tests.sh` sets, and for the same reasons."""
    e = dict(os.environ)
    e["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), str(ROOT / "tests"), e.get("PYTHONPATH", "")])
    # The tests work on a synthetic fixture: they neither read nor change
    # anybody's real profile.
    e["SCHOLION_PROFILE_DIR"] = str(ROOT / "tests" / "fixtures" / "profile")
    e["SCHOLION_OFFLINE"] = "1"
    # Pinned, not inherited: with SCHOLION_LANG=ru in the shell a developer would
    # otherwise get a different run from CI, and a test about language would pass
    # or fail by accident of the terminal.
    e["SCHOLION_LANG"] = "en"
    # The checking tools print «▶», «✓» and «✗». On a Windows console the
    # child interpreters inherit a code page that cannot encode them and die on
    # the first banner, before a single test — which is what every Windows cell
    # of the matrix did on the first run that reached this far (08.09.2026).
    # The application itself already writes UTF-8 whatever the system would
    # choose; the runner and its children have to do the same.
    e["PYTHONIOENCODING"] = "utf-8"
    e["PYTHONUTF8"] = "1"
    # The genome is switched off explicitly: otherwise the run would reach for a
    # real VCF of tens of gigabytes, and the result would depend on whose genome
    # happens to lie next to it.
    e["SCHOLION_GENOME_VCF"] = str(ROOT / "tests" / "fixtures" / "no-such-file.vcf.gz")
    e["SCHOLION_GENOME_DIR"] = str(ROOT / "tests" / "fixtures" / "no-genome")
    e["SCHOLION_WORKSTATION"] = str(ROOT / "tests" / "fixtures" / "no-workstation.json")
    return e


def selection(argv: list[str]) -> tuple[list[str], bool]:
    """Keep named tests out of discovery, which ignores them with explicit -s."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("-s", "--start-directory")
    parser.add_argument("-p", "--pattern")
    parser.add_argument("-t", "--top-level-directory")
    parser.add_argument("-k", action="append", default=[])
    for short, long in (("-v", "--verbose"), ("-q", "--quiet"),
                        ("-f", "--failfast"), ("-c", "--catch"), ("-b", "--buffer")):
        parser.add_argument(short, long, action="store_true")
    parser.add_argument("--locals", action="store_true")
    parser.add_argument("tests", nargs="*")
    args = parser.parse_intermixed_args(argv)
    discovery = (args.start_directory, args.pattern, args.top_level_directory)
    if args.tests and any(discovery):
        parser.error("named tests cannot be combined with discovery -s/-p/-t")
    for name in args.tests:
        if not re.fullmatch(r"tests(?:[./][A-Za-z_]\w*)+", name):
            parser.error(f"invalid test selector {name!r}; remove any pasted comment after #")
    flags = [flag for flag, value in (("-v", args.verbose), ("-q", args.quiet),
             ("-f", args.failfast), ("-c", args.catch), ("-b", args.buffer),
             ("--locals", args.locals)) if value]
    for pattern in args.k:
        flags.extend(["-k", pattern])
    if args.tests:
        print("▶ named tests: " + ", ".join(args.tests), flush=True)
        return [*flags, *args.tests], args.suite_only
    print("▶ test discovery: " + (args.pattern or "test*.py"), flush=True)
    return ["discover", "-s", args.start_directory or "tests", "-t",
            args.top_level_directory or ".", "-p", args.pattern or "test*.py",
            *flags], args.suite_only


#: The checks that run after the suite, each only if the tool is present: the
#: anonymised package does not carry every internal tool, and a run at the
#: recipient's end must not fail over the absence of something they were never
#: given.
AFTER = (
    ("backward compatibility of the public contract", "check_compat.py", []),
    ("the documents inside the package match their sources", "sync_docs.py", []),
    ("the host manifest matches the build", "sync_manifest.py", []),
    ("the assistant rules are in sync with ASSISTANT-RULES.md", "sync_rules.py", []),
    ("Russian has not been added to what ships", "check_language.py", ["--strict"]),
)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    env = environment()
    os.environ.update(env)
    # This process's own banners, for the same reason as the children's.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")

    test_args, suite_only = selection(argv)

    print("▶ tests (SCHOLION_OFFLINE=1 — the network is off: the result must not "
          "depend on whether some external reference answers today)")
    # A separate process, not `unittest.main()` in this one: the environment above
    # has to be in place before `scholion` is imported anywhere, and a test that
    # spawns the CLI must inherit exactly it.
    cmd = [sys.executable, "-m", "unittest", *test_args]
    r = subprocess.run(cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        return r.returncode
    if suite_only:
        return 0

    for title, tool, flags in AFTER:
        path = ROOT / "src" / "tools" / tool
        if not path.exists():
            continue
        print(f"▶ {title}")
        r = subprocess.run([sys.executable, str(path), *flags], cwd=str(ROOT),
                           env=env, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
