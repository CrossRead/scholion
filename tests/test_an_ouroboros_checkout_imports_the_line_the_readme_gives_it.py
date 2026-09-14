"""An Ouroboros checkout imports the line the README gives it.

The README told a person to copy `scholion/ouroboros_tools.py` into Ouroboros's
tools package. The module imports its neighbours relatively (`from . import
engine`), and inside another package there are no neighbours: the copy failed on
its first import with «cannot import name 'engine' from 'ouroboros.tools'», so
the plugin never loaded and nothing said why. The README now gives one line that
imports the installed package; this test lays out a tools package the way an
Ouroboros checkout has one, writes exactly the line the README shows, and
imports it.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import support

ROOT = support.ROOT


def _section() -> str:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return text.split("### 4. A plugin for Ouroboros", 1)[1].split("\n## ", 1)[0]


def _readme_line():
    return re.search(r"^echo '([^']+)' > <ouroboros>/ouroboros/tools/(\w+)\.py$", _section(), re.M)


class TestTheOuroborosInstruction(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ouroboros_")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.tools = self.tmp / "ouroboros" / "tools"
        self.tools.mkdir(parents=True)
        (self.tmp / "ouroboros" / "__init__.py").write_text("", encoding="utf-8")
        (self.tools / "__init__.py").write_text("", encoding="utf-8")

    def _import(self, module: str) -> subprocess.CompletedProcess:
        env = support.env()
        env["PYTHONPATH"] = os.pathsep.join([str(self.tmp), str(ROOT / "src")])
        return subprocess.run(
            [sys.executable, "-c", f"import {module} as m; print(len(m.get_tools()))"],
            capture_output=True, text=True, env=env, cwd=str(self.tmp),
            stdin=subprocess.DEVNULL, timeout=120)

    def _tool_count(self) -> str:
        from scholion import ouroboros_tools
        return str(len(ouroboros_tools.get_tools()))

    def test_the_readme_gives_a_line_and_no_longer_copies_the_module(self):
        self.assertIsNotNone(_readme_line(), "the README section names no line to place")
        self.assertNotIn("ouroboros_tools as m; print(m.__file__)", _section())

    def test_the_line_imports_inside_a_tools_package_and_registers_every_tool(self):
        m = _readme_line()
        (self.tools / f"{m.group(2)}.py").write_text(m.group(1) + "\n", encoding="utf-8")
        r = self._import(f"ouroboros.tools.{m.group(2)}")
        self.assertEqual(0, r.returncode, r.stderr[-800:])
        self.assertEqual(self._tool_count(), r.stdout.strip())

    def test_a_copy_of_the_module_itself_is_what_fails(self):
        """The shape the old instruction produced, kept as the reason for the new one."""
        shutil.copy(ROOT / "src" / "scholion" / "ouroboros_tools.py", self.tools / "ouroboros_tools.py")
        r = self._import("ouroboros.tools.ouroboros_tools")
        self.assertNotEqual(0, r.returncode)
        self.assertIn("ImportError", r.stderr)

    def test_the_folder_form_imports_the_same_way(self):
        shim = ROOT / "ouroboros_plugin" / "scholion_tools.py"
        if not shim.is_file():
            self.skipTest("the folder form does not travel with the package")
        shutil.copy(shim, self.tools / "scholion_tools.py")
        r = self._import("ouroboros.tools.scholion_tools")
        self.assertEqual(0, r.returncode, r.stderr[-800:])
        self.assertEqual(self._tool_count(), r.stdout.strip())


if __name__ == "__main__":
    unittest.main()
