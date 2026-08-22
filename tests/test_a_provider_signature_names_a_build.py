"""A provider's signature may name a build — and only when it names one.

Task 75. The build of a file is established four ways, and they are not equally
strong: a contig length is a fact about the reference, a `##reference=` line is
a path somebody typed and may no longer own, and a provider signature is an
inference about the pipeline that produced the file. The third one was missing,
and it covers a narrow real class — an exome or a panel whose header carries no
`##contig` lengths and whose rows hold nothing past the end of chromosome 1, so
there is nothing to measure and nothing to probe.

What is guarded here is not that the signatures exist. It is that they cannot
become the silent default this layer was built to remove:

  * a signature that recognises only the PROVIDER answers nothing — DRAGEN runs
    against either build, so that entry demands the reference path too;
  * every sample in the table fires its own entry and no other, so a pattern
    cannot rot into one that matches nothing (or everything) unnoticed;
  * a header that says nothing yields `None`, not a guess;
  * and the ranking holds: a contig length beats a signature, a signature beats
    a `##reference=` line.
"""
from __future__ import annotations

import gzip
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholion import genome  # noqa: E402

BUILDS = set(genome._LENGTH_TO_ASSEMBLY.values())


def _vcf(header: str) -> pathlib.Path:
    """A real file, because the reader reads files and not strings."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="signature_"))
    p = d / "sample.vcf.gz"
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        fh.write("##fileformat=VCFv4.2\n" + header.rstrip("\n") + "\n"
                 "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
    return p


class TestTheTableIsEvidenceAndNotAHabit(unittest.TestCase):

    def test_every_entry_is_complete(self):
        self.assertTrue(genome._PROVIDER_SIGNATURES, "the table is empty — nothing is guarded")
        for sig in genome._PROVIDER_SIGNATURES:
            with self.subTest(provider=sig.get("provider")):
                for field in ("provider", "assembly", "needs", "why", "sample"):
                    self.assertTrue(sig.get(field), f"«{field}» is missing or empty")
                self.assertIn(sig["assembly"], BUILDS,
                              "the build is spelled in a way nothing else in the project uses")
                # Prose, not a word. A claim about somebody's pipeline that nobody
                # wrote down is one nobody can check when it stops being true.
                self.assertGreater(len(sig["why"].split()), 5,
                                   "«why» must say why, in a sentence")

    def test_every_sample_fires_its_own_entry_and_no_other(self):
        for sig in genome._PROVIDER_SIGNATURES:
            with self.subTest(provider=sig["provider"]):
                hit = genome._signature_assembly(sig["sample"])
                self.assertIsNotNone(hit, "this pattern matches nothing, not even its own sample")
                self.assertEqual(sig["provider"], hit["provider"],
                                 "two entries claim the same header")
                self.assertEqual(sig["assembly"], hit["assembly"])

    def test_a_provider_alone_settles_nothing(self):
        """The DRAGEN case, spelled out: the pipeline runs against either build."""
        two_part = [s for s in genome._PROVIDER_SIGNATURES if len(s["needs"]) > 1]
        self.assertTrue(two_part, "no entry needs more than the provider's name")
        for sig in two_part:
            with self.subTest(provider=sig["provider"]):
                first_only = sig["sample"].splitlines()[0]
                self.assertIsNone(genome._signature_assembly(first_only),
                                  "half of a two-part signature was accepted as the whole")

    def test_a_header_that_says_nothing_gets_nothing(self):
        p = _vcf("##source=SomeToolNobodyHasHeardOf\n##contig=<ID=1>")
        self.addCleanup(shutil.rmtree, p.parent, True)
        ev = genome.assembly_evidence(str(p))
        self.assertIsNone(ev["assembly"], "a build was invented for a header that names none")
        self.assertIsNone(ev["how"])


class TestTheRankingHolds(unittest.TestCase):

    def test_a_contig_length_beats_a_signature(self):
        # A length is a fact about the reference; a signature is an inference
        # about the producer. The file below carries both, and they disagree.
        p = _vcf("##dataAnalysisProvider=Sequencing.com\n"
                 "##contig=<ID=1,length=249250621>")           # GRCh37 by length
        self.addCleanup(shutil.rmtree, p.parent, True)
        ev = genome.assembly_evidence(str(p))
        self.assertEqual("GRCh37", ev["assembly"])
        self.assertEqual("contig_length", ev["how"])

    def test_a_signature_beats_a_reference_line(self):
        # The reference path points at hg38; the pipeline that made the file is
        # Dante's DRAGEN against GRCh37, and its own reference line says so.
        p = _vcf("##DRAGENCommandLine=<ID=dragen,Version=\"05.021\">\n"
                 "##reference=file:///references/grch37/reference.bin")
        self.addCleanup(shutil.rmtree, p.parent, True)
        ev = genome.assembly_evidence(str(p))
        self.assertEqual("GRCh37", ev["assembly"])
        self.assertEqual("provider_signature", ev["how"])
        self.assertEqual("Dante Labs (DRAGEN)", ev["provider"])

    def test_a_reference_line_still_answers_when_nothing_else_does(self):
        p = _vcf("##reference=file:///data/hg38/Homo_sapiens_assembly38.fasta")
        self.addCleanup(shutil.rmtree, p.parent, True)
        ev = genome.assembly_evidence(str(p))
        self.assertEqual("GRCh38", ev["assembly"])
        self.assertEqual("reference_line", ev["how"])

    def test_the_person_beats_everything(self):
        import os
        p = _vcf("##contig=<ID=1,length=248956422>")           # GRCh38 by length
        self.addCleanup(shutil.rmtree, p.parent, True)
        old = os.environ.get("SCHOLION_GENOME_ASSEMBLY")
        os.environ["SCHOLION_GENOME_ASSEMBLY"] = "T2T-CHM13v2.0"
        genome.assembly_evidence.cache_clear()
        try:
            ev = genome.assembly_evidence(str(p))
            self.assertEqual("T2T-CHM13v2.0", ev["assembly"])
            self.assertEqual("declared", ev["how"])
        finally:
            if old is None:
                os.environ.pop("SCHOLION_GENOME_ASSEMBLY", None)
            else:
                os.environ["SCHOLION_GENOME_ASSEMBLY"] = old
            genome.assembly_evidence.cache_clear()

    def test_the_weak_ones_are_named_as_weak(self):
        # Downstream has to be able to tell a measured build from an inferred
        # one; that is the whole reason `assembly_of` grew a companion.
        self.assertIn("provider_signature", genome.ASSEMBLY_WEAK)
        self.assertIn("reference_line", genome.ASSEMBLY_WEAK)
        self.assertNotIn("contig_length", genome.ASSEMBLY_WEAK)
        for how in genome.ASSEMBLY_WEAK:
            self.assertIn(how, genome.ASSEMBLY_EVIDENCE)

    def test_the_old_entry_point_still_answers_a_word(self):
        p = _vcf("##contig=<ID=1,length=248956422>")
        self.addCleanup(shutil.rmtree, p.parent, True)
        self.assertEqual("GRCh38", genome.assembly_of(str(p)))


if __name__ == "__main__":                                    # pragma: no cover
    unittest.main()
