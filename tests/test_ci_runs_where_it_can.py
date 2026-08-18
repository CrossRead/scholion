"""A workflow step must be able to run in the tree it is shipped to.

The `package` job in `tests.yml` exists to catch exactly one class of defect: a
check that asks the artefact for something only the repository has. Written in
the source tree it passes; shipped to the public repository it fails, and the
author never sees it because the author is in the source tree.

That job was an instance of the class it was written to catch. Its first step
runs `make_shareable.py`, which builds the package FROM `share/` — and `share/`
does not ship. So on the public repository the build went red on every push,
with «Run this from the ORIGINAL repository», and the only thing it proved was
that the check had never been run where it would land.

`tests/support.py` already carries the predicate for this and calls it
`IN_SOURCE_REPO`: does `share/` exist. Python code that reaches for a
repository-only path is expected to consult it. This test extends the same
expectation to the workflows, where the same mistake is easier to make and much
harder to notice — a red badge on a public repository is the first thing a
stranger sees of the project.

The check is textual, which is a weaker instrument than the project prefers, so
it is kept deliberately narrow: it looks only for the tools that CANNOT work
outside the source tree, and asks only that the step naming one be conditional.
It does not try to judge whether the condition is the right one — a wrong
condition is a bug, an absent one is this bug.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import support

WORKFLOWS = support.ROOT / ".github" / "workflows"

# Tools that read `share/` or another path the package does not carry. Each one
# fails closed with a clear message when run outside the source tree — which is
# the correct behaviour and precisely why an unguarded step turns into a red
# build rather than a silent wrong answer.
REPO_ONLY = ("make_shareable.py", "publish_share.sh", "sync_docs.py", "check_push.py")


def _steps(text: str):
    """Split a workflow into steps by the `- name:`/`- uses:` markers.

    A crude split, and named as such. Parsing the YAML properly would be better,
    but PyYAML is not a dependency of this project and adding one to run a test
    that guards a six-line rule is the wrong trade. The split errs towards
    grouping too much into one step, which can only make this test more
    permissive, never falsely accusing.
    """
    # Comment lines are dropped first. The prose in this workflow EXPLAINS why the
    # guard exists and names the tool while doing so, and the first version of this
    # test read that explanation as an unguarded call — a check tripping over its
    # own documentation. What a step runs is `run:`; what it says is not.
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    parts, cur = [], []
    for line in lines:
        if re.match(r"\s+- (name|uses):", line) and cur:
            parts.append("\n".join(cur))
            cur = [line]
        else:
            cur.append(line)
    if cur:
        parts.append("\n".join(cur))
    return parts


class TestNoWorkflowStepNeedsWhatThePackageDoesNotCarry(unittest.TestCase):

    @unittest.skipUnless(WORKFLOWS.is_dir(), "no workflows in this tree")
    def test_a_step_running_a_source_only_tool_is_conditional(self):
        offenders = []
        for wf in sorted(WORKFLOWS.glob("*.yml")):
            for step in _steps(wf.read_text(encoding="utf-8")):
                tool = next((t for t in REPO_ONLY if t in step), None)
                if not tool:
                    continue
                if "if:" not in step:
                    offenders.append(f"{wf.name}: a step runs {tool}, which needs the "
                                     f"source tree, with no condition on being in one")
        self.assertEqual(offenders, [], "\n  " + "\n  ".join(offenders) if offenders else "")

    @unittest.skipUnless(WORKFLOWS.is_dir(), "no workflows in this tree")
    def test_the_condition_is_decided_by_the_same_thing_python_decides_by(self):
        """One question, and it must not grow two answers.

        `support.IN_SOURCE_REPO` is «does share/ exist». If a workflow ever
        starts asking something else — a branch name, a repository name — the two
        drift, and the drift shows up as a red build on somebody else's fork.
        """
        text = (WORKFLOWS / "tests.yml").read_text(encoding="utf-8")
        self.assertIn("-d share", text,
                      "the workflow decides «is this the source tree» by something "
                      "other than the presence of share/, which is what "
                      "support.IN_SOURCE_REPO asks")

    def test_the_predicate_still_means_what_the_workflow_assumes(self):
        """If `share/` stops being the marker, this test is the thing that says so."""
        self.assertEqual(support.IN_SOURCE_REPO, (support.ROOT / "share").is_dir())


class TestASkippedJobSaysWhy(unittest.TestCase):
    """A green tick that ran nothing is worse than a red one.

    The guarded steps are skipped in the public repository by design. Skipped
    silently, the job reports success for having done nothing, which is the shape
    of every environment-dependent check this project has been bitten by. The
    workflow prints a notice instead.
    """

    @unittest.skipUnless(WORKFLOWS.is_dir(), "no workflows in this tree")
    def test_the_skip_is_announced_in_the_log(self):
        text = (WORKFLOWS / "tests.yml").read_text(encoding="utf-8")
        self.assertIn("::notice::", text,
                      "the job can pass by doing nothing and say nothing about it")


if __name__ == "__main__":
    unittest.main()
