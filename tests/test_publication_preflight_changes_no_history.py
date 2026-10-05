"""The publisher can check a candidate without touching a public checkout."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import support


@unittest.skipUnless(support.posix_shell("bash") and shutil.which("git"), "needs bash and git")
class TestPreflight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / "source"
        self.tools = self.root / "src" / "tools"
        self.tools.mkdir(parents=True)
        original = support.ROOT / "src" / "tools" / "publish_share.sh"
        if not original.exists():
            self.skipTest("private publisher is not shipped")
        self.script = self.tools / original.name
        shutil.copyfile(original, self.script)
        (self.root / "VERSION").write_text("0.6.0\n", encoding="utf-8")
        (self.root / "CHANGELOG.md").write_text("## v0.6.0 — candidate\nTest notes.\n", encoding="utf-8")
        self.public = self.base / "existing" / "Scholion-SHARE"
        self.public.mkdir(parents=True)
        (self.public / "README.md").write_text("untouched public checkout\n", encoding="utf-8")
        (self.root / ".publish.conf").write_text(f"SHARE_DIR='{self.public}'\n", encoding="utf-8")
        # A tiny synthetic builder exercises the shell control flow, not the
        # real privacy audit (which has its own end-to-end tests).
        (self.tools / "make_shareable.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "def load_private(repo): return []\n"
            "if __name__ == '__main__' and '--audit-only' not in sys.argv:\n"
            "    p = Path(sys.argv[1]); p.mkdir(parents=True, exist_ok=True)\n"
            "    (p / 'run_tests.sh').write_text('#!/bin/sh\\nexit 0\\n')\n"
            "    (p / 'run_tests.sh').chmod(0o700)\n", encoding="utf-8")
        (self.tools / "test_the_artefact.sh").write_text(
            '#!/bin/sh\nprintf tested > "$1/TESTED"\nexit "${PROBE_TEST_RC:-0}"\n', encoding="utf-8")
        self.env = {**os.environ, "TMPDIR": str(self.base), "SCHOLION_ALLOW_DIRTY": "0"}
        self.env.pop("PUBLIC_REMOTE", None)
        self.env.pop("PUBLIC_REMOTE_MIRROR", None)

    def run_script(self, *args):
        return subprocess.run([support.posix_shell("bash"), str(self.script), *args],
                              cwd=self.root, env=self.env, text=True, capture_output=True, stdin=subprocess.DEVNULL)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, stdin=subprocess.DEVNULL)

    def test_preflight_builds_and_tests_without_git_or_public_changes(self):
        result = self.run_script("--preflight")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        candidates = list(self.base.glob("scholion-preflight.*/Scholion-SHARE"))
        self.assertEqual(1, len(candidates))
        self.assertTrue((candidates[0] / "TESTED").exists(), "must not exit before tests")
        self.assertFalse((candidates[0] / ".git").exists())
        self.assertEqual(["README.md"], sorted(p.name for p in self.public.iterdir()))
        self.assertEqual("untouched public checkout\n", (self.public / "README.md").read_text(encoding="utf-8"))

    def test_a_red_candidate_does_not_report_success(self):
        self.env["PROBE_TEST_RC"] = "1"
        result = self.run_script("--preflight")
        self.assertEqual(5, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("preflight passed", result.stdout)

    def test_worktree_file_does_not_bypass_the_dirty_check(self):
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
                 "commit", "-qm", "fixture")
        linked = self.base / "linked"
        self.git("worktree", "add", "--detach", str(linked))
        self.root = linked
        self.script = linked / "src" / "tools" / "publish_share.sh"
        (linked / "VERSION").write_text("0.6.1\n", encoding="utf-8")
        result = self.run_script("--dry-run")
        self.assertEqual(1, result.returncode)
        self.assertIn("working tree is not clean", result.stdout)

    def test_existing_local_release_tag_stops_before_a_build(self):
        subprocess.run(["git", "init", "-q", str(self.public)], check=True, capture_output=True, stdin=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(self.public), "add", "."], check=True, stdin=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(self.public), "-c", "user.name=Synthetic",
                        "-c", "user.email=synthetic@example.invalid", "commit", "-qm", "fixture"], check=True, stdin=subprocess.DEVNULL)
        subprocess.run(["git", "-C", str(self.public), "tag", "v0.6.0"], check=True, stdin=subprocess.DEVNULL)
        result = self.run_script("--no-push")
        self.assertEqual(1, result.returncode)
        self.assertIn("already exists locally", result.stdout)
        self.assertEqual("untouched public checkout\n", (self.public / "README.md").read_text(encoding="utf-8"))
