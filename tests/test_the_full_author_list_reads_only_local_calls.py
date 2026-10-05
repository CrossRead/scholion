"""All intake rows stay visible; a positive reading is not a conclusion."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import support
from scholion import core, genome, format as fmt, mcp_server
from scholion.engine import panel_intake as PC, system_panels as SP


class TestIntakeReadings(unittest.TestCase):
    def test_unavailable_input_keeps_every_row_and_names_indels(self):
        with mock.patch.object(genome, "available", return_value={"ready": False}), \
                mock.patch.object(core, "profile_genotypes", return_value={}), \
                mock.patch.object(genome, "_gt_at", side_effect=AssertionError("must not read")):
            r = SP.system("author_list", "clinician")
        self.assertTrue(r["patient_readings"])
        self.assertFalse(r["reference_only"])
        self.assertEqual(195, len(r["positions"]))
        self.assertEqual(0, r["counts"]["read"])
        self.assertTrue(all(not p["text"] and p["reading"]["genotype"] is None for p in r["positions"]))
        rows = {p["rsid"]: p for p in r["positions"]}
        for rs in ("rs1587874400", "rs1587875298", "rs587776856", "rs1799768"):
            self.assertEqual("indel_unsupported", rows[rs]["reading"]["reason"])
        self.assertEqual(5, sum(bool(p["author_note"]) for p in r["positions"]))
        self.assertTrue(any(p["value_only"] for p in r["positions"]))
        self.assertIn(r["reading_note"], fmt.system_report(r))
        self.assertEqual({p["rsid"] for p in r["positions"]},
                         {p["rsid"] for g in r["genes"] for p in g["positions"]})
        self.assertTrue(all(p["reading"] for g in r["genes"] for p in g["positions"]))

    def test_reference_and_patient_register_do_not_open_any_genome(self):
        with mock.patch.object(genome, "available", side_effect=AssertionError("reference only")):
            r = SP.system("author_list", "patient")
            self.assertTrue(r["reference_only"])
            self.assertTrue(all("reading" not in p for p in r["positions"]))
            self.assertEqual("unknown_register", SP.system("author_list", "wrong")["status"])

    def test_only_called_values_survive_and_quality_is_not_lost(self):
        loc = {"chrom": "1", "pos": 123, "ref": "A", "alt": "G"}
        for conf in ("called", "confirmed_ref", "called_array", "assumed_ref", "low_depth", None):
            with self.subTest(conf=conf), \
                    mock.patch.object(genome, "resolve_rsid", return_value=loc) as resolve, \
                    mock.patch.object(genome, "_gt_at", return_value={
                        "confidence": conf, "genotype": "AG", "depth": 0,
                        "source": "synthetic", "depth_unverified": True}):
                r = PC._intake_reading("rs123", {"ready": True})
            resolve.assert_called_once_with("rs123", allow_network=False)
            read = conf in ("called", "confirmed_ref", "called_array")
            self.assertEqual(read, r["read"])
            self.assertEqual("AG" if read else None, r["genotype"])
            self.assertEqual(0, r["depth"])
            self.assertEqual({"depth_unverified": True}, r["quality"])

    def test_resolution_failure_indel_and_read_error_never_become_reference(self):
        for loc, reason in ((None, "position_not_resolved"),
                            ({"ref": "AT", "alt": "A"}, "indel_unsupported")):
            with mock.patch.object(genome, "resolve_rsid", return_value=loc), \
                    mock.patch.object(genome, "_gt_at", side_effect=AssertionError("not readable")):
                self.assertEqual(reason, PC._intake_reading("rs123", {"ready": True})["reason"])
        loc = {"chrom": "1", "pos": 123, "ref": "A", "alt": "G"}
        for response in ({}, None, OSError("synthetic unreadable file"),
                         {"confidence": "called", "genotype": None}):
            with mock.patch.object(genome, "resolve_rsid", return_value=loc), \
                    mock.patch.object(genome, "_gt_at", **(
                        {"side_effect": response} if isinstance(response, Exception) else {"return_value": response})):
                r = PC._intake_reading("rs123", {"ready": True})
            self.assertFalse(r["read"])
            self.assertIsNone(r["genotype"])

    def test_a_waiting_position_can_be_read_without_becoming_a_finding(self):
        loc = {"chrom": "1", "pos": 123, "ref": "A", "alt": "G"}
        with mock.patch.object(genome, "available", return_value={"ready": True}), \
                mock.patch.object(genome, "resolve_rsid", return_value=loc), \
                mock.patch.object(genome, "_gt_at", return_value={
                    "confidence": "called", "genotype": "AG", "depth": 20,
                    "source": "synthetic", "low_depth": False}):
            r = PC.author_readings()
        waiting = next(p for p in r["positions"] if p["disposition"] == "waiting" and p["reading"]["read"])
        self.assertTrue(waiting["reason"])
        self.assertTrue(waiting["task"])
        self.assertNotIn("findings", waiting)
        self.assertEqual({}, waiting["text"])
        self.assertEqual(191, r["counts"]["read"])
        self.assertIn("AG", fmt.system_report(r))
        self.assertIn("depth_unverified", fmt.panel_report({**r, "genes": [{"gene": "SYNTHETIC",
            "positions": [{**waiting, "reading": {**waiting["reading"],
                           "quality": {"depth_unverified": True}}}]}]}))

    def test_cli_and_json_preserve_the_complete_list(self):
        for lang in ("en", "ru"):
            code, out, err = support.run(["system", "author_list", "--register", "clinician", "--lang", lang, "--json"])
            self.assertEqual(0, code, err)
            r = json.loads(out)
            self.assertEqual(195, len(r["positions"]))
            self.assertTrue(r["patient_readings"])
            self.assertEqual(sum(p["reading"]["read"] for p in r["positions"]), r["counts"]["read"])
            text = fmt.system_report(r)
            self.assertNotIn("⟦", text)

    def test_mcp_returns_the_same_reading_list_and_qualifications(self):
        from scholion import ouroboros_tools
        ouroboros_tools.unpin_session()
        self.addCleanup(ouroboros_tools.unpin_session)
        with mock.patch.object(genome, "available", return_value={"ready": False}):
            r = mcp_server.call_tool("sch_system", {"key": "author_list", "register": "clinician"},
                                     version="2025-06-18")
        self.assertFalse(r.get("isError"), r)
        text = "\n".join(c.get("text", "") for c in r["content"])
        self.assertIn("rs1799768", text)
        self.assertIn("rs1801282", text)

    def test_profile_values_keep_their_source_without_pretending_to_be_file_calls(self):
        recorded = {"genotype": "AG", "source": "synthetic-profile.json"}
        for loc in (None, {"ref": "A", "alt": "G"}):
            with mock.patch.object(genome, "resolve_rsid", return_value=loc):
                r = PC._intake_reading("rs123", {"ready": False}, recorded=recorded)
            self.assertTrue(r["read"])
            self.assertEqual("AG", r["genotype"])
            self.assertEqual("profile", r["confidence"])
            self.assertIn("synthetic-profile.json", r["message"])
            self.assertIsNone(r["depth"])
            self.assertTrue(r["reader_refusal"])
            self.assertEqual({}, r["quality"])
        with mock.patch.object(genome, "available", return_value={"ready": False}), \
                mock.patch.object(core, "profile_genotypes", return_value={"rs1801282": recorded}):
            r = PC.author_readings()
        self.assertEqual(1, r["counts"]["read"])
        self.assertIn("synthetic-profile.json", fmt.system_report(r))
        with mock.patch.object(genome, "resolve_rsid", return_value={"ref": "A", "alt": "G"}), \
                mock.patch.object(genome, "_gt_at", return_value={"confidence": "called", "genotype": "GG"}):
            r = PC._intake_reading("rs123", {"ready": True}, recorded=recorded)
        self.assertEqual("GG", r["genotype"])
        self.assertEqual("called", r["confidence"])
        with mock.patch.object(genome, "resolve_rsid", return_value=None):
            for bad in ({"genotype": "AG"}, {"source": "x"}, {}):
                self.assertFalse(PC._intake_reading("rs123", {"ready": False}, recorded=bad)["read"])

    def test_a_real_synthetic_vcf_read_changes_with_the_selected_sample(self):
        from tests.test_a_file_without_an_index_is_still_a_file import bgzf, vcf_text, APOE38
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            vcf = root / "synthetic.vcf.gz"
            vcf.write_bytes(bgzf(vcf_text([
                ["19", str(APOE38[1]), "rs429358", "T", "C", "50", "PASS", ".", "GT:DP", "0/1:25", "1/1:30"]
            ], samples=("FIRST", "SECOND"))))
            with mock.patch.dict(os.environ, {"SCHOLION_GENOME_DIR": str(root),
                       "SCHOLION_GENOME_VCF": str(vcf), "SCHOLION_CACHE_DIR": str(root / "cache"),
                       "SCHOLION_OFFLINE": "1", "SCHOLION_GENOME_ENGINE": ""}):
                genome.samples_of.cache_clear()
                self.addCleanup(genome.samples_of.cache_clear)
                for sample, gt in (("FIRST", "TC"), ("SECOND", "CC")):
                    with mock.patch.dict(os.environ, {"SCHOLION_GENOME_SAMPLE": sample}):
                        r = PC._intake_reading("rs429358", genome.available())
                        self.assertTrue(r["read"], r)
                        self.assertEqual(gt, r["genotype"])


if __name__ == "__main__":
    unittest.main()
