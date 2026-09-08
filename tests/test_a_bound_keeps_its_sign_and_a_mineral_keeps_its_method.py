"""Three things an ordinary laboratory form does that the reader now survives:
a bound printed instead of a number keeps its sign, a Cyrillic «НОМА-IR» is the
same index as the Latin one, and calcium measured by two methods stays two
series.

All three were found on real forms on 08.09.2026 and repaired the same day;
what was missing was a form nobody's profile depends on. This is that form.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401
from scholion import core, ingest_labs

HEADER = "Лаборатория · метод ЖХ-МС (ответ МС)\nДата взятия образца: 03.09.2026\n"


def _parse(lines: str):
    markers = core.lab_markers()["markers"]
    _date, found = ingest_labs.parse_report(HEADER + lines, markers, source="probe.txt")
    return found


class TestABoundPrintedInsteadOfANumberKeepsItsSign(unittest.TestCase):

    def test_below_the_limit_is_not_stored_as_measured_at_the_limit(self):
        found = _parse("Эстрадиол                 < 0,09      0,07 - 0,2      нмоль/л\n")
        self.assertIn("estradiol", found, found.keys())
        self.assertEqual(0.09, found["estradiol"]["value"])
        self.assertEqual("<", found["estradiol"].get("censored"),
                         "«below 0.09» was stored as 0.09 measured — a series of such "
                         "results then reads as a level that later rose")

    def test_the_spelled_out_forms_carry_the_same_sign(self):
        for word, sign in (("менее", "<"), ("не более", "<"), ("более", ">"), ("не менее", ">"),
                           ("≤", "<"), ("≥", ">"), (">", ">")):
            with self.subTest(word=word):
                found = _parse(f"Эстрадиол                 {word} 0,09      0,07 - 0,2      нмоль/л\n")
                self.assertEqual(sign, found["estradiol"].get("censored"), word)

    def test_a_bound_in_the_reference_column_is_not_taken_for_the_value(self):
        found = _parse("Эстрадиол                 0,13        < 0,2           нмоль/л\n")
        self.assertEqual(0.13, found["estradiol"]["value"])
        self.assertIsNone(found["estradiol"].get("censored"),
                          "the «<» belongs to the reference column further along the row")


class TestTheIndexIsTheSameInBothAlphabets(unittest.TestCase):

    def test_cyrillic_homa_is_read(self):
        found = _parse("Индекс инсулинорезистентности НОМА-IR   1,8   < 2,7\n")
        self.assertIn("homa_ir", found)
        self.assertEqual(1.8, found["homa_ir"]["value"])


class TestAMineralMeasuredByTwoMethodsStaysTwoSeries(unittest.TestCase):

    def test_biochemical_total_calcium_and_elemental_calcium_are_two_markers(self):
        found = _parse("Кальций общий      2,26     2,15 - 2,50     ммоль/л\n"
                       "Кальций (Ca)       102,8    86 - 104        мг/л\n")
        self.assertEqual(2.26, found["calcium_total"]["value"])
        self.assertEqual(102.8, found["calcium_blood"]["value"],
                         "a unit conversion between two methods presented a change of "
                         "method as a trend")

    def test_a_biochemistry_form_does_not_feed_the_elemental_series(self):
        found = _parse("Биохимия крови\nКальций общий      2,26     2,15 - 2,50     ммоль/л\n")
        self.assertIn("calcium_total", found)
        self.assertNotIn("calcium_blood", found)


if __name__ == "__main__":
    unittest.main()
