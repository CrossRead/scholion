"""A read that failed inside the engine is not an answer about the person (task 209).

Each case below was a broad `except` that returned an empty value, and each empty
value had a meaning downstream: `[]` safety flags is «no red flag on this drug»,
an empty curated file is a shorter gene list printed as the whole one, a span of
0 months is «every reading falls inside six months», a radar without its fitness
domain is a radar of somebody who wears nothing, and an unchecked brief is a
«fresh» one. The failure is reproduced with a mock; the answer must either raise
or say that it did not read.
"""
from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from scholion import core
from scholion.i18n import en, ru

pgx = importlib.import_module("scholion.engine.pgx")
decision = importlib.import_module("scholion.engine.decision")
SP = importlib.import_module("scholion.engine.system_panels")
goals = importlib.import_module("scholion.engine.goals")
lifestyle_mod = importlib.import_module("scholion.engine.lifestyle")


def _knowledge_failing_on(name: str):
    """`core._read_knowledge` that fails for one file and reads every other one."""
    real = core._read_knowledge

    def fake(n: str):
        if n == name:
            raise json.JSONDecodeError("broken on purpose", "", 0)
        return real(n)
    return fake


class TestAnUnreadPrescriptionFileIsNotAbsenceOfAFlag(unittest.TestCase):

    def test_the_failure_is_raised_not_answered_as_no_flag(self):
        with mock.patch.object(core, "medications_json", side_effect=OSError("unreadable")):
            with self.assertRaises(OSError):
                pgx._own_safety_flags("atenolol")


class TestAnUnreadCuratedFileDoesNotShortenTheList(unittest.TestCase):

    def test_the_drug_context_list_raises(self):
        with mock.patch.object(core, "_read_knowledge", _knowledge_failing_on("drug_gene_context.json")):
            with self.assertRaises(ValueError):
                decision.curated_genes("warfarin")

    def _genetic_key(self) -> str:
        return next(d["key"] for d in SP.domains() if d["genetic_half"])

    def test_the_system_panel_file_raises(self):
        key = self._genetic_key()
        with mock.patch.object(core, "_read_knowledge", _knowledge_failing_on("system_gene_panels.json")):
            with self.assertRaises(ValueError):
                SP.composition(key)

    def test_the_base_composition_raises(self):
        key = self._genetic_key()
        with mock.patch.object(core, "_read_knowledge", _knowledge_failing_on("gencc_gene_disease.json")):
            with self.assertRaises(ValueError):
                SP.composition(key)


class TestAnUnreadableDateIsNotAShortWindow(unittest.TestCase):

    def test_the_span_is_unknown_not_zero(self):
        self.assertIsNone(goals._months_between("15.03.2024", "2025-06-01"))
        self.assertEqual(goals._months_between("2024-03-01", "2025-06-01"), 15)

    def test_the_skip_reason_says_the_dates_did_not_read(self):
        series = [{"date": d, "value": v} for d, v in
                  (("01.2023", 30.0), ("06.2023", 25.0), ("01.2024", 20.0))]
        # No corridor, so the person's own series is the only candidate and its
        # reason is the one printed.
        labs = {"markers": {"ferritin_test": {"name": "Ferritin", "unit": "ng/mL",
                                              "direction": "higher_better",
                                              "series": series}}}
        with mock.patch.object(core, "labs", return_value=labs), \
                mock.patch.object(core, "marker_catalog", return_value=[]), \
                mock.patch.object(goals, "_guideline_candidate", return_value=None):
            r = goals.suggest_goal_targets(["ferritin_test"])
        reasons = {s["key"]: s["reason"] for s in r["skipped"]}
        self.assertEqual(reasons.get("ferritin_test"), "dates_unreadable", r)

    def test_the_reason_is_said_in_both_languages(self):
        for cat in (en.MESSAGES, ru.MESSAGES):
            self.assertIn("goalgen.skip.dates_unreadable", cat)


class TestAnUnreadWearableLayerStaysOnTheRadar(unittest.TestCase):

    def test_the_fitness_domain_is_kept_and_named_as_unread(self):
        with mock.patch.object(lifestyle_mod, "lifestyle", side_effect=OSError("unreadable")):
            r = lifestyle_mod.health_radar()
        fit = [d for d in r["domains"] if d["key"] == "fitness"]
        self.assertEqual(len(fit), 1, "the fitness domain vanished from the radar")
        self.assertIsNone(fit[0]["score"])
        self.assertEqual(fit[0]["status"], "nodata")
        self.assertEqual(fit[0]["unread"], "OSError")


class TestAnUncheckedBriefIsNotFresh(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="scholion-209-")
        Path(self.tmp, "lifestyle_brief.json").write_text(
            json.dumps({"_meta": {"updated": "2026-01-01"}}), encoding="utf-8")
        self.restore = support.pin_profile(self.tmp)

    def tearDown(self):
        self.restore()

    def test_a_failed_check_marks_it_for_review(self):
        from scholion import assistant, engine
        with mock.patch.object(engine, "lifestyle_brief", side_effect=OSError("unreadable")):
            items = assistant._curated_state()
        brief = next(i for i in items if i["id"] == "brief")
        self.assertTrue(brief["stale"], "a check that did not run cleared the wording")
        from scholion.i18n import t as _t
        self.assertEqual(brief["note"], _t("assistant.curated.stale_unchecked"))
        self.assertIn("assistant.curated.stale_unchecked", ru.MESSAGES)


if __name__ == "__main__":
    unittest.main()
