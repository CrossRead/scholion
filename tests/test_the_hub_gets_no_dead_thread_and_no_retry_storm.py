"""Two findings of the Ouroboros Hub review of 22.09.2026, and one of our own.

* Under a host that runs every call in a fresh process, `recompute` with
  `confirm=true` started a thread that died with the call: the next call found
  the job interrupted and nothing finished. There it now plans and says why.
* A registry that did not answer was asked again on every call, and every call
  paid the request's timeout. The failure is now remembered for an hour.
* Two starters (the page and a terminal) could both read «not running» and
  both run the steps; the job is now claimed atomically, and a run that did not
  start or raised leaves the job file in a terminal state, not «running».
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, recompute, updates, upgrade


class _Profile(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="hubcall_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self.addCleanup(support.pin_profile(self.profile))
        self.addCleanup(support.pin_cache(self.root / "cache"))
        core.reset_cache()
        self.addCleanup(core.reset_cache)


class TestRecomputeUnderAPerCallHost(_Profile):

    def test_it_plans_and_starts_nothing(self):
        started = []
        with mock.patch.dict(os.environ, {"SCHOLION_MANAGED_BY": "Ouroboros Hub"}), \
                mock.patch("threading.Thread", side_effect=lambda *a, **k: started.append(k)):
            r = recompute.start_in_background()
        self.assertEqual((False, "per_call_host", "Ouroboros Hub"),
                         (r["started"], r["reason"], r["host"]))
        self.assertIn("plan", r)
        self.assertEqual([], started)
        self.assertFalse((self.profile / recompute.JOB).exists())

    def test_the_report_says_where_to_run_it(self):
        from scholion import format as fmt
        text = fmt.recompute_run_report({"started": False, "reason": "per_call_host",
                                         "host": "Ouroboros Hub"})
        self.assertIn("Ouroboros Hub", text)
        self.assertIn("scholion recompute --yes", text)


class TestTheClaim(_Profile):

    def test_a_live_claim_is_busy_and_a_dead_one_is_taken_over(self):
        first = recompute._claim()
        self.assertIsNotNone(first)
        self.assertIsNone(recompute._claim(), "a second starter took a held job")
        recompute._release(first)
        (self.profile / recompute.CLAIM).write_text("999999999", encoding="utf-8")
        again = recompute._claim()
        self.assertIsNotNone(again, "a claim whose owner is gone was never released")
        recompute._release(again)
        self.assertFalse((self.profile / recompute.CLAIM).exists())

    def test_a_run_that_raises_leaves_a_terminal_job_and_no_claim(self):
        claim = recompute._claim()
        with mock.patch.object(recompute, "run", side_effect=RuntimeError("boom")):
            recompute._run_claimed(None, claim)
        job = json.loads((self.profile / recompute.JOB).read_text(encoding="utf-8"))
        self.assertEqual("failed", job["status"])
        self.assertIn("boom", job["reason"])
        self.assertFalse((self.profile / recompute.CLAIM).exists())

    def test_a_run_that_did_not_start_leaves_a_terminal_job(self):
        claim = recompute._claim()
        with mock.patch.object(recompute, "run",
                               return_value={"ok": False, "started": False,
                                             "reason": "nothing_ready"}):
            recompute._run_claimed(None, claim)
        job = json.loads((self.profile / recompute.JOB).read_text(encoding="utf-8"))
        self.assertEqual(("failed", "nothing_ready"), (job["status"], job["reason"]))


class TestAnUnansweredRegistryIsNotAskedOnEveryCall(_Profile):

    def setUp(self):
        super().setUp()
        upgrade._SAID = False
        self.addCleanup(setattr, upgrade, "_SAID", False)

    def test_one_miss_an_hour(self):
        asked = []

        def miss(fetch=None):
            asked.append(1)
            return {"status": "unreachable", "installed": "0.5.7", "latest": None}
        with mock.patch.dict(os.environ, {"SCHOLION_OFFLINE": ""}), \
                mock.patch.object(updates, "check_registry", side_effect=miss):
            self.assertEqual("unreachable", upgrade.notice(now=1000.0)["status"])
            self.assertEqual("unreachable", upgrade.notice(now=1000.0 + 600)["status"])
            self.assertEqual(1, len(asked), "the registry was asked again inside the hour")
            upgrade.notice(now=1000.0 + 3700)
            self.assertEqual(2, len(asked), "after an hour it is asked again")

    def test_a_process_that_heard_nothing_can_still_say_it_later(self):
        with mock.patch.object(upgrade, "notice",
                               return_value={"status": "unreachable", "latest": None}):
            self.assertEqual("", upgrade.session_note(now=1000.0))
        self.assertFalse(upgrade._SAID, "an unanswered check closed the note for the process")
        newer = {"status": "newer", "latest": "99.0.0", "installed": "0.5.7",
                 "route": {"kind": "pip"}}
        with mock.patch.object(upgrade, "notice", return_value=newer):
            self.assertIn("99.0.0", upgrade.session_note(now=2000.0))


if __name__ == "__main__":
    unittest.main()


class TestTheClaimAtItsEdges(_Profile):

    def test_an_unreadable_claim_is_taken_over(self):
        (self.profile / recompute.CLAIM).write_text("not a pid", encoding="utf-8")
        got = recompute._claim()
        self.assertIsNotNone(got)
        recompute._release(got)

    def test_a_claim_that_cannot_be_removed_is_left_and_busy(self):
        (self.profile / recompute.CLAIM).write_text("999999999", encoding="utf-8")
        with mock.patch.object(Path, "unlink", side_effect=OSError("read-only")):
            self.assertIsNone(recompute._claim())

    def test_no_profile_folder_is_no_claim(self):
        with mock.patch.object(recompute, "_profile", return_value=self.root / "absent"):
            self.assertIsNone(recompute._claim())

    def test_release_is_quiet_about_nothing_to_release(self):
        recompute._release(None)
        recompute._release(self.profile / "never-there")

    def _ready_plan(self):
        return {"job": {}, "since": "0.5.6",
                "steps": [{"state": "ready", "command": "scholion ingest-labs", "key": "k"}]}

    def test_a_held_claim_makes_both_starters_busy(self):
        held = recompute._claim()
        self.addCleanup(recompute._release, held)
        env = {k: v for k, v in os.environ.items() if k != "SCHOLION_MANAGED_BY"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(recompute, "plan", return_value=self._ready_plan()):
            self.assertEqual("busy", recompute.start_in_background()["reason"])
            self.assertEqual("busy", recompute.run(confirm=True)["reason"])

    def test_a_free_job_is_claimed_and_started_on_a_thread(self):
        started = []

        class _T:
            def __init__(self, target=None, args=(), daemon=None):
                started.append((target, args))

            def start(self):
                pass
        env = {k: v for k, v in os.environ.items() if k != "SCHOLION_MANAGED_BY"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(recompute, "plan", return_value=self._ready_plan()), \
                mock.patch("threading.Thread", _T):
            r = recompute.start_in_background()
        self.assertEqual({"started": True, "steps": 1}, r)
        self.assertEqual(recompute._run_claimed, started[0][0])
        recompute._release(started[0][1][1])


class TestAMissThatCannotBeWritten(_Profile):

    def test_an_unwritable_cache_does_not_break_the_answer(self):
        blocker = self.root / "blocker"
        blocker.write_text("a file where a folder should be", encoding="utf-8")
        with mock.patch.dict(os.environ, {"SCHOLION_OFFLINE": ""}), \
                mock.patch.object(upgrade, "_notice_path", return_value=blocker / "n.json"), \
                mock.patch.object(updates, "check_registry",
                                  return_value={"status": "unreachable", "installed": "0.5.7",
                                                "latest": None}):
            self.assertEqual("unreachable", upgrade.notice(now=5.0)["status"])
