"""The two flags that name the genome file and the sample, for one command.

Both have worked as environment variables since task 63, and both were
documented. The first outside reviewer found them by reading the source with
`rg`, because a variable is not where anybody looks for an option — and then
wrote them in front of every command by hand, six times.
"""
from __future__ import annotations

import os
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import cli


class TestTheGenomeCanBeNamedOnTheCommandLine(unittest.TestCase):

    def setUp(self):
        self._env = {k: os.environ.get(k)
                     for k in ("SCHOLION_GENOME_VCF", "SCHOLION_GENOME_SAMPLE")}

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_the_flags_reach_the_layer_that_reads_the_environment(self):
        cli._main(["genome-status", "--vcf", "/tmp/nowhere.vcf.gz", "--sample", "P243"])
        self.assertEqual(os.environ["SCHOLION_GENOME_VCF"], "/tmp/nowhere.vcf.gz")
        self.assertEqual(os.environ["SCHOLION_GENOME_SAMPLE"], "P243")

    def test_every_command_accepts_them(self):
        """They live on the common parser, so a command that forgot to inherit it
        would fail here rather than in front of somebody."""
        p = cli.build_parser()
        for cmd in ("genome-status", "limits", "overview", "clinvar"):
            with self.subTest(cmd=cmd):
                args = p.parse_args([cmd, "--vcf", "/tmp/x.vcf.gz"])
                self.assertEqual(args.vcf, "/tmp/x.vcf.gz")


if __name__ == "__main__":
    unittest.main()
