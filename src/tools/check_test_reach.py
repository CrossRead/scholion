#!/usr/bin/env python3
"""How far the test suite reaches into the code — measured, not estimated.

    python3 src/tools/check_test_reach.py            # the table, worst first
    python3 src/tools/check_test_reach.py --json     # the same as a structure
    python3 src/tools/check_test_reach.py --strict   # exit 1 if reach fell
    python3 src/tools/check_test_reach.py --accept   # record the current state

THIS IS NOT `check_coverage.py`, and the two are neighbours in this directory,
so the difference is stated before anything else. That one asks what this build
KNOWS — which drug-gene pairs, which markers, which phenotypes — and compares it
against what an authority says it ought to know. This one asks which lines of
`src/scholion` the suite actually EXECUTES. A build can score perfectly on one
and badly on the other; they have nothing in common but the English word.

## Why measured

A review of this project counted 1050 green tests and concluded the code was
well covered. It was not: the number that had never been taken was 69.9%, and the
modules at the bottom of it were not obscure ones. `provenance.py` — the module
that implements the sentence the product is sold on — stood at 12.8%.
`tabixlite.py`, the VCF reader used whenever `pysam` is absent and therefore the
one most installations actually run, stood at 35.4%. Nothing in the suite could
have said so, because nothing was counting.

Counting was also not available: this project carries no third-party
dependencies, and `coverage` is one. So the measurement is built out of the
standard library, which turns out to be enough.

## Why a baseline rather than a target

The same reasoning as `check_language.py`. A gate set at 90% today fails on
Monday and is switched off on Tuesday, and a gate that is off is worse than
none because it looks like a guarantee. The enforced property is therefore not
«the code is well covered» but «no module lost reach without somebody looking at
it»: `test_reach_baseline.json` records what was accepted, per module, and
`--strict` fails when a module falls below its line or when a module appears
that was never reviewed. Raising it is `--accept`, which rewrites the file, and
the diff is then somebody's to justify in a commit message.

A module that rose above its accepted line is not lowered automatically either.
Work was done; recording it is a deliberate act.

## What is counted

The lines the COMPILER considers executable — `dis.findlinestarts` over the
compiled module and every code object inside it. Not `ast` statement numbers,
which was the first attempt and which counts a decorator and its function as one
line and misses a good deal else. Not branches: this measures statements, and a
statement executed by a test that asserts nothing is still counted. Reach is a
floor under the suite, never a claim about its quality.

## Subprocesses are counted too

Twenty-one of this project's test files run the CLI in a real subprocess, which
is the right way to test a command line and is invisible to any measurement that
watches only its own process. Measured without them the answer is 54.3%; with
them it is 69.9%. The difference is not a detail — it is the difference between
believing `reconcile.py` is dead code and knowing it is half exercised.

They are collected by putting a generated `sitecustomize` on `PYTHONPATH`: every
Python that starts under this run installs the same recorder and writes what it
saw into one directory as it exits.
"""
from __future__ import annotations

import argparse
import ast
import dis
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEASURED = ROOT / "src" / "scholion"
BASELINE = Path(__file__).resolve().parent / "test_reach_baseline.json"

_NOTE = ("Statement reach of the test suite over src/scholion, per module, as a "
         "percentage accepted after review. Written by "
         "`python3 src/tools/check_test_reach.py --accept`. A number here may only "
         "be LOWERED deliberately — see the docstring of that file.")

#: The environment the suite is measured in. It has to be the same environment
#: `run_tests.sh` runs it in, or the two answer about different programs: with a
#: real genome connected the genome paths execute and reach jumps for reasons
#: that have nothing to do with the tests.
#: `tests/test_the_reach_tool_and_the_runner_agree.py` compares this table against
#: the shell script rather than trusting that both were updated together.
SUITE_ENV = {
    "SCHOLION_PROFILE_DIR": str(ROOT / "tests" / "fixtures" / "profile"),
    "SCHOLION_OFFLINE": "1",
    "SCHOLION_LANG": "en",
    "SCHOLION_GENOME_VCF": str(ROOT / "tests" / "fixtures" / "no-such-file.vcf.gz"),
    "SCHOLION_GENOME_DIR": str(ROOT / "tests" / "fixtures" / "no-genome"),
}

# The recorder, as source, because it has to run in processes this one never
# sees. Written to a temporary directory and reached through PYTHONPATH, so a
# subprocess installs it before it imports anything of ours.
#
# Two backends. `sys.monitoring` (3.12+) is what this is built for — it is the
# interpreter's own coverage hook and costs little. Below that there is
# `sys.settrace`, which is slower by a large factor but present since forever and
# gives the same answer; the alternative was a gate that does not run on two of
# the four Pythons this project promises to support, which is the shape of
# «checked everywhere except where it broke».
_RECORDER = '''
import atexit, json, os, pathlib, sys, threading

_dir = os.environ.get("SCHOLION_REACH_DIR")
_root = os.environ.get("SCHOLION_REACH_ROOT")
if _dir and _root:
    _hits = {}

    def _dump():
        if not _hits:
            return
        try:
            p = pathlib.Path(_dir) / ("%d-%d.json" % (os.getpid(), len(_hits)))
            n = 0
            while p.exists():
                n += 1
                p = pathlib.Path(_dir) / ("%d-%d-%d.json" % (os.getpid(), len(_hits), n))
            p.write_text(json.dumps({k: sorted(v) for k, v in _hits.items()}))
        except Exception:
            pass

    if hasattr(sys, "monitoring"):
        _mon = sys.monitoring
        _TOOL = _mon.COVERAGE_ID

        def _line(code, lineno):
            fn = code.co_filename
            if fn.startswith(_root):
                _hits.setdefault(fn, set()).add(lineno)
            return None

        try:
            _mon.use_tool_id(_TOOL, "scholion-reach")
            _mon.register_callback(_TOOL, _mon.events.LINE, _line)
            _mon.set_events(_TOOL, _mon.events.LINE)

            def _stop():
                try:
                    _mon.set_events(_TOOL, 0)
                except Exception:
                    pass
                _dump()

            atexit.register(_stop)
        except Exception:
            pass
    else:
        def _trace(frame, event, arg):
            fn = frame.f_code.co_filename
            if not fn.startswith(_root):
                return None
            if event == "line":
                _hits.setdefault(fn, set()).add(frame.f_lineno)
            return _trace

        try:
            threading.settrace(_trace)
            sys.settrace(_trace)

            def _stop():
                try:
                    sys.settrace(None)
                except Exception:
                    pass
                _dump()

            atexit.register(_stop)
        except Exception:
            pass
'''


def executable_lines(path: Path) -> set:
    """The lines the compiler will emit a line event for.

    Asking the compiler rather than the syntax tree matters: a decorated function
    is one statement to `ast` and several lines to the interpreter, a multi-line
    call is one statement and one line, and a docstring is a statement that never
    executes. Every one of those made the first version of this measurement wrong
    in a different direction.
    """
    src = path.read_text(encoding="utf-8")
    try:
        # A module with no statements at all has nothing to reach, and saying so
        # from the SOURCE rather than from the compiler is what makes the answer
        # the same on every Python. An empty `__init__.py` compiles to an
        # implicit return, and the line it is numbered at moved between 3.10 and
        # 3.11: line 1 there, line 0 here. This counter drops line 0, so the same
        # empty file was measured on one interpreter and skipped on the other —
        # and a baseline taken here then failed on 3.10 for a module that has no
        # code in it.
        if not ast.parse(src).body:
            return set()
        code = compile(src, str(path), "exec")
    except (SyntaxError, ValueError):                        # pragma: no cover
        return set()
    out, stack = set(), [code]
    while stack:
        c = stack.pop()
        for _, line in dis.findlinestarts(c):
            if line:
                out.add(line)
        for k in c.co_consts:
            if isinstance(k, types.CodeType):
                stack.append(k)
    return out


def measure(argv=None) -> dict:
    """Run the suite under the recorder and return {module: (hit, total)}.

    The suite runs in a CHILD, not here. Running it in this process would work
    and was the first version, but then the tool's own imports are already in
    `sys.modules` before measurement starts, and every line executed at import
    time — module constants, catalogue loading, the `@dataclass` bodies — counts
    as reached without any test having asked for it. A child starts clean.
    """
    workdir = Path(tempfile.mkdtemp(prefix="scholion-reach-"))
    try:
        site = workdir / "site"
        site.mkdir()
        (site / "sitecustomize.py").write_text(_RECORDER, encoding="utf-8")
        dumps = workdir / "dumps"
        dumps.mkdir()

        env = dict(os.environ)
        env.update(SUITE_ENV)
        env["SCHOLION_REACH_DIR"] = str(dumps)
        # `.resolve()`: on macOS the temporary root is reached through a symlink
        # and `co_filename` is the resolved form, so an unresolved prefix matches
        # nothing at all and the run reports a confident zero.
        env["SCHOLION_REACH_ROOT"] = str(MEASURED.resolve())
        env["PYTHONPATH"] = os.pathsep.join(
            [str(site), str(ROOT / "src"), str(ROOT / "tests")])
        env.pop("PYTHONDONTWRITEBYTECODE", None)

        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."]
        cmd += list(argv or [])
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, stdin=subprocess.DEVNULL)
        tail = proc.stdout.strip().splitlines()[-3:]

        merged = {}
        for f in dumps.glob("*.json"):
            try:
                got = json.loads(f.read_text())
            except (OSError, json.JSONDecodeError):          # pragma: no cover
                continue
            for k, v in got.items():
                merged.setdefault(k, set()).update(v)

        modules, hit_all, total_all = {}, 0, 0
        for p in sorted(MEASURED.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            lines = executable_lines(p)
            if not lines:
                continue
            hit = merged.get(str(p.resolve()), set()) & lines
            rel = p.relative_to(ROOT).as_posix()
            modules[rel] = {"hit": len(hit), "total": len(lines),
                            "percent": round(100.0 * len(hit) / len(lines), 1)}
            hit_all += len(hit)
            total_all += len(lines)

        return {
            "suite_ok": proc.returncode == 0,
            "suite_tail": tail,
            "processes": len(list(dumps.glob("*.json"))),
            "backend": "sys.monitoring" if hasattr(sys, "monitoring") else "sys.settrace",
            "overall": {"hit": hit_all, "total": total_all,
                        "percent": round(100.0 * hit_all / total_all, 1) if total_all else 0.0},
            "modules": modules,
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _baseline() -> dict:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text(encoding="utf-8")).get("modules", {})


def compare(result: dict) -> tuple:
    """(fell, unlisted, vanished) against the accepted baseline."""
    accepted = _baseline()
    fell, unlisted = [], []
    for rel, m in sorted(result["modules"].items()):
        if rel not in accepted:
            unlisted.append(rel)
        elif m["percent"] < accepted[rel]:
            fell.append((rel, accepted[rel], m["percent"]))
    vanished = sorted(set(accepted) - set(result["modules"]))
    return fell, unlisted, vanished


def _write_baseline(result: dict) -> None:
    BASELINE.write_text(json.dumps({
        "_note": _NOTE,
        "overall": result["overall"]["percent"],
        "modules": {k: v["percent"] for k, v in sorted(result["modules"].items())},
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="how far the test suite reaches into src/scholion")
    ap.add_argument("--json", action="store_true", help="the structure instead of the table")
    ap.add_argument("--strict", action="store_true", help="exit 1 if reach fell below the baseline")
    ap.add_argument("--accept", action="store_true", help="record the current state as accepted")
    ap.add_argument("--worst", type=int, default=15, help="how many modules to print")
    a = ap.parse_args(argv)

    # Asked BEFORE the measurement, because the measurement is the expensive part.
    # `--strict` outside the source tree can only ever answer «nothing compared»:
    # the package skips the tests only the tree can run, so its reach is
    # legitimately lower and the accepted numbers do not describe it. Running the
    # whole suite a second time to reach that conclusion cost a minute and a half
    # on every cell of the matrix and on the release build — for a sentence that
    # was decided before a line of it executed.
    if a.strict and not a.accept and not (ROOT / "share").is_dir():
        print("· not the source repository: the suite skips what only the tree can run, "
              "so the accepted numbers do not apply here. Nothing measured, nothing compared.")
        return 0

    result = measure()

    if a.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["suite_ok"] else 1

    if not result["suite_ok"]:
        print("✗ the suite did not pass, so its reach says nothing:")
        for line in result["suite_tail"]:
            print("   " + line)
        return 1

    o = result["overall"]
    print(f"reach of the suite over src/scholion: {o['hit']}/{o['total']} = {o['percent']}%"
          f"  ({result['processes']} processes, {result['backend']})")
    worst = sorted(result["modules"].items(), key=lambda kv: kv[1]["percent"])[:a.worst]
    print(f"\nleast reached ({len(worst)} of {len(result['modules'])}):")
    for rel, m in worst:
        print(f"  {m['percent']:5.1f}%  {m['hit']:4d}/{m['total']:4d}  {rel}")

    if a.accept:
        _write_baseline(result)
        print(f"\n✓ recorded as accepted: {BASELINE.relative_to(ROOT)}")
        return 0

    if a.strict:
        fell, unlisted, vanished = compare(result)
        for rel, was, now in fell:
            print(f"\n✗ {rel}: reach fell {was}% → {now}%")
        for rel in unlisted:
            print(f"\n✗ {rel}: a module nobody has reviewed the reach of")
        for rel in vanished:
            print(f"\n· {rel}: in the baseline, not in the tree — remove the line")
        if fell or unlisted:
            print("\n  Add the tests, or accept the new number deliberately:")
            print("    python3 src/tools/check_test_reach.py --accept")
            return 1
        print("\n✓ no module lost reach")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
