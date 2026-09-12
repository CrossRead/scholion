"""A phrase keyed by genotype state inside `text` is curated text, and resolves to one language.

Task 168, item D. A position in `system_gene_panels.json` carries its author's
phrase per STATE of the genotype — `text.absent`, `text.het`, `text.hom` — each
a map of two languages. To the resolver `text` was a curated field whose value
was «not a language map», so it was returned untouched and the maps inside it
would have printed raw into a report the day the first position was authored;
to the audit of stray language maps the same maps sat under a field it did not
know. Both now read the state names as curated fields, and the resolver walks
into a curated field that turns out to be a container. Checked on a synthetic
authored position, because the shipped file is deliberately empty.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401
from scholion import core


POSITION = {"rsid": "rs0", "gene": "GX", "mode": "monogenic", "source": "an author",
            "text": {"absent": None,
                     "het": {"en": "one copy: E", "ru": "one copy: R"},
                     "hom": {"en": "two copies: E", "ru": "two copies: R"}},
            "expect": {"marker": "tsh", "direction": "lower",
                       "note": {"en": "why E", "ru": "why R"}}}


class TestTheStatePhrasesResolve(unittest.TestCase):

    def test_each_state_resolves_to_the_requested_language(self):
        out = core._localize_tree({"systems": {"thyroid": {"positions": [POSITION]}}}, "ru")
        p = out["systems"]["thyroid"]["positions"][0]
        self.assertEqual("one copy: R", p["text"]["het"])
        self.assertEqual("two copies: R", p["text"]["hom"])
        self.assertIsNone(p["text"]["absent"], "a state with no phrase stays empty, not a key")
        self.assertEqual("why R", p["expect"]["note"])
        en = core._localize_tree({"p": POSITION}, "en")["p"]
        self.assertEqual("one copy: E", en["text"]["het"])

    def test_a_plain_text_field_is_still_one_string(self):
        out = core._localize_tree({"text": {"en": "E", "ru": "R"}}, "en")
        self.assertEqual("E", out["text"])

    def test_the_state_names_are_curated_fields_for_the_audit(self):
        """The audit in tests/test_localized_fields.py allows a language map
        under a name in LOCALIZABLE_FIELDS; the three states are listed so that
        an authored position does not fail it — and only those three."""
        for state in ("absent", "het", "hom"):
            self.assertIn(state, core.LOCALIZABLE_FIELDS)
        self.assertNotIn("het", core.COMPARED_NOT_TRANSLATED)

    def test_the_engine_reads_the_resolved_phrase(self):
        """`one_language` is what the system entry reads the phrase through, and
        a string is left as it is — so the resolved file and the raw file give
        the same sentence."""
        from scholion.engine.panel_form import one_language
        raw = POSITION["text"]["het"]
        resolved = core._localize_tree({"text": POSITION["text"]}, "en")["text"]["het"]
        self.assertEqual(one_language(raw), one_language(resolved))


if __name__ == "__main__":
    unittest.main()
