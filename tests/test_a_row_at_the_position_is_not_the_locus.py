"""A coordinate is not an identity: the row must be about the locus being asked.

Found from outside. A geneticist ran the package blind over three clinical VCFs
and, checking the output by hand, saw that the alleles at `F5 rs6025` in the
files did not match the alleles the catalogue is written with — in all three. He
withheld the Factor V Leiden conclusion himself. The product would not have: the
reader took, in its own words, «the first variant row at the position» and built
the genotype out of THAT row's REF and ALT.

An insertion, a neighbouring substitution or a multiallelic row can stand on the
same base. The genotype printed from one of those belongs to somebody else's
variant, arrives under this locus's name, and is labelled `called` — the exact
shape this project treats as the worst kind of defect: a wrong value wearing a
confidence label.

So the row is now chosen, not taken. Four outcomes, and the middle two are new:
the row is ours; the row is a reference span, which is an answer; another variant
stands here, which is a refusal with a reason; the reference base is not even
ours, which is a statement about the FILE — another build, another
normalisation — and never about the person.
"""
from __future__ import annotations

import os
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import genome

RSID = "rs6025"          # F5, Leiden. The catalogue writes it C>T.
APOE = "rs429358"        # T>C, used where a second locus is needed.


def row(ref, alt, gt="0/1", chrom="1", pos="169549811", fmt="GT", extra=None):
    """One VCF data line in the shape `_query_region` returns."""
    return [chrom, pos, RSID, ref, alt, "50", "PASS", ".", fmt, extra or gt]


class _Reader(unittest.TestCase):
    """Every test hands the reader its rows and nothing else."""

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in
                     ("SCHOLION_GENOME_VCF", "SCHOLION_GENOME_SAMPLE")}
        self._saved = (genome._query_region, genome.vcf_path,
                       genome._index_usable, genome.file_unreadable,
                       genome.sample_index, genome.assembly_of)
        genome.vcf_path = lambda: "/nowhere/x.vcf.gz"
        genome._index_usable = lambda vp: True
        genome.file_unreadable = lambda vp: False
        genome.sample_index = lambda vcf: 0
        genome.assembly_of = lambda vcf: "GRCh38"

    def tearDown(self):
        (genome._query_region, genome.vcf_path, genome._index_usable,
         genome.file_unreadable, genome.sample_index,
         genome.assembly_of) = self._saved
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def read(self, rows, rsid=RSID):
        genome._query_region = lambda vcf, chrom, pos: rows
        return genome._gt_at(dict(genome.locus(rsid), rsid=rsid))


class TestTheRowThatIsOursIsStillRead(_Reader):

    def test_the_plain_case_is_untouched(self):
        got = self.read([row("C", "T")])
        self.assertEqual(got["confidence"], "called")
        self.assertEqual(got["genotype"], "CT")

    def test_a_shared_suffix_is_the_same_variant_written_longer(self):
        """`CA→TA` is C→T with a letter carried along. Read literally it prints
        `CATA`, which is not a genotype anybody can act on."""
        got = self.read([row("CA", "TA")])
        self.assertEqual(got["confidence"], "called")
        self.assertEqual(got["genotype"], "CT")

    def test_the_right_row_is_chosen_and_not_the_first_one(self):
        """The whole defect, stated as an ordering. If selection were still by
        position alone, the insertion would answer for Factor V Leiden."""
        got = self.read([row("C", "CTT"), row("C", "T")])
        self.assertEqual(got["confidence"], "called")
        self.assertEqual(got["genotype"], "CT")

    def test_a_multiallelic_row_answers_and_says_what_it_is(self):
        got = self.read([row("C", "T,G", gt="1/2")])
        self.assertEqual(got["confidence"], "called")
        self.assertEqual(got["genotype"], "TG")
        self.assertTrue(got["multiallelic"],
                        "one of these alleles is not ours and the reader must say so")


class TestAnotherVariantOnTheSameBase(_Reader):

    def test_it_is_not_read_as_this_locus(self):
        got = self.read([row("C", "CTT")])
        self.assertIsNone(got["genotype"])
        self.assertEqual(got["confidence"], "other_variant_at_position")

    def test_the_answer_carries_what_was_expected_and_what_was_found(self):
        got = self.read([row("C", "CTT")])
        self.assertEqual(got["expected"], "C>T")
        self.assertIn("C>CTT", got["found"])
        self.assertTrue(got["note"].strip())

    def test_the_refusal_has_a_sentence_of_its_own(self):
        """A confidence with no head prints its own key at the reader."""
        from scholion.i18n import t as _t
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                head = _t("genome.refused_head.other_variant_at_position")
            finally:
                os.environ.pop("SCHOLION_LANG", None)
            self.assertNotIn("⟦", head)


class TestAReferenceBaseThatIsNotOurs(_Reader):

    def test_nothing_is_read_across_it(self):
        got = self.read([row("G", "A")])
        self.assertIsNone(got["genotype"])
        self.assertEqual(got["confidence"], "reference_mismatch")

    def test_it_is_reported_as_a_property_of_the_file(self):
        got = self.read([row("G", "A")])
        self.assertEqual(got["expected_ref"], "C")
        self.assertEqual(got["found_ref"], ["G"])

    def test_the_refusal_has_a_sentence_of_its_own(self):
        from scholion.i18n import t as _t
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                head = _t("genome.refused_head.reference_mismatch")
            finally:
                os.environ.pop("SCHOLION_LANG", None)
            self.assertNotIn("⟦", head)


class TestAReferenceSpanIsAnAnswer(_Reader):

    def test_a_gvcf_block_at_our_base_says_reference(self):
        got = self.read([row("C", "<NON_REF>", gt="0/0")])
        self.assertEqual(got["confidence"], "confirmed_ref")
        self.assertEqual(got["genotype"], "CC")

    def test_a_forced_call_at_our_locus_is_read_normally(self):
        """A panel that reports every site it interrogated writes our own alleles
        with a homozygous-reference genotype. That is a call, not a span."""
        got = self.read([row("C", "T", gt="0/0")])
        self.assertEqual(got["confidence"], "called")
        self.assertEqual(got["genotype"], "CC")


class TestAReferenceSpanIsOnlyAnAnswerWhenItsGenotypeSaysSo(_Reader):
    """R2 of the 0.4.11 audit. GATK writes a `<NON_REF>` block over a stretch it
    could NOT read as well — genotype `./.`, depth 0 — and the block branch
    looked at the depth and never at the genotype. An unread stretch printed
    `confirmed_ref`, the strongest label the layer has."""

    def test_an_unread_block_is_a_no_call(self):
        got = self.read([row("C", "<NON_REF>", fmt="GT:DP", extra="./.:0")])
        self.assertIsNone(got["genotype"])
        self.assertEqual(got["confidence"], "no_call_in_vcf")

    def test_a_block_calling_its_symbolic_allele_is_not_a_reference(self):
        got = self.read([row("C", "<NON_REF>", gt="0/1")])
        self.assertIsNone(got["genotype"])
        self.assertEqual(got["confidence"], "other_variant_at_position")

    def test_a_read_block_still_confirms(self):
        got = self.read([row("C", "<NON_REF>", fmt="GT:DP", extra="0/0:31")])
        self.assertEqual((got["confidence"], got["genotype"], got["depth"]),
                         ("confirmed_ref", "CC", 31))


class TestASpanningDeletionIsNotAReferenceBlock(_Reader):
    """R3. `*` says that on one chromosome this base lies inside a deletion that
    began upstream. After `bcftools norm -m-` splits `C→T,*` into two rows and
    the `C→T` row is filtered away, `C→*` is what remains — and it was read as a
    reference block: a person with a deletion across the locus printed `CC`."""

    def test_it_is_a_refusal_with_the_allele_named(self):
        got = self.read([row("C", "*")])
        self.assertIsNone(got["genotype"])
        self.assertEqual(got["confidence"], "other_variant_at_position")
        self.assertIn("C>*", got["found"])

    def test_it_is_not_a_genotype_either(self):
        """`C→T,*` with `1/2`: our allele on one chromosome, a deletion across
        the base on the other. `T*` is not a genotype anybody can act on."""
        got = self.read([row("C", "T,*", gt="1/2")])
        self.assertIsNone(got["genotype"])
        self.assertEqual(got["confidence"], "alleles_not_comparable")

    def test_our_allele_beside_an_unused_deletion_is_still_read(self):
        got = self.read([row("C", "T,*", gt="0/1")])
        self.assertEqual((got["confidence"], got["genotype"]), ("called", "CT"))
        self.assertTrue(got["multiallelic"])


class TestAnotherVariantOnOurBaseIsNotAnotherBuild(_Reader):
    """R4. The build test compared the whole REF, so a deletion `CT→C` or a
    two-base change `CG→TA` standing on our own base answered «the file is in
    another build» — a statement about the FILE, made from a row that merely
    carried a different variant. The build decides one thing: the base on the
    coordinate, which is the first letter of REF."""

    def test_a_deletion_starting_on_our_base_is_another_variant(self):
        got = self.read([row("CT", "C")])
        self.assertEqual(got["confidence"], "other_variant_at_position")
        self.assertIn("CT>C", got["found"])

    def test_a_multi_base_change_on_our_base_is_another_variant(self):
        got = self.read([row("CG", "TA")])
        self.assertEqual(got["confidence"], "other_variant_at_position")

    def test_a_different_first_base_is_still_the_file(self):
        got = self.read([row("GT", "G")])
        self.assertEqual(got["confidence"], "reference_mismatch")


class TestTheGenotypeIsWrittenTheWayTheRowWasChosen(_Reader):
    """R5. The row was chosen by trimming each alternative against the
    reference on its own; the genotype was then rendered by trimming only the
    suffix ALL alleles share. On `CA→TA,CAG` the two disagree, and the
    heterozygote printed as `CATA` — labelled `called`."""

    def test_our_allele_in_a_multiallelic_row_prints_as_ours(self):
        got = self.read([row("CA", "TA,CAG")])
        self.assertEqual((got["confidence"], got["genotype"]), ("called", "CT"))
        self.assertTrue(got["multiallelic"])

    def test_an_allele_of_another_length_beside_ours_is_refused_by_name(self):
        got = self.read([row("CA", "TA,CAG", gt="1/2")])
        self.assertIsNone(got["genotype"])
        self.assertEqual(got["confidence"], "alleles_not_comparable")
        self.assertTrue(got["note"].strip())

    def test_the_refusal_has_a_sentence_of_its_own(self):
        from scholion.i18n import t as _t
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                self.assertNotIn("⟦", _t("genome.refused_head.alleles_not_comparable"))
                self.assertNotIn("⟦", _t("genome.alleles_not_comparable",
                                              ref="CA", alt="TA,CAG", value="1/2"))
            finally:
                os.environ.pop("SCHOLION_LANG", None)


class TestALocusWithNoAllelesToVerifyAgainst(_Reader):

    def test_it_is_read_and_marked_unverified(self):
        """An rsID resolved over the network may arrive without alleles. Refusing
        would lose the answer; reading it silently would claim a check that never
        happened."""
        genome._query_region = lambda vcf, chrom, pos: [row("C", "T")]
        loc = dict(genome.locus(RSID), rsid=RSID)
        loc.pop("ref", None)
        loc.pop("alt", None)
        got = genome._gt_at(loc)
        self.assertEqual(got["confidence"], "called")
        self.assertTrue(got["unverified_locus"])


if __name__ == "__main__":
    unittest.main()
