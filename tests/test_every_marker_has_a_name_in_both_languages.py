"""Every marker of the base has a display name in both languages (owner, 17.09.2026).

323 of 425 markers had no Russian display name, so a Russian card printed «TSH»
and «Uric acid» beside Russian sentences — the mixed page the owner reported in
0.5.1. The name a person reads is now written for every marker in both
languages; recognition names stay what they were, because they are input.
"""
from __future__ import annotations

import json
import re
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import core

CYRILLIC = re.compile(r"[А-Яа-яЁё]")


class TestEveryMarkerIsNamed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(core.knowledge_path("lab_markers.json").read_text(encoding="utf-8"))["markers"]

    def test_both_languages_are_there(self):
        for key, spec in self.base.items():
            labels = spec.get("labels") or {}
            with self.subTest(marker=key):
                self.assertTrue((labels.get("en") or {}).get("display"))
                self.assertTrue((labels.get("ru") or {}).get("display"))

    def test_the_english_name_is_not_russian(self):
        wrong = [k for k, v in self.base.items() if CYRILLIC.search(v["labels"]["en"]["display"])]
        self.assertEqual([], wrong)

    def test_a_russian_card_names_a_marker_in_russian(self):
        self.assertEqual("Тиреотропный гормон (ТТГ)", core.marker_display(self.base["tsh"], "ru"))
        self.assertEqual("Мочевая кислота", core.marker_display(self.base["uric_acid"], "ru"))


if __name__ == "__main__":
    unittest.main()
