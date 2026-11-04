"""The mitochondrial conclusion carries its sample, reads and exact allele."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
import time
from unittest import mock

from scholion import mitochondria as mt
from tests.test_every_door_of_the_local_server_answers import _Live


class TestMitochondrialAnalysis(_Live):
    def setUp(self):
        self.bam = Path(self._tmp) / "synthetic.bam"
        self.index = self.bam.with_suffix(".bam.bai")
        self.bam.write_bytes(b"synthetic alignment")
        self.index.write_bytes(b"synthetic index")
        self.result = self._profile / mt.RESULT
        self.result.unlink(missing_ok=True)
        (self._profile / mt.JOB).unlink(missing_ok=True)
        alignment = mock.patch.object(mt, "_alignment", return_value=(self.bam, self.index))
        tools = mock.patch.object(mt, "_tools", return_value=(
            self.bam.parent, {"java": "java", "samtools": "samtools"}, []))
        alignment.start()
        tools.start()
        self.addCleanup(alignment.stop)
        self.addCleanup(tools.stop)

    def test_site_fraction_support_and_unmeasured_depth_stay_separate(self):
        reads = [(1, Counter(A=89, a=95, G=9, g=7)),
                 (2, Counter(A=85, a=95, G=20)),
                 (3, Counter(A=48, a=49, G=1, g=1)),
                 (4, Counter(A=110, a=89, G=1, g=1)),
                 (5, Counter({"A": 90, "a": 90, "A-1N": 11, "a-1n": 9})),
                 (mt.SPACER, Counter(A=200, a=200))]
        ref = "A" * (mt.SPACER - 1) + "N" + "A" * (mt.LENGTH - mt.SPACER)
        with mock.patch.object(mt, "_count_columns", return_value=reads):
            rows, quality, sites, lineage = mt._summarize(self.bam, "MT", ref, {(1, "G"), (2, "G")})
        self.assertEqual([(1, "supported"), (2, "uncertain"), (5, "technical_indel")],
                         [(r["position"], r["status"]) for r in rows])
        self.assertEqual((200, 9, 7, .08), tuple(rows[0][k] for k in (
            "depth", "forward_alt", "reverse_alt", "fraction")))
        self.assertEqual((4, mt.LENGTH - 1, 0), (quality["at_min_depth"], quality["positions"],
                                                quality["minimum_depth"]))
        self.assertEqual([4, 5], sites)
        self.assertEqual([], lineage)
        self.assertEqual("insufficient_coverage",
                         mt._haplogroup("java", self.bam.parent, self.bam.parent, sites, [])["status"])

    def test_preview_requires_boolean_confirmation_and_failed_run_preserves_bytes(self):
        preview = self.json_of("/api/mitochondria")
        self.assertEqual("ready", preview["status"])
        self.assertEqual(preview, self.json_of("/api/mitochondria", data={"confirm": "true"}))
        self.assertFalse(self.result.exists())
        quality = {"positions": mt.LENGTH - 1}
        group = {"name": None, "status": "insufficient_coverage"}
        with (mock.patch.object(mt, "_reference", return_value=("MT", "A" * mt.LENGTH, "md5")),
              mock.patch.object(mt, "_run"),
              mock.patch.object(mt, "_confirmed", return_value=set()),
              mock.patch.object(mt, "_summarize", return_value=([], quality, [], [])),
              mock.patch.object(mt, "_haplogroup", return_value=group),
              mock.patch.object(mt, "_clinvar", return_value={"status": "unavailable", "date": None})):
            saved = self.json_of("/api/mitochondria", data={"confirm": True})
        self.assertEqual("analyzed", saved["status"])
        self.assertTrue(saved["current"])
        self.assertNotIn("source", saved["result"])
        before = self.result.read_bytes()
        with mock.patch.object(mt, "_reference", side_effect=mt.Refused("reference_mismatch")):
            refused = self.json_of("/api/mitochondria", data={"confirm": True})
        self.assertEqual("reference_mismatch", refused["status"])
        self.assertEqual(before, self.result.read_bytes())
        self.index.write_bytes(b"new index")
        historical = self.json_of("/api/mitochondria")
        self.assertFalse(historical["current"])
        self.assertEqual(saved["result"], historical["result"])

    def test_saved_result_can_be_read_without_tools_or_alignment(self):
        with mock.patch.object(mt, "_alignment", return_value=(None, None)):
            self.assertEqual("needs_bam", mt.report()["status"])
        with mock.patch.object(mt, "_alignment", return_value=(self.bam, None)):
            self.assertEqual("needs_index", mt.report()["status"])

    def test_running_tool_can_be_stopped_from_another_request(self):
        self.result.write_bytes(b'{"schema":1,"variants":[]}')
        before = self.result.read_bytes()
        started = self.bam.parent / "tool-started"
        run = mt._run

        def long_tool(_args, work):
            run([sys.executable, "-c",
                 "import pathlib,sys,time; pathlib.Path(sys.argv[1]).touch(); time.sleep(30)",
                 str(started)], work)

        with (mock.patch.object(mt, "_reference", return_value=("MT", "A" * mt.LENGTH, "md5")),
              mock.patch.object(mt, "_run", side_effect=long_tool),
              ThreadPoolExecutor(max_workers=1) as worker):
            pending = worker.submit(self.json_of, "/api/mitochondria", data={"confirm": True})
            try:
                deadline = time.monotonic() + 5
                while not started.is_file() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(started.is_file())
                self.assertEqual("extract", self.json_of("/api/mitochondria")["job"]["stage"])
                self.assertEqual("busy", self.json_of("/api/mitochondria", data={"confirm": True})["status"])
            finally:
                self.json_of("/api/mitochondria", data={"cancel": True})
            self.assertEqual("cancelled", pending.result(timeout=5)["status"])
        self.assertEqual(before, self.result.read_bytes())

    def test_clinvar_update_reuses_saved_calls_but_method_change_requires_bam(self):
        row = mt._row(12, "A", "G", 150, 8, 6, "supported")
        saved = {"schema": mt.SCHEMA, "source": [mt._witness(self.bam), mt._witness(self.index)],
                 "method": mt._method(self.bam.parent), "annotation_source": "earlier",
                 "variants": [row], "quality": {"minimum_depth": 103}, "haplogroup": {"name": "H"}}
        self.result.write_text(json.dumps(saved), encoding="utf-8")
        with (mock.patch.object(mt, "_annotation", return_value="new"),
              mock.patch.object(mt, "_reference_bases", return_value="A" * mt.LENGTH),
              mock.patch.object(mt, "_clinvar", return_value={"status": "matched_locally", "date": None}),
              mock.patch.object(mt, "_analyze", side_effect=AssertionError("BAM re-read"))):
            preview = self.json_of("/api/mitochondria")
            self.assertEqual(["annotation"], preview["freshness_reasons"])
            self.assertFalse(preview["recalculation_required"])
            refreshed = self.json_of("/api/mitochondria", data={"confirm": True})
            self.assertTrue(refreshed["current"])
            result = json.loads(self.result.read_text(encoding="utf-8"))
            self.assertEqual(saved["variants"], result["variants"])
            self.assertEqual(saved["quality"], result["quality"])
            self.assertEqual(saved["haplogroup"], result["haplogroup"])
            with mock.patch.object(mt, "METHOD", mt.METHOD + 1):
                stale = self.json_of("/api/mitochondria")
                self.assertEqual(["method"], stale["freshness_reasons"])
                self.assertTrue(stale["recalculation_required"])
                refused = self.json_of("/api/mitochondria", data={"confirm": True, "annotations_only": True})
                self.assertEqual("source_changed", refused["status"])

    def test_clinvar_joins_by_exact_allele(self):
        try:
            import pysam
        except ImportError:
            self.skipTest("genome extra is unavailable")
        path = self.bam.with_name("clinvar.vcf")
        path.write_text("""##fileformat=VCFv4.2
##reference=GRCh38
##fileDate=2026-01-01
##contig=<ID=MT>
##INFO=<ID=CLNSIG,Number=.,Type=String,Description="Classification">
##INFO=<ID=CLNREVSTAT,Number=.,Type=String,Description="Review">
##INFO=<ID=CLNDN,Number=.,Type=String,Description="Condition">
##INFO=<ID=GENEINFO,Number=1,Type=String,Description="Gene">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
MT\t12\t123\tA\tG\t.\t.\tCLNSIG=Pathogenic;CLNREVSTAT=reviewed_by_expert_panel;CLNDN=Synthetic;GENEINFO=MT-ND1:1
""", encoding="ascii")
        indexed = pysam.tabix_index(str(path), preset="vcf", force=True)
        variants = [mt._row(12, "A", "G", 150, 8, 6, "supported"),
                    mt._row(12, "A", "T", 150, 8, 6, "supported")]
        with mock.patch("scholion.coverage.clinvar_path", return_value=indexed):
            outcome = mt._clinvar(variants, "A" * mt.LENGTH)
        self.assertEqual({"status": "matched_locally", "date": "2026-01-01"}, outcome)
        self.assertEqual(3, variants[0]["clinvar"]["stars"])
        self.assertIsNone(variants[1]["clinvar"])
        self.assertTrue(mt._review_candidate(variants[0]))
        self.assertFalse(mt._review_candidate({**variants[0], "status": "uncertain"}))
