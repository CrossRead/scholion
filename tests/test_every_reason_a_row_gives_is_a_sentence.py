"""A reason is a sentence, and the vocabulary it is drawn from is enumerated.

On 13.09.2026 the owner's radar printed «не прочитано (coverage_gene_not_in_table)»
on 1120 gene rows: the reason a row gives is built as `coverage_<state>`, two
states were added to the coverage reader after the sentences were written, and
the fallback prints the code itself when a sentence is missing. A code in place
of a reason reads as a malfunction, and the reader cannot tell it from one.

The fallback stays — a row must still say something when a reason is new — but
nothing may reach a person through it. What this holds:

  * every coverage state the reader can return has a sentence in both languages,
    except the one state that is deliberately silent;
  * the enumerated vocabulary is the one the function actually assigns — the
    tuple is checked against the module's own source, so it cannot go stale
    while the test stays green;
  * the sentence is a sentence: not the code, and not a phrase that merely
    contains it.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion.engine import genomics
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru

#: The one state that says nothing: «not unusual for this file» is the state in
#: which a row is READ, and a reason belongs to a row that is not.
SILENT = "fine"


class TestTheVocabularyIsWhatTheCodeAssigns(unittest.TestCase):

    def test_the_tuple_holds_every_state_the_reader_assigns(self):
        src = Path(genomics.__file__).read_text(encoding="utf-8")
        assigned = set(re.findall(r'"state":\s*"([a-z_]+)"', src))
        assigned |= set(re.findall(r'\["state"\]\s*=\s*"([a-z_]+)"', src))
        self.assertTrue(assigned, "the states are no longer written as literals — adjust the scan")
        missing = sorted(assigned - set(genomics.COVERAGE_STATES))
        self.assertEqual([], missing,
                         "a coverage state the reader assigns is not in COVERAGE_STATES: "
                         + ", ".join(missing))


class TestEveryReasonIsASentence(unittest.TestCase):

    def test_every_coverage_state_has_a_sentence_in_both_languages(self):
        for state in genomics.COVERAGE_STATES:
            if state == SILENT:
                continue
            code = "coverage_" + state
            for lang, words in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
                with self.subTest(state=state, lang=lang):
                    key = "system.read_why." + code
                    self.assertIn(key, words, f"{code} has no sentence — a row would print the code")
                    text = words[key]
                    self.assertNotIn(code, text, "the sentence is the code with words around it")
                    self.assertGreater(len(text.split()), 3, "not a sentence")

    def test_the_engine_turns_a_state_into_that_sentence(self):
        for state in genomics.COVERAGE_STATES:
            if state == SILENT:
                continue
            code = "coverage_" + state
            with self.subTest(state=state):
                text = SP._read_why_text(code)
                self.assertNotEqual(code, text,
                                    "the fallback printed the code: no sentence for " + code)
                self.assertEqual(en.MESSAGES["system.read_why." + code], text)

    def test_the_fallback_still_answers_for_a_reason_nobody_has_written(self):
        self.assertEqual("weather_on_mars", SP._read_why_text("weather_on_mars"),
                         "a row must say something even when the reason is new")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
