"""A stored result does not decide the language, and every token has a sentence.

`prs_results.json` and `longevity_findings.json` hold numbers computed once and
kept. They also hold names — and a name inside a stored file is a copy of the
catalogue made on the day of the run, in the language that run was speaking. The
catalogues carry both languages and are resolved on read; nobody asked them, so a
reader in English met Russian names among English rows for as long as the file
was old.

The rule: the catalogue decides what a thing is CALLED, the file decides what the
number IS, and a row the catalogue does not carry keeps every string it was
stored with — a percentile with no name is worse than a name in one language.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core
from scholion.engine import genomics

META = {"purpose": "SYNTHETIC — a test fixture", "synthetic": True}
#: A real term and a real rsID of each catalogue, with a name in the OTHER
#: language stored beside them — which is exactly the shape of a file written a
#: year ago by a run that was speaking Russian.
TERM = "coronary artery disease"
RSID = "rs2802292"                                  # FOXO3, the Willcox variant


def _profile():
    d = Path(tempfile.mkdtemp(prefix="lang_"))
    (d / "prs_results.json").write_text(json.dumps({"_meta": META, "traits": [
        {"term": TERM, "label": "Ишемическая болезнь сердца (ИБС)",
         "category": "Сердечно-сосудистые", "percentile": 91.0, "reliable": True,
         "match_rate": 0.97, "weight_mass_coverage": 0.95},
        {"term": "a term no catalogue carries", "label": "Своё название",
         "category": "Своя категория", "percentile": 40.0, "reliable": True,
         "match_rate": 0.97, "weight_mass_coverage": 0.95},
    ]}, ensure_ascii=False), encoding="utf-8")
    (d / "longevity_findings.json").write_text(json.dumps({"_meta": META,
        "apoe": {"epsilon": "ε2/ε3", "rs429358": "T/T", "rs7412": "C/T"},
        "known": [
            {"rsid": RSID, "gene": "FOXO3", "genotype": "G/T", "copies_favorable": 1,
             "label": "G — самый воспроизведённый вариант долголетия",
             "action": "инсулин/IGF-ось", "verdict": "neutral", "confidence": "high"},
            {"rsid": "rs00000000", "gene": "XXXX", "genotype": "A/A",
             "label": "Своё название", "verdict": "neutral"},
        ],
        "significant_by_gene": {}}, ensure_ascii=False), encoding="utf-8")
    return d


class _InEnglish(unittest.TestCase):

    def setUp(self):
        self.dir = _profile()
        self._env = {k: os.environ.get(k) for k in ("SCHOLION_PROFILE_DIR", "SCHOLION_LANG")}
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.dir)
        os.environ["SCHOLION_LANG"] = "en"
        core.reset_cache()

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        core.reset_cache()
        shutil.rmtree(self.dir, ignore_errors=True)


class TestTheCatalogueNamesThings(_InEnglish):

    def test_a_polygenic_trait_is_named_in_the_language_being_read(self):
        traits = {t["term"]: t for t in
                  (x for c in genomics.prs_findings()["categories"] for x in c["traits"])}
        got = traits[TERM]
        self.assertEqual(got["label"], "Coronary artery disease (CAD)")
        self.assertEqual(got["category"], "Cardiovascular")

    def test_a_trait_the_catalogue_does_not_carry_keeps_its_stored_name(self):
        """Dropping it would leave a percentile with no name, which is worse than
        a name in one language."""
        traits = [x for c in genomics.prs_findings()["categories"] for x in c["traits"]]
        kept = [t for t in traits if t["term"] == "a term no catalogue carries"]
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["label"], "Своё название")

    def test_a_longevity_marker_is_explained_in_the_language_being_read(self):
        known = {k["rsid"]: k for k in genomics.longevity_findings()["known"]}
        self.assertIn("most reproduced", known[RSID]["label"])
        self.assertNotIn("воспроизведённый", known[RSID]["label"])
        self.assertTrue(known[RSID].get("action"))
        self.assertNotIn("ось", known[RSID]["action"])

    def test_a_marker_the_catalogue_does_not_carry_keeps_what_it_had(self):
        known = {k["rsid"]: k for k in genomics.longevity_findings()["known"]}
        self.assertEqual(known["rs00000000"]["label"], "Своё название")

    def test_the_verdict_is_recomputed_from_the_catalogue_not_from_the_file(self):
        """One copy of the FOXO3 favourable allele is `plus_partial` in the
        catalogue. The file says `neutral`, which is what the catalogue said on
        the day of the build — and a stored verdict outliving its rule is the
        same defect as a stored name outliving its language."""
        known = {k["rsid"]: k for k in genomics.longevity_findings()["known"]}
        self.assertEqual(known[RSID]["verdict_token"], "plus_partial")


class TestAnUnknownTokenNeverBecomesAKey(_InEnglish):
    """A stored file may carry anything in `verdict` — the demo profile holds
    «🟢 favourable», a sentence somebody rendered once. Composing a message key
    out of it printed ⟦longevity.verdict.🟢 favourable⟧ at the reader, which is
    the failure mode this project spends most of its guards on: it fails in front
    of a person and nowhere else."""

    def test_a_verdict_the_catalogue_does_not_know_is_not_turned_into_a_key(self):
        raw = json.loads((self.dir / "longevity_findings.json").read_text(encoding="utf-8"))
        raw["known"][1]["verdict"] = "a sentence somebody rendered once"
        raw["known"][1]["confidence"] = "curated_by_hand"
        (self.dir / "longevity_findings.json").write_text(
            json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        core.reset_cache()
        k = {x["rsid"]: x for x in genomics.longevity_findings()["known"]}["rs00000000"]
        self.assertIsNone(k["verdict_token"], "an unknown token was passed off as one we know")
        self.assertNotIn("longevity.verdict", str(k["verdict_label"]))
        self.assertIsNone(k["confidence_label"], "an unknown level produced a phrase key")

    def test_a_verdict_the_catalogue_does_know_still_becomes_a_sentence(self):
        k = {x["rsid"]: x for x in genomics.longevity_findings()["known"]}[RSID]
        self.assertEqual(k["verdict_token"], "plus_partial")
        self.assertTrue(k["verdict_label"])
        self.assertNotIn("longevity.verdict", k["verdict_label"])


class TestTheApoeComponentsAreTheCardAndNotTwoFindings(_InEnglish):
    """The two positions the ε-status is computed from carry `see_apoe`, a token
    our own builder writes. Printed as a verdict it was the bare word; listed as
    findings the two of them repeated the card standing directly above. Both
    halves fixed: it is a sentence wherever it is printed, and the page files it
    under the card rather than beside it."""

    def test_it_is_a_sentence_and_not_the_word_itself(self):
        raw = json.loads((self.dir / "longevity_findings.json").read_text(encoding="utf-8"))
        raw["known"][1]["rsid"] = "rs429358"
        raw["known"][1]["verdict"] = "see_apoe"
        (self.dir / "longevity_findings.json").write_text(
            json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        core.reset_cache()
        k = {x["rsid"]: x for x in genomics.longevity_findings()["known"]}["rs429358"]
        self.assertEqual(k["verdict_token"], "see_apoe")
        self.assertNotEqual(k["verdict_label"], "see_apoe")
        self.assertIn("APOE", k["verdict_label"])

    def test_the_page_files_it_under_the_card(self):
        """Read off the page's own source: the list it builds must exclude the
        token, or the card is repeated twice under itself."""
        from pathlib import Path as _P
        from scholion import core as _c
        page = (_P(_c.__file__).resolve().parent / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("k.verdict_token!=='see_apoe'", page.replace(" ", ""))


class TestEveryTokenHasASentence(unittest.TestCase):
    """The verdict is a token, and the page composes `longevity.verdict.<token>`.
    A composed key is invisible to the static check, so this family needs an
    owner: a token with no phrase prints ⟦longevity.verdict.plus⟧ at a reader."""

    def test_every_verdict_the_catalogue_can_produce_is_written(self):
        from scholion.i18n import en, ru
        raw = json.loads(core.knowledge_path("longevity_directions.json")
                         .read_text(encoding="utf-8"))["directions"]
        tokens = sorted({v for d in raw.values()
                         for v in (d.get("verdict_by_copies") or {}).values()})
        self.assertGreaterEqual(len(tokens), 3, tokens)
        for lang, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            for tok in tokens:
                with self.subTest(lang=lang, token=tok):
                    self.assertIn(f"longevity.verdict.{tok}", cat)

    def test_every_confidence_the_catalogue_can_produce_is_written(self):
        from scholion.i18n import en, ru
        raw = json.loads(core.knowledge_path("longevity_directions.json")
                         .read_text(encoding="utf-8"))["directions"]
        levels = sorted({d.get("confidence") for d in raw.values() if d.get("confidence")})
        self.assertGreaterEqual(len(levels), 2, levels)
        for lang, cat in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            for lv in levels:
                with self.subTest(lang=lang, level=lv):
                    self.assertIn(f"web.longevity.confidence.{lv}", cat)


if __name__ == "__main__":
    unittest.main()
