"""Every reason a file can be set aside is a sentence in both languages.

`t('web.genome.why.' + x.why)` is composed at run time, so the static check that
guards literal keys cannot see it — by design, and the price is that this family
needs an owner. Without one, a new reason returned by `carved_from_a_genome`
reaches the page as ⟦web.genome.why.the_new_one⟧, in front of the reader, in one
language only, with no exception and no log.

The values are read off the function's own source rather than listed here: a list
in a test is a second copy of the enumeration, and copies drift — which is the
defect that started this whole repair.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import genome
from scholion.i18n import en, ru


def reasons():
    """Every string `carved_from_a_genome` can return, read off its source."""
    src = Path(genome.__file__).read_text(encoding="utf-8")
    body = src[src.index("def carved_from_a_genome("):]
    body = body[:body.index(chr(10) + "def ", 10)]
    return sorted(set(re.findall(r'return "([a-z_]+)"', body)))


class TestEveryReasonHasASentence(unittest.TestCase):

    def test_the_scan_finds_the_reasons_at_all(self):
        """A regex that matched nothing would pass every assertion below for ever."""
        self.assertGreaterEqual(len(reasons()), 3, reasons())

    def test_each_one_is_written_in_both_languages(self):
        for lang, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            for why in reasons():
                with self.subTest(lang=lang, why=why):
                    self.assertIn(f"web.genome.why.{why}", cat,
                                  "the page will print the key at the reader")

    def test_no_sentence_outlives_the_reason_it_explains(self):
        """The other direction: a phrase for a reason nobody returns any more is a
        line that reads as current and describes nothing."""
        live = {f"web.genome.why.{w}" for w in reasons()}
        for lang, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            stale = sorted(k for k in cat
                           if k.startswith("web.genome.why.") and k not in live)
            self.assertEqual([], stale, f"{lang}: explains a reason nothing returns")


if __name__ == "__main__":
    unittest.main()
