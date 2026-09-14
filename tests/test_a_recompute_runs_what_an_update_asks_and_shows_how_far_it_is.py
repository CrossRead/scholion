"""A recompute runs what an update asks, and shows how far it is.

Until 13.09.2026 an update named its recompute steps and ran none of them: a
person copied commands into a terminal, filled in the folder by hand, and
watched a silent process. The genome steps were not even named — after the
locus catalogue grew, a profile read 21 of its 92 radar panel positions as not
read, and nothing said why.

What is held here: the plan joins the journal and the data and judges every
step before anything runs; nothing starts without a confirmation; the progress
is a file a second process can read, with «item i of N» and the time left; a
stop is honoured between items and the steps after it do not run;
a failed step stops the sequence; files a step rewrites are copied into the
archive first; the version is recorded only when nothing is left for a person;
and a job whose process died is reported as interrupted, not as running.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import format as fmt
from scholion import recompute, updates

JOURNAL = """# Changelog

## v9.0.2 — 02.01.2030

### What needs recomputing

**Run `scholion ingest-labs --force <folder of laboratory forms>` — if forms were ingested by an earlier version.**
The folder is read again.

**By hand — if a calcium point sits in the wrong series.**
Remove it.

**Run `scholion something-this-face-does-not-run` — if it applies.**
Run it yourself.

## v9.0.1 — 01.01.2030

### What needs recomputing

**Run `scholion ingest-labs <folder of laboratory forms>` — if forms were ingested.**
Read again.

**Run `scholion ingest-garmin` — if Garmin months were imported.**
Import again.

## v9.0.0 — 01.12.2029

### What needs recomputing

Nothing.
"""

ONLY_RUNNABLE = """## v9.0.2 — 02.01.2030

### What needs recomputing

**Run `scholion ingest-labs --force <folder of laboratory forms>` — if forms were ingested by an earlier version.**
Read again.

**Run `scholion ingest-garmin` — if Garmin months were imported.**
Import again.

## v9.0.0 — 01.12.2029

### What needs recomputing

Nothing.
"""


class _Profile(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="recompute_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.forms = self.root / "forms"
        self.forms.mkdir()
        restore = support.pin_profile(self.profile)
        self.addCleanup(restore)
        env = mock.patch.dict(os.environ, {
            "SCHOLION_REPO_DIR": str(self.root),
            "SCHOLION_ARCHIVE_DIR": str(self.root / "archive"),
            "SCHOLION_GENOME_DIR": str(self.root / "genome"),
            "SCHOLION_GENOME_VCF": str(self.root / "genome" / "no-such.vcf.gz")})
        env.start()
        self.addCleanup(env.stop)
        for patch in (mock.patch.object(updates, "installed", return_value="9.0.2"),
                      mock.patch.object(recompute, "_WRITE_EVERY", 0)):
            patch.start()
            self.addCleanup(patch.stop)
        from scholion import core
        core.reset_cache()
        self.addCleanup(core.reset_cache)

    def write(self, name, data):
        (self.profile / name).write_text(json.dumps(data), encoding="utf-8")

    def name_the_folder(self):
        self.write("sources.json", {"folders": {"labs_docs": str(self.forms)}})

    def steps(self, text=JOURNAL, since="9.0.0"):
        return recompute.plan(since=since, text=text)["steps"]


class TestThePlan(_Profile):

    def test_the_same_command_is_one_step_and_the_rest_are_named(self):
        steps = self.steps()
        labs = [s for s in steps if s.get("key") == "scholion ingest-labs"]
        self.assertEqual(1, len(labs), "two releases asking for one command make one step")
        self.assertEqual(["9.0.1", "9.0.2"], labs[0]["versions"])
        self.assertEqual("scholion ingest-labs --force", labs[0]["command"])
        by_hand = [s for s in steps if s["state"] == "by_hand"]
        self.assertEqual(["if a calcium point sits in the wrong series"], by_hand[0]["conditions"])
        foreign = [s for s in steps if s["state"] == "not_run_here"]
        self.assertEqual("scholion something-this-face-does-not-run", foreign[0]["command"])

    def test_a_step_with_nothing_stored_does_not_apply(self):
        labs = next(s for s in self.steps() if s.get("key") == "scholion ingest-labs")
        self.assertEqual(("not_applicable", "no_file"), (labs["state"], labs["why"]))

    def test_a_step_waits_for_the_folder_it_reads_and_says_which(self):
        self.write("labs.json", {"_meta": {}, "markers": {}})
        labs = next(s for s in self.steps() if s.get("key") == "scholion ingest-labs")
        self.assertEqual(("needs_input", "no_folder"), (labs["state"], labs["why"]))
        self.assertIn("labs_docs", fmt.recompute_why(labs))
        self.name_the_folder()
        labs = next(s for s in self.steps() if s.get("key") == "scholion ingest-labs")
        self.assertEqual("ready", labs["state"])

    def test_a_file_written_by_a_build_that_already_did_it_is_not_rebuilt(self):
        self.write("labs.json", {"_meta": {"engine": "9.0.2"}, "markers": {}})
        self.name_the_folder()
        labs = next(s for s in self.steps() if s.get("key") == "scholion ingest-labs")
        self.assertEqual(("already_current", "written_by"), (labs["state"], labs["why"]))

    def test_the_genome_step_comes_from_the_data_as_well_as_from_a_release(self):
        state = {"status": "missing", "refusal": None, "catalogue_positions": 113}
        with mock.patch("scholion.sites.state", return_value=state):
            (step,) = [s for s in self.steps(text=ONLY_RUNNABLE, since="9.0.2")]
        self.assertEqual(("data", "ready", "sites_missing"), (step["source"], step["state"], step["why"]))
        self.assertIn("113 positions", fmt.recompute_why(step))
        with mock.patch("scholion.sites.state", return_value={**state, "refusal": "no_bam"}):
            (step,) = self.steps(text=ONLY_RUNNABLE, since="9.0.2")
        self.assertEqual(("needs_input", "no_bam"), (step["state"], step["why"]))

    def test_the_acmg_step_waits_for_the_clinvar_file_it_reads(self):
        journal = ONLY_RUNNABLE.replace("**Run `scholion ingest-garmin` — if Garmin months were imported.**",
                                        "**Run `scholion acmg-scan` — if an ACMG table was written.**")
        genome = self.root / "genome"
        genome.mkdir()
        (genome / "acmg_sf_hits.tsv").write_text("gene\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"SCHOLION_CLINVAR_VCF": ""}):
            acmg = next(s for s in self.steps(text=journal) if s.get("key") == "scholion acmg-scan")
            self.assertEqual(("needs_input", "no_clinvar"), (acmg["state"], acmg["why"]))
            (genome / "clinvar.vcf.gz").write_bytes(b"")
            acmg = next(s for s in self.steps(text=journal) if s.get("key") == "scholion acmg-scan")
            self.assertEqual("ready", acmg["state"])

    def test_every_state_renders_in_both_languages(self):
        self.write("labs.json", {"_meta": {}, "markers": {}})
        plan = recompute.plan(since="9.0.0", text=JOURNAL)
        for lang in ("en", "ru"):
            with support.lang(lang) if hasattr(support, "lang") else mock.patch.dict(os.environ, {"SCHOLION_LANG": lang}):
                text = fmt.recompute_plan_report(plan)
            self.assertNotIn("⟦", text, text)


class TestTheRun(_Profile):

    def ready_profile(self):
        self.write("labs.json", {"_meta": {}, "markers": {"old": 1}})
        self.write("wearable_trends.json", {"_meta": {}, "sources": {}})
        self.name_the_folder()

    def test_nothing_starts_without_a_confirmation(self):
        self.ready_profile()
        r = recompute.run(confirm=False, since="9.0.0", text=ONLY_RUNNABLE)
        self.assertEqual((False, "not_confirmed"), (r["started"], r["reason"]))
        self.assertFalse((self.profile / recompute.JOB).exists())

    def test_the_progress_is_a_file_with_the_item_and_the_time_left(self):
        self.ready_profile()
        seen = {}

        def labs(step, tick):
            for i, name in enumerate(("a.pdf", "b.pdf", "c.pdf")):
                tick(i, 3, name)
                if i == 1:
                    seen["job"] = recompute.status()
            tick(3, 3, None)
            return {"ok": True, "files_seen": 3}

        r = recompute.run(confirm=True, since="9.0.0", text=ONLY_RUNNABLE,
                          calls={"scholion ingest-labs": labs,
                                 "scholion ingest-garmin": lambda s, tick: {"ok": True}})
        mid = seen["job"]
        self.assertEqual("running", mid["status"])
        self.assertEqual((1, 3, "b.pdf"), (mid["steps"][0]["done"], mid["steps"][0]["total"],
                                           mid["steps"][0]["item"]))
        self.assertIn("left", mid["steps"][0])
        self.assertIn("1 of 3", fmt.recompute_progress_line(mid, 0))
        self.assertTrue(r["ok"], r)
        self.assertEqual("finished", recompute.status()["status"])
        first = recompute.status()["steps"][0]
        self.assertEqual((3, 3, None), (first["done"], first["total"], first["item"]),
                         "a finished step is shown as finished, not as its last tick")
        backup = Path(r["job"]["backup"])
        self.assertTrue((backup / "labs.json").is_file(), "a rewritten file is archived first")
        self.assertEqual("9.0.2", updates.last_used(), "nothing is left, so the version is recorded")

    def test_data_that_never_recorded_its_version_is_not_marked_done_by_a_genome_step(self):
        """Nothing from the journal was planned, so nothing from it may be claimed."""
        self.ready_profile()
        state = {"status": "missing", "refusal": None, "catalogue_positions": 113}
        with mock.patch("scholion.sites.state", return_value=state):
            r = recompute.run(confirm=True, since=None, text=ONLY_RUNNABLE,
                              calls={"scholion genotype-sites": lambda s, tick: {"ok": True}})
        self.assertEqual("finished", r["job"]["status"])
        self.assertIsNone(updates.last_used())
        self.assertEqual("since_unknown", r["job"]["not_recorded"])
        self.assertIn("--since", fmt.recompute_status_report(r["job"]))

    def test_a_step_left_for_a_person_keeps_the_version_unrecorded(self):
        self.ready_profile()
        r = recompute.run(confirm=True, since="9.0.0", text=JOURNAL,
                          calls={"scholion ingest-labs": lambda s, tick: {"ok": True},
                                 "scholion ingest-garmin": lambda s, tick: {"ok": True}})
        self.assertEqual("finished", r["job"]["status"])
        self.assertIsNone(updates.last_used())
        self.assertIn("by hand", fmt.recompute_status_report(r["job"]))

    def test_a_stop_is_honoured_between_items_and_the_sequence_ends(self):
        self.ready_profile()
        before = (self.profile / "labs.json").read_text(encoding="utf-8")

        def labs(step, tick):
            tick(0, 5, "a.pdf")
            self.assertTrue(recompute.stop()["ok"])
            tick(1, 5, "b.pdf")
            raise AssertionError("the tick after a stop must not return")

        garmin = mock.Mock(return_value={"ok": True})
        r = recompute.run(confirm=True, since="9.0.0", text=ONLY_RUNNABLE,
                          calls={"scholion ingest-labs": labs, "scholion ingest-garmin": garmin})
        self.assertEqual("stopped", r["job"]["status"])
        self.assertEqual(["stopped", "waiting"], [s["state"] for s in r["job"]["steps"]])
        garmin.assert_not_called()
        self.assertEqual(before, (self.profile / "labs.json").read_text(encoding="utf-8"))
        self.assertFalse((self.profile / recompute.STOP).exists())

    def test_a_failed_step_stops_the_steps_after_it(self):
        self.ready_profile()
        garmin = mock.Mock(return_value={"ok": True})
        r = recompute.run(confirm=True, since="9.0.0", text=ONLY_RUNNABLE,
                          calls={"scholion ingest-labs": lambda s, tick: {"ok": True, "errors": ["x.pdf"]},
                                 "scholion ingest-garmin": garmin})
        self.assertEqual("failed", r["job"]["status"])
        garmin.assert_not_called()
        self.assertIsNone(updates.last_used())

    def test_a_second_run_while_one_is_running_is_refused(self):
        self.ready_profile()
        (self.profile / recompute.JOB).write_text(json.dumps(
            {"status": "running", "pid": os.getpid(), "steps": []}), encoding="utf-8")
        r = recompute.run(confirm=True, since="9.0.0", text=ONLY_RUNNABLE)
        self.assertEqual((False, "busy"), (r["started"], r["reason"]))

    def test_a_job_whose_process_is_gone_is_interrupted(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"], stdin=subprocess.DEVNULL)
        p.wait()
        (self.profile / recompute.JOB).write_text(json.dumps(
            {"status": "running", "pid": p.pid, "started": "2030-01-02T10:00:00", "steps": []}),
            encoding="utf-8")
        job = recompute.status()
        self.assertEqual("interrupted", job["status"])
        self.assertIn("interrupted", fmt.recompute_status_report(job))


class _Kernel32:
    """A stand-in for kernel32: the handle OpenProcess returns and the exit code it reports."""

    def __init__(self, handle=7, code=259, query_ok=True):
        self.handle, self.code, self.query_ok, self.closed = handle, code, query_ok, []

    def OpenProcess(self, access, inherit, pid):
        return self.handle

    def GetExitCodeProcess(self, handle, ref):
        if not self.query_ok:
            return 0
        ref._obj.value = self.code
        return 1

    def CloseHandle(self, handle):
        self.closed.append(handle)


class TestAProcessIsAskedTheWayItsSystemAnswers(unittest.TestCase):
    """Windows has no signal 0. `os.kill(pid, 0)` raised OSError for a process that
    was gone, the check read that as alive, and a stopped job stayed «running» on
    every Windows cell of the release matrix. The exit code is asked there instead."""

    def test_a_process_that_has_not_exited_is_alive_and_its_handle_is_closed(self):
        k = _Kernel32(code=recompute._STILL_ACTIVE)
        self.assertTrue(recompute._alive_windows(42, k, lambda: 0))
        self.assertEqual([7], k.closed)

    def test_a_process_that_exited_is_gone(self):
        self.assertFalse(recompute._alive_windows(42, _Kernel32(code=0), lambda: 0))

    def test_an_exit_code_that_cannot_be_read_is_not_taken_for_an_exit(self):
        self.assertTrue(recompute._alive_windows(42, _Kernel32(query_ok=False), lambda: 0))

    def test_a_process_that_cannot_be_opened_is_alive_only_when_access_was_refused(self):
        self.assertTrue(recompute._alive_windows(42, _Kernel32(handle=0), lambda: recompute._ERROR_ACCESS_DENIED))
        self.assertFalse(recompute._alive_windows(42, _Kernel32(handle=0), lambda: 87))

    def test_windows_is_asked_through_its_own_check(self):
        with mock.patch.object(recompute, "_alive_windows", return_value=False) as w:
            self.assertFalse(recompute._alive("123", windows=True))
        w.assert_called_once_with(123)

    def test_a_pid_that_is_not_a_number_is_not_declared_gone(self):
        self.assertTrue(recompute._alive("not-a-pid", windows=False))


class TestTheFaces(unittest.TestCase):

    def test_the_plan_and_the_status_answer_from_the_command_line(self):
        code, out, err = support.run(["recompute"])
        self.assertEqual(0, code, err[-600:])
        self.assertIn("What to recompute", out)
        code, out, err = support.run(["recompute", "--status"])
        self.assertEqual(0, code, err[-600:])


if __name__ == "__main__":
    unittest.main()
