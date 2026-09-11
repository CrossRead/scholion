"""A branch that catches a failure reports it — it does not fall back to the
sentence a SUCCESS with nothing to say would print.

Seven `except Exception` branches in the diff before 0.4.11 did the second
thing, and the audit named each. A coverage table that could not be read said
«not measured», which sends the reader to run the measurement. A guideline
copy whose provenance could not be opened said "" — the same value a
provenance WITHOUT a date returns, printed as «—». A pharmacogenetic base
that failed to load marked every drug in the regimen «outside the model», and
the legend under the list confirmed it. The build's age said «unknown» for a
missing journal, a heading that had drifted, and a read that raised — one
word for three different states. And the coverage of a single locus simply
vanished with `pass`, which on a line printed only when it is worth saying is
indistinguishable from «fine».

Each is exercised here by making the call underneath it raise, and each is
required to leave a field or a phrase behind that names the failure. The
same tests reach the branches the suite's own coverage gate reported as never
executed — that reach was the cost of the silence.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import format as fmt
from scholion import limits
from scholion.engine import genomics as G
from scholion.engine import pgx, profile_view
from scholion.engine import sources as S


class TestCoverageThatCouldNotBeReadIsNotUnmeasured(unittest.TestCase):

    def test_a_gene_says_the_table_did_not_open(self):
        with mock.patch.object(limits, "callability", side_effect=OSError("locked")):
            c = G.gene_coverage("BRCA1")
        self.assertEqual("unavailable", c["state"])
        self.assertEqual("OSError", c["reason"])

    def test_the_frame_carries_the_same_state(self):
        with mock.patch.object(limits, "callability", side_effect=OSError("locked")), \
             mock.patch("scholion.genes.resolve", return_value=None):
            layers = G.gene_layers("BRCA1")
        self.assertEqual("unavailable", layers["coverage"]["state"])

    def test_the_line_names_the_reason_and_not_the_other_state(self):
        line = fmt._coverage_line({"state": "unavailable", "reason": "OSError"})
        self.assertIn("OSError", line)
        self.assertNotIn("not measured —", line)

    def test_a_single_locus_keeps_the_failure_instead_of_dropping_it(self):
        with mock.patch.object(G, "gene_coverage", side_effect=RuntimeError("x")), \
             mock.patch("scholion.genome.lookup",
                        return_value={"status": "ok", "gene": "APOE", "rsid": "rs1"}):
            r = G.genome_lookup(rsid="rs1")
        self.assertEqual("unavailable", r["coverage"]["state"])
        self.assertEqual("RuntimeError", r["coverage"]["reason"])


class TestThePanelLayerNamesItsFailure(unittest.TestCase):

    def test_the_reason_travels(self):
        with mock.patch.object(G, "acmg_findings", side_effect=KeyError("genes")), \
             mock.patch("scholion.genes.resolve", return_value=None):
            layers = G.gene_layers("BRCA1")
        self.assertEqual("unavailable", layers["acmg"]["status"])
        self.assertEqual("KeyError", layers["acmg"]["reason"])


class TestTheRegimenDoesNotDeclareEveryDrugOutsideTheModel(unittest.TestCase):

    def test_an_unreadable_base_is_a_mark_of_its_own(self):
        with mock.patch("scholion.core.cpic_kb", side_effect=ValueError("bad json")):
            mark = fmt._pgx_mark("atorvastatin")
        self.assertNotEqual("", mark, "the failure wore the mark of «outside the model»")
        self.assertIn("ValueError", mark)

    def test_a_drug_outside_the_model_is_still_unmarked(self):
        with mock.patch("scholion.core.cpic_kb", return_value={"drugs": []}):
            self.assertEqual("", fmt._pgx_mark("atorvastatin"))


class TestTheSnapshotDateSaysWhenItCouldNotBeRead(unittest.TestCase):

    def test_a_provenance_that_raises_is_not_an_empty_date(self):
        with mock.patch.object(S, "provenance", side_effect=OSError("gone")):
            got = pgx.cpic_snapshot()
        self.assertNotEqual("", got)
        self.assertIn("OSError", got)


class TestTheBuildSaysWhyItsAgeIsUnknown(unittest.TestCase):

    def test_a_journal_that_raises(self):
        with mock.patch("scholion.docs.path_of", side_effect=PermissionError("no")):
            r = S.build_freshness()
        self.assertEqual("unknown", r["status"])
        self.assertEqual("PermissionError", r["reason"])

    def test_a_heading_that_drifted(self):
        p = mock.Mock()
        p.read_text.return_value = "## v9.9.9 (12.09.2026)\n"
        with mock.patch("scholion.docs.path_of", return_value=p):
            r = S.build_freshness()
        self.assertEqual("unknown", r["status"])
        self.assertEqual("no_dated_heading", r["reason"])

    def test_no_journal_at_all(self):
        with mock.patch("scholion.docs.path_of", return_value=None):
            r = S.build_freshness()
        self.assertEqual("no_changelog", r["reason"])

    def test_the_overview_keeps_the_reason(self):
        with mock.patch("scholion.engine.sources.build_freshness",
                        side_effect=RuntimeError("x")):
            r = profile_view._build_freshness()
        self.assertEqual("unknown", r["status"])
        self.assertEqual("RuntimeError", r["reason"])

    def test_in_this_tree_the_age_is_known(self):
        """The regular expression wants `## vX — DD.MM.YYYY`, and any drift in
        the journal's heading made the age `unknown` — a word the earlier guard
        accepted. In the source tree the journal is present and this must
        resolve; it is the drift detector."""
        if not support.IN_SOURCE_REPO:
            self.skipTest("the packaged tree may ship without the journal")
        r = S.build_freshness()
        self.assertNotEqual("unknown", r["status"], r)
        self.assertIsNotNone(r["released"])


if __name__ == "__main__":
    unittest.main()
