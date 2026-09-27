"""The command line stays a table: every command has a handler, and `_main` stays small.

`cli._main` was a single function of 609 lines — a chain of `elif args.cmd ==
...` that every new command made longer, and the one place a person's typed
command turns into an answer. An external review (25.09.2026) named it the
largest risk for the question «why did the program say that»: a branch cannot be
read, tested or blamed on its own when it is line 400 of a function.

It is now `_ACTIONS` and `_QUERIES`, one function per command, moved line for
line. These tests keep it that way: a new command that gets a parser entry but no
handler fails here, and so does a `_main` that starts growing branches again.
"""
from __future__ import annotations

import ast
import inspect
import types
import unittest

import support  # noqa: F401  (puts src/ on the path)
from scholion import cli

MAIN_CEILING = 100      # lines; 74 when the split was made


def _commands():
    p = cli.build_parser()
    sub = [a for a in p._actions if a.__class__.__name__ == "_SubParsersAction"][0]
    return sorted(sub.choices)


def _handler_for(cmd):
    args = types.SimpleNamespace(cmd=cmd)
    for when, run in cli._ACTIONS + cli._QUERIES:
        if when(args):
            return run
    return None


class TestEveryCommandHasAHandler(unittest.TestCase):

    def test_the_parser_lists_commands(self):
        self.assertGreater(len(_commands()), 50)

    def test_each_command_reaches_a_handler(self):
        missing = [c for c in _commands() if _handler_for(c) is None]
        self.assertEqual([], missing, "a command the parser accepts has no handler in "
                                      "cli._ACTIONS or cli._QUERIES — it would print the help")

    def test_no_handler_is_left_without_a_command(self):
        commands = set(_commands())
        for when, run in cli._ACTIONS + cli._QUERIES:
            with self.subTest(handler=run.__name__):
                self.assertTrue(any(when(types.SimpleNamespace(cmd=c)) for c in commands)
                                or "_with_fields" in run.__name__ or "_install" in run.__name__,
                                f"{run.__name__} answers no command the parser knows")


class TestMainStaysADispatcher(unittest.TestCase):

    def test_main_is_short(self):
        lines = len(inspect.getsource(cli._main).splitlines())
        self.assertLessEqual(lines, MAIN_CEILING,
                             "cli._main is growing again — put the new command in its own "
                             "function and a row in _ACTIONS or _QUERIES")

    def test_main_does_not_branch_on_the_command(self):
        """The tail after the dispatch may check the command for its exit code;
        what it may not do is compute an answer per command."""
        tree = ast.parse(inspect.getsource(cli._main).strip())
        fn = tree.body[0]
        computing = [n for n in ast.walk(fn) if isinstance(n, ast.If)
                     and "args.cmd ==" in ast.unparse(n.test)
                     and any(isinstance(x, ast.Assign) and any(
                         isinstance(t, ast.Name) and t.id in ("res", "render") for t in x.targets)
                         for x in ast.walk(n))]
        self.assertEqual([], [ast.unparse(n.test) for n in computing])


if __name__ == "__main__":
    unittest.main()
