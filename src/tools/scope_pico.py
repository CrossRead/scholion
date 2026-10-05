#!/usr/bin/env python3
"""Write `web/pico.scoped.min.css` from Pico's own conditional build.

    python3 src/tools/scope_pico.py path/to/pico.conditional.min.css

Pico ships a «conditional» build that styles bare elements only inside an
element with the class `pico`. It scopes by prefixing every rule with `.pico `,
and that prefix adds one class to the specificity of every rule. This page's
own element rules — `nav button`, `header h1`, `input,select` — were written
against the unconditional build, where Pico's `button` loses to `nav button`;
behind `.pico button` it wins, and the redrawn page came out with Pico's
buttons over our tabs (0.6.0, first render).

`:where(.pico)` scopes the same way and counts for nothing, so the specificity
is exactly the unconditional build's while the scope stays. This script is the
whole change; the MIT banner at the top of Pico's file is kept, and a note under
it says what was done and where.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "src" / "scholion" / "web" / "pico.scoped.min.css"
NOTE = ("/* Scholion: Pico's conditional build with every `.pico` scope written as "
        "`:where(.pico)`, so the scope adds no specificity. src/tools/scope_pico.py */")


def scope(text: str) -> str:
    out = re.sub(r"\.pico(?![\w-])", ":where(.pico)", text)
    end = out.index("*/") + 2          # after Pico's own banner, which stays first
    return out[:end] + "\n" + NOTE + out[end:]


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2])
        return 2
    src = Path(argv[0]).read_text(encoding="utf-8")
    if "v2.1.1" not in src[:200]:
        print("✗ not Pico 2.1.1 — the version this project vendors and records in ATTRIBUTION.md")
        return 1
    OUT.write_text(scope(src), encoding="utf-8")
    print(f"✓ {OUT.relative_to(ROOT)} written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
