"""A workflow that ships runs only tools that ship with it.

The public matrix has a job that counts type errors with `src/tools/check_types.py`.
The workflow travelled to the public tree and the tool did not: the builder
copies tools by name, and nobody had added this one. The job could only fail —
and for one release nobody saw it, because the step before it failed first.

In the source tree every tool is there and this test cannot fail. Its work is
done inside the built package, where the suite runs before anything is
published: a tool a workflow names and the package lacks stops the publication.
"""
from __future__ import annotations

import re
import unittest

import support

TOOL = re.compile(r"(?<![\w/.-])src/tools/[A-Za-z0-9_]+\.(?:py|sh)\b")
GUARD = re.compile(r"\[\s+-[fex]\s+\"?(src/tools/[A-Za-z0-9_]+\.(?:py|sh))\"?\s+\]")


def named_tools(text: str):
    """Tools a script runs, less the ones it first asks the presence of."""
    guarded = set(GUARD.findall(text))
    found = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        for name in TOOL.findall(line):
            if name not in guarded and name not in found:
                found.append(name)
    return found


class TestTheReaderSeesWhatItIsFor(unittest.TestCase):

    def test_a_step_names_its_tool(self):
        self.assertEqual(["src/tools/check_types.py"],
                         named_tools("      - name: types\n        run: python src/tools/check_types.py --strict\n"))

    def test_a_tool_asked_for_first_is_not_a_promise(self):
        text = ('if [ -f src/tools/sync_docs.py ]; then\n  python3 src/tools/sync_docs.py\nfi\n'
                'python3 src/tools/check_compat.py\n# python3 src/tools/old.py\n')
        self.assertEqual(["src/tools/check_compat.py"], named_tools(text))


class TestAWorkflowRunsOnlyWhatThePackageCarries(unittest.TestCase):

    def scripts(self):
        flows = sorted((support.ROOT / ".github" / "workflows").glob("*.yml"))
        runner = support.ROOT / "run_tests.sh"
        return flows + ([runner] if runner.is_file() else [])

    def test_every_tool_named_is_there(self):
        scripts = self.scripts()
        if not scripts:
            self.skipTest("this tree carries neither a workflow nor the runner")
        missing = []
        for script in scripts:
            for name in named_tools(script.read_text(encoding="utf-8")):
                if not (support.ROOT / name).is_file():
                    missing.append(f"{script.relative_to(support.ROOT)} runs {name}")
        self.assertEqual([], missing, "named by a script that ships, and not in this tree")

    def test_a_tool_that_counts_against_a_baseline_has_its_baseline(self):
        tools = support.ROOT / "src" / "tools"
        for tool, baseline in (("check_types.py", "types_baseline.json"),
                               ("check_test_reach.py", "test_reach_baseline.json"),
                               ("check_language.py", "language_baseline.json"),
                               ("check_coverage.py", "coverage_baseline.json")):
            if (tools / tool).is_file():
                with self.subTest(tool=tool):
                    self.assertTrue((tools / baseline).is_file(),
                                    f"{tool} travelled without {baseline}")


class TestTheRunnerCountsTypeErrorsBeforeAPublication(unittest.TestCase):
    """The job in the matrix answers after a tag. It was red on two published
    versions in a row; the step here is what answers before one."""

    def setUp(self):
        runner = support.ROOT / "run_tests.sh"
        if not runner.is_file():
            self.skipTest("this build carries no runner")
        text = runner.read_text(encoding="utf-8")
        self.assertIn("SCHOLION_SKIP_TYPES", text, "the runner does not count type errors at all")
        start = text.index("# Type errors per module")
        self.step = text[start:text.index("# The reach of the suite", start)]

    def test_the_version_is_read_from_the_workflow_that_pins_it(self):
        self.assertIn(".github/workflows/tests.yml", self.step)
        self.assertEqual([], re.findall(r"mypy==\d", self.step),
                         "the runner names a version instead of reading the pinned one")

    def test_the_workflow_does_pin_one(self):
        flow = support.ROOT / ".github" / "workflows" / "tests.yml"
        if not flow.is_file():
            self.skipTest("this tree carries no workflow")
        self.assertRegex(flow.read_text(encoding="utf-8"), r'"mypy==\d+(\.\d+)+"')

    def test_it_says_so_when_it_cannot_run(self):
        for reason in ("uv is not installed", "uv could not provide",
                       "no workflow here pins a mypy version"):
            with self.subTest(reason=reason):
                self.assertIn(reason, self.step)
        self.assertEqual(3, self.step.count("were NOT measured"))

    def test_nothing_is_installed_into_the_interpreter(self):
        self.assertNotIn("pip install", self.step)
        self.assertIn("uv run --no-project --with", self.step)

    def test_a_count_that_grew_stops_the_run(self):
        self.assertIn("check_types.py --strict", self.step)
        self.assertIn("exit 1", self.step)

    def test_a_narrowed_run_and_the_matrix_are_left_alone(self):
        self.assertIn('"$#" -gt 0', self.step)
        self.assertIn('"${CI:-}" = "true"', self.step)


if __name__ == "__main__":
    unittest.main()
