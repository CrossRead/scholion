"""A primary source does not license a substituted drug, population or outcome."""
from __future__ import annotations

import copy
import json
import unittest
from unittest import mock

from scholion import core, engine, format as fmt, i18n
from scholion.engine import pgx
from scholion.interaction_basis import _guard
from tests.test_a_genotype_in_the_profile_is_never_shown_as_unread import _Demo


class TestStudyContext(_Demo):
    def setUp(self):
        super().setUp()
        self.addCleanup(i18n.set_lang, i18n.lang())

    def meds(self, names):
        self.files["medications.json"]["medications"] = [{"name": n, "status": "active"} for n in names]
        self.write(self.files)
        core.reset_cache()

    def test_ferrous_sulfate_warning_is_conditional_and_kept_in_both_directions(self):
        for old, new in (("levothyroxine", "ferrous sulfate"), ("ferrous sulphate", "levothyroxine")):
            self.meds([old])
            for language in ("en", "ru"):
                i18n.set_lang(language)
                row = pgx.check_interactions(new)["interactions"][0]
                self.assertEqual("moderate", row["severity"])
                self.assertFalse(row["interpretation_withheld"])
                self.assertEqual("complete", row["conclusion_basis"]["status"])
                self.assertIsNone(row["manage"])
                text = fmt.prescription_check(engine.check_new_prescription(new))
                self.assertIn(row["effect"], text)
                self.assertIn(row["mechanism"], text)
                self.assertIn("1443969", text)
                self.assertNotEqual("low", engine.check_new_prescription(new)["overall"])

    def test_unstudied_iron_form_and_conflicting_names_keep_the_observed_pair(self):
        for old, new in (("levothyroxine", "ferrous bisglycinate"), ("ferrous fumarate", "levothyroxine"),
                         ("levothyroxine", "ferrous sulfate or ferrous fumarate")):
            self.meds([old])
            row = pgx.check_interactions(new)["interactions"][0]
            self.assertEqual("unknown", row["severity"])
            self.assertIn("drug_scope", row["conclusion_basis"]["missing"])
            self.assertEqual([old], row["with_meds"])

    def test_menopausal_estrogen_study_is_not_a_contraceptive_algorithm(self):
        for old, new in (("levothyroxine", "ethinylestradiol"), ("ethinylestradiol", "levothyroxine")):
            self.meds([old])
            for language in ("en", "ru"):
                i18n.set_lang(language)
                row = pgx.check_interactions(new)["interactions"][0]
                self.assertEqual("unknown", row["severity"])
                self.assertIn("clinical_scope", row["conclusion_basis"]["missing"])
                self.assertIn(i18n.t("interactions.scope.estrogen_study"), row["effect"])
                rx = engine.check_new_prescription(new)
                self.assertNotEqual("low", rx["overall"])
                self.assertIn(row["effect"], fmt.prescription_check(rx))
                self.assertIsNone(row["manage"])

    def test_b12_association_is_not_supplement_correction_or_a_low_pair_verdict(self):
        for old, new in (("omeprazole", "vitamin b12"), ("methylcobalamin", "omeprazole")):
            self.meds([old])
            for language in ("en", "ru"):
                i18n.set_lang(language)
                row = pgx.check_interactions(new)["interactions"][0]
                self.assertTrue(row["interpretation_withheld"])
                self.assertEqual("unknown", row["severity"])
                self.assertIn("clinical_scope", row["conclusion_basis"]["missing"])
                rx = engine.check_new_prescription(new)
                self.assertNotEqual("low", rx["overall"])
                self.assertIn(row["effect"], fmt.prescription_check(rx))
                self.assertIsNone(row["manage"])

    def test_a_newer_local_legacy_copy_does_not_restore_the_substituted_claim(self):
        rows = copy.deepcopy(core.drug_interactions()["interactions"])
        selected = [r for r in rows if {r["a"], r["b"]} in (
            {"thyroid_hormone", "iron_oral"}, {"thyroid_hormone", "combined_oral_contraceptive"}, {"ppi", "vitamin_b12"})]
        for row in selected:
            row.pop("study_context", None)
            row.pop("applicability", None)
            row["effect"] = {"en": "UNQUALIFIED_LOCAL_CLAIM", "ru": "UNQUALIFIED_LOCAL_CLAIM"}
            row["manage"] = {"en": "UNHELD_LOCAL_ALGORITHM", "ru": "UNHELD_LOCAL_ALGORITHM"}
        knowledge = core.profile_dir().parent / "knowledge"
        knowledge.mkdir(exist_ok=True)
        patch = mock.patch.object(core, "knowledge_dir_local", return_value=knowledge)
        patch.start()
        self.addCleanup(patch.stop)
        path = knowledge / "drug_interactions.json"
        path.write_text(json.dumps({"_meta": {"updated": "2099-01-01"}, "interactions": selected}), encoding="utf-8")
        before = path.read_bytes()
        for partner, new in (("levothyroxine", "ferrous sulfate"), ("levothyroxine", "ethinylestradiol"),
                             ("omeprazole", "vitamin b12")):
            self.meds([partner])
            for language in ("en", "ru"):
                i18n.set_lang(language)
                row = pgx.check_interactions(new)["interactions"][0]
                self.assertTrue(row["interpretation_withheld"])
                self.assertIn("clinical_scope", row["conclusion_basis"]["missing"])
                self.assertNotIn("UNQUALIFIED_LOCAL_CLAIM", fmt.prescription_check(engine.check_new_prescription(new)))
                self.assertIsNone(row["manage"])
                self.assertEqual(before, path.read_bytes())
        for row, citations in zip(selected, (("PMID:1443969", "DOI:10.7326/0003-4819-117-12-1010"),
                                              ("PMID:11396440", "DOI:10.1056/NEJM200106073442302"),
                                              ("PMID:24327038", "DOI:10.1001/jama.2013.280490"))):
            for source in citations:
                self.assertTrue(_guard({**row, "source": source}, True)["interpretation_withheld"])
        base = {"a": "A", "b": "B", "effect": "SYNTHETIC", "source": "Synthetic PMID:2", "mechanism": "SYNTHETIC"}
        for applicability in ({"status": "unheld"}, {"status": "unknown"}, [], {}, False):
            out = _guard({**base, "applicability": applicability}, True)
            self.assertTrue(out["interpretation_withheld"])
        self.assertFalse(_guard({**base, "applicability": {"status": "held"}}, True)["interpretation_withheld"])
        self.assertFalse(_guard({**base, "source": None}, True)["conclusion_basis"]["status"] == "complete")


if __name__ == "__main__":
    unittest.main()
