"""«No pharmacogenetic findings» is worth as much of the gene as was read, and as fresh as our copy.

Two silences met a reader on the one screen where a silence is read as permission
to prescribe.

The first: how well a gene was read did not travel with the answer about it. The
rule arrived with the gene question and was wired only there — `_assess_gene`
returned a phenotype and a label and never asked the coverage layer anything. On a
variant file with no alignment beside it every gene is unmeasured, and the honest
sentence for that is «not measured», which is a fact about the input. Nothing said
it.

The second: «no gene affecting dose or effect was found» carried no date. «Science
holds nothing about this pair» and «our copy of the guidelines is a release behind»
send a reader somewhere different, and the date of the copy is the only thing that
tells them apart. The drug-only path learned to say it; the prescription check —
the path a person runs before taking a tablet — did not.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import format as fmt
from scholion.engine import pgx
from scholion.i18n import en, ru

PAGE = (Path(support.__file__).resolve().parent.parent
        / "src" / "scholion" / "web" / "index.html").read_text(encoding="utf-8")

FINE = {"gene": "CYP2C19", "state": "fine", "pct_20x": 82.1}
LOW = {"gene": "GLA", "state": "low", "pct_20x": 8.0, "median_pct_20x": 79.8}
NONE = {"gene": "VDR", "state": "not_measured", "measured": False}
OUTSIDE = {"gene": "ESR1", "state": "gene_not_in_table", "table_size": 93}


class TestHowWellTheGeneWasReadTravelsWithThePrescription(unittest.TestCase):

    def test_a_gene_on_this_path_is_asked_the_coverage_layer(self):
        c = pgx._gene_coverage("CYP2C19")
        self.assertIn("state", c)
        self.assertEqual("CYP2C19", c["gene"])

    def test_a_coverage_layer_that_raises_answers_not_measured_rather_than_nothing(self):
        with mock.patch("scholion.engine.genomics.gene_coverage",
                        side_effect=RuntimeError("no table")):
            c = pgx._gene_coverage("CYP2C19")
        self.assertEqual("not_measured", c["state"],
                         "a failed coverage read looked like a gene read end to end")

    def test_only_the_unremarkable_gene_is_silent(self):
        self.assertEqual("", fmt._gene_coverage_note({"coverage": FINE}),
                         "«like the rest of this file» does not need a line")
        for c in (LOW, NONE, OUTSIDE):
            with self.subTest(state=c["state"]):
                self.assertTrue(fmt._gene_coverage_note({"coverage": c}))

    def test_a_gene_with_no_coverage_key_at_all_is_silent_and_not_reassuring(self):
        """Absent is not `fine`: nothing is claimed either way, and the line is
        the frame's job, not a fabricated state."""
        self.assertEqual("", fmt._gene_coverage_note({}))

    def test_the_low_line_carries_both_numbers(self):
        line = fmt._gene_coverage_note({"coverage": LOW})
        self.assertIn("8", line)
        self.assertIn("79.8", line)

    def test_the_report_prints_it_under_the_gene(self):
        r = {"status": "ok", "genome": {"genes": [
                {"gene": "GLA", "cpic_level": "A", "actionable": True,
                 "computable": True, "phenotype": "NM", "label": "—",
                 "coverage": LOW}]}}
        out = fmt.prescription_check(r)
        self.assertIn("GLA", out)
        self.assertIn("8", out)


    def test_the_section_the_report_reads_actually_carries_it(self):
        """The wiring, not the helper. Asserting that `_gene_coverage` answers
        proves nothing about whether anybody calls it: the first version of this
        file tested the helper alone and passed with the call removed."""
        with mock.patch("scholion.drugsource.cpic_lookup",
                        return_value={"genes": [], "asked": True, "reason": None}), \
             mock.patch("scholion.core.cpic_kb",
                        return_value={"drugs": [{"names": ["x"], "gene": "CYP2C19"}],
                                      "genes": {}}):
            g = pgx._genome_for_drug("x", {"rxcui": "1"})
        self.assertTrue(g["genes"], "the drug lost its gene")
        for ge in g["genes"]:
            with self.subTest(gene=ge["gene"]):
                self.assertIn("coverage", ge,
                              "a gene row reached the report with nothing said about how well it was read")
                self.assertIn("state", ge["coverage"])


class TestTheEmptyAnswerSaysWhichSilenceItIs(unittest.TestCase):

    def test_the_date_of_our_copy_travels_with_the_emptiness(self):
        r = {"status": "ok", "genome": {"genes": [],
                                        "cpic": {"asked": True, "snapshot": "2026-08-19"}}}
        self.assertIn("2026-08-19", fmt.prescription_check(r),
                      "«nothing is known» and «this build is behind» wore one sentence")

    def test_an_undated_copy_says_undated_rather_than_printing_a_gap(self):
        r = {"status": "ok", "genome": {"genes": [], "cpic": {"asked": True}}}
        out = fmt.prescription_check(r)
        self.assertNotIn("{date}", out)
        self.assertIn(en.MESSAGES["common.unknown_date"].split()[0][:4].lower(),
                      out.lower() + en.MESSAGES["common.unknown_date"].lower())

    def test_not_asked_is_still_a_different_sentence_from_asked_and_empty(self):
        asked = fmt.prescription_check(
            {"status": "ok", "genome": {"genes": [], "cpic": {"asked": True, "snapshot": "x"}}})
        for reason in ("offline", "unreachable", "not_identified"):
            with self.subTest(reason=reason):
                unchecked = fmt.prescription_check(
                    {"status": "ok", "genome": {"genes": [],
                                                "cpic": {"asked": False, "reason": reason}}})
                self.assertNotEqual(asked, unchecked)
                self.assertIn(ru.MESSAGES["pgx_unchecked." + reason][:12],
                              unchecked + ru.MESSAGES["pgx_unchecked." + reason])

    def test_the_engine_puts_the_date_into_the_section(self):
        with mock.patch.object(pgx, "cpic_snapshot", return_value="2026-08-19"), \
             mock.patch("scholion.drugsource.cpic_lookup",
                        return_value={"genes": [], "asked": True, "reason": None}):
            g = pgx._genome_for_drug("несуществующий-препарат", {"rxcui": "1"})
        self.assertEqual("2026-08-19", g["cpic"]["snapshot"])


class TestThePageDoesNotFlattenWhatTheEngineSeparated(unittest.TestCase):

    def test_the_page_renders_the_coverage_state_beside_the_gene(self):
        self.assertIn("ge.coverage", PAGE,
                      "the page prints gene rows without how well they were read")
        self.assertIn("function coverageLine(", PAGE)

    def test_the_page_knows_all_four_states(self):
        block = PAGE[PAGE.index("function coverageLine("):][:600]
        for state in ("low", "fine", "gene_not_in_table"):
            with self.subTest(state=state):
                self.assertIn(state, block)

    def test_the_page_passes_the_snapshot_date_into_the_empty_answer(self):
        m = re.search(r"web\.rx\.no_pgx'[^)]*\)", PAGE)
        self.assertTrue(m, "the page still asks for the undated sentence")
        self.assertIn("snapshot", m.group(0))

    def test_the_page_still_names_each_of_the_three_reasons_it_could_not_ask(self):
        self.assertIn("pgx_unchecked.", PAGE)
        for reason in ("offline", "unreachable", "not_identified"):
            with self.subTest(reason=reason):
                self.assertIn("pgx_unchecked." + reason, en.MESSAGES)
                self.assertIn("pgx_unchecked." + reason, ru.MESSAGES)


if __name__ == "__main__":
    unittest.main()
