"""Scholion — the shared core of the assistant for genome, labs and prescriptions.

Hybrid logic: deterministic functions (engine) compute facts and flags from the
reference data (knowledge/) and the profile (profile/), while the LLM wrappers
(Claude skill, Ouroboros plugin) phrase the individual analysis under safety rules.

There is a single core; only the thin wrappers on top of it differ.
"""
from .engine import check_drug_gene, analyze_labs, suggest_tests, load_profile

__all__ = ["check_drug_gene", "analyze_labs", "suggest_tests", "load_profile"]
# Version — from the installed distribution's metadata, and when running from the
# source tree — from the VERSION file. Keeping it here as a literal is not possible:
# it has already diverged from VERSION (0.1.0 against 2.2.0) and would diverge again.
def _detect_version() -> str:
    from importlib.metadata import PackageNotFoundError, version as _v
    try:
        return _v("scholion")
    except PackageNotFoundError:
        from pathlib import Path as _P
        try:
            return (_P(__file__).resolve().parents[2] / "VERSION").read_text(
                encoding="utf-8").strip()
        except OSError:
            return "0+unknown"


__version__ = _detect_version()
