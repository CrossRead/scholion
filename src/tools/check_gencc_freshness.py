#!/usr/bin/env python3
"""How far behind GenCC the shipped gene↔disease file is. No network.

    python3 src/tools/check_gencc_freshness.py                 # report; exit 1 past the limit
    python3 src/tools/check_gencc_freshness.py --max-days 30   # a stricter limit

Reads the two dates `knowledge/gencc_gene_disease.json` records — when it was
pulled and when GenCC last refreshed the export it was pulled from — and judges
by the second. A pull made yesterday of an export refreshed in March is a March
file. Exits 1 when there is no shipped file at all, because then the monogenic
half of every panel is authored by hand, and a reader of the check should know.

The logic lives in `fetch_gencc.py --age`; this is the door named the way every
other gate in this folder is named, so it is found beside them.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_gencc  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    return fetch_gencc.main(["--age"] + argv)


if __name__ == "__main__":
    raise SystemExit(main())
