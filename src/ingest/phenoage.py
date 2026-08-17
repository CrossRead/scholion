#!/usr/bin/env python3
"""PhenoAge (Levine 2018) — a wrapper over scholion.phenoage (formula and rules live there).

⚠️ RULE: compute from ONE panel only. All 9 markers come from a SINGLE blood draw.
If a marker is missing from the fresh panel, carrying it over from the previous one is
FORBIDDEN: the formula is sensitive to albumin and creatinine. The correct answer is
"cannot be computed" plus a list of what to add to the next draw.

Usage:
  python3 src/ingest/phenoage.py --panels              # which panels are complete
  python3 src/ingest/phenoage.py --panel 2026-07 [--track]
  python3 src/ingest/phenoage.py --panel latest
Equivalent through the application CLI:
  cd src && python3 -m scholion phenoage 2026-07 [--track] [--json]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from scholion import phenoage as pa  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="PhenoAge (Levine 2018), strictly from a single panel")
    p.add_argument("--panel", default="latest", help="the panel month YYYY-MM, or latest")
    p.add_argument("--panels", action="store_true", help="an overview of every panel and its completeness")
    p.add_argument("--age", type=float, default=None, help="override the age, in years")
    p.add_argument("--track", action="store_true", help="append to profile/biological_age_history.md")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    if a.panels:
        res, txt = pa.panels_overview(), None
        print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else pa.format_panels(res))
        return 0
    res = pa.compute_panel(a.panel, track=a.track, age=a.age)
    print(json.dumps(res, ensure_ascii=False, indent=2) if a.json else pa.format_result(res))
    return 0 if res.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
