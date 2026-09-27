"""A test of a shell script starts the shell the probe found — never `bash` by name.

`subprocess.run(["bash", …])` and `shutil.which("bash")` do not agree on Windows:
the first starts the launcher in System32, the second finds the one on PATH. A
guard written with the second and a call written with the first skips nothing
and fails everything, and only a Windows runner can see it — which for this
project means after publication. 0.5.9's matrix was red on that alone.

So the rule is held where it can be seen before anything goes out: a test names
its shell through `support.posix_shell()`.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

import support

SHELLS = ("bash", "sh", "zsh")
HERE = Path(__file__).resolve().parent


def bare_shell_calls(source: str):
    """Line numbers where a list handed to a call begins with a shell's bare name."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        for arg in list(node.args) + [k.value for k in node.keywords]:
            if isinstance(arg, (ast.List, ast.Tuple)) and arg.elts:
                first = arg.elts[0]
                if isinstance(first, ast.Constant) and first.value in SHELLS:
                    found.append(node.lineno)
    return found


class TestNoTestStartsAShellByItsBareName(unittest.TestCase):

    def test_the_rule_sees_what_it_is_for(self):
        self.assertEqual([1], bare_shell_calls('run(["bash", "x.sh"])'))
        self.assertEqual([1], bare_shell_calls('run(args=("sh", "-c", "true"))'))
        self.assertEqual([], bare_shell_calls('run([support.posix_shell("bash"), "x.sh"])'))
        self.assertEqual([], bare_shell_calls('names = ["bash", "sh"]'))

    def test_no_test_does(self):
        bad = []
        for f in sorted(HERE.glob("test_*.py")):
            for line in bare_shell_calls(f.read_text(encoding="utf-8")):
                bad.append(f"{f.name}:{line}")
        self.assertEqual([], bad, "start the shell support.posix_shell() found, not a bare name")

    def test_the_probe_answers_with_a_full_path_or_nothing(self):
        found = support.posix_shell("bash")
        if found is None:
            self.skipTest("no bash runs here")
        self.assertTrue(Path(found).is_absolute(), found)
        self.assertIsNone(support.posix_shell("a-shell-nobody-installed"))


if __name__ == "__main__":
    unittest.main()
