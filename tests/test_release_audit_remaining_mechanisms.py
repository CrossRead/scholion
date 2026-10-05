"""The remaining reproducible defects of the release audit, on synthetic inputs."""
from __future__ import annotations

import os
import json
import re
import shutil
import ssl
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import support  # noqa: F401
from scholion import acmg_scan, core, gene_region, genome, ingest_labs, linear, net, ouroboros_tools, phenoage, prs, server, tabixlite
from scholion.engine import panel_genotype, system_panels


class ApoeNeedsTwoConfirmedCalls(unittest.TestCase):
    def test_assumed_reference_does_not_assign_epsilon(self):
        for confidence in (None, "assumed_ref", "not_on_chip", "low_depth"):
            with self.subTest(confidence=confidence), \
                    mock.patch.object(genome, "available", return_value={"ready": True}), \
                    mock.patch.object(genome, "genotype_from_vcf", side_effect=[
                        {"genotype": "TT", "confidence": confidence},
                        {"genotype": "CC", "confidence": "called"}]):
                answer = genome.apoe_status()
                self.assertEqual(answer["status"], "unconfirmed")
                self.assertNotIn("genotype", answer)
                self.assertTrue(answer["message"])

    def test_both_confirmed_calls_keep_the_known_answer(self):
        with mock.patch.object(genome, "available", return_value={"ready": True}), \
                mock.patch.object(genome, "genotype_from_vcf", side_effect=[
                    {"genotype": "TT", "confidence": "confirmed_ref"},
                    {"genotype": "CC", "confidence": "called"}]):
            self.assertEqual(genome.apoe_status()["genotype"], "ε3/ε3")


class RegionUsesTheSelectedSample(unittest.TestCase):
    def report(self, rows, sample=1, kind="missense"):
        loc = {"gene": "SYNTH", "chrom": "chr1", "start": 1, "end": 10,
               "cds": [["chr1", 1, 10]], "strand": "+", "assembly": "GRCh38"}
        def protein(loc, variants, gaps):
            for v in variants:
                v["protein"] = {"kind": kind}
        with mock.patch.object(gene_region.genes, "resolve", return_value=loc), \
                mock.patch.object(genome, "available", return_value={"ready": True}), \
                mock.patch.object(genome, "vcf_path", return_value="synthetic.vcf.gz"), \
                mock.patch.object(genome, "sample_index", return_value=sample), \
                mock.patch.object(genome, "_query_region_range", return_value=rows), \
                mock.patch.object(gene_region, "_protein", side_effect=protein), \
                mock.patch.object(gene_region, "_coverage", return_value={"source": None, "why": "synthetic"}), \
                mock.patch.object(gene_region, "_clinvar_in_region", return_value=[]):
            return gene_region.report("SYNTH", allow_network=False)

    def row(self, gt):
        return ["chr1", "3", ".", "A", "C,G", "30", "PASS", ".", "GT:DP",
                "1/1:50", gt+":20"]

    def test_not_the_first_sample_or_its_unused_alt(self):
        answer = self.report([self.row("0/2")])
        rows = answer["variants"]["coding_rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["genotype"], rows[0]["alt"], rows[0]["depth"]), ("0/2", "G", 20))

    def test_reference_homozygotes_are_not_variants(self):
        self.assertEqual(self.report([self.row("0/0")])["variants"]["total"], 0)

    def test_partial_and_invalid_calls_are_named_not_counted(self):
        for gt in ("./.", "0/.", "0/9", "bad"):
            with self.subTest(gt=gt):
                r = self.report([self.row(gt)])
                self.assertEqual(r["variants"]["total"], 0)
                self.assertIsNone(r["variants"]["consequential"])
                self.assertTrue(r["gaps"])

    def test_missing_sample_refuses_without_counts(self):
        r = self.report([self.row("0/1")], sample=None)
        self.assertEqual(r["reason"], "sample_not_selected")
        self.assertNotIn("variants", r)

    def test_uncomputed_proteins_are_not_zero(self):
        for kind in ("error", "reference_mismatch", "not_substitution", "not_coding"):
            with self.subTest(kind=kind):
                self.assertIsNone(self.report([self.row("0/1")], kind=kind)["variants"]["consequential"])

    def test_a_malformed_row_is_a_refusal_not_a_zero(self):
        r = self.report([["chr1", "bad"]])
        self.assertEqual(r["reason"], "malformed_row")
        self.assertNotIn("variants", r)

    def test_known_consequence_classes_are_computed(self):
        for kind in ("nonsense", "start_lost", "stop_lost"):
            with self.subTest(kind=kind):
                self.assertEqual(self.report([self.row("0/1")], kind=kind)["variants"]["consequential"], 1)


class DiagnosticTLSIsNotSilentlyBypassed(unittest.TestCase):
    def check(self, error, allow=False):
        opener = mock.Mock()
        opener.open.side_effect = error
        with mock.patch.object(net, "offline", return_value=False), \
                mock.patch.object(net, "insecure_allowed", return_value=allow), \
                mock.patch.object(net, "_diag_opener", return_value=opener) as make:
            result = net.diagnose()
            return result, make.call_count

    def test_certificate_failure_is_one_verified_attempt_by_default(self):
        result, count = self.check(urllib.error.URLError(ssl.SSLCertVerificationError("certificate")))
        self.assertFalse(result["ok"])
        self.assertEqual(count, 1)

    def test_only_an_opted_in_certificate_failure_retries(self):
        _, count = self.check(urllib.error.URLError(ssl.SSLCertVerificationError("certificate")), allow=True)
        self.assertEqual(count, 2)
        for error in (TimeoutError("timeout"), urllib.error.URLError("DNS"),
                      urllib.error.HTTPError("https://example.invalid", 500, "failed", {}, None)):
            with self.subTest(error=type(error).__name__):
                self.assertEqual(self.check(error, allow=True)[1], 1)


class SourceAndDrawIdentity(unittest.TestCase):
    def test_equivalent_padded_acmg_alleles_match(self):
        self.assertEqual(acmg_scan._variant_key("chr1", "10", "AC", "AT"),
                         acmg_scan._variant_key("1", "11", "C", "T"))
        self.assertNotEqual(acmg_scan._variant_key("1", "10", "A", "C"),
                            acmg_scan._variant_key("1", "10", "A", "G"))

    def test_a_record_with_no_coordinate_alleles_is_not_comparable(self):
        r = panel_genotype._from_profile({"genotype": "A/A", "source": "synthetic report"}, "A")
        self.assertFalse(r["read"])
        self.assertEqual(r["why"], "genotype_not_comparable")

    def test_a_marker_without_conversion_tables_refuses_foreign_units(self):
        self.assertEqual(ingest_labs._row_unit({"unit": "ng/mL"}, "5 mmol/l"), ("refused", "mmol/L"))
        self.assertIsNone(ingest_labs._row_unit({"unit": "ng/mL"}, "5 ng/ml"))

    def test_age_is_at_draw_not_today(self):
        self.assertEqual(core.age_from({"birth_date": "2000-10-20"}, on="2018-10-19"), 17)
        self.assertEqual(core.age_from({"birth_date": "2000-10-20"}, on="2018-10-20"), 18)
        self.assertIsNone(core.age_from({"birth_date": "2000-10-20"}, on=""))

    def test_unknown_demographics_do_not_select_labelled_intervals(self):
        self.assertFalse(ingest_labs._row_fits("18-25 лет: 10 - 20", "male", None))
        self.assertFalse(ingest_labs._row_fits("Мужчины: 10 - 20", None, 40))
        self.assertTrue(ingest_labs._row_fits("10 - 20", None, None))

    def test_a_birth_date_after_draw_date_is_not_a_clock(self):
        stamps = ingest_labs._form_stamps("Дата забора 22.05.2018 01.01.1970")
        self.assertNotIn("2018-05-22T01:01", stamps)
        self.assertIn("2018-05-22T10:08", ingest_labs._form_stamps("Дата забора 22.05.2018 10:08"))

    def test_table_boundaries_and_printed_flags_survive(self):
        markers = {"ferritin": {"unit": "ng/mL"}}
        text = "Date,Test,Result,Units\n2018-05-22,Ferritin,<5.9,ng/mL\n2018-05-23,Ferritin,5.9 H,ng/mL\n2018-05-24,Ferritin,\"1,250\",ng/mL\n"
        r = ingest_labs.parse_table(text, markers)
        self.assertEqual([p["value"] for p in r["points"]], [5.9, 5.9])
        self.assertEqual(r["points"][0]["censored"], "<")
        self.assertEqual(r["refused"][0]["row"], 4)

    def test_an_index_older_than_the_source_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "synthetic.vcf.gz"
            source.write_bytes(b"synthetic")
            index = Path(str(source)+".tbi")
            index.write_bytes(b"index")
            os.utime(index, ns=(1, 1))
            with self.assertRaisesRegex(ValueError, "predates"):
                tabixlite._index(str(source))

    def test_prs_constraints_are_unique_private_files(self):
        a, b = prs._constraint_file(), prs._constraint_file()
        try:
            self.assertNotEqual(a, b)
            self.assertEqual(a.read_text(encoding="utf-8"), "".join(c+"\n" for c in prs.PRS_CONSTRAINTS))
            if os.name != "nt":
                self.assertEqual(a.stat().st_mode & 0o777, 0o600)
        finally:
            a.unlink()
            b.unlink()


class CompositeUsesOneDraw(unittest.TestCase):
    def labs(self, split):
        return {"markers": {phenoage.LABS_KEYS[k][0]: {"series": [
            {"date": "2026-01-01T10:00" if not split or i < 5 else "2026-01-20T10:00", "value": 1.0}]}
            for i, k in enumerate(phenoage.REQ)}}

    def test_a_complete_month_of_different_draws_is_incomplete(self):
        with mock.patch.object(core, "labs", return_value=self.labs(True)):
            values, missing, used = phenoage.collect_panel("2026-01")
            self.assertTrue(missing)
            self.assertLess(len(values), len(phenoage.REQ))

    def test_two_draws_on_one_day_are_not_joined(self):
        data = self.labs(True)
        for marker in data["markers"].values():
            for point in marker["series"]:
                if point["date"].startswith("2026-01-20"):
                    point["date"] = "2026-01-01T18:00"
        with mock.patch.object(core, "labs", return_value=data):
            self.assertTrue(phenoage.collect_panel("2026-01")[1])

    def test_a_complete_single_draw_is_selected_with_its_full_stamp(self):
        with mock.patch.object(core, "labs", return_value=self.labs(False)):
            self.assertFalse(phenoage.collect_panel("2026-01")[1])
            self.assertEqual(phenoage._selected_draw("2026-01"), "2026-01-01T10:00")

    def test_a_legacy_month_is_not_proof_of_a_single_draw(self):
        data = self.labs(False)
        for marker in data["markers"].values():
            marker["series"][0]["date"] = "2026-01"
        with mock.patch.object(core, "labs", return_value=data):
            r = phenoage.compute_panel("2026-01", age=40)
            self.assertEqual(r["error"], "draw_unknown")
            self.assertFalse(phenoage.panels_overview()["panels"][0]["complete"])

    def test_a_guessed_or_invalid_date_cannot_establish_one_draw(self):
        for stamp, source in (("2026-01-99", "form"), ("2026-01-01T10:00", "filename"),
                              ("2026-01-01T10:00", "ordered")):
            data = self.labs(False)
            for marker in data["markers"].values():
                for point in marker["series"]:
                    point.update(date=stamp, date_source=source)
            with mock.patch.object(core, "labs", return_value=data):
                self.assertTrue(phenoage.collect_panel("2026-01")[1])


class CrossPanelRouteInputs(unittest.TestCase):
    def test_existing_calls_are_observed_without_importing_a_clinical_sentence(self):
        from scholion.engine import route_dependencies, routes
        rules = [{"system": "target", "trigger": {"markers": ["m"], "direction": "high"},
                  "depends_on": {"positions": ["rs1"], "genes": ["GA", "GB"]}}]
        observed = [{"unit": "position", "rsid": "rs1", "read": True, "state": "het", "text": "Do not import"},
                    {"unit": "gene", "gene": "GA", "read": True, "carrier": True},
                    {"unit": "gene", "gene": "GB", "read": False, "carrier": False}]
        with mock.patch.object(routes, "routes_book", return_value={"rules": rules}), \
                mock.patch.object(system_panels, "domains", return_value=[{"key": "target"}, {"key": "source"}, {"key": "other"}]), \
                mock.patch.object(system_panels, "_curated", return_value={"systems": {"source": {"positions": [{"rsid": "rs1"}]}}}), \
                mock.patch.object(system_panels, "_base_rows", side_effect=lambda key: {"rows": [{"gene": "GA"}, {"gene": "GB"}] if key == "source" else []}), \
                mock.patch.object(system_panels, "_genetics_layer", return_value={"rows": observed}) as read:
            result = route_dependencies._observe("target", {"m": {"flag": "high"}}, [])
            self.assertEqual(len(result), 3)
            self.assertNotIn("text", result[0])
            self.assertEqual(routes._genotype_holds(rules[0]["depends_on"], result), ["rs1", "GA"])
            self.assertEqual(routes._unobserved_dependencies(rules[0]["depends_on"], result), ["GB"])
            read.assert_called_once()
            self.assertEqual(route_dependencies._observe("target", {"m": {"flag": "normal"}}, []), [])
            self.assertEqual(route_dependencies._observe("unrelated", {"m": {"flag": "high"}}, []), [])
            self.assertEqual(route_dependencies._observe("target", {"m": {"flag": "high"}}, observed), observed)

    def test_medication_dependencies_are_not_loaded_without_the_trigger(self):
        from scholion.engine import route_dependencies, routes
        rule = {"system": "target", "trigger": {"medications": ["synthetic"]},
                "depends_on": {"positions": ["rs1"]}}
        with mock.patch.object(routes, "routes_book", return_value={"rules": [rule]}), \
                mock.patch.object(core, "medication_names", return_value=[]), \
                mock.patch.object(system_panels, "domains", return_value=[]):
            self.assertEqual(route_dependencies._observe("target", {}, []), [])
            with mock.patch.object(core, "medication_names", return_value=["synthetic"]):
                self.assertEqual(route_dependencies._observe("target", {}, []), [])


class TimeLimitedHostDoesNotStartAnUnboundedPass(unittest.TestCase):
    def setUp(self):
        ouroboros_tools.unpin_session()
        self.addCleanup(ouroboros_tools.unpin_session)

    @mock.patch("scholion.container.ensure")
    @mock.patch.object(ingest_labs, "_inputs", return_value={"ok": True})
    def test_ingest_worker_failure_shapes_are_named_not_printed_as_success(self, inputs, ensure):
        for stdout, stderr, expected in (("{", "Synthetic worker error", "Synthetic worker error"),
                                         ("{", "", "⚠️"), (None, "Synthetic error", "Synthetic error"),
                                         ("[]", "", "⚠️"),
                                         ('{"ok":false,"error":"Synthetic refusal"}', "", "Synthetic refusal")):
            with self.subTest(stdout=stdout), mock.patch.object(subprocess, "run",
                    return_value=mock.Mock(stdout=stdout, stderr=stderr)):
                self.assertIn(expected, ouroboros_tools._h_ingest_labs(None, "/synthetic"))
        data = {"ok": False, "errors": ["synthetic.csv"]}
        with mock.patch.object(subprocess, "run", return_value=mock.Mock(stdout=json.dumps(data))), \
             mock.patch.object(ouroboros_tools.fmt, "ingest_labs_report", return_value="Synthetic partial refusal") as render:
            self.assertEqual("Synthetic partial refusal", ouroboros_tools._h_ingest_labs(None, "/synthetic"))
            render.assert_called_once_with(data)

    def test_host_refusal_reaches_plain_and_structured_tools(self):
        from scholion import recompute
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "synthetic.vcf"
            source.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
            def handler(ctx):
                linear.snapshot(str(source))
                return "Synthetic unreachable success"
            def both():
                linear.snapshot(str(source))
                return "Synthetic unreachable success", {"status": "ok"}
            handler.both = both
            run = ouroboros_tools._noted(handler, "sch_overview")
            with mock.patch.object(recompute, "per_call_host", return_value=True), \
                 mock.patch.object(linear, "_lookup_cache", return_value={}), \
                 mock.patch.object(linear, "_pass") as read:
                self.assertIn("⚠️", run(None))
                text, data = run.both()
                self.assertIn("⚠️", text)
                self.assertEqual(("refused", "host_linear"), (data["status"], data["reason"]))
                self.assertNotIn("unreachable success", text)
                read.assert_not_called()

    def test_unrelated_reader_damage_is_not_relabelled_a_host_timeout(self):
        from scholion import recompute
        def handler(ctx):
            raise linear.Unreadable("damaged", "Synthetic damage")
        with mock.patch.object(recompute, "per_call_host", return_value=True):
            run = ouroboros_tools._noted(handler, "sch_overview")
            with self.assertRaises(linear.Unreadable) as caught:
                run(None)
            self.assertEqual("damaged", caught.exception.why)

    def test_an_actual_ingest_worker_writes_only_the_pinned_synthetic_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile, forms = root / "profile", root / "forms"
            profile.mkdir()
            forms.mkdir()
            (forms / "synthetic.csv").write_text(
                "Date,Test,Result,Units,Reference Range\n2026-01-02,Ferritin,20,ng/mL,13-150\n",
                encoding="utf-8")
            restore = support.pin_profile(profile)
            try:
                core.reset_cache()
                result = ouroboros_tools._h_ingest_labs(None, str(forms))
                self.assertNotIn("⚠️", result)
                data = json.loads((profile / "labs.json").read_text(encoding="utf-8"))
                self.assertEqual(data["markers"]["ferritin"]["series"][0]["value"], 20)
            finally:
                restore()
                core.reset_cache()

    def test_first_wrapped_import_names_the_container_without_breaking_the_session(self):
        from scholion import container
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            profile, forms = root / "profile", root / "forms"
            profile.mkdir()
            forms.mkdir()
            (forms / "synthetic.csv").write_text(
                "Date,Test,Result,Units\n2026-01-02,Ferritin,20,ng/mL\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"SCHOLION_PROFILE_DIR": str(profile),
                    "SCHOLION_REPO_DIR": str(root), "SCHOLION_WORKSTATION": str(root / "absent.json")}):
                core.reset_cache()
                self.addCleanup(core.reset_cache)
                self.assertIsNone(container.identity()["id"])
                run = ouroboros_tools._noted(ouroboros_tools._h_ingest_labs, "sch_ingest_labs")
                result = run(None, folder=str(forms))
                cid = container.identity()["id"]
                self.assertTrue(cid)
                self.assertIn(cid, result)
                self.assertEqual(ouroboros_tools._pin().check()["id"], cid)
                self.assertIn(cid, run(None, folder=str(forms)))
                data = json.loads((profile / "labs.json").read_text(encoding="utf-8"))
                self.assertEqual(data["markers"]["ferritin"]["series"][0]["value"], 20)

    def test_refused_worker_inputs_do_not_name_an_unnamed_container(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            profile = root / "profile"
            profile.mkdir()
            with mock.patch.dict(os.environ, {"SCHOLION_PROFILE_DIR": str(profile),
                    "SCHOLION_REPO_DIR": str(root), "SCHOLION_WORKSTATION": str(root / "absent.json")}):
                core.reset_cache()
                self.addCleanup(core.reset_cache)
                run = ouroboros_tools._noted(ouroboros_tools._h_ingest_labs, "sch_ingest_labs")
                for folder in ("", str(root / "missing"), str(profile)):
                    self.assertIn("⚠️", run(None, folder=folder))
                    self.assertFalse((root / "container.json").exists())

    @mock.patch("scholion.container.ensure")
    @mock.patch.object(ingest_labs, "_inputs", return_value={"ok": True})
    def test_ingest_timeout_returns_a_resumable_terminal_command(self, inputs, ensure):
        with mock.patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 105)) as run:
            result = ouroboros_tools._h_ingest_labs(None, "/synthetic folder")
        self.assertEqual(run.call_args.kwargs["timeout"], 105)
        self.assertIn("scholion ingest-labs '/synthetic folder'", result)

    def test_uncached_pass_is_refused_and_not_cached_as_file_damage(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "synthetic.vcf"
            source.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
            with mock.patch.object(linear, "_lookup_cache", return_value={}), \
                    mock.patch.object(linear, "_pass") as read, linear.host_read() as state:
                with self.assertRaises(linear.Unreadable) as refused:
                    linear.snapshot(str(source))
                self.assertEqual(refused.exception.why, "host_linear")
                self.assertTrue(state["refused"])
                read.assert_not_called()
                self.assertIsNone(linear.pass_failure(str(source)))

    def test_a_complete_cached_pass_is_answerable(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "synthetic.vcf"
            source.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")
            with mock.patch.object(linear, "_lookup_cache", return_value={"rows": {}, "variants": 12}), \
                    linear.host_read() as state:
                self.assertEqual(linear.snapshot(str(source))["variants"], 12)
                self.assertFalse(state["refused"])


class InheritanceIsNotAssumed(unittest.TestCase):
    def finish(self, sex, zygosity):
        row = {"gene": "SYNTH", "finding_grade": True, "recessive_only": True,
               "moi_codes": ["XLR"], "coverage": {}}
        hits = {"status": "ok", "by_gene": {"SYNTH": [{"chrom": "X", "pos": 5000000,
                                                      "alt": "G", "zygosity": zygosity}]}}
        with mock.patch.object(system_panels.panel_form, "gene_row", side_effect=lambda gene, row, scan: dict(row)), \
                mock.patch.object(system_panels.panel_form, "bases_read", return_value=(True, None)), \
                mock.patch.object(core, "profile_sex", return_value=sex):
            return system_panels._finish_base_row(row, {"status": "ok"}, hits)

    def test_moderate_relationships_cannot_be_findings(self):
        self.assertNotIn("Moderate", system_panels.FINDING_GRADE)
        self.assertIn("Moderate", system_panels.NOT_A_FINDING)

    def test_female_heterozygote_is_a_carrier_not_a_finding(self):
        r = self.finish("female", "het")
        self.assertTrue(r["carrier"])
        self.assertEqual(r["findings"], 0)

    def test_male_single_copy_is_not_called_carriership(self):
        r = self.finish("male", "hom")
        self.assertFalse(r["carrier"])
        self.assertEqual(r["findings"], 1)

    def test_unknown_sex_and_male_heterozygotes_withhold(self):
        for sex, zygosity in ((None, "het"), (None, "hom"), ("male", "het")):
            with self.subTest(sex=sex, zygosity=zygosity):
                r = self.finish(sex, zygosity)
                self.assertFalse(r["carrier"])
                self.assertEqual(r["findings"], 0)
                self.assertEqual(r["clinvar"]["withheld"], 1)


class ServerIdentity(unittest.TestCase):
    def ping(self, body, content="application/json", app="Scholion/0.6.0"):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.headers = {"Content-Type": content, "Server": app}
        response.read.return_value = body.encode()
        with mock.patch("urllib.request.urlopen", return_value=response):
            return server._already_ours("127.0.0.1", 1521)

    def test_a_foreign_body_that_mentions_scholion_is_not_ours(self):
        self.assertFalse(self.ping("Welcome to Scholion", "text/html", "Other/1"))
        self.assertFalse(self.ping(json.dumps({"app": "Scholion", "ok": True, "version": "old"})))

    def test_the_current_protocol_identity_is_accepted(self):
        self.assertTrue(self.ping(json.dumps({"app": "Scholion", "ok": True, "version": server.VERSION})))


@unittest.skipUnless(shutil.which("node"), "needs Node to execute actual page functions")
class BrowserRefusals(unittest.TestCase):
    def function(self, name):
        page = (support.ROOT / "src/scholion/web/index.html").read_text(encoding="utf-8")
        start = page.index("function " + name + "(")
        end = re.search(r"\n(?:async )?function \w+\(", page[start + 10:])
        return page[start:start + 10 + end.start()] if end else page[start:]

    def run_js(self, script):
        result = subprocess.run([shutil.which("node"), "-e", script], capture_output=True,
                                text=True, stdin=subprocess.DEVNULL, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_region_refusals_keep_the_message_without_variant_counts(self):
        script = "const assert=require('node:assert/strict'); const esc=x=>String(x??''),t=(k,v={})=>k+JSON.stringify(v);\n"
        script += self.function("geneRegionCard") + "\n"
        script += """
for(const status of ['unresolved_gene','no_genome','needs_index','assembly_mismatch','unreadable_file']){
  const html=geneRegionCard({gene:'SYNTH',status,message:'NAMED_REFUSAL <&',searched:['synthetic.gff3'],fix:'FIX'});
  assert.ok(html.includes('NAMED_REFUSAL')); assert.ok(html.includes('FIX'));
  assert.ok(!html.includes('gene.counts'));
}
const html=geneRegionCard({gene:'SYNTH',status:'ok',location:{source:'synthetic annotation'},
 coverage:{why:'NOT_MEASURED'},variants:{total:1,coding:1,consequential:null,coding_rows:[]},
 gaps:[{what:'READ_GAP',fix:'CHECK'}],blind_spots:['NO_CNV']});
for(const text of ['NOT_MEASURED','gene.not_computed','READ_GAP','NO_CNV','synthetic annotation'])assert.ok(html.includes(text));
"""
        self.run_js(script)

    def test_defaults_are_local_dates_on_both_sides_of_utc(self):
        script = "const assert=require('node:assert/strict');\n" + self.function("localDay") + "\n"
        script += """
for(const [zone,stamp,want] of [['America/Los_Angeles','2026-01-01T01:00:00Z','2025-12-31'],
 ['Asia/Tokyo','2026-01-01T20:00:00Z','2026-01-02']]){
 process.env.TZ=zone;assert.equal(localDay(new Date(stamp)),want);
}
"""
        self.run_js(script)
