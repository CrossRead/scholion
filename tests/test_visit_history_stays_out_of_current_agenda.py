"""A current visit agenda retains history separately without rewriting observations."""
from __future__ import annotations

import datetime
from unittest import mock

from scholion import engine, format as fmt, i18n, store
from tests.test_ingest_reads_a_table import TableCase


class VisitRecency(TableCase):
    def add(self, stamp):
        result = store.add_lab_point("creatinine", stamp, 150, unit="µmol/L",
                                     ref_low=60, ref_high=110, date_source="form")
        self.assertTrue(result["ok"])

    def test_old_result_is_retained_only_in_history_in_both_languages(self):
        self.add("2020-01-01")
        before = {p.name: p.read_bytes() for p in self.profile.iterdir()}
        for language in ("en", "ru"):
            with mock.patch.object(i18n._state, "current", language, create=True):
                data = engine.visit_sheet()
                self.assertFalse(data["measurements"])
                self.assertFalse(data["held_measurements"])
                self.assertEqual("2020-01-01", data["historical_measurements"][0]["date"])
                text = fmt.visit_report(data)
                self.assertIn(i18n.t("visit.historical", n=1), text)
                self.assertIn("2020-01-01", text)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.profile.iterdir()})

    def test_future_result_is_unverified_not_current_or_resolved(self):
        self.add("2099-01-01")
        data = engine.visit_sheet()
        self.assertFalse(data["measurements"])
        self.assertFalse(data["historical_measurements"])
        self.assertEqual(1, len(data["held_measurements"]))
        self.assertIn(i18n.t("visit.date_unverified"), fmt.visit_report(data))

    def test_current_result_still_enters_the_agenda(self):
        self.add(datetime.date.today().isoformat())
        data = engine.visit_sheet()
        self.assertEqual(1, len(data["measurements"]))
        self.assertFalse(data["historical_measurements"])
