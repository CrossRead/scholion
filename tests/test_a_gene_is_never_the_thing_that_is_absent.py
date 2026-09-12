"""Everybody has the gene. What can be missing is a variant, or our knowledge of one.

The fifth class of link was first called «absent» and printed as «named in the
context list and unknown to this build», which a reader shortens to «the gene is
not there». A clinician read it and answered: the wording is wrong — not «no
gene», but «no genetic variants». She is right literally, and the claim we were
making was about a person, not about a build.

The repair goes one step further than she asked, because «no variants» still glues
together two states this project separates everywhere else. A position READ and
matching the reference is a measured absence of a finding. A position held and not
read is an absence of measurement. They read alike on a screen and cost differently
— the same difference that made a missing row print as «reference», and the same
difference that decides whether «no pharmacogenetic findings» means anything.

One level down, the same glue again: eight positions held for a gene, two of them
confirmed against the reference and six with no row at all, summed into one
reassuring sentence. The count now says how many of how many, and names the rest.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import core, format as fmt
from scholion.engine import decision as D
from scholion.i18n import en, ru

PAGE = (Path(support.__file__).resolve().parent.parent
        / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")


class TestTheFifthClassIsAboutVariantsAndNotAboutTheGene(unittest.TestCase):

    def test_the_class_is_no_longer_named_after_an_absent_gene(self):
        self.assertIn("no_variant", D.KINDS)
        self.assertNotIn("absent", D.KINDS)

    def test_no_phrase_says_the_gene_itself_is_missing(self):
        """The claim she objected to, in the words either catalogue could print."""
        for cat, bad in ((en.MESSAGES, ("gene is absent", "gene is not present",
                                        "unknown to this build")),
                         (ru.MESSAGES, ("гена нет", "ген отсутствует",
                                        "сборке неизвестен"))):
            for key, value in cat.items():
                if not key.startswith("decision.") or not isinstance(value, str):
                    continue
                for phrase in bad:
                    with self.subTest(key=key, phrase=phrase):
                        self.assertNotIn(phrase, value.lower())

    def test_every_state_has_a_sentence_in_both_languages(self):
        for state in D.VARIANT_STATES:
            for cat, name in ((en.MESSAGES, "en"), (ru.MESSAGES, "ru")):
                with self.subTest(state=state, lang=name):
                    self.assertIn("decision.variant." + state, cat)


class TestTheStateIsDecidedFromTheDataAndNotByDefault(unittest.TestCase):

    BOOK = {"loci": {"rsA": {"gene": "GENEX"}, "rsB": {"gene": "GENEX"},
                     "rsC": {"gene": "OTHER"}}}

    def _state(self, results):
        with mock.patch.object(core, "loci", lambda: self.BOOK), \
             mock.patch("scholion.genome.lookup",
                        side_effect=lambda rs, *a, **k: {"result": results.get(rs, {})}):
            return D.variant_state("GENEX")

    def test_read_and_matching_the_reference_is_a_finding(self):
        s = self._state({"rsA": {"confidence": "confirmed_ref", "depth": 26},
                         "rsB": {"confidence": "confirmed_ref", "depth": 31}})
        self.assertEqual("no_variant_called", s["state"])
        self.assertEqual(2, s["confirmed_ref"])
        self.assertEqual(0, s["unread"])
        self.assertEqual((26, 31), (s["depth_min"], s["depth_max"]))

    def test_held_and_unread_is_not_the_same_state(self):
        s = self._state({})
        self.assertEqual("not_read", s["state"])
        self.assertEqual(2, s["unread"])

    def test_a_part_read_and_a_part_not_is_counted_as_both(self):
        """Two confirmed out of eight held is not «no variants in this gene»."""
        s = self._state({"rsA": {"confidence": "confirmed_ref", "depth": 26}})
        self.assertEqual("no_variant_called", s["state"])
        self.assertEqual(1, s["confirmed_ref"])
        self.assertEqual(1, s["unread"])

    def test_a_called_variant_is_said_out_loud_rather_than_swallowed(self):
        s = self._state({"rsA": {"confidence": "called", "depth": 22}})
        self.assertEqual("variant_called", s["state"])

    def test_a_gene_this_build_holds_no_position_for_says_that_about_itself(self):
        with mock.patch.object(core, "loci", lambda: self.BOOK):
            s = D.variant_state("NOTHELD")
        self.assertEqual("no_positions", s["state"])
        self.assertEqual(0, s["positions"])

    def test_a_lookup_that_raises_leaves_the_position_unread_not_reference(self):
        with mock.patch.object(core, "loci", lambda: self.BOOK), \
             mock.patch("scholion.genome.lookup", side_effect=RuntimeError("no file")):
            s = D.variant_state("GENEX")
        self.assertEqual("not_read", s["state"])
        self.assertEqual(2, s["unread"])

    def test_it_runs_on_the_real_catalogue_too(self):
        s = D.variant_state("DPYD")
        self.assertIn(s["state"], D.VARIANT_STATES)
        self.assertEqual(s["positions"],
                         (s.get("called") or 0) + (s.get("confirmed_ref") or 0) + s["unread"])


class TestTheEvidenceIsPrinted(unittest.TestCase):

    def test_the_measured_absence_carries_its_count_and_its_depth(self):
        line = fmt._variant_state_line({"state": "no_variant_called", "positions": 2,
                                        "confirmed_ref": 2, "unread": 0,
                                        "depth_min": 24, "depth_max": 34})
        self.assertIn("2", line)
        self.assertIn("24–34×", line)

    def test_one_depth_is_not_printed_as_a_range(self):
        line = fmt._variant_state_line({"state": "no_variant_called", "positions": 1,
                                        "confirmed_ref": 1, "unread": 0,
                                        "depth_min": 26, "depth_max": 26})
        self.assertIn("26×", line)
        self.assertNotIn("26–26", line)

    def test_the_unread_remainder_is_named_in_the_same_breath(self):
        line = fmt._variant_state_line({"state": "no_variant_called", "positions": 8,
                                        "confirmed_ref": 2, "unread": 6,
                                        "depth_min": 24, "depth_max": 34})
        self.assertIn("6", line)

    def test_no_state_renders_an_empty_placeholder(self):
        for state in D.VARIANT_STATES:
            with self.subTest(state=state):
                line = fmt._variant_state_line({"state": state, "positions": 1,
                                                "confirmed_ref": 1, "called": 1,
                                                "unread": 0, "depth_min": 9, "depth_max": 9})
                self.assertTrue(line)
                self.assertNotIn("{", line)
                self.assertNotIn("⟦", line)

    def test_a_row_without_a_state_adds_no_line(self):
        self.assertEqual("", fmt._variant_state_line({}))

    def test_the_line_reaches_the_answer(self):
        ctx = {"blocks": {k: [] for k in D.KINDS},
               "curated": {"asked": True, "refused": 0},
               "verdict": {"kind": "no_rule", "why": "no_pair"}}
        ctx["blocks"]["no_variant"] = [{"gene": "GENEX", "kind": "no_variant",
                                        "text": "t", "source": "s",
                                        "variant": {"state": "not_read", "positions": 3}}]
        lines = fmt._context_lines(ctx)
        self.assertTrue(any("3" in l for l in lines))


class TestThePageSaysTheSameFourStates(unittest.TestCase):

    def test_the_page_has_the_function_and_asks_for_every_state(self):
        self.assertIn("function variantStateLine(", PAGE)
        for state in D.VARIANT_STATES:
            with self.subTest(state=state):
                self.assertIn("decision.variant." + state, PAGE)

    def test_the_page_no_longer_asks_for_the_old_class(self):
        self.assertNotIn("decision.kind.absent", PAGE)
        self.assertNotIn("'absent'", PAGE.split("function contextHtml(")[1][:400])


if __name__ == "__main__":
    unittest.main()
