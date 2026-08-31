"""A gene that takes a diplotype says so, instead of showing a tag SNP.

CYP2D6 decides codeine, tramadol, tamoxifen and the tricyclics. It is resolved by
the full diplotype — copy number and phase — and by no single SNP. The knowledge
base has said exactly that since it was written: `track2_targets.CYP2D6` carries
`needs_full_diplotype: true` and the note «a single SNP is not enough».

Nothing read it. Asked about codeine, the answer printed the gene, the word
«important», the bare genotype `rs3892097 A/A`, and the promise that a full genome
would bring the rest — which for THIS gene is false. A fact computed, written down
and read by nobody is indistinguishable, from outside, from a fact nobody
established; this project has now found that shape five times.

So: the flag is read; the tag SNPs stay visible under a name that says what they
are; and the sentence about what would close the gap names the two things that
actually close it — a star-allele caller over the reads, or a laboratory report
that states the diplotype. The second is the only route open to somebody who has
no BAM, which is what this task was raised about.

The last class here is about that route: a diplotype the person was GIVEN is
evidence, but it is not the same evidence as one called from their own
alignments, and the note used to assert the caller's name over both.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path

from scholion import core
from scholion.engine import pgx


class TestTheCatalogueIsActuallyRead(unittest.TestCase):

    def test_the_flag_is_where_the_code_looks_for_it(self):
        """If the catalogue is ever reshaped, this fails here rather than by
        quietly going back to printing a tag SNP as the answer."""
        target = (core.cpic_kb().get("track2_targets") or {}).get("CYP2D6") or {}
        self.assertTrue(target.get("needs_full_diplotype"))
        self.assertTrue(str(target.get("note") or "").strip())

    def test_the_gene_is_not_modelled_by_tag_snps_at_all(self):
        """The premise. If CYP2D6 ever gains a tag-SNP model, the branch under
        test stops being reachable and this test says so."""
        self.assertNotIn("CYP2D6", core.cpic_kb().get("genes", {}))


class TestWhatTheAnswerSaysAboutSuchAGene(unittest.TestCase):

    def _assess(self):
        return pgx._assess_gene("CYP2D6")

    def test_it_is_not_computable_and_says_which_kind_of_gap_this_is(self):
        a = self._assess()
        self.assertFalse(a["computable"])
        self.assertTrue(a.get("needs_full_diplotype"))
        self.assertEqual(a["phenotype"], "needs_diplotype")

    def test_the_tag_snps_are_not_offered_as_the_genes_variants(self):
        """`markers` is what the renderer prints as «variants: …». For this gene
        it must be empty, or the bare genotype returns to standing beside the
        word «important» as the answer."""
        a = self._assess()
        self.assertEqual(a["markers"], [])
        self.assertIn("tag_markers", a)

    def test_it_names_what_would_actually_close_the_gap(self):
        a = self._assess()
        closes = a.get("closes") or ""
        self.assertTrue(closes)
        low = closes.lower()
        self.assertTrue("pypgx" in low or "pharmcat" in low)
        self.assertTrue("laborator" in low or "лаборатор" in low)

    def test_it_does_not_promise_that_a_variant_file_closes_it(self):
        """The old answer's actual words. A VCF, however complete, does not
        resolve copy number — promising it is the defect, not the wording."""
        a = self._assess()
        blob = (str(a.get("label", "")) + " " + str(a.get("closes", ""))).lower()
        self.assertNotIn("track 2", blob)
        self.assertNotIn("трек 2", blob)


class TestADiplotypeSaysWhereItCameFrom(unittest.TestCase):
    """Both routes are good evidence. They are not the same evidence, and the
    sentence used to assert the caller's name over both."""

    def test_a_call_from_our_own_pipeline_is_recognised(self):
        self.assertTrue(pgx._from_reads({"source": "pgx_star_alleles.tsv"}))
        self.assertTrue(pgx._from_reads({"source": "PyPGx 0.25"}))
        self.assertTrue(pgx._from_reads({"source": "PharmCAT"}))

    def test_a_report_the_person_was_given_is_not_mistaken_for_one(self):
        self.assertFalse(pgx._from_reads({"source": "laboratory PGx report 2026-03-14"}))

    def test_a_source_that_did_not_name_itself_is_not_assumed_to_be_ours(self):
        """Silence is not a claim of provenance. Assuming the pipeline here is
        exactly the default this project removes."""
        self.assertFalse(pgx._from_reads({}))
        self.assertFalse(pgx._from_reads({"source": ""}))

    def test_both_sentences_exist_in_both_languages(self):
        from scholion import i18n
        was = i18n.lang()
        self.addCleanup(i18n.set_lang, was)
        for lang in ("en", "ru"):
            i18n.set_lang(lang)
            for key in ("phenotype.from_called_diplotype", "phenotype.from_reported_diplotype",
                        "gene.needs_diplotype", "gene.diplotype_closes",
                        "prescription.tag_snps_only"):
                self.assertNotIn("⟦", i18n.t(key, diplotype="*1/*4", source="x", list="y"),
                                 f"{lang}: {key}")


if __name__ == "__main__":
    unittest.main()
