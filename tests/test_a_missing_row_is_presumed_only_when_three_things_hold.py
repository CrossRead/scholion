"""A missing row is «taken by the reference» only when three things hold at once (task 201).

Between `confirmed_ref` — a measured 0/0 with its depth — and `assumed_ref` —
nothing to presume from — stands `presumed_ref`: a whole-genome file that has no
row at a position almost certainly matched the reference there. Almost. A
presumption about the reference is a presumption about the ABSENCE of a risk,
so it always turns «unknown» into good news, and the rules around it are about
when it has no right to appear:

* never on a chip, a genotype table or a panel — there a missing row means
  «the position is not on the chip»;
* never where a coverage table that exists calls the gene low or does not hold
  it; no table at all is no objection;
* never for a position outside the catalogue, whose ref/alt pair is unknown;
* and never with an alignment at hand — then the answer is «not read yet» and
  the step that reads it.

Where it does appear: the caveat stands INSIDE the sentence, it is never a
finding, it has its own counter outside «read N of M», and it never lets a list
be called read end to end.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, i18n
from scholion.engine import panel_form, system_panels as SP

LOCI = {"loci": {"rs1": {"gene": "G1", "chrom": "1", "pos": 100, "ref": "A", "alt": "G"}}}
NO_ROW = {"status": "ok", "result": {"genotype": "AA", "confidence": "assumed_ref", "depth": None}}
HGVS = "NC_000001.11:g.100A>G"


class _NoRow(unittest.TestCase):

    def call(self, scan=None, coverage="not_measured", has_bam=False, rsid="rs1", risk="G"):
        scan = scan or {"status": "ok", "input_profile": "whole_genome"}
        with mock.patch("scholion.genome.lookup", lambda rs: NO_ROW), \
                mock.patch.object(core, "loci", lambda: LOCI), \
                mock.patch("scholion.engine.genomics.gene_coverage", lambda g, rows=None: {"state": coverage}):
            return SP._genotype(rsid, HGVS, "G1", risk, scan, ("A", "G"), has_bam=has_bam)


class TestWhenItMayAppear(_NoRow):

    def test_a_whole_genome_file_with_no_objection_and_no_alignment_presumes(self):
        g = self.call()
        self.assertEqual(("absent", False, True, "presumed_ref"),
                         (g["state"], g["read"], g.get("presumed"), g["why"]))

    def test_a_coverage_table_that_found_the_gene_fine_is_no_objection_either(self):
        self.assertTrue(self.call(coverage="fine").get("presumed"))

    def test_the_reference_carrying_the_named_allele_presumes_two_copies(self):
        g = self.call(risk="A")
        self.assertEqual("hom", g["state"])
        self.assertTrue(g["presumed"])


class TestWhenItHasNoRight(_NoRow):

    def test_never_on_a_chip_a_genotype_table_or_a_panel(self):
        from scholion.engine.genomics import NARROW_INPUTS
        self.assertTrue(NARROW_INPUTS)
        for profile in sorted(NARROW_INPUTS):
            with self.subTest(input=profile):
                g = self.call(scan={"status": "ok", "input_profile": profile})
                self.assertNotIn("presumed", g)
                self.assertEqual(("unread", "assumed_ref", "narrow_input"),
                                 (g["state"], g["why"], g["presumed_refused"]))

    def test_never_where_the_coverage_table_objects(self):
        for state in ("low", "gene_not_in_table"):
            with self.subTest(coverage=state):
                g = self.call(coverage=state)
                self.assertEqual(("unread", "coverage_objects"), (g["state"], g["presumed_refused"]))

    def test_never_for_a_position_outside_the_catalogue(self):
        g = self.call(rsid="rs999")
        self.assertEqual(("unread", "not_in_catalogue"), (g["state"], g["presumed_refused"]))

    def test_never_with_an_alignment_at_hand(self):
        g = self.call(has_bam=True)
        self.assertEqual(("unread", "assumed_ref", "alignment_at_hand"),
                         (g["state"], g["why"], g["presumed_refused"]))

    def test_never_without_a_named_allele(self):
        self.assertEqual("risk_allele_not_declared", self.call(risk=None)["presumed_refused"])


class TestARowThatIsThereIsReadAndSaysWhatItDoesNotKnow(unittest.TestCase):
    """The other side of the same question (owner, 18.09.2026): the row IS in
    the file, so the position is read — and where the row states no depth and
    no alignment is here to measure one, the depth is said to be unverified.
    Decided in the READER, so every face says it the same way."""

    def mark(self, depth, bam):
        from scholion import genome
        out = {"genotype": "AG", "confidence": "called", "depth": depth}
        with mock.patch("scholion.gene_region.bam_path", lambda: bam):
            genome._mark_depth_unverified(out)
        return out

    def test_a_row_with_no_depth_and_no_alignment_says_the_depth_is_unverified(self):
        out = self.mark(None, None)
        self.assertTrue(out["depth_unverified"])
        self.assertTrue(out["note"])

    def test_a_row_that_states_its_depth_needs_no_caveat(self):
        self.assertNotIn("depth_unverified", self.mark(31, None))

    def test_with_an_alignment_the_depth_is_measurable_and_the_caveat_is_not_printed(self):
        self.assertNotIn("depth_unverified", self.mark(None, "/tmp/a.bam"))

    def test_the_caveat_joins_a_note_that_is_already_there(self):
        from scholion import genome
        out = {"genotype": "AA", "confidence": "confirmed_ref", "depth": None, "note": "first."}
        with mock.patch("scholion.gene_region.bam_path", lambda: None):
            genome._mark_depth_unverified(out)
        self.assertTrue(out["note"].startswith("first."))
        self.assertGreater(len(out["note"]), len("first."))

    def test_the_card_takes_the_reader_s_word(self):
        row = {"status": "ok", "result": {"genotype": "AG", "confidence": "called", "depth": None,
                                          "depth_unverified": True}}
        with mock.patch("scholion.genome.lookup", lambda rs: row):
            g = SP._genotype("rs1", HGVS, "G1", "G", {"status": "ok"}, ("A", "G"), has_bam=False)
        self.assertEqual(("het", True, True), (g["state"], g["read"], g.get("depth_unverified")))

    def test_the_caveat_is_a_sentence_in_both_languages(self):
        try:
            for lang in ("en", "ru"):
                i18n.set_lang(lang)
                for key in ("system.row.depth_unverified", "genome.depth_unverified"):
                    self.assertNotIn("⟦", i18n.t(key))
        finally:
            i18n.set_lang(None)


class TestAPresumptionNeverReachesADrugOrASecondaryFinding(unittest.TestCase):
    """«Taken by the reference» belongs to the panels of a system and to nothing
    else. A pharmacogenetic diplotype, a secondary finding and a longevity locus
    built on a row that is not there would print «normal metaboliser» or «no
    finding» from a property of the file — the failure this project exists to
    remove. Those entries refuse, as they always did."""

    def test_the_only_module_that_presumes_is_the_panel_reader(self):
        from pathlib import Path
        import scholion
        root = Path(scholion.__file__).resolve().parent
        holders = sorted(p.relative_to(root).as_posix() for p in root.rglob("*.py")
                         if '"presumed_ref"' in p.read_text(encoding="utf-8"))
        # the reader of a position, the states of «read», and the card that prints what closes it
        self.assertEqual(["engine/panel_genotype.py", "engine/panel_reading.py", "engine/system_panels.py"], holders)

    def test_a_drug_gene_with_no_row_is_a_gap_and_never_a_reference_call(self):
        from scholion.engine import pgx
        src = __import__("inspect").getsource(pgx)
        self.assertIn('== "assumed_ref"', src)
        self.assertNotIn("presumed", src)


class TestTheCardCarriesBothCaveats(unittest.TestCase):
    """The row of the card, and the printed line, carry what the reader said."""

    def _card(self, geno):
        import test_a_system_answers_with_its_seven_layers as layers
        case = layers._State("rows"); case.setUp()
        try:
            with mock.patch.object(SP, "_genotype", lambda *a, **k: dict(geno)):
                return {r["gene"]: r for r in SP.system("thyroid", "clinician")["genetics"]["rows"]
                        if r.get("unit") == "position"}
        finally:
            case.tearDown()

    def test_a_row_read_with_no_depth_is_read_and_says_the_depth_is_unverified(self):
        rows = self._card({"state": "het", "read": True, "genotype": "AG", "confidence": "called",
                           "depth": None, "depth_unverified": True})
        row = next(iter(rows.values()))
        self.assertEqual((True, "file_only"), (row["read"], row["read_state"]))
        self.assertTrue(row["depth_note"])
        from scholion import format as fmt
        self.assertIn(row["depth_note"], fmt._system_gene_row(row, "clinician"))

    def test_a_presumed_row_prints_what_closes_it(self):
        rows = self._card({"state": "absent", "read": False, "presumed": True, "why": "presumed_ref",
                           "genotype": "AA", "confidence": "assumed_ref", "depth": None})
        row = next(iter(rows.values()))
        self.assertEqual("presumed", row["read_state"])
        self.assertEqual(0, row["findings"])
        from scholion import format as fmt
        self.assertIn(row["closes_text"], fmt._system_gene_row(row, "clinician"))


class TestWhatItIsCountedAs(unittest.TestCase):

    def rows(self):
        return [{"gene": "A", "read": True, "read_state": "read", "findings": 0},
                {"gene": "B", "read": False, "read_state": "presumed", "read_why": "presumed_ref", "findings": 0}]

    def test_it_has_its_own_counter_and_the_list_is_not_read_end_to_end(self):
        """For the verdict it stays among the unread — the three entries answer
        one state in one voice — and is named apart beside it."""
        v = panel_form.verdict(self.rows(), {"status": "ok"})
        self.assertEqual(("clear_partial", 1, 1), (v["kind"], v["unread"], v["presumed"]))
        self.assertEqual({}, v["why_counts"], "a presumption is not a gap in the file")
        self.assertIn("1", panel_form.unread_line(v))

    def test_it_is_not_counted_among_the_unread_reasons(self):
        rows = self.rows() + [{"gene": "C", "read": False, "read_state": "unread", "read_why": "coverage_low", "findings": 0}]
        v = panel_form.verdict(rows, {"status": "ok"})
        self.assertEqual(("clear_partial", 2, 1), (v["kind"], v["unread"], v["presumed"]))
        self.assertEqual({"thin": 1}, v["why_counts"])
        block = panel_form.unread_block(v)
        self.assertEqual(1, block["total"])
        self.assertEqual(1, block["presumed_ref"]["positions"])
        self.assertEqual([("thin", 1)], [(r["reason"], r["positions"]) for r in block["by_reason"]])

    def test_the_reasons_are_a_field_a_model_does_not_have_to_parse(self):
        v = {"why_counts": {"no_row": 3}}
        block = panel_form.unread_block(v)
        self.assertEqual("scholion recompute", block["by_reason"][0]["closes_with"])
        self.assertIsNone(panel_form.unread_block({"kind": "clear_measured"}))

    def test_the_caveat_stands_inside_the_sentence_in_both_languages(self):
        try:
            for lang, inside in (("en", "taken by the reference"), ("ru", "принято по референсу")):
                i18n.set_lang(lang)
                for key in ("system.row.presumed_absent", "system.row.presumed_hom"):
                    text = i18n.t(key, gene="G1", rsid="rs1")
                    self.assertIn(inside, text)
                    self.assertNotIn("⟦", text)
                self.assertNotIn("⟦", panel_form.unread_line({"presumed": 2}))
        finally:
            i18n.set_lang(None)


if __name__ == "__main__":
    unittest.main()
