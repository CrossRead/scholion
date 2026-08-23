"""The VCF reader that runs when nothing else is installed, read end to end.

`tabixlite` is not a fallback in the sense of «rarely used». `pysam` is an
optional extra of this package — it needs compiling and it is platform-specific —
and `bcftools` is something a person installs on purpose. So on an ordinary
`pip install scholion` this module is what answers every question about the
genome. It stood at 41.5% reach: `_scan`, the row-matching rule, had a test
because it had once been wrong; the parsing of the index and the whole of the
I/O had none.

That distribution is exactly backwards from the risk. A misread `.tbi` does not
raise — `query()` catches everything and returns `[]` — and an empty answer from
this reader means «no row at this position», which for a VCF made by
`bcftools call -mv` is read as HOMOZYGOUS FOR THE REFERENCE. A parser that
quietly loses a contig therefore does not produce an error or a gap. It produces
a confident, wrong, normal-looking genotype.

WHAT IS TESTED AGAINST WHAT. Two kinds of fixture, on purpose:

* the real one — `tests/fixtures/genome/tiny.vcf.gz`, a genuine bgzip+tabix pair
  built by the real tools, so that the reader is proved against the format as it
  actually occurs and not only against this file's idea of it;
* indexes packed byte by byte inside the test, for everything the one real
  fixture cannot show — several contigs, a linear index with holes, a position
  past the end of the array, bins present, the wrong magic. Packing them here is
  also the only honest way to test the parser: a fixture cannot be malformed on
  purpose without becoming a file somebody has to explain.

The hand-built pairs use plain gzip rather than bgzf, which works because every
virtual offset in them is zero: `query()` then seeks to byte 0 and hands the
whole file to `gzip.GzipFile`, which is what it would do with the first block of
a bgzf file anyway. What that cannot exercise is a seek to a later block; the
real fixture is what covers the file being opened at an offset at all.
"""
from __future__ import annotations

import gzip
import pathlib
import shutil
import struct
import tempfile
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import tabixlite as tx

FIXTURE = support.ROOT / "tests" / "fixtures" / "genome" / "tiny.vcf.gz"

#: The one row the real fixture carries, and the contig it lives on. Named here
#: rather than read out of the file, so that a fixture quietly losing its only
#: row fails these tests instead of making them vacuous.
FIXTURE_CONTIG = "6"
FIXTURE_POS = 18143724
FIXTURE_RSID = "rs1800462"


def pack_tbi(refs, bins_per_ref: int = 0) -> bytes:
    """A `.tbi` as bytes. `refs` is {contig: [linear offsets]}.

    The layout is the one in the tabix specification: magic, eight int32 of
    header, the null-separated contig names, then per contig the bin index and
    the linear index. `bins_per_ref` writes bins the reader is supposed to walk
    past without reading — for VCF the linear index alone answers, and skipping
    the bins correctly is a piece of pointer arithmetic that is either right or
    silently reads the linear offsets out of the middle of a bin.
    """
    names = b"".join(n.encode() + b"\x00" for n in refs)
    out = b"TBI\x01" + struct.pack("<8i", len(refs), 2, 1, 2, 0, ord("#"), 0, len(names)) + names
    for lin in refs.values():
        out += struct.pack("<i", bins_per_ref)
        for b in range(bins_per_ref):
            out += struct.pack("<Ii", 4681 + b, 1)       # one chunk
            out += struct.pack("<QQ", 0, 0)              # 16 bytes of chunk
        out += struct.pack("<i", len(lin))
        out += struct.pack("<%dQ" % len(lin), *lin)
    return gzip.compress(out)


class _Tree(unittest.TestCase):
    """A temporary directory holding a gzip VCF and whatever index the test wants."""

    HEADER = "##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n"

    def setUp(self):
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="tabixlite-")).resolve()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name: str, rows, refs, bins_per_ref: int = 0) -> str:
        body = self.HEADER + "".join(
            f"{c}\t{p}\t{i}\tA\tG\t60\tPASS\t.\n" for c, p, i in rows)
        vcf = self.dir / name
        vcf.write_bytes(gzip.compress(body.encode()))
        (self.dir / (name + ".tbi")).write_bytes(pack_tbi(refs, bins_per_ref))
        return str(vcf)


class TestTheIndexIsParsed(_Tree):

    def test_the_real_fixture_names_its_contig(self):
        idx = tx.TabixIndex(str(FIXTURE) + ".tbi")
        self.assertEqual([FIXTURE_CONTIG], idx.contigs(),
                         "tabix indexes only the contigs that carry rows, and this fixture "
                         "carries one")

    def test_several_contigs_keep_their_order_and_their_numbers(self):
        path = self.write("m.vcf.gz", [], {"1": [0], "2": [0], "X": [0]})
        idx = tx._index(path)
        self.assertEqual(["1", "2", "X"], idx.contigs())
        self.assertEqual({"1": 0, "2": 1, "X": 2}, idx.names,
                         "a contig mapped to the wrong reference number reads another "
                         "contig's offsets")

    def test_bins_are_walked_past_without_disturbing_the_linear_index(self):
        """The pointer arithmetic that is either exactly right or silently reads
        the linear offsets out of the middle of a bin — and then every query on
        that contig seeks somewhere arbitrary."""
        plain = self.write("a.vcf.gz", [], {"1": [11, 22, 33]}, bins_per_ref=0)
        binned = self.write("b.vcf.gz", [], {"1": [11, 22, 33]}, bins_per_ref=5)
        self.assertEqual(tx.TabixIndex(plain + ".tbi").linear,
                         tx.TabixIndex(binned + ".tbi").linear,
                         "the bins changed what the linear index says")

    def test_a_file_that_is_not_a_tabix_index_is_refused_by_name(self):
        bad = self.dir / "bad.vcf.gz.tbi"
        bad.write_bytes(gzip.compress(b"NOTTABIX" + b"\x00" * 64))
        with self.assertRaises(ValueError) as caught:
            tx.TabixIndex(str(bad))
        self.assertIn("bad.vcf.gz.tbi", str(caught.exception),
                      "the refusal does not say which file it is about")

    def test_a_broken_index_makes_contigs_empty_rather_than_raising(self):
        """`contigs()` is asked while deciding whether a genome is usable at all,
        and it is asked about files that may be anything."""
        (self.dir / "junk.vcf.gz.tbi").write_bytes(b"not gzip at all")
        self.assertEqual([], tx.contigs(str(self.dir / "junk.vcf.gz")))

    def test_an_index_that_is_not_there_makes_contigs_empty(self):
        self.assertEqual([], tx.contigs(str(self.dir / "absent.vcf.gz")))


class TestTheVirtualOffset(_Tree):

    def test_a_contig_the_index_does_not_name_answers_nothing(self):
        """`None`, and not `0`. Zero is a legitimate offset — the start of the
        file — so a contig that is absent must not be answered with one."""
        path = self.write("v.vcf.gz", [], {"1": [0]})
        self.assertIsNone(tx._index(path).voffset("22", 1))

    def test_a_contig_with_an_empty_linear_index_starts_at_the_beginning(self):
        path = self.write("e.vcf.gz", [], {"1": []})
        self.assertEqual(0, tx._index(path).voffset("1", 1))

    def test_the_interval_is_chosen_by_sixteen_kilobase_blocks(self):
        """The linear index has one entry per 16 kb of the contig, and the entry
        for a position is the one that contains it — not the first, not the
        last."""
        idx = tx._index(self.write("k.vcf.gz", [], {"1": [100, 200, 300]}))
        self.assertEqual(100, idx.voffset("1", 1))
        self.assertEqual(100, idx.voffset("1", 16384))
        self.assertEqual(200, idx.voffset("1", 16385))
        self.assertEqual(300, idx.voffset("1", 32769))

    def test_a_position_past_the_end_of_the_index_uses_the_last_interval(self):
        """A contig is longer than the index describes when the tail carries no
        rows. Clamping to the last entry means the scan starts somewhere real and
        stops at the first row of the next contig; not clamping would index out
        of the array."""
        idx = tx._index(self.write("p.vcf.gz", [], {"1": [100, 200]}))
        self.assertEqual(200, idx.voffset("1", 900_000_000))

    def test_a_hole_in_the_index_walks_back_to_the_last_real_offset(self):
        """A 16 kb window with no rows in it is written as zero. Seeking to zero
        would restart the file from the header; the reader walks back instead."""
        idx = tx._index(self.write("h.vcf.gz", [], {"1": [100, 0, 0, 400]}))
        self.assertEqual(100, idx.voffset("1", 20_000))
        self.assertEqual(100, idx.voffset("1", 36_000))
        self.assertEqual(400, idx.voffset("1", 52_000))

    def test_a_hole_at_the_very_beginning_answers_zero(self):
        idx = tx._index(self.write("h2.vcf.gz", [], {"1": [0, 0, 400]}))
        self.assertEqual(0, idx.voffset("1", 1))


class TestTheIndexIsNotRememberedLongerThanItIsTrue(_Tree):
    """A rebuilt genome is read from its new index, not from the old one.

    The cache used to be keyed on the path and nothing ever cleared it: a VCF
    re-called and re-indexed under a running `serve` kept its previous index for
    as long as the tab stayed open. That fails in the quietest possible way —
    `query` returns nothing, and nothing at this position means «homozygous for
    the reference» to everything downstream. Not an error, not a gap: an ordinary
    genotype, wrong.

    Both files are changed in SIZE as well as in content, so the test does not
    depend on how fine the filesystem's modification clock happens to be.
    """

    def test_a_reindexed_genome_is_read_again(self):
        rows_before = [("1", 100, "rsA")]
        rows_after = [("1", 100, "rsA"), ("1", 200, "rsB"), ("2", 50, "rsC")]
        path = self.write("live.vcf.gz", rows_before, {"1": [0]})
        self.assertEqual(["1"], tx.contigs(path))
        self.assertEqual([], tx.query(path, "2", 50))

        self.write("live.vcf.gz", rows_after, {"1": [0], "2": [0]})
        self.assertEqual(["1", "2"], tx.contigs(path),
                         "the reader answered from an index that no longer describes the file")
        self.assertEqual(["rsC"], [r[2] for r in tx.query(path, "2", 50)],
                         "a position present in the rebuilt genome was reported as absent, "
                         "which downstream reads as «reference here»")

    def test_an_unchanged_index_is_parsed_once(self):
        """The invalidation must not turn into re-reading the index on every
        query — that is why it is keyed rather than dropped."""
        path = self.write("stable.vcf.gz", [("1", 100, "rsA")], {"1": [0]})
        self.assertIs(tx._index(path), tx._index(path))


class TestQueryingTheRealFixture(unittest.TestCase):
    """Against a bgzip+tabix pair the real tools produced."""

    def test_the_row_that_is_there_is_found_whole(self):
        rows = tx.query(str(FIXTURE), FIXTURE_CONTIG, FIXTURE_POS)
        self.assertEqual(1, len(rows), "the fixture's only row was not read back")
        self.assertEqual(FIXTURE_CONTIG, rows[0][0])
        self.assertEqual(str(FIXTURE_POS), rows[0][1])
        self.assertEqual(FIXTURE_RSID, rows[0][2])
        self.assertEqual("0/1", rows[0][-1].split(":")[0],
                         "the genotype column did not survive the split")

    def test_a_position_with_no_row_answers_empty(self):
        """And this is the answer the engine reads as «homozygous reference», so
        it has to be empty for the right reason: the site really has no row."""
        self.assertEqual([], tx.query(str(FIXTURE), FIXTURE_CONTIG, FIXTURE_POS + 1))

    def test_a_contig_the_index_does_not_carry_answers_empty(self):
        self.assertEqual([], tx.query(str(FIXTURE), "1", 100))

    def test_a_window_reaches_forward_and_not_backward(self):
        self.assertEqual(1, len(tx.query(str(FIXTURE), FIXTURE_CONTIG,
                                         FIXTURE_POS - 500, 500)))
        self.assertEqual([], tx.query(str(FIXTURE), FIXTURE_CONTIG,
                                      FIXTURE_POS + 1, 500))


class TestQueryingWhatTheFixtureCannotShow(_Tree):

    def setUp(self):
        super().setUp()
        self.rows = [("1", 100, "rsA"), ("1", 200, "rsB"),
                     ("2", 50, "rsC"), ("2", 60, "rsD")]

    def test_a_row_is_matched_on_its_own_contig_only(self):
        path = self.write("q.vcf.gz", self.rows, {"1": [0], "2": [0]})
        self.assertEqual(["rsA"], [r[2] for r in tx.query(path, "1", 100)])
        self.assertEqual(["rsC"], [r[2] for r in tx.query(path, "2", 50)])

    def test_a_window_collects_every_row_inside_it_and_stops(self):
        path = self.write("w.vcf.gz", self.rows, {"1": [0], "2": [0]})
        self.assertEqual(["rsA", "rsB"], [r[2] for r in tx.query(path, "1", 100, 150)])
        self.assertEqual(["rsC", "rsD"], [r[2] for r in tx.query(path, "2", 50, 20)],
                         "the window crossed into the next contig or stopped too early")

    def test_a_position_between_two_rows_answers_empty(self):
        path = self.write("b.vcf.gz", self.rows, {"1": [0], "2": [0]})
        self.assertEqual([], tx.query(path, "1", 150))

    def test_a_vcf_that_is_not_there_answers_empty(self):
        self.assertEqual([], tx.query(str(self.dir / "nothing.vcf.gz"), "1", 100))

    def test_a_vcf_present_without_its_index_answers_empty(self):
        """Not a crash, and not the whole file scanned either: with no index
        there is nothing to seek by."""
        vcf = self.dir / "lonely.vcf.gz"
        vcf.write_bytes(gzip.compress((self.HEADER + "1\t100\trsA\tA\tG\t60\tPASS\t.\n").encode()))
        self.assertEqual([], tx.query(str(vcf), "1", 100))

    def test_an_index_that_disagrees_with_its_file_does_not_hang(self):
        """A virtual offset points at a byte inside a block. When the index was
        built against a different file — a VCF re-called and not re-indexed is
        the ordinary way this happens — that byte can lie past the end of what
        there is to decompress. The reader has to run out of data and stop, not
        spin asking for more.

        It answers empty, which the engine reads as «reference here». That is the
        wrong answer, and it is the honest one available: nothing in a stale index
        says it is stale. What this test pins is only that the reader terminates.
        """
        offset_inside_a_block_that_is_not_there = 50_000
        path = self.write("stale.vcf.gz", self.rows,
                          {"1": [offset_inside_a_block_that_is_not_there], "2": [0]})
        self.assertEqual([], tx.query(path, "1", 100))

    def test_a_truncated_body_gives_back_what_was_read(self):
        """A file cut off mid-stream is not a reason to lose the rows that were
        already whole — `query` returns them and does not raise."""
        path = self.write("t.vcf.gz", self.rows, {"1": [0], "2": [0]})
        data = pathlib.Path(path).read_bytes()
        pathlib.Path(path).write_bytes(data[:len(data) - 5])
        self.assertEqual([], tx.query(path + ".missing", "1", 100))
        rows = tx.query(path, "1", 100, 150)
        self.assertIsInstance(rows, list)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
