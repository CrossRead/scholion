"""The recompute is one step from every face, and the commands it prints can be typed here.

Two things went wrong on the owner's own machine on 18.09.2026, and both were about
the same distance between what the product said and what a person could do.

The first: the product printed `scholion genotype-sites`, and the shell answered
«command not found» — the package was installed, its console script was not on the
PATH. The commands stay written in one spelling, the same in every language; what is
added, once and only where it is needed, is a line saying how this machine spells
them.

The second: `recompute` had no tool at all, by a recorded decision — a tool call that
blocked for minutes would leave a model reporting on a job it could no longer see.
That reason stopped being true when the progress became a file: the tool reads the
plan, starts the steps in the background, and returns. Somebody whose only face is an
assistant could not be told what their data needed until this existed.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  (pins the fixture profile)
from scholion import contract, format as fmt, recompute


class TestHowThisMachineSpellsIt(unittest.TestCase):

    def test_the_word_is_used_when_the_shell_knows_it(self):
        self.assertEqual("scholion", recompute.program_prefix("/usr/local/bin/scholion"))

    def test_otherwise_the_module_is_named_with_the_interpreter_that_is_running(self):
        prefix = recompute.program_prefix(None)
        self.assertTrue(prefix.endswith(" -m scholion"), prefix)
        self.assertNotIn("/", prefix)          # a name to type, not a path
        self.assertNotIn("unittest", prefix)   # the runner is not the program

    def test_the_note_is_absent_where_the_word_works(self):
        with mock.patch.object(recompute.shutil, "which", return_value="/usr/local/bin/scholion"):
            self.assertEqual("", fmt.spelling_note("recompute --yes"))

    def test_the_note_names_the_prefix_and_shows_one_command_whole(self):
        with mock.patch.object(recompute.shutil, "which", return_value=None):
            note = fmt.spelling_note("recompute --yes")
            prefix = recompute.program_prefix(None)
        self.assertIn(prefix, note)
        self.assertIn(f"{prefix} recompute --yes", note)

    def test_the_reports_that_print_commands_carry_it_and_the_commands_are_untouched(self):
        from scholion import updates
        with mock.patch.object(recompute.shutil, "which", return_value=None):
            plan = fmt.recompute_plan_report(recompute.plan())
            version = fmt.version_report(updates.status())
            prefix = recompute.program_prefix(None)
        for text in (plan, version):
            self.assertIn(prefix, text)
        # the canonical spelling is what the phrases keep saying: the note explains
        # it once instead of every line being rewritten, which is also why a step's
        # `command` stays the key the runner matches on.
        self.assertIn("scholion recompute", plan)

    def test_a_step_keeps_the_command_the_runner_answers_to(self):
        for step in recompute.plan()["steps"]:
            if step.get("key") in recompute.RUNNERS:
                self.assertEqual(step["key"], recompute.runner_key(step["command"]))


class TestTheThirdFaceCanRecompute(unittest.TestCase):

    def tools(self):
        from scholion import ouroboros_tools as ot
        return ot, {tool.name: tool for tool in ot.get_tools()}

    def test_the_tool_is_registered_and_the_command_is_no_longer_a_gap(self):
        _, tools = self.tools()
        self.assertIn("sch_recompute", tools)
        self.assertEqual("sch_recompute", contract.PLUGIN["recompute"])
        self.assertNotIn("recompute", contract.NO_PLUGIN)
        self.assertEqual([], contract.check_plugin_parity())

    def test_it_reads_the_plan_and_starts_nothing_without_a_yes(self):
        ot, tools = self.tools()
        with mock.patch.object(recompute, "start_in_background") as started, \
                mock.patch.object(ot.fmt, "recompute_plan_report", return_value="PLAN") as planned:
            out = tools["sch_recompute"].handler(ot.ToolContext())
        self.assertIn("PLAN", out)
        self.assertEqual(1, planned.call_count)
        started.assert_not_called()

    def test_a_yes_starts_the_steps_in_the_background_and_does_not_wait(self):
        ot, tools = self.tools()
        for yes in (True, "true", "yes", "1"):
            with mock.patch.object(recompute, "start_in_background",
                                   return_value={"started": True, "ok": True}) as started, \
                    mock.patch.object(recompute, "run") as ran:
                tools["sch_recompute"].handler(ot.ToolContext(), confirm=yes)
            self.assertEqual(1, started.call_count, yes)
            ran.assert_not_called()

    def test_both_languages_describe_it_and_its_one_parameter(self):
        from scholion.i18n import t
        for lang in ("ru", "en"):
            with mock.patch.dict("os.environ", {"SCHOLION_LANG": lang}):
                for key in ("tool.sch_recompute.description", "tool.sch_recompute.param.confirm"):
                    text = t(key)
                    self.assertTrue(text and not text.startswith("tool."), (lang, key))


if __name__ == "__main__":
    unittest.main()
