"""C2 of the 0.6.0 brief: no module holds a person's data path from import time.

A switch of container (task 192) is a change of what `core.repo_dir()`
returns. It reaches every reader only because every reader asks: a module
that computed `PROFILE = core.profile_dir() / "labs.json"` at import would go
on reading the first person for the life of the process — the web server's
life, on a clinician's machine — and nothing would look wrong.

Two places run at import and are walked here: module- and class-level
assignments, and the default values of function arguments. Parsed, not
grepped, so a docstring that explains the mistake is not the mistake.
"""
from __future__ import annotations

import ast
import unittest

import support

PKG = support.SRC / "scholion"

#: Every function whose answer is a person's folder or file.
DATA_PATHS = {"repo_dir", "profile_dir", "slot_dir", "raw_dir", "work_dir", "archive_dir",
              "cache_dir", "genome_dir", "genome_bases", "knowledge_dir_local", "source_path",
              "markers_overlay_path", "markers_overlay_read_path", "ingest_manifest_path",
              "active_dir", "home", "chosen_genome_vcf", "chosen_genome_bam",
              "chosen_genome_reference"}


def _calls_a_data_path(node: ast.AST) -> list:
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if name in DATA_PATHS:
                out.append(name)
    return out


def import_time_paths(source: str) -> list:
    """(line, function) of every data path computed when the module is imported."""
    tree = ast.parse(source)
    found = []

    def walk_body(body):
        for stmt in body:
            if isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)) and stmt.value is not None:
                found.extend((stmt.lineno, n) for n in _calls_a_data_path(stmt.value))
            elif isinstance(stmt, ast.ClassDef):
                walk_body(stmt.body)
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = stmt.args
                for d in list(args.defaults) + [d for d in args.kw_defaults if d is not None]:
                    found.extend((stmt.lineno, n) for n in _calls_a_data_path(d))
            if isinstance(stmt, ast.ClassDef):
                for sub in stmt.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for d in list(sub.args.defaults) + [d for d in sub.args.kw_defaults if d]:
                            found.extend((sub.lineno, n) for n in _calls_a_data_path(d))
    walk_body(tree.body)
    return found


class TestNoModuleRemembersWhoseDataItRead(unittest.TestCase):

    def test_the_package_computes_no_data_path_at_import(self):
        offenders = {}
        for f in sorted(PKG.rglob("*.py")):
            hits = import_time_paths(f.read_text(encoding="utf-8"))
            if hits:
                offenders[str(f.relative_to(PKG))] = hits
        self.assertEqual({}, offenders,
                         "these modules compute a person's path when they are imported, so a "
                         "switch of container never reaches them; compute it inside the "
                         "function that uses it")

    def test_the_walk_sees_what_it_is_looking_for(self):
        """A walk that finds nothing passes for ever; each shape is planted once."""
        planted = (
            "from scholion import core\nLABS = core.profile_dir() / 'labs.json'\n",
            "from scholion.core import cache_dir\nX: str = str(cache_dir())\n",
            "def read(path=core.slot_dir('raw')):\n    pass\n",
            "class A:\n    WHERE = core.repo_dir()\n",
            "def read(*, path=core.work_dir()):\n    pass\n",
        )
        for src in planted:
            with self.subTest(src=src):
                self.assertTrue(import_time_paths(src), "the walk missed a planted path")
        self.assertEqual([], import_time_paths(
            "def labs():\n    return core.profile_dir() / 'labs.json'\n"))

    def test_the_walk_covers_the_package(self):
        self.assertGreater(len(list(PKG.rglob("*.py"))), 80)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
