"""A local SNP confirmation must retain identity and refuse unsafe evidence."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import fastalite, genome, sites


class TestBamPositionConfirmation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bam = self.root / "synthetic.bam"
        self.bam.write_bytes(b"synthetic alignment witness")
        Path(str(self.bam) + ".bai").write_bytes(b"synthetic index witness")
        self.loc = {"chrom": "1", "pos": 100, "ref": "A", "alt": "G"}
        self.build = {"assembly": "GRCh38", "prefix": "", "contigs": {"1": 248956422}}
        self.fasta = mock.Mock(index={"1": (248956422,)})
        self.fasta.fetch.return_value = "A"
        self.calls = []
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(sites, "requirements", return_value={
            "vcf": "synthetic.vcf", "bam": str(self.bam), "reference": "synthetic.fa",
            "bcftools": "synthetic-bcftools"}))
        self.alignment = stack.enter_context(mock.patch.object(sites, "alignment_build", return_value=self.build))
        stack.enter_context(mock.patch.object(fastalite, "Fasta", return_value=self.fasta))
        self.sample = stack.enter_context(mock.patch.object(genome, "sample_index", return_value=0))
        stack.enter_context(mock.patch.object(genome, "samples_of", return_value=["SYNTHETIC"]))

    def read(self, gt="0/1", fmt="GT:DP:GQ", sample="SYNTHETIC", ref="A", alt="G",
             values="0/1:30:60", status="PASS", position=100, mutate=False, empty=False):
        values = gt + values[values.index(":"):]
        body = "" if empty else f"1\t{position}\t.\t{ref}\t{alt}\t60\t{status}\t.\t{fmt}\t{values}\n"
        output = (f"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample}\n" + body).encode()
        def run(argv, **kwargs):
            self.calls.append(argv)
            if mutate and argv[1] == "call":
                self.bam.write_bytes(b"changed alignment")
            return subprocess.CompletedProcess(argv, 0, stdout=output if argv[1] == "call" else b"pileup")
        with mock.patch.object(sites.subprocess, "run", side_effect=run):
            return sites.verify_position(self.loc, "GRCh38", self.bam)

    def test_called_and_reference_genotypes_keep_quality_and_identity_without_writing(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        result = self.read(gt="0|1")
        self.assertEqual((result["genotype"], result["phased"], result["depth"]), ("AG", True, 30))
        self.assertEqual(result["variant_identity"], {"assembly": "GRCh38", "chrom": "1", "pos": 100, "ref": "A", "alt": "G"})
        reference = self.read(gt="0/0", fmt="GT:DP:PL", values="0/0:31:0,40,80")
        self.assertEqual((reference["genotype"], reference["confidence"], reference["likelihood_gap_phred"]), ("AA", "confirmed_ref", 40))
        self.assertIn("--keep-unseen-allele", self.calls[-1])
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_low_depth_quality_filter_and_ambiguous_reference_are_refused(self):
        for kw in ({"values": "0/1:9:60"}, {"values": "0/1:30:19"}, {"status": "LowQual"},
                   {"gt": "0/0", "fmt": "GT:DP:PL", "values": "0/0:31:0,5,20"},
                   {"gt": "0/0", "fmt": "GT:DP:PL", "values": "0/0:31:."}):
            with self.subTest(kw=kw):
                self.assertEqual(self.read(**kw), {"reason": "low_quality"})

    def test_other_allele_partial_call_wrong_position_and_sample_are_not_confirmations(self):
        for kw in ({"alt": "C"}, {"gt": "./1"}, {"gt": "2/2"}, {"ref": "T"},
                   {"position": 101}, {"empty": True}):
            with self.subTest(kw=kw):
                self.assertEqual(self.read(**kw), {"reason": "no_call"})
        self.assertEqual(self.read(sample="OTHER"), {"reason": "sample_mismatch"})
        self.sample.return_value = None
        self.assertEqual(self.read(), {"reason": "sample_mismatch"})

    def test_reference_and_assembly_mismatches_do_not_start_the_caller(self):
        self.fasta.fetch.return_value = "C"
        self.assertEqual(self.read(), {"reason": "reference_mismatch"})
        self.assertFalse(self.calls)
        self.build["assembly"] = "GRCh37"
        self.assertEqual(self.read(), {"reason": "build_mismatch"})
        self.assertFalse(self.calls)

    def test_input_changes_failures_and_unsupported_loci_cannot_produce_a_reading(self):
        self.assertEqual(self.read(mutate=True), {"reason": "read_failed"})
        self.alignment.side_effect = OSError("unreadable synthetic input")
        self.assertEqual(self.read(), {"reason": "read_failed"})
        self.loc["chrom"] = "X"
        self.assertEqual(self.read(), {"reason": "unsupported_locus"})
        Path(str(self.bam) + ".bai").unlink()
        self.assertEqual(self.read(), {"reason": "no_index"})
