"""Both release runners execute explicit selectors rather than rediscovering all tests."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import support


class TestRunnerSelection(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / "src/tools").mkdir(parents=True)
        (self.root / "tests").mkdir()
        (self.root / "tests/__init__.py").write_text("", encoding="utf-8")
        for rel in ("run_tests.sh", "src/tools/run_tests.py"):
            shutil.copy2(support.ROOT / rel, self.root / rel)
        (self.root / "src/tools/check_compat.py").write_text(
            "print('AFTER_SUITE_GATE')\n", encoding="utf-8")
        (self.root / "tests/test_chosen.py").write_text(
            "import unittest\n"
            "class Chosen(unittest.TestCase):\n"
            " def test_one(self): print('SELECTED_ONE')\n"
            " def test_two(self): print('SELECTED_TWO')\n", encoding="utf-8")
        (self.root / "tests/test_other.py").write_text(
            "import unittest\n"
            "class Other(unittest.TestCase):\n"
            " def test_other(self): print('OTHER_TEST')\n", encoding="utf-8")

    def run_runner(self, face, args, env_overrides=None):
        if face == "shell":
            bash = support.posix_shell("bash")
            if not bash:
                self.skipTest("no working POSIX bash; Python runner is tested separately")
            command = [bash, str(self.root / "run_tests.sh")]
        else:
            command = [sys.executable, str(self.root / "src/tools/run_tests.py")]
        env = support.env()
        # Avoid another interpreter's acceptance pass in this miniature repository.
        env.update(CI="true", SCHOLION_SKIP_REACH="1")
        env.update(env_overrides or {})
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        return subprocess.run([*command, *args], cwd=self.root, env=env,
                              capture_output=True, text=True, encoding="utf-8", timeout=15,
                              stdin=subprocess.DEVNULL)

    def test_a_legacy_console_is_configured_before_selection_prints(self):
        for args, count in (([], 3), (["tests.test_chosen"], 2)):
            with self.subTest(args=args):
                result = self.run_runner("python", args, {
                    "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0",
                })
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"Ran {count} tests", result.stderr)
                self.assertIn("AFTER_SUITE_GATE", result.stdout)
                self.assertNotIn("UnicodeEncodeError", result.stderr)

    def check_named(self, face):
        cases = (
            (["tests.test_chosen"], 2),
            (["tests.test_chosen.Chosen"], 2),
            (["tests.test_chosen.Chosen.test_one"], 1),
            (["tests/test_chosen.py"], 2),
            (["-v", "tests.test_chosen", "-k", "one"], 1),
            (["-p", "test_chosen.py"], 2),
        )
        for args, count in cases:
            with self.subTest(face=face, args=args):
                result = self.run_runner(face, args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"Ran {count} test", result.stderr)
                self.assertIn("SELECTED_ONE", result.stdout)
                self.assertNotIn("OTHER_TEST", result.stdout)
                self.assertIn("AFTER_SUITE_GATE", result.stdout)

    def test_python_runner_selects_modules_classes_methods_paths_and_filters(self):
        self.check_named("python")

    def test_shell_runner_selects_modules_classes_methods_paths_and_filters(self):
        self.check_named("shell")

    def check_default_and_errors(self, face):
        result = self.run_runner(face, [])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        self.assertIn("OTHER_TEST", result.stdout)
        self.assertIn("AFTER_SUITE_GATE", result.stdout)
        result = self.run_runner(face, ["tests.test_chosen", "tests.test_other"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 3 tests", result.stderr)
        for args in (["tests.test_missing"], ["tests.test_chosen", "#", "comment"],
                     ["tests.test_chosen", "-p", "test_other.py"]):
            with self.subTest(face=face, args=args):
                result = self.run_runner(face, args)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("OTHER_TEST", result.stdout)
                self.assertNotIn("AFTER_SUITE_GATE", result.stdout)

    def test_python_default_and_invalid_selectors(self):
        self.check_default_and_errors("python")

    def test_shell_default_and_invalid_selectors(self):
        self.check_default_and_errors("shell")

    def test_python_suite_only_leaves_post_suite_gates_to_the_shell(self):
        result = self.run_runner("python", ["--suite-only", "tests.test_chosen"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 2 tests", result.stderr)
        self.assertNotIn("AFTER_SUITE_GATE", result.stdout)
