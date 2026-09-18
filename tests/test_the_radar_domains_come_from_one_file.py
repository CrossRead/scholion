"""The body systems of the radar are declared once, in knowledge/, and every reader sees the same list.

Task 168, step 1. `_RADAR_DOMAINS` was a Python constant inside `lifestyle.py`.
The moment a second engine — the genetic half of a system — depends on the same
eleven names, a constant held in one module and re-typed in another is the shape
every pair of copies in this project has drifted into, and the drift would show
not as a failing test but as a system present on the radar and absent from its
own card. So the list lives in `knowledge/radar_domains.json`, `lifestyle.py`
builds its constant from the file, `system_panels.py` reads the same file, and
this test compares what each of them sees.

The wearables system is the other half of the guard. «Fitness» is built from
wearable metrics and attached by `health_radar` after the loop; a file that
listed only the laboratory domains would lose it, and a reader that counted
every domain would attach a genetic half to it by inattention. The file names
it, says where it comes from, and says it has no genetic half — and that is
checked, not assumed. (Eleven laboratory domains and a twelfth from wearables
until 13.09.2026; twelve and a thirteenth since «Heart and vessels» was added.)
"""
from __future__ import annotations

import json
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion.engine import system_panels as SP

# `engine.lifestyle` is a function on the facade; the MODULE is what holds the
# constant, so it is imported by path, as the body-map test does.
import importlib
L = importlib.import_module("scholion.engine.lifestyle")
from scholion.i18n import en, ru


def _file():
    return json.loads(core.knowledge_path("radar_domains.json").read_text(encoding="utf-8"))


class TestOneFileFeedsEveryReader(unittest.TestCase):

    def test_lifestyle_sees_exactly_the_laboratory_domains_of_the_file(self):
        labs = [(d["key"], list(d["markers"])) for d in _file()["domains"]
                if d["source"] == "labs"]
        self.assertEqual(labs, list(L._RADAR_DOMAINS),
                         "lifestyle.py and radar_domains.json disagree — the constant "
                         "is built from the file, so this means the file changed under "
                         "a cached import or somebody re-typed the list")

    def test_the_composition_of_0_4_9_is_intact(self):
        """Twelve laboratory systems: the eleven of 0.4.9, the endocrine ones
        split in four, and «Heart and vessels» after lipids since 13.09.2026
        (the owner's decision; the reason is `_meta.why_cardio`). The 0.4.9
        composition is recorded in the file's _meta; the guard is here."""
        keys = [k for k, _ in L._RADAR_DOMAINS]
        # The systems added since keep the first twelve in place and in order
        # (amino acids, task 200): the axes a stored radar drew stay where they were.
        self.assertEqual(keys[:12], ["lipids", "cardio", "glucose", "inflammation", "thyroid",
                                     "adrenals", "gonads", "growth", "pancreas", "liver",
                                     "micronutrients", "renal"])
        self.assertIn("amino_acids", keys[12:])
        self.assertIn("why_four_endocrine_systems", _file()["_meta"])
        self.assertIn("why_cardio", _file()["_meta"])

    def test_system_panels_reads_the_same_file(self):
        self.assertEqual([k for k, _ in L._RADAR_DOMAINS],
                         [d["key"] for d in SP.domains() if d["source"] == "labs"])
        self.assertEqual({k: m for k, m in L._RADAR_DOMAINS},
                         {d["key"]: d["markers"] for d in SP.domains() if d["source"] == "labs"})

    def test_every_domain_can_be_named_in_both_languages(self):
        for d in _file()["domains"]:
            for cat in (en.MESSAGES, ru.MESSAGES):
                with self.subTest(key=d["key"]):
                    self.assertIn("radar.domain." + d["key"], cat)


class TestTheTwelfthSystemIsNeitherLostNorGivenGenes(unittest.TestCase):

    def test_fitness_is_in_the_file_from_the_wearables_and_without_a_genetic_half(self):
        fit = [d for d in _file()["domains"] if d["key"] == "fitness"]
        self.assertEqual(1, len(fit), "the wearables system is missing from the file")
        self.assertEqual("wearables", fit[0]["source"])
        self.assertIs(False, fit[0]["genetic_half"])
        self.assertEqual([], fit[0]["markers"])

    def test_fitness_is_not_a_laboratory_domain(self):
        self.assertNotIn("fitness", [k for k, _ in L._RADAR_DOMAINS],
                         "fitness is attached by health_radar from the wearables, "
                         "not scored from a laboratory panel")

    def test_every_laboratory_domain_declares_its_source_and_its_genetic_half(self):
        for d in _file()["domains"]:
            with self.subTest(key=d["key"]):
                self.assertIn(d["source"], ("labs", "wearables"))
                self.assertIsInstance(d["genetic_half"], bool)
                self.assertEqual(d["genetic_half"], d["source"] == "labs")
                self.assertTrue((d.get("why") or "").strip(),
                                "a domain with no reason recorded cannot be disagreed with")


if __name__ == "__main__":
    unittest.main()
