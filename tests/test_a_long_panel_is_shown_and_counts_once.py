"""A system's long panel is shown beside its score and counts in it once (task 200).

Amino acids and protein are a system with seven markers in the score and a panel
of thirty-two amino acids and nine ratios beside it. A single amino acid says
little on its own, so the panel is not scored marker by marker: the share of it
outside its corridor is one term of the score, so a drifting panel shows at the
top level without thirty corridors outvoting the system's own markers (owner,
17.09.2026). A ratio is shown as printed or computed from components of one day,
and one with no published range is a value, not a deviation. A marker may count
in two systems; its first system in the file stays its home.
"""
from __future__ import annotations

import importlib
import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import format as F, i18n
from scholion.engine import panel_labs as PL
from scholion.engine import system_panels as SP
from scholion.i18n import en, ru

# The facade exports a function of the same name; the module is asked for by path.
L = importlib.import_module("scholion.engine.lifestyle")

DOM = {"key": "amino_acids", "panel_markers": ["aa_phenylalanine", "aa_tyrosine", "aa_glycine"],
       "derived": ["aa_ratio_phe_tyr", "aa_ratio_gly_ser", "aa_fischer_ratio", "aa_ratio_met_hcy"]}


def row(key, value, date="2026-06-01", flag="ok", abnormal=False, lo=10, hi=100):
    return {"key": key, "name": key, "value": value, "unit": "umol/L", "date": date, "flag": flag,
            "abnormal": abnormal, "ref_low": lo, "ref_high": hi}


class TestThePanelView(unittest.TestCase):

    def by_key(self):
        return {"aa_phenylalanine": row("aa_phenylalanine", 60), "aa_tyrosine": row("aa_tyrosine", 50),
                "aa_glycine": row("aa_glycine", 200, date="2026-06-01"),
                "aa_serine": row("aa_serine", 100, date="2025-01-01"),
                "aa_ratio_met_hcy": row("aa_ratio_met_hcy", 3.1, lo=None, hi=None)}

    def test_measured_and_unmeasured(self):
        v = PL.panel_view(DOM, self.by_key())
        self.assertEqual(3, len(v["markers"]))
        self.assertEqual([], v["unmeasured"])
        self.assertFalse(v["scored"])

    def test_each_ratio_says_where_its_value_comes_from(self):
        ratios = {x["key"]: x for x in PL.panel_view(DOM, self.by_key())["ratios"]}
        self.assertEqual("computed", ratios["aa_ratio_phe_tyr"]["origin"])
        self.assertAlmostEqual(1.2, ratios["aa_ratio_phe_tyr"]["value"])
        self.assertEqual("not_same_day", ratios["aa_ratio_gly_ser"]["origin"])
        self.assertEqual("missing", ratios["aa_fischer_ratio"]["origin"])
        self.assertIn("aa_leucine", ratios["aa_fischer_ratio"]["missing"])
        self.assertEqual("printed", ratios["aa_ratio_met_hcy"]["origin"])
        self.assertFalse(ratios["aa_ratio_met_hcy"]["has_range"])

    def test_a_zero_component_is_not_computable(self):
        bk = {"aa_phenylalanine": row("aa_phenylalanine", 60), "aa_tyrosine": row("aa_tyrosine", 0)}
        ratios = {x["key"]: x for x in PL.panel_view(DOM, bk)["ratios"]}
        self.assertEqual("not_computable", ratios["aa_ratio_phe_tyr"]["origin"])

    def test_a_system_without_a_panel_has_none(self):
        self.assertIsNone(PL.panel_view({"key": "lipids"}, {}))

    def test_the_report_prints_every_kind_of_ratio_in_both_languages(self):
        v = PL.panel_view(DOM, self.by_key())
        for lang, words in (("en", en.MESSAGES), ("ru", ru.MESSAGES)):
            with self.subTest(lang=lang):
                i18n.set_lang(lang)
                try:
                    text = "\n".join(F._panel_lines(v))
                finally:
                    i18n.set_lang(None)
                self.assertNotIn("⟦", text)
                self.assertIn(words["system.panel_labs.no_range"], text)


class TestThePanelCountsOnce(unittest.TestCase):

    def test_the_share_outside_is_one_term(self):
        bk = {"aa_phenylalanine": row("aa_phenylalanine", 200, flag="high", abnormal=True),
              "aa_tyrosine": row("aa_tyrosine", 50), "aa_glycine": row("aa_glycine", 50),
              "aa_serine": row("aa_serine", 50)}
        with mock.patch.dict(L._RADAR_PANELS, {"amino_acids": ["aa_phenylalanine", "aa_tyrosine",
                                                               "aa_glycine", "aa_serine"]}):
            term = L._panel_term("amino_acids", bk)
        self.assertEqual({"measured": 4, "judged": 4, "outside": 1, "score": 75,
                          "outside_keys": ["aa_phenylalanine"]}, term)

    def test_no_judged_panel_marker_adds_nothing(self):
        bk = {"aa_phenylalanine": row("aa_phenylalanine", 60, flag="norange", lo=None, hi=None)}
        with mock.patch.dict(L._RADAR_PANELS, {"amino_acids": ["aa_phenylalanine"]}):
            self.assertIsNone(L._panel_term("amino_acids", bk))

    def test_the_shipped_domain_scores_seven_and_shows_the_rest(self):
        (d,) = [x for x in SP.domains() if x["key"] == "amino_acids"]
        self.assertEqual(7, len(d["markers"]))
        self.assertTrue(d["panel_markers"])
        self.assertFalse(set(d["markers"]) & set(d["panel_markers"]),
                         "a marker is either scored or shown, never both")
        # 12 → 13 on 21.09.2026: Hyp:Pro, one of the ratios the panel author reads (task 205 H);
        # 13 → 14 on 25.09.2026: Trp:LNAA, with the denominator she named on 23.09.2026
        self.assertEqual(14, len(d["derived"]))
        self.assertIn("amino_acids", L._RADAR_PANELS)


class TestAMarkerInTwoSystems(unittest.TestCase):

    def test_its_first_system_is_its_home_and_every_system_is_named(self):
        home, every = SP.marker_systems(), SP.marker_systems_all()
        self.assertEqual("inflammation", home["homocysteine"])
        self.assertEqual(["inflammation", "amino_acids"], every["homocysteine"])
        self.assertEqual(["renal", "amino_acids"], every["creatinine"])
        self.assertEqual(["micronutrients", "musculoskeletal"], every["vitamin_d"])
        self.assertEqual(["inflammation", "immune"], every["crp_hs"])


class TestARatioTakesTheDrawThatHoldsItsComponents(unittest.TestCase):
    """A component measured again later must not throw away the draw they shared.

    Found on the owner's own profile, 17.09.2026: urea/creatinine — the one
    ratio of this panel with a published corridor — and methionine/homocysteine
    both refused to compute. Both pairs were drawn together on 22.07.2026, and
    both were dropped only because creatinine and homocysteine had a fresher
    point from 03.09. The rule «two values drawn months apart describe no
    moment» stands; what changed is that the engine now looks for the latest day
    that satisfies it instead of testing the newest points alone.
    """

    def _row(self, key, points):
        return {"key": key, "value": points[-1][1], "date": points[-1][0],
                "series": [{"date": d, "value": v} for d, v in points]}

    def test_the_last_draw_holding_every_component_is_the_one_used(self):
        from scholion.engine import panel_labs
        by_key = {"urea": self._row("urea", [("2026-07-22T09:28", 5.0)]),
                  "creatinine": self._row("creatinine", [("2026-07-22T09:28", 80.0),
                                                         ("2026-09-03T08:10", 88.0)])}
        r = panel_labs._ratio("urea_creatinine_ratio", by_key)
        self.assertEqual("computed", r["origin"], r)
        self.assertTrue(str(r["date"]).startswith("2026-07-22"), r)

    def test_a_marker_with_no_series_still_answers_from_its_single_point(self):
        from scholion.engine import panel_labs
        by_key = {"urea": {"key": "urea", "value": 5.0, "date": "2026-07-22T09:28"},
                  "creatinine": {"key": "creatinine", "value": 80.0, "date": "2026-07-22T10:00"}}
        r = panel_labs._ratio("urea_creatinine_ratio", by_key)
        self.assertEqual("computed", r["origin"], r)

    def test_a_ratio_whose_denominator_is_zero_says_so_instead_of_failing(self):
        from scholion.engine import panel_labs
        by_key = {"urea": self._row("urea", [("2026-07-22T09:28", 5.0)]),
                  "creatinine": self._row("creatinine", [("2026-07-22T09:28", 0.0)])}
        r = panel_labs._ratio("urea_creatinine_ratio", by_key)
        self.assertIn(r["origin"], ("not_computable", "computed"), r)

    def test_a_printed_ratio_is_taken_as_printed(self):
        from scholion.engine import panel_labs
        by_key = {"urea_creatinine_ratio": {"key": "urea_creatinine_ratio", "value": 0.06,
                                            "date": "2026-07-22", "name": "Urea/creatinine"},
                  "urea": self._row("urea", [("2026-07-22T09:28", 5.0)]),
                  "creatinine": self._row("creatinine", [("2026-07-22T09:28", 80.0)])}
        r = panel_labs._ratio("urea_creatinine_ratio", by_key)
        self.assertEqual("printed", r["origin"], r)

    def test_a_point_with_no_value_and_a_point_that_is_not_a_number_are_skipped(self):
        from scholion.engine import panel_labs
        by_key = {"urea": {"key": "urea", "value": 5.0, "date": "2026-07-22T09:28",
                           "series": [{"date": "2026-05-01", "value": None},
                                      {"date": "2026-07-22T09:28", "value": 5.0}]},
                  "creatinine": self._row("creatinine", [("2026-05-01", 70.0),
                                                         ("2026-07-22T09:28", 80.0)])}
        self.assertEqual("computed", panel_labs._ratio("urea_creatinine_ratio", by_key)["origin"])
        by_key["urea"]["series"][1]["value"] = "not a number"
        self.assertEqual("not_computable", panel_labs._ratio("urea_creatinine_ratio", by_key)["origin"])

    def test_components_that_never_share_a_day_are_still_refused(self):
        from scholion.engine import panel_labs
        by_key = {"urea": self._row("urea", [("2026-07-22T09:28", 5.0)]),
                  "creatinine": self._row("creatinine", [("2026-09-03T08:10", 88.0)])}
        r = panel_labs._ratio("urea_creatinine_ratio", by_key)
        self.assertEqual("not_same_day", r["origin"], r)


if __name__ == "__main__":
    unittest.main()
