"""Every TLS context this project builds names the oldest protocol it accepts.

The scan of the published code asked for this in one file; it was set there, and
a second context — built three days later, in the test written FOR that very
fix — went in without it. One instance repaired, another created in the same
wave, in the neighbouring file.

So the rule stops being «this context» and becomes «every context»: wherever
`ssl.SSLContext(...)` is constructed, `minimum_version` is set in the same
function. The default is not dangerous here (both contexts serve loopback for
the length of one test) and that is beside the point — a policy that lives in
whichever files somebody remembered is not a policy, and this is the third time
in this project that a fixed instance turned out to be a class.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCANNED = ("src", "tests")


def _builds_context(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
    return name == "SSLContext"


def _sets_floor(scope: ast.AST) -> bool:
    for node in ast.walk(scope):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "minimum_version":
                    return True
    return False


def _scopes(tree: ast.AST):
    """Every function, plus the module itself: a context may be built at import."""
    yield tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


class TestEveryContextNamesItsFloor(unittest.TestCase):

    def test_no_context_is_built_without_a_minimum_version(self):
        bad, seen = [], 0
        for base in SCANNED:
            for p in sorted((ROOT / base).rglob("*.py")):
                try:
                    tree = ast.parse(p.read_text(encoding="utf-8"))
                except SyntaxError:                          # pragma: no cover
                    continue
                for scope in _scopes(tree):
                    # Only the scope that BUILDS one is asked about it.
                    built = [n for n in ast.walk(scope) if _builds_context(n)]
                    if not built:
                        continue
                    if isinstance(scope, ast.Module) and any(
                            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                            for n in ast.walk(scope)):
                        # The module scope repeats what the functions hold; asking
                        # it as well would report every file twice.
                        continue
                    seen += len(built)
                    if not _sets_floor(scope):
                        bad.append(f"{p.relative_to(ROOT)}:{built[0].lineno}")
        self.assertEqual([], bad,
                         "these build a TLS context without saying which protocols it accepts")
        self.assertGreater(seen, 0, "no TLS context was found at all — the walk is scanning nothing")

    def test_the_rule_can_fire(self):
        bad_src = "import ssl\ndef f():\n    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)\n    return ctx\n"
        good_src = ("import ssl\ndef f():\n    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)\n"
                    "    ctx.minimum_version = ssl.TLSVersion.TLSv1_2\n    return ctx\n")
        for src, expect in ((bad_src, False), (good_src, True)):
            tree = ast.parse(src)
            fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
            self.assertTrue(any(_builds_context(n) for n in ast.walk(fn)))
            self.assertEqual(expect, _sets_floor(fn))


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
