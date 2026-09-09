"""A file carved out of a genome is not a second genome.

The folder holds the person's reads and, by design, several files called from
those same reads: the loci of the catalogue, the scoring sites of the polygenic
models, the longevity markers. Counting one of those as a second genome makes the
choice ambiguous, and an ambiguous choice reads NOTHING — every locus in the
product then answers «not read» while the reads sit in the file beside it.

That is what happened. The exclusion was a set of four file NAMES, and on 14.08 an
output was written under a fifth; nothing failed, and the genomic layer went dark
for a month with a message about positions. So the question is no longer what a
file is called but what it says about itself: bcftools records the command in the
header, and a pileup restricted to a list of sites — or an annotation pass over
another file's rows — is not the genome it came from.

Two invariants beside it. The rule may narrow the candidate set and may never
empty it: a folder holding nothing but extractions still holds the person's reads.
And whatever it sets aside is REPORTED with the reason, because a file that
disappears from a list silently is the same defect one level down.
"""
from __future__ import annotations

import gzip
import os
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import genome
# The same one-block BGZF writer the older genome test uses. Plain gzip is a file
# this layer deliberately refuses to call connected, so a fixture written with it
# tests the refusal instead of the rule.
from test_one_file_one_person import bgzf

_ROW = "chr1\t55039974\trs11591147\tG\tA\t60\t.\tDP=30\tGT:DP\t0/1:30\n"


def _vcf(extra_header=(), samples=("ME",)):
    head = "##fileformat=VCFv4.2\n" + "".join(h + "\n" for h in extra_header)
    return (head
            + "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t"
            + "\t".join(samples) + "\n" + _ROW).encode()


#: The exact lines bcftools wrote into this project's own files. Copied from a
#: real folder rather than invented: a rule tested only against headers written
#: to pass it proves nothing about the files it will meet.
PILEUP_WHOLE = ("##bcftoolsVersion=1.24+htslib-1.24",
                "##bcftoolsCommand=mpileup -f /ref/GRCh38_no_alt.fa -r chr1:1-20000000 -a AD,DP -Ou /w/x.bam",
                "##bcftools_concatCommand=concat -Oz /w/_chr/chr1_1_20000000.vcf.gz /w/_chr/chr2.vcf.gz")
PILEUP_SITES = ("##bcftoolsVersion=1.24+htslib-1.24",
                "##bcftoolsCommand=mpileup -R /tmp/scoring_ext.bed -f /ref/GRCh38_no_alt.fa -a FORMAT/DP -Ou /w/x.bam",
                "##bcftools_callCommand=call -m -Oz -o genome/scoring_sites_ext.fixed.vcf.gz; Date=Thu Aug 14 07:39:00 2026")
ANNOTATED = PILEUP_WHOLE + (
                "##bcftools_annotateCommand=annotate -a /w/clinvar/clinvar.chr.vcf.gz -c INFO/CLNSIG -Oz",)


class _Folder(unittest.TestCase):

    KEYS = ("SCHOLION_GENOME_DIR", "SCHOLION_GENOME_VCF", "SCHOLION_GENOME_SAMPLE")

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in self.KEYS}
        for k in self.KEYS:
            os.environ.pop(k, None)
        self.dir = Path(tempfile.mkdtemp())
        os.environ["SCHOLION_GENOME_DIR"] = str(self.dir)
        genome.samples_of.cache_clear()
        genome._header.cache_clear()

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        genome.samples_of.cache_clear()
        genome._header.cache_clear()

    def write(self, name, header=()):
        p = self.dir / name
        p.write_bytes(bgzf(_vcf(header)))
        Path(str(p) + ".tbi").write_bytes(b"\x1f\x8b" + b"\0" * 30)
        return p


class TestTheFileSaysWhatItIs(_Folder):

    def test_a_call_restricted_to_a_list_of_sites_is_an_extraction(self):
        self.assertEqual(
            genome.carved_from_a_genome(str(self.write("anything.vcf.gz", PILEUP_SITES))),
            "sites_only")

    def test_a_whole_genome_call_is_not(self):
        self.assertIsNone(
            genome.carved_from_a_genome(str(self.write("mine.vcf.gz", PILEUP_WHOLE))))

    def test_an_annotated_copy_is_an_extraction(self):
        self.assertEqual(
            genome.carved_from_a_genome(str(self.write("mine.ann.vcf.gz", ANNOTATED))),
            "annotated_copy")

    def test_our_own_stamp_is_enough_on_its_own(self):
        """A writer that leaves no command line still has to be able to say so."""
        self.assertEqual(
            genome.carved_from_a_genome(str(self.write(
                "x.vcf.gz", ("##scholion=derived:loci_sites",)))),
            "declared")

    def test_the_name_is_never_consulted(self):
        """Both halves of it: an extraction under an unknown name is still one,
        and a genome under a name our pipeline once used is still a genome."""
        self.assertEqual(genome.carved_from_a_genome(
            str(self.write("scoring_sites_ext.fixed.vcf.gz", PILEUP_SITES))), "sites_only")
        self.assertIsNone(genome.carved_from_a_genome(
            str(self.write("loci_sites.vcf.gz", PILEUP_WHOLE))))


class TestTheFolderResolvesToOneGenome(_Folder):

    def test_the_case_that_took_a_month_to_notice(self):
        """One genome, one extraction under a name no list held. Before this rule
        the folder offered two candidates, nothing was chosen, and every locus in
        the product answered «not read»."""
        mine = self.write("NA12878.full.vcf.gz", PILEUP_WHOLE)
        self.write("scoring_sites_ext.fixed.vcf.gz", PILEUP_SITES)
        av = genome.available()
        self.assertIsNone(av["ambiguous"], "the extraction was counted as a second genome")
        self.assertEqual(av["vcf"], str(mine))
        self.assertEqual([x["why"] for x in genome.vcf_excluded()], ["sites_only"])

    def test_two_real_genomes_are_still_a_question_for_the_person(self):
        self.write("alice.vcf.gz", PILEUP_WHOLE)
        self.write("bob.vcf.gz", PILEUP_WHOLE)
        av = genome.available()
        self.assertEqual((av["ambiguous"] or {}).get("reason"), "several_files")
        self.assertIsNone(av["vcf"])

    def test_the_rule_may_narrow_the_set_and_never_empty_it(self):
        """A folder holding only extractions still holds the person's reads. An
        answer of «no genome here» would be worse than the ambiguity, and worse
        than reading one of them."""
        self.write("a_sites.vcf.gz", PILEUP_SITES)
        self.write("b_sites.vcf.gz", PILEUP_SITES)
        self.assertEqual(len(genome.vcf_candidates()), 2)
        self.assertEqual(genome.vcf_excluded(), [],
                         "nothing may be reported as excluded when nothing was")

    def test_what_was_set_aside_is_reported_with_its_reason(self):
        self.write("mine.vcf.gz", PILEUP_WHOLE)
        self.write("sites.vcf.gz", PILEUP_SITES)
        ex = genome.vcf_excluded()
        self.assertEqual(len(ex), 1)
        self.assertTrue(ex[0]["path"].endswith("sites.vcf.gz"))
        self.assertEqual(ex[0]["why"], "sites_only")


class TestAChoiceIsMadeOnceAndKept(_Folder):

    def setUp(self):
        super().setUp()
        from scholion import core, store
        self.core, self.store = core, store
        self.profile = Path(tempfile.mkdtemp())
        self._prof = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.profile)
        core.reset_cache()

    def tearDown(self):
        if self._prof is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._prof
        self.core.reset_cache()
        super().tearDown()

    def test_the_choice_settles_an_ambiguity_and_survives_the_next_start(self):
        a = self.write("alice.vcf.gz", PILEUP_WHOLE)
        self.write("bob.vcf.gz", PILEUP_WHOLE)
        self.assertEqual((genome.available()["ambiguous"] or {}).get("reason"), "several_files")
        r = self.store.set_genome_vcf(str(a))
        self.assertTrue(r["ok"], r)
        self.core.reset_cache()
        av = genome.available()
        self.assertIsNone(av["ambiguous"])
        self.assertEqual(av["vcf"], str(a))

    def test_a_choice_that_names_nothing_is_refused_rather_than_stored(self):
        r = self.store.set_genome_vcf(str(self.dir / "nope.vcf.gz"))
        self.assertFalse(r["ok"])
        self.assertIsNone(self.core.chosen_genome_vcf())

    def test_a_file_that_is_not_a_vcf_is_refused(self):
        p = self.dir / "notes.txt"
        p.write_text("x", encoding="utf-8")
        self.assertFalse(self.store.set_genome_vcf(str(p))["ok"])

    def test_a_choice_whose_file_moved_says_so_instead_of_asking_again(self):
        a = self.write("alice.vcf.gz", PILEUP_WHOLE)
        self.store.set_genome_vcf(str(a))
        self.core.reset_cache()
        a.unlink()
        genome._header.cache_clear()
        amb = genome.available()["ambiguous"] or {}
        self.assertEqual(amb.get("reason"), "chosen_missing")
        self.assertTrue(str(amb.get("chosen") or "").endswith("alice.vcf.gz"))

    def test_clearing_it_returns_the_folder_to_the_search(self):
        a = self.write("alice.vcf.gz", PILEUP_WHOLE)
        self.store.set_genome_vcf(str(a))
        self.core.reset_cache()
        self.store.set_genome_vcf("")
        self.core.reset_cache()
        self.assertIsNone(self.core.chosen_genome_vcf())
        self.assertEqual(genome.available()["vcf"], str(a))


if __name__ == "__main__":
    unittest.main()
