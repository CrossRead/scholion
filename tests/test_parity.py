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
