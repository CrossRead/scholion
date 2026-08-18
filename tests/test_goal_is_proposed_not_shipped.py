"""A goal is proposed from evidence, never shipped with the product.

Until 0.3.0 `health_goals.json` arrived carrying one person's targets — a weight,
a body-fat percentage, a reference window of 2021–2022 — and every new profile
opened under them. The mechanism was general; the numbers in it were not.

What replaces it has to earn each number, and the tests here are about WHERE a
number came from rather than what it is. Three sources, and they are not
interchangeable:

  guideline      a clinical association published it, and it is quoted with its
                 citation;
  personal_best  the person's own series reached it, with the date and the count
                 behind it — a fact about them, not advice from anybody;
  reference      the wall of the laboratory corridor, weakest of the three.

The failure this guards against is any of the three quietly turning into another:
a corridor bound presented as a recommendation, a recommendation presented as an
observation, or — the one that started all of this — somebody else's number
presented as yours.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support

KB = support.ROOT / "src" / "scholion" / "knowledge" / "goal_targets.json"


def _profile(markers):
    d = Path(tempfile.mkdtemp(prefix="goalgen_"))
    for name, body in (("labs.json", {"markers": markers}),
                       ("medications.json", {"medications": []}),
                       ("pharmacogenomics.json", {"genotypes": []})):
        body["_meta"] = {"purpose": "SYNTHETIC — a test fixture", "synthetic": True}
        (d / name).write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return d


def _series(*pairs):
    return [{"date": d, "value": v} for d, v in pairs]


class TestEveryProposedNumberSaysWhereItCameFrom(unittest.TestCase):

    def setUp(self):
        self.dirs = []

    def tearDown(self):
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    def _run(self, markers):
        d = _profile(markers)
        self.dirs.append(d)
        return support.run_json(["goal-suggest"], profile_dir=d)

    def test_no_proposal_lacks_a_source(self):
        r = self._run({"ferritin": {"name": "Ferritin", "unit": "ng/mL", "ref_low": 20,
                                    "ref_high": 150,
                                    "series": _series(("2023-01", 34), ("2024-06", 22),
                                                      ("2025-06", 18), ("2026-06", 13))}})
        self.assertTrue(r["proposals"], "nothing was proposed for a four-year decline")
        for p in r["proposals"]:
            with self.subTest(marker=p["key"]):
                self.assertIn(p["proposed"], ("guideline", "personal_best", "reference"))
                cand = next(c for c in p["candidates"] if c["source"] == p["proposed"])
                self.assertTrue(cand.get("why"), "a number with no account of itself")

    def test_a_personal_best_carries_the_date_and_the_count_behind_it(self):
        """«Where you have been» is only a fact if it says when, and out of how many."""
        r = self._run({"ferritin": {"name": "Ferritin", "unit": "ng/mL", "ref_low": 20,
                                    "ref_high": 150,
                                    "series": _series(("2023-01", 34), ("2024-06", 22),
                                                      ("2025-06", 18), ("2026-06", 13))}})
        p = next(x for x in r["proposals"] if x["key"] == "ferritin")
        self.assertEqual(p["proposed"], "personal_best",
                         "a corridor bound was preferred to the person's own best")
        cand = next(c for c in p["candidates"] if c["source"] == "personal_best")
        self.assertEqual(cand["value"], 34)
        obs = cand["observed"]
        self.assertEqual(obs["date"], "2023-01")
        self.assertEqual(obs["n"], 4)
        self.assertGreater(obs["span_months"], 6)

    def test_a_guideline_target_never_appears_without_its_citation(self):
        kb = json.loads(KB.read_text(encoding="utf-8"))["targets"]
        for key, entry in kb.items():
            with self.subTest(marker=key):
                src = entry.get("source") or {}
                for field in ("body", "document", "year", "url"):
                    self.assertTrue(src.get(field),
                                    f"{key}: a target with no {field} is an assertion, "
                                    f"not a citation")
                self.assertTrue(entry.get("no_target") or entry.get("value") is not None
                                or entry.get("by_category"),
                                f"{key}: neither a target nor a stated refusal")

    def test_a_withdrawn_target_is_carried_rather_than_quietly_replaced(self):
        """The Endocrine Society withdrew the 25(OH)D target in 2024.

        The laboratory corridor is still on the form, so a proposal may still be
        made from it — but the refusal has to travel with it. Without that, the
        corridor silently supplies the number the society declined to write, and
        the reader cannot tell which of the two they are looking at.
        """
        r = self._run({"vitamin_d": {"name": "Vitamin D (25-OH)", "unit": "ng/mL",
                                     "ref_low": 30, "ref_high": 100,
                                     "series": _series(("2025-01", 21), ("2025-08", 23),
                                                       ("2026-06", 23.8))}})
        p = next((x for x in r["proposals"] if x["key"] == "vitamin_d"), None)
        met = next((x for x in r["already_met"] if x["key"] == "vitamin_d"), None)
        skipped = next((x for x in r["skipped"] if x["key"] == "vitamin_d"), None)
        carrier = p or met or skipped
        self.assertIsNotNone(carrier, "the marker vanished from all three lists")
        if p:
            self.assertTrue(p.get("caveat"), "the withdrawal did not travel with the number")
            self.assertIn("Endocrine Society", p["caveat"])
        else:
            self.assertTrue(any(c.get("no_target") for c in carrier.get("candidates", [])))

    def test_a_target_for_a_condition_is_not_chosen_on_an_unconfirmed_condition(self):
        """ADA's «under 7 %» is a goal for somebody who HAS diabetes.

        Offered to a person with a normal HbA1c it is worse than useless: it reads
        as permission to sit anywhere below 7. It stays visible as a candidate; it
        may not be the proposal.
        """
        r = self._run({"hba1c": {"name": "HbA1c", "unit": "%", "ref_low": 4.0, "ref_high": 6.0,
                                 "series": _series(("2024-01", 5.9), ("2025-01", 6.3),
                                                   ("2026-06", 6.4))}})
        p = next((x for x in r["proposals"] if x["key"] == "hba1c"), None)
        if p is not None:
            self.assertNotEqual(p["proposed"], "guideline",
                                "a diabetes target was adopted for a profile that does not "
                                "say the person has diabetes")

    def test_a_target_already_met_is_not_offered_as_something_to_reach(self):
        r = self._run({"alt": {"name": "ALT", "unit": "U/L", "ref_high": 33,
                               "series": _series(("2024-01", 19), ("2025-01", 20),
                                                 ("2026-06", 19))}})
        self.assertFalse([x for x in r["proposals"] if x["key"] == "alt"],
                         "a goal was proposed for a value already inside its corridor")
        self.assertTrue([x for x in r["already_met"] if x["key"] == "alt"]
                        or [x for x in r["skipped"] if x["key"] == "alt"],
                        "the marker disappeared instead of being accounted for")

    def test_a_single_reading_is_never_a_personal_best(self):
        r = self._run({"ferritin": {"name": "Ferritin", "unit": "ng/mL", "ref_low": 20,
                                    "ref_high": 150, "series": _series(("2026-06", 13))}})
        for p in r["proposals"]:
            cand = next(c for c in p["candidates"] if c["source"] == p["proposed"])
            self.assertNotEqual(cand["source"], "personal_best",
                                "one measurement was called a best")

    def test_what_was_passed_over_is_accounted_for(self):
        """A list of proposals with no account of the rest reads as «these are the
        ones that matter», which is a different and false claim."""
        r = self._run({"ferritin": {"name": "Ferritin", "unit": "ng/mL", "ref_low": 20,
                                    "ref_high": 150, "series": _series(("2026-06", 13))},
                       "alt": {"name": "ALT", "unit": "U/L", "ref_high": 33,
                               "series": _series(("2026-06", 19))}})
        seen = {x["key"] for x in r["proposals"]} | {x["key"] for x in r["already_met"]} \
            | {x["key"] for x in r["skipped"]}
        self.assertEqual(seen, {"ferritin", "alt"}, "a marker was silently dropped")
        for s in r["skipped"]:
            self.assertTrue(s.get("reason"), "passed over with no reason given")


class TestWritingAGoalDoesNotOverwriteOne(unittest.TestCase):
    """A target the person wrote by hand is the strongest source there is.

    Stronger than any guideline, because it is theirs. A writer that replaced it
    would be this feature's own defect pointed the other way.
    """

    def setUp(self):
        self.dir = _profile({"ferritin": {"name": "Ferritin", "unit": "ng/mL", "ref_low": 20,
                                          "ref_high": 150,
                                          "series": _series(("2023-01", 34), ("2024-06", 22),
                                                            ("2025-06", 18), ("2026-06", 13))}})

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_an_existing_target_survives(self):
        goals = self.dir / "health_goals.json"
        goals.write_text(json.dumps({
            "_meta": {"purpose": "SYNTHETIC — a test fixture", "synthetic": True},
            "targets": [{"label": "Ferritin", "source": "lab:ferritin", "target": ">=80",
                         "best": "mine"}]}, ensure_ascii=False), encoding="utf-8")
        code, out, err = support.run(["goal-suggest", "--write"], profile_dir=self.dir)
        self.assertEqual(code, 0, err)
        after = json.loads(goals.read_text(encoding="utf-8"))
        mine = [t for t in after["targets"] if t["label"] == "Ferritin"]
        self.assertEqual(len(mine), 1, "the writer duplicated a target instead of keeping it")
        self.assertEqual(mine[0]["target"], ">=80",
                         "a target the person set by hand was replaced by a proposed one")

    def test_what_is_written_records_where_it_came_from(self):
        code, out, err = support.run(["goal-suggest", "--write"], profile_dir=self.dir)
        self.assertEqual(code, 0, err)
        after = json.loads((self.dir / "health_goals.json").read_text(encoding="utf-8"))
        for t in after["targets"]:
            with self.subTest(target=t.get("label")):
                self.assertIn("_from", t, "a number in the file with no account of itself")
                self.assertIn(t["_from"]["source"],
                              ("guideline", "personal_best", "reference"))

    def test_nothing_is_written_without_being_asked(self):
        support.run(["goal-suggest"], profile_dir=self.dir)
        self.assertFalse((self.dir / "health_goals.json").exists(),
                         "a read-only command wrote to the profile")


if __name__ == "__main__":
    unittest.main()
