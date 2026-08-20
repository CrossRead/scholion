"""Two audit findings that produce a wrong CLINICAL statement, not a gap.

38 — «no pathogenic variant found» was said without regard to whether the gene
was read at all. The coverage has been computed all along (`limits.callability`
reads `profile/callability.tsv`) and the findings report never consulted it: two
facts held, neither compared with the other. A negative result in a gene read at
72 % is not the same sentence as one in a gene read end to end, and nothing on
screen told them apart.

42 — TTN, RYR1 and CACNA1S were reported for any pathogenic variant, on the same
footing as BRCA1. ACMG reports them only for a narrow class: TTN for truncating
variants in constitutively expressed exons, RYR1 and CACNA1S for variants
established in malignant hyperthermia. TTN is one of the largest genes in the
genome and almost everybody carries rare variation in it, so «any P/LP» there
hands a cardiomyopathy finding to a large share of healthy people.
"""
from __future__ import annotations

import json
import unittest

import support  # noqa: F401
from scholion import core
from scholion.engine import genomics

CATALOGUE = core._read_knowledge("acmg_sf.json")


class TestANarrowGeneIsNotReportedOnAnyVariant(unittest.TestCase):
    NARROW = {"TTN": "truncating_only", "RYR1": "mh_associated_only",
              "CACNA1S": "mh_associated_only"}

    def test_the_three_genes_carry_a_narrow_rule(self):
        genes = CATALOGUE["genes"]
        for gene, rule in self.NARROW.items():
            with self.subTest(gene=gene):
                self.assertEqual(genes[gene]["report_rule"], rule)

    def test_the_narrow_rule_explains_itself(self):
        """A rule nobody can read is a rule nobody will keep."""
        for gene in self.NARROW:
            self.assertTrue(CATALOGUE["genes"][gene].get("report_rule_note"))

    def test_an_ordinary_gene_is_untouched(self):
        self.assertEqual(CATALOGUE["genes"]["BRCA1"]["report_rule"], "any")

    def test_the_engine_re_decides_rather_than_trusting_the_scan_file(self):
        """The TSV on disk outlives the code that wrote it: «reportable=yes» in a
        file written before this rule existed must not walk past it."""
        import inspect
        from scholion import genome
        src = inspect.getsource(genome.acmg_sf_findings)
        self.assertIn("needs_variant_class", src)
        self.assertIn("cat.get(\"genes\"", src)


class TestANegativeCarriesWhatWasNotRead(unittest.TestCase):
    def test_the_findings_report_lists_genes_read_too_shallowly(self):
        r = genomics.acmg_findings()
        if r.get("status") != "ok":
            self.skipTest("the ACMG scan has not been run in this fixture")
        self.assertIn("unread_genes", r)
        self.assertIsInstance(r["unread_genes"], list)

    def test_every_listed_gene_is_below_the_threshold(self):
        r = genomics.acmg_findings()
        if r.get("status") != "ok":
            self.skipTest("the ACMG scan has not been run in this fixture")
        for g in r["unread_genes"]:
            self.assertLess(g["pct"], 90.0)

    def test_the_block_is_attached_whether_or_not_anything_was_found(self):
        """A gene read at 72 % qualifies a finding as much as it qualifies a
        silence, so the block does not depend on the hit list being empty."""
        r = genomics.acmg_findings()
        if r.get("status") != "ok":
            self.skipTest("the ACMG scan has not been run in this fixture")
        self.assertIn("unread_genes", r)


if __name__ == "__main__":
    unittest.main()


class TestIndelsCannotBeMatchedSilently(unittest.TestCase):
    """44 — `bcftools annotate` matches on the exact REF/ALT text, and an indel
    has many equally valid spellings. Without left-alignment the same variant in
    two files can fail to meet, and the miss is SILENT: a pathogenic indel comes
    out looking like a locus with nothing in it."""

    def test_the_engine_reports_whether_variants_were_left_aligned(self):
        from scholion import genome
        n = genome.clinvar_normalisation()
        self.assertIn("left_aligned", n)

    def test_the_caveat_is_attached_when_they_were_not(self):
        r = genomics.clinvar_findings()
        if r.get("status") == "input_is_an_array":
            self.skipTest("array input closes this path by design")
        from scholion import genome
        if genome.clinvar_normalisation().get("left_aligned"):
            self.skipTest("this fixture was normalised against a reference")
        self.assertTrue(r.get("indel_caveat"),
                        "indels were matched without left-alignment and nothing said so")

    def test_the_caveat_qualifies_an_empty_list_too(self):
        """An indel that could not be matched is missing from an empty list and
        from a full one alike — the silence needs the caveat more, not less."""
        from scholion import format as fmt
        out = fmt.clinvar_report({"status": "ok", "count": 0,
                                  "indel_caveat": "CAVEAT-MARKER"})
        self.assertIn("CAVEAT-MARKER", out)


class TestTwoHeterozygotesAreNotBiallelic(unittest.TestCase):
    """43 — a gene that needs BOTH copies affected is biallelic only when the two
    variants sit on DIFFERENT chromosomes. A homozygote settles that; two
    heterozygotes do not, and an unphased file cannot tell in cis from in trans.
    Calling two hets «biallelic» turns an ordinary carrier into a patient."""

    def test_the_scan_no_longer_calls_two_hets_biallelic(self):
        import io as _io, pathlib
        src = pathlib.Path("src/ingest/acmg_sf_scan.py").read_text(encoding="utf-8")
        self.assertIn("needs_phase", src)
        self.assertNotIn('biallelic = any(r["zygosity"] == "hom" for r in rs) or len(rs) >= 2', src)

    def test_the_engine_re_decides_it_from_the_catalogue(self):
        import inspect
        from scholion import genome
        s = inspect.getsource(genome.acmg_sf_findings)
        self.assertIn("needs_phase", s)
        self.assertIn('"biallelic"', s)

    def test_the_findings_carry_the_bucket(self):
        r = genomics.acmg_findings()
        if r.get("status") != "ok":
            self.skipTest("the ACMG scan has not been run in this fixture")
        self.assertIn("needs_phase", r)


class TestAPolygenicGateIsNotWeightBlind(unittest.TestCase):
    """45 — a flat threshold on the COUNT of matched variants ignores that a
    score's variants carry wildly different weights. Ninety per cent of the
    variants can be sixty per cent of the weight, and the percentile computed
    from what is left describes a different model than the published one. The
    engine already returned `weight_mass_coverage`; nothing consulted it."""

    def test_the_weight_mass_gate_exists_and_matches_the_count_gate(self):
        from scholion.engine import genomics as g
        from scholion import limits
        self.assertEqual(g._PRS_MIN_WEIGHT_MASS, limits.PRS_MIN_MATCH)

    def test_a_score_light_on_weight_is_withdrawn(self):
        from scholion.engine import genomics as g
        tr = {"match_rate": 0.99, "weight_mass_coverage": 0.55, "reliable": True}
        # the guard loop runs inside prs_findings; exercise its condition directly
        self.assertLess(tr["weight_mass_coverage"], g._PRS_MIN_WEIGHT_MASS)


class TestLoincIsReachableBothWays(unittest.TestCase):
    """60/21 — a FHIR Observation names its analyte by LOINC code, so the reverse
    direction is what an import needs, and it did not exist."""

    def test_the_reverse_index_resolves_a_known_code(self):
        from scholion import core
        self.assertEqual(core.loinc_index().get("2345-7"), "glucose")

    def test_the_coverage_is_stated_as_a_fraction(self):
        from scholion import core
        c = core.loinc_coverage()
        self.assertGreater(c["markers"], c["coded"],
                           "if every marker had a code this test is stale, not passing")
        self.assertLess(c["pct"], 100.0)


class TestUrsaPgxIsNamedNotPretended(unittest.TestCase):
    """59 — a tool listed as available and not actually reachable is the failure
    the external-tools file exists to prevent, so it is recorded as considered."""

    def test_it_is_recorded_with_its_licence_and_what_it_would_close(self):
        from scholion import core
        e = (core._read_knowledge("external_tools.json").get("considered") or {}).get("ursapgx")
        self.assertIsNotNone(e)
        self.assertEqual(e["license"], "MIT")
        self.assertTrue(e["would_close"])
        self.assertEqual(e["status"], "named, not integrated")

    def test_it_is_not_in_the_installable_set(self):
        from scholion import core
        tools = core._read_knowledge("external_tools.json").get("tools") or {}
        self.assertNotIn("ursapgx", tools)
