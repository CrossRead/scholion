"""Numbers nobody published are marked as such, and cannot join quietly.

The reviewers' strongest single correction to our own account of ourselves: three
of the four numeric thresholds in the lab and genome layers were written up as
«considered engineering decisions» and are nothing of the kind. They are an
author's preferences. A product has to draw a line somewhere, so having them is
fine; printing them in the same voice as a guideline is not, because a number
with no document behind it then borrows an authority it does not have.

So each is registered with what would replace it and — the field that matters —
what it does NOT license. And the registry is enforced by enumeration rather than
by memory: any module-level numeric constant in these modules must be either
registered or excused by name here, so the next magic number cannot arrive
silently the way these did.

Also here: the declared minimum Python. `pyproject.toml` tells pip `>=3.10` and
pip obeys, but a source tree, a vendored copy or a system Python bypasses that
metadata entirely — the reviewers ran the package on 3.9.6 and nothing said a
word.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
import scholion
from scholion import limits
from scholion.engine import labs

#: Constants that are NOT thresholds — they describe a format, a size or an
#: index, and no external document could ever «replace» them. Excused by name so
#: that the excuse itself is visible.
NOT_A_THRESHOLD = {
    "MINIMUM_PYTHON",
    "INTERVAL_BASIS_DEFAULT",
}


def _module_constants(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or not target.id.isupper():
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, (int, float)) \
                    and not isinstance(node.value.value, bool):
                out[target.id] = node.value.value
    return out


class TestEveryAuthorSettingIsDeclared(unittest.TestCase):

    MODULES = {"scholion.limits": (limits, Path(limits.__file__)),
               "scholion.engine.labs": (labs, Path(labs.__file__))}

    def test_no_unregistered_numeric_constant(self):
        for name, (mod, path) in self.MODULES.items():
            registered = set(getattr(mod, "AUTHOR_SETTINGS", {}))
            for const in _module_constants(path):
                if const in NOT_A_THRESHOLD or const.startswith("_"):
                    continue
                with self.subTest(module=name, constant=const):
                    self.assertIn(const, registered,
                                  f"{name}.{const} is a number nobody published and it is not "
                                  f"registered in AUTHOR_SETTINGS. Register it with what would "
                                  f"replace it and what it does not license, or excuse it by "
                                  f"name in NOT_A_THRESHOLD here.")

    def test_every_entry_says_what_it_does_not_license(self):
        for name, (mod, _path) in self.MODULES.items():
            for const, entry in getattr(mod, "AUTHOR_SETTINGS", {}).items():
                with self.subTest(module=name, constant=const):
                    for field in ("value", "basis", "closes", "does_not_license"):
                        self.assertTrue(str(entry.get(field, "")).strip(),
                                        f"{const}: «{field}» is empty — an entry without it is "
                                        f"a label, not a declaration")
                    self.assertEqual(entry["value"], getattr(mod, const),
                                     "the registry and the constant have drifted apart")

    def test_the_registry_names_the_four_the_review_named(self):
        registered = set(limits.AUTHOR_SETTINGS) | set(labs.AUTHOR_SETTINGS)
        for expected in ("WEAK_10X", "PRS_MIN_MATCH", "MOVE_MIN_SD", "NEAR_LIMIT_FRACTION"):
            with self.subTest(constant=expected):
                self.assertIn(expected, registered)


class TestTheDeclaredPythonMinimumIsEnforced(unittest.TestCase):

    def test_the_package_states_a_minimum(self):
        self.assertEqual(scholion.MINIMUM_PYTHON, (3, 10))

    def test_the_declaration_and_the_guard_agree(self):
        text = (support.ROOT / "pyproject.toml").read_text(encoding="utf-8")
        m = re.search(r'requires-python\s*=\s*"[><=~^]*([0-9]+)\.([0-9]+)', text)
        self.assertIsNotNone(m, "pyproject.toml states no minimum at all")
        self.assertEqual((int(m.group(1)), int(m.group(2))), scholion.MINIMUM_PYTHON,
                         "pip is told one minimum and the code enforces another")

    def test_the_guard_refuses_rather_than_warning(self):
        real = scholion.MINIMUM_PYTHON
        try:
            scholion.MINIMUM_PYTHON = (99, 0)
            with self.assertRaises(RuntimeError) as cm:
                scholion._check_python()
            self.assertIn("99.0", str(cm.exception))
        finally:
            scholion.MINIMUM_PYTHON = real


if __name__ == "__main__":
    unittest.main()
