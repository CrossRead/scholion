"""Every release says what to recompute in a form a program reads.

The journal always had a section «What needs recomputing», and nothing read it: a
person who upgraded had to read every entry to learn what to re-run, and a doctor
ran the product three days behind a release that answered her own complaint
(13.09.2026). The section now has a grammar — «Nothing», or bold leads of the
shape «Run `scholion …` — when.» / «By hand — when.» — and `scholion.updates`
reads it. This file holds the grammar for the whole journal, so an entry written
tomorrow in free prose fails the build rather than going unread.
"""
from __future__ import annotations

import re
import unittest

import support
from scholion import contract, updates

ROOT = support.ROOT


class TestTheJournalFollowsTheGrammar(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        cls.entries = updates.parse_journal(cls.text)
        cls.commands = set(contract.cli_commands())

    def test_every_section_parses_without_a_problem(self):
        self.assertGreater(len(self.entries), 20)
        for e in self.entries:
            with self.subTest(version=e["version"]):
                self.assertEqual([], e["problems"])

    def test_the_current_version_and_the_unreleased_block_carry_the_section(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        current = [e for e in self.entries if e["version"] == version]
        self.assertEqual(1, len(current), f"no journal entry for {version}")
        self.assertTrue(current[0]["has_section"])
        m = re.search(r"^## Not released\s*$", self.text, re.M)
        if m:
            nxt = re.search(r"^## ", self.text[m.end():], re.M)
            block = self.text[m.end(): m.end() + (nxt.start() if nxt else len(self.text))]
            self.assertIn("### What needs recomputing", block,
                          "the unreleased block says nothing about what to recompute")
            body = block.split("### What needs recomputing", 1)[1].split("\n### ", 1)[0]
            self.assertEqual([], updates.parse_section(body)["problems"])

    def test_every_scholion_command_a_lead_names_exists(self):
        for e in self.entries:
            for a in e["actions"]:
                for c in a["commands"]:
                    if c.startswith("scholion "):
                        name = c.split()[1]
                        with self.subTest(version=e["version"], command=c):
                            self.assertIn(name, self.commands)

    def test_the_copy_the_package_carries_reads_the_same(self):
        self.assertEqual(self.entries, updates.parse_journal(updates.journal_text()))


class TestTheReaderReadsWhatItShould(unittest.TestCase):

    def test_versions_compare_as_numbers(self):
        self.assertGreater(updates.version_tuple("0.4.10"), updates.version_tuple("0.4.9"))
        self.assertEqual((0, 5, 0), updates.version_tuple("0.5.0+local"))

    def test_an_update_from_0_4_8_collects_what_came_after_and_not_before(self):
        got = updates.between("0.4.8", "0.5.0")
        versions = [e["version"] for e in got]
        self.assertIn("0.5.0", versions)
        self.assertIn("0.4.11", versions)
        self.assertIn("0.4.9", versions)
        self.assertNotIn("0.4.8", versions, "the version one updates FROM is already applied")
        self.assertNotIn("0.4.10", versions, "a release that asks for nothing is not listed")
        cmds = {c for e in got for a in e["actions"] for c in a["commands"]}
        self.assertIn("scholion acmg-scan", cmds)

    def test_a_free_prose_section_and_a_malformed_lead_are_named(self):
        self.assertTrue(updates.parse_section("Re-run the import once.")["problems"])
        bad = updates.parse_section("**Run the import once.**\nThen look again.")
        self.assertTrue(bad["problems"])
        bad2 = updates.parse_section("**Run `rm -rf x` — always.**")
        self.assertTrue(any("not a scholion command" in p for p in bad2["problems"]))

    def test_a_lead_carries_its_commands_condition_and_explanation(self):
        s = updates.parse_section(
            "**Run `scholion labs` and `scholion overview` — if saved before.**\n"
            "The thresholds changed.\n\n"
            "**By hand — if a point sits in the low tens.**\nRemove it.")
        self.assertEqual([], s["problems"])
        self.assertEqual(["scholion labs", "scholion overview"], s["actions"][0]["commands"])
        self.assertEqual("if saved before", s["actions"][0]["condition"])
        self.assertEqual("The thresholds changed.", s["actions"][0]["text"])
        self.assertTrue(s["actions"][1]["manual"])
        self.assertEqual("Remove it.", s["actions"][1]["text"])


if __name__ == "__main__":
    unittest.main()
