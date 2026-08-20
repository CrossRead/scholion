"""A query past the end of a contig stops there instead of reading to EOF.

The defect: the row scanner skipped every row of another contig, whichever side
of ours it lay on. A position past the end of chr1 therefore matched nothing and
kept decompressing chr2, chr3 and the rest of the file — on a personal VCF of
about 200 MB a single call of minutes, and inside the PGS re-genotyping loop a
practical hang. Nothing was wrong with the answer, so no test that checked
answers could see it.

The rule being tested is a rule about ordering, so it is tested on ordered lines
rather than on a bgzf file: the I/O was never the part that was wrong.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion.tabixlite import _scan


def rows(*specs):
    return [f"{c}\t{p}\t.\tA\tG".encode() for c, p in specs]


class TestTheScanStops(unittest.TestCase):

    def test_a_row_of_the_next_contig_ends_the_scan(self):
        lines = rows(("1", 100), ("1", 200), ("2", 5), ("3", 5), ("4", 5))
        out, seen, stop = _scan(lines, "1", 100, 0, False)
        self.assertTrue(stop, "chr1 is over at the first chr2 row — there is nothing further to find")
        self.assertTrue(seen)
        self.assertEqual([r[1] for r in out], ["100"])

    def test_a_position_past_the_end_of_the_contig_still_stops(self):
        """The case that hung: nothing matches, and the file goes on for gigabytes."""
        lines = rows(("1", 100), ("2", 5), ("3", 5))
        out, seen, stop = _scan(lines, "1", 9_000_000, 0, False)
        self.assertEqual(out, [])
        self.assertTrue(stop, "no match is not a reason to read the rest of the genome")

    def test_the_tail_of_the_previous_contig_is_skipped_not_stopped_on(self):
        """The index lands on the start of a block, which may still hold chr1 rows."""
        lines = rows(("1", 900), ("1", 950), ("2", 100), ("2", 200))
        out, seen, stop = _scan(lines, "2", 100, 100, False)
        self.assertFalse(stop, "we had not reached chr2 yet — stopping here would lose the answer")
        self.assertTrue(seen)
        self.assertEqual([r[1] for r in out], ["100", "200"])

    def test_a_position_past_the_window_ends_the_scan(self):
        lines = rows(("1", 100), ("1", 150), ("1", 400))
        out, seen, stop = _scan(lines, "1", 100, 100, False)
        self.assertTrue(stop)
        self.assertEqual([r[1] for r in out], ["100", "150"])

    def test_seen_carries_across_batches(self):
        """query() reads in 1 MB chunks; the contig may end in the next chunk."""
        first, seen, stop = _scan(rows(("1", 100)), "1", 100, 1000, False)
        self.assertFalse(stop)
        self.assertTrue(seen)
        second, seen, stop = _scan(rows(("2", 1)), "1", 100, 1000, seen)
        self.assertTrue(stop, "the contig ended in the next chunk and the scan must end with it")
        self.assertEqual(second, [])

    def test_headers_and_junk_do_not_confuse_it(self):
        lines = [b"##fileformat=VCFv4.2", b"", b"1\tnot-a-number\t.\tA\tG"] + rows(("1", 100))
        out, seen, stop = _scan(lines, "1", 100, 0, False)
        self.assertEqual([r[1] for r in out], ["100"])
        self.assertFalse(stop)


if __name__ == "__main__":
    unittest.main()
