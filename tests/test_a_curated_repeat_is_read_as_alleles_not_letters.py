"""An explicitly curated insertion is read, but absence never gives a repeat count."""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401
from scholion import genome, indel_genotype, linear


class CuratedRepeat(unittest.TestCase):
    def setUp(self):
        self.loc = genome.resolve_rsid("rs1799762", allow_network=False)
        self.assertIsNotNone(self.loc)

    def row(self, pos=None, ref="T", alt="TG", gt="0/1", depth="20", filt="PASS", info="."):
        return ["7", str(pos or self.loc["pos"]), "rs1799762", ref, alt, "30", filt, info,
                "GT:DP", "1/1:99", gt+":"+depth]

    def read(self, rows, assembly="GRCh38", sample=1, unreadable=False, loc=None):
        with mock.patch.object(genome, "vcf_path", return_value="synthetic.vcf.gz"), \
                mock.patch.object(genome, "file_unreadable", return_value=unreadable), \
                mock.patch.object(genome, "sample_index", return_value=sample), \
                mock.patch.object(genome, "assembly_of", return_value=assembly), \
                mock.patch.object(genome, "_query_region_range", side_effect=rows if isinstance(rows, Exception) else None,
                                  return_value=rows), \
                mock.patch.object(genome, "_mark_depth_unverified"):
            return genome._gt_at(loc or self.loc)

    def test_selected_sample_all_three_genotypes(self):
        for gt, want in (("0/0", "4G/4G"), ("0/1", "4G/5G"), ("1/1", "5G/5G")):
            with self.subTest(gt=gt):
                r = self.read([self.row(gt=gt)])
                self.assertEqual(r["genotype"], want)
                self.assertEqual(r["confidence"], "called")
                self.assertEqual(r["depth"], 20)

    def test_repeat_padding_and_both_builds(self):
        for assembly, anchor in (("GRCh38", self.loc["pos"]), ("GRCh37", self.loc["pos_grch37"])):
            for offset, ref, alt in ((0, "T", "TG"), (1, "GGGG", "GGGGG"), (3, "G", "GG")):
                with self.subTest(assembly=assembly, offset=offset):
                    r = self.read([self.row(pos=anchor + offset, ref=ref, alt=alt)], assembly=assembly)
                    self.assertEqual(r["genotype"], "4G/5G")
                    self.assertEqual(r["read_pos"], anchor)

    def test_absence_anchor_and_other_insertions_are_not_reference(self):
        for rows in ([], [self.row(alt=".", gt="0/0")], [self.row(alt="<NON_REF>", gt="0/0")],
                     [self.row(alt="TC")], [self.row(ref="C")], [self.row(ref="")],
                     [self.row(pos=self.loc["pos"] - 1)]):
            with self.subTest(rows=rows):
                r = self.read(rows)
                self.assertIsNone(r["genotype"])
                self.assertEqual(r["confidence"], "indel_not_read")

    def test_missing_partial_haploid_and_bad_calls_refuse(self):
        for gt in ("./.", "0/.", "1", "bad", "0/9"):
            with self.subTest(gt=gt):
                self.assertIsNone(self.read([self.row(gt=gt)])["genotype"])
        self.assertEqual(self.read([["7", "bad"]])["confidence"], "malformed_genotype")

    def test_an_unselected_allele_does_not_change_repeat_identity(self):
        r = self.read([self.row(alt="TG,TC", gt="0/1")])
        self.assertEqual(r["genotype"], "4G/5G")
        self.assertEqual(self.read([self.row(alt="TG,TC", gt="0/2")])["confidence"], "alleles_not_comparable")

    def test_conflicting_rows_are_not_one_confirmed_genotype(self):
        self.assertEqual(self.read([self.row(), self.row(gt="1/1")])["confidence"], "alleles_not_comparable")

    def test_quality_flags_are_kept(self):
        r = self.read([self.row(depth="2", filt="LowQual", info="IMPUTED")])
        self.assertTrue(r["low_depth"])
        self.assertTrue(r["filtered"])
        self.assertTrue(r["imputed"])
        self.assertIsNone(self.read([self.row(depth=".")])["depth"])

    def test_duplicate_rows_cannot_upgrade_a_low_quality_observation(self):
        for rows in ([self.row(), self.row(depth="2", filt="LowQual")],
                     [self.row(depth="2", filt="LowQual"), self.row()]):
            self.assertEqual(self.read(rows)["confidence"], "duplicate_repeat_calls")
            self.assertIsNone(self.read(rows)["genotype"])

    def test_missing_sample_build_or_valid_reference_refuses(self):
        for kwargs, why in (({"sample": None}, "sample_not_chosen"),
                            ({"assembly": None}, "no_coordinates_for_assembly"),
                            ({"assembly": "unknown"}, "no_coordinates_for_assembly"),
                            ({"unreadable": True}, "unreadable_file")):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.read([], **kwargs)["confidence"], why)
        loc = dict(self.loc, repeat_call={"reference": "bad", "alleles": {}})
        self.assertEqual(self.read([], loc=loc)["confidence"], "alleles_not_comparable")
        with mock.patch.object(genome, "vcf_path", return_value=None):
            self.assertEqual(indel_genotype.read(self.loc)["confidence"], "unreadable_file")

    def test_reader_failures_are_named(self):
        for error, why in ((genome.RangeNeedsIndex(), "needs_index"),
                           (genome.ContigNotInFile("7"), "contig_not_in_file"),
                           (linear.Unreadable("damaged", "synthetic"), "damaged")):
            with self.subTest(why=why):
                self.assertEqual(self.read(error)["confidence"], why)

    def test_old_identifier_remains_distinct(self):
        self.assertNotEqual(self.loc["rsid"], "rs1799768")
        self.assertEqual(self.loc["repeat_call"]["reference"], "TGGGGA")
