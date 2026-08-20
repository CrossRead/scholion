"""One file, one person — and everything else named rather than guessed at.

Tasks 63 and 64. Both are the same defect wearing two coats: the code found
something plausible, answered from it, and said nothing about the choice it had
made. Three shapes of it were reproduced on the real engine and all three were
silent.

* A folder holding `chr1.vcf.gz` … `chr22.vcf.gz` answered APOE — which is on
  chromosome 19 — from `chr1.vcf.gz`, as «TT, reference», while `chr19.vcf.gz`
  lay in the same folder and was never opened.
* A folder holding two people answered about whichever name sorts first.
* A trio file answered from column ten, which belongs to whoever the caller
  happened to list first — a child, a mother, a stranger.

And the one that was worse, because it was not a refusal but an answer: a
`.vcf.gz` compressed with ordinary gzip instead of bgzip was declared «Genome
connected» and reported reference at every locus. The diagnosis existed —
`unusable_nearby()` names that exact case and prints the command that fixes it —
and it was consulted only when no file had been found or no reader was
installed. A reader is essentially always installed, so it was never consulted
when it mattered. The system held both facts and compared neither with the other.

No external binary is used here. A BGZF block is written in fifteen lines below,
because a test that skips when `bgzip` is missing is a test that reports health
it did not measure.
"""
from __future__ import annotations

import gzip
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import support  # noqa: F401
from scholion import format as fmt, genome


def bgzf(data: bytes) -> bytes:
    """A single BGZF block: a gzip member carrying the BC extra field.

    Written by hand rather than shelled out to `bgzip`, so that these assertions
    hold on a machine that has no htslib installed — which is most machines a new
    user brings, and exactly the ones the two tasks are about.
    """
    comp = zlib.compressobj(6, zlib.DEFLATED, -15)
    body = comp.compress(data) + comp.flush()
    extra = b"BC" + struct.pack("<H", 2) + struct.pack("<H", len(body) + 25)
    head = b"\x1f\x8b\x08\x04" + b"\0" * 6 + struct.pack("<H", len(extra)) + extra
    return head + body + struct.pack("<II", zlib.crc32(data) & 0xFFFFFFFF, len(data))


_ROW = "19\t44908684\trs429358\tT\tC\t50\tPASS\t.\tGT\t{gts}\n"


def _vcf_text(samples, gts) -> bytes:
    return ("##fileformat=VCFv4.2\n##source=SYNTHETIC test fixture\n"
            + "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t"
            + "\t".join(samples) + "\n"
            + _ROW.format(gts="\t".join(gts))).encode()


class _Folder(unittest.TestCase):
    """Each test gets its own genome folder and no environment left behind."""

    KEYS = ("SCHOLION_GENOME_DIR", "SCHOLION_GENOME_VCF", "SCHOLION_GENOME_SAMPLE",
            "SCHOLION_ARRAY_FILE", "SCHOLION_GENOME_ASSEMBLY")

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

    def write(self, name, samples=("ME",), gts=("0/1",), bgzip=True, index=True):
        p = self.dir / name
        raw = _vcf_text(samples, gts)
        p.write_bytes(bgzf(raw) if bgzip else gzip.compress(raw))
        if index:
            # Two bytes of gzip magic is all `_tbi_usable` reads, and all a
            # truncated real index would have. The queries here are stubbed.
            Path(str(p) + ".tbi").write_bytes(b"\x1f\x8b" + b"\0" * 30)
        return p


class TestSeveralFilesAreNotOneGenome(_Folder):

    def test_a_per_chromosome_set_is_not_answered_from_the_first_part(self):
        self.write("chr1.vcf.gz")
        self.write("chr19.vcf.gz")
        av = genome.available()
        self.assertFalse(av["ready"])
        self.assertEqual(av["reason"], "several_files")
        self.assertEqual(av["vcf_count"], 2)
        self.assertIsNone(av["vcf"], "no file may be nominated while the choice is open")

    def test_both_names_are_printed_so_the_person_can_choose(self):
        self.write("alice.vcf.gz")
        self.write("bob.vcf.gz")
        out = fmt.genome_status_report(genome.available())
        self.assertIn("alice.vcf.gz", out)
        self.assertIn("bob.vcf.gz", out)
        self.assertIn("SCHOLION_GENOME_VCF", out)

    def test_naming_the_file_settles_it(self):
        a = self.write("alice.vcf.gz")
        self.write("bob.vcf.gz")
        os.environ["SCHOLION_GENOME_VCF"] = str(a)
        av = genome.available()
        self.assertIsNone(av["ambiguous"])
        self.assertEqual(av["vcf"], str(a))

    def test_our_own_derived_files_do_not_count_as_a_second_genome(self):
        """`loci_sites.vcf.gz` is called from the same reads and sits beside the
        main file by design. Counting it would make every complete profile
        ambiguous — a refusal triggered by our own pipeline."""
        self.write("genome.vcf.gz")
        self.write("loci_sites.vcf.gz")
        av = genome.available()
        self.assertEqual(av["vcf_count"], 1)
        self.assertIsNone(av["ambiguous"])


class TestSeveralSamplesAreNotOnePerson(_Folder):

    def setUp(self):
        super().setUp()
        self.vcf = self.write("trio.vcf.gz",
                              samples=("CHILD", "MOTHER", "FATHER"),
                              gts=("0/1", "0/0", "0/0"))

    def test_the_samples_are_read_out_of_the_file_and_named(self):
        av = genome.available()
        self.assertEqual(av["samples"], ["CHILD", "MOTHER", "FATHER"])
        self.assertFalse(av["ready"])
        self.assertEqual(av["reason"], "several_samples")
        self.assertIsNone(av["sample"])

    def test_the_column_follows_the_name_and_not_the_order(self):
        """The whole point, stated as a difference between two people.

        Column ten is the child and is heterozygous; the mother is not. If the
        answer were the same for both names, the selection would be decorative.
        """
        seen = {}
        original = genome._query_region
        genome._query_region = lambda vcf, chrom, pos: [
            _ROW.format(gts="0/1\t0/0\t0/0").rstrip("\n").split("\t")]
        try:
            for name in ("CHILD", "MOTHER"):
                os.environ["SCHOLION_GENOME_SAMPLE"] = name
                seen[name] = genome._gt_at(dict(genome.locus("rs429358"), rsid="rs429358"))
        finally:
            genome._query_region = original
        self.assertEqual(seen["CHILD"]["genotype"], "TC")
        self.assertEqual(seen["MOTHER"]["genotype"], "TT")

    def test_nothing_is_read_while_nobody_is_chosen(self):
        got = genome._gt_at(dict(genome.locus("rs429358"), rsid="rs429358"))
        self.assertEqual(got["confidence"], "sample_not_chosen")
        self.assertIsNone(got["genotype"])

    def test_a_name_that_is_not_in_the_file_is_a_typo_and_says_so(self):
        os.environ["SCHOLION_GENOME_SAMPLE"] = "AUNT"
        av = genome.available()
        self.assertEqual(av["reason"], "sample_not_found")
        out = fmt.genome_status_report(av)
        self.assertIn("CHILD", out, "the names the file DOES carry are the useful half")

    def test_one_sample_needs_no_choice(self):
        (self.dir / "trio.vcf.gz").unlink()
        (self.dir / "trio.vcf.gz.tbi").unlink()
        genome.samples_of.cache_clear()
        self.write("me.vcf.gz", samples=("ME",))
        av = genome.available()
        self.assertEqual(av["sample"], "ME")
        self.assertIsNone(av["ambiguous"])


class TestAFileThatCannotBeReadIsNotConnected(_Folder):
    """Task 64, and the one confident wrong answer of the whole corpus run."""

    def test_ordinary_gzip_is_not_declared_connected(self):
        self.write("genome.vcf.gz", bgzip=False)
        av = genome.available()
        self.assertFalse(av["ready"])
        self.assertEqual(av["reason"], "unreadable_file")
        self.assertEqual((av["unusable"] or {}).get("reason"), "gzip_not_bgzip")

    def test_the_diagnosis_is_asked_of_the_file_even_when_a_reader_exists(self):
        """The regression itself. The check was skipped exactly when a reader was
        installed — which is nearly always — so it never ran when it mattered."""
        self.write("genome.vcf.gz", bgzip=False)
        original = genome._have_bcftools
        genome._have_bcftools = lambda: True
        try:
            av = genome.available()
        finally:
            genome._have_bcftools = original
        self.assertFalse(av["ready"])
        self.assertIsNotNone(av["unusable"])

    def test_no_locus_answers_reference_out_of_it(self):
        self.write("genome.vcf.gz", bgzip=False)
        got = genome._gt_at(dict(genome.locus("rs429358"), rsid="rs429358"))
        self.assertIsNone(got, "«reference» out of a file that cannot be opened is the "
                               "worst answer this project can give")

    def test_a_bgzf_file_is_still_fine(self):
        self.write("genome.vcf.gz")
        av = genome.available()
        self.assertIsNone(av["unusable"])


class TestGenomicDataThatIsNotAVcfIsNamed(_Folder):
    """Eleven formats printed one sentence — «the full VCF is not connected» — at
    people whose file was lying in that very folder. Each class needs a different
    next step, so each class is named."""

    CASES = {"genome.bcf": "bcf", "genome.vcf.bgz": "vcf_container",
             "sample.bam": "alignment", "reads_R1.fastq.gz": "reads",
             "provider_export.tar.gz": "archive", "cohort.g.vcf.gz": "gvcf"}

    def test_every_class_is_recognised_by_its_own_name(self):
        for name, kind in self.CASES.items():
            with self.subTest(file=name):
                for f in self.dir.iterdir():
                    f.unlink()
                (self.dir / name).write_bytes(b"\0" * 64)
                found = genome.foreign_inputs()
                self.assertEqual([f["kind"] for f in found], [kind])

    def test_the_report_says_what_to_do_with_each(self):
        for name in self.CASES:
            with self.subTest(file=name):
                for f in self.dir.iterdir():
                    f.unlink()
                (self.dir / name).write_bytes(b"\0" * 64)
                out = fmt.genome_status_report(genome.available())
                self.assertIn(name, out)
                self.assertNotIn("⟦", out, "a class with no sentence written for it")

    def test_a_gvcf_is_not_mistaken_for_the_genome(self):
        """Every gVCF name also ends in `.vcf.gz`. Read as a plain VCF it answers
        «reference» for whole uncovered stretches, silently."""
        (self.dir / "cohort.g.vcf.gz").write_bytes(b"\0" * 64)
        self.assertEqual(genome.vcf_candidates(), [])
        self.assertEqual(genome.available()["reason"], "foreign_input")


class TestTheLocusCommandTellsTheSameStory(_Folder):
    """Task 64's second item: two commands, one folder, two different stories."""

    def _refusal(self):
        return fmt.genome_report(genome.lookup(rsid="rs429358"))

    def test_the_gene_and_the_coordinate_reach_the_line(self):
        out = self._refusal()
        self.assertIn("APOE", out)
        self.assertIn("44908684", out)
        self.assertNotIn("None:None", out, "a missing dictionary lookup leaking into "
                                           "what a person reads")
        self.assertNotIn("(, ", out)

    def test_each_refusal_names_its_own_reason(self):
        seen = set()
        cases = [(lambda: None, "no_file"),
                 (lambda: self.write("genome.vcf.gz", bgzip=False), "unreadable_file"),
                 (lambda: (self.write("a.vcf.gz"), self.write("b.vcf.gz")), "several_files")]
        for make, reason in cases:
            for f in list(self.dir.iterdir()):
                f.unlink()
            genome.samples_of.cache_clear()
            make()
            with self.subTest(reason=reason):
                r = genome.lookup(rsid="rs429358")
                self.assertEqual(r["status"], "no_genome")
                self.assertEqual(r["reason"], reason)
                seen.add(r["message"])
        self.assertEqual(len(seen), 3, "three situations, three sentences — the same "
                                       "sentence for all of them is the defect")

    def test_a_person_holding_their_file_is_not_told_to_go_and_get_one(self):
        self.write("genome.vcf.gz", bgzip=False)
        r = genome.lookup(rsid="rs429358")
        self.assertNotIn("genome/*.vcf.gz", r["message"],
                         "the file IS there; sending them to obtain one is the "
                         "contradiction between the two commands")


class TestAReaderThatIsInstalledIsNotAReaderThatCanRead(_Folder):
    """Found by phase 2 of task 78, and not by any test that existed.

    The reader was chosen by what is INSTALLED. pysam is installed nearly
    everywhere, so a file with no index at all, or with a truncated one, reported
    «Genome connected» and then printed `genotype **?** ()` — a genotype-shaped
    hole. Every reader here seeks by position, so every reader needs an index.
    """

    def test_no_index_is_not_a_connected_genome(self):
        p = self.write("genome.vcf.gz")
        Path(str(p) + ".tbi").unlink()
        av = genome.available()
        self.assertFalse(av["ready"])
        self.assertIsNone(av["engine"])

    def test_a_truncated_index_is_not_an_index(self):
        p = self.write("genome.vcf.gz")
        Path(str(p) + ".tbi").write_bytes(b"")
        self.assertFalse(genome.available()["ready"])

    def test_a_csi_index_counts_where_a_reader_can_use_it(self):
        """`.csi` is what tabix writes for long contigs and what some providers
        ship. It was never looked for at all."""
        p = self.write("genome.vcf.gz")
        Path(str(p) + ".tbi").rename(str(p) + ".csi")
        have = genome._have_bcftools() or genome._have_pysam()
        self.assertEqual(genome._index_usable(p), have,
                         "a csi is readable by bcftools and pysam and not by our own "
                         "tabix reader — and claiming otherwise made every locus «reference»")

    def test_an_empty_answer_is_never_printed_as_a_genotype(self):
        p = self.write("genome.vcf.gz")
        Path(str(p) + ".tbi").unlink()
        out = fmt.genome_report(genome.lookup(rsid="rs429358"))
        self.assertNotIn("genotype", out.lower())
        self.assertIn("rs429358", out)


class TestSilenceIsNotReferenceWhenTheBuildIsUnknown(_Folder):
    """Case 21 of the format matrix, and the last confident wrong answer in it.

    A GRCh37 file with no `##contig` block and no variant past the end of
    chromosome 1 cannot be placed in a build. Asked at a GRCh38 coordinate it
    returns nothing — and «nothing» was read as «reference», so a heterozygous
    APOE ε4 carrier came back a non-carrier. A row that IS found is different:
    finding it is itself evidence that the coordinates line up.
    """

    def _loc(self):
        return dict(genome.locus("rs429358"), rsid="rs429358")

    def _with_rows(self, rows):
        original = genome._query_region
        genome._query_region = lambda vcf, chrom, pos: rows
        try:
            return genome._gt_at(self._loc())
        finally:
            genome._query_region = original

    def setUp(self):
        super().setUp()
        self.write("genome.vcf.gz")            # no contig block: the build cannot be told
        genome.assembly_of.cache_clear()
        genome._chr_prefix.cache_clear()

    def test_the_build_really_is_unestablished_here(self):
        self.assertIsNone(genome.assembly_of(str(genome.vcf_path())))

    def test_no_row_plus_no_build_is_not_a_reference_call(self):
        got = self._with_rows([])
        self.assertEqual(got["confidence"], "no_row_and_build_unknown")
        self.assertIsNone(got["genotype"])

    def test_a_row_that_was_found_is_still_answered(self):
        """The reverse. Refusing everything would be as wrong as the state this
        replaces: a row at the asked position proves the coordinates line up."""
        row = "19\t44908684\trs429358\tT\tC\t50\tPASS\t.\tGT\t0/1".split("\t")
        got = self._with_rows([row])
        self.assertEqual(got["genotype"], "TC")
        self.assertEqual(got["confidence"], "called")

    def test_naming_the_build_settles_it(self):
        os.environ["SCHOLION_GENOME_ASSEMBLY"] = "GRCh38"
        genome.assembly_of.cache_clear()
        try:
            got = self._with_rows([])
            self.assertEqual(got["confidence"], "assumed_ref")
        finally:
            os.environ.pop("SCHOLION_GENOME_ASSEMBLY", None)
            genome.assembly_of.cache_clear()


if __name__ == "__main__":
    unittest.main()
