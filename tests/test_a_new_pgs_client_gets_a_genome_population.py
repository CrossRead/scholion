"""A fresh client's prepared genotypes determine and accompany the PGS panel."""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
from unittest import mock

import support
from pgs_support import calibrated
from scholion import core, engine, population, prs
from scholion.pgs_validation import reference_snapshot


class FreshClient(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.genome = self.root / "genome"
        self.genome.mkdir()
        self.env = mock.patch.dict(os.environ, {
            "SCHOLION_PROFILE_DIR": str(self.profile), "SCHOLION_CACHE_DIR": str(self.root / "cache"),
            "SCHOLION_GENOME_DIR": str(self.genome), "SCHOLION_GENOME_VCF": str(self.genome / "absent.vcf.gz"),
            "SCHOLION_OFFLINE": "0", "SCHOLION_LANG": "en"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(core.reset_cache)
        core.reset_cache()
        self.vcf = self.genome / "scoring.vcf"
        self.vcf.write_text("##fileformat=VCFv4.2\n##reference=GRCh38\n"
                            "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC\n", encoding="utf-8")
        self.calls = []
        self.sidecar = mock.Mock()
        self.sidecar.call.side_effect = self.call
        self.row = calibrated({"pgs_id": "PGS000001", "percentile": 71})
        self.row["reference_panel_ancestry"] = "SAS"
        self.row["reference_validation"]["snapshot_sha256"] = reference_snapshot(self.row)

    def prepare_genotypes(self, number=110):
        rows = ["##fileformat=VCFv4.2", "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC"]
        mapping = {}
        for n in range(number):
            pos = 1 + n * 1_000_000
            mapping[f"1:{pos}"] = f"rs{1000+n}"
            rows.append(f"1\t{pos}\t.\tA\tG\t.\tPASS\t.\tGT:DP\t0/0:30")
        with gzip.open(self.genome / "longevity_sites.vcf.gz", "wt", encoding="utf-8") as stream:
            stream.write("\n".join(rows)+"\n")
        (self.genome / "longevity_rsmap.json").write_text(json.dumps(mapping), encoding="utf-8")

    def frequencies(self, _rs):
        return {p: {"A": 0.8 if p == "SAS" else 0.2, "G": 0.2 if p == "SAS" else 0.8} for p in population.SUPERPOPS}

    def call(self, name, args):
        self.calls.append((name, args))
        if name == "compute_prs_by_trait":
            return {"rows": [dict(self.row)]}
        return dict(self.row, method="reference_panel", reliable=True)

    def run_report(self):
        with mock.patch.object(prs, "_MCP", return_value=self.sidecar):
            return prs.report(str(self.vcf), normalize=False,
                              traits=[{"term": "synthetic trait", "label": "Synthetic trait", "efo_id": "EFO_TEST"}])

    def test_fresh_genotypes_to_automatic_assignment_to_scoring_to_saved_report_to_cli(self):
        self.prepare_genotypes()
        with mock.patch.object(population, "fetch_frequencies", side_effect=self.frequencies) as fetch:
            report = self.run_report()
        self.assertTrue(report["ok"], report)
        self.assertEqual(110, fetch.call_count)
        self.assertEqual("SAS", report["superpopulation"])
        self.assertEqual("genome", report["superpopulation_source"])
        self.assertEqual("SAS", next(a for n, a in self.calls if n == "compute_prs_by_trait")["superpopulation"])
        self.assertTrue(report["traits"][0]["chosen"]["reliable"])
        assignment = json.loads((self.profile / "ancestry_check.json").read_text(encoding="utf-8"))
        self.assertEqual("determined", assignment["status"])
        self.assertEqual("SAS", assignment["verdict_superpop"])
        spec = importlib.util.spec_from_file_location("population_test_builder", support.ROOT / "src/ingest/prs_results_build.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        raw = self.root / "raw.json"
        raw.write_text(json.dumps(report), encoding="utf-8")
        with mock.patch.object(builder, "RESULTS", self.profile / "prs_results.json"), \
             mock.patch.object(builder, "REGISTRY", self.root / "registry.json"):
            builder.main(["prs_results_build.py", str(raw)])
        core.reset_cache()
        result = engine.prs_findings()
        self.assertTrue(result["stats"]["panel_matches_ancestry"])
        self.assertEqual("genome", result["stats"]["superpopulation_source"])
        self.assertFalse(any(c["key"].startswith("panel_") for c in result["method_caveats"]))
        cli = json.loads(subprocess.check_output([sys.executable, "-m", "scholion", "prs", "--json"], env=dict(os.environ, PYTHONPATH=str(support.SRC)), cwd=self.root, stdin=subprocess.DEVNULL))
        self.assertEqual("SAS", cli["stats"]["ancestry_determined"])
        self.assertTrue(cli["stats"]["panel_matches_ancestry"])
        # Once assigned, another calculation does not fetch or repeat analysis.
        with mock.patch.object(population, "fetch_frequencies") as fetch:
            self.assertTrue(self.run_report()["ok"])
            fetch.assert_not_called()

    def test_ambiguous_genome_does_not_silently_score_against_europe(self):
        self.prepare_genotypes()
        same = {p: {"A": 0.5, "G": 0.5} for p in population.SUPERPOPS}
        with mock.patch.object(population, "fetch_frequencies", return_value=same), \
             mock.patch.object(prs, "_MCP") as sidecar:
            report = prs.report(str(self.vcf), traits=[{"term": "test"}])
        self.assertFalse(report["ok"])
        self.assertEqual("ambiguous", report["population_assignment"]["status"])
        self.assertIsNone(core.ancestry()["value"])
        sidecar.assert_not_called()

    def test_missing_or_insufficient_genotypes_refuse_before_network_and_scoring(self):
        for number, expected in ((None, "no_bam"), (99, "insufficient_genotypes")):
            if number:
                self.prepare_genotypes(number)
            with mock.patch.object(population, "fetch_frequencies") as fetch, mock.patch.object(prs, "_MCP") as sidecar:
                report = prs.report(str(self.vcf), traits=[{"term": "test"}])
            self.assertEqual(expected, report["population_assignment"]["status"])
            fetch.assert_not_called()
            sidecar.assert_not_called()

    def test_offline_without_reference_frequencies_does_not_call_network(self):
        self.prepare_genotypes()
        with mock.patch.dict(os.environ, {"SCHOLION_OFFLINE": "1"}), mock.patch.object(population, "fetch_frequencies") as fetch:
            report = self.run_report()
        self.assertFalse(report["ok"])
        self.assertEqual("reference_unavailable", report["population_assignment"]["status"])
        fetch.assert_not_called()

    def test_a_different_sample_is_not_used_to_determine_the_scoring_population(self):
        self.prepare_genotypes()
        self.vcf.write_text(self.vcf.read_text(encoding="utf-8").replace("SYNTHETIC", "OTHER"), encoding="utf-8")
        with mock.patch.object(population, "fetch_frequencies") as fetch, mock.patch.object(prs, "_MCP") as sidecar:
            report = prs.report(str(self.vcf), traits=[{"term": "test"}])
        self.assertEqual("sample_mismatch", report["population_assignment"]["status"])
        fetch.assert_not_called()
        sidecar.assert_not_called()

    def test_an_assignment_is_not_reused_after_its_input_changes(self):
        self.prepare_genotypes()
        with mock.patch.object(population, "fetch_frequencies", side_effect=self.frequencies):
            self.assertTrue(self.run_report()["ok"])
        self.assertEqual("SAS", core.ancestry()["value"])
        self.prepare_genotypes(99)
        core.reset_cache()
        self.assertIsNone(core.ancestry()["value"])
        with mock.patch.object(prs, "_MCP") as sidecar:
            report = prs.report(str(self.vcf), traits=[{"term": "test"}])
        self.assertEqual("insufficient_genotypes", report["population_assignment"]["status"])
        sidecar.assert_not_called()

    def test_cached_public_frequencies_support_a_fresh_offline_assignment(self):
        self.prepare_genotypes()
        cache = core.cache_dir() / "population-frequencies.json"
        cache.parent.mkdir(parents=True)
        cache.write_text(json.dumps({f"rs{1000+n}": self.frequencies("") for n in range(110)}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"SCHOLION_OFFLINE": "1"}), mock.patch.object(population, "fetch_frequencies") as fetch:
            report = self.run_report()
        self.assertTrue(report["ok"], report)
        self.assertEqual("SAS", report["superpopulation"])
        fetch.assert_not_called()

    def connect_genome(self):
        from scholion import store
        with gzip.open(self.genome / "full.vcf.gz", "wt", encoding="utf-8") as stream:
            stream.write(self.vcf.read_text(encoding="utf-8"))
        # The normal product connection, not a direct ancestry-file write.
        os.environ.pop("SCHOLION_GENOME_VCF", None)
        core.reset_cache()
        return store.set_genome_vcf(str(self.genome / "full.vcf.gz"))

    def test_connecting_a_genome_assigns_population_before_any_pgs_run(self):
        self.prepare_genotypes()
        with mock.patch.object(population, "fetch_frequencies", side_effect=self.frequencies):
            connected = self.connect_genome()
        self.assertTrue(connected["ok"])
        self.assertEqual("SAS", connected["population_assignment"]["verdict_superpop"])
        self.assertEqual("SAS", core.ancestry()["value"])
        from scholion import population_preparation
        self.assertEqual("SAS", population_preparation.state()["value"])
        with mock.patch.object(population, "fetch_frequencies") as fetch:
            result = self.run_report()
        fetch.assert_not_called()
        self.assertEqual("SAS", result["superpopulation"])
        # A changed scoring sample is refused even after assignment exists.
        self.vcf.write_text(self.vcf.read_text(encoding="utf-8").replace("SYNTHETIC", "OTHER"), encoding="utf-8")
        with mock.patch.object(prs, "_MCP") as sidecar:
            result = self.run_report()
        sidecar.assert_not_called()
        self.assertEqual("sample_mismatch", result["population_assignment"]["status"])

    def test_a_new_input_with_the_same_sample_name_does_not_inherit_an_old_assignment(self):
        self.prepare_genotypes()
        with mock.patch.object(population, "fetch_frequencies", side_effect=self.frequencies):
            self.connect_genome()
        other = self.genome / "new.vcf.gz"
        with gzip.open(other, "wt", encoding="utf-8") as stream:
            stream.write(self.vcf.read_text(encoding="utf-8"))
        from scholion import store
        with mock.patch.object(population, "fetch_frequencies") as fetch:
            result = store.set_genome_vcf(str(other))
        fetch.assert_not_called()
        self.assertEqual("no_bam", result["population_assignment"]["status"])
        self.assertIsNone(core.ancestry()["value"])
        # A retry must not adopt the old prepared sites merely because the
        # failed connection already saved the new path.
        with mock.patch.object(population, "fetch_frequencies") as fetch:
            retry = store.set_genome_vcf(str(other))
        fetch.assert_not_called()
        self.assertEqual("no_bam", retry["population_assignment"]["status"])
        self.assertIsNone(core.ancestry()["value"])

    def test_the_rsmap_is_part_of_assignment_provenance(self):
        self.prepare_genotypes()
        with mock.patch.object(population, "fetch_frequencies", side_effect=self.frequencies):
            self.connect_genome()
        (self.genome / "longevity_rsmap.json").write_text("{}", encoding="utf-8")
        core.reset_cache()
        self.assertIsNone(core.ancestry()["value"])

    def test_connection_prepares_missing_sites_from_bam_then_assigns_and_scores(self):
        from scholion import bamlite, population_preparation, sites
        self.prepare_genotypes()
        prepared = self.genome / "longevity_sites.vcf.gz"
        payload = prepared.read_bytes()
        mapping = json.loads((self.genome / "longevity_rsmap.json").read_text(encoding="utf-8"))
        prepared.unlink()
        bam = self.root / "reads.bam"
        bam.touch()
        Path(str(bam) + ".bai").touch()
        ref = self.root / "ref.fa"
        ref.touch()
        Path(str(ref) + ".fai").write_text("1\t248956422\t0\t60\t61\n", encoding="utf-8")
        req = {"bam": str(bam), "reference": str(ref), "bcftools": "bcftools", "vcf": None}
        commands = []

        def run(pipeline):
            commands.append(pipeline)
            argv = pipeline[-1]
            if argv[1] == "call":
                self.assertNotIn("-v", argv)
                self.assertIn("FORMAT/DP", pipeline[0])
                Path(argv[argv.index("-o")+1]).write_bytes(payload)
            else:
                Path(argv[-1]+".tbi").touch()
            return {"rc": 0}

        with mock.patch.object(sites, "requirements", return_value=req), \
             mock.patch.object(bamlite, "reference_lengths", return_value={"1": 248956422}), \
             mock.patch.object(population_preparation, "resolve_positions", return_value=mapping), \
             mock.patch.object(sites, "_run_pipeline", side_effect=run), \
             mock.patch.object(population, "fetch_frequencies", side_effect=self.frequencies):
            result = self.connect_genome()
        self.assertEqual("SAS", result["population_assignment"]["verdict_superpop"])
        self.assertEqual(2, len(commands))
        self.assertTrue(prepared.exists())
        self.assertTrue(self.run_report()["ok"])

    def test_reference_build_mismatch_stops_before_any_coordinate_lookup_or_genotyping(self):
        from scholion import bamlite, population_preparation, sites
        bam = self.root / "reads.bam"
        bam.touch()
        Path(str(bam)+".bai").touch()
        ref = self.root / "ref.fa"
        Path(str(ref)+".fai").write_text("1\t249250621\t0\t60\t61\n", encoding="utf-8")
        req = {"bam": str(bam), "reference": str(ref), "bcftools": "bcftools", "vcf": None}
        with mock.patch.object(sites, "requirements", return_value=req), \
             mock.patch.object(bamlite, "reference_lengths", return_value={"1": 248956422}), \
             mock.patch.object(population_preparation, "resolve_positions") as lookup, \
             mock.patch.object(sites, "_run_pipeline") as run:
            result = self.connect_genome()
        self.assertEqual("build_mismatch", result["population_assignment"]["status"])
        lookup.assert_not_called()
        run.assert_not_called()

    def test_changing_the_connected_input_during_assignment_invalidates_the_result(self):
        from scholion import population_preparation
        self.prepare_genotypes()

        def changing_reference(rsid):
            if rsid == "rs1000":
                with self.vcf.open("a", encoding="utf-8") as stream:
                    stream.write("##synthetic_change_during_preparation\n")
            return self.frequencies(rsid)

        with mock.patch.object(population, "fetch_frequencies", side_effect=changing_reference):
            result = population_preparation.prepare(self.vcf)
        self.assertEqual("invalid_genotypes", result["status"])
        self.assertIsNone(result["verdict_superpop"])
        self.assertIsNone(core.ancestry()["value"])

    def test_changed_prepared_sites_during_lookup_do_not_get_a_new_valid_fingerprint(self):
        self.prepare_genotypes()

        def changing_reference(rsid):
            if rsid == "rs1000":
                self.prepare_genotypes(99)
            return self.frequencies(rsid)

        with mock.patch.object(population, "fetch_frequencies", side_effect=changing_reference):
            result = population.determine(self.genome / "longevity_sites.vcf.gz", self.genome / "longevity_rsmap.json")
        self.assertEqual("invalid_genotypes", result["status"])
        self.assertIsNone(result["verdict_superpop"])

    def test_a_population_prepared_on_demand_is_checked_against_the_scoring_sample(self):
        self.prepare_genotypes()
        connected = self.genome / "connected.vcf.gz"
        with gzip.open(connected, "wt", encoding="utf-8") as stream:
            stream.write(self.vcf.read_text(encoding="utf-8"))
        os.environ["SCHOLION_GENOME_VCF"] = str(connected)
        self.vcf.write_text(self.vcf.read_text(encoding="utf-8").replace("SYNTHETIC", "OTHER"), encoding="utf-8")
        core.reset_cache()
        with mock.patch.object(population, "fetch_frequencies", side_effect=self.frequencies), \
             mock.patch.object(prs, "_MCP") as sidecar:
            result = prs.report(str(self.vcf), traits=[{"term": "test"}])
        self.assertEqual("sample_mismatch", result["population_assignment"]["status"])
        sidecar.assert_not_called()

    def test_stale_population_has_a_visible_reason_in_both_languages(self):
        from scholion import i18n, population_preparation
        self.prepare_genotypes()
        with mock.patch.object(population, "fetch_frequencies", side_effect=self.frequencies):
            self.run_report()
        self.prepare_genotypes(99)
        core.reset_cache()
        for lang in ("en", "ru"):
            i18n.set_lang(lang)
            try:
                status = population_preparation.state()
                self.assertIsNone(status["value"])
                self.assertEqual("determined", status["reason"])
                self.assertNotIn("⟦", status["note"])
            finally:
                i18n.set_lang(None)

    def test_cli_connection_prepares_and_exposes_the_population_without_a_pgs_run(self):
        self.prepare_genotypes()
        full = self.genome / "full.vcf.gz"
        with gzip.open(full, "wt", encoding="utf-8") as stream:
            stream.write(self.vcf.read_text(encoding="utf-8"))
        cache = self.root / "cache"
        cache.mkdir()
        (cache / "population-frequencies.json").write_text(json.dumps({f"rs{1000+n}": self.frequencies("") for n in range(110)}), encoding="utf-8")
        env = dict(os.environ, PYTHONPATH=str(support.SRC), SCHOLION_OFFLINE="1")
        env.pop("SCHOLION_GENOME_VCF", None)
        result = json.loads(subprocess.check_output([sys.executable, "-m", "scholion", "choose-genome", str(full), "--json"], env=env, cwd=self.root, stdin=subprocess.DEVNULL))
        self.assertEqual("SAS", result["population_assignment"]["verdict_superpop"])
        status = json.loads(subprocess.check_output([sys.executable, "-m", "scholion", "genome-status", "--json"], env=env, cwd=self.root, stdin=subprocess.DEVNULL))
        self.assertEqual("SAS", status["population"]["value"])

    def test_web_connection_prepares_and_exposes_the_same_shared_population(self):
        from scholion import server
        self.prepare_genotypes()
        full = self.genome / "full.vcf.gz"
        with gzip.open(full, "wt", encoding="utf-8") as stream:
            stream.write(self.vcf.read_text(encoding="utf-8"))
        os.environ.pop("SCHOLION_GENOME_VCF", None)
        srv = server._Server(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            request = urllib.request.Request(base + "/api/choose-genome", data=json.dumps({"path": str(full)}).encode(), headers={"Content-Type": "application/json"})
            with mock.patch.object(population, "fetch_frequencies", side_effect=self.frequencies), urllib.request.urlopen(request, timeout=20) as response:
                result = json.load(response)
            self.assertEqual("SAS", result["population_assignment"]["verdict_superpop"])
            with urllib.request.urlopen(base + "/api/genome-status", timeout=20) as response:
                status = json.load(response)
            self.assertEqual("SAS", status["population"]["value"])
            self.assertEqual("genome", status["population"]["source"])
        finally:
            srv.shutdown()
            srv.server_close()
            thread.join(timeout=5)

    def test_an_unreachable_reference_does_not_repeat_a_timeout_for_every_marker(self):
        self.prepare_genotypes()
        with mock.patch.object(population, "fetch_frequencies", side_effect=OSError("synthetic unavailable")) as fetch:
            result = self.run_report()
        self.assertEqual("reference_unavailable", result["population_assignment"]["status"])
        self.assertEqual(1, fetch.call_count)

    def test_disappearing_prepared_sites_during_lookup_are_a_refusal(self):
        self.prepare_genotypes()

        def disappearing_reference(rsid):
            if rsid == "rs1000":
                (self.genome / "longevity_sites.vcf.gz").unlink()
            return self.frequencies(rsid)

        with mock.patch.object(population, "fetch_frequencies", side_effect=disappearing_reference):
            result = self.run_report()
        self.assertEqual("invalid_genotypes", result["population_assignment"]["status"])
        self.assertIsNone(core.ancestry()["value"])
