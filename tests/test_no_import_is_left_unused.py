"""An import nobody uses is found here, before the public linter finds it.

The public matrix runs a linter this machine does not have — the package depends
on nothing, and its suite asks nothing of whoever runs it. So the one class that
linter catches most often had no gate on this side of a publication: 0.5.9 went
out with two imports left behind by an edit, the matrix went red on them, and
the version was already on the registry.

This is that class and nothing wider, written against the standard library. A
name counts as read when the code reads it, when a quoted annotation names it, or
when `__all__` exports it — and not when the same letters merely occur in some
string: the first draft of this reader took `"callset2-test.json"` for a use of
`json` and so missed one of the very two imports it was written for. The
exemptions the linter is given in `pyproject.toml` are read from there, so the
two readers cannot be told different things.
"""
from __future__ import annotations

import ast
import re
import unittest

import support

NOQA = re.compile(r"#\s*noqa(?::\s*[A-Z0-9, ]+)?", re.I)
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def exempt_files(pyproject: str):
    """Paths `pyproject.toml` tells the linter not to judge by this rule."""
    out, inside = set(), False
    for line in pyproject.splitlines():
        line = line.strip()
        if line.startswith("["):
            inside = line == "[tool.ruff.lint.per-file-ignores]"
        elif inside and "=" in line and not line.startswith("#"):
            path, rules = line.split("=", 1)
            if "F401" in rules or '"F"' in rules:
                out.add(path.strip().strip('"'))
    return out


def unused_imports(source: str):
    """[(line, name)] of names an import binds and nothing in the module reads."""
    tree = ast.parse(source)
    lines = source.splitlines()
    bound = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                bound.append((node, a.asname or a.name.split(".")[0], a))
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for a in node.names:
                if a.name != "*":
                    bound.append((node, a.asname or a.name, a))
    used = set()
    quoted = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            quoted.append(node.returns)
        elif isinstance(node, ast.arg):
            quoted.append(node.annotation)
        elif isinstance(node, ast.AnnAssign):
            quoted.append(node.annotation)
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
                quoted.append(node.value)
    for q in quoted:
        for node in ast.walk(q) if q is not None else ():
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                used.update(WORD.findall(node.value))
    out = []
    for node, name, alias in bound:
        if name in used:
            continue
        if alias.asname and alias.asname == alias.name:
            continue                      # `import x as x` — a declared re-export
        span = range(node.lineno, (getattr(node, "end_lineno", None) or node.lineno) + 1)
        if any(NOQA.search(lines[n - 1]) for n in span if 0 < n <= len(lines)):
            continue
        out.append((node.lineno, name))
    return sorted(out)


class TestTheReaderSeesWhatItIsFor(unittest.TestCase):

    def test_the_two_shapes_that_went_out(self):
        self.assertEqual([(1, "json")], unused_imports("import json\nimport os\nos.getcwd()\n"))
        self.assertEqual([(1, "contextmanager")], unused_imports(
            "from contextlib import contextmanager, redirect_stdout\nredirect_stdout(None)\n"))

    def test_the_same_letters_in_a_string_are_not_a_use(self):
        self.assertEqual([(1, "json")], unused_imports("import json\nname = 'callset2-test.json'\n"))

    def test_the_exemptions_are_the_linters_own(self):
        text = '[tool.ruff.lint.per-file-ignores]\n# a facade\n"src/a/__init__.py" = ["F401"]\n[other]\n"x.py" = ["F401"]\n'
        self.assertEqual({"src/a/__init__.py"}, exempt_files(text))

    def test_what_is_not_a_finding(self):
        for source in ("import json  # noqa: F401\n",
                       "from a import (\n    b,  # noqa: F401\n)\n",
                       "from __future__ import annotations\n",
                       "import os.path\nos.getcwd()\n",
                       "from typing import List\nx: 'List[int]' = []\n",
                       "from a import b\n__all__ = ['b']\n",
                       "from a import b as b\n",
                       "import json\nname = 'callset.json'\njson.dumps(name)\n",
                       "def f():\n    import json\n    return json.dumps(1)\n"):
            with self.subTest(source=source):
                self.assertEqual([], unused_imports(source))


class TestNoImportIsLeftUnused(unittest.TestCase):

    def test_in_the_code_and_in_the_tests(self):
        bad = []
        exempt = exempt_files((support.ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        for top in ("src", "tests"):
            for f in sorted((support.ROOT / top).rglob("*.py")):
                if f.relative_to(support.ROOT).as_posix() in exempt:
                    continue
                try:
                    found = unused_imports(f.read_text(encoding="utf-8"))
                except SyntaxError:
                    continue                  # a fixture written to be broken
                bad += [f"{f.relative_to(support.ROOT)}:{line} {name}" for line, name in found]
        self.assertEqual([], bad, "imported and never read — remove it, or say why with # noqa: F401")


if __name__ == "__main__":
    unittest.main()
