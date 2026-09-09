#!/usr/bin/env python3
"""How far the test suite reaches into the code — measured, not estimated.

    python3 src/tools/check_test_reach.py            # the table, worst first
    python3 src/tools/check_test_reach.py --json     # the same as a structure
    python3 src/tools/check_test_reach.py --strict   # exit 1 if reach fell
    python3 src/tools/check_test_reach.py --accept   # record the current state
    python3 src/tools/check_test_reach.py --accept-new   # only modules with no number yet
    python3 src/tools/check_test_reach.py --rebaseline   # move the whole file to this machine

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

## Why `--accept` seeds the baseline before it measures

`--accept` refuses to record the reach of a suite that did not pass — a red
suite says nothing about reach. And the suite carries a cheap guard,
`TestTheBaselineDescribesThisTree`, that fails whenever a module in the tree has
no line in the baseline, telling the user to run `--accept`. Together those two
made a circle: add a module, the guard turns the suite red, the red suite blocks
`--accept`, and the only exit was to seed the new module at 0.0 by hand and run
`--accept` a second time. Four modules paid for that on 08.09.2026.

So `--accept` does the seeding itself, before the measurement starts: modules in
the tree with no accepted number are entered at 0.0, modules in the baseline
with no file behind them are removed, and both are printed. The measured run
then sees a baseline that describes the tree, the guard is satisfied, and the
real numbers overwrite the seeds. If the suite fails anyway the file is put back
exactly as it was, so a refused `--accept` leaves no half-written state behind.
`--strict` does none of this: it still fails on a module nobody reviewed.

## Why `--accept` refuses to cross machines

A number here is not a property of the code alone. It is what THIS suite reached
on THIS interpreter with THIS backend — the two backends do not count a line
identically — and, in at least one case, with a file that is not in the
repository at all: `bamlite.py` stands at 89.4% because
`test_read_depth_matches_the_native_run.py` runs against the owner's own
alignment, and that test says so in its own docstring. It skips everywhere else,
and the module reads 0.0% there.

So a full `--accept` run from a second machine does not record work. It moves
the entire baseline to that machine, silently, under one line of output — on
09.09.2026 that would have restamped the file from 3.13 / darwin to 3.10 /
linux and lowered six modules, five of them by fractions of a point and one from
89.4 to 0.0. `--strict` had been printing a warning about exactly this mismatch
for months; `--accept` was the half of the pair that ignored it.

The three writing modes are therefore not one:

* **`--accept`** records the whole measurement and REFUSES when the baseline was
  taken elsewhere. It refuses before measuring, because the answer does not
  depend on the ninety seconds.
* **`--accept-new`** records only the modules that have no accepted number at
  all — the operation the suite's own guard asks for when a module is added. It
  touches no other number, not `overall`, and not the stamp. It runs anywhere,
  because adding a line nobody had reviewed cannot lower anybody's floor.
* **`--rebaseline`** is the deliberate whole-file move, and it prints every
  number that falls, old → new, BEFORE it writes. «Somebody's to justify in a
  commit message» is only true if somebody was shown it at the time.

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
                got = json.loads(f.read_text(encoding="utf-8"))
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
            "backend": _backend(),
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


def _backend() -> str:
    """Which hook will count the lines. One spelling, because a refusal that
    named a backend the run then did not use would be about nothing."""
    return "sys.monitoring" if hasattr(sys, "monitoring") else "sys.settrace"


def _taken_with(backend: str) -> dict:
    """What measured: the two backends do not count a line identically, and a
    module moves by up to about a point between them with no change to the code
    — seen on the same commit, 3.11 against 3.13 (task 125)."""
    return {"python": "%d.%d" % sys.version_info[:2], "backend": backend,
            "platform": sys.platform}


def _baseline_meta() -> dict:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text(encoding="utf-8")).get("taken_with", {})


def _here() -> dict:
    """The stamp this run would write — known before the suite is measured."""
    return _taken_with(_backend())


def stamp_gap():
    """`(recorded, here)` when the accepted numbers were taken elsewhere, else None.

    `None` also when the file says nothing about what measured it: an unstamped
    baseline is one written before the stamp existed, and refusing over a fact
    nobody recorded would refuse for ever.
    """
    meta, here = _baseline_meta(), _here()
    if not meta or meta == here:
        return None
    return meta, here


def _gap_sentence(meta: dict, here: dict) -> str:
    return (f"the accepted numbers were taken with Python {meta.get('python')} / "
            f"{meta.get('backend')} on {meta.get('platform')}; this run is Python "
            f"{here['python']} / {here['backend']} on {here['platform']}")


def tree_modules() -> set:
    """The modules the measurement will report on: every file under
    `src/scholion` with at least one executable line, as a path relative to ROOT.
    The same set `measure()` builds and the guard test in the suite builds; one
    spelling, so the three cannot disagree about what a module is."""
    return {p.relative_to(ROOT).as_posix()
            for p in MEASURED.rglob("*.py")
            if "__pycache__" not in p.parts and executable_lines(p)}


def seed_baseline() -> tuple:
    """Make the baseline describe the tree BEFORE the suite is measured.

    Returns `(added, dropped, previous)`: the modules entered at 0.0 because
    they had no accepted number, the modules removed because no file stands
    behind them any more, and the file's previous text (`None` if there was no
    file) so a caller can put it back when the measurement is refused. Nothing
    is written when there is nothing to change.
    """
    present = tree_modules()
    previous = BASELINE.read_text(encoding="utf-8") if BASELINE.exists() else None
    doc = json.loads(previous) if previous else {}
    accepted = dict(doc.get("modules", {}))
    added = sorted(present - set(accepted))
    dropped = sorted(set(accepted) - present)
    if not added and not dropped:
        return [], [], previous
    for rel in added:
        accepted[rel] = 0.0
    for rel in dropped:
        del accepted[rel]
    BASELINE.write_text(json.dumps({
        "_note": doc.get("_note", _NOTE),
        # Kept through the seed: what measured the accepted numbers is still
        # true of them, and the measured run rewrites it anyway.
        **({"taken_with": doc["taken_with"]} if "taken_with" in doc else {}),
        "overall": doc.get("overall", 0.0),
        "modules": dict(sorted(accepted.items())),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return added, dropped, previous


def _restore_baseline(previous) -> None:
    if previous is None:
        if BASELINE.exists():
            BASELINE.unlink()
    else:
        BASELINE.write_text(previous, encoding="utf-8")


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


def _write_only_new(result: dict, added: list, dropped: list, previous) -> None:
    """Record the measured number for modules that had none; change nothing else.

    Everything the file already said stays as it was, to the byte — the note,
    the stamp, the overall, and every other module's accepted floor. What is
    written here is a line that did not exist, which cannot lower anybody's
    number and therefore does not need the machine to match.
    """
    doc = json.loads(previous) if previous else {}
    accepted = dict(doc.get("modules", {}))
    for rel in added:
        m = result["modules"].get(rel)
        accepted[rel] = m["percent"] if m else 0.0
    for rel in dropped:
        accepted.pop(rel, None)
    BASELINE.write_text(json.dumps({
        "_note": doc.get("_note", _NOTE),
        **({"taken_with": doc["taken_with"]} if "taken_with" in doc else {}),
        "overall": doc.get("overall", result["overall"]["percent"]),
        "modules": dict(sorted(accepted.items())),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_baseline(result: dict) -> None:
    BASELINE.write_text(json.dumps({
        "_note": _NOTE,
        "taken_with": _taken_with(result["backend"]),
        "overall": result["overall"]["percent"],
        "modules": {k: v["percent"] for k, v in sorted(result["modules"].items())},
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="how far the test suite reaches into src/scholion")
    ap.add_argument("--json", action="store_true", help="the structure instead of the table")
    ap.add_argument("--strict", action="store_true", help="exit 1 if reach fell below the baseline")
    ap.add_argument("--accept", action="store_true", help="record the current state as accepted")
    ap.add_argument("--accept-new", action="store_true", dest="accept_new",
                    help="record only the modules that have no accepted number yet")
    ap.add_argument("--rebaseline", action="store_true",
                    help="move the whole baseline to this machine, printing what falls")
    ap.add_argument("--worst", type=int, default=15, help="how many modules to print")
    a = ap.parse_args(argv)

    # Asked BEFORE the measurement, because the measurement is the expensive part.
    # `--strict` outside the source tree can only ever answer «nothing compared»:
    # the package skips the tests only the tree can run, so its reach is
    # legitimately lower and the accepted numbers do not describe it. Running the
    # whole suite a second time to reach that conclusion cost a minute and a half
    # on every cell of the matrix and on the release build — for a sentence that
    # was decided before a line of it executed.
    writing = a.accept or a.accept_new or a.rebaseline

    # Before the measurement, because the answer does not depend on it: a full
    # `--accept` from a machine other than the one the numbers were taken on
    # does not record work, it moves the baseline. The deliberate move has its
    # own name, and it prints what it lowers.
    gap = stamp_gap()
    if a.accept and gap:
        print("✗ " + _gap_sentence(*gap) + ".")
        print("\n  A full accept from here would rewrite every number with this "
              "machine's, and some of them are lower for reasons that are not the "
              "code: the two backends do not count a line identically, and at least "
              "one module is reached only where the owner's own alignment is.")
        print("\n  Add a module's first number:   "
              "python3 src/tools/check_test_reach.py --accept-new")
        print("  Move the baseline here anyway: "
              "python3 src/tools/check_test_reach.py --rebaseline")
        print("  Or accept on that interpreter, where the comparison is like for like.")
        return 1

    if a.strict and not writing and not (ROOT / "share").is_dir():
        print("· not the source repository: the suite skips what only the tree can run, "
              "so the accepted numbers do not apply here. Nothing measured, nothing compared.")
        return 0

    # `--accept` first makes the baseline describe the tree, or the suite's own
    # guard turns the run red over exactly the module `--accept` was asked to
    # record — see «Why `--accept` seeds the baseline» in the docstring.
    added, dropped, previous = ([], [], None)
    if writing:
        added, dropped, previous = seed_baseline()
        for rel in added:
            print(f"· {rel}: not in the baseline — entered at 0.0% for the measurement")
        for rel in dropped:
            print(f"· {rel}: in the baseline, not in the tree — removed")

    # `--accept-new` with nothing to add has nothing to measure. The suite costs
    # a minute and a half and the answer is already known.
    if a.accept_new and not added and not dropped:
        print("· every module in the tree already has an accepted number; nothing to record")
        return 0

    result = measure()

    if a.json:
        if writing and not result["suite_ok"]:
            _restore_baseline(previous)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["suite_ok"] else 1

    if not result["suite_ok"]:
        if writing and (added or dropped):
            _restore_baseline(previous)
            print("· the baseline was put back as it was; nothing was accepted")
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

    shown = BASELINE.relative_to(ROOT) if BASELINE.is_relative_to(ROOT) else BASELINE

    if a.accept_new:
        _write_only_new(result, added, dropped, previous)
        for rel in added:
            m = result["modules"].get(rel) or {}
            print(f"\n✓ {rel}: {m.get('percent', 0.0)}% recorded as its first accepted number")
        if gap:
            print("\n· measured here, and the file's stamp is left as it was: "
                  + _gap_sentence(*gap) + ". Nothing else in it was touched.")
        print(f"\n✓ {len(added)} added, {len(dropped)} removed: {shown}")
        return 0

    if a.rebaseline:
        # What a whole-file move costs, said before it is made rather than left
        # to `git diff` afterwards.
        fell, _unlisted, _vanished = compare(result)
        for rel, was, now in fell:
            print(f"\n· {rel}: {was}% → {now}% — lowered by this rebaseline")
        if gap:
            print("\n· " + _gap_sentence(*gap) + "; the stamp moves to this run.")
        if not fell:
            print("\n· no accepted number falls")
        _write_baseline(result)
        print(f"\n✓ the baseline now describes this machine: {shown}")
        return 0

    if a.accept:
        _write_baseline(result)
        print(f"\n✓ recorded as accepted: {shown}")
        return 0

    if a.strict:
        meta, here = _baseline_meta(), _taken_with(result["backend"])
        if not meta:
            print("\n· the accepted numbers do not say what measured them; from the next "
                  "--accept on, the baseline records the interpreter, the backend and the platform")
        elif meta != here:
            print("\n· " + _gap_sentence(meta, here) + ". The two backends "
                  "do not count a line identically — a module can move by up to about a point "
                  "with no change to the code. The numbers below are compared as they are; to "
                  "compare like with like, run on that interpreter, or accept anew on this one.")
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
