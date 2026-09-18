"""The ClinVar file the pipeline cached is the one the engine finds (17.09.2026).

The preparation script caches the published ClinVar VCF under
SCHOLION_CLINVAR_CACHE, or ~/genomic_work/clinvar. The engine looked only beside
the genome, so a machine that had run the pipeline heard «no ClinVar» from the
coverage step, the ACMG scan and the recompute plan — and the coverage the new
systems need could not be measured from the page. One search now serves all
three; an explicit genome directory keeps it inside that directory, so a test on
synthetic data never reaches a real file.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import coverage, recompute


class TestTheCachedFileIsFound(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="cv_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        (self.cache / "clinvar.vcf.gz").write_bytes(b"")

    def test_the_pipeline_cache_is_searched(self):
        env = {k: v for k, v in os.environ.items() if k not in ("SCHOLION_GENOME_DIR", "SCHOLION_CLINVAR_VCF")}
        env["SCHOLION_CLINVAR_CACHE"] = str(self.cache)
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("scholion.core.genome_bases", lambda: [self.root / "genome"]):
            self.assertEqual(self.cache / "clinvar.vcf.gz", coverage.clinvar_path())

    def test_an_explicit_genome_directory_keeps_the_search_inside(self):
        with mock.patch.dict(os.environ, {"SCHOLION_GENOME_DIR": str(self.root / "genome"),
                                          "SCHOLION_CLINVAR_CACHE": str(self.cache)}):
            os.environ.pop("SCHOLION_CLINVAR_VCF", None)
            self.assertIsNone(coverage.clinvar_path())


class TestTheRecomputePlanRunsTheCheckOfTheForms(unittest.TestCase):

    def test_provenance_is_a_step_this_build_runs(self):
        self.assertIn("scholion provenance", recompute.RUNNERS)
        self.assertEqual("labs_docs", recompute.RUNNERS["scholion provenance"]["folder"])


if __name__ == "__main__":
    unittest.main()
