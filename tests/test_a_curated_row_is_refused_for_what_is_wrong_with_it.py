"""A curated panel row is refused for what is wrong with it, and a strand error never reads as «absent».

The panel file is written by hand, and a wrong row does not look wrong. Until
task 199 the genotype count took the risk allele on trust: a letter that is not
one of the two at the position was counted in the person's genotype, found zero
times, and the card printed «the allele is absent». The machine check of the
clinicians' second round (17.09.2026) found five such rows among sixty-three;
each is a fixture below, refused by its own reason, with the coordinates as
Ensembl gives them for GRCh38.

Held here as well: every row shipped today passes; every sentence in the raw
file exists in both languages; the file names batches and roles, never a
person; and a genotype holding a letter not of its locus is not counted at all.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion.engine import panel_gate as G

SRC = "a named source"
BILINGUAL = {"en": "a sentence", "ru": "a sentence (ru)"}


def row(**over):
    base = {"rsid": "rs1", "gene": "GENE", "hgvs": "NC_000001.11:g.100A>G",
            "risk_allele": "G", "mode": "pgx", "source": SRC,
            "text": {"het": BILINGUAL, "hom": BILINGUAL},
            "submitter": "panel_2026_09_13",
            "review": {"by_role": "panel_author", "on": "2026-09-13", "scope": "sentence_against_source"}}
    base.update(over)
    return base


def why(p, levels=None, markers=("tsh",)):
    return G.refusal(p, list(markers), SRC, (p.get("source") if isinstance(p, dict) else "") or "", levels)


#: The five rows the second round sent back, as written, at their real loci.
FIVE = {
    # A ladder written in C/T at a point whose alleles are G/A.
    "CYP19A1 rs2470152": (row(gene="CYP19A1", rsid="rs2470152", hgvs="NC_000015.10:g.51302775G>A",
                              risk_allele="T", mode="common_variant", effect_size="OR 1.2",
                              ladder={"base": "CC", "het": "CT", "hom": "TT"}),
                          "risk_allele_not_at_locus"),
    # A risk allele T at a point that holds G and A.
    "SLC6A2 rs5569": (row(gene="SLC6A2", rsid="rs5569", hgvs="NC_000016.10:g.55697923G>A",
                          risk_allele="T", mode="common_variant", effect_size="OR 1.1"),
                      "risk_allele_not_at_locus"),
    # Risk TT in the columns; the ladder puts TT at the base and GG at the top.
    "ADIPOQ rs2241766": (row(gene="ADIPOQ", rsid="rs2241766", hgvs="NC_000003.12:g.186853103T>G",
                             risk_allele="T", mode="common_variant", effect_size="OR 1.3",
                             ladder={"base": "TT", "het": "TG", "hom": "GG"}),
                         "ladder_top_mismatch"),
    # The ladder refused, and a «risk genotype» kept beside the refusal.
    "HTR2A rs6311": (row(gene="HTR2A", rsid="rs6311", hgvs="NC_000013.11:g.46897343C>T",
                         risk_allele="T", mode="common_variant", effect_size="OR 1.1",
                         ladder="refused", risk_genotype="TT"),
                     "refusal_with_risk_genotype"),
    # Corrected to G/GG at a point whose plus-strand alleles are C/T.
    "KCNJ11 rs5215": (row(gene="KCNJ11", rsid="rs5215", hgvs="NC_000011.10:g.17387083C>T",
                          risk_allele="G", mode="common_variant", effect_size="OR 1.1"),
                      "risk_allele_not_at_locus"),
}


class TestTheFiveRowsTheSecondRoundSentBack(unittest.TestCase):

    def test_each_is_refused_by_its_own_reason(self):
        for name, (p, reason) in FIVE.items():
            with self.subTest(row=name):
                self.assertEqual(reason, why(p))

    def test_a_row_declared_on_the_minus_strand_is_read_on_the_plus_strand(self):
        """KCNJ11 lies on the minus strand: G there is C on the plus strand."""
        p = dict(FIVE["KCNJ11 rs5215"][0], strand="-")
        self.assertIsNone(why(p))
        self.assertEqual("C", G.risk_on_plus(p))


class TestEveryReasonRefuses(unittest.TestCase):

    CASES = {
        "not_a_row": "a string",
        "no_source": row(source=""),
        "no_rsid": row(rsid=""),
        "no_mode": row(mode="guess"),
        "bad_kind": row(kind="rumour"),
        "no_coordinate": row(hgvs="rs1 on chromosome 1"),
        "risk_allele_not_at_locus": row(risk_allele="T"),
        "ladder_top_mismatch": row(ladder={"base": "AA", "het": "AG", "hom": "AA"}),
        "refusal_with_risk_genotype": row(ladder="refused", risk_genotype="GG"),
        "text_not_bilingual": row(text={"en": "only English"}),
        "personal_name_in_package": row(submitter="Dr. Example Person"),
        "level_not_in_legend": row(evidence={"level": "Z"}),
        "level_e_with_text": row(evidence={"level": "E"}),
        "monogenic_without_classification_or_moi": row(mode="monogenic"),
        "common_variant_without_effect": row(mode="common_variant"),
        "expect_marker_not_in_panel": row(expect={"marker": "ferritin", "direction": "lower"}),
    }

    def test_each_reason_has_a_row_that_it_refuses(self):
        levels = {x: {} for x in "ABCDE"}
        for reason, p in self.CASES.items():
            with self.subTest(reason=reason):
                source = "" if reason == "no_source" else SRC
                got = G.refusal(p, ["tsh"], source, source, levels)
                self.assertEqual(reason, got)

    def test_a_reviewer_named_by_anything_but_a_role_is_refused(self):
        for review in ({"by_role": "Dr Somebody"}, "Dr Somebody", {"on": "2026-09-13"}):
            with self.subTest(review=review):
                self.assertEqual("personal_name_in_package", why(row(review=review)))
        self.assertEqual("personal_name_in_package", why(row(signed_by="owner")),
                         "the retired field could hold a name and is refused on sight")

    def test_a_good_row_passes(self):
        self.assertIsNone(why(row()))


class TestTheGenotypeIsCountedOnlyAtItsLocus(unittest.TestCase):

    def test_a_letter_not_of_the_locus_is_not_a_zero(self):
        at = ("G", "A")
        self.assertEqual(0, G.copies("GG", "A", at))
        self.assertEqual(1, G.copies("G/A", "A", at))
        self.assertIsNone(G.copies("CT", "T", at), "a genotype of another locus read as absent")
        self.assertIsNone(G.copies("--", "A", at))


class TestTheShippedPanelPassesAndSaysItInBothLanguages(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import json
        cls.raw = json.loads(core.knowledge_path("system_gene_panels.json").read_text(encoding="utf-8"))

    def positions(self):
        for key, spec in (self.raw.get("systems") or {}).items():
            for p in spec.get("positions") or []:
                yield key, spec, p

    def test_every_shipped_row_passes_the_gate_read_raw(self):
        from scholion.engine import system_panels as SP
        refused = []
        for key, spec, p in self.positions():
            markers = next((d.get("markers") or [] for d in SP.domains() if d["key"] == key), [])
            source = p.get("source") or spec.get("source") or ""
            if isinstance(source, dict):
                source = source.get("en") or ""
            reason = G.refusal(p, markers, source, source)
            if reason:
                refused.append((key, p.get("rsid"), reason))
        self.assertEqual([], refused)
        self.assertEqual(217, sum(1 for _ in self.positions()),
                         "the count changed — say so in the shipped pages in the same commit")

    def test_no_shipped_row_names_a_person(self):
        for key, _, p in self.positions():
            with self.subTest(row=(key, p.get("rsid"))):
                self.assertNotIn("signed_by", p)
                self.assertRegex(p.get("submitter") or "", G.BATCH)
                self.assertIn((p.get("review") or {}).get("by_role"), G.REVIEWERS)


if __name__ == "__main__":
    unittest.main()
