"""A gene is asked of every shelf that holds anything about one.

What this build knows about a gene is kept in several places, each keyed
differently: the curated catalogue by rsID, the ClinVar scan by coordinate, the
ACMG secondary-findings panel by symbol, coverage by gene. Nothing joined them.
The path a person naturally takes — `genome --gene X` — read the catalogue alone
and answered «not in the coordinate reference», which is a statement about one
shelf and reads as a statement about the genome.

A clinician asked about the bile-acid transporters and was told there was nothing
to say «even in general terms from your genome». The ClinVar table on that machine
held 386 findings, and ABCB4 and ABCB11 carry real pathogenic variants. Nobody
looked, because nothing could: the scan table has no gene column, and the command
had no way to filter by one.

Two things are held here. A gene is matched to ClinVar findings by COORDINATE,
which needs no re-scan and fails honestly when the coordinate cannot be had. And
every layer reports one of three states — what it holds, that it holds nothing,
or that it could not be asked and what would let it be. A layer silently skipped
is the defect this file exists to prevent.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import format as fmt
from scholion.engine import genomics as G


GENE = {"chrom": "chr7", "start": 100, "end": 200,
        "assembly": "GRCh38", "resolved_by": "gff3"}

HITS = {"status": "ok", "count": 4, "hits": [
    {"chrom": "chr7", "pos": "150", "rsid": "rs1", "tier": "pathogenic"},
    {"chrom": "7", "pos": "199", "rsid": "rs2", "tier": "risk"},      # same chromosome, other spelling
    {"chrom": "chr7", "pos": "201", "rsid": "rs3", "tier": "risk"},   # just outside
    {"chrom": "chr8", "pos": "150", "rsid": "rs4", "tier": "risk"},   # another chromosome
]}


def with_gene(rec, hits=HITS):
    return (mock.patch.object(G, "clinvar_findings", return_value=hits),
            mock.patch("scholion.genes.resolve", return_value=rec))


class TestAGeneIsMatchedByCoordinate(unittest.TestCase):

    def run_for(self, rec, hits=HITS):
        a, b = with_gene(rec, hits)
        with a, b:
            return G.clinvar_for_gene("ABCB4")

    def test_only_the_findings_inside_the_gene_come_back(self):
        r = self.run_for(GENE)
        self.assertEqual("ok", r["status"])
        self.assertEqual(["rs1", "rs2"], [h["rsid"] for h in r["hits"]])

    def test_the_two_spellings_of_a_chromosome_are_one_chromosome(self):
        """`chr7` in the scan table and `7` in the gene record. A join that fails
        on the prefix returns «nothing found», which is the worst wrong answer
        available here."""
        r = self.run_for({**GENE, "chrom": "7"})
        self.assertEqual(["rs1", "rs2"], [h["rsid"] for h in r["hits"]])

    def test_the_bounds_are_inclusive_and_do_not_leak(self):
        r = self.run_for({**GENE, "start": 150, "end": 199})
        self.assertEqual(["rs1", "rs2"], [h["rsid"] for h in r["hits"]])
        r = self.run_for({**GENE, "start": 151, "end": 198})
        self.assertEqual([], r["hits"])

    def test_a_gene_with_no_coordinates_is_not_a_gene_with_no_findings(self):
        r = self.run_for(None)
        self.assertEqual("gene_unresolved", r["status"])
        self.assertIsNone(r.get("count"), "an unresolved gene reported a count")
        self.assertTrue(r.get("fix"), "the refusal does not say what would close it")

    def test_the_finding_carries_the_gene_it_was_matched_to(self):
        r = self.run_for(GENE)
        self.assertEqual({"ABCB4"}, {h["gene"] for h in r["hits"]})


class TestEveryLayerReports(unittest.TestCase):

    def layers(self, **over):
        base = {"gene": "BRCA1",
                "catalogue": {"count": 0},
                "clinvar": {"status": "ok", "count": 2, "resolved_by": "gff3",
                            "region": {"chrom": "chr17", "start": 1, "end": 9}},
                "acmg": {"in_panel": True, "count": 0, "unread": False},
                "coverage": {"measured": False}}
        base.update(over)
        return base

    def test_every_layer_gets_a_line(self):
        out = fmt.gene_layers_report(self.layers())
        self.assertEqual(5, len([l for l in out.split("\n") if l.startswith(("·", "**"))]),
                         out)

    def test_a_layer_that_could_not_be_asked_says_so_and_why(self):
        out = fmt.gene_layers_report(self.layers(
            clinvar={"status": "gene_unresolved", "fix": "a local GFF3 closes it"}))
        self.assertIn("cannot be asked", out)
        self.assertIn("a local GFF3 closes it", out)

    def test_membership_of_the_shipped_panel_is_answered_without_a_coordinate(self):
        """The 84 symbols travel inside the build. A gene named in one place may
        not be unknown in another — which is what happened to BRCA1 on a machine
        with no annotation file and no network."""
        out = fmt.gene_layers_report(self.layers(
            clinvar={"status": "gene_unresolved", "fix": "x"}))
        self.assertIn("ACMG SF panel: in it", out)

    def test_a_gene_outside_the_panel_is_told_from_one_inside_it(self):
        out = fmt.gene_layers_report(self.layers(acmg={"in_panel": False}))
        self.assertIn("not in it", out)

    def test_unmeasured_coverage_qualifies_the_silence(self):
        out = fmt.gene_layers_report(self.layers())
        self.assertIn("nothing in the part that was read", out)

    def test_the_frame_comes_before_the_findings(self):
        """A reader told which shelves were asked only afterwards has already
        read the silence as an answer."""
        r = {"status": "ok", "gene": "DPYD", "layers": self.layers(),
             "loci": [], "disclaimer": "—"}
        out = fmt.genome_report(r)
        self.assertLess(out.index("What this build holds"), out.index("loci:"),
                        out[:200])


class TestTheShippedPanelIsReadWithoutTheNetwork(unittest.TestCase):

    def test_a_panel_gene_is_recognised_offline(self):
        with mock.patch("scholion.genes.resolve", return_value=None):
            self.assertTrue(G.gene_layers("BRCA1")["acmg"]["in_panel"])

    def test_a_gene_outside_the_panel_is_not(self):
        with mock.patch("scholion.genes.resolve", return_value=None):
            self.assertFalse(G.gene_layers("ABCB4")["acmg"]["in_panel"])


class TestWhatISkippedCheckingTheFirstTime(unittest.TestCase):
    """Four defects the first pass introduced, found by re-reading it as somebody
    else's work. Every one is a silent wrong answer of the kind this project
    refuses everywhere else — which is what made them worth a class of their own.
    """

    def test_a_truncated_scan_cannot_say_the_gene_is_clear(self):
        """`clinvar_findings` returns a PAGE and reports the total. Filtering the
        page by gene and printing «0 in this gene» is a false negative, and it
        would be silent."""
        short = {"status": "ok", "count": 900,
                 "hits": [{"chrom": "chr9", "pos": "5", "rsid": "r", "tier": "risk"}]}
        with mock.patch.object(G, "clinvar_findings", return_value=short), \
             mock.patch("scholion.genes.resolve", return_value=GENE):
            r = G.clinvar_for_gene("X")
        self.assertEqual({"read": 1, "of": 900}, r["truncated"])

    def test_a_complete_scan_carries_no_such_warning(self):
        with mock.patch.object(G, "clinvar_findings", return_value=HITS), \
             mock.patch("scholion.genes.resolve", return_value=GENE):
            r = G.clinvar_for_gene("X")
        self.assertIsNone(r.get("truncated"))

    def test_the_warning_reaches_the_reader(self):
        out = fmt.clinvar_gene_report(
            {"gene": "X", "status": "ok", "count": 0, "hits": [], "scanned": 900,
             "resolved_by": "gff3", "region": {"chrom": "chr9", "start": 1, "end": 9},
             "truncated": {"read": 1, "of": 900}})
        self.assertIn("900", out)

    def test_a_frame_that_could_not_be_built_says_so(self):
        """It used to be swallowed, so a reader saw a page with no frame and no
        reason to think one was owed."""
        with mock.patch.object(G, "gene_layers", side_effect=RuntimeError("x")), \
             mock.patch("scholion.genome.lookup", return_value={"status": "ok", "gene": "X"}):
            r = G.genome_lookup(gene="X")
        self.assertEqual("unavailable", r["layers"]["status"])

    def test_a_short_name_does_not_earn_a_pharmacogenetic_tag(self):
        """The containment rule was copied out of a lookup where the caller has
        already typed a drug name. Here it labels a list, and one letter of a
        supplement's name matched a three-letter catalogue entry."""
        kb = {"drugs": [{"names": ["ипп", "omeprazole"], "gene": "CYP2C19"}]}
        with mock.patch("scholion.core.cpic_kb", return_value=kb):
            self.assertEqual("", fmt._pgx_mark("и"))
            self.assertEqual("", fmt._pgx_mark("п"))
            self.assertIn("CYP2C19", fmt._pgx_mark("ипп"),
                          "an exact name stopped matching")
            self.assertIn("CYP2C19", fmt._pgx_mark("Omeprazole 20"),
                          "a real containment stopped matching")

    def test_a_folded_note_has_a_ceiling(self):
        """A «first sentence» in this data can itself run three hundred
        characters."""
        note = "Х" * 400 + ". хвост"
        with mock.patch("scholion.core.cpic_kb", return_value={"drugs": []}):
            out = fmt.medications_report({"medications": [{"name": "x", "note": note}]})
        line = [l for l in out.split("\n") if l.strip().startswith("·")][0]
        self.assertLess(len(line), 200, line[:80])


class TestHowWellThisGeneWasRead(unittest.TestCase):
    """Coverage comes with the answer about the gene — and only when it is worth
    saying.

    The ruler is the file's own middle, and that was measured before it was
    chosen. On a 30× whole genome the callable fraction at 20× runs: median 79.8,
    best gene 92, and not one of ninety-three reaching 95. An absolute clinical
    threshold therefore fires on 89 of 93 — which is the project's own rule about
    a flag that goes off on everything: it measures a property of the data, not
    of the objects. Against the median, eight fire, and they are the genes that
    are hard to sequence for known reasons — X-linked, pseudogene homology,
    GC-rich.

    Four states, one of them silent. `fine` means «not unusual for this file» and
    never «adequate»: what is adequate depends on the question, which the product
    does not know. The other three speak, because a silence meaning «nobody
    measured» is read as reassurance — the same mistake as a missing row printing
    as «reference».
    """

    TABLE = {f"G{i}": {"pct_20x": "80.0"} for i in range(20)}

    def test_a_gene_far_below_its_own_files_middle_is_low(self):
        t = {**self.TABLE, "GLA": {"pct_20x": "8.3"}}
        self.assertEqual("low", G.gene_coverage("GLA", t)["state"])

    def test_a_gene_in_line_with_the_file_is_not(self):
        t = {**self.TABLE, "BRCA1": {"pct_20x": "67.5"}}
        self.assertEqual("fine", G.gene_coverage("BRCA1", t)["state"])

    def test_the_rule_does_not_fire_on_everything(self):
        """The whole reason the ruler is relative. A check that flags almost every
        object is measuring the data."""
        fired = sum(1 for g in self.TABLE if G.gene_coverage(g, self.TABLE)["state"] == "low")
        self.assertEqual(0, fired, "a file of evenly read genes flagged some of them")

    def test_a_file_read_badly_throughout_still_speaks(self):
        """The relative rule alone would go quiet on a file where everything is
        equally bad, because nothing is far from the middle."""
        t = {f"G{i}": {"pct_20x": "20.0"} for i in range(10)}
        self.assertEqual("low", G.gene_coverage("G1", t)["state"])

    def test_a_gene_outside_the_table_is_not_a_gene_with_good_coverage(self):
        c = G.gene_coverage("ABCB4", self.TABLE)
        self.assertEqual("gene_not_in_table", c["state"])
        self.assertEqual(len(self.TABLE), c["table_size"])

    def test_no_table_at_all_is_its_own_state(self):
        self.assertEqual("not_measured", G.gene_coverage("X", {})["state"])

    def test_the_number_travels_with_every_verdict(self):
        """A verdict without the measurement behind it is what this layer exists
        to refuse."""
        t = {**self.TABLE, "GLA": {"pct_20x": "8.3"}}
        line = fmt._coverage_line(G.gene_coverage("GLA", t))
        self.assertIn("8.3", line)
        self.assertIn("80.0", line, "the middle it is being compared against is not shown")

    def test_the_quiet_state_does_not_promise_adequacy(self):
        t = {**self.TABLE, "BRCA1": {"pct_20x": "78.0"}}
        line = fmt._coverage_line(G.gene_coverage("BRCA1", t))
        self.assertNotIn("adequate", line.lower())
        self.assertNotIn("enough", line.lower().replace("«enough»", ""))

    def test_a_single_locus_carries_it_where_there_is_no_frame(self):
        r = {"status": "ok", "rsid": "rs1", "gene": "APOE", "chrom": "19",
             "pos": 1, "result": {"genotype": "TT", "confidence": "called"},
             "coverage": {"state": "low", "pct_20x": 57.7, "median_pct_20x": 79.8},
             "disclaimer": "—"}
        self.assertIn("57.7", fmt.genome_report(r))

    def test_and_stays_quiet_on_a_well_read_one(self):
        r = {"status": "ok", "rsid": "rs1", "gene": "SLCO1B1", "chrom": "12",
             "pos": 1, "result": {"genotype": "TT", "confidence": "called"},
             "coverage": {"state": "fine", "pct_20x": 78.0}, "disclaimer": "—"}
        self.assertNotIn("78.0", fmt.genome_report(r))


NOT_RUN = {"status": "not_run", "hits": [], "count": None,
           "message": "Your VCF has not been annotated against ClinVar yet."}


class TestTheFrameBlamesTheRightThing(unittest.TestCase):
    """Found by the audit before 0.4.11. On the fixture — a gene resolved by
    the GFF3, a region in hand, and no scan table — the frame printed «the
    gene's coordinates were not obtained», and the ACMG line said «in it, 0
    findings» about a panel nobody had scanned. The first sends a reader to
    fetch an annotation file they did not need; the second is a false «clean»
    on hereditary cancer. Both were one branch that did not look at the status.
    """

    def frame_for(self, hits):
        with mock.patch.object(G, "clinvar_findings", return_value=hits), \
             mock.patch("scholion.genes.resolve", return_value=GENE):
            return G.gene_layers("BRCA1")

    def test_a_scan_that_was_not_run_is_not_a_gene_without_coordinates(self):
        out = fmt.gene_layers_report(self.frame_for(NOT_RUN))
        self.assertIn("scan has not been run", out)
        self.assertNotIn("coordinates were not obtained", out)

    def test_the_scans_own_sentence_travels_into_the_frame(self):
        """`clinvar_hits` puts its reason under `message`; the layer read only
        `reason` and `note`, so the commonest refusal arrived with no sentence
        and the renderer fell back to one about a broken index."""
        layers = self.frame_for(NOT_RUN)
        self.assertEqual(NOT_RUN["message"], layers["clinvar"]["scan_note"])
        self.assertIn("not been annotated", fmt.gene_layers_report(layers))

    def test_clinvar_by_gene_without_a_table_does_not_blame_the_index(self):
        with mock.patch.object(G, "clinvar_findings", return_value=NOT_RUN), \
             mock.patch("scholion.genes.resolve", return_value=GENE):
            out = fmt.clinvar_gene_report(G.clinvar_for_gene("BRCA1"))
        self.assertIn("not been annotated", out)
        self.assertNotIn("broken index", out)

    def test_a_panel_gene_nobody_scanned_has_no_count(self):
        layers = {"gene": "BRCA1", "catalogue": {"count": 0},
                  "clinvar": {"status": "not_run"},
                  "acmg": {"in_panel": True, "count": 0, "unread": None,
                           "status": "not_run"},
                  "coverage": {"measured": False}}
        out = fmt.gene_layers_report(layers)
        acmg = [l for l in out.split("\n") if "ACMG" in l]
        self.assertEqual(1, len(acmg), out)
        self.assertNotIn("0 finding", acmg[0], "a count was printed for a scan that never ran")
        self.assertIn("has not been run", acmg[0], acmg[0])

    def test_a_panel_gene_that_was_scanned_still_has_one(self):
        layers = {"gene": "BRCA1", "catalogue": {"count": 0},
                  "clinvar": {"status": "not_run"},
                  "acmg": {"in_panel": True, "count": 0, "unread": False, "status": "ok"},
                  "coverage": {"measured": False}}
        self.assertIn("0 findings", fmt.gene_layers_report(layers))

    def test_a_scan_that_failed_is_told_from_one_that_was_not_run(self):
        out = fmt.gene_layers_report({
            "gene": "X", "catalogue": {"count": 0},
            "clinvar": {"status": "error", "scan_note": "bad table"},
            "acmg": {"in_panel": True, "status": "error"},
            "coverage": {"measured": False}})
        self.assertIn("could not be asked (error)", out)
        self.assertIn("bad table", out)

    def test_the_truncation_warning_reaches_the_frame(self):
        """`clinvar_for_gene` set it; the layer did not copy it, and the frame
        said «0 in this gene» over a finding past the cut — the very defect
        the previous release fixed on the other path."""
        short = {"status": "ok", "count": 900,
                 "hits": [{"chrom": "chr9", "pos": "5", "rsid": "r", "tier": "risk"}]}
        layers = self.frame_for(short)
        self.assertEqual({"read": 1, "of": 900}, layers["clinvar"]["truncated"])
        self.assertIn("900", fmt.gene_layers_report(layers))


class TestANumberInTheFrameAgreesWithItsWord(unittest.TestCase):
    """Three literals that went past `plural()`, and a fold that cut at an
    abbreviation. Held here rather than in the catalogue walk, because that
    walk looks for `{n}` and these were spelled `{count}` and `{days}`."""

    def acmg_line(self, n):
        return fmt.gene_layers_report({
            "gene": "X", "catalogue": {"count": 0}, "clinvar": {"status": "not_run"},
            "acmg": {"in_panel": True, "count": n, "unread": False, "status": "ok"},
            "coverage": {"measured": False}})

    def test_one_finding_and_two_findings(self):
        self.assertIn("1 finding\n", self.acmg_line(1) + "\n")
        self.assertIn("2 findings", self.acmg_line(2))
        self.assertNotIn("finding(s)", self.acmg_line(2))

    def test_the_whole_table_count_agrees_too(self):
        r = {"gene": "X", "status": "ok", "count": 0, "hits": [], "resolved_by": "gff3",
             "region": {"chrom": "chr9", "start": 1, "end": 9}}
        self.assertIn("1 finding", fmt.clinvar_gene_report({**r, "scanned": 1}))
        self.assertIn("386 findings", fmt.clinvar_gene_report({**r, "scanned": 386}))

    def test_the_age_of_the_build_agrees(self):
        base = {"markers_total": 1, "abnormal_count": 0, "flagged": [],
                "high_flags": [], "watch_flags": [], "pending_suggestions": [],
                "genome_gaps": [], "disclaimer": "—"}
        one = fmt.overview_report({**base, "build": {
            "status": "ageing", "days": 1, "installed": "0.4.8", "released": "2026-07-12"}})
        many = fmt.overview_report({**base, "build": {
            "status": "ageing", "days": 60, "installed": "0.4.8", "released": "2026-07-12"}})
        self.assertIn("1 day ago", one)
        self.assertIn("60 days ago", many)

    def test_a_phrase_nothing_prints_is_not_kept(self):
        from scholion.i18n import en, ru
        for cat in (en.MESSAGES, ru.MESSAGES):
            self.assertNotIn("gene.layer.coverage_yes", cat)

    def test_the_fold_ceiling_has_a_name(self):
        self.assertIsInstance(fmt.NOTE_FOLD_CEILING, int)
        self.assertGreater(fmt.NOTE_FOLD_CEILING, 0)

    def test_a_fold_does_not_cut_at_an_abbreviation(self):
        self.assertEqual("Take with food, e.g. breakfast",
                         fmt._first_sentence("Take with food, e.g. breakfast. Then stop."))
        self.assertEqual("Утром, т.е. до еды",
                         fmt._first_sentence("Утром, т.е. до еды. Потом отмена."))

    def test_a_fold_still_cuts_at_a_sentence(self):
        self.assertEqual("First", fmt._first_sentence("First. Second."))


if __name__ == "__main__":
    unittest.main()
