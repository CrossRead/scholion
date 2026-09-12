"""On a full genome with only the ACMG scan, its 84 genes were «not put through
ClinVar» like every other, the reason printed as a code on two hundred lines,
and an authored «asked about» position counted as a finding. Found 13.09.2026
on a Genome in a Bottle sample; all three held here against mocked frames,
never a real genome.
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401
from scholion import format as fmt
from scholion.engine import genomics, panel_form, system_panels as SP

SCAN_OK = {"status": "ok", "genes": []}
WIDE_NOT_RUN = {"status": "not_run", "reason": "no_annotation"}
ACMG_OK = {"status": "ok", "scanned": "2026-09-13",
           "hits": [{"gene": "LDLR", "clnsig": "Pathogenic", "zygosity": "het", "reportable": True}]}


def _frames(acmg=ACMG_OK):
    return (mock.patch.object(panel_form, "scan_for", lambda genes: {**SCAN_OK, "genes": sorted(genes)}),
            mock.patch.object(genomics, "clinvar_findings", lambda: WIDE_NOT_RUN),
            mock.patch.object(genomics, "acmg_findings", lambda: acmg))


class TestTheScanCountsForItsGenes(unittest.TestCase):

    def test_an_acmg_gene_is_through_clinvar_and_the_rest_say_so_in_words(self):
        a, b, c = _frames()
        with a, b, c:
            r = SP.system("lipids", "clinician")
        rows = {x["gene"]: x for x in r["genetics"]["rows"] if x["unit"] == "gene"}
        ldlr, abca1 = rows["LDLR"], rows["ABCA1"]
        self.assertEqual("acmg_scan", ldlr["clinvar"]["via"])
        self.assertEqual(1, ldlr["clinvar"]["hits"])
        self.assertEqual(1, ldlr["findings"], "a pathogenic hit the scan found is a finding")
        self.assertNotEqual("clinvar_not_run", ldlr.get("read_why"),
                            "the scan put this gene through ClinVar")
        self.assertEqual("clinvar_not_run", abca1["read_why"])
        self.assertTrue(abca1["read_why_text"])
        self.assertNotEqual(abca1["read_why"], abca1["read_why_text"], "a sentence, not the code")
        self.assertEqual("finding", r["verdict"]["kind"])

    def test_the_genome_basket_groups_the_unread_by_reason_and_names_what_closes_it(self):
        a, b, c = _frames()
        with a, b, c:
            r = SP.system("lipids")
        groups = [x for x in r["next"]["genome"]["rows"] if x["origin"] == "unread_group"]
        self.assertTrue(groups)
        by = {g["why"]: g for g in groups}
        self.assertIn("clinvar_not_run", by)
        self.assertIn("ABCA1", by["clinvar_not_run"]["genes"])
        self.assertEqual(by["clinvar_not_run"]["n"], len(by["clinvar_not_run"]["genes"]))
        self.assertIn("preparing-the-genome", by["clinvar_not_run"]["closes"])
        self.assertNotIn("clinvar_not_run", by["clinvar_not_run"]["text"], "no code in the sentence")
        text = fmt.system_report(r)
        self.assertIn(by["clinvar_not_run"]["closes"], text)
        self.assertNotIn("(clinvar_not_run)", text)


class TestAnAskedAboutPositionIsPrintedAndIsNotAFinding(unittest.TestCase):

    CUR = {"_meta": {}, "systems": {"adrenals": {"source": "a test", "positions": [
        {"rsid": "rs0", "gene": "GX", "hgvs": "NC_000022.11:g.1G>A", "risk_allele": "A", "mode": "pgx",
         "kind": "asked_about", "source": "a test",
         "text": {"het": {"en": "one copy: nothing follows", "ru": "one copy: nothing follows"},
                  "hom": {"en": "two copies: nothing follows", "ru": "two copies: nothing follows"}}}]}}}

    def _card(self, register):
        a, b, c = _frames()
        with a, b, c, mock.patch.object(SP, "_curated", lambda: self.CUR), \
                mock.patch.object(SP, "_genotype", lambda rsid, hgvs, gene, risk, scan:
                                  {"state": "het", "read": True, "genotype": "GA", "confidence": "called", "depth": 40}):
            return SP.system("adrenals", register)

    def test_both_registers_print_the_row_with_its_state_and_no_finding(self):
        for reg in ("patient", "clinician"):
            with self.subTest(register=reg):
                r = self._card(reg)
                (row,) = [x for x in r["genetics"]["rows"] if x.get("rsid") == "rs0"]
                self.assertEqual("het", row["state"])
                self.assertEqual(0, row["findings"])
                self.assertEqual("kind", row["not_a_finding_why"])
                self.assertEqual("one copy: nothing follows", row["text"])
                self.assertNotEqual("finding", r["verdict"]["kind"])
                text = fmt.system_report(r)
                self.assertIn("one copy of the named allele", text)
                self.assertNotIn("not determined", text.split("**4.")[0])


if __name__ == "__main__":
    unittest.main()
