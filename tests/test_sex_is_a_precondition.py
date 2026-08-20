"""Two places where a missing sex used to produce a confident wrong answer.

TASK 86. «3× the upper limit of normal» is a rule, and the upper limit of normal
is published as a sex pair. The catalogue stored the product instead of the rule
— 123 for ALT, 570 for CK, both computed from the male bound — so a woman on a
statin with ALT 110 got no signal (hers is about 99) and with CK 520 got no
signal (hers is about 510). Both are misses in the dangerous direction:
drug-induced liver injury and statin myopathy. `clinical_thresholds.json` had
said in its own `_meta` that the fix was an `applies_when_sex` field «plus two
lines in `_thresholds_for` next to the class check — otherwise the field is
decoration rather than a rule». It had been decoration for as long as the note
had been there.

TASK 87. `prs.py` did not contain the word `sex`, so a woman with a VCF was
handed a prostate-cancer percentile as an ordinary line of the report.

Both guards treat an unrecorded sex as its own case rather than as one of the
two. They resolve it in OPPOSITE directions, and that is the point: a decision
threshold errs towards asking a doctor, while a percentile about an organ has
nothing to err towards and is withheld.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, prs
from scholion.engine import labs


class SexCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = self.tmp.name
        self.set_sex(None)

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        core.reset_cache()
        self.tmp.cleanup()

    def set_sex(self, sex):
        profile = {"sex": sex} if sex else {}
        Path(self.tmp.name, "metrics.json").write_text(
            json.dumps({"profile": profile}), encoding="utf-8")
        core.reset_cache()


class TestThresholdsFollowTheRuleNotTheProduct(SexCase):

    def alt(self, value):
        return labs._decision_limits("alt", value)

    def ck(self, value):
        return labs._decision_limits("ck", value, active_classes={"statin"})

    def test_a_woman_with_alt_110_on_a_statin_gets_the_signal(self):
        self.set_sex("female")
        crossed = [d for d in self.alt(110.0) if d["crossed"]]
        self.assertTrue(crossed, "3×33 is 99 — the value is over it")
        self.assertEqual(crossed[0]["value"], 99.0)

    def test_a_man_with_alt_110_does_not(self):
        self.set_sex("male")
        self.assertEqual([d for d in self.alt(110.0) if d["crossed"]], [],
                         "3×41 is 123 — the same value is under it, and that is correct")

    def test_a_woman_with_ck_520_on_a_statin_gets_the_signal(self):
        self.set_sex("female")
        crossed = [d for d in self.ck(520.0) if d["crossed"]]
        self.assertTrue(crossed)
        self.assertEqual(crossed[0]["value"], 510.0)

    def test_the_number_is_computed_from_the_bound_not_stored_beside_it(self):
        self.set_sex("male")
        d = self.alt(1.0)[0]
        self.assertEqual(d["ref_high_used"], 41)
        self.assertEqual(d["value"], 123.0)
        self.assertIn("ref_high", d["from_rule"])

    def test_an_unrecorded_sex_takes_the_more_sensitive_bound_and_says_so(self):
        self.set_sex(None)
        d = [x for x in self.alt(110.0) if x["crossed"]]
        self.assertTrue(d, "falling silent is not the safe side for a decision limit")
        self.assertTrue(d[0].get("sex_unknown_most_cautious"))
        self.assertIn("sex", d[0]["note"].lower())

    def test_the_catalogue_no_longer_stores_the_product(self):
        for key in ("alt", "ck"):
            with self.subTest(marker=key):
                first = core.clinical_thresholds()["markers"][key][0]
                self.assertIn("multiple_of_ref_high", first)
                self.assertNotIn("value", first,
                                 "a rule and its product in one entry is two sources of truth")


class TestASexSpecificScoreIsWithheld(SexCase):

    def traits(self):
        return prs._load_traits()

    def test_a_woman_is_not_given_a_prostate_percentile(self):
        self.set_sex("female")
        kept, withheld = prs._sex_filtered(self.traits())
        terms = [w["term"] for w in withheld]
        self.assertIn("prostate cancer", terms)
        self.assertNotIn("prostate cancer", [t.get("term") for t in kept])

    def test_a_man_keeps_them(self):
        self.set_sex("male")
        kept, withheld = prs._sex_filtered(self.traits())
        self.assertEqual(withheld, [])

    def test_an_unrecorded_sex_withholds_rather_than_defaulting(self):
        self.set_sex(None)
        _kept, withheld = prs._sex_filtered(self.traits())
        self.assertTrue(withheld)
        self.assertEqual({w["reason"] for w in withheld}, {"sex_not_recorded"})

    def test_the_withheld_ones_are_named_not_dropped(self):
        self.set_sex("female")
        _kept, withheld = prs._sex_filtered(self.traits())
        for w in withheld:
            with self.subTest(term=w["term"]):
                self.assertTrue(w.get("label"))
                self.assertTrue(w.get("applies_to_sex"))

    def test_the_stored_report_is_filtered_too(self):
        """`prs_results.json` may predate the moment the sex was recorded."""
        from scholion.engine import genomics
        stored = [{"term": "prostate cancer", "label": "Prostate cancer", "percentile": 91,
                   "reliable": True},
                  {"term": "type 2 diabetes", "label": "Type 2 diabetes", "percentile": 55,
                   "reliable": True}]
        self.set_sex("female")
        kept, withheld = genomics._withheld_by_sex(stored)
        self.assertEqual([t["term"] for t in kept], ["type 2 diabetes"])
        self.assertEqual(len(withheld), 1)
        self.assertIn("organ", withheld[0]["note"])


if __name__ == "__main__":
    unittest.main()
