"""A prescription reaches its genes through the system its class acts on, and a
system's card names the prescriptions acting on it and the target set on it.

Task 168, steps 4 and 7. Three things are held here:

  * the class → system map is small, gated against the domain file, and a
    prescription whose class it does not place is listed as UNMAPPED on the
    card rather than left out — a prescription silently absent from every
    system reads as one that acts on nothing;
  * the clinician's target (task 170) stands as layer 5 of the card, and a
    value the corridor calls normal while the target does not is a QUESTION
    with the origin `target`, asked once and never as an instruction;
  * the prescription entry no longer waits for a hand-written list: its genes
    are inherited from the genetic half of the system its class acts on, and
    the drug entry is the clinician's layer of exceptions — a sentence, a
    class, or a signed exclusion; an unsigned exclusion is refused and counted,
    and the `_proposed` draft is never read.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core, store
from scholion.engine import decision as D
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru


class _Pinned(unittest.TestCase):
    """A copy of the synthetic fixture, pinned for one test."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.profile = self.tmp / "profile"
        shutil.copytree(support.FIXTURE_PROFILE, self.profile)
        self._restore = support.pin_profile(self.profile)
        self._restore_cache = support.pin_cache(self.tmp / "cache")
        core.reset_cache()

    def tearDown(self):
        self._restore()
        self._restore_cache()
        core.reset_cache()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_meds(self, meds):
        p = self.profile / "medications.json"
        p.write_text(json.dumps({"_meta": {"purpose": "synthetic"}, "medications": meds},
                                ensure_ascii=False), encoding="utf-8")
        core.reset_cache()


class TestTheClassMapIsSmallAndGated(unittest.TestCase):

    def test_the_shipped_rows_are_facts_by_name_and_every_system_is_a_domain(self):
        cmap = SP.class_systems()
        self.assertEqual(0, cmap["refused"])
        known = {d["key"] for d in SP.domains()}
        classes = set(core.med_classes().get("classes") or {})
        for cls, keys in cmap["classes"].items():
            with self.subTest(cls=cls):
                self.assertIn(cls, classes, "a class the dictionary does not know")
                self.assertTrue(set(keys) <= known)
        self.assertEqual(["thyroid"], cmap["classes"]["thyroid_hormone"])
        self.assertEqual(["lipids"], cmap["classes"]["statin"])
        self.assertEqual(["glucose"], cmap["classes"]["biguanide"])

    def test_a_row_naming_no_domain_is_dropped_and_counted(self):
        book = {"classes": {"statin": {"systems": ["lipids", "no-such-system"]},
                            "ppi": {"systems": ["stomach"]}}}
        with mock.patch.object(core, "_read_knowledge",
                               lambda name: book if name == "drug_class_systems.json" else _real(name)):
            cmap = SP.class_systems()
        self.assertEqual(["lipids"], cmap["classes"]["statin"])
        self.assertNotIn("ppi", cmap["classes"])
        self.assertEqual(2, cmap["refused"])

    def test_the_left_out_classes_are_named_with_the_reason(self):
        meta = json.loads((core._KNOWLEDGE_DIR / "drug_class_systems.json")
                          .read_text(encoding="utf-8"))["_meta"]
        # `ace_inhibitor` stood in this list until 13.09.2026, when «Heart and
        # vessels» gave the antihypertensive classes a system (task 179); the
        # macrolides are the antibiotic that still has none.
        for cls in ("macrolide", "ppi", "nsaid", "iodine"):
            self.assertIn(cls, meta["why_partial"])
        for cls in ("ace_inhibitor", "anticoagulant_vka", "antiplatelet_p2y12", "antiarrhythmic"):
            self.assertNotIn(cls, meta["why_partial"],
                             f"{cls} is placed on cardio and must not be explained away as well")


_REAL_READ = core._read_knowledge


def _real(name):
    return _REAL_READ(name)


class TestLayerFourNamesThePrescriptionsActingOnASystem(_Pinned):

    def test_a_current_statin_stands_on_the_lipid_card_and_on_no_other(self):
        lip = SP.system("lipids")["medications"]
        self.assertEqual("ok", lip["status"])
        self.assertEqual(["statin"], lip["rows"][0]["via"])
        self.assertEqual("mapped", lip["rows"][0]["map_status"])
        thy = SP.system("thyroid")["medications"]
        self.assertEqual("empty", thy["status"])
        self.assertEqual("none_acts_here", thy["empty_why"])
        self.assertTrue(thy["empty_reason"])

    def test_a_prescription_whose_class_has_no_row_is_listed_as_unmapped(self):
        self.write_meds([{"name": "omeprazole", "dose": "20 mg"}])
        m = SP.system("liver")["medications"]
        self.assertEqual([], m["rows"])
        self.assertEqual([{"name": "omeprazole", "classes": ["ppi"], "map_status": "no_map"}],
                         m["unmapped"])

    def test_a_prescription_no_class_recognises_is_listed_as_unclassified(self):
        self.write_meds([{"name": "zzz-unknown-substance"}])
        m = SP.system("liver")["medications"]
        self.assertEqual([{"name": "zzz-unknown-substance", "map_status": "no_class"}],
                         m["unclassified"])

    def test_a_stopped_prescription_is_not_a_current_one(self):
        self.write_meds([{"name": "atorvastatin", "status": "stopped"}])
        m = SP.system("lipids")["medications"]
        self.assertEqual("empty", m["status"])
        self.assertEqual("no_current_prescriptions", m["empty_why"])

    def test_the_listing_places_every_current_prescription_once(self):
        # The fixture holds a statin and a vitamin D preparation, in that order.
        statin, vitamin_d = [m["name"] for m in core.active_medications()]
        rows = SP.systems()["prescriptions"]
        self.assertEqual({statin: ["lipids"], vitamin_d: ["micronutrients"]},
                         {r["name"]: r["systems"] for r in rows})


class TestLayerFiveIsTheCliniciansTarget(_Pinned):

    def _target(self, **kw):
        args = dict(low=4.0, high=5.0, unit="mmol/L", set_by="Dr. Fixture",
                    set_on="2026-09-12", subject="owner")
        args.update(kw)
        r = store.set_clinician_target("glucose", **args)
        self.assertTrue(r["ok"], r)
        core.reset_cache()

    def test_without_a_target_the_layer_names_the_reason(self):
        tg = SP.system("glucose")["target"]
        self.assertEqual(("empty", "no_target_set"), (tg["status"], tg["empty_why"]))
        self.assertEqual("no_lab_half", SP.system("fitness")["target"]["empty_why"])

    def test_a_value_in_the_corridor_outside_the_target_is_a_question(self):
        self._target()
        s = SP.system("glucose")
        row = s["target"]["rows"][0]
        self.assertEqual(("glucose", True, True, "above"),
                         (row["marker"], row["outside_target"], row["in_corridor"], row["side"]))
        self.assertEqual("Dr. Fixture", row["set_by"])
        qs = [q for q in s["questions"]["rows"] if q["origin"] == "target"]
        self.assertEqual(1, len(qs))
        self.assertIn("Dr. Fixture", qs[0]["text"])
        self.assertTrue(qs[0]["text"].rstrip().endswith("?"))
        asks = [q for q in s["next"]["ask"]["rows"] if q.get("origin") == "target"]
        self.assertEqual(1, len(asks), "the question reaches the «ask» basket once")

    def test_a_met_target_asks_nothing(self):
        self._target(high=6.0)
        s = SP.system("glucose")
        self.assertFalse(s["target"]["rows"][0]["outside_target"])
        self.assertEqual([], [q for q in s["questions"]["rows"] if q["origin"] == "target"])

    def test_the_target_does_not_move_the_score_or_the_flag(self):
        before = SP.system("glucose")["labs"]
        self._target()
        after = SP.system("glucose")["labs"]
        self.assertEqual(before["score"], after["score"])
        self.assertEqual(before["abnormal"], after["abnormal"])


THYROID = {"_meta": {"export_last_modified": "2026-09-06"},
           "systems": {"thyroid": {"source": "t", "genes": {
               "DIO2": {"submissions": [{"classification": "Strong", "moi_code": "AD"}]},
               "TPO": {"submissions": [{"classification": "Strong", "moi_code": "AR"}]},
               "TSHR": {"submissions": [{"classification": "Definitive", "moi_code": "AD"}]}}}}}
CLASS_MAP = {"classes": {"thyroid_hormone": {"systems": ["thyroid"]}}}


class TestAPrescriptionInheritsTheSystemsGenes(unittest.TestCase):

    def setUp(self):
        real = core._read_knowledge
        self._p = [mock.patch.object(SP, "_base", lambda: THYROID),
                   mock.patch.object(SP, "_curated", lambda: {"systems": {}}),
                   mock.patch.object(core, "_read_knowledge",
                                     lambda n: CLASS_MAP if n == "drug_class_systems.json" else real(n))]
        for p in self._p:
            p.start()

    def tearDown(self):
        for p in reversed(self._p):
            p.stop()

    def test_with_no_entry_the_genes_come_from_the_system_as_pending(self):
        with mock.patch.object(D, "_context", lambda: {"drugs": {}}):
            got = D.curated_genes("levothyroxine")
        self.assertTrue(got["asked"])
        self.assertEqual({"DIO2", "TPO", "TSHR"}, {r["gene"] for r in got["pending"]})
        self.assertEqual(3, got["inherited"])
        self.assertEqual([{"key": "thyroid", "status": "composed", "genes": 3}], got["systems"])
        self.assertIn("thyroid", got["pending"][0]["source"])
        self.assertIn("2026-09-06", got["pending"][0]["source"])

    def test_the_entry_is_a_layer_of_exceptions_over_the_inherited_list(self):
        book = {"drugs": {"levothyroxine": {"source": "a clinician", "genes": {
            "DIO2": {"kind": "asked_about", "text": {"en": "nothing follows", "ru": "x"},
                     "source": "PMID 1"},
            "TPO": {"exclude": True, "source": "not relevant to replacement"},
            "SLC16A10": {"kind": "mechanism"}}}}}
        with mock.patch.object(D, "_context", lambda: book):
            got = D.curated_genes("levothyroxine")
        self.assertEqual(["DIO2"], [r["gene"] for r in got["genes"]], "her sentence wins")
        self.assertEqual({"SLC16A10", "TSHR"}, {r["gene"] for r in got["pending"]},
                         "her own named gene and the inherited one both wait")
        self.assertEqual(["TPO"], got["excluded"])
        self.assertEqual(0, got["refused"])

    def test_an_exclusion_with_no_source_anywhere_is_refused_and_counted(self):
        book = {"drugs": {"levothyroxine": {"genes": {"TPO": {"exclude": True}}}}}
        with mock.patch.object(D, "_context", lambda: book):
            got = D.curated_genes("levothyroxine")
        self.assertEqual(1, got["refused"])
        self.assertIn("TPO", {r["gene"] for r in got["pending"]}, "struck by nobody: still listed")

    def test_a_class_with_no_row_in_the_map_is_answered_as_before(self):
        with mock.patch.object(D, "_context", lambda: {"drugs": {}}):
            got = D.curated_genes("omeprazole")
        self.assertFalse(got["asked"])
        self.assertEqual([], got["systems"])

    def test_a_system_whose_half_is_not_composed_is_named_and_hands_over_nothing(self):
        with mock.patch.object(SP, "_base", lambda: {"systems": {}}), \
                mock.patch.object(D, "_context", lambda: {"drugs": {}}):
            got = D.curated_genes("levothyroxine")
        self.assertFalse(got["asked"])
        self.assertEqual([{"key": "thyroid", "status": "not_composed", "genes": 0}], got["systems"])

    def test_the_proposed_draft_is_never_read(self):
        book = D._context()
        self.assertIn("_proposed", book)
        drafts = [k for k in book["_proposed"] if k != "note"]
        self.assertTrue(drafts, "the draft block is empty — nothing here is guarding anything")
        for name in drafts:
            self.assertNotIn(name, book.get("drugs") or {})
            self.assertFalse(D.curated_genes(name)["genes"], "a draft row reached an answer")
        self.assertIn("exceptions", (book["_meta"].get("purpose") or "").lower())

    def test_the_inherited_rows_reach_the_reading_verdict(self):
        with mock.patch.object(D, "_context", lambda: {"drugs": {}}), \
                mock.patch("scholion.genome.available", lambda: {"ready": False, "reason": "no_file"}):
            c = D.classify({"genes": [], "cpic": {"asked": True}}, "levothyroxine")
        self.assertEqual({"DIO2", "TPO", "TSHR"}, {r["gene"] for r in c["named"]})
        self.assertEqual("not_determined", c["panel_verdict"]["kind"])

    def test_every_new_key_is_in_both_catalogues(self):
        for k in ("decision.via_system", "decision.through_systems", "decision.system_reached",
                  "decision.system_not_composed", "decision.excluded_by_clinician",
                  "system.q.target", "system.why.no_current_prescriptions",
                  "system.why.none_acts_here", "system.why.no_target_set"):
            with self.subTest(key=k):
                self.assertIn(k, en.MESSAGES)
                self.assertIn(k, ru.MESSAGES)


if __name__ == "__main__":
    unittest.main()
