"""Reading a consumer genotyping array, with a three-valued answer per locus.

Backlog task 1. A chip and a sequenced genome fail in opposite directions, and
collapsing the difference is the most dangerous thing this layer can do.

In a variants-only VCF a position with no row WAS read and matched the reference
— assuming reference there is defensible, and the project labels it
`assumed_ref`. On an array a position with no row was NEVER INTERROGATED: the
chip carries a few hundred thousand of three billion positions. Carrying the VCF
assumption across turns «this instrument cannot see that locus» into «you do not
have that variant», which is reassurance about something nobody looked at.

So the three answers are held apart here, in both directions: what the chip
called, what it tried and failed to call, and what it does not carry at all.
"""
from __future__ import annotations

import os
import pathlib
import unittest

import support  # noqa: F401
from scholion import array_genome, genome

FIX = pathlib.Path(__file__).resolve().parent / "fixtures" / "arrays"
FORMATS = {"23andme.txt": "23andMe", "ancestrydna.txt": "AncestryDNA",
           "myheritage.csv": "MyHeritage"}


class _Array(unittest.TestCase):
    def _use(self, name):
        os.environ["SCHOLION_ARRAY_FILE"] = str(FIX / name)
        os.environ["SCHOLION_GENOME_VCF"] = str(FIX / "no-such-file.vcf.gz")
        array_genome._CACHE.clear()

    def tearDown(self):
        os.environ.pop("SCHOLION_ARRAY_FILE", None)
        os.environ.pop("SCHOLION_GENOME_VCF", None)
        array_genome._CACHE.clear()


class TestEveryVendorFormatIsRead(_Array):
    def test_the_vendor_is_recognised_from_the_header_not_the_name(self):
        for name, vendor in FORMATS.items():
            with self.subTest(file=name):
                self._use(name)
                idx = array_genome.index()
                self.assertTrue(idx["ok"], idx)
                self.assertEqual(idx["vendor"], vendor)
                self.assertGreater(idx["markers"], 0)

    def test_a_genotype_reads_the_same_whichever_vendor_wrote_it(self):
        """AncestryDNA splits the two alleles into separate columns; MyHeritage
        quotes every cell. The answer must not depend on that."""
        for name in FORMATS:
            with self.subTest(file=name):
                self._use(name)
                self.assertEqual(array_genome.status("rs4149056")["genotype"], "TC")


class TestTheThreeAnswersStayApart(_Array):
    def test_a_called_position(self):
        self._use("23andme.txt")
        st = array_genome.status("rs4149056")
        self.assertEqual(st["status"], "called")
        self.assertEqual(st["genotype"], "TC")

    def test_a_position_the_chip_carries_but_could_not_call(self):
        self._use("23andme.txt")
        st = array_genome.status("rs1799853")          # printed as «--»
        self.assertEqual(st["status"], "no_call")
        self.assertIsNone(st.get("genotype"))

    def test_a_position_the_chip_does_not_carry(self):
        self._use("23andme.txt")
        st = array_genome.status("rs1801131")
        self.assertEqual(st["status"], "not_on_chip")

    def test_the_two_kinds_of_absence_are_not_the_same_answer(self):
        """rs1799853 is ON the 23andMe fixture (failed call) and ABSENT from the
        MyHeritage one. Same rsid, two different truths about the instrument."""
        self._use("23andme.txt")
        a = array_genome.status("rs1799853")["status"]
        self._use("myheritage.csv")
        b = array_genome.status("rs1799853")["status"]
        self.assertEqual((a, b), ("no_call", "not_on_chip"))


class TestAnArrayIsNeverTreatedAsASequencedGenome(_Array):
    def test_a_missing_position_never_becomes_a_reference_call(self):
        """The single most dangerous sentence this layer could produce."""
        self._use("23andme.txt")
        r = genome.lookup(rsid="rs1801131")
        res = r.get("result") or {}
        self.assertEqual(res.get("confidence"), "not_on_chip")
        self.assertNotIn(res.get("confidence"), ("assumed_ref", "confirmed_ref"))
        self.assertIsNone(res.get("genotype"))

    def test_the_input_class_says_what_answered(self):
        self._use("23andme.txt")
        st = genome.available()
        self.assertEqual(st["input_class"], "array")
        self.assertFalse(st["vcf_present"])
        self.assertEqual((st["array"] or {}).get("vendor"), "23andMe")

    def test_a_called_locus_carries_its_source(self):
        self._use("23andme.txt")
        res = genome.lookup(rsid="rs4149056")["result"]
        self.assertEqual(res["source"], "array")
        self.assertEqual(res["confidence"], "called_array")


class TestTheCeilingIsStated(_Array):
    def test_monogenic_questions_are_refused_for_an_array(self):
        from scholion import limits
        self._use("23andme.txt")
        rows = {r["architecture"]: r for r in limits.scope()["rows"]}
        self.assertEqual(rows["monogenic"]["state"], "not_supported")

    def test_the_input_is_not_described_as_a_genome(self):
        from scholion import limits
        self._use("23andme.txt")
        sc = limits.scope()
        self.assertEqual(sc["input"], "array")
        self.assertNotEqual(sc["input"], "wgs")


if __name__ == "__main__":
    unittest.main()


class TestTheFormatFactsFromTheRealExport(_Array):
    """Established on a real 23andMe v5 export (631 455 rows) by the run of task
    78 — recorded so nobody has to rediscover them."""

    def test_crlf_does_not_end_up_glued_to_the_genotype(self):
        """The real files end lines with CRLF. «TC\\r» matches nothing in the
        catalogue and looks exactly like a failed call."""
        self._use("23andme_crlf.txt")
        self.assertEqual(array_genome.status("rs4149056")["genotype"], "TC")

    def test_internal_vendor_ids_are_skipped(self):
        """`i3002401` is the vendor's own probe, not a dbSNP record: it cannot be
        matched to the catalogue and must not be half-matched."""
        self._use("23andme_crlf.txt")
        self.assertNotIn("i3002401", array_genome.index()["genotypes"])

    def test_the_build_is_read_from_the_header_prose(self):
        """The export says «reference human assembly build 37» in words. Reading
        it beats the folklore that arrays are always GRCh37."""
        self._use("23andme_crlf.txt")
        self.assertEqual(array_genome.declared_assembly(), "GRCh37")


class TestStrandAmbiguousLociAreNamed(_Array):
    """Six catalogue loci have alleles that are their own complement. If a
    provider reported the minus strand the call would still land inside
    {ref, alt} — indistinguishable from a correct one — and DPYD and TPMT, the
    chemotherapy dosing genes, are among them."""

    EXPECTED = {"rs67376798", "rs75017182", "rs1800462",
                "rs1799945", "rs17580", "rs12934922"}

    def test_they_are_computed_from_the_catalogue_not_hardcoded(self):
        self._use("23andme.txt")
        self.assertEqual(set(array_genome.strand_ambiguous_loci()), self.EXPECTED)

    def test_such_a_locus_is_not_handed_over_beside_the_rest(self):
        self._use("23andme_crlf.txt")
        st = array_genome.status("rs67376798")
        self.assertEqual(st["status"], "called_strand_ambiguous")
        self.assertNotEqual(st["status"], "called")

    def test_the_coverage_report_names_them(self):
        self._use("23andme_crlf.txt")
        cov = array_genome.catalogue_coverage()
        self.assertIn("rs67376798", [a["rsid"] for a in cov["strand_ambiguous"]])


class TestTheThreeDangerousPathsAreClosed(_Array):
    """The acceptance criterion of the task: ClinVar, ACMG SF and PGS on an array
    answer with a refusal AND A REASON, never with a value."""

    def test_all_three_refuse(self):
        from scholion.engine import genomics
        self._use("23andme.txt")
        for name, fn in (("clinvar", genomics.clinvar_findings),
                         ("acmg", genomics.acmg_findings),
                         ("prs", genomics.prs_findings)):
            with self.subTest(path=name):
                r = fn()
                self.assertEqual(r.get("status"), "input_is_an_array")
                self.assertFalse(r.get("available"))
                self.assertTrue(r.get("message"), "refused without saying why")

    def test_the_refusal_says_what_the_array_can_answer_instead(self):
        from scholion.engine import genomics
        self._use("23andme.txt")
        self.assertTrue(genomics.clinvar_findings().get("open_instead"))

    def test_the_locus_catalogue_stays_open(self):
        """The whole point: an array is not useless, it is bounded."""
        self._use("23andme.txt")
        self.assertEqual(genome.lookup(rsid="rs4149056")["result"]["genotype"], "TC")


class TestTheThreeNumbers(_Array):
    def test_the_report_gives_called_no_call_and_absent(self):
        self._use("23andme.txt")
        cov = array_genome.catalogue_coverage()
        self.assertEqual(cov["called"] + cov["no_call"] + cov["absent"],
                         cov["catalogue_total"])
        self.assertGreater(cov["catalogue_total"], 0)
