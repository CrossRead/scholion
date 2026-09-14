"""A series belongs to a method, not to a substance.

Calcium was split by hand on 08.09.2026: the ICP row in mg/L and the
biochemistry row in mmol/L became two keys, because the two methods disagree
by more than ten per cent on the same sample and one series would have shown a
change of method as a trend. The class was wider than calcium. Magnesium's ICP
row still multiplied a biochemistry 0.90 mmol/L by 24.305 and stored 21.87 mg/L
next to 19.3 and 18.4; copper had one key for both methods; iron had two keys
and no unit gate on the ICP one, so a molar row that carried the symbol was
stored as if it were µg/L — not converted, simply misread.

Two guarantees here. First, the rule is declared in the dictionary and read by
`src/tools/check_method_mixing.py`, and this file proves the tool bites: a
molar unit put back on an ICP series, a gate removed, a declaration dropped —
each is refused. Second, the forms: magnesium in both shapes a Russian
laboratory prints, each landing in its own key and neither feeding the other.
"""
from __future__ import annotations

import copy
import io
import sys
import unittest
from unittest import mock

import support  # noqa: F401
from scholion import core, ingest_labs

sys.path.insert(0, str(support.ROOT / "src" / "tools"))
import check_method_mixing as cmm  # noqa: E402

HEADER = "Лаборатория · метод ЖХ-МС (ответ МС)\nДата взятия образца: 03.09.2026\n"


def _problems(markers, units):
    return {r["key"]: r["problems"] for r in cmm.inventory(markers, units) if r["problems"]}


class TestNoElementMixesMethods(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.markers, cls.units = cmm.load()

    def test_the_dictionary_declares_every_split_and_mixes_nothing(self):
        bad = _problems(self.markers, self.units)
        self.assertEqual(bad, {}, "a series mixes methods: " + "; ".join(
            f"{k}: {', '.join(v)}" for k, v in bad.items()))

    def test_every_two_method_element_holds_both_methods(self):
        for analyte in cmm.TWO_METHOD:
            with self.subTest(element=analyte):
                methods = {spec.get("method") for key, spec in self.markers.items()
                           if cmm.analyte_of(key) == analyte}
                self.assertEqual({"icp", "biochemistry"}, methods)

    def test_the_icp_series_of_every_two_method_element_takes_no_molar_unit(self):
        table = cmm.spelling_table(self.units)
        for key, spec in self.markers.items():
            if cmm.analyte_of(key) in cmm.TWO_METHOD and spec.get("method") == "icp":
                with self.subTest(marker=key):
                    molar = [s for _f, s in cmm.spellings(spec) if cmm.family(s, table) == "molar"]
                    self.assertEqual([], molar, f"{key} would convert a biochemistry number "
                                     "into an ICP point")
                    self.assertTrue(spec.get("units"), f"{key} has no unit gate")

    # ── the tool bites: each of these is the dictionary as it was, put back ──

    def test_a_molar_unit_put_back_on_the_icp_magnesium_series_is_refused(self):
        m = copy.deepcopy(self.markers)
        m["magnesium_blood"]["units"]["mmol/L"] = 24.305
        self.assertIn("magnesium_blood", _problems(m, self.units),
                      "the entry that turned 0.90 mmol/L into 21.87 mg/L passed the guard")

    def test_an_icp_series_without_a_unit_gate_is_refused(self):
        m = copy.deepcopy(self.markers)
        del m["iron_blood"]["units"]
        self.assertIn("iron_blood", _problems(m, self.units),
                      "an ICP row with no gate stores a molar number as mass")

    def test_one_key_taking_both_methods_with_no_declaration_is_refused(self):
        m = copy.deepcopy(self.markers)
        del m["copper"]["method"]
        m["copper"]["units"]["umol/L"] = 63.546
        del m["copper_total"]
        self.assertIn("copper", _problems(m, self.units), "copper as it was until 12.09.2026")

    def test_a_biochemistry_series_not_gated_off_elemental_forms_is_refused(self):
        m = copy.deepcopy(self.markers)
        del m["copper_total"]["labels"]["ru"]["form_exclude"]
        self.assertIn("copper_total", _problems(m, self.units))

    def test_a_split_with_one_side_missing_is_refused(self):
        m = copy.deepcopy(self.markers)
        del m["zinc_total"]
        self.assertIn("zinc", _problems(m, self.units), "half a split is no split")

    def test_a_method_outside_the_vocabulary_is_refused(self):
        m = copy.deepcopy(self.markers)
        m["selenium"]["method"] = "spectrometry"
        self.assertIn("selenium", _problems(m, self.units))

    def test_selenium_keeps_both_units_because_it_has_one_method(self):
        """The one element allowed a molar unit beside a mass one — declared, not inferred."""
        self.assertEqual("icp", self.markers["selenium"].get("method"))
        self.assertIn("selenium", cmm.ONE_METHOD)
        rows = {r["key"]: r for r in cmm.inventory(self.markers, self.units)}
        self.assertEqual(["mass", "molar"], rows["selenium"]["families"])
        self.assertEqual([], rows["selenium"]["problems"])

    def test_the_tool_exits_nonzero_on_a_mix(self):
        m = copy.deepcopy(self.markers)
        m["calcium_blood"]["units"]["mmol/L"] = 40.08
        with mock.patch.object(cmm, "load", lambda: (m, self.units)), \
             mock.patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(1, cmm.main([]))
        with mock.patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(0, cmm.main([]))


class TestMagnesiumInBothShapesLandsInItsOwnSeries(unittest.TestCase):

    def parse(self, lines: str):
        markers = core.lab_markers()["markers"]
        _date, found = ingest_labs.parse_report(HEADER + lines, markers, source="probe.txt")
        return {k: v["value"] for k, v in found.items()}

    def test_biochemistry_magnesium_in_mmol_per_litre_is_the_biochemistry_series(self):
        found = self.parse("Магний             0,90     0,66 - 1,07     ммоль/л\n")
        self.assertEqual(0.9, found.get("magnesium_total"))
        self.assertNotIn("magnesium_blood", found)

    def test_icp_magnesium_in_mg_per_litre_is_the_elemental_series(self):
        found = self.parse("Магний (Mg)        21,9     17 - 29         мг/л\n")
        self.assertEqual(21.9, found.get("magnesium_blood"))
        self.assertNotIn("magnesium_total", found)

    def test_both_on_one_form_stay_two_series(self):
        found = self.parse("Магний             0,90     0,66 - 1,07     ммоль/л\n"
                           "Магний (Mg)        21,9     17 - 29         мг/л\n")
        self.assertEqual(0.9, found["magnesium_total"])
        self.assertEqual(21.9, found["magnesium_blood"])

    def test_the_shape_that_was_misfiled_never_reaches_the_icp_series(self):
        """«Магний (Mg) 0,90 ммоль/л» — the symbol on a biochemistry form.

        Until 12.09.2026 this became 21.87 mg/L in the ICP series. Today the
        parser hands the row to the longest matching name, the ICP key, whose
        gate refuses it: dropped, not misfiled. If it lands anywhere, the only
        right place is the biochemistry series — asserted so that a parser that
        falls through on a refused unit passes here without an edit.
        """
        found = self.parse("Магний (Mg)        0,90     0,66 - 1,07     ммоль/л\n")
        self.assertNotIn("magnesium_blood", found,
                         "a biochemistry mmol/L value was converted into the ICP series")
        self.assertEqual(found.get("magnesium_total", 0.9), 0.9)

    def test_copper_and_iron_follow_the_same_rule(self):
        found = self.parse("Медь               15,2     11,0 - 22,0     мкмоль/л\n"
                           "Медь (Cu)          966      700 - 1400      мкг/л\n"
                           "Сывороточное железо 15,2    5,83 - 34,5     мкмоль/л\n"
                           "Железо (Fe)        450      560 - 2500      мкг/л\n")
        self.assertEqual(15.2, found["copper_total"])
        self.assertEqual(966.0, found["copper"])
        self.assertEqual(15.2, found["iron"])
        self.assertEqual(450.0, found["iron_blood"])

    def test_a_molar_iron_row_with_the_symbol_is_not_stored_as_micrograms(self):
        found = self.parse("Железо (Fe)        15,2     5,83 - 34,5     мкмоль/л\n")
        self.assertNotIn("iron_blood", found, "15.2 µmol/L was stored as 15.2 µg/L")

    def test_a_biochemistry_form_feeds_no_elemental_series(self):
        found = self.parse("Биохимия крови\n"
                           "Медь (Cu)          966      700 - 1400      мкг/л\n"
                           "Железо (Fe)        450      560 - 2500      мкг/л\n"
                           "Магний (Mg)        21,9     17 - 29         мг/л\n")
        self.assertEqual({}, {k: v for k, v in found.items()
                              if k in ("copper", "iron_blood", "magnesium_blood")})

    def test_an_elemental_form_feeds_no_biochemistry_series(self):
        found = self.parse("Ответ ИСП\n"
                           "Медь               15,2     11,0 - 22,0     мкмоль/л\n"
                           "Магний             0,90     0,66 - 1,07     ммоль/л\n"
                           "Цинк               12,5     7,0 - 23,0      мкмоль/л\n")
        self.assertEqual({}, {k: v for k, v in found.items()
                              if k in ("copper_total", "magnesium_total", "zinc_total")})



class TestAFormRuleDoesNotHideInsideAnOrdinaryWord(unittest.TestCase):
    """«Исполнитель: ООО "ДНКОМ"» stands in the header of every form this
    laboratory prints, and for four markers it was a rule.

    `form_exclude` held «исп» — meaning the elemental forms, «Ответ ИСП-МС» —
    and a form rule is matched as a SUBSTRING over the form's text plus its file
    name. So on every form of that laboratory the four biochemistry keys
    excluded themselves, while the elemental twins do not answer to the printed
    names («Кальций общий», «Магний», «Цинк»): three printed lines per form
    reached no series at all, and nothing failed. Two draws of 2023 sit in the
    owner's profile with their uric acid and phosphorus and without their
    calcium, magnesium and zinc — found on 14.09.2026 by reading the forms.

    The matcher is left as it is: a rule such as «макро- и микроэлемент» is a
    prefix of what the form prints, so a word boundary would break eight
    elemental keys to fix one. The rule is fixed instead, and the shape is held
    by the hygiene check below.
    """

    #: the header of that laboratory, cut to what decides the outcome
    DNKOM = ('Заказчик: Общество с ограниченной ответственностью «Медгород»\n'
             'Исполнитель: ООО "ДНКОМ"\n'
             'Биоматериал: Кровь (сыворотка);\n'
             'Взятие биоматериала: 28.02.2023 08:37\n'
             'Биохимический анализ крови\n')

    THREE_LINES = ("Кальций общий 2,31 ммоль/л 2,20 - 2,65\n"
                   "Магний 0,78 ммоль/л 0,73 - 1,06\n"
                   "Цинк 11,1 мкмоль/л 10,7 - 18,4\n")

    def parse(self, lines: str):
        markers = core.lab_markers()["markers"]
        _date, found = ingest_labs.parse_report(
            self.DNKOM + lines, markers,
            source="ПАЦИЕНТ - 3302192728 (Биохимический анализ крови).pdf")
        return found

    def test_the_three_printed_lines_reach_their_own_series(self):
        found = self.parse(self.THREE_LINES)
        self.assertEqual(2.31, found.get("calcium_total", {}).get("value"),
                         "total calcium printed on the form reached no series")
        self.assertEqual(0.78, found.get("magnesium_total", {}).get("value"))
        self.assertEqual(11.1, found.get("zinc_total", {}).get("value"))

    def test_the_elemental_twins_take_nothing_from_this_form(self):
        found = self.parse(self.THREE_LINES)
        self.assertEqual({}, {k: v["value"] for k, v in found.items()
                              if k in ("calcium_blood", "magnesium_blood", "zinc")},
                         "a biochemistry row was converted into the elemental series")

    def test_an_elemental_form_of_the_same_laboratory_still_feeds_no_biochemistry_series(self):
        """The rule it replaced has to keep doing its work: the two spellings of
        that form are «Ответ ИСП-МС» in the file name and «ИСП-МС» in the body."""
        markers = core.lab_markers()["markers"]
        for source, body in (("ПАЦИЕНТ - 6140857643 (Ответ ИСП-МС).pdf", "Диагностика микроэлементозов\n"),
                             ("probe.pdf", "Диагностика микроэлементозов (ИСП-МС)\n")):
            with self.subTest(form=source):
                _d, found = ingest_labs.parse_report(
                    "Дата взятия биоматериала: 16.02.2019\n" + body +
                    "Кальций общий 2,31 ммоль/л\nМагний 0,78 ммоль/л\nЦинк 11,1 мкмоль/л\n",
                    markers, source=source)
                self.assertEqual({}, {k: v["value"] for k, v in found.items()
                                      if k in ("calcium_total", "magnesium_total", "zinc_total")})

    def test_no_form_rule_can_hide_inside_an_ordinary_word(self):
        """The shape of the defect, not its instance: a rule of three letters
        matched a word no one was thinking about. A rule that carries a space or
        a hyphen («ответ исп», «исп-мс», «гх-мс») cannot; neither can one long
        enough that containment in a common word is not an accident. Seven is
        where the rules of this dictionary actually stand: «скрытую» passes,
        «биохимия» passes, «исп» does not.
        """
        #: a rule shorter than that, and without a separator, is accepted only by
        #: name and with the reason it is safe.
        accepted = {
            "lcms": "the separator-less spelling of LC-MS/MS beside «lc-ms» and «lc-ms/ms»; "
                    "four Latin letters in a corpus of Russian forms, and no word of either "
                    "language a laboratory prints contains them",
        }
        offenders = []
        for key, spec in core.lab_markers()["markers"].items():
            for lang, lab in (spec.get("labels") or {}).items():
                if not isinstance(lab, dict):
                    continue
                for field in ("form_require", "form_exclude"):
                    for rule in lab.get(field) or []:
                        if " " in rule or "-" in rule or len(rule) >= 7:
                            continue
                        if rule.lower() in accepted:
                            continue
                        offenders.append(f"{key}.{lang}.{field}: {rule!r}")
        self.assertEqual(offenders, [],
                         "a form rule this short is matched as a substring of the whole form and "
                         "its file name, so it can fire on an ordinary word in the header — give "
                         "it a space or a hyphen, or spell it out")


class TestTypedInputObeysTheSameRule(unittest.TestCase):
    """The web form and the CLI convert through `core.convert_to_canonical`."""

    def setUp(self):
        self.m = core.lab_markers()["markers"]

    def test_a_molar_value_typed_into_the_icp_magnesium_series_is_refused(self):
        res = core.convert_to_canonical(self.m["magnesium_blood"], "mmol/L", 0.9)
        self.assertFalse(res["ok"], "0.9 mmol/L became an ICP point by arithmetic")
        self.assertIn("mg/L", res["accepted"])

    def test_the_same_value_typed_into_the_biochemistry_series_is_taken_as_is(self):
        res = core.convert_to_canonical(self.m["magnesium_total"], "mmol/L", 0.9)
        self.assertTrue(res["ok"])
        self.assertEqual(0.9, res["value"])

    def test_equivalents_belong_to_the_biochemistry_series_and_halve_for_a_divalent_ion(self):
        self.assertFalse(core.convert_to_canonical(self.m["calcium_blood"], "mEq/L", 4.6)["ok"])
        self.assertEqual(2.3, core.convert_to_canonical(self.m["calcium_total"], "mEq/L", 4.6)["value"])


if __name__ == "__main__":
    unittest.main()
