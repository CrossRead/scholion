"""A sourced formula cannot borrow a missing input from another draw."""
from __future__ import annotations

import copy
import math
from unittest import mock

from scholion import core, engine, format as fmt, i18n, ouroboros_tools
from tests.test_ingest_reads_a_table import TableCase


class TestFib4(TableCase):
    def setUp(self):
        super().setUp()
        self.previous_language = i18n.lang()
        i18n.set_lang("en")
        self.addCleanup(i18n.set_lang, self.previous_language)
        self.data = {"markers": {k: {"unit": unit, "series": [
            {"date": "2026-02-01T08:30", "value": value, "date_source": "form"}]}
            for k, unit, value in [("ast", "U/L", 40), ("alt", "U/L", 25),
                                   ("platelets", "10*9/L", 200)]}}
        self.profile_data = {"birth_date": "1976-02-02"}

    def calculate(self):
        with mock.patch.object(core, "labs", return_value=self.data), \
                mock.patch.object(core, "metrics_json", return_value={"profile": self.profile_data}):
            return engine.fib4()

    def point(self, key):
        return self.data["markers"][key]["series"][0]

    def test_formula_uses_age_at_draw_and_retains_sources_without_writing(self):
        source = {"path": "synthetic.pdf", "pages": [1], "specimen": "blood",
                  "draw_date": "2026-02-01T08:30"}
        for key in self.data["markers"]:
            self.point(key)["source"] = source
        before = {p.name: p.read_bytes() for p in self.profile.iterdir()}
        result = self.calculate()
        self.assertEqual(("computed", 1.96, 49), (result["status"], result["value"], result["age"]))
        self.assertEqual("withheld", result["interpretation"]["status"])
        self.assertTrue(all(p["source"] == source for p in result["inputs"]))
        self.assertIn("16729309", fmt.fib4_report(result))
        self.assertNotIn("risk", {k for k in result})
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.profile.iterdir()})

    def test_never_joins_two_times_on_one_day(self):
        self.point("alt")["date"] = "2026-02-01T09:30"
        result = self.calculate()
        self.assertIsNone(result["value"])
        self.assertEqual("missing", result["status"])
        self.assertEqual({"ast", "platelets"}, set(result["missing"]))

    def test_latest_complete_draw_is_labelled_when_newer_draw_is_partial(self):
        self.data["markers"]["ast"]["series"].append(
            {"date": "2026-02-02", "value": 400, "date_source": "form"})
        result = self.calculate()
        self.assertEqual(1.96, result["value"])
        self.assertEqual("2026-02-01T08:30", result["date"])
        self.assertTrue(any("2026-02-02" in x for x in result["issues"]))

    def test_month_filename_order_and_unknown_dates_are_not_collection_stamps(self):
        for stamp, basis in [("2026-02", "form"), ("2026-02-01", "filename"),
                             ("2026-02-01", "ordered"), ("2026-02-01", None)]:
            with self.subTest(stamp=stamp, basis=basis):
                self.point("alt").update(date=stamp, date_source=basis)
                self.assertIsNone(self.calculate()["value"])

    def test_invalid_values_censors_duplicates_and_materials_withhold(self):
        pristine = copy.deepcopy(self.data)
        for changes in [{"value": True}, {"value": 0}, {"value": -1}, {"value": math.inf},
                        {"value": math.nan}, {"value": "unknown"}, {"censored": True},
                        {"comparator": "<"}, {"source": {"specimen": "urine"}},
                        {"source": {"draw_date": "2026-02-02"}}]:
            with self.subTest(changes=changes):
                self.data = copy.deepcopy(pristine)
                self.point("ast").update(changes)
                result = self.calculate()
                self.assertEqual("invalid", result["status"])
                self.assertIsNone(result["value"])
        self.data = pristine
        self.data["markers"]["ast"]["series"].append(dict(self.point("ast")))
        self.assertEqual("invalid", self.calculate()["status"])

    def test_same_date_on_different_forms_does_not_establish_one_draw(self):
        self.point("ast")["source"] = {"path": "first.pdf", "pages": [1]}
        self.point("alt")["source"] = {"path": "second.pdf", "pages": [1]}
        self.assertEqual("invalid", self.calculate()["status"])

    def test_missing_and_incompatible_units_withhold(self):
        for unit in ["", "mg/dL", "unknown"]:
            with self.subTest(unit=unit):
                self.data["markers"]["ast"]["unit"] = unit
                self.assertEqual("invalid", self.calculate()["status"])

    def test_gateway_unit_aliases_are_accepted(self):
        self.data["markers"]["platelets"]["unit"] = "10^9/L"
        self.assertEqual(1.96, self.calculate()["value"])

    def test_missing_age_is_not_replaced_with_a_default(self):
        self.profile_data = {}
        result = self.calculate()
        self.assertIn("age", result["missing"])
        self.assertIsNone(result["value"])

    def test_invalid_birth_date_does_not_fall_back_to_year(self):
        self.profile_data = {"birth_date": "1976-02-31", "birth_year": 1976}
        self.assertEqual("invalid", self.calculate()["status"])
        for year in [True, "invalid", 2027, 0]:
            self.profile_data = {"birth_year": year}
            self.assertEqual("invalid", self.calculate()["status"])

    def test_age_limits_and_approximation_are_explicit(self):
        self.profile_data = {"birth_date": "2000-01-01"}
        self.assertEqual("not_applicable", self.calculate()["status"])
        self.profile_data = {"birth_year": 1950}
        result = self.calculate()
        self.assertEqual("computed", result["status"])
        self.assertEqual("birth_year", result["age_basis"])
        self.assertGreaterEqual(len(result["issues"]), 2)

    def test_future_draw_cannot_be_computed(self):
        for key in self.data["markers"]:
            self.point(key)["date"] = "2099-01-01"
        self.assertEqual("invalid", self.calculate()["status"])

    def test_existing_radar_entry_points_retain_the_index_and_language(self):
        result = self.calculate()
        radar = {**engine.health_radar(), "validated_indices": [result]}
        with mock.patch.object(engine, "health_radar", return_value=radar):
            text, data = ouroboros_tools._h_radar.both()
            self.assertEqual(result, data["validated_indices"][0])
            self.assertIn("FIB-4", text)
        i18n.set_lang("ru")
        self.assertNotIn("⟦", fmt.fib4_report(self.calculate()))

    def test_liver_panel_and_tool_keep_the_same_index_in_both_registers(self):
        from scholion.engine import validated
        result = self.calculate()
        with mock.patch.object(validated, "fib4", return_value=result):
            for register in ("patient", "clinician"):
                card = engine.system("liver", register)
                self.assertEqual([result], card["validated_indices"])
                with mock.patch.object(engine, "system", return_value=card):
                    text = ouroboros_tools._h_system(None, key="liver", register=register)
                self.assertIn("Liver fibrosis index (FIB-4)", text)
            self.assertEqual([], engine.system("thyroid")["validated_indices"])
        i18n.set_lang("ru")
        self.assertIn("(" + result["name"] + ")", fmt.fib4_report(result))
