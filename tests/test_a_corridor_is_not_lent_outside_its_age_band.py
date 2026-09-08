"""A corridor is not lent outside its age band — and every corridor in the
dictionary, not only the scored ones, says whose it is and whether age matters.

Two comments left beside the sex rule, both true. First: `ref_sex` was declared
for the thirty-five markers the radar scores, and for the other three hundred
and forty the question was still spelled as the absence of a field. Second: age
is the same class as sex and was not modelled at all — IGF-1 and DHEA-S depend
on age more than on sex, every laboratory bands them, and the dictionary held
one corridor for each, transcribed from one person's form at one age.

So the gate now covers every marker that holds a corridor, on both axes. The
vocabulary of `ref_age` has three states and no default: `any`, `banded` (the
laboratory bands it and the band of the corridor on record was not recorded —
lent to nobody), or a band in years. An unknown age is not lent a band: a
plausible default is the defect this exists to remove, not the remedy.
"""
from __future__ import annotations

import json
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core
from scholion import format as fmt
from scholion.engine import labs

SEX_WORDS = ("any", "male", "female", "unreviewed")

#: Corridors that could not be checked against a form or a standard interval
#: on 08.09.2026, frozen. **This set may only shrink**: a marker leaves it the
#: day somebody reads its form or names the interval it matches, and a marker
#: cannot join it — `unreviewed` is a debt recorded, not a place to park a
#: question. The estrogen-metabolite panel, osteocalcin and urine creatinine.
UNREVIEWED = frozenset({
    "est_16aohe1", "est_2ohe1", "est_2ohe2", "est_2ohe_sum", "est_2omee1",
    "est_4ohe1", "est_4omee1", "osteocalcin", "urine_creatinine",
})
AGE_WORDS = ("any", "banded")


def _corridor(e):
    return e.get("ref_low") is not None or e.get("ref_high") is not None


class TestEveryCorridorInTheDictionaryDeclaresBothAxes(unittest.TestCase):

    def setUp(self):
        self.cat = json.loads(
            core.knowledge_path("lab_markers.json").read_text(encoding="utf-8"))["markers"]

    def test_every_corridor_says_whose_it_is(self):
        silent = [k for k, e in self.cat.items()
                  if _corridor(e) and not e.get("ref_by_sex") and e.get("ref_sex") not in SEX_WORDS]
        self.assertEqual(silent, [], "these hold one corridor and do not say whose: "
                         + ", ".join(silent))

    def test_every_corridor_says_whether_age_matters(self):
        silent = []
        for k, e in self.cat.items():
            if not _corridor(e):
                continue
            rule = e.get("ref_age")
            ok = rule in AGE_WORDS or (isinstance(rule, dict)
                                       and {"min", "max"} <= set(rule)
                                       and rule["min"] <= rule["max"])
            if not ok:
                silent.append(k)
        self.assertEqual(silent, [], "these hold a corridor and do not say whether it "
                         "depends on age (any / banded / {min, max}): " + ", ".join(silent))

    def test_the_age_banded_hormones_are_not_lent_as_if_age_did_not_exist(self):
        for k in ("igf1", "dheas"):
            with self.subTest(marker=k):
                self.assertNotEqual(self.cat[k].get("ref_age"), "any",
                                    f"{k} is banded by age at every laboratory")

    def test_the_unreviewed_set_can_only_shrink(self):
        now = {k for k, e in self.cat.items() if e.get("ref_sex") == "unreviewed"}
        self.assertEqual(set(), now - UNREVIEWED,
                         "a corridor was parked as `unreviewed` — read its form or name the "
                         "interval it matches instead: " + ", ".join(sorted(now - UNREVIEWED)))
        gone = UNREVIEWED - now
        self.assertEqual(set(), {k for k in gone if k in self.cat and self.cat[k].get("ref_sex") == "unreviewed"})

    def test_a_test_for_one_sex_declares_a_corridor_of_that_sex(self):
        for k, e in self.cat.items():
            if e.get("applies_to_sex"):
                with self.subTest(marker=k):
                    self.assertIn(e["applies_to_sex"], ("male", "female"))
                    self.assertEqual(e.get("ref_sex"), e["applies_to_sex"],
                                     "a male-only test cannot hold a female or neutral corridor")

    def test_a_marker_with_no_corridor_owes_no_declaration(self):
        """The gate asks about lending; a marker with nothing to lend has nothing
        to declare, and demanding a word there would be a field nobody reads."""
        self.assertTrue(any(not _corridor(e) and "ref_age" not in e for e in self.cat.values()))


class TestTheCorridorStaysInsideItsBand(unittest.TestCase):
    """Built rather than found, as the sex tests are: the value is stored with no
    range of its own, so the dictionary's corridor is the only one on offer."""

    def one(self, key, age, sex="male", value=150.0, rule=None):
        base = core.lab_markers()
        cat = json.loads(json.dumps(base))
        if rule is not None:
            cat["markers"][key]["ref_age"] = rule
        with mock.patch.object(core, "labs", lambda: {"markers": {key: {
                "name": key.upper(), "unit": "ng/mL",
                "series": [{"date": "2026-06", "value": value}]}}}), \
             mock.patch.object(core, "profile_sex", lambda: sex), \
             mock.patch.object(core, "profile_age", lambda: age), \
             mock.patch.object(core, "lab_markers", lambda: cat):
            for m in labs.analyze_labs()["markers"]:
                if m["key"] == key:
                    return m
        self.fail(f"{key} did not reach the marker list at all")

    def test_a_banded_corridor_with_no_band_on_record_is_lent_to_nobody(self):
        for age in (25, 45, 70, None):
            with self.subTest(age=age):
                m = self.one("igf1", age)
                self.assertIsNone(m["ref_low"])
                self.assertIsNone(m["ref_high"])
                self.assertEqual(m["flag"], "norange")
                self.assertFalse(m["abnormal"])
                self.assertTrue(m["ref_age_unbanded"], "the reason must be printable")

    def test_inside_the_band_the_corridor_is_lent(self):
        m = self.one("igf1", 45, rule={"min": 40, "max": 49})
        self.assertEqual(m["ref_low"], 90)
        self.assertEqual(m["ref_high"], 250)
        self.assertFalse(m["ref_age_other"])
        self.assertFalse(m["ref_age_unknown"])

    def test_outside_the_band_it_is_withheld_with_the_reason(self):
        m = self.one("igf1", 62, rule={"min": 40, "max": 49})
        self.assertIsNone(m["ref_high"], "a corridor of another age band was lent")
        self.assertTrue(m["ref_age_other"])
        self.assertEqual(m["flag"], "norange")

    def test_an_unrecorded_age_is_not_lent_a_band(self):
        m = self.one("igf1", None, rule={"min": 40, "max": 49})
        self.assertIsNone(m["ref_high"])
        self.assertTrue(m["ref_age_unknown"])
        self.assertFalse(m["ref_age_other"])

    def test_an_age_independent_corridor_is_lent_at_every_age(self):
        for age in (25, 70, None):
            with self.subTest(age=age):
                m = self.one("igf1", age, rule="any")
                self.assertEqual(m["ref_high"], 250)
                self.assertFalse(m["ref_age_unbanded"])

    def test_the_sex_rule_still_comes_first(self):
        """A man's corridor asked for by a woman is refused for the sex reason,
        whatever the age says — one reason, the nearer one."""
        m = self.one("dheas", 40, sex="female", rule={"min": 35, "max": 44})
        self.assertIsNone(m["ref_high"])
        self.assertTrue(m["ref_sex_other"])
        self.assertFalse(m["ref_age_other"])


class TestAnUncheckedCorridorAndAOneSexTest(unittest.TestCase):

    def one(self, key, sex, value=1.0):
        with mock.patch.object(core, "labs", lambda: {"markers": {key: {
                "name": key.upper(), "unit": "x",
                "series": [{"date": "2026-06", "value": value}]}}}), \
             mock.patch.object(core, "profile_sex", lambda: sex), \
             mock.patch.object(core, "profile_age", lambda: 45):
            for m in labs.analyze_labs()["markers"]:
                if m["key"] == key:
                    return m
        self.fail(f"{key} did not reach the marker list at all")

    def test_an_unreviewed_corridor_is_lent_to_nobody(self):
        for sex in ("male", "female", None):
            with self.subTest(sex=sex):
                m = self.one("est_2ohe1", sex)
                self.assertIsNone(m["ref_high"])
                self.assertEqual(m["flag"], "norange")
                self.assertTrue(m["ref_sex_unreviewed"])
                self.assertFalse(m["ref_sex_other"], "«unreviewed» is not «somebody else's»")

    def test_psa_for_a_woman_is_not_a_borrowed_corridor_but_a_test_that_does_not_apply(self):
        m = self.one("psa_total", "female")
        self.assertIsNone(m["ref_high"])
        self.assertTrue(m["sex_not_applicable"])
        self.assertFalse(m["ref_sex_other"], "the interval is not the fact; the test is")
        self.assertEqual(m["flag"], "norange")

    def test_psa_for_a_man_is_his_test_and_only_the_age_band_withholds_it(self):
        m = self.one("psa_total", "male")
        self.assertFalse(m["sex_not_applicable"])
        self.assertIsNone(m["ref_high"], "total PSA is banded by age at every laboratory")
        self.assertTrue(m["ref_age_unbanded"], "the one reason left must be the age band")
        free = self.one("psa_free_pct", "male")
        self.assertEqual(free["ref_low"], 15.0, "the free fraction is not banded and is his")
        self.assertFalse(free["sex_not_applicable"])

    def test_psa_with_no_sex_recorded_is_refused_for_the_sex_reason_not_this_one(self):
        m = self.one("psa_total", None)
        self.assertIsNone(m["ref_high"])
        self.assertFalse(m["sex_not_applicable"], "nobody said the person is not a man")
        self.assertTrue(m["ref_sex_other"])


class TestTheReasonIsPrintedBesideTheValue(unittest.TestCase):
    """A refusal the page does not print is a corridor that silently vanished."""

    def test_each_of_the_three_reasons_has_its_own_words(self):
        seen = set()
        for flag in ("ref_age_other", "ref_age_unknown", "ref_age_unbanded",
                     "ref_sex_unreviewed", "sex_not_applicable"):
            text = fmt._fmt_ref({"ref_low": None, "ref_high": None, flag: True})
            self.assertTrue(text.strip(), f"{flag} printed nothing")
            self.assertNotIn(text, seen, "two different reasons must not read the same")
            seen.add(text)
        self.assertIn("birth-year", fmt._fmt_ref({"ref_low": None, "ref_high": None,
                                                  "ref_age_unknown": True}),
                      "the reason names what would supply the corridor")


class TestTheAgeReaderIsOne(unittest.TestCase):

    def test_core_reads_both_birth_fields(self):
        from datetime import date
        y = date.today().year
        self.assertEqual(y - 1980, core.age_from({"birth_year": 1980}))
        self.assertIn(core.age_from({"birth_date": f"{y - 40}-01-01"}), (39, 40))
        self.assertIsNone(core.age_from({}))
        self.assertIsNone(core.age_from({"birth_year": "nineteen-eighty"}))


if __name__ == "__main__":
    unittest.main()
