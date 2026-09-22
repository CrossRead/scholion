"""No position of an authored list leaves it without a word.

Task 204 closed with the sentence «a silently dropped row must not exist», and
nothing checked it. On 21.09.2026 the panel author asked why SRD5A1 rs1691053 —
a row she had placed herself on 17.09 — was nowhere in the product, and a check
of her whole list of 29.06.2026 against the catalogue of 0.5.4 found twelve rows
like it: not in the catalogue, not in any waiting list, not named in the
backlog. Seven of them she had placed herself (task 205).

`knowledge/panel_intake.json` is the ledger: every position the list names is
`in_catalogue` or waiting/refused with a reason and the backlog row that closes
it. These tests make the ledger the only way a position can be absent.
"""
from __future__ import annotations

import json
import re
import unittest

import support

KNOW = support.SRC / "scholion" / "knowledge"
INTAKE = KNOW / "panel_intake.json"


def _load(name):
    return json.loads((KNOW / name).read_text(encoding="utf-8"))


@unittest.skipUnless(INTAKE.exists(), "the intake ledger is not part of this build")
class TestTheLedger(unittest.TestCase):

    def setUp(self):
        self.ledger = _load("panel_intake.json")
        self.loci = {k.lower() for k in _load("loci.json")["loci"]}

    def lists(self):
        return self.ledger["lists"].items()

    def test_every_position_is_in_the_catalogue_or_says_why_not(self):
        silent = []
        for name, lst in self.lists():
            for p in lst["positions"]:
                rs = p["rsid"].lower()
                if rs in self.loci:
                    continue
                if p.get("disposition") in ("waiting", "refused") and (p.get("reason") or "").strip():
                    continue
                silent.append(f"{name} row {p['row']}: {p.get('gene') or '—'} {rs}")
        self.assertEqual([], silent, "positions absent from the catalogue with no reason")

    def test_in_catalogue_means_in_the_catalogue_and_on_a_panel(self):
        """A coordinate nobody reads is not an answer: the position is on a panel a card shows."""
        text = "".join((KNOW / f).read_text(encoding="utf-8")
                       for f in ("system_gene_panels.json", "on_demand_panels.json"))
        shown = {x.lower() for x in re.findall(r'"rsid":\s*"(rs\d+)"', text, re.I)}
        stale = [f"row {p['row']} {p['rsid']}" for _, lst in self.lists() for p in lst["positions"]
                 if p.get("disposition") == "in_catalogue"
                 and (p["rsid"].lower() not in self.loci or p["rsid"].lower() not in shown)]
        self.assertEqual([], stale)

    def test_a_waiting_position_that_arrived_is_marked_as_arrived(self):
        """The other direction: a reason that outlived its position misleads the next reader."""
        arrived = [f"row {p['row']} {p['rsid']}" for _, lst in self.lists() for p in lst["positions"]
                   if p.get("disposition") != "in_catalogue" and p["rsid"].lower() in self.loci]
        self.assertEqual([], arrived)

    def test_a_waiting_position_names_the_backlog_row_that_closes_it(self):
        open_md = (support.ROOT / "backlog" / "open.md")
        if not open_md.exists():
            self.skipTest("the backlog does not travel")
        text = open_md.read_text(encoding="utf-8")
        opened = {m.group(1) for m in re.finditer(r"^\| (\d+) \|", text, re.M)}
        bad = [f"row {p['row']} {p['rsid']} → {p.get('task')}" for _, lst in self.lists() for p in lst["positions"]
               if p.get("disposition") == "waiting"
               and (re.match(r"\d+", str(p.get("task") or "")) or [None])[0] not in opened]
        self.assertEqual([], bad, "a waiting position must point at an open backlog row")

    def test_the_list_is_whole(self):
        for name, lst in self.lists():
            positions = lst["positions"]
            self.assertEqual(lst["distinct_positions"], len(positions), name)
            self.assertEqual(len(positions), len({p["rsid"].lower() for p in positions}), name)
            self.assertTrue(all(re.fullmatch(r"rs\d+", p["rsid"]) for p in positions), name)

    def test_the_ledger_carries_nothing_but_identifiers(self):
        """rsID, gene, row, disposition and the product's own reason — no phrase, genotype or name
        from the author's file travels in the package through this ledger."""
        allowed = {"row", "rsid", "gene", "disposition", "reason", "recorded_in", "task"}
        extra = {k for _, lst in self.lists() for p in lst["positions"] for k in p} - allowed
        self.assertEqual(set(), extra)

    def test_the_older_waiting_list_agrees(self):
        """199 D recorded its own waiting list; where the two speak of one position, they agree."""
        w = (_load("system_gene_panels.json").get("_meta") or {}).get("waiting_199d") or {}
        arrived = sorted(rs for rs in w if rs.lower() in self.loci)
        self.assertEqual([], arrived, "waiting_199d still lists positions that are in the catalogue")


if __name__ == "__main__":
    unittest.main()
