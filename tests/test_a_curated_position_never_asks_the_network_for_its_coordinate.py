"""A curated position carries its coordinate in the build, so a card never waits on a network.

On 17.09.2026 twenty-eight positions were added to the system panels and none
of them reached `loci.json`. Nothing failed: `genome.resolve_rsid` falls back to
Ensembl, so every render of the card asked the network for the coordinate and
waited about three and a half seconds per position — the amino acid card took
44 seconds to open, and a machine with no network would have shown the
positions as unread instead. The fallback is right for a rsID somebody types;
it is wrong as the way a shipped row finds its own position.

Two rules hold that: every curated position is in the locus catalogue, and the
coordinate there is the coordinate its HGVS states. The second one matters
because a plausible wrong number is the failure this whole catalogue exists to
prevent (task 40).
"""
from __future__ import annotations

import json
import re
import unittest

import support  # noqa: F401
from scholion import core

HGVS = re.compile(r"NC_0*(\d+)\.\d+:g\.(\d+)([ACGT])>([ACGT])$")
CHROM = {23: "X", 24: "Y"}


def _positions():
    systems = core._read_knowledge("system_gene_panels.json")["systems"]
    for key, spec in systems.items():
        for p in spec.get("positions") or []:
            yield key, p


def _catalogue():
    return json.loads(core.knowledge_path("loci.json").read_text(encoding="utf-8"))["loci"]


class TestEveryCuratedPositionIsInTheCatalogue(unittest.TestCase):

    def test_no_shipped_position_has_to_be_looked_up_online(self):
        loci = _catalogue()
        missing = sorted({p["rsid"] for _, p in _positions() if p["rsid"] not in loci})
        self.assertEqual([], missing,
                         "these positions would send every card to Ensembl: " + ", ".join(missing))

    def test_the_catalogue_says_what_the_hgvs_of_the_row_says(self):
        loci = _catalogue()
        wrong = []
        for key, p in _positions():
            m = HGVS.match(p.get("hgvs") or "")
            if not m:
                continue
            n = int(m.group(1))
            want = (CHROM.get(n, str(n)), int(m.group(2)), m.group(3))
            l = loci.get(p["rsid"]) or {}
            got = (str(l.get("chrom")), l.get("pos"), l.get("ref"))
            if got != want:
                wrong.append(f"{key}/{p['rsid']}: the row says {want}, the catalogue {got}")
        self.assertEqual([], wrong, "\n  ".join(wrong))


if __name__ == "__main__":
    unittest.main()
