"""«Heart and vessels» is a system of the radar, with a home for what had none.

Added 13.09.2026 by the owner's decision (task 179). The strongest
pharmacogenetic pairs — warfarin with VKORC1/CYP2C9/CYP4F2, clopidogrel with
CYP2C19, the beta-blockers, the anticoagulants and antiplatelets — and the
cardiovascular polygenic scores had no system to stand on, because the radar
measured no panel a cardiologist orders. Now it does: the five markers a
laboratory issues beside, not inside, the lipid panel. The classes named for
the pressure, the rhythm and the clot are placed on it, the cardiovascular
OUTCOMES move off the lipid card (which keeps the lipid MEASUREMENTS), and the
genetic half is composed from the base like every other system's. Lipids stay
a separate system; the wearable's pulse stays in fitness, because a domain has
one source.
"""
from __future__ import annotations

import json
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru

MARKERS = ["lpa", "apob", "apoa1", "fibrinogen", "d_dimer"]
CLASSES = ("ace_inhibitor", "arb", "beta_blocker", "ccb", "thiazide", "loop_diuretic",
           "anticoagulant_vka", "doac", "antiplatelet_p2y12", "antiarrhythmic")
TRAITS = ("coronary artery disease", "myocardial infarction", "peripheral arterial disease",
          "abdominal aortic aneurysm", "atrial fibrillation", "heart failure", "hypertension",
          "systolic blood pressure", "ischemic stroke", "venous thromboembolism")


def _knowledge(name: str):
    return json.loads(core.knowledge_path(name).read_text(encoding="utf-8"))


class TestTheDomain(unittest.TestCase):

    def test_cardio_is_a_laboratory_domain_with_its_five_markers_after_lipids(self):
        doms = SP.domains()
        keys = [d["key"] for d in doms]
        self.assertIn("cardio", keys)
        self.assertEqual(keys.index("cardio"), keys.index("lipids") + 1,
                         "the segment stands beside lipids, the panel it is issued next to")
        (c,) = [d for d in doms if d["key"] == "cardio"]
        self.assertEqual("labs", c["source"])
        self.assertIs(True, c["genetic_half"])
        self.assertEqual(MARKERS, c["markers"])

    def test_every_marker_exists_and_belongs_to_this_system_only(self):
        book = _knowledge("lab_markers.json")["markers"]
        owner = SP.marker_systems()
        for m in MARKERS:
            with self.subTest(marker=m):
                self.assertIn(m, book, f"{m} is not a marker of lab_markers.json")
                self.assertEqual("cardio", owner[m], "a marker belongs to one system")
                self.assertTrue(book[m]["labels"].get("en", {}).get("display"),
                                f"{m} has no English display name")
        # The panel does not reach into lipids: the lipid panel keeps its four.
        for m in ("cholesterol_total", "ldl", "hdl", "triglycerides"):
            self.assertEqual("lipids", owner[m])

    def test_the_domain_and_its_place_can_be_named_in_both_languages(self):
        for cat in (en.MESSAGES, ru.MESSAGES):
            self.assertTrue(cat["radar.domain.cardio"].strip())
            self.assertTrue(cat["web.body.place.heart"].strip())
        self.assertEqual("Heart and vessels", en.MESSAGES["radar.domain.cardio"])
        self.assertNotEqual(en.MESSAGES["radar.domain.cardio"], ru.MESSAGES["radar.domain.cardio"],
                            "the Russian catalogue carries the English phrase")
        self.assertIn("cardio", en.MESSAGES["tool.sch_system.param.key"])
        self.assertIn("cardio", ru.MESSAGES["tool.sch_system.param.key"])

    def test_the_segment_is_drawn_at_the_heart(self):
        body = _knowledge("body_map.json")
        self.assertEqual("heart", body["places"]["cardio"]["place"])
        self.assertIn("heart", body["vocabulary"])
        self.assertTrue(body["places"]["cardio"]["basis"].strip(),
                        "an exception to the producing-organ rule owes a reason")


class TestWhatStandsOnIt(unittest.TestCase):

    def test_the_classes_named_for_pressure_rhythm_and_clot_act_on_it(self):
        cmap = SP.class_systems()
        self.assertEqual(0, cmap["refused"], "a row names a system the radar does not hold")
        for cls in CLASSES:
            with self.subTest(cls=cls):
                self.assertEqual(["cardio"], cmap["classes"].get(cls))
        meta = _knowledge("drug_class_systems.json")["_meta"]
        for cls in CLASSES:
            self.assertNotIn(cls, meta["why_partial"], f"{cls} is placed and explained away at once")
        # The classes whose system is an indication, not a name, are still out.
        for cls in ("macrolide", "ppi", "nsaid", "thiopurine"):
            self.assertNotIn(cls, cmap["classes"])
            self.assertIn(cls, meta["why_partial"])

    def test_the_cardiovascular_outcomes_stand_on_cardio_and_not_on_lipids(self):
        m = SP.prs_system_map()
        self.assertEqual(0, m["refused"])
        cardio = m["systems"]["cardio"]["traits"]
        lipids = m["systems"]["lipids"]["traits"]
        for t in TRAITS:
            with self.subTest(trait=t):
                self.assertIn(t, cardio)
                self.assertNotIn(t, lipids)
        # The lipid MEASUREMENTS stay where their panel is.
        for t in ("LDL cholesterol", "HDL cholesterol", "total cholesterol",
                  "triglyceride measurement", "lipoprotein A"):
            self.assertIn(t, lipids)
            self.assertNotIn(t, cardio)
        partial = _knowledge("prs_system_map.json")["_meta"]["why_partial"]
        for t in TRAITS:
            self.assertNotIn(t, partial, f"{t} is placed and explained away at once")

    def test_the_genetic_half_is_composed_from_the_base_and_the_lung_vessels_stay_out(self):
        base = _knowledge("gencc_gene_disease.json")["systems"]
        self.assertIn("cardio", base)
        genes = base["cardio"]["genes"]
        # One gene from each disease group the filter names.
        for g in ("MYBPC3", "KCNH2", "SCN5A", "PKP2", "FBN1", "F5", "PROC", "NOTCH3", "MEF2A"):
            with self.subTest(gene=g):
                self.assertIn(g, genes)
        # Pulmonary arterial hypertension is a disease of the lung's vessels and
        # was vetoed by name; the veto is what keeps BMPR2 off the card.
        self.assertNotIn("BMPR2", genes)
        self.assertNotIn("LIMS2", genes, "a limb-girdle dystrophy row reached through a submitter's title")
        r = SP.system("cardio")
        self.assertEqual("composed", r["genetics"]["status"])
        self.assertEqual(len(genes), r["genetics"]["base"]["genes"])
        self.assertIn("cardio", SP.genes_index().get("MYBPC3", []))


if __name__ == "__main__":
    unittest.main()
