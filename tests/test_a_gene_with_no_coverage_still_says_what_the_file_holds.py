"""A gene whose bases were never measured still says what the file holds.

«Read» means two things at once: the variants went through ClinVar AND a
coverage table says the bases were read deeply enough. The second half needs an
alignment, and not everybody has one — a raw file alone cannot tell «no variant
here» from «nobody looked here».

Until 17.09.2026 the row printed only the gap. After the gene–disease base grew
by 372 genes, every one of them waited for a coverage table before it would say
that the file holds nothing pathogenic in it — an answer the file already had.
The gap is still stated, and it still keeps the gene out of «read»; what the
file says is said beside it, with the alignment named as what would settle the
rest.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401
from scholion.engine import system_panels as SP

SCAN = {"status": "ok"}


def _row(gene: str, hits, coverage_state=None):
    """One base gene through the engine, with the coverage table saying nothing."""
    clinvar = {"status": "ok", "by_gene": {gene: hits}}
    return SP._finish_base_row(_base(gene), SCAN, clinvar)


def _base(gene: str):
    return {"unit": "gene", "origin": "base", "gene": gene, "mode": "monogenic",
            "classifications": ["Definitive"], "moi_codes": ["AD"], "assertions": [],
            "finding_grade": True, "recessive_only": False, "weaker_assertions": 0,
            "other_assertions": 0, "text": None, "pending": False, "kind": None}


class TestTheFileAnswersWithoutACoverageTable(unittest.TestCase):

    def test_a_clear_gene_says_the_file_holds_nothing_and_names_the_alignment(self):
        row = _row("BRCA2", [])
        # The file read the gene; the DEPTH is what nobody measured. Calling
        # that «not read» said something false about the file (owner,
        # 17.09.2026), so the third state is what the row carries.
        self.assertEqual("file_only", row["read_state"])
        self.assertIs(True, row["read"])
        self.assertTrue(str(row["read_why"]).startswith("coverage"), row["read_why"])
        self.assertEqual({"variants": 0, "findings": 0, "carrier": False}, row["file_says"])
        self.assertIn("BAM", row["file_says_text"])

    def test_a_gene_the_table_measured_and_found_thin_is_still_not_read(self):
        """The other half of the same rule: a table that WAS made and found the
        gene thin is a measurement, and it says the gene was not read."""
        from scholion.engine import panel_form
        self.assertEqual("unread", panel_form.read_state(False, "coverage_low"))
        self.assertEqual("file_only", panel_form.read_state(False, "coverage_not_measured"))
        self.assertEqual("read", panel_form.read_state(True, None))

    def test_a_gene_with_a_finding_says_how_many_the_file_holds(self):
        row = _row("LDLR", [{"zygosity": "het", "significance": "Pathogenic"}])
        self.assertEqual(1, row["file_says"]["variants"])
        self.assertTrue(row["file_says_text"])

    def test_nothing_is_claimed_when_the_file_never_went_through_clinvar(self):
        row = SP._finish_base_row(_base("BRCA2"), SCAN,
                                  {"status": "input_too_narrow", "by_gene": {}})
        self.assertIsNone(row.get("file_says"))
        self.assertIsNone(row.get("file_says_text"))
        self.assertNotIn("⟦", str(row.get("read_why_text")),
                         "the reason is a sentence, not the code behind it")

    def test_the_unread_line_names_the_reason_and_what_closes_it(self):
        """A reader who has run every recompute the product offered is owed the
        next step, and it differs by reason."""
        from scholion.engine import panel_form
        v = {"kind": "clear_partial", "unread": 3, "total": 10,
             "why_counts": {"thin": 2, "no_row": 1}}
        line = panel_form.unread_line(v)
        self.assertIn("2", line)
        self.assertIn("1", line)
        self.assertNotIn("⟦", line)
        one = panel_form.unread_line({"why_counts": {"thin": 4}})
        self.assertNotIn("4", one, "one reason for all of them does not repeat the count")
        self.assertIsNone(panel_form.unread_line({"kind": "clear_measured"}))

    def test_every_unread_reason_falls_into_a_class(self):
        from scholion.engine import panel_form
        self.assertEqual("thin", panel_form.unread_class("coverage_low"))
        self.assertEqual("no_row", panel_form.unread_class("assumed_ref"))
        self.assertEqual("clinvar", panel_form.unread_class("clinvar_not_run"))
        self.assertEqual("other", panel_form.unread_class("something_new"))

    def test_a_verdict_counts_the_depthless_rows_apart_from_the_unread_ones(self):
        from scholion.engine import panel_form
        rows = [{"gene": "A", "read": True, "read_state": "file_only", "findings": 0},
                {"gene": "B", "read": True, "read_state": "read", "findings": 0}]
        v = panel_form.verdict(rows, {"status": "ok"})
        self.assertEqual("clear_file_only", v["kind"])
        self.assertEqual(1, v["depthless"])
        self.assertIn("1", panel_form.verdict_line(v))

    def test_the_sentence_exists_in_both_languages(self):
        from scholion import i18n
        for key in ("system.row.file_says_clear", "system.row.file_says_found",
                    "system.row.file_says_carrier", "system.read_why.clinvar_input_too_narrow"):
            for lang in ("en", "ru"):
                with self.subTest(key=key, language=lang):
                    self.assertNotIn("⟦", i18n.t(key, lang=lang, gene="GENE", n=1, variants="1"))


if __name__ == "__main__":
    unittest.main()
