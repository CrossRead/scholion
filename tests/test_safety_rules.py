"""The safety rules for the conclusions — the very thing the project was written for.

This is not a check that "the code did not crash" but a check of the promises the
system makes to the user. Each of them has already been broken once in manual
mode, so here they are pinned down by machine:

  · no reference range on the form → the marker is shown WITHOUT an abnormality flag;
  · the biological age is computed ONLY from a complete panel of a single draw;
  · the PhenoAge formula contains no sex term (Levine 2018) — which means that
    changing the sex in the profile has no right to move the result;
  · the direction of the coefficients is not mixed up: inflammation ages you,
    albumin makes you younger;
  · a clinical conclusion is accompanied by the caveat "not a diagnosis".
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support
from scholion import i18n


class TestReferenceRanges(unittest.TestCase):

    def setUp(self):
        self.labs = support.run_json(["labs"])
        self.by_key = {m["key"]: m for m in self.labs["markers"]}

    def test_no_range_means_no_flag(self):
        m = self.by_key["ferritin_no_ref"]
        self.assertIsNone(m.get("ref_low"))
        self.assertIsNone(m.get("ref_high"))
        self.assertFalse(m["abnormal"],
                         "a marker with no printed range cannot be an «abnormality»: somebody "
                         "else's reference range invents findings out of thin air")
        # `norange`, not `ok`. Both keep the marker out of the abnormality count,
        # and only one of them is honest: «ok» is a verdict — it says the value sits
        # inside a corridor — and there is no corridor. The renderer prints a
        # neutral dot for it rather than the green tick that used to appear beside
        # the very first number a person enters by hand.
        self.assertEqual(m["flag"], "norange")
        self.assertNotEqual(m["flag"], "ok",
                            "a green flag on a value with nothing to compare it against is a "
                            "statement about a person made from the absence of data")

    def test_one_sided_ranges_are_computed_correctly(self):
        self.assertEqual(self.by_key["ldl"]["flag"], "high")    # only the upper bound
        self.assertEqual(self.by_key["hdl"]["flag"], "low")     # only the lower bound
        self.assertEqual(self.by_key["glucose"]["flag"], "ok")  # the value is inside the range

    def test_the_caveat_is_in_place(self):
        """The caveat is checked in EVERY language the build can print in.

        A literal here would pin the promise to one language, and the promise is
        made to whoever is reading — so the phrase is taken from the catalogue and
        every report is asked for in the language it belongs to.
        """
        for lang in i18n.available():
            caveat = i18n.CATALOGUES[lang]["disclaimer.general"]
            for cmd in (["labs"], ["second-opinion"], ["radar"], ["overview"]):
                with self.subTest(command=cmd[0], language=lang):
                    code, out, _ = support.run(cmd + ["--lang", lang])
                    self.assertEqual(code, 0)
                    self.assertIn(caveat, out,
                                  f"{cmd[0]}: a clinical conclusion without the caveat")


class TestBiologicalAge(unittest.TestCase):
    """PhenoAge is the most sensitive place: a pretty number is easy to obtain."""

    def _profile_copy(self, tmp):
        prof = Path(tmp) / "profile"
        shutil.copytree(support.FIXTURE_PROFILE, prof)
        return prof

    def _phenoage(self, prof):
        return support.run_json(["phenoage", "2026-07"], profile_dir=prof)

    def test_a_complete_panel_is_computed(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._phenoage(self._profile_copy(tmp))
            self.assertTrue(r.get("ok"), r)
            self.assertEqual(r["panel"], "2026-07")
            self.assertGreater(r["phenoage"], 0)

    def test_an_incomplete_panel_is_not_computed(self):
        """We remove one marker — there must be no result, not even an approximate one."""
        with tempfile.TemporaryDirectory() as tmp:
            prof = self._profile_copy(tmp)
            labs = json.loads((prof / "labs.json").read_text(encoding="utf-8"))
            del labs["markers"]["albumin"]
            (prof / "labs.json").write_text(json.dumps(labs, ensure_ascii=False), encoding="utf-8")
            r = self._phenoage(prof)
            self.assertFalse(r.get("ok"),
                             "biological age must not be computed from an incomplete panel: "
                             "substituting albumin from another month gives a pretty "
                             "but wrong number")
            self.assertTrue(r.get("missing") or r.get("missing_ru"),
                            "it must say exactly what is missing")

    def test_sex_does_not_influence_the_result(self):
        """The Levine 2018 formula has no sex term. If the result moved, the formula was edited."""
        with tempfile.TemporaryDirectory() as tmp:
            prof = self._profile_copy(tmp)
            base = self._phenoage(prof)["phenoage"]
            metrics = json.loads((prof / "metrics.json").read_text(encoding="utf-8"))
            metrics["profile"]["sex"] = "f"
            (prof / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False),
                                               encoding="utf-8")
            self.assertAlmostEqual(base, self._phenoage(prof)["phenoage"], places=6)

    def test_the_directions_of_the_coefficients(self):
        """Inflammation ages you, albumin makes you younger. A swapped sign is a quiet error."""
        with tempfile.TemporaryDirectory() as tmp:
            prof = self._profile_copy(tmp)
            base = self._phenoage(prof)["phenoage"]

            def _set(marker, value):
                labs = json.loads((prof / "labs.json").read_text(encoding="utf-8"))
                labs["markers"][marker]["series"] = [{"date": "2026-07", "value": value}]
                (prof / "labs.json").write_text(json.dumps(labs, ensure_ascii=False),
                                                encoding="utf-8")

            _set("crp_hs", 12.0)
            self.assertGreater(self._phenoage(prof)["phenoage"], base,
                               "a rise in CRP is obliged to raise the biological age")
            _set("crp_hs", 1.1)
            _set("albumin", 51.0)
            self.assertLess(self._phenoage(prof)["phenoage"], base,
                            "a rise in albumin is obliged to lower the biological age")


if __name__ == "__main__":
    unittest.main()
