#!/usr/bin/env python3
"""Validate a reviewed bilingual extraction and emit an intake-joined registry.

Input: {notes: {rsID: {ru, en, review, provenance}}}. Extraction and translation
are reviewed before this step; no patient data or workbook binaries are copied.
An unknown position, missing translation or named reviewer refuses the WHOLE
import. With --check, compare against the packaged registry without writing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scholion.panel_notes import validate  # noqa: E402

KNOW = Path(__file__).resolve().parents[1] / "scholion" / "knowledge"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="new file only; never overwrite a registry")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        notes = raw["notes"]
        validate(notes, json.loads((KNOW / "panel_intake.json").read_text(encoding="utf-8")))
        if args.check:
            installed = json.loads((KNOW / "panel_author_notes.json").read_text(encoding="utf-8"))
            if installed["notes"] != notes:
                raise ValueError("extraction differs from the packaged registry")
        else:
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump({"notes": notes}, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("Import refused: " + str(exc), file=sys.stderr)
        return 1
    print(f"Validated {len(notes)} author notes against the intake ledger.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
