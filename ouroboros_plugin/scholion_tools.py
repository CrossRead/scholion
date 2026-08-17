"""Ouroboros plugin — folder form.

The implementation lives inside the package (`scholion/ouroboros_tools.py`) so
that `pip install scholion` delivers it too. This file exists for the form where
the project is unpacked as a folder and never installed: it puts `src/` on the
import path and re-exports the same entry point, so there is one implementation
and two ways to reach it.

Install: copy either this file or `scholion/ouroboros_tools.py` into the tools
package of your Ouroboros checkout — discovery is a scan of `ouroboros.tools.*`,
and the contract is a module exporting `get_tools() -> list[ToolEntry]`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from scholion.ouroboros_tools import get_tools  # noqa: E402,F401

if __name__ == "__main__":
    for tool in get_tools():
        print(f"[tool] {tool.name}: {tool.schema['description'][:60]}...")
