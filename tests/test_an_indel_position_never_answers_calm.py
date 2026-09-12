"""An indel position never answers calm.

Task 172. A clinician's panel was read position by position through the locus
reader, each locus built from the form — rsID, HGVS, coordinate — and two of the
twenty-three came back with an EMPTY genotype string labelled `assumed_ref`: a
deletion and a duplication in SECISBP2, both frameshifts, the class of event
where «nothing found» costs the most. An empty string handed over as an answer
is silence read as calm — exactly what the four read-states and the refusal by
name for a multiallelic position exist to prevent.

The cause is not a bug in a branch but a shape the reader was never built for.
A VCF writes a deletion at `g.N del` one base upstream, anchored on the base
before it, as a pair of alleles of different length. The reader fetches N and
compares one base a side; it finds nothing at N and calls the nothing
«reference» — and the reference base it doubles into a genotype was the empty
string the form-built locus carried.

Design (b) of the task: refuse by name. The anchor base is not on the form and
not in the catalogue, so even a locus that says «del» cannot be turned into a
pair here, and a pair typed in by hand would still meet a reader that reads one
base a side. So the locus is refused before any file is opened: the coordinate
is given, the event is named, no genotype is written, no reference is assumed.

The guard this file holds: **a locus whose event is not a single-base
substitution never yields a non-empty calm answer, and never `assumed_ref`.**
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import callset, format as fmt, genome
from scholion.i18n import en, ru

#: The two positions of the panel, as the form gave them: an rsID, an HGVS with
#: its accession, a GRCh38 coordinate, and no alleles. Synthetic in every way
#: that matters — no genotype of anybody travels with them.
DELETION = {"rsid": "rs1587874400", "gene": "SECISBP2", "chrom": "9", "pos": 89328754,
            "hgvs": "NC_000009.12:g.89328754del", "ref": "", "alt": ""}
DUPLICATION = {"rsid": "rs1587875298", "gene": "SECISBP2", "chrom": "9", "pos": 89328885,
               "hgvs": "g.89328885dup", "ref": "", "alt": ""}


def row(ref, alt, gt="0/1", chrom="9", pos="89328754", fmt_="GT:DP", extra=None):
    """One VCF data line in the shape `_query_region` returns."""
    return [chrom, pos, ".", ref, alt, "50", "PASS", ".", fmt_, extra or f"{gt}:30"]


class _Reader(unittest.TestCase):
    """Every test hands the reader its rows and nothing else. The no-row path
    asks two more questions — a sites VCF and the call set's shape — and both
    are answered «nothing to say» so that the path is reachable without a file."""

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in
                     ("SCHOLION_GENOME_VCF", "SCHOLION_GENOME_SAMPLE", "SCHOLION_LANG")}
        self._saved = (genome._query_region, genome.vcf_path, genome._index_usable,
                       genome.file_unreadable, genome.sample_index, genome.assembly_of,
                       genome._ref_evidence, callset.measure)
        genome.vcf_path = lambda: Path("/nowhere/x.vcf.gz")
        genome._index_usable = lambda vp: True
        genome.file_unreadable = lambda vp: False
        genome.sample_index = lambda vcf: 0
        genome.assembly_of = lambda vcf: "GRCh38"
        genome._ref_evidence = lambda loc: None
        callset.measure = lambda vcf: {"class": "unknown"}
        os.environ["SCHOLION_LANG"] = "en"

    def tearDown(self):
        (genome._query_region, genome.vcf_path, genome._index_usable,
         genome.file_unreadable, genome.sample_index, genome.assembly_of,
         genome._ref_evidence, callset.measure) = self._saved
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def read(self, rows, loc):
        genome._query_region = lambda vcf, chrom, pos: rows
        return genome._gt_at(dict(loc))


class TestTheDefectAsItWasFound(_Reader):
    """The first test reproduces the panel run: on the old code both loci come
    back `genotype: ''` with `confidence: assumed_ref`."""

    def test_the_deletion_is_not_an_empty_reference(self):
        got = self.read([], DELETION)
        self.assertNotEqual("assumed_ref", got["confidence"],
                            "a frameshift deletion was read as the assumed reference")
        self.assertNotEqual("", got["genotype"],
                            "an empty string went out in the shape of a genotype")
        self.assertEqual("indel_not_read", got["confidence"])
        self.assertIsNone(got["genotype"])

    def test_the_duplication_is_not_either(self):
        got = self.read([], DUPLICATION)
        self.assertEqual("indel_not_read", got["confidence"])
        self.assertIsNone(got["genotype"])
        self.assertEqual("duplication", got["event"])


class TestTheGuard(_Reader):

    def test_a_row_on_the_coordinate_does_not_make_it_calm(self):
        """A substitution standing on the same base is somebody else's variant.
        Read through a locus with no alleles it was `called`, marked unverified,
        and printed as this frameshift's genotype."""
        got = self.read([row("C", "T")], DELETION)
        self.assertEqual("indel_not_read", got["confidence"])
        self.assertIsNone(got["genotype"])

    def test_alleles_of_different_length_are_an_indel_without_any_hgvs(self):
        """A locus written the way a VCF writes the event — `CA→C`, `C→CA` — is
        still not a pair this reader can compare one base a side."""
        for ref, alt in (("CA", "C"), ("C", "CA")):
            with self.subTest(ref=ref, alt=alt):
                got = self.read([], {"rsid": "rs0", "chrom": "9", "pos": 89328753,
                                     "ref": ref, "alt": alt})
                self.assertEqual("indel_not_read", got["confidence"])
                self.assertIsNone(got["genotype"])
                self.assertEqual("indel", got["event"])
                self.assertEqual(f"{ref}>{alt}", got["expected"])

    def test_the_refusal_stands_before_the_file_is_opened(self):
        with mock.patch.object(genome, "vcf_path",
                               side_effect=AssertionError("the file was opened")):
            got = genome._gt_at(dict(DELETION))
        self.assertEqual("indel_not_read", got["confidence"])

    def test_a_chip_does_not_answer_for_it_either(self):
        """A chip's `D`/`I` letters are a vocabulary of their own, not this
        locus's alleles. Without the guard the array branch answered `DI` under
        the label «called»."""
        with mock.patch.object(genome, "vcf_path", return_value=None), \
             mock.patch("scholion.array_genome.status",
                        return_value={"status": "called", "genotype": "DI"}):
            got = genome._gt_at(dict(DELETION))
        self.assertEqual("indel_not_read", got["confidence"])
        self.assertIsNone(got["genotype"])

    def test_the_coordinate_and_the_event_are_named(self):
        got = self.read([], DELETION)
        self.assertEqual("deletion", got["event"])
        self.assertEqual(DELETION["hgvs"], got["hgvs"])
        self.assertIn("9:89328754", got["note"])
        self.assertIn("deletion", got["note"])
        self.assertIn("9:89328753-89328754", got["note"],
                      "the anchored region a person can look at is not named")
        self.assertIsNone(got["expected"], "alleles were invented for a locus that has none")


class TestTheHgvsIsReadForItsEventAndNothingElse(unittest.TestCase):

    def test_the_forms_a_form_can_carry(self):
        cases = {
            "NC_000009.12:g.89328754del": "deletion",
            "g.89328885dup": "duplication",
            "g.100_102del": "deletion",
            "c.671delC": "deletion",
            "g.100_101insA": "insertion",
            "g.100_101dupAT": "duplication",
            "chr1:g.100delinsAT": "delins",
            "g.100C>T": "substitution",
            "NC_000001.11:g.169549811C>T": "substitution",
        }
        for hgvs, kind in cases.items():
            with self.subTest(hgvs=hgvs):
                self.assertEqual(kind, genome._hgvs_event(hgvs))

    def test_a_protein_form_decides_nothing(self):
        """`p.Pro224LeufsTer32` is what the form printed beside the deletion. It
        is not a coordinate and names no genomic event this reader can act on:
        the answer is «does not say», never «therefore a substitution»."""
        self.assertIsNone(genome._hgvs_event("p.Pro224LeufsTer32"))
        self.assertIsNone(genome._hgvs_event(""))
        self.assertIsNone(genome._hgvs_event(None))

    def test_the_letters_on_the_form_are_never_alleles(self):
        """A form prints somebody's genotype letters beside the HGVS — on an
        unstated strand, at times at protein level. The event is read from the
        HGVS alone, and no allele pair is built out of the letters."""
        loc = dict(DELETION, form_genotype="CC", genotype="CC")
        self.assertEqual("deletion", genome._indel_event(loc))
        got = genome._indel_refusal(loc, "deletion")
        self.assertIsNone(got["expected"])
        self.assertIsNone(got["genotype"])


class TestNothingElseChanges(_Reader):
    """Guards against the fix over-reaching. These pass with the fix reverted;
    they are here so the refusal cannot spread to positions it is not about."""

    def test_an_ordinary_substitution_is_untouched(self):
        loc = {"rsid": "rs6025", "gene": "F5", "chrom": "1", "pos": 169549811,
               "hgvs": "NC_000001.11:g.169549811C>T", "ref": "C", "alt": "T"}
        got = self.read([row("C", "T", chrom="1", pos="169549811")], loc)
        self.assertEqual("called", got["confidence"])
        self.assertEqual("CT", got["genotype"])

    def test_a_locus_with_no_alleles_and_no_hgvs_is_still_read_unverified(self):
        """Nothing says what such a locus is, so the existing path stands:
        read, and marked as a check that never happened."""
        loc = {"rsid": "rs0", "chrom": "9", "pos": 89328754}
        got = self.read([row("C", "T")], loc)
        self.assertEqual("called", got["confidence"])
        self.assertTrue(got["unverified_locus"])

    def test_an_empty_reference_field_is_never_doubled_into_a_genotype(self):
        """The same empty string, on a locus nobody can tell is an indel: the
        weakest state may still not carry `''` where a genotype goes."""
        loc = {"rsid": "rs0", "chrom": "9", "pos": 89328754, "ref": "", "alt": ""}
        got = self.read([], loc)
        self.assertNotEqual("", got.get("genotype"))


class TestTheAnswerSaysItOnTheScreen(_Reader):

    def test_both_languages_carry_the_phrases(self):
        keys = ["genome.refused_head.indel_not_read", "genome.refused.indel_not_read"]
        keys += ["genome.event." + k for k in
                 ("deletion", "duplication", "insertion", "delins", "indel", "multi_base")]
        for key in keys:
            for cat, lang in ((en.MESSAGES, "en"), (ru.MESSAGES, "ru")):
                with self.subTest(key=key, lang=lang):
                    self.assertIn(key, cat)
                    self.assertTrue(cat[key].strip())

    def test_the_line_is_a_refusal_and_not_a_genotype(self):
        res = self.read([], DELETION)
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            with self.subTest(lang=lang):
                out = fmt.genome_report({"status": "ok", "rsid": DELETION["rsid"],
                                         "gene": "SECISBP2", "chrom": "9",
                                         "pos": DELETION["pos"], "locus": dict(DELETION),
                                         "result": res, "disclaimer": "—"})
                self.assertIn("rs1587874400", out)
                self.assertNotIn("⟦", out, "a catalogue key reached the reader")
                self.assertNotIn("genotype **", out)
                self.assertTrue(out.lstrip().startswith("⚪"),
                                f"not rendered as a refusal: {out[:80]!r}")


if __name__ == "__main__":
    unittest.main()
