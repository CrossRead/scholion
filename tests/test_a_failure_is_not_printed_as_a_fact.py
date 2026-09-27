"""A failure is never printed as a fact about the person (task 209, round 2).

Four places where something that could not be read came out as a statement:

1. A lab value that could not be compared with a clinical action threshold (text
   in place of a number) dropped the threshold row. The ❗ «crossed» vanished, the
   prescription check lost its «watch» item, and with a drug in context the next
   threshold printed as «not reached».
2. A date of the last measurement that could not be read counted as «recent», so
   a monitoring test was marked done, moved down the list, and the garbled string
   was printed as the date of the last measurement.
3. When the wearable metrics could not be read at all, the overview dropped its
   lifestyle line — the same page as «nothing worth watching».
4. Online, a request to RxNorm that got no answer came back as «no such drug».
"""
from __future__ import annotations

import unittest
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path

from scholion import core, drugsource, format as fmt, net
import importlib

from scholion.engine import _helpers as H, labs as LB, pgx as PG
from scholion.format_primitives import _decision_suffix

# the package re-exports a FUNCTION named `lifestyle`, which hides the module
LS = importlib.import_module("scholion.engine.lifestyle")

_THRESHOLD = {"markers": {"hct": [{"value": 54.0, "side": "high", "label": "therapy pause",
                                    "action": "pause", "source": "guideline"}]}}


class TestAValueThatCannotBeComparedLeavesTheThresholdOpen(unittest.TestCase):

    def rows(self, value):
        with mock.patch.object(core, "clinical_thresholds", return_value=_THRESHOLD):
            return LB._decision_limits("hct", value)

    def test_text_is_an_unresolved_row_not_a_missing_one(self):
        (row,) = self.rows("haemolysed")
        self.assertIsNone(row["crossed"], "an uncompared threshold was dropped or decided")
        self.assertEqual("not_comparable", row["why"])

    def test_no_number_at_all_is_unresolved_too(self):
        (row,) = self.rows(None)
        self.assertIsNone(row["crossed"])

    def test_a_number_still_compares(self):
        self.assertIs(True, self.rows(55.0)[0]["crossed"])
        self.assertIs(False, self.rows(40.0)[0]["crossed"])

    def test_the_text_says_could_not_be_compared_and_never_not_reached(self):
        m = {"decisions": [{"value": 54.0, "side": "high", "label": "therapy pause",
                            "crossed": None, "why": "not_comparable"}]}
        for context in (False, True):
            with self.subTest(context=context):
                s = _decision_suffix(m, context=context)
                self.assertIn("could not be compared", s)
                self.assertNotIn("not reached", s)

    def test_a_compared_threshold_still_says_not_reached(self):
        m = {"decisions": [{"value": 54.0, "side": "high", "label": "therapy pause",
                            "crossed": False}]}
        self.assertIn("not reached", _decision_suffix(m, context=True))

    def test_the_web_page_renders_the_open_state(self):
        html = (support.SRC / "scholion" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("d.crossed===null", html)
        self.assertIn("web.decision.not_comparable", html)

    def test_the_prescription_check_puts_it_into_unresolved(self):
        marker = {"key": "creatinine", "name": "Creatinine", "value": "see note", "unit": "",
                  "flag": "norange", "near_limit": None, "personal_move": None,
                  "ref_low": None, "ref_high": None,
                  "decisions": [{"value": 150.0, "side": "high", "label": "dose review",
                                 "crossed": None, "why": "not_comparable"}]}
        with mock.patch.object(PG, "analyze_labs", return_value={"markers": [marker]}):
            r = PG.check_new_prescription("metformin")
        self.assertEqual(["Creatinine"], [x["name"] for x in r["labs"]["unresolved"]])
        mon = [u for u in r["unresolved"] if u["what"] == "monitoring"]
        self.assertTrue(mon and "Creatinine" in mon[0]["detail"],
                        "an uncompared threshold did not reach `unresolved`")
        self.assertNotEqual("low", r["overall"])


class TestAnUnreadableDateIsNotARecentOne(unittest.TestCase):

    def test_the_decision_form_says_unknown(self):
        self.assertIsNone(H._recent_or_unknown("13.09.2026"))
        self.assertIsNone(H._recent_or_unknown("sometime"))

    def test_the_display_form_keeps_it_in_view(self):
        # profile_view / system_panels / lifestyle keep an abnormal value with a
        # garbled date on screen rather than filing it under «stale».
        self.assertIs(True, H._recent("13.09.2026"))
        self.assertIs(False, H._recent(""))

    def suggest(self, last_date):
        rules = {"rules": [{"id": "r1", "suggest": "Creatinine", "why": "w", "priority": "high",
                            "when": {"measured": ["creatinine"]}, "covers": ["creatinine"],
                            "recheck_months": 3}]}
        with mock.patch.object(core, "test_rules", return_value=rules), \
                mock.patch.object(LB, "_eval_condition", return_value=True), \
                mock.patch.object(LB, "_marker_last_date", return_value=last_date):
            return LB.suggest_tests()

    def test_a_test_with_an_unreadable_date_stays_pending(self):
        r = self.suggest("13.09.2026")
        (s,) = r["suggestions"]
        self.assertFalse(s.get("done_recently"), "an unreadable date counted as recently done")
        self.assertNotIn("last_measured", s, "a garbled string printed as the last measurement")
        self.assertEqual("13.09.2026", s["last_measured_unreadable"])
        self.assertEqual(1, r["count"])
        text = fmt.tests_report(r)
        self.assertIn("cannot be read", text)

    def test_a_readable_recent_date_is_still_done(self):
        import datetime
        (s,) = self.suggest(datetime.date.today().strftime("%Y-%m-%d"))["suggestions"]
        self.assertTrue(s.get("done_recently"))


class TestUnreadWearablesAreSaidOnTheOverview(unittest.TestCase):

    def test_a_failed_read_is_named_not_dropped(self):
        with mock.patch.object(LS, "lifestyle", side_effect=OSError("disk")):
            block = LS._lifestyle_overview()
        self.assertIsNotNone(block, "a failed read came back as «no lifestyle block»")
        self.assertEqual("OSError", block["unread"])
        base = {"markers_total": 1, "abnormal_count": 0, "flagged": [], "high_flags": [],
                "watch_flags": [], "pending_suggestions": [], "genome_gaps": [],
                "disclaimer": "—", "lifestyle": block}
        self.assertIn("could not be read", fmt.overview_report(base))


class TestANetworkFailureIsNotAnUnknownDrug(unittest.TestCase):

    def lookup(self, get_json):
        with mock.patch.object(net, "offline", return_value=False), \
                mock.patch.object(net, "get_json", side_effect=get_json), \
                mock.patch.object(drugsource, "_load_cache", return_value={}), \
                mock.patch.object(drugsource, "_save_cache"):
            return (PG._check_drug_online("zzunreachableol"),
                    PG.check_interactions("zzunreachableol"))

    def test_no_answer_is_could_not_be_looked_up(self):
        r, inter = self.lookup(lambda url, *a, **k: None)
        self.assertNotEqual("not_found", r["status"], "a network failure printed as «no such drug»")
        self.assertEqual(("not_checked", "unreachable"), (r["status"], r["reason"]))
        self.assertEqual("unreachable", drugsource.why_unresolved("zzunreachableol"))
        self.assertIn("could not be looked up", r["message"])
        self.assertIn("did not answer", inter["message"])
        self.assertIn("could not be looked up", fmt.drug_check(r))

    def test_an_answered_miss_is_still_not_found(self):
        r, inter = self.lookup(lambda url, *a, **k: {})
        self.assertEqual(("not_found", "unknown_name"), (r["status"], r["reason"]))
        self.assertEqual("not_found", drugsource.why_unresolved("zzunreachableol"))
        self.assertNotIn("did not answer", inter["message"])


if __name__ == "__main__":
    unittest.main()
