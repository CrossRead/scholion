#!/usr/bin/env python3
"""How much Russian is left in what ships outward.

Owner's decision (15.08.2026): **the core and the public repository are in
English**, the output language is switched by the user, personal files stay in
Russian forever. The rule was adopted as "this is how it is always to be
developed", and so it must be enforced by a check rather than by memory: an
agreement about language is exactly the kind of rule that gets broken one line at
a time over a month and is noticed only by an outside reader.

    python3 src/tools/check_language.py             # summary by layer
    python3 src/tools/check_language.py --files     # by file, worst first
    python3 src/tools/check_language.py --strict    # exit 1 if the remainder grew
    python3 src/tools/check_language.py --accept    # record the current state as accepted

## Why `--strict` is not "zero"

The first plan was to translate everything and then fail on the first Cyrillic
letter. That target turned out to be unreachable, and not because the work was
unfinished: what remains is a recogniser quoting the Russian line it matches, a
lab-form pattern, the endonym in a language switcher. Each was examined one by
one and each has to stay. A gate set at an unreachable number never turns on,
and a gate that never turns on is indistinguishable from no gate at all.

So the gate is set on the DERIVATIVE instead. `language_baseline.json` records
what was accepted, file by file, after that review; `--strict` fails when a file
exceeds its accepted count or when a file appears that was never reviewed. The
enforced property is not "there is no Russian" but "no Russian was added without
somebody looking at it" — which is the property that was actually wanted, and
the only one that can be enforced honestly.

Raising the baseline is deliberate and visible: `--accept` rewrites the file, the
diff shows up in review, and the reason belongs in the commit message.

## Where Russian is allowed forever

The line runs not between files but between roles of the text.

**Input** — what the program RECOGNISES. Marker synonyms in
`knowledge/lab_markers.json` (the Russian names for LDL, for glycated
haemoglobin) are a dictionary for parsing Russian lab forms, that is, a function
of the product. Removing them removes the ability to read the forms; it does not
translate the interface.

**Output** — what the program PRINTS. Here there must be no Russian in the public
tree: it moves into the message catalogue `i18n/ru.py` and is switched on by the
user's choice.

It is easy to get this wrong exactly here: in one and the same JSON the
`synonyms` field is input, while the `note` field is output.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CYRILLIC = re.compile(r"[Ѐ-ӿ]")

# ── what we do not look at at all ────────────────────────────────────────
PERSONAL_DIRS = {"profile", "genome", "raw", "work", "archive", "reports", "_backups",
                 "_to_delete", "inbox", "kb", "demo", ".git", "__pycache__", ".cache",
                 "dist", "node_modules"}
PERSONAL_FILES = {
    "CHANGELOG.private.md",          # the owner's personal log
    "src/skill/SKILL.md",            # personal edition of the skill, with the clinical key
    ".personal_patterns",
    "_commit_msg.txt",               # a draft the assistant hands to the owner; gitignored
}

# ── Russian is allowed: as input, not as output ──────────────────────────
# JSON fields of the knowledge bases that SERVE TO RECOGNISE Russian lab forms
# and drug names. Everything else in the same files is printed to a human.
#
# The list was derived from the bases themselves, not invented: at first it was a
# set of guesses and reported 1912 violations in `lab_markers.json`, of which 1374
# turned out to be the recognition dictionary. A number obtained by guessing
# cannot be planned against — it overstates the work threefold and devalues the
# check.
INPUT_FIELDS = {
    # the dictionary for recognising lab forms
    "names", "name_ru", "names_ru", "synonyms", "aliases", "ru", "ru_name",
    "patterns", "match", "keywords", "brand_ru",
    # conditions matched against the text of a form: also input, also in Russian
    "form_require", "form_exclude", "prefer_form", "require", "exclude",
    "next_require", "next_exclude",
    "material",
}

# Units of measurement are a special case, and so are named separately rather
# than dumped into the list above. A unit such as mmol/L is at once read off the
# form AND printed in the report: as input it stays, as output it must be chosen
# by language. Until the message catalogue exists, we count them on a separate
# line so as not to confuse them with the real translation remainder.
UNIT_FIELDS = {"unit", "units"}

ALLOWED_FILES = {
    "src/scholion/i18n/ru.py",       # the catalogue of Russian messages — its point is Russian
}
ALLOWED_SUFFIXES = (
    ".ru.md",                        # deliberately Russian documents next to English ones
    ".ru.html",                      # the Russian presentation of the project
)

LAYERS = (
    ("core",             ("src/scholion",)),
    ("data preparation", ("src/ingest", "src/annotate")),
    ("tools",            ("src/tools",)),
    ("tests",            ("tests",)),
    ("plugin",           ("ouroboros_plugin",)),
    ("skill and rules",  ("share/SKILL.shared.md", "ASSISTANT-RULES.md")),
    ("documentation",    ("docs", "README.md", "share/README.md", "DISCLAIMER.md")),
    ("changelog",        ("CHANGELOG.md",)),
)


_OWNER_BEGIN, _OWNER_END = "<!-- OWNER:BEGIN -->", "<!-- OWNER:END -->"


# A Russian fragment quoted inside a comment as a SAMPLE of what the parser
# matches — a line from a lab form, a unit, a section name. It explains the code
# next to it; translating it would sever the comment from the regex it describes.
# Recognised by guillemets, the quoting style used consistently in this project.
#
# Such a line is counted on its own line of the report, not silently dropped.
# For a long time this pattern was defined here and never applied: the comment
# claimed samples were legitimate, the code counted them as debt, and the
# difference was roughly twofold on the biggest recogniser file. Excluding them
# outright would have been the worse repair of the two — a meter that understates
# the remaining work reports "done" while the work is still there. So they are
# separated rather than forgiven, the same way units of measurement are.
#
# Two quoting styles count. Guillemets are the project's own, used for a phrase.
# Backticks are the ordinary way to name a literal — a drug name, a field value,
# a folder — and an English changelog explaining which Russian string used to
# leak has no way to do it except by writing that string down. The backtick form
# is deliberately narrow: a SINGLE token, no spaces. A Russian sentence in
# backticks is prose that was never translated, and it stays counted as debt.
QUOTED_SAMPLE = re.compile(r"«[^»]*»|`[^`\s]+`")


def _without_personal(text: str) -> str:
    """Drop the marked personal block: Russian inside it is a decision, not a debt.

    Files such as `CLAUDE.md` ship in the package with that block cut out;
    counting it as translation remainder means keeping work in the report
    forever that will never be done.
    """
    i, j = text.find(_OWNER_BEGIN), text.find(_OWNER_END)
    if i >= 0 and j > i:
        return text[:i] + text[j + len(_OWNER_END):]
    return text


def _skip(rel: Path) -> bool:
    if set(rel.parts) & PERSONAL_DIRS:
        return True
    if str(rel) in PERSONAL_FILES or str(rel) in ALLOWED_FILES:
        return True
    return str(rel).endswith(ALLOWED_SUFFIXES)


_UNITS: dict = {}
_SAMPLES: dict = {}


def _text_hits(rel: Path, text: str) -> int:
    """Cyrillic lines in code or prose, with quoted samples put to one side."""
    debt = samples = 0
    for ln in text.splitlines():
        if not CYRILLIC.search(ln):
            continue
        if CYRILLIC.search(QUOTED_SAMPLE.sub("", ln)):
            debt += 1
        else:
            samples += 1
    _SAMPLES[str(rel)] = samples
    return debt


def _json_hits(path: Path) -> int:
    """Cyrillic in a knowledge-base JSON — only outside the recognition fields.

    We count values, not lines of the file: one `synonyms` field holding a list
    of twenty names would otherwise look like twenty violations, whereas it is a
    single legitimate place.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return sum(1 for ln in path.read_text(encoding="utf-8", errors="replace").splitlines()
                   if CYRILLIC.search(ln))
    count = 0
    units = 0

    def _is_language_map(node) -> bool:
        """A per-language map: every key a two-letter code, and there is a value.

        Everything under one is already routed through the language layer — it IS
        the translation — so it carries no remainder to count, whatever the field
        is called. Before the marker dictionary moved to `labels.<lang>`, this was
        achieved by accident: `ru` happened to be in INPUT_FIELDS, so a string
        directly under a `ru` key was skipped. That stopped holding the moment a
        language map gained a level («labels.ru.display»), and the measure would
        have reported hundreds of new violations for work that had just been done
        correctly. A number that jumps for the wrong reason is worse than no
        number: this one drives a release gate.
        """
        return (isinstance(node, dict) and bool(node)
                and all(isinstance(k, str) and len(k) == 2 and k.isalpha() for k in node))

    def walk(node, key=None):
        nonlocal count, units
        if isinstance(node, dict):
            if _is_language_map(node) and "en" in node:
                return
            # A language map WITHOUT an English branch is not translated — it is
            # Russian with a language key on it. Walking into it keeps that in the
            # remainder, which is the whole point of the measure: the fallback rule
            # («a missing language falls back to the one that exists») makes such an
            # entry work, not finished. Recognition fields inside it are still
            # skipped by INPUT_FIELDS, so only what gets PRINTED is counted.
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for v in node:
                walk(v, key)
        elif isinstance(node, str) and CYRILLIC.search(node):
            if key in INPUT_FIELDS:
                return
            if key in UNIT_FIELDS:
                units += 1
                return
            count += 1

    walk(data)
    _UNITS[str(path.relative_to(ROOT))] = units
    return count


def remainder() -> dict:
    """File → how many places hold Russian. An empty dict = the public tree is in English."""
    found = {}
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if _skip(rel):
            continue
        # `.toml` was missing here for a while, and `pyproject.toml` — the manifest
        # of the published package, 36 Russian lines of it — was therefore never
        # measured. A meter is only as honest as its list of extensions.
        if p.suffix.lower() not in (".py", ".md", ".json", ".html", ".sh", ".txt",
                                    ".yml", ".yaml", ".toml", ".cfg", ".ini", ".cff", ""):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        text = _without_personal(text)
        if not CYRILLIC.search(text):
            continue
        n = _json_hits(p) if p.suffix.lower() == ".json" else _text_hits(rel, text)
        if n:
            found[str(rel)] = n
    return found


BASELINE = Path(__file__).resolve().parent / "language_baseline.json"

ACCEPT_NOTE = (
    "Russian places accepted after review: recognition patterns, samples quoted "
    "next to the regex that matches them, endonyms. Written by "
    "`python3 src/tools/check_language.py --accept`. A number here may only be "
    "raised deliberately — see the docstring of that file."
)


def _accepted() -> dict:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text(encoding="utf-8")).get("files", {})


def _regressions(data: dict):
    """(grown files, files absent from the baseline).

    A file that fell BELOW its accepted count is not an error — work was done.
    It is not auto-lowered either: rewriting the baseline is an explicit act, so
    that a drop and a rise are both visible in the same diff.

    A file is looked up by path first and by bare name second. The reason is the
    package: the sanitizer flattens `share/PREPARING-THE-GENOME.md` to the root,
    so inside the delivery the same file has a different path, and a gate keyed
    on paths alone declared it brand new and failed the recipient's test run on
    text nobody had touched. The fallback is refused when two baseline entries
    share a name — there the guess would be arbitrary, and an arbitrary
    forgiveness is worse than a false alarm.
    """
    accepted = _accepted()
    names: dict = {}
    for k, v in accepted.items():
        names.setdefault(Path(k).name, []).append(v)
    by_name = {n: v[0] for n, v in names.items() if len(v) == 1}

    grew, appeared = [], []
    for k, v in sorted(data.items()):
        if k in accepted:
            if v > accepted[k]:
                grew.append((k, accepted[k], v))
        elif Path(k).name in by_name:
            was = by_name[Path(k).name]
            if v > was:
                grew.append((k, was, v))
        else:
            appeared.append((k, v))
    return grew, appeared


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    data = remainder()
    total = sum(data.values())

    if "--files" in argv:
        for name, n in sorted(data.items(), key=lambda kv: -kv[1]):
            print(f"{n:6}  {name}")
    else:
        print("Russian left in the public tree (input dictionaries are not counted):\n")
        counted = set()
        for label, paths in LAYERS:
            n = sum(v for k, v in data.items()
                    if any(k == p or k.startswith(p.rstrip("/") + "/") for p in paths))
            counted |= {k for k in data if any(k == p or k.startswith(p.rstrip("/") + "/") for p in paths)}
            print(f"  {label:20} {n:6}")
        other = sum(v for k, v in data.items() if k not in counted)
        if other:
            print(f"  {'other':20} {other:6}")
        print(f"  {'—' * 20} {'—' * 6}")
        print(f"  {'total':20} {total:6}   files: {len(data)}")
        units_total = sum(_UNITS.values())
        if units_total:
            print(f"\n  counted separately: {units_total} units of measurement — they are both\n"
                  f"  input and output; they are translated by choosing at print time,\n"
                  f"  not by replacing the value")
        samples_total = sum(_SAMPLES.values())
        if samples_total:
            print(f"\n  counted separately: {samples_total} lines that only quote a Russian\n"
                  f"  sample in «guillemets» — a line of a lab form shown next to the regex\n"
                  f"  that matches it. Translating one severs the comment from its code.")

    if "--accept" in argv:
        BASELINE.write_text(
            json.dumps({"_note": ACCEPT_NOTE, "files": dict(sorted(data.items()))},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n✅ accepted as the baseline: {total} in {len(data)} files "
              f"→ {BASELINE.relative_to(ROOT)}")
        print("   Say in the commit message what was added and why it has to stay.")
        return 0

    if "--strict" in argv:
        grew, appeared = _regressions(data)
        if grew or appeared:
            print("\n❌ Russian was added to the public tree")
            for name, was, now in grew:
                print(f"   {name}: {was} → {now}")
            for name, now in appeared:
                print(f"   {name}: {now} — the file is not in the baseline at all")
            print("\n   Either route the phrase through src/scholion/i18n, or — if it is\n"
                  "   input, a recognition pattern, a quoted sample — record the decision\n"
                  "   with `python3 src/tools/check_language.py --accept` and say why.")
            return 1
        print(f"\n✅ the remainder did not grow: {total} accepted places in {len(data)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
