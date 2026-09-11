"""The ACMG table is read with what it says about itself, and a crossed one is not read.

A7 and B.2 of the 0.4.11 audit. The table of secondary findings is written once
by `scholion acmg-scan` and read for months by `scholion acmg`. Two things can
make it a table about nothing: the genome file it was matched against replaced
by one called in another build — every coordinate then half a million bases off
— and a table written by the earlier scan against a ClinVar release of another
build, which holds a silent zero because nothing lined up. Until the sidecar
existed the reader could not tell either from a clean negative, and «no
reportable findings» was printed over both.

The second half is smaller and of the same shape. The scan now keeps a row the
caller itself did not pass — FILTER other than PASS — under `reportable =
filtered`. The reader bucketed everything that was not a finding as a carrier
state, and counted such a row as a second allele when deciding whether a
recessive gene needed phasing: a question raised by a call nobody stood behind.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import acmg_scan, format as fmt, genome


def hit(gene, reportable, zygosity="het", pos="1000", rsid="rs1", filt="PASS"):
    return {"gene": gene, "chrom": "17", "pos": pos, "ref": "G", "alt": "A", "rsid": rsid,
            "zygosity": zygosity, "reportable": reportable, "clnsig": "Pathogenic",
            "review": "reviewed_by_expert_panel", "inheritance": "AD", "report_rule": "any",
            "phenotype": "", "clndn": "", "filter": filt}


class _Table(unittest.TestCase):
    """A genome folder holding a table, optionally its sidecar, and a stubbed
    personal file whose build is GRCh38."""

    KEYS = ("SCHOLION_GENOME_DIR", "SCHOLION_GENOME_VCF", "SCHOLION_GENOME_SAMPLE",
            "SCHOLION_ARRAY_FILE")

    def setUp(self):
        self._env = {k: os.environ.get(k) for k in self.KEYS}
        for k in self.KEYS:
            os.environ.pop(k, None)
        self.dir = Path(tempfile.mkdtemp())
        os.environ["SCHOLION_GENOME_DIR"] = str(self.dir)
        self._saved = (genome.vcf_path, genome.assembly_of)
        genome.vcf_path = lambda: self.dir / "me.vcf.gz"
        genome.assembly_of = lambda vcf: "GRCh38"

    def tearDown(self):
        genome.vcf_path, genome.assembly_of = self._saved
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def write(self, rows, meta=None):
        lines = ["\t".join(acmg_scan.COLS)]
        for r in rows:
            lines.append("\t".join(str(r.get(c, "")) for c in acmg_scan.COLS))
        (self.dir / acmg_scan.OUT_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")
        if meta is not None:
            (self.dir / acmg_scan.META_NAME).write_text(json.dumps(meta), encoding="utf-8")


class TestACrossedTableIsNotReadAsFindings(_Table):

    def test_a_table_matched_in_another_build_than_the_file(self):
        meta = {"assembly": "GRCh37", "clinvar_assembly": "GRCh37", "scanned": "2026-09-01"}
        self.write([hit("BRCA1", "yes")], meta)
        found = genome.acmg_sf_findings()
        self.assertEqual(found["status"], "assembly_crossed")
        self.assertEqual(found["reportable"], [])
        self.assertEqual(found["hits"], [])
        self.assertEqual(found["table_provenance"], meta)
        self.assertIn("GRCh37", found["message"])
        self.assertIn("GRCh38", found["message"])
        self.assertNotIn("⟦", fmt.acmg_report(found))

    def test_a_table_matched_across_clinvar_builds(self):
        """The silent zero: nothing lined up, so nothing was found, and the
        table reads as a clean negative."""
        self.write([], {"assembly": "GRCh38", "clinvar_assembly": "GRCh37"})
        found = genome.acmg_sf_findings()
        self.assertEqual(found["status"], "assembly_crossed")
        self.assertEqual(found["table_assembly"], "GRCh38")
        self.assertEqual(found["clinvar_assembly"], "GRCh37")

    def test_a_matching_table_is_read_and_carries_its_provenance(self):
        meta = {"assembly": "GRCh38", "clinvar_assembly": "GRCh38",
                "clinvar_file_date": "2026-08-31", "scanned": "2026-09-01"}
        self.write([hit("BRCA1", "yes")], meta)
        found = genome.acmg_sf_findings()
        self.assertEqual(found["status"], "ok", found.get("message"))
        self.assertEqual([r["gene"] for r in found["reportable"]], ["BRCA1"])
        self.assertEqual(found["table_provenance"], meta)
        self.assertFalse(found["table_provenance_missing"])

    def test_a_table_without_a_sidecar_is_read_and_says_it_cannot_be_checked(self):
        self.write([hit("BRCA1", "yes")])
        found = genome.acmg_sf_findings()
        self.assertEqual(found["status"], "ok")
        self.assertIsNone(found["table_provenance"])
        self.assertTrue(found["table_provenance_missing"])

    def test_the_sentences_exist_in_both_languages(self):
        from scholion.i18n import t as _t
        for lang in ("en", "ru"):
            os.environ["SCHOLION_LANG"] = lang
            try:
                for key in ("genome.acmg_assembly_crossed_personal",
                            "genome.acmg_assembly_crossed_clinvar"):
                    with self.subTest(lang=lang, key=key):
                        self.assertNotIn("⟦", _t(key, table="GRCh37", other="GRCh38"))
            finally:
                os.environ.pop("SCHOLION_LANG", None)


class TestAFilteredRowIsNeitherAFindingNorACarrierState(_Table):

    META = {"assembly": "GRCh38", "clinvar_assembly": "GRCh38"}

    def test_it_is_listed_on_its_own(self):
        self.write([hit("BRCA1", "yes"), hit("BRCA2", "filtered", pos="2000", rsid="rs2",
                                              filt="LowQual")], self.META)
        found = genome.acmg_sf_findings()
        self.assertEqual([r["gene"] for r in found["reportable"]], ["BRCA1"])
        self.assertEqual(found["carriers"], [], "a row the caller flagged is not a carrier state")
        self.assertEqual([r["gene"] for r in found["filtered"]], ["BRCA2"])

    def test_it_is_not_a_second_allele_of_a_recessive_gene(self):
        """MUTYH is reportable only biallelic. One real heterozygote and one
        LowQual row used to become «two hits, phase unknown»."""
        self.write([hit("MUTYH", "yes", pos="3000", rsid="rs3"),
                    hit("MUTYH", "filtered", pos="3001", rsid="rs4", filt="LowQual")],
                   self.META)
        found = genome.acmg_sf_findings()
        self.assertEqual(found["needs_phase"], [])
        self.assertEqual([r["gene"] for r in found["reportable"]], ["MUTYH"])

    def test_two_real_heterozygotes_still_need_phase(self):
        self.write([hit("MUTYH", "yes", pos="3000", rsid="rs3"),
                    hit("MUTYH", "yes", pos="3001", rsid="rs4")], self.META)
        found = genome.acmg_sf_findings()
        self.assertEqual(len(found["needs_phase"]), 2)
        self.assertEqual(found["reportable"], [])


if __name__ == "__main__":
    unittest.main()
