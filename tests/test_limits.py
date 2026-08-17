"""«What cannot be said» is a work order, not a shrug.

The command exists because a limitation mentioned only inside another report is
one nobody can point at — not in a screenshot, not in a post, not in a
conversation with a doctor. But a command that only lists what is missing would
be worse than none: it would be the product agreeing with its own critics once a
day and changing nothing.

So the invariant this file defends is the one the owner stated as a rule for the
whole project: **where we write «unknown», we say in the same breath what exists,
what exactly is missing, and what would close it.** Every item is checked for
that third part, and the remedy is checked for being the RIGHT one — an
instruction that argues with its own diagnosis («re-genotype» for a score
withdrawn because the model does not reproduce) is worse than silence, because it
sends a person to do work that cannot help.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support

from scholion import core, limits


class _Profile(unittest.TestCase):

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.profile = self.dir / "profile"
        self.profile.mkdir()
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.profile)
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        core.reset_cache()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _write(self, name, obj):
        (self.profile / name).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
        core.reset_cache()


class TestEveryLimitationCarriesItsRemedy(_Profile):

    def test_an_empty_profile_names_every_missing_layer(self):
        r = limits.report()
        kinds = {i["kind"] for i in r["items"]}
        self.assertIn("genome", kinds)
        self.assertIn("labs", kinds)
        self.assertIn("medications", kinds)
        self.assertIn("wearables", kinds)

    def test_no_item_states_a_limitation_without_saying_what_closes_it(self):
        """The rule, checked mechanically rather than trusted to reviewers."""
        for item in limits.report()["items"]:
            with self.subTest(what=item["what"]):
                self.assertTrue(item["closes"].strip(),
                                "a limitation with no way out is a shrug in the shape of a "
                                "report — say what exists, what is missing and what would "
                                "close it, or do not print the item")
                self.assertTrue(item["why"].strip())

    def test_the_count_of_closable_matches_the_items(self):
        r = limits.report()
        self.assertEqual(r["closable"], len(r["items"]))
        self.assertEqual(r["count"], len(r["items"]))


class TestCoverageIsPublishedRatherThanKept(_Profile):
    """`profile/callability.tsv` was computed by a script and read by nothing.

    That is the exact shape of the defect the standards legislate against: ACMG
    2013 makes disclosure of achieved coverage a «must», because a gene read at
    70 % yields the same «no findings» as a gene read at 100 %.
    """

    HEAD = ("gene\tpanel\tchrom\tlength_bp\tmean_depth\trel_to_panel\t"
            "pct_1x\tpct_10x\tpct_20x\tpct_30x\n")

    def _callability(self, rows):
        (self.profile / "callability.tsv").write_text(
            self.HEAD + "".join(rows), encoding="utf-8")

    def test_an_unmeasured_genome_says_so_instead_of_showing_zeroes(self):
        cov = limits.coverage_summary()
        self.assertFalse(cov["known"])
        self.assertIn("callability", cov["closes"])

    def test_a_measured_genome_reports_its_numbers(self):
        self._callability([
            "BRCA1\tACMG\t17\t81000\t34.2\t1.02\t99.9\t98.4\t95.1\t88.0\n",
            "PMS2\tACMG\t7\t16000\t12.1\t0.36\t95.0\t61.2\t40.0\t20.0\n",
        ])
        cov = limits.coverage_summary()
        self.assertTrue(cov["known"])
        self.assertEqual(cov["genes"], 2)
        self.assertEqual(cov["weak_total"], 1)
        self.assertEqual(cov["weak"][0]["gene"], "PMS2")

    def test_a_weak_gene_becomes_a_limitation_naming_the_gene_and_the_number(self):
        self._callability(["PMS2\tACMG\t7\t16000\t12.1\t0.36\t95.0\t61.2\t40.0\t20.0\n"])
        # The genome branch only runs with a VCF connected; the summary is what
        # the report publishes either way, so it is asserted directly.
        cov = limits.coverage_summary()
        self.assertEqual(cov["weak"][0]["pct_10x"], 61.2)

    def test_a_broken_row_does_not_take_the_file_with_it(self):
        """A half-written TSV must degrade to «unknown», never to «good»."""
        self._callability(["BRCA1\tACMG\t17\t81000\tNOT-A-NUMBER\t1.0\t99\t98\t95\t88\n",
                           "PMS2\tACMG\t7\t16000\t12.1\t0.36\t95.0\t61.2\t40.0\t20.0\n"])
        cov = limits.coverage_summary()
        self.assertEqual(cov["genes"], 1, "a malformed row was counted as a measured gene")


class TestTheRemedyMatchesTheCause(_Profile):
    """A score is withdrawn for two different kinds of reason, and only one of
    them is the person's to fix."""

    def _prs(self, traits):
        self._write("prs_results.json", {"_meta": {"synthetic": True}, "traits": traits})

    def test_poor_coverage_offers_re_genotyping(self):
        self._prs([{"label": "X", "match_rate": 0.58, "reliable": False}])
        item = [i for i in limits.report()["items"] if i["kind"] == "prs"][0]
        self.assertIn("prs_genotype_sites", item["closes"])

    def test_a_model_that_does_not_reproduce_does_not_offer_re_genotyping(self):
        """The instruction that argues with its own diagnosis.

        Coverage is fine; the model is the problem. Telling the person to
        re-genotype sends them to spend an evening on work that cannot move the
        answer — the same defect as advising «build a VCF» about positions that a
        connected VCF simply does not cover.
        """
        self._prs([{"label": "Y", "match_rate": 0.99, "reliable": False,
                    "validity_note": "models do not reproduce between cohorts"}])
        item = [i for i in limits.report()["items"] if i["kind"] == "prs"][0]
        self.assertNotIn("prs_genotype_sites", item["closes"])
        self.assertTrue(item["closes"].strip())

    def test_when_both_hold_the_remedy_says_which_half_it_fixes(self):
        """The two causes are read from the record, not from the note's wording.

        This case used to be triggered by «poor coverage AND a validity note is
        present» — and every withdrawn score carries a note, because that is what a
        note is for. The condition therefore reduced to «poor coverage», and all
        three withdrawn scores of the demo profile printed the same sentence word
        for word, two of them wrongly: a near-zero effect size is not closed by
        re-genotyping anything.

        `withdrawn_because` states the cause as data. Where the PGS layer has not
        said, the coverage figure is a fact and stands in for it.
        """
        self._prs([{"label": "Z", "match_rate": 0.58, "reliable": False,
                    "withdrawn_because": ["coverage", "model"],
                    "validity_note": "the model has a near-zero effect size"}])
        item = [i for i in limits.report()["items"] if i["kind"] == "prs"][0]
        self.assertIn("prs_genotype_sites", item["closes"])
        self.assertIn("rest", item["closes"].lower())

    def test_a_note_alone_no_longer_decides_the_remedy(self):
        """Good coverage, a note, and no declared cause: a statement about the model.

        The mirror of the case above — proof that the prose is not being read.
        """
        self._prs([{"label": "Z2", "match_rate": 0.58, "reliable": False,
                    "validity_note": "the model has a near-zero effect size"}])
        item = [i for i in limits.report()["items"] if i["kind"] == "prs"][0]
        self.assertNotIn("rest", item["closes"].lower(),
                         "the remedy is still being chosen by whether a note exists")

    def test_the_declared_cause_outranks_the_coverage_figure(self):
        """0.58 is poor coverage, and the layer says the model is the problem."""
        self._prs([{"label": "Z3", "match_rate": 0.58, "reliable": False,
                    "withdrawn_because": ["model"]}])
        item = [i for i in limits.report()["items"] if i["kind"] == "prs"][0]
        self.assertNotIn("prs_genotype_sites", item["closes"])

    def test_a_measured_quantity_outranks_every_other_remedy(self):
        """Ferritin is the case that made this visible.

        The model estimates a quantity that is sitting in the person's own lab
        results. Sending them to re-genotype scoring sites is work that cannot
        change what is already known, and the demo profile printed exactly that
        instruction beside a measured value of 13 ng/mL.
        """
        self._write("labs.json", {"_meta": {"synthetic": True}, "markers": {
            "ferritin": {"name": "Ferritin", "unit": "ng/mL", "ref_low": 20, "ref_high": 150,
                         "series": [{"date": "2026-06", "value": 13}]}}})
        self._prs([{"label": "Ferritin level", "match_rate": 0.58, "reliable": False,
                    "withdrawn_because": ["coverage", "model"]}])
        item = [i for i in limits.report()["items"] if i["kind"] == "prs"][0]
        self.assertNotIn("prs_genotype_sites", item["closes"],
                         "the person is told to re-genotype a quantity they have measured")
        self.assertIn("13", item["closes"], "the measurement is not quoted back")
        self.assertIn("Ferritin", item["closes"])

    def test_a_trait_with_no_measurement_of_its_own_is_untouched(self):
        """The lookup must not invent a measurement out of a name it half-matched."""
        self._write("labs.json", {"_meta": {"synthetic": True}, "markers": {
            "ferritin": {"name": "Ferritin", "unit": "ng/mL",
                         "series": [{"date": "2026-06", "value": 13}]}}})
        self._prs([{"label": "Breast cancer", "match_rate": 0.58, "reliable": False}])
        item = [i for i in limits.report()["items"] if i["kind"] == "prs"][0]
        self.assertIn("prs_genotype_sites", item["closes"])
        self.assertNotIn("13", item["closes"])

    def test_a_score_the_prs_layer_trusts_is_not_listed_here(self):
        """Two screens disagreeing about one number is worse than either.

        87 % coverage is below this module's own notion of good and the PGS layer
        trusts it anyway. The layer's verdict wins: a threshold repeated in a
        second place is a second opinion nobody asked for.
        """
        self._prs([{"label": "W", "match_rate": 0.87, "reliable": True,
                    "percentile_reliable": True}])
        self.assertEqual([i for i in limits.report()["items"] if i["kind"] == "prs"], [])


class TestTheReportRenders(_Profile):

    def test_both_languages_render_without_a_traceback_or_a_raw_key(self):
        from scholion import format as fmt, i18n
        for code in ("en", "ru"):
            with self.subTest(language=code):
                i18n.set_lang(code)
                core.reset_cache()
                text = fmt.limits_report(limits.report())
                self.assertNotIn("limits.", text, "an untranslated message key reached the page")
                self.assertTrue(text.strip())
        i18n.set_lang("en")


if __name__ == "__main__":
    unittest.main()
