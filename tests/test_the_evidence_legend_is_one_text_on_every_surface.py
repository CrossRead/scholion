"""The legend of evidence levels is one text, and every surface reads it (task 199).

A level is only as useful as the reader's idea of what it means, and five
explanations in five places drift into five meanings. The words live in
`knowledge/evidence_levels.json`; the command line, the page and the docs page
print them, and the canon tells an assistant to name the level with the claim.
"""
from __future__ import annotations

import json
import unittest

import support
from scholion import core
from scholion.engine import panel_gate as G
from scholion.i18n import en, ru

LEVELS = ("A", "B", "C", "D", "E")


def _raw():
    return json.loads(core.knowledge_path("evidence_levels.json").read_text(encoding="utf-8"))


class TestTheLegend(unittest.TestCase):

    def test_five_levels_in_order_and_both_languages(self):
        levels = _raw()["levels"]
        self.assertEqual(LEVELS, tuple(x["level"] for x in levels))
        for x in levels:
            for field in ("short", "full", "says"):
                with self.subTest(level=x["level"], field=field):
                    self.assertTrue(x[field]["en"] and x[field]["ru"])

    def test_a_conclusion_is_allowed_at_a_and_b_only(self):
        self.assertEqual(["A", "B"], [x["level"] for x in _raw()["levels"] if x["verdict_allowed"]])

    def test_e_means_no_source(self):
        e = next(x for x in _raw()["levels"] if x["level"] == "E")
        self.assertEqual(["none"], e["basis"])

    def test_the_engine_reads_it_localised(self):
        r = G.legend()
        self.assertEqual("ok", r["status"])
        self.assertEqual(["A", "B"], r["verdict_levels"])
        self.assertTrue(all(isinstance(x["short"], str) for x in r["levels"]))


class TestEverySurfaceSaysTheSameWords(unittest.TestCase):

    def test_the_docs_page_carries_every_level_in_the_legends_words(self):
        page = (support.ROOT / "src" / "scholion" / "docs" / "evidence-levels.md").read_text(encoding="utf-8")
        for x in _raw()["levels"]:
            with self.subTest(level=x["level"]):
                self.assertIn(x["full"]["en"], page)

    def test_the_command_line_prints_the_legend_in_both_languages(self):
        for lang, words in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            code, out, err = support.run(["evidence-levels"], lang=lang)
            self.assertEqual(0, code, err)
            with self.subTest(lang=lang):
                self.assertIn(words["evidence.title"], out)
                for x in _raw()["levels"]:
                    self.assertIn(x["full"][lang], out)

    def test_the_json_answer_has_the_key_the_answers_refer_to(self):
        r = support.run_json(["evidence-levels"])
        self.assertEqual("evidence_levels", r["key"])
        self.assertEqual(list(LEVELS), [x["level"] for x in r["levels"]])

    def test_the_page_reads_the_legend_from_the_route(self):
        page = (support.ROOT / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/api/evidence-levels", page)
        self.assertIn('id="gd-levels"', page)

    def test_the_canon_tells_an_assistant_to_name_the_level(self):
        canon = (support.ROOT / "src" / "scholion" / "skill" / "ASSISTANT-RULES.md").read_text(encoding="utf-8")
        self.assertIn("relayed with its level", canon)
        self.assertIn("scholion\nevidence-levels", canon)


if __name__ == "__main__":
    unittest.main()
