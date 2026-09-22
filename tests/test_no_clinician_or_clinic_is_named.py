"""No clinician and no clinic is named in anything that travels.

The owner's decision of 21.09.2026: the name of the clinic whose doctors review
the panels, and their names and initials, are not included anywhere. A reviewed
sentence carries a role and a date (`review {by_role, on, scope}`), never a
person; a local note that names its author lives in the profile and never ships.

The question came up because a clinician, asked who signs, offered the clinic's
name instead of her own — a generous answer, and one that would read as the
clinic endorsing the product. The rule is written for every name of this kind,
not for that one answer.

The names themselves may not appear here either: this file travels with the
package. So the test holds SHA-256 digests of lower-cased stems and compares the
start of every word against them. A stem, not a word, because Russian declines
names — the genitive, the prepositional, the instrumental — and a check on whole
words would pass every case but the one it was written with.
"""
from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

import support

#: stem length → digests of stems that must not start any word in a shipped file
_FORBIDDEN = {
    7: {"1e17b04e14d6e73710f4860f57b0de65a7ff76a92b67a16f3abbf58bb1daba9a",
        "36a5bc82b9477af6f77ab49cd88df9cdf9d6543fa62de9d1cbe1d683ad47750e",
        "381ad3bb4b02a11a1981dd58a847133ca2d4af66ff981c556175e7ca4f74226f",
        "b5ae92db3fa10a822fda7d992896ab13fac35b9cf3574faf2b74b49fba6adef0",
        "fc10ecfe126e2287bbdab4845133ada9fdb47c3123f97c69db17801bd4d41d40"},
    8: {"8227b8a3e9a1421256c407344800fb17073a3e35be3d8ab695ad6f32fdf44cc0",
        "e308bd57d010b614ace92d37588144b34a34c793b355bbfdcf230d02315a5ccc"},
    10: {"991c37a237373bd1aec7707fa29610413281c64fcd1f62cd570092a742ca8821"},
}
#: Real words that share a forbidden stem and are not a name of this kind.
_ALLOWED = {"archimedes", "archimedean"}

_WORD = re.compile(r"[0-9A-Za-z\u0401\u0410-\u044f\u0451]+")
_TEXT = {".py", ".json", ".md", ".txt", ".html", ".js", ".css", ".sh", ".toml", ".cff", ".yml", ".yaml", ""}

#: What travels: the package's own include list, plus what the public repository
#: carries beside it — the pages, the plugin packages and the documents.
_PATHS = ("src/scholion", "src/tools", "src/ingest", "tests", "docs", "share", "agent-plugin",
          "ouroboros_plugin", "README.md", "CHANGELOG.md", "CONTRIBUTING.md", "DISCLAIMER.md",
          "SECURITY.md", "THREAT_MODEL.md", "CITATION.cff", "ASSISTANT-RULES.md")


def named(text: str):
    """The words of `text` that start with a forbidden stem."""
    hits = []
    for w in _WORD.findall(text):
        low = w.lower()
        if low in _ALLOWED:
            continue
        for n, digests in _FORBIDDEN.items():
            if len(low) >= n and hashlib.sha256(low[:n].encode()).hexdigest() in digests:
                hits.append(w)
                break
    return hits


def _files():
    for rel in _PATHS:
        base = support.ROOT / rel
        if not base.exists():
            continue
        for f in ([base] if base.is_file() else sorted(base.rglob("*"))):
            if f.is_file() and f.suffix.lower() in _TEXT and "__pycache__" not in f.parts:
                yield f


class TestNoOneIsNamed(unittest.TestCase):

    def test_nothing_that_travels_names_a_clinician_or_a_clinic(self):
        found = []
        for f in _files():
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            words = named(text)
            if words:
                # The file and the count, not the words: the report would print the name.
                found.append(f"{f.relative_to(support.ROOT)}: {len(words)}")
        self.assertEqual([], found, "a clinician or a clinic is named in what travels")

    def test_the_check_sees_a_declined_form_and_lets_an_ordinary_word_pass(self):
        """Proven on a digest built here, so the test does not have to spell a real name."""
        stem = "smithso"
        _FORBIDDEN.setdefault(len(stem), set()).add(hashlib.sha256(stem.encode()).hexdigest())
        try:
            self.assertEqual(["Smithsonova"], named("seen by Dr Smithsonova today"))
            self.assertEqual([], named("smith smiths smithy"))
        finally:
            _FORBIDDEN[len(stem)].discard(hashlib.sha256(stem.encode()).hexdigest())

    def test_a_word_that_is_not_a_name_is_allowed_by_name(self):
        self.assertEqual([], named("Archimedes"))


if __name__ == "__main__":
    unittest.main()
