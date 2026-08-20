"""Scholion — the shared core of the assistant for genome, labs and prescriptions.

Hybrid logic: deterministic functions (engine) compute facts and flags from the
reference data (knowledge/) and the profile (profile/), while the LLM wrappers
(Claude skill, Ouroboros plugin) phrase the individual analysis under safety rules.

There is a single core; only the thin wrappers on top of it differ.
"""
#: The minimum this package is tested on, and the ONE place it is stated in code.
#: `pyproject.toml` declares `>=3.10` to pip, and pip honours it — but a source
#: tree, a vendored copy or a system Python bypasses that metadata entirely, and
#: the reviewers ran the package on 3.9.6 with nothing said. Running on an
#: unsupported interpreter is not neutral: it either crashes somewhere far from
#: the cause, or works differently in a place nobody looks. `test_python_minimum`
#: keeps this pair and the declaration in `pyproject.toml` from drifting.
MINIMUM_PYTHON = (3, 10)


def _check_python() -> None:
    import sys as _sys
    if _sys.version_info < MINIMUM_PYTHON:
        have = ".".join(str(x) for x in _sys.version_info[:3])
        want = ".".join(str(x) for x in MINIMUM_PYTHON)
        raise RuntimeError(
            f"Scholion needs Python {want} or newer; this interpreter is {have} "
            f"({_sys.executable}). Refusing rather than running on an interpreter "
            f"nothing was tested on: the failure would surface somewhere far from "
            f"the cause. Install a newer Python and reinstall the package.")


_check_python()

from .engine import check_drug_gene, analyze_labs, suggest_tests, load_profile   # noqa: E402

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
