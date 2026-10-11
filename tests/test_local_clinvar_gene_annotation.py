"""A legacy annotation gets gene names only from exact local reference alleles."""
from __future__ import annotations

import gzip
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, genome

class LocalGeneAnnotation(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.addCleanup(support.pin_profile(self.root))
        self.patch = mock.patch.dict(os.environ, {"SCHOLION_CLINVAR_CACHE": str(self.root)})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.path = self.root / "clinvar.vcf.gz"
        Path(str(self.path) + ".tbi").touch()
        self.header("GRCh38")
        (self.root / "clinvar_meta.json").write_text(
            '{"url":"https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"}', encoding="utf-8")
        (self.root / "clinvar_hits.tsv").write_text(
            "chrom\tpos\tref\talt\nchr1\t100\tA\tG\ninvalid\t200\tC\tT\n", encoding="utf-8")
    def header(self, build):
        with gzip.open(self.path, "wt", encoding="utf-8") as out:
            out.write("##reference=" + build + "\n#CHROM\n1\t100\n")
    def read(self, result):
        with mock.patch.object(genome, "_have_bcftools", return_value=True), \
             mock.patch.object(core, "genome_bases", return_value=[self.root]), \
             mock.patch.object(genome.subprocess, "run", return_value=result) as query:
            found = genome._clinvar_local_gene_map()
            return found, query
    def test_local_query_uses_exact_alleles_and_omits_invalid_coordinates(self):
        result = subprocess.CompletedProcess([], 0, "1\t100\tA\tG\tGNMT:1|MTR:2\n1\t100\tA\tT\tOTHER:3\n1\t100\tC\tG\t.\n")
        found, query = self.read(result)
        self.assertEqual("GNMT|MTR", found[("1", "100", "A", "G")])
        self.assertEqual("OTHER", found[("1", "100", "A", "T")])
        self.assertNotIn(("1", "100", "C", "G"), found)
        self.assertEqual("1:100-100", query.call_args.args[0][3])
        self.assertEqual(subprocess.DEVNULL, query.call_args.kwargs["stdin"])
    def test_other_coordinate_build_never_supplies_gene_names(self):
        self.header("GRCh37")
        found, query = self.read(subprocess.CompletedProcess([], 0, ""))
        self.assertEqual({}, found)
        query.assert_not_called()
    def test_unknown_or_different_table_build_cannot_recover_gene_names(self):
        for metadata in ('{}', '{"url":"https://example.org/vcf_GRCh37/clinvar.vcf.gz"}', 'null', 'invalid'):
            (self.root / "clinvar_meta.json").write_text(metadata, encoding="utf-8")
            found, query = self.read(subprocess.CompletedProcess([], 0, "1\t100\tA\tG\tWRONG:1\n"))
            self.assertEqual({}, found)
            query.assert_not_called()

    def test_failed_reference_query_preserves_missing_annotation(self):
        found, _ = self.read(subprocess.CompletedProcess([], 1, ""))
        self.assertEqual({}, found)
