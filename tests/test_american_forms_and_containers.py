"""Tasks 84 and 89: the draw date on an American form, and data in a container.

Both tasks are the same shape — a file that is perfectly readable and was
answered as if it were not — and both are measured against the reference corpus
rather than against imagination.

**Task 84.** Sixteen real American laboratory forms out of sixteen failed on one
gate: «no draw date could be found on the form». Three things were missing and
all three are here. A LabCorp report prints its dates as a TABLE, the heading on
one line and the values on the next, so a reader that wants the label and the
date on the same line finds neither. A two-digit year is ordinary. And a page
that carries `12/15/2008` has SAID which order it prints in — there is no
fifteenth month — so `12/10/2008` beside it is no longer a coin toss. That last
one is not the guess the refusal rule exists to prevent: the evidence is on the
page, in the same table, printed by the same instrument. What is still refused
is a page whose dates contradict each other.

**Task 89.** A VCF compressed with bzip2, a VCF whose provider URL-encoded the
brackets in its own file name, and a VCF inside a provider's zip are all
ordinary VCFs. They cannot be seeked into, but the catalogue is fifty-four loci,
so one cached pass over the file answers all of them.
"""
from __future__ import annotations

import bz2
import gzip
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholion import genome, ingest_labs, tabular_genome  # noqa: E402


_LABCORP = """LAB RESULTS
Last Name Lab ID Specimen Number Time Collected Date Entered Time Reported
CLEMENT 12/10/2008 12:00 AM 12/10/2008 12/15/2008 7:06 AM
Date of Birth Age Sex Fasting Physician Name Physician ID
11/01/1955 53 M
"""

_DIRECTLABS = """Date Collected Time Collected Date Entered Date Reported
07/30/15 10:49 07/30/15 08/04/15
"""


class TestTheDrawDateOnAnAmericanForm(unittest.TestCase):

    def test_a_heading_line_with_the_values_underneath_is_read(self):
        date, ambiguity = ingest_labs.english_date(_DIRECTLABS)
        self.assertIsNone(ambiguity)
        self.assertEqual("2015-07-30", date)   # two-digit year, and 30 > 12

    def test_one_decidable_date_settles_the_others_on_the_same_page(self):
        # 12/15/2008 can only be M/D/Y. That is the page speaking, not us.
        self.assertEqual("mdy", ingest_labs.page_convention(_LABCORP))
        date, ambiguity = ingest_labs.english_date(_LABCORP)
        self.assertIsNone(ambiguity)
        self.assertEqual("2008-12-10", date)

    def test_a_page_that_contradicts_itself_is_still_refused(self):
        both = "Collected 03/04/2015 Reported 25/04/2015 Entered 04/13/2015"
        self.assertIsNone(ingest_labs.page_convention(both))
        date, ambiguity = ingest_labs.english_date("Collected 03/04/2015\n" + both)
        self.assertIsNone(date)
        self.assertIsNotNone(ambiguity)

    def test_a_lone_ambiguous_date_is_still_refused(self):
        date, ambiguity = ingest_labs.english_date("Collected: 07/12/2015")
        self.assertIsNone(date)
        self.assertEqual(["2015-07-12", "2015-12-07"], ambiguity["both"])

    def test_the_order_date_is_read_and_named_as_not_the_draw(self):
        date, ambiguity, kind = ingest_labs.english_date_near("Ordered Date: 08/20/2012")
        self.assertEqual("2012-08-20", date)
        self.assertEqual("ordered", kind)
        # And it is NOT returned by the draw-date reader, which is the whole point.
        self.assertEqual((None, None), ingest_labs.english_date("Ordered Date: 08/20/2012"))

    def test_a_spelled_month_in_the_file_name_is_read_and_a_slashed_one_is_not(self):
        self.assertEqual("2017-04-12",
                         ingest_labs.date_from_filename("LEF_Blood_Tests_April_12__2017.pdf"))
        self.assertEqual("2015-01-15",
                         ingest_labs.date_from_filename("Blood_Chemistry_Labs_1-15-2015.pdf"))
        # 4 and 11 are both possible months: nothing in a file name says which.
        self.assertIsNone(ingest_labs.date_from_filename("Labs_4-11-2017.pdf"))


_VCF = ("##fileformat=VCFv4.1\n"
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tME\n"
        "19\t44908684\trs429358\tT\tC\t50\tPASS\t.\tGT\t0/1\n"
        "1\t11796321\trs1801133\tG\tA\t50\tPASS\t.\tGT\t1/1\n").encode()

_TABLE = ("##FileFormat=Genos\n"
          "##Columns=CHROM\tBEGIN\tEND\tID\tGENOTYPE\n"
          "chr19\t44908683\t44908684\trs429358\tT/C\n"
          "chr1\t11796320\t11796321\trs1801133\tA/A\n").encode()


class TestDataInAContainer(unittest.TestCase):
    """Task 89: readable is readable, whatever it arrived wrapped in."""

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("SCHOLION_GENOME_DIR", "SCHOLION_GENOME_VCF",
                               "SCHOLION_ARRAY_FILE", "SCHOLION_CACHE_DIR")}
        for k in self._env:
            os.environ.pop(k, None)
        self.dir = Path(tempfile.mkdtemp())
        os.environ["SCHOLION_GENOME_DIR"] = str(self.dir)
        os.environ["SCHOLION_CACHE_DIR"] = str(self.dir / "cache")

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_a_vcf_in_bzip2_answers(self):
        (self.dir / "export.bz2").write_bytes(bz2.compress(_VCF))
        self.assertEqual("called", tabular_genome.status("rs429358")["status"])
        self.assertEqual("TC", tabular_genome.status("rs429358")["genotype"])

    def test_a_vcf_whose_name_was_mangled_by_a_provider_answers(self):
        (self.dir / "calls.vcf_5B1_5D.gz").write_bytes(gzip.compress(_VCF))
        self.assertEqual("AA", tabular_genome.status("rs1801133")["genotype"])

    def test_a_vcf_inside_a_providers_zip_answers(self):
        path = self.dir / "provider.zip"
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("README.txt", "thank you for choosing us")
            zf.writestr("calls.vcf", _VCF)
        self.assertEqual("TC", tabular_genome.status("rs429358")["genotype"])

    def test_a_genotype_table_answers_and_carries_the_chip_ceiling(self):
        (self.dir / "sample_genotype.tsv").write_bytes(_TABLE)
        st = tabular_genome.status("rs429358")
        self.assertEqual("called", st["status"])
        self.assertEqual("TC", st["genotype"])
        # A locus with no row was never typed — it is NOT the reference.
        absent = tabular_genome.status("rs4149056")
        self.assertEqual("not_in_file", absent["status"])
        self.assertEqual("genotype_table", tabular_genome.summary()["class"])

    def test_the_status_says_what_it_is_rather_than_calling_it_a_genome(self):
        (self.dir / "export.bz2").write_bytes(bz2.compress(_VCF))
        av = genome.available()
        self.assertTrue(av["ready"])
        self.assertEqual("tabular", av["input_class"])
        self.assertIsNone(av["vcf"])
        from scholion import format as fmt
        out = fmt.genome_status_report(av)
        self.assertNotIn("File: None", out)
        self.assertNotIn("Genome connected", out)
        self.assertNotIn("⟦", out)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
