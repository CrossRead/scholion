"""A chip is a connected input, and the frame says which questions it opens.

R6 of the 0.4.11 audit. The frame of open and closed paths was built from the
readiness of the SEQUENCED path alone. An array is ready — the catalogue and the
pharmacogenetics resting on it are exactly what a chip answers as designed — so
its status said «array connected» on one line and «no genome» on every one of
the six paths beneath it. Two sentences about the same file, contradicting each
other, and the second one closing the two paths the chip can carry.

The frame now belongs to whichever input answered. On a chip the catalogue and
pharmacogenetics are open; a region — any gene beyond the catalogue — is closed
with its own reason, because a chip reads the positions somebody chose and a
gene is a stretch nobody chose; the screens are closed as too narrow, which is
what they are. And the gene report follows the same frame instead of walking on
into a region query with no VCF at all.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import format as fmt, gene_region, genes, genome

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "arrays" / "23andme.txt"


class _ChipOnly(unittest.TestCase):
    """A genome folder holding one consumer array export and nothing else."""

    KEYS = ("SCHOLION_GENOME_DIR", "SCHOLION_GENOME_VCF", "SCHOLION_GENOME_SAMPLE",
            "SCHOLION_ARRAY_FILE", "SCHOLION_CACHE_DIR", "SCHOLION_GENOME_ENGINE")

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in self.KEYS}
        for k in self.KEYS:
            os.environ.pop(k, None)
        self.dir = Path(tempfile.mkdtemp())
        shutil.copy(FIXTURE, self.dir / "genome_Full.txt")
        os.environ["SCHOLION_GENOME_DIR"] = str(self.dir)
        self._clear()

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._clear()

    @staticmethod
    def _clear():
        from scholion import array_genome as _arr
        genome.samples_of.cache_clear()
        for name in ("index", "array_path", "_index"):
            fn = getattr(_arr, name, None)
            if hasattr(fn, "cache_clear"):
                fn.cache_clear()

    def paths(self):
        av = genome.available()
        self.assertTrue(av["ready"], av.get("reason"))
        self.assertEqual(av["input_class"], "array")
        return {p["path"]: p for p in av["paths"]}


class TestTheFrameBelongsToTheInputThatAnswered(_ChipOnly):

    def test_no_path_says_no_genome_over_a_connected_chip(self):
        why = {name: p.get("why") for name, p in self.paths().items()}
        self.assertNotIn("no_genome", why.values(), why)

    def test_the_catalogue_and_pharmacogenetics_are_open(self):
        paths = self.paths()
        self.assertTrue(paths["loci"]["open"])
        self.assertTrue(paths["pgx"]["open"])

    def test_a_region_is_closed_with_its_own_reason(self):
        region = self.paths()["region"]
        self.assertFalse(region["open"])
        self.assertEqual(region["why"], "not_sequenced")

    def test_the_screens_are_closed_as_too_narrow(self):
        paths = self.paths()
        for name in ("clinvar", "acmg", "pgs"):
            with self.subTest(path=name):
                self.assertFalse(paths[name]["open"])
                self.assertEqual(paths[name]["why"], "input_too_narrow")

    def test_the_status_page_prints_the_frame(self):
        out = fmt.genome_status_report(genome.available())
        self.assertNotIn("⟦", out)
        self.assertNotIn("no genome is connected", out)


class TestAGeneReportFollowsTheFrame(_ChipOnly):

    def test_a_gene_beyond_the_catalogue_is_refused_by_the_same_reason(self):
        """The report used to walk on into the region query with no VCF at all.
        The gene is resolved by a stub: whether an annotation is on this machine
        has nothing to do with the property under test."""
        saved = genes.resolve
        genes.resolve = lambda gene, allow_network=True: {
            "gene": gene, "chrom": "17", "start": 43_044_295, "end": 43_125_483,
            "strand": -1, "cds": []}
        try:
            out = gene_region.report("BRCA1")
        finally:
            genes.resolve = saved
        self.assertEqual(out["status"], "not_sequenced")
        self.assertEqual(out["reason"], "not_sequenced")
        self.assertNotIn("variants", out, "a count here would be a claim nothing measured")
        self.assertTrue(out["message"].strip())
        self.assertNotIn("⟦", out["message"])


class TestTheSentencesExist(unittest.TestCase):

    def test_in_both_languages(self):
        from scholion.i18n import t as _t
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                for key in ("paths.why.not_sequenced", "genome.refused.not_sequenced",
                            "genome.refused_head.not_sequenced"):
                    with self.subTest(lang=lang, key=key):
                        self.assertNotIn("⟦", _t(key))
            finally:
                os.environ.pop("SCHOLION_LANG", None)


if __name__ == "__main__":
    unittest.main()
