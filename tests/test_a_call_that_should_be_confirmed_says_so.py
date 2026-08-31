"""A genotype read from a VCF says how well the reads actually supported it.

Depth said HOW MANY reads there were. Nothing said how they were DIVIDED — and
that is the field that can tell a clean heterozygote from a mosaic, a duplicated
region mapping onto this one, contamination or an artefact. A call whose reads
split 15/85 was presented in exactly the same words as one that split 50/50, and
a ClinVar finding is read off it and taken to a doctor.

The caller's own quality score was not read either, and the flags that DID exist
— imputed, filtered, low depth — were three separate keys a reader had to know to
look for. They are now one list, and every entry names the measurement that
raised it: «needs confirmation» without a reason is unanswerable, and a reader
who cannot answer it ignores it.

What these thresholds are NOT is clinical. They are quality-control heuristics
and they are deliberately permissive: what they produce is «have this confirmed
by another method», never «this is wrong». A call outside the band is usually
still right, and one inside it can still be wrong. They exist because the
alternative to a flag here is not silence — it is false confidence.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path

from scholion import genome


class TestHowTheReadsWereDivided(unittest.TestCase):

    FMT = ["GT", "AD", "DP"]

    def test_the_fraction_comes_out_of_ad(self):
        self.assertEqual(genome._allele_fraction(self.FMT, ["0/1", "85,15", "100"],
                                                 ["0", "1"]), 0.15)

    def test_a_file_without_ad_says_nothing_rather_than_guessing(self):
        self.assertIsNone(genome._allele_fraction(["GT", "DP"], ["0/1", "100"], ["0", "1"]))

    def test_a_malformed_ad_says_nothing(self):
        for bad in (["0/1", "abc", "100"], ["0/1", "0,0", "100"], ["0/1", "50", "50"]):
            self.assertIsNone(genome._allele_fraction(self.FMT, bad, ["0", "1"]))

    def test_the_second_alternate_allele_is_the_one_counted(self):
        """A multi-allelic row: the fraction has to be of the allele this person
        was actually called for, not of «everything that is not reference»."""
        af = genome._allele_fraction(self.FMT, ["0/2", "60,5,35", "100"], ["0", "2"])
        self.assertEqual(af, 0.35)


class TestWhatIsWorthConfirming(unittest.TestCase):

    def test_a_heterozygote_whose_reads_do_not_split_near_half(self):
        why = genome.confirmation_reasons({}, af=0.15, idx=["0", "1"])
        self.assertEqual([w["what"] for w in why], ["allele_fraction_off_half"])

    def test_a_heterozygote_that_splits_near_half_is_left_alone(self):
        for af in (0.42, 0.5, 0.58):
            self.assertEqual(genome.confirmation_reasons({}, af=af, idx=["0", "1"]), [])

    def test_a_homozygote_still_carrying_the_reference(self):
        why = genome.confirmation_reasons({}, af=0.7, idx=["1", "1"])
        self.assertEqual([w["what"] for w in why],
                         ["allele_fraction_low_for_homozygote"])

    def test_a_homozygous_reference_is_not_judged_by_that_rule(self):
        self.assertEqual(genome.confirmation_reasons({}, af=0.02, idx=["0", "0"]), [])

    def test_the_callers_own_quality_score(self):
        why = genome.confirmation_reasons({}, qual=12.0, idx=["0", "1"])
        self.assertEqual([w["what"] for w in why], ["low_qual"])
        self.assertEqual(genome.confirmation_reasons({}, qual=99.0, idx=["0", "1"]), [])

    def test_the_flags_that_already_existed_join_the_same_list(self):
        why = genome.confirmation_reasons(
            {"low_depth": True, "filtered": "LowGQ", "imputed": True}, depth=4)
        self.assertEqual([w["what"] for w in why], ["low_depth", "filtered", "imputed"])

    def test_every_reason_names_the_measurement_that_raised_it(self):
        why = genome.confirmation_reasons({"low_depth": True}, qual=5.0, af=0.1,
                                          idx=["0", "1"], depth=3)
        self.assertEqual(len(why), 3)
        for w in why:
            self.assertIn("value", w)
            self.assertIsNotNone(w["value"])

    def test_a_clean_call_raises_nothing(self):
        self.assertEqual(
            genome.confirmation_reasons({}, qual=140.0, af=0.49, idx=["0", "1"], depth=42), [])


class TestEveryReasonCanBeSaidOutLoud(unittest.TestCase):
    """A code with no sentence behind it reaches the reader as its own key — this
    project has shipped ⟦…⟧ to a person once already."""

    def test_each_reason_has_a_phrase_in_both_languages(self):
        """The language is global state, so it is put back. A test that leaves it
        where it found it is not being tidy — the suite runs in one process, and
        every test after this one would otherwise read a catalogue it did not
        choose. That is how this file first failed six unrelated tests."""
        from scholion import i18n
        was = i18n.lang()
        self.addCleanup(i18n.set_lang, was)
        reasons = ("allele_fraction_off_half", "allele_fraction_low_for_homozygote",
                   "low_qual", "low_depth", "filtered", "imputed")
        for lang in ("en", "ru"):
            i18n.set_lang(lang)
            for what in reasons:
                phrase = i18n.t("genome.confirm_" + what)
                self.assertNotIn("⟦", phrase, f"{lang}: genome.confirm_{what}")
            self.assertNotIn("⟦", i18n.t("genome.needs_confirmation",
                                         what="x", value=1))


if __name__ == "__main__":
    unittest.main()
