"""A denominator counts the thing its noun names.

The lipid card said, in one line: «genes: 38; positions of the curated panel: 7;
read: 11, unread: 34», and under it «unread of its genes: 34, of a list of 45».
Both numbers were true of the list as a whole and of neither half: 45 is 38 genes
plus 7 positions, and the 11 read are 4 genes and 7 positions. A reader binds a
count to the nearest noun, and here the nearest noun was the wrong one.

Two ways were open. Counting each half inside the VERDICT was tried and rejected:
the same state then produced two different sentences across the three entries,
which is the one thing task 171 forbids — a list of genes and a list of positions
refuse in one voice or the refusals drift apart. So the verdict keeps counting
the list and says ROWS, which is true of both halves, while the summary above it
counts each half against its own denominator, where there is room to.

Held here:

  * the verdict's noun is not «genes» while its denominator counts more than
    genes;
  * an unread position keeps the list from reading as clear, and is counted;
  * the summary line asks for a read count per half, and for no count over both.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion.engine import panel_form
from scholion.i18n import en, ru

SCAN = {"status": "ok"}


def _gene(name, read=True, findings=0):
    return {"unit": "gene", "gene": name, "read": read, "findings": findings}


def _pos(name, read=True, findings=0):
    return {"unit": "position", "gene": name, "rsid": "rs1", "read": read,
            "findings": findings}


class TestTheNounAndTheDenominatorAgree(unittest.TestCase):

    def test_the_sentence_does_not_say_genes_over_a_list_that_holds_more(self):
        for words, gene_word in ((en.MESSAGES, "genes"), (ru.MESSAGES, "генов")):
            for key in ("screen.and_unread", "screen.clear_partial"):
                with self.subTest(key=key, word=gene_word):
                    text = words[key]
                    head = text.split("{genes}")[0]     # the trailing list of names is fine
                    self.assertNotIn(gene_word + ":", head,
                                     "the count is over the rows of the list, not its genes")

    def test_the_denominator_counts_every_row_of_the_list(self):
        rows = [_gene("A"), _gene("B", read=False), _pos("P1"), _pos("P2")]
        v = panel_form.verdict(rows, SCAN)
        self.assertEqual(4, v["total"])
        self.assertEqual(1, v["unread"])

    def test_an_unread_position_keeps_the_list_from_reading_as_clear(self):
        rows = [_gene("A"), _pos("P1", read=False)]
        v = panel_form.verdict(rows, SCAN)
        self.assertEqual("clear_partial", v["kind"],
                         "every gene read and a position unread is not «clear»")
        self.assertEqual(1, v["unread"])


class TestTheSummaryCountsEachHalf(unittest.TestCase):

    def test_the_composed_line_asks_for_a_read_count_per_half(self):
        for words in (en.MESSAGES, ru.MESSAGES):
            text = words["system.genetics.composed"]
            for field in ("{base_genes}", "{read_genes}", "{positions}", "{read_positions}"):
                with self.subTest(field=field):
                    self.assertIn(field, text)
            bare = text.replace("{read_genes}", "").replace("{read_positions}", "")
            self.assertNotIn("{read}", bare,
                             "one read count over both halves is what this replaces")
            self.assertNotIn("{unread}", bare)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
