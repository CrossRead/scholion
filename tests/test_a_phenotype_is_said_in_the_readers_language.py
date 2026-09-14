"""A pharmacogenetic phenotype is said in the reader's language, hedge and all.

A star-allele call in the profile carries CPIC's English phrase for its
phenotype, and that phrase was printed as the label — English on a Russian page,
at the line a person reads about a drug. It is worded from what it names now.
The qualifier stays: «likely poor metabolizer» worded as «poor metaboliser»
would be a firmer claim than the call made. A phrase the table does not know is
printed as it came, never guessed at. The expected wording is read from the
catalogues, so this file holds no phrase of its own to drift from them.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import i18n
from scholion.engine.pgx_labels import phenotype_words
from scholion.i18n import en, ru


class _Lang:
    def __init__(self, lang):
        self.lang = lang

    def __enter__(self):
        self.old = i18n.lang()
        i18n.set_lang(self.lang)

    def __exit__(self, *exc):
        i18n.set_lang(self.old)


class TestAPhenotypePhrase(unittest.TestCase):

    def test_every_metaboliser_phenotype_is_worded_from_the_catalogue(self):
        for word, code in (("Normal", "NM"), ("Intermediate", "IM"), ("Poor", "PM"),
                           ("Rapid", "RM"), ("Ultrarapid", "UM")):
            for spelling in ("Metabolizer", "metaboliser"):
                phrase = f"{word} {spelling}"
                for lang, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
                    with self.subTest(phrase=phrase, lang=lang), _Lang(lang):
                        self.assertEqual(cat[f"phenotype.label.{code}"], phenotype_words(phrase))

    def test_a_function_phenotype_is_worded_from_the_catalogue(self):
        for word in ("normal", "decreased", "poor", "increased"):
            with self.subTest(word=word), _Lang("ru"):
                self.assertEqual(ru.MESSAGES[f"phenotype.function.{word}"],
                                 phenotype_words(f"{word.title()} Function"))

    def test_the_hedge_is_kept(self):
        with _Lang("ru"):
            want = ru.MESSAGES["phenotype.qualifier.likely"].format(label=ru.MESSAGES["phenotype.label.IM"])
            self.assertEqual(want, phenotype_words("Likely Intermediate Metabolizer"))
            want = ru.MESSAGES["phenotype.qualifier.possible"].format(label=ru.MESSAGES["phenotype.function.decreased"])
            self.assertEqual(want, phenotype_words("Possible Decreased Function"))
        with _Lang("en"):
            self.assertIn("likely", phenotype_words("Likely Poor Metabolizer"))

    def test_an_unknown_phrase_is_printed_as_it_came(self):
        for phrase in ("Indeterminate", "", "Poor Something", "Likely"):
            with self.subTest(phrase=phrase):
                self.assertEqual(phrase, phenotype_words(phrase))


if __name__ == "__main__":
    unittest.main()
