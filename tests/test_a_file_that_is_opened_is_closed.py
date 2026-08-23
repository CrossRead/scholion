"""A file opened for reading is opened in a `with`, or handed to the caller.

The suite printed 159 `ResourceWarning: unclosed file` lines — three tests, each
walking the whole tree with `ast.parse(io.open(path).read())`, one warning per
file read. Nothing leaked for longer than a garbage collection, and that is not
the point. The point is that a run whose output is 159 lines of noise is a run
nobody reads to the end, and the next warning — the one that matters — arrives
into a screen already full of warnings that do not.

The rule is narrow: an opened file is either bound by a `with`, or returned to
whoever asked for it (`tabular_genome` opens a container and hands the handle
back — closing it there would break the reader). Everything else is a handle
dropped on the floor.

Scope: the package and the suite. `src/ingest` holds one-shot scripts that open
a file, write it and exit — the process ends before anything could accumulate,
and they are left alone deliberately rather than by oversight.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCANNED = ("src/scholion", "tests")

#: The openers this rule knows. `open` itself plus the compression modules —
#: they return the same kind of object and leak the same way.
_OPENERS = {"open"}


def _is_open_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
    return name in _OPENERS


def _offences(tree: ast.AST) -> list:
    """Discarded opens: the handle is consumed on the spot and never bound."""
    # Everything inside a `with` header, and everything inside a `return`, is
    # fine — the first is closed by the statement, the second is the caller's.
    allowed = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                for sub in ast.walk(item.context_expr):
                    allowed.add(id(sub))
        if isinstance(node, ast.Return) and node.value is not None:
            for sub in ast.walk(node.value):
                allowed.add(id(sub))

    out = []
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            if not _is_open_call(child) or id(child) in allowed:
                continue
            # `open(...).read()` — the handle is the receiver of a method call;
            # `json.load(open(...))` — the handle is an argument to another call.
            if isinstance(parent, (ast.Attribute, ast.Call)):
                out.append(child.lineno)
    return out


def _files():
    for base in SCANNED:
        for p in sorted((ROOT / base).rglob("*.py")):
            yield p


class TestEveryOpenedFileIsClosed(unittest.TestCase):

    def test_no_handle_is_dropped_on_the_floor(self):
        bad = []
        for p in _files():
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError:                              # pragma: no cover
                continue
            for line in _offences(tree):
                bad.append(f"{p.relative_to(ROOT)}:{line}")
        self.assertEqual([], bad,
                         "these open a file and never close it — wrap the call in a `with`")

    def test_the_walk_is_looking_at_something(self):
        """A scan that reads no files passes as readily as a clean tree."""
        seen = 0
        for p in _files():
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError:                              # pragma: no cover
                continue
            seen += sum(1 for n in ast.walk(tree) if _is_open_call(n))
        self.assertGreater(seen, 20, "the walk found almost no file access — it is scanning nothing")

    def test_the_rule_catches_what_it_is_written_for(self):
        """The gate must be able to fire — on each shape it is meant to catch."""
        for source in ('ast.parse(open(p).read())',
                       'json.load(open(p))',
                       'text = open(p, encoding="utf-8").read()'):
            with self.subTest(source=source):
                self.assertTrue(_offences(ast.parse(source)), f"not caught: {source}")

    def test_the_rule_leaves_the_two_honest_shapes_alone(self):
        for source in ('with open(p) as fh:\n    d = fh.read()\n',
                       'def f(p):\n    return io.TextIOWrapper(open(p, "rb"))\n'):
            with self.subTest(source=source):
                self.assertEqual([], _offences(ast.parse(source)), f"false alarm: {source}")


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
