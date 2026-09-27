#!/usr/bin/env python3
"""Type errors in the core — counted per module, and never allowed to grow.

    python3 src/tools/check_types.py            # the table, worst first
    python3 src/tools/check_types.py --strict   # exit 1 if any module gained errors
    python3 src/tools/check_types.py --accept   # record the current state

Runs in CI only (`.github/workflows/tests.yml`, job `lint`). `mypy` is a
third-party tool and the package depends on nothing, so neither `run_tests.sh`
nor the person who unpacked the archive is asked to have it.

## Why a baseline rather than zero

The first run over `src/scholion` found 336 errors in 43 modules. Most are the
type checker inferring `str` for a dictionary that holds lists and then objecting
to `.append`: true about the annotations, silent about behaviour. A gate at zero
would fail on the first push and be switched off on the second, and a gate that
is off is worse than none because it looks like a guarantee. The same reasoning
as `check_test_reach.py` and `check_language.py`: the enforced property is «no
module gained a type error without somebody looking at it». A new module starts
at zero. Fixing errors and running `--accept` lowers the line; nothing raises it.

## What it is not

It does not see import cycles — Python resolves those at run time, in whatever
order modules happen to be imported. That class has its own test,
`tests/test_every_module_imports_on_its_own.py`.

The count depends on the mypy version, so CI pins it; a version change is an
`--accept` of its own, in a commit that says so.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = Path(__file__).resolve().parent / "types_baseline.json"
TARGET = "src/scholion"
ARGS = ["--python-version", "3.10", "--ignore-missing-imports", "--no-error-summary",
        "--hide-error-context", "--no-color-output", "--show-error-codes"]
_LINE = re.compile(r"^(?P<file>[^:]+\.py):\d+: error: ")


def measure() -> Counter:
    try:
        r = subprocess.run([sys.executable, "-m", "mypy", *ARGS, TARGET],
                           cwd=ROOT, capture_output=True, text=True, timeout=900)
    except FileNotFoundError:
        raise SystemExit("mypy is not installed: `python -m pip install mypy` (CI pins the version)")
    if "No module named mypy" in (r.stderr or ""):
        raise SystemExit("mypy is not installed: `python -m pip install mypy` (CI pins the version)")
    counts: Counter = Counter()
    for line in (r.stdout or "").splitlines():
        m = _LINE.match(line)
        if m:
            counts[m.group("file").replace("\\", "/")] += 1
    if r.returncode not in (0, 1):
        # 2 is a crash or a usage error — not a count of anything.
        raise SystemExit(f"mypy did not finish (exit {r.returncode}):\n{r.stderr[-2000:]}")
    return counts


def load() -> dict:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text(encoding="utf-8")).get("errors", {})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--accept", action="store_true")
    a = ap.parse_args(argv)
    now = measure()
    if a.accept:
        BASELINE.write_text(json.dumps({
            "_meta": {"what": "mypy errors per module of src/scholion; may fall, may not grow",
                      "tool": "src/tools/check_types.py"},
            "errors": dict(sorted(now.items()))}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"recorded: {sum(now.values())} errors in {len(now)} modules")
        return 0
    base = load()
    grew = {f: (base.get(f, 0), n) for f, n in now.items() if n > base.get(f, 0)}
    fell = {f: (n, now.get(f, 0)) for f, n in base.items() if now.get(f, 0) < n}
    for f, n in now.most_common():
        print(f"{n:5d}  {f}" + (f"   (was {base.get(f, 0)})" if f in grew else ""))
    print(f"total {sum(now.values())} (baseline {sum(base.values())})")
    if fell:
        print("fewer than recorded — lower the line with --accept: "
              + ", ".join(f"{f} {a}→{b}" for f, (a, b) in fell.items()))
    if grew:
        print("MORE than recorded: " + ", ".join(f"{f} {a}→{b}" for f, (a, b) in grew.items()))
        return 1 if a.strict else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
