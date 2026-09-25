"""The panel author's answers of 23.09.2026, read the way she wrote them (task 205 B, F, G, H, I).

* A man carries one copy of X: rs5934505 is read as that one copy — `hemi` —
  and a heterozygous call on his X is not a reading; with no sex on file the
  position is not read rather than read as a woman's.
* A ladder the author declined is not drawn from the locus.
* Carriership of a recessive gene has the class she named; OTC, on X, is not
  carriership in a man, and its sentence follows the sex and the variant class.
* Two different pathogenic variants in a two-copy gene are a result to phase,
  not two carriers.
* Elastase, the methionine load and ADMA/SDMA are offered only under her
  conditions; Trp:LNAA is computed with her denominator.
* Every new correction rule passes the route gate, and the positions of her list
  carry the corrected genes.
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

import support
from scholion import core, provenance
from scholion.engine import labs as LB, panel_form, panel_gate, panel_genotype as PG, routes, system_panels as SP

KNOW = support.ROOT / "src" / "scholion" / "knowledge"


def _raw(name):
    return json.loads((KNOW / name).read_text(encoding="utf-8"))


def _position(system, rsid):
    for p in _raw("system_gene_panels.json")["systems"][system]["positions"]:
        if p["rsid"] == rsid:
            return p
    raise KeyError(rsid)


class TestOneCopyOfX(unittest.TestCase):

    def test_the_position_is_on_x_outside_the_pseudoautosomal_regions(self):
        self.assertTrue(PG.on_x(_position("gonads", "rs5934505")))
        self.assertFalse(PG.on_x(_position("gonads", "rs1691053")))
        self.assertFalse(PG.on_x({"hgvs": "NC_000023.11:g.1000000A>G"}), "PAR1 has two copies in a man")

    def test_a_man_is_read_as_one_copy(self):
        read = {"state": "hom", "read": True, "genotype": "TT"}
        self.assertEqual("hemi", PG.as_hemizygous(read, "male")["state"])
        self.assertEqual("absent", PG.as_hemizygous({"state": "absent", "read": True}, "male")["state"])
        het = PG.as_hemizygous({"state": "het", "read": True}, "male")
        self.assertEqual(("unread", "het_on_male_x"), (het["state"], het["why"]))

    def test_a_woman_is_read_as_two_and_an_unknown_sex_is_not_read(self):
        read = {"state": "het", "read": True}
        self.assertEqual("het", PG.as_hemizygous(read, "female")["state"])
        self.assertEqual("sex_unknown_on_x", PG.as_hemizygous(read, None)["why"])

    def test_the_card_row_of_a_man(self):
        spec = {"positions": [_position("gonads", "rs5934505")]}
        with mock.patch.object(SP, "_genotype", lambda *a, **k: {"state": "hom", "read": True, "genotype": "T",
                                                                  "confidence": "called"}), \
                mock.patch.object(core, "profile_sex", lambda: "male"):
            out = SP._curated_rows("gonads", spec, [], {"status": "ok", "input_profile": "whole_genome"}, {})
        (row,) = out["rows"]
        self.assertEqual("hemi", row["state"])
        self.assertTrue(row["hemizygous"])
        self.assertEqual({"base": "C", "hom": "T"}, row["ladder"])
        self.assertIn("testosterone", row["text"].lower() + json.dumps(row["text"]))


class TestARefusedLadder(unittest.TestCase):

    def test_no_ladder_is_drawn(self):
        p = _position("gonads", "rs1691053")
        self.assertEqual("refused", p["ladder"])
        self.assertIsNone(panel_gate.ladder(p))
        self.assertIsNone(panel_gate.refusal(p, [], "", p["source"]))


class TestCarrierClasses(unittest.TestCase):

    BOOK = _raw("system_gene_panels.json")["systems"]["amino_acids"]["carrier_classes"]

    def row(self, gene, **kw):
        return {"gene": gene, "carrier": kw.get("carrier", False), "findings": kw.get("findings", 0)}

    def test_silent_and_possible_effect(self):
        with mock.patch("scholion.engine.panel_form._t", lambda k, **kw: k):
            r = self.row("PAH", carrier=True)
            panel_form.carrier_class(r, self.BOOK, "male", [])
            self.assertEqual("silent", r["carrier_class"])
            r = self.row("SLC7A9", carrier=True)
            panel_form.carrier_class(r, self.BOOK, "female", [])
            self.assertEqual("possible_effect", r["carrier_class"])

    def test_otc_follows_the_sex_and_the_class(self):
        hit = {"clnsig": "Likely_pathogenic", "chrom": "X", "pos": 38400000, "ref": "C", "alt": "T"}
        man = self.row("OTC", findings=1)
        panel_form.carrier_class(man, self.BOOK, "male", [hit])
        self.assertIn("X:38400000 C>T", man["carrier_class_text"])
        self.assertNotIn("{variant}", man["carrier_class_text"])
        woman = self.row("OTC", findings=1)
        panel_form.carrier_class(woman, self.BOOK, "female", [dict(hit, clnsig="Pathogenic")])
        self.assertNotIn("{class_word}", woman["carrier_class_text"])
        self.assertNotEqual(man["carrier_class_text"], woman["carrier_class_text"])
        unknown = self.row("OTC", findings=1)
        panel_form.carrier_class(unknown, self.BOOK, None, [hit])
        self.assertTrue(unknown["carrier_class_text"])


class TestTwoVariantsInATwoCopyGene(unittest.TestCase):

    def test_they_are_a_result_to_phase(self):
        row = {"gene": "PAH", "finding_grade": True, "recessive_only": True, "coverage": {}}
        hits = [{"chrom": "12", "pos": 1, "alt": "A", "zygosity": "het"},
                {"chrom": "12", "pos": 2, "alt": "T", "zygosity": "het"}]
        with mock.patch.object(panel_form, "gene_row", lambda g, r, s: r), \
                mock.patch.object(panel_form, "bases_read", lambda g, c: (True, None)), \
                mock.patch.object(panel_form, "read_state", lambda a, b: "read"):
            out = SP._finish_base_row(dict(row), {"status": "ok"}, {"status": "ok", "by_gene": {"PAH": hits}})
        self.assertFalse(out["carrier"])
        self.assertEqual(1, out["findings"])
        self.assertTrue(out["two_variants_text"])

    def test_one_variant_is_still_carriership(self):
        row = {"gene": "PAH", "finding_grade": True, "recessive_only": True, "coverage": {}}
        with mock.patch.object(panel_form, "gene_row", lambda g, r, s: r), \
                mock.patch.object(panel_form, "bases_read", lambda g, c: (True, None)), \
                mock.patch.object(panel_form, "read_state", lambda a, b: "read"):
            out = SP._finish_base_row(dict(row), {"status": "ok"},
                                      {"status": "ok", "by_gene": {"PAH": [{"chrom": "12", "pos": 1, "alt": "A"}]}})
        self.assertTrue(out["carrier"])
        self.assertNotIn("two_variants_text", out)


class TestTestsOfferedUnderHerCondition(unittest.TestCase):

    RULES = {r["id"]: r for r in _raw("test_rules.json")["rules"]}
    PANEL = {"aa_glycine": 1.0}

    def fires(self, rid, flags, measured):
        with mock.patch.object(LB, "_flags_now", lambda: flags), \
                mock.patch.object(LB, "_latest_value", lambda k: measured.get(k)):
            return LB._eval_condition(self.RULES[rid]["when"])

    def test_elastase(self):
        self.assertFalse(self.fires("amino_fecal_elastase", {}, self.PANEL))
        self.assertTrue(self.fires("amino_fecal_elastase", {"albumin": "low"}, self.PANEL))
        self.assertFalse(self.fires("amino_fecal_elastase", {"vitamin_d": "low"}, self.PANEL),
                         "a low vitamin D alone is too common to select anyone")
        self.assertTrue(self.fires("amino_fecal_elastase", {"vitamin_d": "low", "aa_lysine": "low"}, self.PANEL))

    def test_methionine_load(self):
        self.assertTrue(self.fires("amino_methionine_load", {"homocysteine": "high"}, self.PANEL))
        self.assertFalse(self.fires("amino_methionine_load", {"homocysteine": "high", "folate": "low"}, self.PANEL),
                         "a low folate explains the homocysteine: the data do not disagree")
        self.assertFalse(self.fires("amino_methionine_load", {}, self.PANEL))

    def test_dimethylarginines(self):
        self.assertTrue(self.fires("amino_dimethylarginines", {"lpa": "high"}, self.PANEL))
        self.assertTrue(self.fires("amino_dimethylarginines", {"aa_arginine": "low"}, self.PANEL))
        self.assertFalse(self.fires("amino_dimethylarginines", {}, self.PANEL))


class TestTrpLnaa(unittest.TestCase):

    def test_her_denominator(self):
        spec = provenance.DERIVED["aa_ratio_trp_lnaa"]
        v = {"aa_tryptophan": 60, "aa_leucine": 120, "aa_isoleucine": 60, "valine": 220,
             "aa_phenylalanine": 55, "aa_tyrosine": 65}
        self.assertAlmostEqual(60 / 520, spec["fn"](v))
        self.assertIn("aa_ratio_trp_lnaa", [d for d in _raw("radar_domains.json")["domains"]
                                            if d["key"] == "amino_acids"][0]["derived"])


class TestTheNewCorrectionRules(unittest.TestCase):

    def test_each_passes_the_gate(self):
        known = core.lab_markers().get("markers") or {}
        rules = {r["key"]: r for r in _raw("correction_routes.json")["rules"]}
        for key in ("pah_carrier_phenylalanine", "ass1_asl_carrier_citrulline", "gatm_carrier_creatine",
                    "hyperoxaluria_carrier_collagen"):
            with self.subTest(rule=key):
                self.assertIsNone(routes.route_refusal(rules[key], known))
        self.assertEqual("level_below_b", routes.route_refusal(rules["slc6a19_carrier_niacinamide"], known),
                         "a carrier statement resting on a gene paper prints as «adds nothing» with its reason")


class TestTheListCarriesTheCorrectedGenes(unittest.TestCase):

    def test_th_and_mttp(self):
        rows = {r["rsid"]: r for r in list(_raw("panel_intake.json")["lists"].values())[0]["positions"]}
        self.assertEqual(("TH", "in_catalogue"), (rows["rs6356"]["gene"], rows["rs6356"]["disposition"]))
        self.assertEqual(("MTTP", "refused"), (rows["rs3816873"]["gene"], rows["rs3816873"]["disposition"]))
        self.assertEqual("TH", _raw("loci.json")["loci"]["rs6356"]["gene"])


if __name__ == "__main__":
    unittest.main()
