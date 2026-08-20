"""The message catalogues do not diverge, and the language is chosen predictably.

Two lists of phrases edited by hand always diverge — the only question is
whether a test notices it or a reader does. What is more, they diverge quietly:
a missing key does not break the program, it merely prints an English phrase in
the middle of a Russian report, and that looks like sloppiness on the author's
part rather than a defect.

Worse than a missing key is a lost placeholder. The phrase "current
abnormalities: {abnormal}", from which `{abnormal}` fell out during
translation, is printed without the number — and in a health report a hole
where the number should be reads as "there were no measurements". That is why
not only the keys are compared, but also the sets of placeholders inside each
of them.
"""
from __future__ import annotations

import re
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import i18n

PLACEHOLDER = re.compile(r"\{(\w+)\}")


class TestCatalogues(unittest.TestCase):

    def setUp(self):
        self.reference = i18n.CATALOGUES[i18n.DEFAULT]

    def test_languages_are_declared(self):
        self.assertIn(i18n.DEFAULT, i18n.available())
        self.assertIn("ru", i18n.available(), "the Russian catalogue must be present in the build")

    def test_key_sets_match(self):
        for code, catalogue in i18n.CATALOGUES.items():
            if code == i18n.DEFAULT:
                continue
            with self.subTest(language=code):
                missing = sorted(set(self.reference) - set(catalogue))
                extra = sorted(set(catalogue) - set(self.reference))
                self.assertEqual(missing, [], f"«{code}» is missing keys: " + ", ".join(missing[:10]))
                self.assertEqual(extra, [], f"«{code}» has keys the reference does not "
                                            f"(a rename left half-done?): " + ", ".join(extra[:10]))

    def test_placeholders_match(self):
        for code, catalogue in i18n.CATALOGUES.items():
            if code == i18n.DEFAULT:
                continue
            for key, reference_phrase in self.reference.items():
                if key not in catalogue:
                    continue
                with self.subTest(language=code, key=key):
                    self.assertEqual(
                        set(PLACEHOLDER.findall(catalogue[key])),
                        set(PLACEHOLDER.findall(reference_phrase)),
                        f"«{key}»: the set of placeholders has diverged — the phrase will print "
                        f"without the number, or crash on substitution")

    def test_there_are_no_empty_phrases(self):
        for code, catalogue in i18n.CATALOGUES.items():
            empty = sorted(k for k, v in catalogue.items() if not v.strip())
            self.assertEqual(empty, [], f"«{code}» has empty phrases: " + ", ".join(empty[:10]))

    def test_no_key_is_defined_twice(self):
        """A key written twice is invisible to every other test here.

        The catalogues are dict literals: a repeated key does not raise, it
        silently wins over the earlier one, and by the time the tests see a
        catalogue it is already a dict with the duplicate collapsed. So the
        comparison of key sets — the check written to keep the catalogues
        honest — cannot see this class at all, and the audit found six such
        keys (`count.nights.*` in both languages) that no gate had reported.
        This one reads the source text instead of the loaded object, because
        that is the only place where the duplicate still exists.
        """
        import collections
        from pathlib import Path
        here = Path(i18n.__file__).resolve().parent
        for code in sorted(i18n.CATALOGUES):
            path = here / f"{code}.py"
            if not path.exists():
                continue
            with self.subTest(language=code):
                keys = re.findall(r'^\s*"([^"]+)"\s*:', path.read_text(encoding="utf-8"), re.M)
                twice = sorted(k for k, n in collections.Counter(keys).items() if n > 1)
                self.assertEqual(twice, [], f"«{code}» defines a key more than once "
                                            f"(the second definition wins silently): "
                                            + ", ".join(twice[:10]))

    def test_plural_forms_are_complete(self):
        """A key with forms must have all the forms of its own language.

        English makes do with two, Russian needs three. A missing form produces
        "⟦count.markers.few⟧" in the report — that is, an internal identifier
        instead of text.
        """
        stems = {k.rsplit(".", 1)[0] for k in self.reference if k.rsplit(".", 1)[-1] in ("one", "few", "many")}
        for stem in sorted(stems):
            with self.subTest(stem=stem):
                self.assertIn(f"{stem}.one", self.reference)
                self.assertIn(f"{stem}.many", self.reference)
                ru = i18n.CATALOGUES["ru"]
                for form in ("one", "few", "many"):
                    self.assertIn(f"{stem}.{form}", ru,
                                  f"Russian needs all three forms, «{form}» is missing")


class TestLanguageChoice(unittest.TestCase):

    def tearDown(self):
        i18n.set_lang(None)

    def test_the_default_is_english(self):
        i18n.set_lang(None)
        self.assertEqual(i18n.DEFAULT, "en")

    def test_an_explicit_choice_beats_the_environment(self):
        self.assertEqual(i18n.set_lang("ru"), "ru")
        self.assertIn("Обзор", i18n.t("overview.title"))

    def test_an_unknown_language_does_not_break_anything(self):
        """A shortcut with `SCHOLION_LANG=de` is obliged to print in English rather than crash.

        Refusing to start because of a language preference is a worse answer than
        printing in a language everybody reads.
        """
        self.assertEqual(i18n.set_lang("de"), i18n.DEFAULT)
        self.assertNotIn("⟦", i18n.t("overview.title"))

    def test_a_missing_key_is_visible_as_a_defect(self):
        self.assertEqual(i18n.t("no.such.key"), "⟦no.such.key⟧")

    def test_a_missing_placeholder_is_not_printed_silently(self):
        """Half a phrase in a medical report is worse than an explicit error."""
        with self.assertRaises(KeyError):
            i18n.t("overview.counts", total=1)      # abnormal is missing

    def test_russian_plural_forms(self):
        i18n.set_lang("ru")
        self.assertEqual(i18n.plural(1, "count.markers"), "1 показатель")
        self.assertEqual(i18n.plural(3, "count.markers"), "3 показателя")
        self.assertEqual(i18n.plural(11, "count.markers"), "11 показателей")
        self.assertEqual(i18n.plural(21, "count.markers"), "21 показатель")

    def test_english_plural_forms(self):
        i18n.set_lang("en")
        self.assertEqual(i18n.plural(1, "count.markers"), "1 marker")
        self.assertEqual(i18n.plural(5, "count.markers"), "5 markers")

    def test_a_placeholder_may_be_named_after_the_signature(self):
        """`t()` must not reserve any placeholder name for itself.

        A catalogue phrase is free to use `{key}` or `{n}` — those names belong
        to the phrase, not to this function. When they were ordinary parameters,
        `t("brief.no_metric", key=key)` raised TypeError, and it did so on the
        most ordinary path there is: a metric that simply has no value. The
        report died where it should have printed "no such metric".
        """
        for name in ("key", "n"):
            with self.subTest(placeholder=name):
                i18n.CATALOGUES[i18n.DEFAULT]["_probe"] = "[%s]" % ("{%s}" % name)
                try:
                    self.assertEqual(i18n.t("_probe", **{name: "x"}), "[x]")
                finally:
                    del i18n.CATALOGUES[i18n.DEFAULT]["_probe"]

    def test_the_real_call_site_that_used_to_crash(self):
        from scholion import engine
        self.assertIn("no-such-metric", engine._brief_life("no-such-metric")["text"])


if __name__ == "__main__":
    unittest.main()
