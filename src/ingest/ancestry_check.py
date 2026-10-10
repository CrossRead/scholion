#!/usr/bin/env python3
"""Compatibility entry point for the packaged genome-derived population step.

Uses the active profile and connected genome, never a repository owner's paths.
PGS preparation invokes the same implementation automatically when needed.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from scholion.population import _cli  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_cli())
