#!/usr/bin/env python3
"""A backward-compatibility check on the public contract.

Why. From the moment someone else uses the project, it acquires users of two
kinds: a human who has command names written down in shortcuts and scripts, and
an assistant that parses `--json` by field names. Both are a public interface,
even if nobody ever called it that. A silently renamed field looks to them like a
function that has disappeared.

What counts as the contract:
  1. **entry points** (`python3 -m scholion` and the `crossread` wrapper) — every
     call starts from them;
  2. **CLI command names** — a command that disappears breaks a shortcut and the skill;
  3. **top-level fields in `--json`** — a field that disappears breaks parsing;
  4. **environment variable names** by which the paths are set;
  5. **profile file names** that the core reads.

Items 1 and 4 were added after the project was renamed: the change of package and
variable names touched not a single command, so the check stayed silent — while
for the user every written-down invocation line stopped working. A contract that
does not see the most frequent way of breaking compatibility guards the wrong
thing.

The one-way rule: **adding is allowed, removing is not**. A new command and a new
field do not break compatibility. Deletion and renaming always do, and therefore
require an explicit human action: `--accept` overwrites the baseline, and then the
change must reach the CHANGELOG as an incompatible one.

Run:
    python3 src/tools/check_compat.py            # check
    python3 src/tools/check_compat.py --accept   # accept a new baseline (deliberately!)
    python3 src/tools/check_compat.py --show     # what is in the contract now
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
BASELINE = ROOT / "tests" / "contracts" / "public_contract.json"
FIXTURE = ROOT / "tests" / "fixtures" / "profile"

# Commands whose JSON is captured into the baseline. Writing and long-running ones
# are left out: their contract is the result of the operation, not the shape of a report.
SNAPSHOT_CMDS = [
    ["overview"], ["labs"], ["suggest-tests"], ["second-opinion"], ["radar"],
    ["medications"], ["markers"], ["metrics"], ["goal"], ["genome-status"],
    ["genome-updates"], ["clinvar"], ["acmg"], ["prs"], ["longevity"],
    ["profile"], ["assistant"], ["drug", "atorvastatin"],
    ["prescription", "atorvastatin"], ["phenoage", "--panels"],
]

ENTRYPOINTS = ["python3 -m scholion", "bin/crossread"]

# Read from the tree, not typed here. The list used to be six names while the code
# read twenty-one; the fifteen it did not name could be renamed in silence, because
# the check compared a frozen list against the same frozen list. That is the shape
# of gate this project has now been bitten by twice (the APOE table, the emitted
# vocabularies): a derivable table typed by hand goes stale without a sound.
#
# Only our own names and the ones we promise to honour are the contract. PATH, HOME
# and TMPDIR are read too, but they belong to the operating system: we do not get to
# promise anything about them, so they are not in the contract.
_ENV_READ = re.compile(r"""(?:environ\.get|getenv)\(\s*["']([A-Z][A-Z0-9_]*)["']"""
                       r"""|environ\[\s*["']([A-Z][A-Z0-9_]*)["']""")
FOREIGN_ENV = {
    # Not ours by name, but the product reads it and its behaviour depends on it.
    "PRS_MCP_PKG",
}


def env_vars() -> list:
    names = set()
    for p in sorted(SRC.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        for a, b in _ENV_READ.findall(p.read_text(encoding="utf-8", errors="ignore")):
            n = a or b
            if n.startswith("SCHOLION_") or n in FOREIGN_ENV:
                names.add(n)
    return sorted(names)


ENV_VARS = None      # filled in collect(); see env_vars() above

PROFILE_FILES = [
    "labs.json", "medications.json", "metrics.json", "health_goals.json",
    "focus.json", "lifestyle_brief.json", "pharmacogenomics.json", "experiments.json",
]


def _env() -> dict:
    e = dict(os.environ)
    e["PYTHONPATH"] = str(SRC) + os.pathsep + e.get("PYTHONPATH", "")
    e["SCHOLION_PROFILE_DIR"] = str(FIXTURE)
    e["SCHOLION_REPO_DIR"] = str(ROOT)
    e["SCHOLION_OFFLINE"] = "1"     # a contract snapshot must not depend on external references
    e["SCHOLION_GENOME_VCF"] = str(FIXTURE.parent / "no-such-file.vcf.gz")   # nor on a genome being present
    e["SCHOLION_GENOME_DIR"] = str(FIXTURE.parent / "no-such-genome-dir")
    return e


def collect() -> dict:
    """A snapshot of the current contract — on the synthetic fixture, not on personal data."""
    sys.path.insert(0, str(SRC))
    from scholion import contract as _c                # noqa: E402

    commands = sorted(_c.cli_commands())
    fields: dict = {}
    for argv in SNAPSHOT_CMDS:
        p = subprocess.run([sys.executable, "-m", "scholion", *argv, "--json"],
                           cwd=str(ROOT), env=_env(), capture_output=True, text=True)
        name = " ".join(argv[:1])
        if p.returncode != 0:
            fields[name] = {"__error__": "the command failed while the contract was being taken"}
            continue
        try:
            data = json.loads(p.stdout)
        except json.JSONDecodeError:
            fields[name] = {"__error__": "the --json output does not parse"}
            continue
        fields[name] = sorted(data.keys()) if isinstance(data, dict) else ["__list__"]
    return {"_note": "The baseline of the public contract. Adding is allowed; removing "
                     "only deliberately (--accept) and with an entry in the CHANGELOG "
                     "as an incompatible change.",
            "entrypoints": ENTRYPOINTS, "env_vars": env_vars(),
            "commands": commands, "json_fields": fields, "profile_files": PROFILE_FILES}


def compare(base: dict, cur: dict) -> list:
    problems = []
    for e in sorted(set(base.get("entrypoints", [])) - set(cur.get("entrypoints", []))):
        problems.append(f"INCOMPATIBLE: the entry point \"{e}\" has disappeared — every "
                        f"shortcut, the skill and the plugin that name it stop working")
    for v in sorted(set(base.get("env_vars", [])) - set(cur.get("env_vars", []))):
        problems.append(f"INCOMPATIBLE: the environment variable \"{v}\" is no longer read")
    lost = set(base.get("commands", [])) - set(cur.get("commands", []))
    for c in sorted(lost):
        problems.append(f"INCOMPATIBLE: the command \"{c}\" has disappeared — shortcuts and the skill break")
    for cmd, keys in (base.get("json_fields") or {}).items():
        now = cur.get("json_fields", {}).get(cmd)
        if now is None:
            problems.append(f"INCOMPATIBLE: JSON is no longer taken from \"{cmd}\"")
            continue
        for k in sorted(set(keys) - set(now)):
            problems.append(f"INCOMPATIBLE: \"{cmd} --json\" has lost the field \"{k}\"")
    for f in sorted(set(base.get("profile_files", [])) - set(cur.get("profile_files", []))):
        problems.append(f"INCOMPATIBLE: the profile file \"{f}\" is no longer read")
    return problems


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    cur = collect()
    if "--show" in argv:
        print(json.dumps(cur, ensure_ascii=False, indent=2))
        return 0
    if "--accept" in argv or not BASELINE.exists():
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        if BASELINE.exists():
            old = json.loads(BASELINE.read_text(encoding="utf-8"))
            for p in compare(old, cur):
                print("  ↳ accepted: " + p)
        BASELINE.write_text(json.dumps(cur, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"✅ Baseline written: {BASELINE.relative_to(ROOT)}")
        print("   If anything in the list above is a real loss, describe it in the "
              "CHANGELOG as an incompatible change and raise the major version.")
        return 0
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    problems = compare(base, cur)
    added = sorted(set(cur["commands"]) - set(base.get("commands", [])))
    if added:
        print("Added (compatible): " + ", ".join(added))
    if not problems:
        print(f"✅ Backward compatibility preserved: {len(cur['commands'])} commands, "
              f"{len(cur['json_fields'])} JSON snapshots.")
        return 0
    print("❌ Backward compatibility is broken:")
    for p in problems:
        print("  · " + p)
    print("\nIf the change is deliberate — run with --accept and describe it in the CHANGELOG.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
