"""An exome, told apart from a panel — and the paths that were shut on it opened.

Found from outside. Three clinical VCFs were run through the package blind; the
ClinVar and ACMG steps returned `input_too_narrow` for all three and never
looked at anything. The refusal was not wrong in its own terms — the files
measured as narrow — but the measurement had only one kind of window to look
through: three deliberately GENE-POOR stretches, where an exome is empty by
construction. Empty there meant `sparse`, and `sparse` closed the two paths that
exist precisely to find a known pathogenic variant in a gene.

So the file that covers twenty thousand genes was refused on the grounds that it
covers nothing, and the reviewer's conclusion — «it found nothing» — was true in
a way nobody could see: it never looked.

The fix is a second kind of window. An exome is EMPTY where genes are not and
POPULATED where they are; a panel is empty in both; a whole genome is full in
both and is classified before either. The decision is that contrast, not a level,
because a contrast survives depth, ancestry and the caller's settings.

What stays shut on an exome is the polygenic score, and for a reason that is not
caution: a score's weights and its reference distribution are genome-wide, and
summing them over the coding two per cent produces a number with no distribution
behind it.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import callset
from scholion.engine import genomics


def measured(poor, rich, dense=3, **kw):
    """A measurement in the shape `measure()` returns, without a file."""
    m = {"measured": poor is not None, "observed_per_mb": poor,
         "coding_per_mb": rich, "coding_probes_dense": dense,
         "only_indels": False, "only_snvs": False, "imputed_share": None}
    m.update(kw)
    return m


class TestTheShapeOfAnExome(unittest.TestCase):

    def test_empty_between_genes_and_full_inside_them(self):
        self.assertEqual(callset._classify(measured(poor=2, rich=140)), "exome")

    def test_the_same_shape_when_the_poor_windows_could_not_be_measured(self):
        """The usual case: an exome has no rows at all out there, and `_probe`
        cannot tell «no rows» from «no such contig». That silence used to end as
        `unmeasured`, which is also narrow."""
        self.assertEqual(callset._classify(measured(poor=None, rich=140)), "exome")

    def test_a_whole_genome_is_not_an_exome(self):
        """It is full in the gene-poor windows too, and is decided there."""
        self.assertEqual(callset._classify(measured(poor=1550, rich=2000)), "whole_genome")

    def test_a_panel_is_not_an_exome(self):
        """Empty in both kinds of window — a few hundred genes are not dense in
        three unrelated stretches at once."""
        self.assertEqual(callset._classify(measured(poor=140, rich=3, dense=0)), "panel")
        self.assertEqual(callset._classify(measured(poor=None, rich=4, dense=0)), "unmeasured")

    def test_one_dense_window_is_not_enough(self):
        """A large panel can be thick in one gene-rich stretch by accident. Two
        of three is the rule, so that accident does not become a class."""
        self.assertEqual(callset._classify(measured(poor=None, rich=140, dense=1)), "unmeasured")

    def test_the_contrast_has_to_be_real(self):
        """A screen that is thin everywhere is thin, not coding-enriched."""
        self.assertEqual(callset._classify(measured(poor=30, rich=40)), "sparse")

    def test_imputation_still_decides_first(self):
        m = measured(poor=None, rich=140, imputed_share=0.9)
        self.assertEqual(callset._classify(m), "imputed_panel")

    def test_a_split_callset_still_decides_first(self):
        m = measured(poor=None, rich=140, only_indels=True)
        self.assertEqual(callset._classify(m), "partial_callset_indels")


class TestWhichPathsAnExomeOpens(unittest.TestCase):

    def test_clinvar_and_the_acmg_list_are_not_closed_on_an_exome(self):
        self.assertNotIn("exome", genomics.NARROW_INPUTS)

    def test_a_polygenic_score_is(self):
        self.assertIn("exome", genomics.NARROW_FOR_SCORES)

    def test_every_narrow_class_still_has_its_own_sentence(self):
        """A class with no message prints its own key at the reader."""
        from scholion.i18n import t as _t
        for cls in sorted(genomics.NARROW_INPUTS | genomics.NARROW_FOR_SCORES):
            if cls in ("array", "genotype_table"):
                continue
            with self.subTest(cls=cls):
                self.assertNotIn("⟦", _t("narrow.path_closed_" + cls, per_mb=0, share=0))
                self.assertNotIn("⟦", _t("limits.scope.input_" + cls, per_mb=0, share=0))

    def test_the_exome_class_has_a_status_line_and_a_boundary(self):
        from scholion.i18n import t as _t
        self.assertNotIn("⟦", _t("genome_status.callset_exome", per_mb=1, coding_per_mb=140, share=0))
        self.assertNotIn("⟦", _t("narrow.exome_boundary"))


if __name__ == "__main__":
    unittest.main()


class TestWhatAnAnswerOnAnExomeCarries(unittest.TestCase):
    """An open path states its boundary, because an answer with none teaches the
    reader that «answered» means «everything was looked at». On an exome it does
    not: the coding part was looked at."""

    def _with_profile(self, profile):
        from scholion import genome as g
        saved = g.available
        g.available = lambda: {"input_profile": profile,
                               "callset": {"coding_per_mb": 140}}
        try:
            return genomics._input_boundary()
        finally:
            g.available = saved

    def test_an_exome_answer_names_what_it_did_not_look_at(self):
        b = self._with_profile("exome")
        self.assertEqual(b["input_profile"], "exome")
        self.assertEqual(b["coding_per_mb"], 140)
        self.assertTrue(b["note"].strip())

    def test_a_whole_genome_answer_carries_no_such_note(self):
        self.assertIsNone(self._with_profile("whole_genome"))


class TestTheGateItself(unittest.TestCase):
    """The refusal a score meets on an exome, taken through the gate rather than
    inferred from the set it is in."""

    def _closed(self, profile, also=frozenset()):
        from scholion import genome as g
        saved = g.available
        g.available = lambda: {"ready": True, "input_profile": profile,
                               "callset": {"observed_per_mb": 2, "coding_per_mb": 140}}
        try:
            return genomics._array_only_input(also)
        finally:
            g.available = saved

    def test_a_score_is_refused_on_an_exome_with_a_sentence(self):
        closed = self._closed("exome", genomics.NARROW_FOR_SCORES)
        self.assertIsNotNone(closed)
        self.assertEqual(closed["status"], "input_too_narrow")
        self.assertEqual(closed["input_profile"], "exome")
        self.assertNotIn("⟦", closed["message"])

    def test_the_same_exome_does_not_close_the_paths_that_read_a_known_variant(self):
        self.assertIsNone(self._closed("exome"))
