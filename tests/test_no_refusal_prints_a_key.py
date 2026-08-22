"""No path of refusal may print a message-catalogue key at a person.

Task 88. The head of a refused locus was built by gluing a value onto a prefix —
`"genome.refused_head." + confidence`. `confidence` is not an enumeration of
refusal reasons; two of its values had no line in either language, and the
resolver did what it is designed to do with an unknown key: it printed the key.
So the commonest question anybody asks of a consumer chip — «what is my APOE» —
answered with ⟦genome.refused_head.not_on_chip⟧, in six of the twelve arrays of
the reference corpus.

A missing line is a translation problem. A missing line reaching a person is a
different problem, and it is this one. The check walks the source for every
literal that can arrive at that head and demands a line for it in BOTH
languages, because the next value will be added the same way this one was.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "scholion"

#: The two modules whose dictionaries reach the locus report. Narrowed on
#: purpose: `reason` is a common field name and half the package uses it for
#: something else, so a package-wide sweep would demand a refusal sentence for
#: an unparsed lab date.
_MODULES = ("genome.py", "array_genome.py")


def _literals(field: str, modules=_MODULES) -> set:
    """Every string literal ever assigned to `field` in a dict in those modules."""
    out = set()
    for path in [SRC / m for m in modules]:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and k.value == field
                        and isinstance(v, ast.Constant) and isinstance(v.value, str)):
                    out.add(v.value)
    return out


def _catalogue(lang: str) -> dict:
    ns: dict = {}
    exec(compile((SRC / "i18n" / f"{lang}.py").read_text(encoding="utf-8"),
                 f"{lang}.py", "exec"), ns)
    best = max((v for v in ns.values() if isinstance(v, dict)), key=len, default=None)
    if not best or len(best) < 500:
        raise AssertionError(f"no catalogue found in {lang}.py")
    return best


class TestEveryRefusalHasASentence(unittest.TestCase):
    def test_every_reachable_head_has_a_line_in_both_languages(self):
        en, ru = _catalogue("en"), _catalogue("ru")
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from scholion.genome import REFUSAL_REASONS
        # Three sources, and all three have put a value in front of a reader.
        # `confidence` is the one that leaked; `status` from the array reader is
        # copied straight into `confidence` by `genome._gt_at`; `reason` is the
        # enumeration the status command answers with.
        wanted = set(REFUSAL_REASONS)
        wanted |= _literals("confidence")
        wanted |= _literals("reason")
        wanted |= _literals("status", ("array_genome.py",))
        missing_en = sorted(k for k in wanted if f"genome.refused_head.{k}" not in en)
        missing_ru = sorted(k for k in wanted if f"genome.refused_head.{k}" not in ru)
        self.assertEqual([], missing_en,
                         "these can reach the refusal head and have no English line")
        self.assertEqual([], missing_ru,
                         "these can reach the refusal head and have no Russian line")

    def test_the_fallback_never_returns_a_key(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from scholion.format import _refused_head
        for value in (None, "", "a_value_nobody_has_written_yet"):
            head = _refused_head(value)
            self.assertNotIn("⟦", head, f"a key leaked for {value!r}")
            self.assertNotIn("genome.refused_head", head)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
