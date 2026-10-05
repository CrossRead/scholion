"""What the profile already records reaches every screen that needs it.

The interface review of 25.09.2026 measured three gaps on the demo, all of them
data a screen could not show because an engine never read it:

* F5, CYP2C19, MTHFR and APOE are written in the profile, and the radar printed
  them «not read» — the system panels read positions only out of a VCF;
* four of seven prescriptions — oral iron, vitamin B12, the combined oral
  contraceptive, vitamin C — were recognised by nothing, so no interaction,
  monitoring or genotype question was ever asked of them;
* factor V Leiden under a combined oral contraceptive — the one combination on
  the demo a clinician must not miss — lived only as a sentence in the
  profile's own notes, and no screen printed it.

Each is held here on the demo itself, generated into a throw-away folder.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import core, demo


class _Demo(unittest.TestCase):

    def setUp(self):
        root = Path(tempfile.mkdtemp(prefix="profile_reads_")).resolve()
        self.addCleanup(shutil.rmtree, root, True)
        self.prof = root / "profile"
        self.prof.mkdir()
        self.files = demo.build_all()
        self.write(self.files)
        self.addCleanup(support.pin_profile(self.prof))
        self.addCleanup(support.pin_cache(root / "cache"))
        old = os.environ.get("SCHOLION_LANG")
        os.environ["SCHOLION_LANG"] = "en"
        self.addCleanup(lambda: os.environ.update({"SCHOLION_LANG": old}) if old is not None
                        else os.environ.pop("SCHOLION_LANG", None))

    def write(self, files):
        for name, data in files.items():
            path = self.prof / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class TestTheProfileGenotypeIsRead(_Demo):

    def rows(self, key):
        from scholion.engine import system_panels
        gen = system_panels.system(key, "clinician").get("genetics") or {}
        return {r.get("rsid"): r for r in gen.get("rows") or [] if r.get("unit") == "position"}

    def test_the_four_the_review_named_are_read(self):
        for key, rsid, state in (("cardio", "rs6025", "het"), ("cardio", "rs12248560", "hom"),
                                 ("inflammation", "rs1801133", "hom"), ("lipids", "rs429358", "het")):
            with self.subTest(rsid=rsid):
                row = self.rows(key)[rsid]
                self.assertIs(True, row.get("read"), f"{rsid} is in the profile and printed unread")
                self.assertEqual(state, row.get("state"))
                self.assertEqual("profile", (row.get("genotype") or {}).get("confidence"),
                                 "a reading must say where it came from")

    def test_a_gene_the_profile_records_is_not_a_gap(self):
        """The header counted APOE and CYP2D6 as «not read from the genome»
        while the profile held the APOE pair and a CYP2D6 diplotype."""
        gaps = core.genome_gaps()
        self.assertNotIn("APOE", gaps)
        self.assertNotIn("CYP2D6", gaps)

    def test_a_minus_strand_record_is_complemented_once(self):
        """F5 is written G/A in the gene's letters; the catalogue's pair is C/T."""
        g = self.rows("cardio")["rs6025"].get("genotype") or {}
        self.assertEqual("G/A", g.get("genotype"))
        self.assertEqual("-", g.get("strand_of_record"))

    def test_a_palindromic_position_is_never_complemented(self):
        from scholion.engine import panel_genotype
        got = panel_genotype._from_profile({"genotype": "C/C", "source": "x"}, "A", ("A", "T"))
        self.assertIs(False, got["read"], "an A/T position read as its complement")

    def test_a_record_the_position_cannot_hold_stays_unread(self):
        from scholion.engine import panel_genotype
        got = panel_genotype._from_profile({"genotype": "A/A", "source": "x"}, "T", ("C", "G"))
        self.assertEqual("unread", got["state"])


class TestEveryPrescriptionIsInTheCheck(_Demo):

    def test_seven_of_seven_are_recognised(self):
        meds = self.files["medications.json"]["medications"]
        for m in meds:
            with self.subTest(drug=m["name"]):
                self.assertTrue(core.classify_drug(m["name"]), f"{m['name']} is recognised by nothing")

    def test_the_levothyroxine_check_sees_the_whole_regimen(self):
        from scholion import engine
        r = engine.check_new_prescription("Levothyroxine")
        pairs = {(i["a"], i["b"]) for i in r["interactions"].get("interactions", [])}
        self.assertIn(("thyroid_hormone", "iron_oral"), pairs)
        self.assertIn(("thyroid_hormone", "combined_oral_contraceptive"), pairs)
        partial = [u for u in r["unresolved"] if u.get("what") == "interactions"]
        self.assertEqual([], partial, "part of the regimen still falls outside the check")

    def test_every_new_pair_names_its_source(self):
        data = core._read_knowledge("drug_interactions.json")
        for i in data["interactions"]:
            if {"iron_oral", "vitamin_b12", "combined_oral_contraceptive", "vitamin_c"} & {i["a"], i["b"]}:
                with self.subTest(pair=(i["a"], i["b"])):
                    self.assertRegex(i.get("source") or "", r"PMID \d+|doi:10\.")


class TestFactorVLeidenUnderThePillReachesEveryFace(_Demo):

    def test_the_prescription_check_puts_it_first(self):
        from scholion import engine, format as fmt
        r = engine.check_new_prescription("Combined oral contraceptive")
        self.assertEqual("high", r["overall"])
        flag = next(f for f in r["safety_flags"] if f.get("origin") == "genotype")
        self.assertEqual(("F5", "rs6025", "het"), (flag["gene"], flag["rsid"], flag["state"]))
        self.assertRegex(flag["source"], r"PMID \d+")
        head = "\n".join(fmt.prescription_check(r).splitlines()[:7])
        self.assertIn("F5 rs6025", head, "the flag is not the first thing the answer says")

    def test_the_regimen_says_it_on_the_overview_the_treatment_and_the_second_opinion(self):
        from scholion import engine, format as fmt
        for name, data, render in (("overview", engine.overview(), fmt.overview_report),
                                   ("medications", engine.medications_view(), fmt.medications_report),
                                   ("second_opinion", engine.second_opinion(), fmt.second_opinion_report)):
            with self.subTest(face=name):
                found = data.get("regimen_cautions", data.get("cautions")) or []
                self.assertEqual(["F5"], [c["gene"] for c in found])
                head = "\n".join(render(data).splitlines()[:3])
                self.assertIn("🔴", head, "the caution is not printed first")

    def test_the_page_prints_it_on_the_three_views(self):
        page = (support.SRC / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        for needle in ("${cautionsHtml(o.regimen_cautions)}", "${cautionsHtml(d.cautions)}",
                       "${cautionsHtml(meds&&meds.cautions)}"):
            self.assertIn(needle, page)

    def test_a_person_without_the_allele_is_not_warned(self):
        files = copy.deepcopy(self.files)
        for g in files["pharmacogenomics.json"]["genotypes"]:
            if g["rsid"] == "rs6025":
                g["genotype"] = "G/G"
        self.write(files)
        from scholion import engine
        self.assertEqual([], engine.regimen_cautions())

    def test_a_caution_without_a_reading_is_not_raised(self):
        files = copy.deepcopy(self.files)
        files["pharmacogenomics.json"]["genotypes"] = [
            g for g in files["pharmacogenomics.json"]["genotypes"] if g["rsid"] != "rs6025"]
        self.write(files)
        from scholion import engine
        self.assertEqual([], engine.regimen_cautions(), "a caution raised on a guess")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
