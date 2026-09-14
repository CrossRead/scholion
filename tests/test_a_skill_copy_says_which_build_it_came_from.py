"""A skill copy says which build it came from.

A skill entry copied into a skills folder does not update itself: after an
upgrade the host goes on reading the old text, and nothing said so. `scholion skill
--install` now replaces the copy and records the build beside it, and `selfcheck`
fails on a copy that differs from the installed build: a host reading an old
entry works under instructions this build no longer gives.
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
from scholion import format as fmt, updates


class _Home(unittest.TestCase):

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="skillhome_")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        patch = mock.patch.dict(os.environ, {"HOME": str(self.home), "USERPROFILE": str(self.home)})
        patch.start(); self.addCleanup(patch.stop)


class TestTheInstall(_Home):

    def test_it_installs_records_and_then_reports_nothing_to_do(self):
        r = updates.install_skill()
        self.assertTrue(r["ok"], r)
        target = self.home / ".agents/skills/scholion/SKILL.md"
        self.assertEqual(updates.package_skill_entry().read_bytes(), target.read_bytes())
        self.assertEqual(updates.installed(), (target.parent / updates.SKILL_SIDECAR).read_text(encoding="utf-8").strip())
        again = updates.install_skill()
        self.assertEqual("unchanged", again["action"])
        self.assertEqual([{"path": str(target), "version": updates.installed(), "status": "current",
                           "severity": None}], updates.skill_copies())

    def test_a_stale_copy_is_replaced_and_says_what_it_was(self):
        folder = self.home / ".agents/skills/scholion"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("an old entry", encoding="utf-8")
        (folder / updates.SKILL_SIDECAR).write_text("0.4.8\n", encoding="utf-8")
        (copy,) = updates.skill_copies()
        self.assertEqual(("older", "0.4.8", "error"), (copy["status"], copy["version"], copy["severity"]))
        self.assertIn("scholion skill --install", fmt.skill_copies_lines([copy]))
        self.assertIn("🔴", fmt.skill_copies_lines([copy]))
        r = updates.install_skill()
        self.assertEqual(("replaced", "0.4.8"), (r["action"], r["previous"]))
        self.assertIn("0.4.8", fmt.skill_install_report(r))

    def test_a_copy_made_by_hand_is_unmarked(self):
        folder = self.home / ".claude/skills/scholion"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("copied by hand", encoding="utf-8")
        (copy,) = updates.skill_copies()
        self.assertEqual("unmarked", copy["status"])

    def test_another_hosts_folder_can_be_named(self):
        r = updates.install_skill(str(self.home / "elsewhere" / "scholion"))
        self.assertTrue(r["ok"])
        self.assertTrue((self.home / "elsewhere/scholion/SKILL.md").is_file())

    def test_no_copies_says_nothing(self):
        self.assertEqual([], updates.skill_copies())
        self.assertEqual("", fmt.skill_copies_lines([]))


class TestTheCommandLine(_Home):

    def test_install_through_the_command(self):
        env = support.env()
        env.update({"HOME": str(self.home), "USERPROFILE": str(self.home)})
        import subprocess, sys
        r = subprocess.run([sys.executable, "-m", "scholion", "skill", "--install", "--json"],
                           capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        self.assertEqual(0, r.returncode, r.stderr)
        self.assertTrue(json.loads(r.stdout)["ok"])
        self.assertTrue((self.home / ".agents/skills/scholion" / updates.SKILL_SIDECAR).is_file())

    def test_selfcheck_fails_while_a_copy_is_stale_and_passes_once_it_is_replaced(self):
        import subprocess, sys
        env = support.env()
        env.update({"HOME": str(self.home), "USERPROFILE": str(self.home)})
        folder = self.home / ".claude/skills/scholion"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("an old entry", encoding="utf-8")
        (folder / updates.SKILL_SIDECAR).write_text("0.4.8\n", encoding="utf-8")
        run = lambda: subprocess.run([sys.executable, "-m", "scholion", "selfcheck"],
                                     capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)
        stale = run()
        self.assertEqual(1, stale.returncode, stale.stdout + stale.stderr)
        self.assertIn("0.4.8", stale.stdout)
        r = updates.install_skill(str(folder))
        self.assertTrue(r["ok"], r)
        fresh = run()
        self.assertEqual(0, fresh.returncode, fresh.stdout + fresh.stderr)


if __name__ == "__main__":
    unittest.main()
