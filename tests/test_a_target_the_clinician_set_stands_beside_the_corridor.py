"""A target the clinician set stands beside the corridor — and never becomes a flag.

Task 170. The product knew two kinds of «normal»: the corridor printed on the
form and the person's own goal for their metrics. The figure a treating
clinician steers toward at this stage of treatment had nowhere to live, and it
usually lies INSIDE the laboratory corridor: four thyroid markers in range, a
calm system on screen, and a free T4 above the target the clinician had set
that same week. The product was not wrong. It was silent about the number the
treatment is run by.

What is held here, in the order it matters:

  * a target is ENTERED with who set it and when, and refused by name without
    either — a figure with no author would read back as the product's own;
  * a marker the dictionary does not know is refused, with the near misses;
  * the figures convert to the marker's canonical unit, all of them, by the
    unit they were given in;
  * `outside_target` is computed against the latest value and `flag` is NOT —
    the assertion is written so that folding the target into the flag fails it;
  * the report prints the provenance and asks a question rather than issuing
    an instruction;
  * the route that owns the list carries `outside_target`, the command line
    sets, lists and removes, the parity map is whole;
  * and a target lives in its own file, so a re-import of the laboratory
    folder cannot take it with the series it rewrites.

Nothing here touches ./profile: every test pins a temporary copy.
"""
from __future__ import annotations

import json
import shutil
import socket
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

import support
from scholion.engine import targets
from scholion import cli, contract, core, engine, format as fmt, server, store
from scholion.i18n import t as _t


class _Pinned(unittest.TestCase):
    """A copy of the synthetic fixture, pinned for the length of one test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.profile = self.root / "profile"
        shutil.copytree(support.FIXTURE_PROFILE, self.profile)
        self._restore = support.pin_profile(self.profile)
        self._restore_cache = support.pin_cache(self.root / "cache")
        core.reset_cache()

    def tearDown(self):
        self._restore()
        self._restore_cache()
        core.reset_cache()
        self.tmp.cleanup()

    def target_file(self) -> dict:
        p = self.profile / "clinician_targets.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    @staticmethod
    def glucose_target(**kw) -> dict:
        """The fixture's glucose is 5.2 in a corridor of 4.1–6.05: a target of
        4–5 puts the value inside the corridor and above the target, which is
        exactly the case the whole layer was built for."""
        args = dict(low=4.0, high=5.0, unit="mmol/L", set_by="Dr. Fixture",
                    set_on="2026-09-12", subject="owner")
        args.update(kw)
        return store.set_clinician_target("glucose", **args)


class TestATargetNamesWhoSetItAndWhen(_Pinned):

    def test_without_an_author_it_is_refused_by_name_and_nothing_is_written(self):
        r = self.glucose_target(set_by="")
        self.assertFalse(r["ok"])
        self.assertIn("--set-by", r["error"], "the refusal does not name the missing field")
        self.assertFalse((self.profile / "clinician_targets.json").exists())

    def test_without_a_day_it_is_refused_by_name(self):
        for bad in ("", "yesterday", "2026-09", "2026-13-45"):
            with self.subTest(set_on=bad):
                r = self.glucose_target(set_on=bad)
                self.assertFalse(r["ok"])
                self.assertIn("--set-on", r["error"])
        self.assertFalse((self.profile / "clinician_targets.json").exists())

    def test_without_a_figure_it_is_refused(self):
        r = self.glucose_target(low=None, high=None)
        self.assertFalse(r["ok"])
        self.assertIn("--value", r["error"])

    def test_the_provenance_and_the_source_are_stored_with_the_figures(self):
        self.assertTrue(self.glucose_target(note="steady on the current dose")["ok"])
        (entry,) = self.target_file()["targets"]
        self.assertEqual(entry["set_by"], "Dr. Fixture")
        self.assertEqual(entry["set_on"], "2026-09-12")
        self.assertEqual(entry["source"], "clinician")
        self.assertEqual(entry["note"], "steady on the current dose")
        self.assertEqual(entry["subject"], "owner")
        self.assertIn("_meta", self.target_file(), "the file carries no stamp")


class TestTheMarkerMustBeOneTheDictionaryKnows(_Pinned):

    def test_a_misspelling_is_refused_with_the_near_misses(self):
        r = store.set_clinician_target("glocose", low=4.0, high=5.0, unit="mmol/L",
                                       set_by="Dr. Fixture", set_on="2026-09-12",
                                       subject="owner")
        self.assertFalse(r["ok"])
        self.assertIn("glucose", [c["key"] for c in r["candidates"]])
        self.assertFalse((self.profile / "clinician_targets.json").exists())

    def test_a_printed_name_resolves_to_the_key(self):
        r = store.set_clinician_target("Glucose", low=4.0, high=5.0, unit="mmol/L",
                                       set_by="Dr. Fixture", set_on="2026-09-12",
                                       subject="owner")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["marker"], "glucose")


class TestTheFiguresConvertToTheCanonicalUnit(_Pinned):

    def test_every_bound_converts_by_the_unit_it_was_given_in(self):
        r = self.glucose_target(low=72, high=90, unit="mg/dL")
        self.assertTrue(r["ok"], r)
        tg = r["target"]
        self.assertEqual(tg["unit"], "mmol/L")
        self.assertAlmostEqual(tg["low"], 72 * 0.05551, places=2)
        # The second bound used to stay 90 — converted by a factor of one after
        # the first bound had already switched the unit to the canonical one.
        self.assertAlmostEqual(tg["high"], 90 * 0.05551, places=2)

    def test_a_unit_the_marker_does_not_take_is_refused(self):
        r = self.glucose_target(unit="furlongs")
        self.assertFalse(r["ok"])
        self.assertIn("mg/dL", r["error"], "the refusal does not list what is accepted")

    def test_a_known_marker_with_no_unit_is_refused(self):
        r = self.glucose_target(unit=None)
        self.assertFalse(r["ok"])


class TestOutsideTheTargetIsNeverAFlag(_Pinned):

    def test_inside_the_corridor_and_above_the_target(self):
        self.assertTrue(self.glucose_target()["ok"])
        (m,) = engine.analyze_labs(["glucose"])["markers"]
        self.assertTrue(m["outside_target"])
        self.assertEqual(m["target"]["side"], "above")
        self.assertEqual(m["target"]["set_by"], "Dr. Fixture")
        # Revert-proof: the two assertions below fail the day the target is
        # folded into the flag. The corridor calls 5.2 normal, and so does the
        # flag — a target is the frame of a treatment, not a diagnosis.
        self.assertEqual(m["flag"], "ok")
        self.assertFalse(m["abnormal"])

    def test_the_summary_counts_it_without_counting_it_as_abnormal(self):
        self.assertTrue(self.glucose_target()["ok"])
        r = engine.analyze_labs(["glucose"])
        self.assertEqual(r["outside_target_count"], 1)
        self.assertEqual(r["abnormal_count"], 0)

    def test_a_single_figure_is_compared_strictly_and_names_the_side(self):
        """«Free T3 5.0» has no inside; whether 5.1 is «at 5.0» is the
        clinician's tolerance to state as bounds, never this layer's to assume."""
        self.assertTrue(self.glucose_target(low=None, high=None, value=5.5)["ok"])
        (m,) = engine.analyze_labs(["glucose"])["markers"]
        self.assertTrue(m["outside_target"])
        self.assertEqual(m["target"]["side"], "below")
        self.assertEqual(m["flag"], "ok")

    def test_a_marker_with_no_target_says_so_rather_than_saying_false(self):
        (m,) = engine.analyze_labs(["glucose"])["markers"]
        self.assertIsNone(m["target"])
        self.assertIsNone(m["outside_target"])

    def test_the_helper_itself(self):
        self.assertIsNone(engine.labs.outside_target(None, 5.0))
        self.assertIsNone(engine.labs.outside_target({"set_by": "x"}, 5.0))
        self.assertTrue(engine.labs.outside_target({"high": 2.0}, 2.1))
        self.assertFalse(engine.labs.outside_target({"low": 1.0, "high": 2.0}, 2.0))
        self.assertTrue(engine.labs.outside_target({"low": 1.0}, 0.9))


class TestTheReportPrintsTheProvenanceAndAsksAQuestion(_Pinned):

    def test_the_labs_report(self):
        self.assertTrue(self.glucose_target()["ok"])
        text = fmt.labs_report(engine.analyze_labs(["glucose"]))
        self.assertIn("target 4–5", text)
        self.assertIn("set by Dr. Fixture on 2026-09-12", text)
        line = next(l for l in text.splitlines() if "worth discussing" in l)
        self.assertIn("above the target", line)
        self.assertTrue(line.rstrip().endswith("?"), "the question is not asked as one")

    def test_no_question_is_asked_when_the_target_is_met(self):
        self.assertTrue(self.glucose_target(high=6.0)["ok"])
        text = fmt.labs_report(engine.analyze_labs(["glucose"]))
        self.assertIn("set by Dr. Fixture", text)
        self.assertNotIn("worth discussing", text)

    def test_the_target_list_report(self):
        self.assertTrue(self.glucose_target()["ok"])
        text = fmt.targets_report(engine.targets.clinician_targets_view())
        self.assertIn("1 target", text)
        self.assertIn("now 5.2 (2026-07)", text)
        self.assertIn("worth discussing", text)
        self.assertIn("not a deficit", text)

    def test_the_wording_carries_no_instruction(self):
        """The clinical part refuses the imperative: «start», «raise», «stop»."""
        self.assertTrue(self.glucose_target()["ok"])
        text = (fmt.labs_report(engine.analyze_labs(["glucose"]))
                + fmt.targets_report(engine.targets.clinician_targets_view())).lower()
        for word in ("start ", "increase ", "raise ", "stop ", "lower the dose"):
            self.assertNotIn(word, text)


class TestTheCommandLine(_Pinned):

    @staticmethod
    def main(argv) -> tuple:
        """`cli.main` with its output captured, so the suite's own log stays readable."""
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_set_list_remove(self):
        code, out, _ = self.main(["target", "set", "glucose", "--low", "4", "--high", "5",
                                  "--unit", "mmol/L", "--set-by", "Dr. Fixture",
                                  "--set-on", "2026-09-12"])
        self.assertEqual(code, 0, out)
        self.assertEqual(self.target_file()["targets"][0]["marker"], "glucose")
        code, out, _ = self.main(["target", "list"])
        self.assertEqual(code, 0)
        self.assertIn("Dr. Fixture", out)
        code, bare, _ = self.main(["target"])
        self.assertEqual((code, bare), (0, out), "a bare `target` does not list")
        code, out, _ = self.main(["target", "list", "--json"])
        self.assertEqual(json.loads(out)["targets"][0]["outside_target"], True)
        self.assertEqual(self.main(["target", "remove", "glucose"])[0], 0)
        self.assertEqual(self.target_file()["targets"], [])

    def test_the_command_refuses_a_target_without_provenance(self):
        with self.assertRaises(SystemExit):
            self.main(["target", "set", "glucose", "--low", "4", "--unit", "mmol/L"])
        self.assertFalse((self.profile / "clinician_targets.json").exists())

    def test_a_second_removal_refuses_by_name(self):
        self.assertTrue(self.glucose_target()["ok"])
        self.assertEqual(store.remove_clinician_target("glucose")["removed"], 1)
        r = store.remove_clinician_target("glucose")
        self.assertFalse(r["ok"])
        self.assertIn("glucose", r["error"])

    def test_the_command_is_in_the_contract_where_it_belongs(self):
        self.assertEqual(contract.check_parity(), [])
        self.assertIn("target", contract.WRITES)
        self.assertIn("target", contract.DICTATED)
        self.assertNotIn("target", contract.AUTHORS)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestTheRouteThatOwnsTheList(_Pinned):

    def setUp(self):
        super().setUp()
        self.port = _free_port()
        self.srv = server._Server(("127.0.0.1", self.port), server.Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        for _ in range(50):
            try:
                self.call("/api/ping")
                break
            except Exception:
                time.sleep(0.05)

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def call(self, path, data=None):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body,
                                     method="POST" if body is not None else "GET")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))

    def test_set_read_and_remove_over_http(self):
        r = self.call("/api/targets", {"marker": "glucose", "low": 4, "high": 5,
                                       "unit": "mmol/L", "set_by": "Dr. Fixture",
                                       "set_on": "2026-09-12"})
        self.assertTrue(r["ok"], r)
        d = self.call("/api/targets")
        (row,) = d["targets"]
        self.assertTrue(row["outside_target"])
        self.assertTrue(row["in_corridor"])
        self.assertEqual(row["set_by"], "Dr. Fixture")
        self.assertEqual(d["to_discuss"], ["glucose"])
        # and the labs route carries it beside the corridor, flag untouched
        (m,) = [x for x in self.call("/api/labs")["markers"] if x["key"] == "glucose"]
        self.assertTrue(m["outside_target"])
        self.assertEqual(m["flag"], "ok")
        self.assertTrue(self.call("/api/targets/remove", {"marker": "glucose"})["ok"])
        self.assertEqual(self.call("/api/targets")["targets"], [])

    def test_a_refusal_comes_back_as_a_reason(self):
        r = self.call("/api/targets", {"marker": "glucose", "low": 4, "unit": "mmol/L"})
        self.assertFalse(r["ok"])
        self.assertIn("--set-by", r["error"])


FERRITIN_FORM = """Date,Test,Result,Units,Reference Range
2026-08-20T07:30,Ferritin,31,ng/mL,13-150
"""


class TestATargetSurvivesAReimport(_Pinned):

    def test_the_laboratory_folder_rewrites_the_series_and_not_the_target(self):
        forms = self.root / "forms"
        forms.mkdir()
        (forms / "august.csv").write_text(FERRITIN_FORM, encoding="utf-8")
        r = store.set_clinician_target("ferritin", low=50, unit="ng/mL",
                                       set_by="Dr. Fixture", set_on="2026-09-12",
                                       subject="owner")
        self.assertTrue(r["ok"], r)
        from scholion import ingest_labs
        res = ingest_labs.ingest(str(forms), force=True)
        self.assertGreaterEqual(res.get("points_added", 0), 1, res)
        (entry,) = self.target_file()["targets"]
        self.assertEqual(entry["set_by"], "Dr. Fixture")
        (m,) = engine.analyze_labs(["ferritin"])["markers"]
        self.assertEqual(m["value"], 31)
        self.assertTrue(m["outside_target"], "the re-imported value is not judged by the target")
        self.assertEqual(m["target"]["side"], "below")
        self.assertEqual(m["flag"], "ok")


if __name__ == "__main__":
    unittest.main()


class TestTheOtherRefusalsAreByName(_Pinned):
    """Every way a target can be malformed is refused with its own sentence,
    and none of them writes the file."""

    def test_no_marker_at_all(self):
        out = store.set_clinician_target("  ", low=4.0, high=5.0, unit="mmol/L",
                                         set_by="Dr. Fixture", set_on="2026-09-12")
        self.assertFalse(out["ok"])
        self.assertEqual(_t("store.target_need_marker"), out["error"])
        self.assertEqual({}, self.target_file())

    def test_a_subject_nobody_declared(self):
        out = self.glucose_target(subject="martian")
        self.assertFalse(out["ok"])
        self.assertIn("martian", out["error"])
        self.assertEqual({}, self.target_file())

    def test_a_figure_that_is_not_a_number(self):
        out = self.glucose_target(low=None, high=None, value="about five")
        self.assertFalse(out["ok"])
        self.assertEqual(_t("store.value_not_number"), out["error"])
        self.assertEqual({}, self.target_file())

    def test_a_lower_bound_above_the_upper_one(self):
        out = self.glucose_target(low=5.0, high=4.0)
        self.assertFalse(out["ok"])
        self.assertIn("5", out["error"])
        self.assertIn("4", out["error"])
        self.assertEqual({}, self.target_file())

    def test_removing_when_nothing_was_ever_set(self):
        out = store.remove_clinician_target("glucose")
        self.assertFalse(out["ok"])
        self.assertEqual(_t("store.no_targets_file"), out["error"])


class TestATargetRelayedByTheOwnerClaimsADemonstration(unittest.TestCase):
    """Task 102 holds for a target as it does for a point: the owner's own
    frame of treatment is not written into a fictional person's profile."""

    def test_the_demonstration_is_erased_first_and_the_answer_says_so(self):
        root = Path(tempfile.mkdtemp(prefix="target_claim_"))
        self.addCleanup(shutil.rmtree, root, True)
        code, out, err = support.run(["init", "--demo", "--dir", str(root / "profile")])
        self.assertEqual(0, code, err or out)
        self.addCleanup(support.pin_profile(root / "profile"))
        self.addCleanup(support.pin_cache(root / "cache"))
        res = store.set_clinician_target("glucose", low=4.0, high=5.0, unit="mmol/L",
                                         set_by="Dr. Fixture", set_on="2026-09-12",
                                         subject="owner")
        self.assertTrue(res["ok"], res)
        self.assertTrue(res.get("claimed"), "the erase is reported, not silent")
        labs = json.loads((root / "profile" / "labs.json").read_text(encoding="utf-8")) \
            if (root / "profile" / "labs.json").exists() else {}
        self.assertFalse((labs.get("markers") or {}).get("glucose", {}).get("series"),
                         "the demonstration's series survived the claim")
