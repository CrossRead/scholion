"""A result row is read whole: its number, its unit, its corridor — or not at all.

Seven ways an ordinary form row used to become a different number, each found
by the 0.5.7 review and each reproduced here on an invented row before it was
repaired. None of them failed loudly; every one stored a plausible value.

* a flag or a unit glued to the number cut the decimals off (6.5 became 6.0);
* a space as the thousands mark cut the number at the space (1250 became 1);
* a digit of the analyte's own name was taken for its result;
* a longer analyte that contains a shorter one's name was stored as the shorter;
* a marker with no `units` map took its number as written whatever the unit
  («95 mg/dL» of glucose became 95 mmol/L);
* a one-sided corridor printed on the result row («до 5,2») was never read;
* a corridor the form did not print was copied in from the dictionary and then
  judged as if the form had printed it.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401
from scholion import core, ingest_labs

HEADER = "Laboratory\nДата взятия образца: 03.09.2026\n"


def _parse(row: str):
    markers = core.lab_markers()["markers"]
    return ingest_labs.parse_report(HEADER + row + "\n", markers, source="probe.txt")[1]


class TestTheNumberIsTakenWhole(unittest.TestCase):

    def test_a_flag_glued_to_the_result_keeps_the_decimals(self):
        found = _parse("Глюкоза    6,5H    3,9 - 6,1   ммоль/л")
        self.assertEqual(6.5, found["glucose"]["value"])

    def test_a_unit_glued_to_the_result_keeps_the_decimals(self):
        found = _parse("Глюкоза    6,5ммоль/л    3,9 - 6,1")
        self.assertEqual(6.5, found["glucose"]["value"])

    def test_a_thousands_space_in_the_result_is_read_against_the_row_corridor(self):
        found = _parse("Ферритин   1 250,0   нг/мл   20 - 250")
        self.assertEqual(1250.0, found["ferritin"]["value"])

    def test_the_small_reading_wins_when_it_is_the_one_near_the_corridor(self):
        found = _parse("Нейтрофилы, абс.   3 450   10^9/л   1,8 - 6,6")
        self.assertEqual(3.0, found["neut_abs"]["value"])

    def test_an_ordinary_three_digit_result_is_unchanged(self):
        found = _parse("Ферритин   120   нг/мл   20 - 250")
        self.assertEqual(120.0, found["ferritin"]["value"])

    def test_a_digit_of_the_name_is_not_the_result(self):
        found = _parse("Инсулиноподобный фактор роста-1 (ИФР-1)  180  нг/мл  100 - 300")
        self.assertEqual(180.0, found["igf1"]["value"])
        found = _parse("Витамин B6 (пиридоксаль-5-фосфат)  42  нмоль/л  20 - 300")
        self.assertEqual(42.0, found["vitamin_b6"]["value"])


class TestALongerAnalyteIsNotTheShorterOne(unittest.TestCase):

    def test_prefixed_names_are_not_their_stem(self):
        for row, wrong in (("Преальбумин   0,25   г/л   0,2 - 0,4", "albumin"),
                           ("Микроальбумин   12   мг/л   < 30", "albumin"),
                           ("Макропролактин  40  %  < 40", "prolactin"),
                           ("Холестерин не-ЛПВП   4,1   ммоль/л  < 3,4", "hdl"),
                           ("Латентная железосвязывающая способность  40  мкмоль/л  20 - 62",
                            "tibc"),
                           ("Фолиевая кислота в эритроцитах  800  нг/мл  280 - 900", "folate")):
            with self.subTest(row=row):
                self.assertNotIn(wrong, _parse(row))

    def test_the_stem_itself_is_still_read(self):
        self.assertEqual(1.4, _parse("Холестерин ЛПВП  1,4  ммоль/л  > 1,0")["hdl"]["value"])
        self.assertEqual(42.0, _parse("Альбумин  42  г/л  35 - 52")["albumin"]["value"])


class TestTheUnitOnTheRowIsHonoured(unittest.TestCase):

    def test_a_factor_unit_converts_the_value_and_the_corridor(self):
        g = _parse("Glucose  95  mg/dL  70 - 99")["glucose"]
        self.assertAlmostEqual(5.27, g["value"], places=2)
        self.assertAlmostEqual(3.89, g["ref_low"], places=2)
        self.assertAlmostEqual(5.50, g["ref_high"], places=2)

    def test_a_formula_unit_goes_through_the_formula(self):
        h = _parse("HbA1c  48  mmol/mol  < 42")["hba1c"]
        self.assertAlmostEqual(6.54, h["value"], places=2)
        self.assertAlmostEqual(5.99, h["ref_high"], places=2)

    def test_a_unit_the_marker_refuses_leaves_the_row_unread(self):
        self.assertNotIn("lpa", _parse("Lp(a)  30  mg/dL  < 30"))

    def test_the_canonical_unit_leaves_the_number_as_written(self):
        self.assertEqual(5.4, _parse("Glucose  5.4  mmol/L  3.9 - 6.1")["glucose"]["value"])


class TestAOneSidedCorridorOnTheRowIsRead(unittest.TestCase):

    def test_upper_and_lower(self):
        c = _parse("Холестерин общий   5,6   ммоль/л   < 5,2")["cholesterol_total"]
        self.assertEqual((None, 5.2), (c["ref_low"], c["ref_high"]))
        c = _parse("Холестерин общий   5,6   ммоль/л   до 5,2")["cholesterol_total"]
        self.assertEqual((None, 5.2), (c["ref_low"], c["ref_high"]))
        h = _parse("Холестерин ЛПВП  1,4  ммоль/л  > 1,0")["hdl"]
        self.assertEqual((1.0, None), (h["ref_low"], h["ref_high"]))


class TestTheDictionaryCorridorIsNotCopiedIntoThePoint(unittest.TestCase):

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        (self.root / "forms").mkdir()
        (self.root / "profile").mkdir()
        self._restore = support.pin_profile(self.root / "profile")
        self._restore_cache = support.pin_cache(self.root / "cache")
        core.reset_cache()

    def tearDown(self):
        self._restore()
        self._restore_cache()
        core.reset_cache()
        self.tmp.cleanup()

    def test_a_point_keeps_only_the_corridor_its_form_printed(self):
        import json
        (self.root / "forms" / "a.txt").write_text(
            "Laboratory\nДата взятия биоматериала: 14.03.2024 08:20\n"
            "Глюкоза  5,4  ммоль/л\n", encoding="utf-8")
        out = ingest_labs.ingest(str(self.root / "forms"), force=True)
        self.assertEqual(1, out["points_added"], out)
        labs = json.loads((self.root / "profile" / "labs.json").read_text(encoding="utf-8"))
        point = labs["markers"]["glucose"]["series"][0]
        # The form printed no range; the point must not claim one. The reference
        # base is lent later, labelled, by the corridor module and its checks.
        self.assertIsNone(point.get("ref_low"))
        self.assertIsNone(point.get("ref_high"))


if __name__ == "__main__":
    unittest.main()
