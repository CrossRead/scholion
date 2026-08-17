"""Multilingual knowledge fields resolve to one language, with a source-language fallback.

The rule this pins down is a project-wide one: **the language of the data belongs
to the data, the language of the frame belongs to the interface.** A curated field
written by the project can be a per-language map; a value that arrived from a
person's own document is printed exactly as it was written, because the report has
to match the paper they are holding.

Two failures are guarded against here, and they fail in opposite directions.

Printing a raw `{'en': ..., 'ru': ...}` into a report is the loud one — it looks
like a bug and someone fixes it. Silently printing nothing because the requested
language is missing is the quiet one, and it is worse: a person reading about
their own health cannot tell an empty explanation from an explanation that does
not exist. Hence the fallback goes to the language of the source rather than to an
empty string, and hence a resolver in the loader rather than a rule that two dozen
call sites have to remember.
"""
from __future__ import annotations

import json
import re
import unittest

import support  # noqa: F401
from scholion import core, i18n


class TestResolution(unittest.TestCase):

    def tearDown(self):
        i18n.set_lang(None)

    def test_the_requested_language_wins(self):
        self.assertEqual(core._localized({"en": "Iron", "ru": "Железо"}, "ru"), "Железо")
        self.assertEqual(core._localized({"en": "Iron", "ru": "Железо"}, "en"), "Iron")

    def test_a_missing_language_falls_back_to_the_source(self):
        """A phrase that exists in one language only is printed in that language.

        Not an empty string and not the key: an explanation about someone's own
        health is worth more in the wrong language than absent in the right one.
        """
        self.assertEqual(core._localized({"ru": "Только по-русски"}, "en"), "Только по-русски")
        self.assertEqual(core._localized({"de": "Nur Deutsch"}, "en"), "Nur Deutsch")

    def test_a_plain_string_is_left_alone(self):
        self.assertEqual(core._localized("plain text", "ru"), "plain text")

    def test_an_ordinary_object_is_not_mistaken_for_a_language_map(self):
        """`{'value': 1}` is data, not a translation. Only two-letter alphabetic
        keys are treated as languages, so a nested object survives untouched."""
        obj = {"value": 1, "unit": "mmol/L"}
        self.assertEqual(core._localized(obj, "en"), obj)
        # Two-letter keys are not enough on their own: a translation maps a
        # language to TEXT. `{"ab": 1}` is a lookup table that happens to have
        # short keys, and resolving it would silently replace a structure with
        # one of its numbers.
        self.assertEqual(core._localized({"ab": 1, "cd": 2}, "en"), {"ab": 1, "cd": 2})

    def test_only_curated_fields_are_resolved(self):
        """A field nobody curated keeps whatever it holds."""
        tree = {"m": {"note": {"en": "E", "ru": "R"}, "raw": {"en": "x", "ru": "h"}}}
        out = core._localize_tree(tree, "ru")
        self.assertEqual(out["m"]["note"], "R")
        self.assertEqual(out["m"]["raw"], {"en": "x", "ru": "h"},
                         "an unlisted field must not be resolved")

    def test_a_persons_own_data_is_never_localized(self):
        """The resolver is scoped to the knowledge directory, and that scoping is
        the whole reason `unit` can be curated in one place and untouchable in
        another.

        A unit inside `wearable_metrics.json` is ours: we defined the metric, so
        it is written in both languages. A unit inside somebody's `labs.json`
        came off their lab form, and printing anything else there would make the
        report disagree with the paper in their hand. Same field name, two
        owners — told apart by which file it lives in, not by its name.
        """
        profile = support.FIXTURE_PROFILE / "labs.json"
        raw = json.loads(profile.read_text(encoding="utf-8"))
        for code in ("en", "ru"):
            i18n.set_lang(code)
            core.reset_cache()
            again = json.loads(profile.read_text(encoding="utf-8"))
            self.assertEqual(again, raw,
                             "profile data changed with the language — the resolver "
                             "reached outside the knowledge directory")
        i18n.set_lang(None)


class TestNoRawMapsReachReports(unittest.TestCase):
    """No language map may survive into a rendered report.

    Checked against the real knowledge base rather than a fixture: the defect this
    catches is a field added to a JSON file without being added to the resolver's
    list, and only the real files can show that.
    """

    def _kb_files(self):
        return sorted(core._KNOWLEDGE_DIR.glob("*.json"))

    def test_every_language_map_sits_in_a_curated_field(self):
        stray = []
        for path in self._kb_files():
            data = json.loads(path.read_text(encoding="utf-8"))

            def walk(node, key=None, trail="", parent=None):
                if isinstance(node, dict):
                    is_language_map = bool(node) and all(
                        isinstance(k, str) and len(k) == 2 and k.isalpha() for k in node)
                    # Legal in two shapes: a curated FIELD, or any value inside a
                    # curated CONTAINER — an object whose keys are data (the name
                    # of an alternative, a ClinVar review status) and whose values
                    # are prose. A field-name rule cannot reach inside those.
                    # A third legal shape: a STRUCTURAL language map, whose values
                    # are objects rather than prose and which a dedicated accessor
                    # reads (see core.STRUCTURAL_LANGUAGE_MAPS). Allowed only when
                    # the values really are structure — a prose map that sneaks in
                    # under such a name would still print raw, so the shape is
                    # checked and not just the name.
                    structural = (key in getattr(core, "STRUCTURAL_LANGUAGE_MAPS", set())
                                  and all(isinstance(v, dict) for v in node.values()))
                    allowed = (key in core.LOCALIZABLE_FIELDS
                               or parent in core.LOCALIZABLE_CONTAINERS
                               or structural)
                    if is_language_map and not allowed:
                        stray.append(f"{path.name}: {trail} (field «{key}»)")
                        return
                    if is_language_map and structural:
                        # Walk INTO it: the fields inside each language are ordinary
                        # fields and get the ordinary audit. Stopping here would make
                        # the name a blanket exemption for everything below it.
                        for k, v in node.items():
                            walk(v, key, f"{trail}.{k}", key)
                        return
                    for k, v in node.items():
                        walk(v, k, f"{trail}.{k}", key)
                elif isinstance(node, list):
                    for v in node:
                        walk(v, key, trail, parent)

            walk(data)
        self.assertEqual(stray, [], "a language map in a field the resolver does not know — "
                                    "it would print raw into a report:\n  " + "\n  ".join(stray[:10]))

    def test_both_languages_render_without_raw_maps(self):
        for code in ("en", "ru"):
            with self.subTest(language=code):
                i18n.set_lang(code)
                core.reset_cache()
                for path in self._kb_files():
                    text = json.dumps(core._read_knowledge(path.name), ensure_ascii=False)
                    for field in sorted(core.LOCALIZABLE_FIELDS):
                        for opening in ('{"en"', '{"ru"'):
                            self.assertNotIn(f'"{field}": {opening}', text,
                                             f"{path.name}: «{field}» stayed a map after resolution")
        i18n.set_lang(None)
        core.reset_cache()


class TestComparedValuesStayLiteral(unittest.TestCase):
    """A value the code compares must never become a translation.

    `quality_label` is ranked, `level` selects an icon, `severity` orders
    interactions. Translate one of those and nothing raises — the ranking simply
    comes out wrong, quietly, in a report about somebody's health. The two sets
    are therefore kept disjoint by a test rather than by care.
    """

    def test_the_two_sets_do_not_overlap(self):
        overlap = sorted(core.LOCALIZABLE_FIELDS & core.COMPARED_NOT_TRANSLATED)
        self.assertEqual(overlap, [], "a field is both translated and compared: " + ", ".join(overlap))

    def test_no_compared_field_holds_a_language_map(self):
        offenders = []
        for path in sorted(core._KNOWLEDGE_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))

            def walk(node, key=None):
                if isinstance(node, dict):
                    if key in core.COMPARED_NOT_TRANSLATED and node and all(
                            isinstance(k, str) and len(k) == 2 and k.isalpha() for k in node):
                        offenders.append(f"{path.name}: «{key}»")
                        return
                    for k, v in node.items():
                        walk(v, k)
                elif isinstance(node, list):
                    for v in node:
                        walk(v, key)

            walk(data)
        self.assertEqual(offenders, [], "a compared value was turned into a translation: "
                                        + ", ".join(offenders))


if __name__ == "__main__":
    unittest.main()
