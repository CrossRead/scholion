"""How the file is punctuated and how it is wrapped are properties of the file.

Two defects from the PGP corpus run, both in a handful of lines, both of the
same shape: something was decided by a label instead of by the bytes.

  · the delimiter was chosen by vendor name, so a genuine 23andMe export that
    someone had opened in a spreadsheet and re-saved parsed to zero rows — and
    the product then told the user «this position is not on the 23andMe array
    at all». That was the single confident wrong answer in the whole run: a
    parse failure served as a fact about the instrument.
  · the search looked only at `*.txt`, `*.csv`, `*.tsv`, so four arrays out of
    seven were never offered to the detector that knows how to unwrap them.

The third test here is the rule that makes the first defect impossible to
repeat in a new disguise: vendor recognised, zero rows read → refuse, never an
empty index.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import array_genome as arr

FIX = Path(__file__).resolve().parent / "fixtures" / "arrays"


class ArrayCase(unittest.TestCase):

    def use(self, name):
        os.environ["SCHOLION_ARRAY_FILE"] = str(FIX / name)
        arr._CACHE.clear()

    def tearDown(self):
        os.environ.pop("SCHOLION_ARRAY_FILE", None)
        arr._CACHE.clear()


class TestTheDelimiterComesFromTheFile(ArrayCase):

    def test_a_23andme_export_re_saved_as_csv_still_reads(self):
        self.use("23andme_spreadsheet.csv")
        idx = arr.index()
        self.assertTrue(idx["ok"])
        self.assertEqual(idx["vendor"], "23andMe", "the vendor is still 23andMe — a "
                                                   "spreadsheet changes the punctuation, not the author")
        self.assertGreater(idx["markers"], 0, "zero rows here is the defect this test exists for")
        self.assertEqual(arr.status("rs4149056")["status"], "called")

    def test_the_wrong_answer_it_used_to_give(self):
        """The regression in its own words: absence must not be manufactured."""
        self.use("23andme_spreadsheet.csv")
        st = arr.status("rs4149056")
        self.assertNotEqual(st["status"], "not_on_chip",
                            "a locus the chip DOES carry was reported as absent because "
                            "the reader could not parse the file")

    def test_a_tab_file_is_still_read_as_tabs(self):
        self.use("23andme.txt")
        self.assertEqual(arr._delimiter(FIX / "23andme.txt"), "\t")
        self.assertTrue(arr.index()["ok"])

    def test_a_quoted_csv_is_read_as_commas(self):
        self.use("myheritage.csv")
        self.assertEqual(arr._delimiter(FIX / "myheritage.csv"), ",")
        self.assertEqual(arr.status("rs4149056")["status"], "called")


class TestWrappedExports(ArrayCase):
    """The wrappers are BUILT here, not committed.

    A `.gz` or a `.zip` in the tree is a blob the build audit cannot read into,
    and its denylist is right to refuse one: the whole point of that gate is that
    nothing opaque travels in the package. So the archives are made at test time
    from the plain fixtures next door — same bytes, no blob in the repository.
    """

    def setUp(self):
        import bz2
        import gzip
        import tempfile
        import zipfile
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        with gzip.open(self.dir / "23andme.txt.gz", "wb") as fh:
            fh.write((FIX / "23andme.txt").read_bytes())
        with bz2.open(self.dir / "ancestrydna.txt.bz2", "wb") as fh:
            fh.write((FIX / "ancestrydna.txt").read_bytes())
        with zipfile.ZipFile(self.dir / "myheritage.zip", "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("README.txt", "Thank you for downloading your DNA data.\n")
            z.writestr("MyHeritage_raw_dna_data.csv", (FIX / "myheritage.csv").read_bytes())

    def tearDown(self):
        super().tearDown()
        self.tmp.cleanup()

    def wrapped(self, name):
        os.environ["SCHOLION_ARRAY_FILE"] = str(self.dir / name)
        arr._CACHE.clear()

    def test_gzip(self):
        self.wrapped("23andme.txt.gz")
        self.assertTrue(arr.index()["ok"])
        self.assertEqual(arr.status("rs4149056")["status"], "called")

    def test_bzip2(self):
        self.wrapped("ancestrydna.txt.bz2")
        idx = arr.index()
        self.assertTrue(idx["ok"])
        self.assertEqual(idx["vendor"], "AncestryDNA")

    def test_a_provider_zip_with_a_readme_inside(self):
        """What a provider actually hands people: an archive with junk in it."""
        self.wrapped("myheritage.zip")
        idx = arr.index()
        self.assertTrue(idx["ok"], "the README must not be mistaken for the data")
        self.assertEqual(arr.status("rs4149056")["status"], "called")

    def test_the_search_offers_wrapped_files_to_the_detector(self):
        for name in ("23andme.txt.gz", "ancestrydna.txt.bz2", "myheritage.zip"):
            with self.subTest(name=name):
                self.assertTrue(any(name.endswith(p.lstrip("*"))
                                    for p in arr._SEARCH_PATTERNS),
                                f"{name} is not covered by any search pattern, so the "
                                f"detector never sees it")


class TestZeroRowsIsARefusal(ArrayCase):

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        p = Path(self.tmp.name) / "broken.txt"
        # A recognisable 23andMe banner and nothing a reader can use.
        p.write_text("# This data file generated by 23andMe\n"
                     "# rsid\tchromosome\tposition\tgenotype\n", encoding="utf-8")
        self.path = p

    def tearDown(self):
        super().tearDown()
        self.tmp.cleanup()

    def test_the_index_refuses_instead_of_returning_empty(self):
        os.environ["SCHOLION_ARRAY_FILE"] = str(self.path)
        arr._CACHE.clear()
        idx = arr.index()
        self.assertFalse(idx["ok"])
        self.assertEqual(idx["reason"], "array_unreadable")
        self.assertEqual(idx.get("vendor"), "23andMe",
                         "the vendor WAS recognised — this is not «no array»")

    def test_a_locus_says_the_file_was_not_read_not_that_the_chip_lacks_it(self):
        os.environ["SCHOLION_ARRAY_FILE"] = str(self.path)
        arr._CACHE.clear()
        st = arr.status("rs4149056")
        self.assertEqual(st["status"], "array_unreadable")
        self.assertNotEqual(st["status"], "not_on_chip")
        self.assertIn("NOT a statement about the chip", st["note"])

    def test_genome_status_shows_the_third_state(self):
        os.environ["SCHOLION_ARRAY_FILE"] = str(self.path)
        arr._CACHE.clear()
        from scholion import genome
        av = genome.available()
        self.assertTrue(av.get("array_unreadable"),
                        "`array: null` on its own reads as «no array here»")


if __name__ == "__main__":
    unittest.main()
