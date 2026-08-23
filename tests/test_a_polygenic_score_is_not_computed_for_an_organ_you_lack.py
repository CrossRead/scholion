"""The polygenic layer: the transport, the choice of model, and who a score is for.

`prs.py` had the lowest reach in the package — 19.2% of 291 lines — and it is not
a peripheral module. It decides WHICH polygenic model is applied to somebody's
genome and therefore which percentile they are shown, and a percentile is the
kind of number people remember and repeat.

Three things are pinned here, and each is a defect this module has already had.

WHO A SCORE IS FOR. This module did not contain the word `sex` anywhere, and a
woman with a VCF was handed a prostate-cancer percentile as an ordinary line of
the report — a number about an organ she does not have, printed with exactly the
confidence of the rest. The guard is symmetric and it also withholds when sex is
not recorded, because guessing is the same failure the other way round.

WHICH MODEL IS TAKEN. The server's own top-ranked model puts a «reliable
percentile» above coverage, and it has returned a genome-wide model matching
about a fifth of the positions. Taking the most-covered one blindly is no better:
among equally covered models there are outliers sitting at percentile 0 or 100.
`_pick_covered` is that judgement, and it was unexercised.

WHAT AN ANSWER IS. The heavy computation happens in a separate process, spoken to
over stdio. Every shape that process can answer in — a structured result, JSON
inside a text block, prose inside a text block, an error flag, an error object,
silence — has to be told apart, because three of them look like «no data» from
here and only one of them is.

No subprocess is started and nothing is installed. `Popen` is replaced by a fake
that answers with lines, and for the report itself the whole client is replaced.
The suite runs with SCHOLION_OFFLINE=1, which this module treats as a refusal to
start the server at all — that is the first test below.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import prs


class FakePipe:
    """stdin: collects what the client wrote. stdout: hands back scripted lines."""

    def __init__(self, lines):
        self.written = []
        self._lines = list(lines)

    # stdin
    def write(self, s):
        self.written.append(s)

    def flush(self):
        pass

    # stdout
    def readline(self):
        return self._lines.pop(0) if self._lines else ""


class FakeProc:
    def __init__(self, lines):
        pipe = FakePipe(lines)
        self.stdin = pipe
        self.stdout = pipe
        self.terminated = False

    def terminate(self):
        self.terminated = True


def rpc(id_, result):
    return json.dumps({"jsonrpc": "2.0", "id": id_, "result": result}) + "\n"


INIT = rpc(1, {"protocolVersion": "2024-11-05"})


def client(*after_init):
    """An `_MCP` talking to a fake process that answers with these lines."""
    proc = FakeProc([INIT, *after_init])
    with mock.patch.object(prs.subprocess, "Popen", return_value=proc), \
            mock.patch("scholion.net.offline", return_value=False):
        return prs._MCP(), proc


class TestTheServerIsNotStartedWhenItMayNotBe(unittest.TestCase):

    def test_offline_is_one_switch_and_it_stops_this_too(self):
        """`uvx` fetches the package from PyPI on first use, so «offline» has to
        mean something here as well — otherwise a single honest switch has an
        exception nobody would guess."""
        with mock.patch("scholion.net.offline", return_value=True):
            with self.assertRaises(prs.PrsUnavailable):
                prs._MCP()

    def test_a_machine_without_uvx_is_told_so_rather_than_crashing(self):
        with mock.patch("scholion.net.offline", return_value=False), \
                mock.patch.object(prs.subprocess, "Popen", side_effect=FileNotFoundError()):
            with self.assertRaises(prs.PrsUnavailable):
                prs._MCP()

    def test_the_package_spec_is_pinned_and_a_strange_one_is_not_run(self):
        """`uvx` runs whatever spec it is handed, so one environment variable
        would otherwise be code execution."""
        for raw in ("just-prs-mcp@0.1.4", "local-build"):
            with mock.patch.dict(os.environ, {"PRS_MCP_PKG": raw}):
                self.assertEqual(raw, prs._prs_pkg())
        for raw in ("evil; rm -rf /", "https://example.com/x.tar.gz", "../../thing", "a b"):
            with self.subTest(raw=raw):
                with mock.patch.dict(os.environ, {"PRS_MCP_PKG": raw}):
                    self.assertEqual(prs._DEFAULT_PKG, prs._prs_pkg(),
                                     "a spec that is not a package name was accepted")


class TestEveryShapeAnAnswerCanTake(unittest.TestCase):

    def test_a_structured_result_is_unwrapped(self):
        m, _ = client(rpc(2, {"structuredContent": {"result": {"score": 1.2}}}))
        self.assertEqual({"score": 1.2}, m.call("compute_prs", {}))

    def test_a_structured_result_without_a_result_key_is_taken_whole(self):
        m, _ = client(rpc(2, {"structuredContent": {"rows": []}}))
        self.assertEqual({"rows": []}, m.call("compute_prs", {}))

    def test_json_inside_a_text_block_is_parsed(self):
        m, _ = client(rpc(2, {"content": [{"type": "text", "text": '{"rows": [1]}'}]}))
        self.assertEqual({"rows": [1]}, m.call("compute_prs", {}))

    def test_prose_inside_a_text_block_comes_back_as_prose(self):
        m, _ = client(rpc(2, {"content": [{"type": "text", "text": "no models"}]}))
        self.assertEqual("no models", m.call("compute_prs", {}))

    def test_a_tool_error_is_raised_and_not_returned_as_emptiness(self):
        """FastMCP marks a refusal with isError. Reading it as an empty result
        would turn «this argument is wrong» into «this person has no risk»."""
        m, _ = client(rpc(2, {"isError": True,
                              "content": [{"type": "text", "text": "unknown tool"}]}))
        with self.assertRaises(RuntimeError) as caught:
            m.call("nope", {})
        self.assertIn("unknown tool", str(caught.exception))

    def test_a_protocol_error_is_raised_with_its_message(self):
        line = json.dumps({"jsonrpc": "2.0", "id": 2,
                           "error": {"message": "bad params"}}) + "\n"
        m, _ = client(line)
        with self.assertRaises(RuntimeError) as caught:
            m.call("compute_prs", {})
        self.assertIn("bad params", str(caught.exception))

    def test_a_server_that_goes_quiet_is_not_waited_on_for_ever(self):
        m, _ = client()          # nothing after the handshake
        with self.assertRaises(prs.PrsUnavailable):
            m.call("compute_prs", {})

    def test_noise_between_the_messages_is_stepped_over(self):
        m, _ = client("not json at all\n", "\n", rpc(2, {"structuredContent": 7}))
        self.assertEqual(7, m.call("compute_prs", {}))

    def test_the_handshake_is_sent_before_anything_is_asked(self):
        m, proc = client(rpc(2, {"structuredContent": 1}))
        m.call("compute_prs", {"x": 1})
        sent = [json.loads(s) for s in proc.stdin.written]
        self.assertEqual("initialize", sent[0]["method"])
        self.assertEqual("notifications/initialized", sent[1]["method"])
        self.assertEqual("tools/call", sent[2]["method"])
        self.assertEqual("compute_prs", sent[2]["params"]["name"])

    def test_closing_ends_the_process(self):
        m, proc = client()
        m.close()
        self.assertTrue(proc.terminated)

    def test_the_transport_check_asks_something_that_needs_no_network(self):
        m, proc = client(rpc(2, {"structuredContent": {"result": {"verdict": "ok"}}}))
        with mock.patch.object(prs, "_MCP", return_value=m):
            got = prs.selftest()
        self.assertTrue(got["ok"])
        self.assertEqual({"verdict": "ok"}, got["assess"])
        self.assertTrue(proc.terminated, "the transport check left a process running")


class TestChoosingWhichModelSpeaks(unittest.TestCase):

    @staticmethod
    def row(rate, reliable=False, quality="High", mass=0.5, name="x"):
        return {"pgs_id": name, "match_rate": rate, "percentile_reliable": reliable,
                "quality_label": quality, "weight_mass_coverage": mass}

    def test_nothing_computed_is_nothing_chosen(self):
        self.assertIsNone(prs._pick_covered([]))

    def test_a_well_covered_model_beats_a_genome_wide_one(self):
        rows = [self.row(0.2, reliable=True, name="wide"), self.row(0.95, name="covered")]
        self.assertEqual("covered", prs._pick_covered(rows)["pgs_id"],
                         "a model matching a fifth of the positions was preferred")

    def test_among_well_covered_models_a_reliable_percentile_wins(self):
        rows = [self.row(0.95, reliable=False, name="a"),
                self.row(0.93, reliable=True, name="b")]
        self.assertEqual("b", prs._pick_covered(rows)["pgs_id"])

    def test_quality_decides_next(self):
        rows = [self.row(0.95, reliable=True, quality="Low", name="low"),
                self.row(0.95, reliable=True, quality="High", name="high")]
        self.assertEqual("high", prs._pick_covered(rows)["pgs_id"])

    def test_weight_mass_decides_after_quality(self):
        rows = [self.row(0.95, reliable=True, mass=0.3, name="thin"),
                self.row(0.95, reliable=True, mass=0.9, name="thick")]
        self.assertEqual("thick", prs._pick_covered(rows)["pgs_id"])

    def test_when_nothing_is_well_covered_the_best_of_a_bad_lot_is_still_named(self):
        """Returning nothing would print «not computed» for a trait that was."""
        rows = [self.row(0.2, name="a"), self.row(0.4, name="b")]
        self.assertEqual("b", prs._pick_covered(rows)["pgs_id"])

    def test_a_quality_label_nobody_knows_ranks_below_the_ones_we_do(self):
        rows = [self.row(0.95, reliable=True, quality="Excellent", name="strange"),
                self.row(0.95, reliable=True, quality="Very Low", name="known")]
        self.assertEqual("known", prs._pick_covered(rows)["pgs_id"])


class TestReadingTheServersOtherAnswers(unittest.TestCase):

    def test_the_parquet_path_is_found_however_it_is_named(self):
        for key in ("genotypes_path", "output_path", "parquet_path", "normalized_path", "path"):
            with self.subTest(key=key):
                self.assertEqual("/tmp/g.parquet", prs._extract_path({key: "/tmp/g.parquet"}))

    def test_a_bare_string_is_a_path_only_if_it_looks_like_one(self):
        self.assertEqual("/tmp/g.parquet", prs._extract_path("/tmp/g.parquet"))
        self.assertIsNone(prs._extract_path("done"))

    def test_a_path_that_is_not_parquet_is_still_taken_on_the_second_pass(self):
        self.assertEqual("/tmp/g.arrow", prs._extract_path({"path": "/tmp/g.arrow"}))

    def test_nothing_recognisable_is_no_path(self):
        self.assertIsNone(prs._extract_path({"status": "ok"}))
        self.assertIsNone(prs._extract_path(None))

    def test_a_number_that_is_not_a_number_becomes_the_default(self):
        self.assertEqual(0.0, prs._num(None))
        self.assertEqual(0.0, prs._num("0.9"), "a numeric string is not a number here")
        self.assertEqual(0.9, prs._num(0.9))
        self.assertEqual(1.0, prs._num(None, 1.0))

    def test_rows_are_read_only_out_of_a_reply_that_has_them(self):
        self.assertEqual([1], prs._rows_of({"rows": [1]}))
        self.assertEqual([], prs._rows_of({"other": 1}))
        self.assertEqual([], prs._rows_of("a sentence"))


class TestWhoAScoreIsFor(unittest.TestCase):

    TRAITS = [{"label": "Prostate cancer", "term": "prostate carcinoma", "applies_to_sex": "male"},
              {"label": "Breast cancer", "term": "breast carcinoma", "applies_to_sex": "female"},
              {"label": "Type 2 diabetes", "term": "type 2 diabetes"}]

    def kept_and_withheld(self, sex):
        with mock.patch("scholion.core.profile_sex", return_value=sex):
            return prs._sex_filtered(self.TRAITS)

    def test_a_trait_for_an_organ_the_person_does_not_have_is_not_scored(self):
        kept, withheld = self.kept_and_withheld("female")
        self.assertEqual(["Breast cancer", "Type 2 diabetes"], [t["label"] for t in kept])
        self.assertEqual(["Prostate cancer"], [w["label"] for w in withheld])
        self.assertEqual("other_sex", withheld[0]["reason"])

    def test_the_guard_works_the_other_way_round_too(self):
        kept, withheld = self.kept_and_withheld("male")
        self.assertEqual(["Prostate cancer", "Type 2 diabetes"], [t["label"] for t in kept])
        self.assertEqual(["Breast cancer"], [w["label"] for w in withheld])

    def test_an_unrecorded_sex_withholds_both_rather_than_guessing_one(self):
        kept, withheld = self.kept_and_withheld(None)
        self.assertEqual(["Type 2 diabetes"], [t["label"] for t in kept])
        self.assertEqual({"sex_not_recorded"}, {w["reason"] for w in withheld})

    def test_what_was_withheld_is_named_rather_than_dropped(self):
        """A trait that vanishes from a panel is indistinguishable from a trait
        that was never in it — which is why the reason travels in the result."""
        _, withheld = self.kept_and_withheld("female")
        self.assertTrue(all(w.get("term") and w.get("applies_to_sex") for w in withheld))


def quiet():
    return contextlib.redirect_stderr(io.StringIO())


class FakeMCP:
    """The whole client, replaced. `answers` maps a tool name to a value or to a
    callable taking the arguments; a value that is an Exception is raised."""

    def __init__(self, answers):
        self.answers = answers
        self.calls = []
        self.closed = False

    def call(self, name, args):
        self.calls.append((name, args))
        a = self.answers.get(name)
        if callable(a):
            a = a(args)
        if isinstance(a, Exception):
            raise a
        return a

    def close(self):
        self.closed = True


class TestTheReportItself(unittest.TestCase):

    TRAIT = [{"label": "Type 2 diabetes", "term": "type 2 diabetes", "efo_id": "EFO_0001360"}]

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="prs-")
        self.vcf = Path(self.tmp) / "genome.vcf.gz"
        self.vcf.write_bytes(b"\x1f\x8b")
        self._male = mock.patch("scholion.core.profile_sex", return_value="male")
        self._male.start()

    def tearDown(self):
        self._male.stop()
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_report(self, answers, **kw):
        """`report` narrates its progress on stderr on purpose — a run over a real
        genome takes minutes and a silent one looks hung. Here it is swallowed:
        a test suite is not the console it was written for."""
        fake = FakeMCP(answers)
        with mock.patch.object(prs, "_MCP", return_value=fake), quiet():
            got = prs.report(str(self.vcf), traits=list(self.TRAIT), **kw)
        return got, fake

    def test_a_vcf_that_is_not_there_is_refused_before_anything_is_started(self):
        fake = FakeMCP({})
        with mock.patch.object(prs, "_MCP", return_value=fake), quiet():
            got = prs.report("/no/such/genome.vcf.gz", traits=list(self.TRAIT))
        self.assertFalse(got["ok"])
        self.assertIn("genome.vcf.gz", got["error"])
        self.assertEqual([], fake.calls, "the server was started for a file that is not there")

    def test_a_panel_filtered_down_to_nothing_is_refused_rather_than_run(self):
        got, fake = self.run_report({}, only=["nothing matches this"])
        self.assertFalse(got["ok"])
        self.assertEqual([], fake.calls)

    def test_only_narrows_the_panel_by_label_or_term(self):
        got, _ = self.run_report(
            {"normalize_vcf": {"genotypes_path": "/tmp/g.parquet"},
             "compute_prs_by_trait": {"rows": [{"pgs_id": "PGS1", "match_rate": 0.95}]}},
            only=["diabetes"])
        self.assertEqual(["Type 2 diabetes"], [t["label"] for t in got["traits"]])

    def test_the_genome_is_normalised_once_and_reused(self):
        got, fake = self.run_report(
            {"normalize_vcf": {"genotypes_path": "/tmp/g.parquet"},
             "compute_prs_by_trait": {"rows": [{"pgs_id": "PGS1", "match_rate": 0.95}]}})
        self.assertTrue(got["ok"])
        self.assertEqual("/tmp/g.parquet", got["genotypes_path"])
        self.assertEqual(1, sum(1 for n, _ in fake.calls if n == "normalize_vcf"))
        args = next(a for n, a in fake.calls if n == "compute_prs_by_trait")
        self.assertEqual("/tmp/g.parquet", args["genotypes_path"],
                         "the normalised file was not reused, so the VCF is parsed again "
                         "for every trait")

    def test_a_normalisation_that_failed_does_not_stop_the_report(self):
        got, _ = self.run_report(
            {"normalize_vcf": RuntimeError("out of disk"),
             "compute_prs_by_trait": {"rows": [{"pgs_id": "PGS1", "match_rate": 0.9}]}})
        self.assertTrue(got["ok"])
        self.assertIsNone(got["genotypes_path"])
        self.assertEqual("ok", got["traits"][0]["status"])

    def test_a_trait_with_no_identifier_is_looked_up_by_name(self):
        got, fake = self.run_report(
            {"normalize_vcf": {"path": "/tmp/g.parquet"},
             "search_traits": {"traits": [{"trait_id": "EFO_9"}]},
             "compute_prs_by_trait": {"rows": [{"pgs_id": "PGS1", "match_rate": 0.9}]}})
        # the trait in TRAIT carries an efo_id, so this one is built without it
        self.assertTrue(got["ok"])

    def test_a_trait_nobody_can_identify_is_reported_as_such(self):
        traits = [{"label": "Something", "term": "something"}]
        fake = FakeMCP({"normalize_vcf": {"path": "/tmp/g.parquet"},
                        "search_traits": {"traits": []}})
        with mock.patch.object(prs, "_MCP", return_value=fake), quiet():
            got = prs.report(str(self.vcf), traits=traits)
        self.assertEqual("trait_not_found", got["traits"][0]["status"])

    def test_a_trait_that_threw_is_a_row_with_an_error_and_not_a_lost_line(self):
        got, _ = self.run_report(
            {"normalize_vcf": {"path": "/tmp/g.parquet"},
             "compute_prs_by_trait": RuntimeError("model missing")})
        self.assertEqual("error", got["traits"][0]["status"])
        self.assertIn("model missing", got["traits"][0]["error"])

    def test_an_older_server_that_rejects_the_extra_arguments_is_asked_again_without_them(self):
        """The optional arguments only exist in newer versions of the server.
        Failing the whole trait because one of them is unknown would make a new
        default break every older installation."""
        seen = []

        def answer(args):
            seen.append(dict(args))
            if "profile" in args:
                raise RuntimeError("compute_prs_by_trait() got an unexpected keyword argument")
            return {"rows": [{"pgs_id": "PGS1", "match_rate": 0.95}]}

        got, _ = self.run_report(
            {"normalize_vcf": {"path": "/tmp/g.parquet"}, "compute_prs_by_trait": answer},
            profile="all")
        self.assertEqual("ok", got["traits"][0]["status"])
        self.assertEqual(2, len(seen), "the retry without the optional arguments did not happen")
        self.assertNotIn("profile", seen[1])

    def test_the_best_covered_model_is_taken_when_that_was_asked_for(self):
        rows = [{"pgs_id": "wide", "match_rate": 0.2, "percentile_reliable": True},
                {"pgs_id": "covered", "match_rate": 0.97}]
        got, _ = self.run_report(
            {"normalize_vcf": {"path": "/tmp/g.parquet"},
             "compute_prs_by_trait": {"rows": rows}}, pick="covered")
        self.assertEqual("covered", got["traits"][0]["chosen"]["pgs_id"])

    def test_by_default_the_servers_own_first_row_is_taken(self):
        rows = [{"pgs_id": "first", "match_rate": 0.2},
                {"pgs_id": "second", "match_rate": 0.97}]
        got, _ = self.run_report(
            {"normalize_vcf": {"path": "/tmp/g.parquet"},
             "compute_prs_by_trait": {"rows": rows}})
        self.assertEqual("first", got["traits"][0]["chosen"]["pgs_id"])

    def test_a_better_covered_fallback_model_replaces_a_poor_one(self):
        got, _ = self.run_report(
            {"normalize_vcf": {"path": "/tmp/g.parquet"},
             "compute_prs_by_trait": {"rows": [{"pgs_id": "poor", "match_rate": 0.3}]},
             "search_scores": {"scores": [{"pgs_id": "PGS999", "variants_number": 4000}]},
             "compute_prs": {"match_rate": 0.92}}, fallback=True)
        self.assertEqual("ok_fallback", got["traits"][0]["status"])
        self.assertEqual("PGS999", got["traits"][0]["fallback"]["pgs_id"])

    def test_a_fallback_that_is_no_better_is_not_taken(self):
        got, _ = self.run_report(
            {"normalize_vcf": {"path": "/tmp/g.parquet"},
             "compute_prs_by_trait": {"rows": [{"pgs_id": "poor", "match_rate": 0.5}]},
             "search_scores": {"scores": [{"pgs_id": "PGS999", "variants_number": 4000}]},
             "compute_prs": {"match_rate": 0.4}}, fallback=True)
        self.assertEqual("ok", got["traits"][0]["status"])
        self.assertNotIn("fallback", got["traits"][0])

    def test_the_report_says_what_it_withheld_and_why(self):
        traits = [{"label": "Breast cancer", "term": "breast carcinoma",
                   "applies_to_sex": "female"},
                  {"label": "Type 2 diabetes", "term": "type 2 diabetes", "efo_id": "EFO_1"}]
        fake = FakeMCP({"normalize_vcf": {"path": "/tmp/g.parquet"},
                        "compute_prs_by_trait": {"rows": [{"pgs_id": "P", "match_rate": 0.9}]}})
        with mock.patch.object(prs, "_MCP", return_value=fake), quiet():
            got = prs.report(str(self.vcf), traits=traits)
        self.assertEqual(["Breast cancer"], [w["label"] for w in got["withheld_by_sex"]])

    def test_the_server_is_closed_even_when_a_trait_fails(self):
        _, fake = self.run_report(
            {"normalize_vcf": {"path": "/tmp/g.parquet"},
             "compute_prs_by_trait": RuntimeError("boom")})
        self.assertTrue(fake.closed, "a process was left running after a failure")


class TestTheFallbackSearch(unittest.TestCase):

    def test_a_search_that_fails_says_so_instead_of_returning_nothing(self):
        fake = FakeMCP({"search_scores": RuntimeError("timeout")})
        got, err = prs._search_scores_fallback(fake, "diabetes", None, "/tmp/x.vcf.gz")
        self.assertIsNone(got)
        self.assertIn("timeout", err)

    def test_a_reply_that_is_not_a_list_of_models_is_refused(self):
        fake = FakeMCP({"search_scores": {"scores": "not a list"}})
        got, err = prs._search_scores_fallback(fake, "diabetes", None, "/tmp/x.vcf.gz")
        self.assertIsNone(got)
        self.assertTrue(err)

    def test_models_too_large_to_cover_are_not_chosen(self):
        fake = FakeMCP({"search_scores": {"scores": [
            {"pgs_id": "huge", "variants_number": 1_000_000},
            {"pgs_id": "tiny", "variants_number": 3}]}})
        got, err = prs._search_scores_fallback(fake, "diabetes", None, "/tmp/x.vcf.gz")
        self.assertIsNone(got)
        self.assertTrue(err)

    def test_the_largest_model_that_can_still_be_covered_is_taken(self):
        fake = FakeMCP({"search_scores": {"scores": [
            {"pgs_id": "small", "variants_number": 100},
            {"pgs_id": "big", "variants_number": 40_000},
            {"pgs_id": "huge", "variants_number": 900_000}]},
            "compute_prs": {"match_rate": 0.9}})
        got, err = prs._search_scores_fallback(fake, "diabetes", "/tmp/g.parquet",
                                               "/tmp/x.vcf.gz")
        self.assertIsNone(err)
        self.assertEqual("big", got["pgs_id"])
        args = next(a for n, a in fake.calls if n == "compute_prs")
        self.assertEqual("/tmp/g.parquet", args["genotypes_path"])

    def test_a_computation_that_fails_is_reported_with_the_model_it_failed_on(self):
        fake = FakeMCP({"search_scores": {"scores": [{"pgs_id": "PGS7", "variants_number": 900}]},
                        "compute_prs": RuntimeError("no weights")})
        got, err = prs._search_scores_fallback(fake, "diabetes", None, "/tmp/x.vcf.gz")
        self.assertIsNone(got)
        self.assertIn("PGS7", err)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
