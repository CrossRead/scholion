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
import hashlib
import gzip
import os
import tempfile
import unittest
from unittest import mock
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
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name).resolve()
        (self.dir / "me.vcf.gz").write_bytes(gzip.compress(
            b"##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tME\n"))
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
            meta.update({"personal_path": str(self.dir / "me.vcf.gz"),
                         "personal_identity": acmg_scan.source_identity(self.dir / "me.vcf.gz"),
                         "table_sha256": hashlib.sha256((self.dir / acmg_scan.OUT_NAME).read_bytes()).hexdigest(),
                         "sample": "ME"})
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

    def test_a_table_without_a_sidecar_is_refused_not_read_as_a_finding(self):
        self.write([hit("BRCA1", "yes")])
        found = genome.acmg_sf_findings()
        self.assertEqual(found["status"], "table_unverified")
        self.assertEqual(found["hits"], [])
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


class TestAStaleTableCannotAnswer(_Table):

    def current(self):
        self.write([hit("BRCA1", "yes")], {"assembly": "GRCh38", "clinvar_assembly": "GRCh38"})
        return self.dir / "me.vcf.gz"

    def refused(self, reason):
        found = genome.acmg_sf_findings()
        self.assertEqual("table_unverified", found["status"], found)
        self.assertEqual(reason, found["reason"])
        for key in ("hits", "reportable", "carriers", "filtered", "needs_phase", "needs_variant_class"):
            self.assertEqual([], found[key])
        self.assertIn("not a negative result", fmt.acmg_report(found))

    def test_disappeared_vcf_and_unselected_vcf_refuse(self):
        p = self.current(); p.unlink()
        self.refused("source_unavailable")
        with mock.patch.object(genome, "vcf_path", return_value=None):
            self.refused("source_unavailable")

    def test_a_same_build_replacement_and_same_size_edit_refuse(self):
        p = self.current()
        original = p.read_bytes(); st = p.stat()
        p.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
        self.assertEqual(st.st_size, p.stat().st_size)
        self.refused("source_changed")
        p.write_bytes(original)
        self.current()
        new = self.dir / "replacement.vcf.gz"
        new.write_bytes(p.read_bytes()); os.replace(new, p)
        self.refused("source_changed")

    def test_another_path_with_the_same_content_is_not_the_input(self):
        p = self.current()
        other = self.dir / "other.vcf.gz"; other.write_bytes(p.read_bytes())
        with mock.patch.object(genome, "vcf_path", return_value=other):
            self.refused("source_changed")

    def test_selected_sample_changed_or_unknown_refuses(self):
        self.current()
        with mock.patch.object(genome, "samples_of", return_value=["OTHER"]):
            self.refused("sample_changed")
        with mock.patch.object(genome, "sample_index", return_value=None):
            self.refused("sample_changed")
        with mock.patch.object(genome, "sample_index", return_value=2):
            self.refused("sample_changed")

    def test_old_corrupt_and_missing_metadata_do_not_become_a_negative(self):
        self.current()
        p = self.dir / acmg_scan.META_NAME
        for raw in ('{"assembly":"GRCh38"}', '{broken', '[]', '{}'):
            p.write_text(raw, encoding="utf-8")
            self.refused("metadata_unverified")

    def test_a_changed_table_refuses_even_if_the_genome_is_unchanged(self):
        self.current()
        (self.dir / acmg_scan.OUT_NAME).write_text("gene\n", encoding="utf-8")
        self.refused("table_changed")

    def test_a_broken_sidecar_halfway_through_the_read_refuses(self):
        self.current()
        real = acmg_scan.read_meta
        with mock.patch.object(acmg_scan, "read_meta", side_effect=[real(self.dir), None]):
            self.refused("table_changed")

    def test_a_source_changing_after_reading_rows_is_checked_again(self):
        self.current()
        identity = acmg_scan.source_identity(self.dir / "me.vcf.gz")
        with mock.patch.object(acmg_scan, "source_identity", side_effect=[identity, OSError("changed")]):
            self.refused("source_unavailable")

    def test_unreadable_source_and_changing_stat_refuse(self):
        p = self.current()
        with mock.patch.object(acmg_scan, "source_identity", side_effect=OSError("synthetic unavailable")):
            self.refused("source_unavailable")
        with mock.patch.object(Path, "stat", return_value=mock.Mock(st_dev=-1, st_ino=-1,
                                                                   st_size=-1, st_mtime_ns=-1, st_ctime_ns=-1)):
            with self.assertRaises(OSError):
                acmg_scan.source_identity(p)

    def test_atomic_replace_failure_keeps_the_old_table_and_cleans_temp(self):
        self.current()
        path = self.dir / acmg_scan.OUT_NAME
        before = path.read_bytes()
        with mock.patch.object(acmg_scan.os, "replace", side_effect=OSError("synthetic refusal")):
            with self.assertRaises(OSError):
                acmg_scan._atomic_bytes(path, b"new content")
        self.assertEqual(before, path.read_bytes())
        self.assertEqual([], list(self.dir.glob(".acmg-*")))

    def test_windows_uses_change_time_not_creation_time(self):
        import ctypes
        import types
        kernel = mock.Mock()
        def fill(handle, info_class, target, size):
            self.assertEqual((123, 0), (handle, info_class))
            target._obj.ChangeTime = 987654321
            return True
        kernel.GetFileInformationByHandleEx.side_effect = fill
        with mock.patch.dict("sys.modules", {"msvcrt": types.SimpleNamespace(get_osfhandle=lambda fd: 123)}), \
                mock.patch.object(ctypes, "WinDLL", return_value=kernel, create=True), \
                mock.patch.object(ctypes, "get_last_error", return_value=5, create=True):
            self.assertEqual(987654321, acmg_scan._windows_change_time(7))
            kernel.GetFileInformationByHandleEx.side_effect = None
            kernel.GetFileInformationByHandleEx.return_value = False
            with self.assertRaises(OSError):
                acmg_scan._windows_change_time(7)

    def test_table_removed_between_open_and_validation_refuses(self):
        self.current()
        table = self.dir / acmg_scan.OUT_NAME
        content = table.read_bytes()
        metadata = acmg_scan.read_meta(table)
        table.unlink()
        self.assertEqual("table_changed", acmg_scan.table_refusal(
            table, metadata, self.dir / "me.vcf.gz", content))

    def test_failed_flush_preserves_existing_table_and_removes_partial_temp(self):
        self.current()
        path = self.dir / acmg_scan.OUT_NAME
        before = path.read_bytes()
        with mock.patch.object(acmg_scan.os, "fsync", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                acmg_scan._atomic_bytes(path, b"partial new table")
        self.assertEqual(before, path.read_bytes())
        self.assertEqual([], list(self.dir.glob(".acmg-*")))


if __name__ == "__main__":
    unittest.main()
