#!/usr/bin/env python3
"""A series belongs to a method, not to a substance.

    python3 src/tools/check_method_mixing.py          # the inventory, exit 1 on a mix
    python3 src/tools/check_method_mixing.py --json   # the same as a structure

## The rule

An element such as calcium is measured two ways. A clinical-chemistry analyser
reports it in a molar unit (mmol/L, µmol/L, or the equivalent mEq/L); an
elemental analysis (ICP, ICP-MS) reports mass per litre (mg/L, µg/L). The two
disagree beyond rounding — more than ten per cent on the same sample has been
seen for calcium — so a row that takes both and multiplies one into the other
by the atomic weight presents a change of method as a trend in the person.

A unit conversion is therefore legitimate WITHIN a method (mg/dL ↔ mmol/L of
the same biochemistry assay, µg/dL ↔ µg/L of the same ICP assay) and
illegitimate ACROSS methods. The dictionary spells this as two keys per
element, each declaring `method` (`icp` or `biochemistry`), the ICP key
accepting no molar unit at all, and each key gated off the other method's
forms. Calcium was split this way by hand on 08.09.2026; this tool holds the
rule for every element so that the next one is refused rather than found.

## What is checked, and why the list of elements is written here

The dictionary alone cannot say which analytes laboratories measure two ways —
that is a fact about laboratories, not about units. So the tool carries it:
`TWO_METHOD` names the elements with a clinical-chemistry assay AND an
elemental one, `ONE_METHOD` the elements that only atomic spectrometry
measures (a molar unit there is the same assay in a different unit, and one
row may keep both families). Everything else that accepts both families —
bilirubin in mg/dL, cortisol in µg/dL — is one assay in two conventions, and
is listed in the inventory with that verdict so the reader sees it was looked
at.

The unit family of a spelling is read through `knowledge/units.json`, which
maps every code to its English and Russian label, so that this file carries no
Russian and needs no list of spellings of its own.

Why the parser side matters: `ingest_labs` uses `units` as a GATE — a row whose
segment holds none of the marker's units is skipped — so an ICP key without a
gate stores a molar number as if it were µg/L, not converted, simply misread.
That is the shape `iron_blood` had until 12.09.2026, and the reason an ICP key
of a two-method element must declare a gate.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE = ROOT / "src" / "scholion" / "knowledge"

METHODS = ("icp", "biochemistry")

#: Elements a laboratory measures by clinical chemistry AND by elemental
#: analysis. Each needs two keys, and the reason is on record in the marker's
#: `method_note`.
TWO_METHOD = {
    "calcium": "colorimetric total calcium (mmol/L) and ICP (mg/L)",
    "magnesium": "colorimetric serum magnesium (mmol/L) and ICP (mg/L)",
    "zinc": "colorimetric serum zinc (µmol/L) and ICP (µg/L)",
    "copper": "colorimetric serum copper (µmol/L) and ICP (µg/L)",
    "iron": "ferrozine serum iron (µmol/L) and ICP whole-blood iron (µg/L)",
}

#: Elements with one assay only: a molar unit is the same measurement in a
#: different unit, and converting it is a conversion within the method.
ONE_METHOD = {
    "selenium": "atomic spectrometry (ICP-MS / AAS) is the only assay; no chemistry analyser measures it",
    "phosphorus": "inorganic phosphate is a chemistry assay; mg/dL is its US convention",
}

#: Elements the dictionary holds under one key and one unit family. Listed so
#: that a key starting with one of these words is recognised as an element
#: at all: the day one of them gains a second unit family, it must declare.
OTHER_ELEMENTS = (
    "potassium", "sodium", "chloride", "lithium", "manganese", "chromium", "iodine",
    "molybdenum", "cobalt", "boron", "nickel", "arsenic", "lead", "mercury", "cadmium",
    "aluminum", "strontium", "silver", "titanium", "thallium", "beryllium",
)

#: The key shapes that are «the element in blood, by some method». Any other
#: suffix is a different quantity — `calcium_ionized` is the free fraction,
#: not total calcium by another method — and stays outside the rule.
SERIES_SUFFIXES = ("", "_blood", "_total")

_MOLAR = re.compile(r"(?:^|\d)(?:[munp]?mol|meq)/l$")
_MASS = re.compile(r"^[munp]?g/(?:l|dl|ml)$")


def _norm(s: str) -> str:
    for sp in (" ", " ", " ", " "):
        s = s.replace(sp, "")
    return s.strip().casefold()


def load(knowledge: Path = KNOWLEDGE):
    markers = json.loads((knowledge / "lab_markers.json").read_text(encoding="utf-8"))["markers"]
    units = json.loads((knowledge / "units.json").read_text(encoding="utf-8"))["units"]
    return markers, units


def spelling_table(units: dict) -> dict:
    """Every spelling the label table knows → its code, case and spaces folded."""
    table = {}
    for code, entry in units.items():
        table[_norm(code)] = code
        for label in (entry.get("label") or {}).values():
            if isinstance(label, str):
                table[_norm(label)] = code
    return table


def family(spelling: str, table: dict):
    """'molar', 'mass', or None when the label table cannot place the spelling."""
    code = table.get(_norm(spelling))
    if code is None:
        return None
    c = code.casefold()
    if _MOLAR.search(c):
        return "molar"
    if _MASS.match(c):
        return "mass"
    return None


def spellings(spec: dict):
    """Every unit spelling a marker accepts, with where it was declared."""
    out = []
    if spec.get("unit"):
        out.append(("unit", spec["unit"]))
    for field in ("units", "convert"):
        for s in (spec.get(field) or {}):
            out.append((field, s))
    return out


def analyte_of(key: str):
    """The element a key is a series of, or None. Only the declared key shapes count."""
    for name in list(TWO_METHOD) + list(ONE_METHOD) + list(OTHER_ELEMENTS):
        if key in (name + suffix for suffix in SERIES_SUFFIXES):
            return name
    return None


def _ru(spec: dict, field: str):
    return ((spec.get("labels") or {}).get("ru") or {}).get(field) or []


def inventory(markers: dict, units: dict):
    """One row per marker that is under the rule or accepts both unit families.

    Each row: key, analyte, method, canonical unit, families (with the spelling
    the table could not place, if any), a verdict in words, and `problems` — the
    list that makes the tool exit 1. A row with an empty list passed.
    """
    table = spelling_table(units)
    rows = []
    by_analyte: dict = {}
    for key, spec in markers.items():
        fams, unplaced = set(), []
        for _field, s in spellings(spec):
            f = family(s, table)
            if f is None:
                unplaced.append(s)
            else:
                fams.add(f)
        analyte = analyte_of(key)
        method = spec.get("method")
        both = fams == {"molar", "mass"}
        if not (both or analyte in TWO_METHOD or method):
            continue
        row = {"key": key, "analyte": analyte, "method": method, "unit": spec.get("unit"),
               "families": sorted(fams), "unplaced": unplaced, "verdict": "", "problems": []}
        if method is not None and method not in METHODS:
            row["problems"].append(f"method {method!r} is not one of {METHODS}")
        if analyte is None:
            row["verdict"] = "not an element: one assay in two conventions, the conversion is within the method"
        elif analyte in ONE_METHOD:
            row["verdict"] = f"one method — {ONE_METHOD[analyte]}"
            if both and method is None:
                row["problems"].append("accepts both unit families and declares no method")
        elif analyte in TWO_METHOD:
            row["verdict"] = f"two methods — {TWO_METHOD[analyte]}"
            by_analyte.setdefault(analyte, []).append(row)
            if method is None:
                row["problems"].append("a series of a two-method element declares no method")
            elif method == "icp":
                molar = [s for f, s in spellings(spec) if family(s, table) == "molar"]
                if molar:
                    row["problems"].append("the ICP series accepts a molar unit: " + ", ".join(molar))
                if not spec.get("units"):
                    row["problems"].append("the ICP series has no unit gate — a molar row would be stored as mass")
                if family(spec.get("unit") or "", table) != "mass":
                    row["problems"].append("the ICP series' canonical unit is not mass per volume")
                if not (_ru(spec, "form_exclude") or _ru(spec, "form_require")):
                    row["problems"].append("the ICP series is not gated off biochemistry forms")
            elif method == "biochemistry":
                # No unit gate is demanded on this side. A gate narrows recognition
                # on every form that prints the unit once in a column header, and
                # `iron` carries years of history on such forms; the direction a
                # gate here would guard — an ICP mass row into the molar series — is
                # already stopped by the ICP key's own gate and by the form words.
                if family(spec.get("unit") or "", table) != "molar":
                    row["problems"].append("the biochemistry series' canonical unit is not molar")
                if not _ru(spec, "form_exclude"):
                    row["problems"].append("the biochemistry series is not gated off elemental forms")
            if unplaced:
                row["problems"].append("spellings the unit table cannot place: " + ", ".join(unplaced))
        else:
            row["verdict"] = "an element with one key; declares nothing"
            if both and method is None:
                row["problems"].append("accepts both unit families and declares no method")
        rows.append(row)

    for analyte, group in by_analyte.items():
        present = {r["method"] for r in group if r["method"] in METHODS}
        if present != set(METHODS):
            for r in group:
                r["problems"].append(f"{analyte}: the dictionary holds {sorted(present) or 'no'} method(s), "
                                     f"the split into both is missing")
    return rows


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    rows = inventory(*load())
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        print("Markers that accept both a molar and a mass-per-volume unit, or belong to a "
              "two-method element:\n")
        w = max(len(r["key"]) for r in rows) + 2
        for r in rows:
            fams = "+".join(r["families"]) or "-"
            print(f"  {r['key']:{w}} {(r['method'] or '-'):13} {(r['unit'] or '-'):8} {fams:11} {r['verdict']}")
            for p in r["problems"]:
                print(f"  {'':{w}} !! {p}")
    # With --json the structure is the whole of stdout, so that a caller can
    # parse it; the verdict in words goes to stderr and the exit code.
    out = sys.stderr if "--json" in argv else sys.stdout
    bad = [r for r in rows if r["problems"]]
    if bad:
        print(f"\nA series mixes methods: {len(bad)} marker(s) — "
              + ", ".join(r["key"] for r in bad), file=out)
        return 1
    print(f"\nno series mixes methods: {len(rows)} looked at", file=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
