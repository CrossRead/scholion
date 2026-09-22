"""Under a host that installs the package, `update` is the host's, and the note is said once a day.

Two findings of the Ouroboros Hub maintainer on review of PR #74 (19.09.2026),
both about our code rather than theirs:

* the Hub runs a skill in a child of the HOST's interpreter, so the route
  «pip in the running interpreter» would have installed into the host's Python
  instead of the skill's isolated environment — a change to somebody else's
  environment, made from a process nobody watches;
* the newer-build note appeared on every answer, because «once» was kept in a
  module variable and the Hub starts a fresh process for every tool call.

And a third, which was ours to notice: the manifest a host reads is written by
hand around two derived fields, so the `subprocess` permission and the corrected
network paragraph the maintainer added on their side would have been reverted
by our next pull request. The tests at the bottom hold them in place.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import format as fmt, upgrade

HUB = support.ROOT / "ouroboros_plugin" / "hub" / "scholion"
MANIFEST = HUB / "SKILL.md"


class _Cache(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="host_")).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(support.pin_cache(self.root / "cache"))
        upgrade._SAID = False
        self.addCleanup(setattr, upgrade, "_SAID", False)


class TestTheRoute(unittest.TestCase):

    def test_a_host_is_named_and_nothing_is_installable(self):
        with mock.patch.dict(os.environ, {"SCHOLION_MANAGED_BY": "Ouroboros Hub"}):
            r = upgrade.route("/usr/local", None, "/usr/local/bin/python3")
        self.assertEqual({"kind": "host", "host": "Ouroboros Hub", "command": [], "installable": False}, r)

    def test_without_a_host_the_routes_are_as_they_were(self):
        env = {k: v for k, v in os.environ.items() if k != "SCHOLION_MANAGED_BY"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertNotEqual("host", upgrade.route("/usr/local", None, "/usr/local/bin/python3")["kind"])

    def test_a_confirmed_install_under_a_host_runs_nothing(self):
        ran = []
        with mock.patch.dict(os.environ, {"SCHOLION_MANAGED_BY": "Ouroboros Hub"}):
            r = upgrade.install(confirm=True, run=lambda *a, **k: ran.append(a))
            text = fmt.update_install_report(r)
        self.assertEqual((False, "host_managed"), (r["ok"], r["reason"]))
        self.assertEqual([], ran)
        self.assertIn("Ouroboros Hub", text)
        self.assertNotIn("pip", text)

    def test_the_version_report_names_the_host_instead_of_a_command(self):
        n = {"status": "newer", "latest": "99.0.0", "installed": "0.5.4",
             "route": {"kind": "host", "host": "Ouroboros Hub", "command": [], "installable": False}}
        text = fmt.update_report(n)
        self.assertIn("Ouroboros Hub", text)
        self.assertNotIn("update --yes", text)


class TestTheNoteIsSaidOnceADay(_Cache):
    """Each `_SAID = False` below is a fresh process, which is what the Hub gives every call."""

    NEWER = {"status": "newer", "latest": "99.0.0", "installed": "0.5.4", "route": {"kind": "pip"}}

    def _fresh(self, now, answer=None):
        upgrade._SAID = False
        with mock.patch.object(upgrade, "notice", return_value=answer or self.NEWER):
            return upgrade.session_note(now=now)

    def test_a_fresh_process_does_not_repeat_it(self):
        self.assertIn("99.0.0", self._fresh(1000.0))
        self.assertEqual("", self._fresh(1000.0 + 3600))
        self.assertEqual("", self._fresh(1000.0 + 23 * 3600))

    def test_it_comes_back_the_next_day_and_for_the_next_release(self):
        self.assertIn("99.0.0", self._fresh(1000.0))
        self.assertIn("99.0.0", self._fresh(1000.0 + 25 * 3600))
        later = {**self.NEWER, "latest": "99.1.0"}
        self.assertIn("99.1.0", self._fresh(1000.0 + 25 * 3600 + 60, later))

    def test_under_a_host_it_says_the_host_updates_and_not_to_call_update(self):
        hosted = {**self.NEWER, "route": {"kind": "host", "host": "Ouroboros Hub"}}
        note = self._fresh(1000.0, hosted)
        self.assertIn("Ouroboros Hub", note)
        self.assertNotIn("update --yes", note)

    def test_a_fresh_check_of_the_registry_keeps_what_was_said(self):
        asked = []

        def fetch(url):
            asked.append(url)
            return {"info": {"version": "99.0.0"}}
        with mock.patch.dict(os.environ, {"SCHOLION_OFFLINE": ""}):
            upgrade.notice(fetch=fetch, now=10.0)
            upgrade._remember_said("99.0.0", 10.0)
            upgrade.notice(fetch=fetch, now=10.0 + 25 * 3600)   # the cache is stale: asked again
        self.assertEqual(2, len(asked))
        self.assertEqual("99.0.0", (upgrade._read_cached() or {}).get("said", {}).get("latest"))


@unittest.skipUnless(MANIFEST.exists(), "the Hub skill is not part of this build")
class TestTheHubSaysSo(unittest.TestCase):

    def test_the_plugin_marks_the_run_as_the_hosts(self):
        text = (HUB / "plugin.py").read_text(encoding="utf-8")
        self.assertRegex(text, r'os\.environ\.setdefault\("SCHOLION_MANAGED_BY"')

    def test_the_manifest_declares_subprocess_because_the_package_starts_programs(self):
        starts = [p.relative_to(support.ROOT) for p in (support.SRC / "scholion").rglob("*.py")
                  if re.search(r"^\s*(import subprocess|from subprocess)", p.read_text(encoding="utf-8"), re.M)]
        self.assertTrue(starts, "the package no longer starts any program — then drop the permission")
        perms = re.search(r"^permissions:\s*\[([^\]]*)\]", MANIFEST.read_text(encoding="utf-8"), re.M)
        self.assertIn("subprocess", [p.strip() for p in perms.group(1).split(",")],
                      f"these modules start programs and the manifest does not say so: {starts[:5]}")

    def test_the_manifest_counts_the_registry_among_what_goes_out(self):
        text = MANIFEST.read_text(encoding="utf-8")
        self.assertNotIn("Exactly two named", text)
        self.assertIn("PyPI", text)


if __name__ == "__main__":
    unittest.main()
