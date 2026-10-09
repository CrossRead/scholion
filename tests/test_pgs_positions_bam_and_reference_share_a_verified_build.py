"""Reject coordinate mismatches before an expensive BAM call begins."""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import support


class BuildGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = support.ROOT / "src/ingest"
        path = cls.directory / "_pgs_build.py"
        if not path.exists():
            raise unittest.SkipTest("ingest scripts are absent")
        spec = importlib.util.spec_from_file_location("pgs_coordinate_guard", path)
        cls.guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.guard)

    def test_bam_reference_and_bed_must_agree_even_with_full_coverage(self):
        for build, length in (("GRCh37", 249250621), ("GRCh38", 248956422)):
            with self.subTest(build=build), tempfile.TemporaryDirectory() as temp:
                d = Path(temp).resolve(); bed = d / "sites.bed"; bed.write_text("chr1\t99\t100\n", encoding="utf-8")
                reference = d / "ref.fa"; fai = d / "ref.fa.fai"
                fai.write_text(f"chr1\t{length}\t0\t60\t61\n", encoding="utf-8")
                self.guard.bed_metadata(bed, build, [{"harmonized_build": build}])
                run = mock.Mock(stdout=f"@SQ\tSN:chr1\tLN:{length}\n")
                with mock.patch.dict(os.environ, {"PGS_GENOME_BUILD": build}), \
                     mock.patch.object(self.guard.subprocess, "run", return_value=run):
                    self.assertEqual(build, self.guard.check_inputs(bed, d / "input.bam", reference))
                    fai.write_text("chr1\t1000\t0\t60\t61\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "same verified"):
                        self.guard.check_inputs(bed, d / "input.bam", reference)
                    fai.write_text(f"chr1\t{length}\t0\t60\t61\n", encoding="utf-8")
                    bed.write_text("chr1\t199\t200\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "provenance"):
                        self.guard.check_inputs(bed, d / "input.bam", reference)

    def test_unknown_build_or_missing_metadata_refuses(self):
        with mock.patch.dict(os.environ, {"PGS_GENOME_BUILD": ""}):
            with self.assertRaisesRegex(ValueError, "no default"):
                self.guard.requested_build()
        self.assertIsNone(self.guard.assembly_from_lengths([1000]))
        self.assertIsNone(self.guard.assembly_from_lengths([249250621, 248956422]))

    def test_extraction_selects_the_target_coordinates_and_writes_provenance(self):
        for build in ("GRCh37", "GRCh38"):
            with self.subTest(build=build), tempfile.TemporaryDirectory() as temp:
                d = Path(temp).resolve(); cache = d / "scores"; cache.mkdir()
                for target, pos in (("GRCh37", 100), ("GRCh38", 200)):
                    with gzip.open(cache / f"PGS000001_hmPOS_{target}.txt.gz", "wt", encoding="utf-8") as handle:
                        handle.write(f"#pgs_id=PGS000001\n#genome_build=GRCh37\n#HmPOS_build={target}\nhm_chr\thm_pos\n1\t{pos}\n")
                out = d / "sites.bed"
                env = dict(os.environ, PGS_GENOME_BUILD=build, SCHOLION_PRS_CACHE=str(cache))
                result = subprocess.run([sys.executable, str(self.directory / "prs_extract_sites.py"), str(out)],
                                        env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(f"chr1\t{99 if build == 'GRCh37' else 199}\t{100 if build == 'GRCh37' else 200}\n", out.read_text(encoding="utf-8"))
                self.assertEqual(build, self.guard.check_bed(out, build)["genome_build"])
                meta = json.loads(Path(str(out) + ".meta.json").read_text(encoding="utf-8"))
                self.assertEqual("GRCh37", meta["models"][0]["original_build"])


if __name__ == "__main__":
    unittest.main()
