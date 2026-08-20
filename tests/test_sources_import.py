"""The import mechanism for external reference sources.

A catalogue that mirrors a source which moves upstream, and has no import path,
drifts silently: it keeps answering while the answer stops matching what it
claims to be. That is the shape of the defect the colleagues' audit found in the
hand-copied CPIC table. These tests hold the mechanism that replaces it.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest

import support  # noqa: F401
from scholion import core, sources


def _fake_cpic(url):
    if "/allele?" in url and "CYP2C9" in url:
        return [{"name": "*2", "activityvalue": "0.0",
                 "clinicalfunctionalstatus": "No function"},
                {"name": "*3", "activityvalue": "0.0",
                 "clinicalfunctionalstatus": "No function"}]
    if "/diplotype?" in url and "CYP2C9" in url:
        return [{"generesult": "Normal Metabolizer", "totalactivityscore": "2.0"},
                {"generesult": "Intermediate Metabolizer", "totalactivityscore": "1.0"},
                {"generesult": "Poor Metabolizer", "totalactivityscore": "0.5"}]
    return []


class TestEveryMirroredSourceHasAPath(unittest.TestCase):
    """The gate: a knowledge file that mirrors an upstream must be in the
    register, with either an importer or a written reason it cannot have one."""

    def test_every_source_declares_licence_homepage_and_cadence(self):
        for s in sources.state():
            with self.subTest(source=s["id"]):
                self.assertTrue(s["license"], "a source with no licence recorded")
                self.assertTrue(s["homepage"], "a source with no address recorded")
                self.assertTrue(s["cadence"], "a source that does not say how it changes")

    def test_a_source_is_either_automatic_or_says_why_not(self):
        for s in sources.state():
            with self.subTest(source=s["id"]):
                self.assertTrue(s["auto"] or s["why_manual"],
                                "neither an importer nor a recorded reason")

    def test_the_registry_covers_the_catalogues_that_mirror_an_upstream(self):
        """Named explicitly: if one of these stops being registered, the mirror
        has lost its import path and this fails."""
        registered = {f["file"] for s in sources.state() for f in s["files"]}
        for name in ("cpic_drug_gene.json", "acmg_sf.json", "lab_markers.json",
                     "prs_models.json", "longevitymap.json"):
            self.assertIn(name, registered, f"{name} mirrors an upstream and is unregistered")

    def test_live_sources_store_nothing(self):
        for s in sources.state():
            if s["kind"] == "live":
                self.assertEqual(s["files"], [],
                                 "a live lookup must not claim to feed a stored file")


class TestTheCpicImportDetectsDrift(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.environ["SCHOLION_REPO_DIR"] = self.d
        core.reset_cache()

    def tearDown(self):
        os.environ.pop("SCHOLION_REPO_DIR", None)
        core.reset_cache()

    def test_a_changed_upstream_label_is_reported_and_applied(self):
        r = sources.refresh("cpic", fetch=_fake_cpic)
        drift = [c for c in r["changes"] if c.get("field") == "function"]
        self.assertTrue(drift, "the importer did not notice a changed function label")
        self.assertEqual(drift[0]["was"], "decreased")
        self.assertEqual(drift[0]["now"], "none")

    def test_the_refresh_lands_beside_the_profile_not_in_the_package(self):
        sources.refresh("cpic", fetch=_fake_cpic)
        local = pathlib.Path(self.d) / "knowledge" / "cpic_drug_gene.json"
        self.assertTrue(local.is_file(), "the refresh did not write a local copy")
        self.assertTrue(core.knowledge_is_local("cpic_drug_gene.json"),
                        "the local copy does not take precedence")
        pkg = pathlib.Path(core.__file__).resolve().parent / "knowledge" / "cpic_drug_gene.json"
        self.assertNotIn("imported", json.loads(pkg.read_text(encoding="utf-8"))["_meta"],
                         "the import wrote into the package instead of the data directory")

    def test_provenance_is_stamped(self):
        sources.refresh("cpic", fetch=_fake_cpic)
        meta = json.loads((pathlib.Path(self.d) / "knowledge" / "cpic_drug_gene.json")
                          .read_text(encoding="utf-8"))["_meta"]["imported"]
        for k in ("source", "fetched", "endpoint", "license"):
            self.assertIn(k, meta)

    def test_band_labels_survive_an_import(self):
        """CPIC publishes boundaries, not our wording: an import that dropped the
        labels would leave the phenotype printed with no name."""
        sources.refresh("cpic", fetch=_fake_cpic)
        kb = json.loads((pathlib.Path(self.d) / "knowledge" / "cpic_drug_gene.json")
                        .read_text(encoding="utf-8"))
        for b in kb["genes"]["CYP2C9"]["activity_bands"]:
            self.assertTrue(b.get("label"), "a band lost its label during import")

    def test_a_manual_source_is_skipped_with_its_reason(self):
        r = sources.refresh("loinc", fetch=_fake_cpic)
        self.assertTrue(r["skipped"])
        self.assertTrue(r["reason"])


class TestOfflineIsHonoured(unittest.TestCase):
    def test_refresh_refuses_to_reach_the_network_when_offline(self):
        old = os.environ.get("SCHOLION_OFFLINE")
        os.environ["SCHOLION_OFFLINE"] = "1"
        try:
            with self.assertRaises(sources.SourceUnavailable):
                sources.refresh("cpic")      # the real fetcher, which must refuse
        finally:
            if old is None:
                os.environ.pop("SCHOLION_OFFLINE", None)
            else:
                os.environ["SCHOLION_OFFLINE"] = old


if __name__ == "__main__":
    unittest.main()


class TestQuotedProseIsRefreshed(unittest.TestCase):
    """Finding 57: the recommendation wording is CPIC's, quoted. A quote that is
    never re-checked becomes a misquote the day the guideline is revised."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.environ["SCHOLION_REPO_DIR"] = self.d
        core.reset_cache()

    def tearDown(self):
        os.environ.pop("SCHOLION_REPO_DIR", None)
        core.reset_cache()

    @staticmethod
    def _fetch(url):
        if "/recommendation?" in url and "clopidogrel" in url:
            return [{"classification": "Strong",
                     "drugrecommendation": "REVISED: avoid clopidogrel entirely.",
                     "implications": {"CYP2C19": "revised implication"},
                     "phenotypes": {"CYP2C19": "Poor Metabolizer"},
                     "drug": {"name": "clopidogrel"}}]
        return []

    def test_a_revised_guideline_sentence_is_reported_and_applied(self):
        r = sources.refresh("cpic", fetch=self._fetch)
        revised = [c for c in r["changes"]
                   if c.get("field") == "recommendation" and c.get("drug") == "clopidogrel"]
        self.assertTrue(revised, "a changed CPIC sentence was not noticed")
        self.assertEqual(revised[0]["now"], "REVISED: avoid clopidogrel entirely.")
        kb = json.loads((pathlib.Path(self.d) / "knowledge" / "cpic_drug_gene.json")
                        .read_text(encoding="utf-8"))
        clop = next(x for x in kb["drugs"] if "clopidogrel" in x["names"])
        self.assertEqual(clop["guidance"]["PM"]["cpic"]["recommendation"],
                         "REVISED: avoid clopidogrel entirely.")

    def test_our_own_patient_facing_note_is_never_overwritten_by_the_import(self):
        """The two layers must stay separate: an import that rewrote our plain
        line with the guideline's clinician-facing English would silently drop
        the Russian and the patient framing."""
        before = json.loads(core.knowledge_path("cpic_drug_gene.json")
                            .read_text(encoding="utf-8"))
        note_before = next(x for x in before["drugs"] if "clopidogrel" in x["names"]
                           )["guidance"]["PM"]["note"]
        sources.refresh("cpic", fetch=self._fetch)
        kb = json.loads((pathlib.Path(self.d) / "knowledge" / "cpic_drug_gene.json")
                        .read_text(encoding="utf-8"))
        note_after = next(x for x in kb["drugs"] if "clopidogrel" in x["names"]
                          )["guidance"]["PM"]["note"]
        self.assertEqual(note_before, note_after)

    def test_a_pair_without_a_quote_does_not_get_one_unattended(self):
        """Attaching a first quote is a judgement about which row applies; the
        refresh keeps quotes true, it does not make new ones."""
        sources.refresh("cpic", fetch=self._fetch)
        kb = json.loads((pathlib.Path(self.d) / "knowledge" / "cpic_drug_gene.json")
                        .read_text(encoding="utf-8"))
        warf = next(x for x in kb["drugs"] if "warfarin" in x["names"])
        for g in warf["guidance"].values():
            if isinstance(g, dict):
                self.assertIsNone(g.get("cpic"))
