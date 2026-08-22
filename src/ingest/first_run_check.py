#!/usr/bin/env python3
"""First run for a new user: what is already there, what is missing, what can be trusted.

The project was built for one person who had years of lab forms accumulated. A new
user has none — and the main danger lies not in empty screens but in silent
substitutions: showing someone else's reference range, computing biological age from
an incomplete panel, taking a template for a filled-in profile. The script checks
exactly that and states what must not be trusted in the current state.

The project's key rule, which is verified here:
    reference ranges are taken from the user's PRINTED LAB FORM, not from the code.
    No form — no range; the marker is shown WITHOUT a flag, and that is honest.
    Substituting a "generally accepted norm" is forbidden: it depends on the method,
    the units, sex and age, and a foreign norm creates false deviations out of nothing.

Run:  python3 src/ingest/first_run_check.py
Changes nothing — it only reads and prints. Sends nothing outside.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    from scholion import core
    PROFILE = Path(core.profile_dir())
except Exception as e:                                     # noqa: BLE001
    sys.exit(f"❌ cannot import the scholion package: {e}")

OK, WARN, BAD = "✓", "⚠", "✗"


def _load(name):
    p = PROFILE / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                      # noqa: BLE001
        return {}


def _is_template(obj) -> bool:
    """A template from the package differs from a filled-in profile by a mark in meta.

    The shipped templates carry the Russian word ШАБЛОН in meta.purpose, so both
    spellings are checked — dropping either would let a template pass as a profile.
    """
    if not isinstance(obj, dict):
        return False
    meta = obj.get("meta") or obj.get("_meta") or {}
    txt = " ".join(str(v) for v in meta.values() if isinstance(v, str)).upper()
    return "ШАБЛОН" in txt or "TEMPLATE" in txt


def main() -> int:
    print(f"First-run check · {date.today()}")
    print(f"Profile: {PROFILE}\n")
    problems, notes = [], []

    # --- 1. demographics: needed for the age-based calculations
    metrics = _load("metrics.json") or {}
    prof = metrics.get("profile", {}) if isinstance(metrics, dict) else {}
    sex, birth = prof.get("sex"), prof.get("birth_date") or prof.get("birth_year")
    if sex and birth:
        # The value itself is not printed — a first-run check only needs to confirm
        # demographics were entered, not to put a date of birth on the screen (or
        # in whatever captures this terminal's scrollback).
        print(f"{OK} demographics: sex {sex}, date of birth set")
    else:
        print(f"{BAD} demographics are not filled in (profile/metrics.json → profile.sex, birth_date)")
        problems.append("without sex and date of birth, biological age is not computed "
                        "and sex-dependent thresholds cannot be read")

    # --- 2. lab results and, above all, the reference ranges
    labs = _load("labs.json") or {}
    markers = labs.get("markers", {}) if isinstance(labs, dict) else {}
    if _is_template(labs) or not markers:
        print(f"{WARN} no lab results — that is a normal start: load the PDF forms "
              f"(python3 -m scholion ingest-labs \"<folder with PDFs>\")")
        notes.append("while there are no lab results, the laboratory part cannot be analysed — "
                     "and the application says so honestly instead of showing empty zeros")
    else:
        with_ref = sum(1 for m in markers.values()
                       if isinstance(m, dict) and (m.get("ref_low") is not None
                                                   or m.get("ref_high") is not None))
        share = with_ref / max(len(markers), 1)
        state = OK if share >= 0.8 else WARN
        print(f"{state} markers: {len(markers)}, of them with a reference range: "
              f"{with_ref} ({share:.0%})")
        if share < 0.8:
            notes.append(f"{len(markers) - with_ref} markers have no range — they are "
                         f"shown WITHOUT a deviation flag. That is the correct behaviour: "
                         f"someone else's norm would create false deviations. The range will "
                         f"appear by itself once a reference line is printed on the form")

    # --- 3. genome
    # detected exactly as the application does — otherwise the check answers another question
    avail = {}
    try:
        from scholion import genome as _g
        avail = _g.available() or {}
    except Exception:                                      # noqa: BLE001
        pass
    if avail.get("ready"):
        print(f"{OK} genome connected: {Path(str(avail.get('vcf', '?'))).name}")
    elif avail.get("vcf"):
        print(f"{BAD} genome found but not ready to be read "
              f"({avail.get('reason') or 'no .tbi index'})")
        problems.append("build the index: tabix -p vcf <file in genome/>")
    else:
        print(f"{WARN} no full VCF — the genome part answers «the database is not connected». "
              f"How to obtain it is described in genome/README.md")

    # --- 4. prescriptions
    meds = _load("medications.json") or {}
    lst = meds.get("medications", []) if isinstance(meds, dict) else []
    if _is_template(meds) or not lst:
        print(f"{WARN} no prescriptions — the check of interactions and control tests "
              f"will be empty until the regimen is entered")
    else:
        print(f"{OK} prescriptions: {len(lst)}")

    # --- 5. biological age: completeness of the panels
    try:
        from scholion import phenoage
        ov = phenoage.panels_overview()
        complete = ov.get("complete", []) or []
        panels = ov.get("panels", []) or []
        if not panels:
            print(f"{WARN} PhenoAge: no panels — a draw with all 9 markers on one day is needed")
        elif not complete:
            miss = panels[-1].get("missing_ru", [])
            print(f"{WARN} PhenoAge: no complete panels; the latest one is missing: "
                  f"{', '.join(miss)}")
            notes.append("biological age is computed ONLY from a complete panel of a "
                         "single draw — substituting values from other months is forbidden")
        elif len(complete) == 1:
            print(f"{WARN} PhenoAge: only one complete panel ({complete[0]}) — "
                  f"there is a value, but the PACE of ageing is not computed")
            notes.append("a slope through one point does not exist: a second complete "
                         "panel is needed for a series")
        else:
            print(f"{OK} PhenoAge: complete panels {len(complete)} — a series can be built")
    except Exception as e:                                 # noqa: BLE001
        print(f"{WARN} PhenoAge not checked: {e}")

    # --- 6. external utilities: what is missing and what exactly that blocks
    import shutil
    tools = [
        ("bcftools", "fast VCF reading", "not critical: there is a pure-python reader, tabixlite"),
        ("samtools", "working with BAM (coverage, re-genotyping, star alleles)",
         "without it only the BAM scripts are unavailable; the application and the lab analysis work"),
        ("tabix", "VCF indexing", "needed once, while preparing the genome"),
        ("java", "PharmCAT (the CPIC report)", "needed only for diplotype-level pharmacogenetics"),
        ("mosdepth", "callability of the clinical genes", "needed only for that check"),
    ]
    missing = [(n, what, ok) for n, what, ok in tools if shutil.which(n) is None]
    have = [n for n, _, _ in tools if shutil.which(n) is not None]
    if have:
        print(f"{OK} external utilities found: {', '.join(have)}")
    for n, what, consequence in missing:
        print(f"{WARN} `{n}` is missing ({what}) — {consequence}")
    if missing:
        names = " ".join(n for n, _, _ in missing)
        print(f"    install if needed:  brew install {names}")
        notes.append("THE APPLICATION ITSELF needs no external utilities: reading the genome "
                     "works on pure Python (tabixlite), and parsing lab results and "
                     "prescriptions all the more so. The utilities are needed only by the "
                     "raw-data scripts, and each of them checks for its own tools and refuses "
                     "with a clear message rather than crashing with a traceback")

    # --- 7. action thresholds: where they are limited by context
    try:
        th = json.loads((ROOT / "src/scholion/knowledge/clinical_thresholds.json")
                        .read_text(encoding="utf-8")).get("markers", {})
        gated = sorted({k for k, rules in th.items()
                        for r in (rules or []) if r.get("applies_when_class")})
        noted = sorted({k for k, rules in th.items()
                        for r in (rules or []) if r.get("applies_to")})
        if gated:
            print(f"{OK} thresholds limited by drug class (the engine enforces this): "
                  + ", ".join(gated))
        if noted:
            print(f"{OK} thresholds with a human-readable applicability note: " + ", ".join(noted))
            notes.append("the `applies_to` note is NOT enforced by the engine — it is a hint "
                         "for the reader. The machine-enforced restriction is only "
                         "`applies_when_class`. Most thresholds are derived from outcomes and "
                         "are the same for adults")
    except Exception:                                      # noqa: BLE001
        pass

    print()
    if problems:
        print("Needs action:")
        for p in problems:
            print(f"  {BAD} {p}")
    if notes:
        print("What to trust and what not to:")
        for n in notes:
            print(f"  · {n}")
    print("\nWhat the project NEVER does with an empty profile: it does not substitute "
          "someone else's reference ranges, does not fill in missing markers from "
          "neighbouring draws, and does not show a biological age from an incomplete "
          "panel. An empty place is called empty.")
    print("Not a diagnosis. Every conclusion is material for a conversation with a doctor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
