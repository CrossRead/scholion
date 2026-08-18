"""Parity of the entry points: everything the web can do, the command line can do too.

This test is the mechanism that holds a rule of the project: a capability appears
in the core and gets an entry point in the CLI and in the web SIMULTANEOUSLY. As
long as the rule lived only in a document, it was broken silently: the summary,
the "Second opinion" and the health index by body system existed only in the
tabs, and the assistant did not see them.

The test starts nothing over the network: the routes are read from the server's
source, the commands are asked of the CLI parser itself.
"""
import unittest

from scholion import contract


class TestParity(unittest.TestCase):

    def test_every_route_is_described(self):
        problems = contract.check_parity()
        self.assertEqual(problems, [], "\n".join(["The parity of the entry points is broken:", *problems]))

    def test_the_map_does_not_refer_to_non_existent_commands(self):
        cmds = set(contract.cli_commands())
        for route, cmd in contract.PARITY.items():
            self.assertIn(cmd, cmds, f"{route} → there is no command «{cmd}» in the CLI")

    def test_the_exceptions_are_explained(self):
        for route, reason in contract.NO_CLI.items():
            self.assertTrue(len(reason) > 15,
                            f"{route}: the reason for the exception must be intelligible, not a brush-off")
        for cmd, reason in contract.CLI_ONLY.items():
            self.assertTrue(len(reason) > 15, f"{cmd}: the reason must be intelligible")

    def test_the_routes_and_commands_are_not_empty(self):
        # protection against "the test is green because nothing was found"
        self.assertGreater(len(contract.server_routes()), 20)
        self.assertGreater(len(contract.cli_commands()), 20)


if __name__ == "__main__":
    unittest.main()


class TestTheThirdFaceKeepsUp(unittest.TestCase):
    """One core, three faces — and the map covered two of them.

    The docstring at the top of `contract.py` names the web, the CLI and the
    Ouroboros plugin, and describes the defect the map was written after:
    «Second opinion», the summary and the health index lived only in the web tabs
    for half a year, because a capability added «quickly» to one face stays there.

    The plugin then did exactly that for the next six months, unwatched. Nine
    capabilities had a route and a command and no tool — among them `limits`, the
    answer to «what can this data NOT tell you». The reader who needs that answer
    most is a language model about to make a negative statement, and it was the
    one face that could not ask for it.

    A missing tool is worse than a missing route for a reason worth stating: a
    person looking at a web page can see that a tab is absent. A model cannot see
    a capability it was never shown — it answers from what it has instead of
    saying it cannot.
    """

    def test_every_command_has_a_tool_or_a_written_reason(self):
        self.assertEqual(contract.check_plugin_parity(), [])

    def test_the_map_does_not_promise_tools_that_are_not_registered(self):
        tools = set(contract.plugin_tools())
        missing = sorted(t for t in contract.PLUGIN.values() if t not in tools)
        self.assertEqual(missing, [], "the map is ahead of the plugin")

    def test_no_tool_writes_to_the_profile(self):
        """The canon says a model does not change therapy or the profile.

        The absence of a write tool is what makes that more than a promise. Every
        write command is listed in NO_PLUGIN as «a write», and this checks the
        list has not quietly lost one.
        """
        writes = {"add-lab", "add-med", "remove-med", "add-metric", "focus-log",
                  "set-folder", "import-labs", "ingest-studies", "ingest-garmin"}
        for cmd in sorted(writes & set(contract.cli_commands())):
            with self.subTest(command=cmd):
                self.assertNotIn(cmd, contract.PLUGIN,
                                 f"«{cmd}» writes to the profile and is exposed as a tool")
                self.assertIn(cmd, contract.NO_PLUGIN)

    def test_the_tools_a_model_needs_before_a_negative_statement_are_there(self):
        """Named one by one, because these are the ones whose absence is silent.

        `limits` says what the data cannot answer; `provenance` says which points
        are confirmed by nothing. A model without them does not know it is
        guessing.
        """
        tools = set(contract.plugin_tools())
        for name in ("sch_limits", "sch_provenance", "sch_overview", "sch_second_opinion"):
            with self.subTest(tool=name):
                self.assertIn(name, tools)

