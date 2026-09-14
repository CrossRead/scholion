"""An expectation about a genotype is not asked where no genotype was read.

`expect` lets the author of a panel declare a direction on a marker of the same
system — «with this genotype I expect LDL higher» — and the engine fills in the
person's last value and asks whether the picture agrees. Until 13.09.2026 it
asked that question for a position that had never been read: on the demo profile,
whose genome is not readable at all, five such questions stood on the lipid card,
each saying «with this genotype». There is no genotype until the position is
read.

Held here:

  * a read position with an expectation still raises the question;
  * an unread one raises none — and is named in the genome basket instead, so
    the author's expectation is not lost, it is waiting on the step that would
    answer it;
  * a marker never taken is still a gap, one question per marker, read or not.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion.engine import system_panels as SP

LOCI = {"loci": {"rsREAD": {"gene": "READ"}, "rsUNREAD": {"gene": "UNREAD"}}}
CALLS = {"rsREAD": {"genotype": "AG", "confidence": "called", "depth": 30},
         "rsUNREAD": {"genotype": None, "confidence": "assumed_ref", "why": "not_in_file"}}
TXT = {"en": "what follows", "ru": "what follows (ru)"}


def _lookup(rsid=None, gene=None):
    return {"status": "ok", "rsid": rsid, "result": dict(CALLS.get(rsid) or {})}


def _pos(rs, gene, marker="glucose"):
    return {"rsid": rs, "gene": gene, "hgvs": "NC_000001.11:g.100A>G", "risk_allele": "G",
            "mode": "monogenic", "classification": "Strong", "moi": "AD", "kind": "mechanism",
            "text": {"het": TXT, "hom": TXT}, "source": "the author",
            "expect": {"marker": marker, "direction": "higher"}}


CURATED = {"_meta": {"why_empty": "nobody wrote a row"},
           "systems": {"glucose": {"source": None,
                                   "positions": [_pos("rsREAD", "READ"),
                                                 _pos("rsUNREAD", "UNREAD")]}}}


class TestAnExpectationWaitsForTheReading(unittest.TestCase):

    def setUp(self):
        self._patches = [
            mock.patch.object(core, "loci", lambda: LOCI),
            mock.patch("scholion.genome.lookup", _lookup),
            mock.patch("scholion.genome.available", lambda: {"ready": True}),
            mock.patch.object(SP, "_base", lambda: {"_meta": {}, "systems": {}}),
            mock.patch.object(SP, "_curated", lambda: CURATED),
            mock.patch.object(SP, "_terms", lambda: {}),
            mock.patch.object(SP, "_clinvar_by_gene", lambda scan: {}),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()

    def _card(self):
        return SP.system("glucose", "clinician")

    def test_the_question_is_asked_of_the_position_that_was_read(self):
        asked = [q for q in self._card()["questions"]["rows"] if q.get("origin") == "expect"]
        self.assertEqual(["READ"], [q.get("gene") for q in asked],
                         "the expectation of a read position must still be asked")

    def test_no_question_speaks_of_a_genotype_at_a_position_nobody_read(self):
        card = self._card()
        for q in card["questions"]["rows"]:
            self.assertNotEqual("UNREAD", q.get("gene"),
                                "an expectation was asked of a position that was not read")

    def test_the_unread_position_is_named_in_the_genome_basket_instead(self):
        genome = self._card()["next"]["genome"]["rows"]
        self.assertIn("UNREAD", [r.get("gene") for r in genome],
                      "the position the expectation waits on must be named as unread")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
