"""A VCF with no index, read anyway — and the paths that used to close on it.

Found from outside, and the sequence matters. A reviewer was handed three
clinical VCFs: valid, bgzip-compressed, single-sample, and without `.tbi`. His
machine had no bcftools, no tabix and no pysam — the ordinary state of an
ordinary machine. Every reader in this package seeks by position and every seek
needs an index, so the genomic layer answered that it could not read them. He
installed pysam into a temporary directory and built the indexes by hand.

A physician will not do that, and a package that requires it has not shipped its
genomic layer at all. So a file with no index is now read the only way a file can
be read without one: once, from beginning to end. The single pass keeps three
things and nothing else — the rows on the catalogue's positions in both builds,
the counts in the windows the class measurement needs, and the header. It is
cached under the file's identity, so the pass happens once per file rather than
once per question.

Deliberately not an index builder: a `.tbi` written wrong is worse than none,
because bcftools and pysam would trust it and answer from the wrong place.
"""
from __future__ import annotations

import gzip
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import callset, genome, linear


def block(data: bytes) -> bytes:
    """One BGZF block, written by hand so this holds on a machine with no htslib."""
    comp = zlib.compressobj(6, zlib.DEFLATED, -15)
    body = comp.compress(data) + comp.flush()
    extra = b"BC" + struct.pack("<H", 2) + struct.pack("<H", len(body) + 25)
    head = b"\x1f\x8b\x08\x04" + b"\0" * 6 + struct.pack("<H", len(extra)) + extra
    return head + body + struct.pack("<II", zlib.crc32(data) & 0xFFFFFFFF, len(data))


def bgzf(data: bytes) -> bytes:
    """A complete BGZF file: the data in blocks of 60 KB, then the empty block
    bgzip writes last. Several blocks, so that a cut between two of them — a
    valid gzip stream that simply stops early — is something a test can make."""
    out = b"".join(block(data[i:i + 60_000]) for i in range(0, len(data), 60_000))
    return out + linear.BGZF_EOF


#: APOE rs429358 in GRCh38, and the same locus's GRCh37 coordinate. Both are
#: collected by the pass, because which build the file is in is decided later.
APOE38 = ("19", 44908684)
APOE37 = ("19", 45411941)


def vcf_text(rows, samples=("ME",)) -> bytes:
    head = ("##fileformat=VCFv4.2\n##source=SYNTHETIC test fixture\n"
            "##contig=<ID=19,length=58617616>\n"
            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t" + "\t".join(samples) + "\n")
    return (head + "".join("\t".join(r) + "\n" for r in rows)).encode()


class _NoIndex(unittest.TestCase):
    """A folder holding one bgzip VCF and no index at all."""

    KEYS = ("SCHOLION_GENOME_DIR", "SCHOLION_GENOME_VCF", "SCHOLION_GENOME_SAMPLE",
            "SCHOLION_GENOME_ENGINE", "SCHOLION_CACHE_DIR")

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in self.KEYS}
        for k in self.KEYS:
            os.environ.pop(k, None)
        self.dir = Path(tempfile.mkdtemp())
        os.environ["SCHOLION_GENOME_DIR"] = str(self.dir)
        genome.samples_of.cache_clear()

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        genome.samples_of.cache_clear()

    def write(self, rows, name="genome.vcf.gz", samples=("ME",)):
        p = self.dir / name
        p.write_bytes(bgzf(vcf_text(rows, samples)))
        return p


class TestTheSinglePass(_NoIndex):

    def test_a_row_on_a_catalogue_position_is_found(self):
        p = self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        got = linear.rows_at(str(p), "19", APOE38[1])
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][4], "C")

    def test_both_builds_of_a_locus_are_collected(self):
        """Which build the file is in is established from its contigs, and that
        happens after this pass. Collecting one build here would make the pass
        depend on an answer it exists to help produce."""
        p = self.write([["19", str(APOE37[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        self.assertEqual(len(linear.rows_at(str(p), "19", APOE37[1])), 1)

    def test_a_position_nobody_asked_about_is_not_kept(self):
        """The rows of somebody's genome are not a cache."""
        p = self.write([["19", "12345", ".", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        snap = linear.snapshot(str(p))
        self.assertEqual(snap["variants"], 1)
        self.assertEqual(snap["rows"], {})

    def test_the_contig_may_be_written_either_way(self):
        p = self.write([["chr19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        self.assertEqual(len(linear.rows_at(str(p), "19", APOE38[1])), 1)

    def test_a_file_that_is_not_a_vcf_is_not_read(self):
        p = self.dir / "notes.vcf.gz"
        p.write_bytes(gzip.compress(b"this is not a vcf\n"))
        self.assertFalse(linear.usable(str(p)))
        self.assertEqual(linear.why_not(str(p)), "not_a_vcf")
        # Not `[]`: an empty list at a position is «reference», and nothing here
        # was read.
        with self.assertRaises(linear.Unreadable):
            linear.rows_at(str(p), "19", APOE38[1])


class TestTheLayerAnswersWithoutAnIndex(_NoIndex):

    def test_the_status_names_the_reader_that_needs_none(self):
        self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        av = genome.available()
        self.assertEqual(av["engine"], "linear")
        self.assertTrue(av["ready"], "a readable VCF is not «no genome» because a sidecar is missing")

    def test_the_genotype_is_read(self):
        self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        got = genome._gt_at(dict(genome.locus("rs429358"), rsid="rs429358"))
        self.assertEqual(got["confidence"], "called")
        self.assertEqual(got["genotype"], "TC")

    def test_the_status_line_says_why_the_first_question_is_slow(self):
        from scholion.i18n import t as _t
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                self.assertNotIn("⟦", _t("genome_status.no_index_linear"))
            finally:
                os.environ.pop("SCHOLION_LANG", None)


class TestThePassIsPaidForOnce(_NoIndex):

    def test_the_second_question_does_not_read_the_file_again(self):
        """Fifty-four loci used to mean fifty-four reads of the same cache file,
        per command. The pass is one pass; so is reading its result."""
        p = self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        linear._MEMO.clear()
        first = linear.snapshot(str(p))
        self.assertTrue(first)
        opened = []
        real_open = linear._open
        linear._open = lambda v: opened.append(v) or real_open(v)
        try:
            for _ in range(5):
                linear.rows_at(str(p), "19", APOE38[1])
        finally:
            linear._open = real_open
        self.assertEqual(opened, [], "the file was re-opened after the pass was already made")

    def test_a_file_too_large_to_read_in_one_pass_is_not_claimed(self):
        """A reader that takes a file and then answers nothing is the defect this
        project has fixed twice. Past the cap the honest answer is the old one:
        this file needs an index."""
        p = self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        linear._MEMO.clear()
        saved = linear.MAX_MB
        linear.MAX_MB = 0
        try:
            self.assertFalse(linear.usable(str(p)))
            self.assertIsNone(genome.available()["engine"])
        finally:
            linear.MAX_MB = saved

    def test_a_pass_already_made_is_not_refused_by_the_cap(self):
        p = self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        linear._MEMO.clear()
        linear.snapshot(str(p))                      # pay for it once
        saved = linear.MAX_MB
        linear.MAX_MB = 0
        try:
            self.assertTrue(linear.usable(str(p)))
        finally:
            linear.MAX_MB = saved


class TestWhatTheLinearReaderMayNotAnswer(_NoIndex):
    """The half of the change that keeps the index rule intact.

    The pass keeps the catalogue's positions and nothing else, so a question over
    a whole REGION — any gene outside the catalogue — cannot be answered from it,
    and the seeking readers cannot answer it either without the index they seek
    by. The first version of this work only redirected the point query and left
    the region query returning `[]`, which is a sentence about the person: «this
    gene carries no variants». Under a status line saying the genome is
    connected, that is the exact defect the index rule was written against.
    """

    def test_a_region_query_refuses_by_name(self):
        p = self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        with self.assertRaises(genome.RangeNeedsIndex):
            genome._query_region_range(str(p), "19", 1, 100000)

    def test_a_gene_outside_the_catalogue_is_refused_and_not_reported_empty(self):
        """The whole point, taken through the command a person would type.

        The gene is resolved here by a stub, because whether an Ensembl
        annotation happens to be on this machine has nothing to do with the
        property under test: given a resolved gene and a file with no index, the
        answer must be a refusal that names the index — and never a report
        carrying «0 variants».
        """
        self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        from scholion import gene_region, genes
        saved = genes.resolve
        genes.resolve = lambda gene, allow_network=True: {
            "gene": gene, "chrom": "19", "start": 44_900_000, "end": 44_920_000,
            "strand": 1, "cds": []}
        try:
            out = gene_region.report("BRCA1")
        finally:
            genes.resolve = saved
        self.assertEqual(out["status"], "needs_index")
        self.assertNotIn("variants", out, "a count here would be a claim nothing measured")
        self.assertIn("tabix", out["message"])

    def test_the_frame_says_which_question_the_missing_index_closes(self):
        self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        paths = {p["path"]: p for p in genome.available()["paths"]}
        self.assertTrue(paths["loci"]["open"], "the catalogue is what the pass collected")
        self.assertFalse(paths["region"]["open"])
        self.assertEqual(paths["region"]["why"], "needs_index")

    def test_the_limitation_is_listed_with_what_closes_it(self):
        self.write([["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]])
        from scholion import limits as _lim
        items = [i for i in _lim._genome_limits() if "index" in i["why"].lower()]
        self.assertTrue(items, "a person told «connected» and nothing else will ask it a gene")
        self.assertIn("tabix", items[0]["closes"])

    def test_the_sentences_exist_in_both_languages(self):
        from scholion.i18n import t as _t
        import os as _os
        for lang in ("en", "ru"):
            _os.environ["SCHOLION_LANG"] = lang
            try:
                for key in ("paths.region", "paths.why_needs_index",
                            "genome.refused.needs_index", "limits.no_index_what",
                            "limits.no_index_why", "limits.no_index_closes"):
                    with self.subTest(lang=lang, key=key):
                        self.assertNotIn("⟦", _t(key))
            finally:
                _os.environ.pop("SCHOLION_LANG", None)


class TestTheClassIsStillMeasured(_NoIndex):
    """`unmeasured` closes ClinVar and the ACMG list, so a file nobody could
    probe was a file whose paths shut for a reason that was about us."""

    def test_the_windows_are_counted_on_the_way_through(self):
        rows = [["17", str(40_000_000 + i * 1000), ".", "A", "G", "50", "PASS", ".", "GT", "0/1"]
                for i in range(600)]
        p = self.write(rows)
        counted = linear.probe_counts(str(p))
        self.assertTrue(counted, "the pass must produce window counts, not only rows")
        self.assertEqual(sum(c["observed"] for c in counted["coding"]), 600)

    def test_an_exome_shaped_file_with_no_index_measures_as_an_exome(self):
        """Populated in the three gene-dense windows, empty in the gene-poor
        ones: the shape of an exome, and the class that opens ClinVar and the
        ACMG list on it. This used to assert only «not unmeasured», which the
        class `sparse` also satisfies — and `sparse` shuts both paths."""
        rows = []
        for chrom, start in (("17", 40_000_000), ("11", 62_000_000), ("19", 35_000_000)):
            # Substitutions and indels both, as a real call set has: a file of
            # substitutions alone is a split call set, and classified as one.
            rows += [[chrom, str(start + i * 500), ".", "A", "G" if i % 5 else "GT",
                      "50", "PASS", ".", "GT", "0/1"] for i in range(400)]
        p = self.write(sorted(rows, key=lambda r: (r[0], int(r[1]))))
        m = callset.measure(str(p))
        self.assertEqual(m["class"], "exome", m)
        self.assertEqual(m["coding_probes_dense"], 3)

    def test_a_thin_screen_with_no_index_measures_as_sparse(self):
        """The same pass, the opposite shape: a few rows in a gene-poor window
        and nothing where the genes are is a screen, and stays closed."""
        rows = [["1", str(20_000_000 + i * 100_000), ".", "A", "G", "50", "PASS", ".", "GT", "0/1"]
                for i in range(100)]
        p = self.write(rows)
        m = callset.measure(str(p))
        self.assertEqual(m["class"], "sparse", m)


def _first_block_size(raw: bytes) -> int:
    """BSIZE of the first block: total block size minus one, at offset 16."""
    return struct.unpack("<H", raw[16:18])[0] + 1


class TestAFileThatDoesNotReachItsEndIsNotRead(_NoIndex):
    """R1 of the 0.4.11 audit, reproduced exactly as reported.

    A heterozygous APOE ε4 carrier, three thousand rows, the file cut in half by
    an interrupted copy. The half that remained was a valid gzip stream — it
    simply stopped — and the pass over it returned its rows, found none at
    rs429358, and the locus answered `TT, assumed_ref`: a carrier printed as a
    non-carrier, under a status line that said the genome was connected.
    """

    def setUp(self):
        super().setUp()
        linear._MEMO.clear()
        filler = [["19", str(40_000_000 + i * 100), ".", "A", "G", "50", "PASS", ".", "GT", "0/1"]
                  for i in range(3000)]
        het = [["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]]
        self.whole = bgzf(vcf_text(filler + het))
        self.assertGreater(len(self.whole), 2 * len(linear.BGZF_EOF) + _first_block_size(self.whole),
                           "the fixture must span several blocks for a cut to be possible")

    def _put(self, raw: bytes):
        p = self.dir / "genome.vcf.gz"
        p.write_bytes(raw)
        genome.samples_of.cache_clear()
        return p

    def test_a_file_cut_between_two_blocks_is_named_truncated(self):
        p = self._put(self.whole[:_first_block_size(self.whole)])
        self.assertEqual(linear.why_not(str(p)), "truncated")
        self.assertTrue(linear.bgzf_eof_missing(str(p)))
        self.assertFalse(linear.bgzf_eof_missing(str(self._put(self.whole))))

    def test_the_carrier_is_not_printed_as_a_non_carrier(self):
        """The wrong answer itself. Before the fix: `TT`, `assumed_ref`."""
        self._put(self.whole[:_first_block_size(self.whole)])
        got = genome._gt_at(dict(genome.locus("rs429358"), rsid="rs429358"))
        self.assertIsNotNone(got, "a named refusal, not silence")
        self.assertIsNone(got["genotype"])
        self.assertEqual(got["confidence"], "unreadable_file")
        self.assertEqual(got["reason"], "truncated")
        self.assertNotIn("⟦", got["note"])

    def test_the_status_does_not_say_ready_over_it(self):
        self._put(self.whole[:_first_block_size(self.whole)])
        av = genome.available()
        self.assertFalse(av["ready"])
        self.assertIsNone(av["engine"])
        self.assertEqual(av["reason"], "unreadable_file")
        self.assertEqual((av["unusable"] or {}).get("reason"), "truncated")
        from scholion import format as fmt
        out = fmt.genome_status_report(av)
        self.assertNotIn("⟦", out)
        self.assertIn("genome.vcf.gz", out)

    def test_a_pass_that_dies_half_way_is_a_failure_and_not_a_reference(self):
        """The other cut: the end-of-file block is there, and a block in the
        middle is damaged. The pass starts, fails, and the failure — not an
        empty row list — is what every question after it meets."""
        first = _first_block_size(self.whole)
        raw = bytearray(self.whole)
        for i in range(first + 30, first + 60):
            raw[i] ^= 0xFF
        p = self._put(bytes(raw))
        self.assertIsNone(linear.why_not(str(p)), "the damage is not visible from the outside")
        snap = linear.snapshot(str(p))
        self.assertTrue(snap.get("failed"), snap)
        self.assertEqual(linear.why_not(str(p)), "pass_failed")
        with self.assertRaises(linear.Unreadable):
            linear.rows_at(str(p), "19", APOE38[1])
        self.assertEqual(linear.probe_counts(str(p)), {})
        got = genome._gt_at(dict(genome.locus("rs429358"), rsid="rs429358"))
        self.assertEqual((got or {}).get("confidence"), "unreadable_file")
        self.assertEqual(got["reason"], "pass_failed")
        self.assertIsNone(got["genotype"])

    def test_the_status_meets_the_failed_pass_first(self):
        """`available()` makes the pass itself, so the failure is in the status
        and not one question later under a line that already said «ready»."""
        first = _first_block_size(self.whole)
        raw = bytearray(self.whole)
        for i in range(first + 30, first + 60):
            raw[i] ^= 0xFF
        self._put(bytes(raw))
        av = genome.available()
        self.assertFalse(av["ready"])
        self.assertEqual((av["unusable"] or {}).get("reason"), "pass_failed")
        self.assertTrue((av["unusable"] or {}).get("detail"))

    def test_a_whole_file_is_still_read(self):
        """The check must not turn away the file it exists to protect."""
        self._put(self.whole)
        got = genome._gt_at(dict(genome.locus("rs429358"), rsid="rs429358"))
        self.assertEqual((got["confidence"], got["genotype"]), ("called", "TC"))

    def test_a_file_past_the_cap_says_it_needs_an_index_by_name(self):
        self._put(self.whole)
        saved = linear.MAX_MB
        linear.MAX_MB = 0
        try:
            got = genome._gt_at(dict(genome.locus("rs429358"), rsid="rs429358"))
        finally:
            linear.MAX_MB = saved
        self.assertEqual(got["confidence"], "needs_index")
        self.assertIsNone(got["genotype"])

    def test_the_sentences_exist_in_both_languages(self):
        from scholion.i18n import t as _t
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                for key in ("genome_status.unusable_truncated", "genome_status.unusable_pass_failed",
                            "genome.refused_head.truncated", "genome.refused_head.pass_failed",
                            "genome.refused_head.needs_index", "genome.unreadable_truncated",
                            "genome.unreadable_pass_failed", "genome.unreadable_not_a_vcf",
                            "genome.too_large_for_one_pass"):
                    with self.subTest(lang=lang, key=key):
                        self.assertNotIn("⟦", _t(key, path="x", detail="d", mb=1))
            finally:
                os.environ.pop("SCHOLION_LANG", None)


class TestTheSnapshotIsSomebodysGenotypes(_NoIndex):
    """B.16. The rows the pass keeps are the sample columns of fifty-four
    clinical loci — APOE, F5, DPYD — in clear text. They were written to the
    application cache, a folder `SCHOLION_CACHE_DIR` may point at any disk,
    against the module's own sentence that the rows of a genome are not a cache.
    They now live beside the genome, in the one folder already treated as this
    person's data; and they never CREATE that folder.
    """

    ROW = [["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT", "0/1"]]

    def setUp(self):
        super().setUp()
        linear._MEMO.clear()
        self.cache = Path(tempfile.mkdtemp())
        os.environ["SCHOLION_CACHE_DIR"] = str(self.cache)

    def test_the_rows_are_not_written_to_the_application_cache(self):
        p = self.write(self.ROW)
        self.assertTrue(linear.snapshot(str(p)).get("rows"))
        self.assertEqual(list(self.cache.rglob("linear-*.json")), [],
                         "somebody's genotypes in the application cache")
        beside = list((self.dir / "cache").glob("linear-*.json"))
        self.assertEqual(len(beside), 1, "the snapshot is kept beside the genome")

    def test_the_cache_never_creates_a_genome_folder(self):
        """An absent genome folder means «no genome connected». A cache that
        creates it would make the product believe one is."""
        absent = self.dir / "absent"
        os.environ["SCHOLION_GENOME_DIR"] = str(absent)
        p = self.dir / "elsewhere.vcf.gz"
        p.write_bytes(bgzf(vcf_text(self.ROW)))
        self.assertTrue(linear.snapshot(str(p)).get("rows"))
        self.assertFalse(absent.exists(), "the row cache created a genome folder")
        self.assertEqual(list(self.cache.rglob("linear-*.json")), [])

    def test_the_snapshot_is_written_whole_or_not_at_all(self):
        """B.17: a reader that opens the file while it is being written must
        never parse half a snapshot — the half it parses answers for the
        positions it does not hold. Written to a temporary name and renamed."""
        p = self.write(self.ROW)
        seen = []
        real = os.replace

        def spy(src, dst):
            seen.append((str(src), str(dst)))
            return real(src, dst)
        os.replace = spy
        try:
            linear.snapshot(str(p))
        finally:
            os.replace = real
        self.assertEqual(len(seen), 1, "the snapshot was not written through a rename")
        src, dst = seen[0]
        self.assertTrue(src.endswith(".tmp"))
        self.assertTrue(dst.endswith(".json") and Path(dst).exists())
        self.assertEqual(list((self.dir / "cache").glob("*.tmp")), [])

    def test_two_threads_make_one_pass(self):
        """B.17: the web server answers each request on its own thread, and two
        status requests used to start two passes over the same file."""
        import threading
        import time
        p = self.write(self.ROW)
        passes = []
        real = linear._pass

        def slow(vcf):
            passes.append(vcf)
            time.sleep(0.3)
            return real(vcf)
        linear._pass = slow
        try:
            ts = [threading.Thread(target=linear.snapshot, args=(str(p),)) for _ in range(2)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
        finally:
            linear._pass = real
        self.assertEqual(len(passes), 1, "two passes over one file")

    def test_a_file_rewritten_within_the_same_second_is_another_file(self):
        """B.22: the identity was whole-second mtime plus size, so a file
        replaced within the second by one of the same size answered with the
        old file's genotypes."""
        p = self.write(self.ROW)
        st = os.stat(p)
        before = (linear._stamp(str(p)), callset._cache_path(str(p)))
        same_second = (st.st_mtime_ns // 1_000_000_000) * 1_000_000_000 + 1_000
        os.utime(p, ns=(st.st_atime_ns, same_second))
        after = (linear._stamp(str(p)), callset._cache_path(str(p)))
        self.assertEqual(int(os.stat(p).st_mtime), int(st.st_mtime), "the test did not stay in the second")
        self.assertNotEqual(before[0], after[0], "the reader's identity did not notice the rewrite")
        self.assertNotEqual(before[1], after[1], "the class measurement's identity did not notice it")

    def test_the_cap_is_a_wait_and_not_an_afternoon(self):
        """B.18. The cap is on the compressed size, the only number known before
        the pass; at the throughput of the standard-library reader 8 GB
        compressed was hours with no progress shown."""
        if os.environ.get("SCHOLION_LINEAR_MAX_MB"):
            self.skipTest("the cap is overridden in this environment")
        self.assertLessEqual(linear.MAX_MB, 2048)


class TestTheSecondLineOfDefenceStillHolds(unittest.TestCase):
    """The frame the status carries refuses a region on a no-index file before
    the query is ever made — so the reader's own refusal, `RangeNeedsIndex`,
    is no longer reached on the ordinary path. It stays, and it stays TESTED:
    a frame that mistakenly reports the region open (a bug in the frame, a
    status computed for another file) must still end in a named refusal rather
    than in a report carrying «0 variants».
    """

    def test_a_raise_from_the_reader_is_still_a_named_refusal(self):
        from unittest import mock
        from scholion import gene_region, genes
        loc = {"gene": "BRCA1", "chrom": "19", "start": 44_900_000, "end": 44_920_000,
               "strand": 1, "cds": []}
        status = {"ready": True, "paths": [{"path": "region", "open": True}]}

        def raise_needs_index(*_a, **_k):
            raise genome.RangeNeedsIndex("no index")

        with mock.patch.object(genes, "resolve", lambda gene, allow_network=True: dict(loc)), \
             mock.patch.object(genome, "available", lambda: status), \
             mock.patch.object(genome, "vcf_path", lambda: "/nowhere/me.vcf.gz"), \
             mock.patch.object(genome, "_query_region_range", raise_needs_index):
            out = gene_region.report("BRCA1")
        self.assertEqual("needs_index", out.get("status"), out)
        self.assertNotIn("variants", out, "a refusal carried a variant list — the empty list "
                                          "would print as «no variants in this gene»")
        self.assertTrue(out.get("message"))


if __name__ == "__main__":
    unittest.main()
