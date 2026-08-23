"""A `for` target must not carry the name of its function's own parameter.

Task 70. `store.add_lab_point(..., name=...)` held the marker's printed label in
`name`, and a loop inside it wrote `for name, bound in (("ref_low", …), …)`.
Python does not scope a `for` target to the loop, so after it ran the label was
the string "ref_high" — for every marker in every real ingest, because the loop
runs whenever a known marker arrives with a unit. Nothing failed; every marker
was simply renamed on screen.

The check costs a syntax-tree walk and covers the whole tree, so it is here
rather than in the reviewer's memory.
"""
from __future__ import annotations

import ast
import io
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _targets(node):
    if isinstance(node, ast.Name):
        yield node.id
    elif isinstance(node, (ast.Tuple, ast.List)):
        for e in node.elts:
            yield from _targets(e)


class TestNoLoopVariableShadowsAParameter(unittest.TestCase):
    def test_the_whole_tree(self):
        bad = []
        for path in sorted(SRC.rglob("*.py")):
            try:
                with io.open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read())
            except SyntaxError:
                continue
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                a = fn.args
                params = {p.arg for p in
                          list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs)}
                params |= {x.arg for x in (a.vararg, a.kwarg) if x}
                for loop in ast.walk(fn):
                    if not isinstance(loop, (ast.For, ast.AsyncFor)):
                        continue
                    for name in _targets(loop.target):
                        if name in params:
                            bad.append(f"{path.relative_to(ROOT)}:{loop.lineno} "
                                       f"in {fn.name}(): loop variable «{name}» is also "
                                       f"a parameter of the same function")
        self.assertEqual(bad, [], "a loop target silently overwrites a parameter:\n  " +
                                  "\n  ".join(bad))


if __name__ == "__main__":
    unittest.main()
