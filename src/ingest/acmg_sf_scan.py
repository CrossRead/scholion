#!/usr/bin/env python3
"""The ACMG SF screen — kept as a path, run by the package.

    python3 src/ingest/acmg_sf_scan.py [personal.vcf.gz] [clinvar.vcf.gz]

The pass itself moved into the package on 10.09.2026 and is `scholion acmg-scan`.
It had to: this directory travels in the source archive and not in the wheel, so
after an ordinary `pip install` the product could say «the ACMG scan has not been
run» and offer nothing that would run it. Two copies of the same matching rules
would be worse than the original problem — the wrong one gets fixed — so what is
left here is the path, pointing at the one implementation.

The behaviour is the same in one respect that matters and better in another: the
same 84 genes, the same P/LP filter, the same per-gene reporting rules; and the
builds of the two files are now compared before a single position is, because
matching a GRCh37 file against the GRCh38 ClinVar finds nothing at all — or finds
a coordinate that belongs to another base — and both look like an answer.

Exit codes, because a shell script cannot read `--json`:

    0   the table was written (an empty table is a normal outcome, and is 0)
    2   the screen refused — no ClinVar file, crossed builds, several samples —
        and printed why; NOTHING was written, and a table from an earlier run
        still on disk is that earlier run's answer, not this one's
    1   the pass itself failed

`scholion acmg-scan` returns 0 on a refusal as well, on the ground that the
refusal is the answer; `quarterly_reanalysis.sh` branches on this script's code
to decide whether to read the table, and 0 there would read the stale one. Until
the two agree, the code that keeps the reanalysis honest is the one kept here.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from scholion import acmg_scan                                   # noqa: E402

#: The outcome that wrote a table, and the code for everything that answered
#: without writing one. Named so the script above and this one read one table.
EXIT_WRITTEN, EXIT_REFUSED = 0, 2


def main(argv) -> int:
    personal = argv[1] if len(argv) > 1 else None
    clinvar = argv[2] if len(argv) > 2 else None
    # No `out_dir`: the table goes where `scholion acmg` looks for it, which the
    # package decides. Naming a folder here made this path and the command write
    # to two places the moment the genome folder was not the repository's.
    res = acmg_scan.scan(personal_vcf=personal, clinvar_vcf=clinvar)
    print(res.get("message") or "")
    print(f"status: {res.get('status')}")
    if res.get("status") == "ok":
        print(f"personal records scanned: {res['scanned']}; "
              f"ClinVar records scanned: {res['clinvar_scanned']}; "
              f"no-calls at listed positions: {res.get('no_calls', 0)}; "
              f"rows with a FILTER other than PASS: {res.get('filtered', 0)}")
        return EXIT_WRITTEN
    return EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
