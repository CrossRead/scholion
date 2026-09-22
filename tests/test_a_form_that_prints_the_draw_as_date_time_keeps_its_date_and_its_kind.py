"""A form that prints the draw as «Дата/время забора» keeps its date and its kind.

Task 115, the part that was left. Forms from this clinic print their dates in
two shapes nothing here read, so every one of them lost its date:

  · a laboratory form says «Дата/время забора: 07.02.2024 10:08:00» — the
    loader found the markers and dropped them all for want of a date (seven files
    and twenty-two values in the archive this was measured on);
  · a study says it in a header line — «04.10.23 14:15 ВЕЛОЭРГОМЕТРИЯ РЕЗУЛЬТАТ»,
    a two-digit year, the clock time and the kind in capitals — and, for an
    examination written up later, «Дата/время: 04.10.2023 18:30:09» under it.
    None of fifteen studies had a date; most had no kind.

The fixtures below are shaped like those forms and hold nothing of anybody's.
Three things that sit on the same forms must NOT be taken for the date: the birth
date in «Пол/Возр.», the print time in the footer, and a date inside a
recommendation.
"""
from __future__ import annotations

import unittest

import support  # noqa: F401
from scholion import core, ingest_labs, ingest_studies

LAB = ("Филиал «Клиника»\n"
       "Пол/Возр. :Мужской / 01.01.1970 (56лет) Медкарта № 1/А\n"
       "Лаб.номер :123 Дата/время забора: 07.02.2024 10:08:00\n"
       "Глюкоза 5,1 ммоль/л 4,1 - 5,9\n"
       "01.02.2026 10:00 Подпись:\n")

BODY = ("Исследование выполнено по стандартной методике. " * 6).strip()


def study(header: str, extra: str = "") -> str:
    return (f"Рег. №: 1/A Пациент № м/к: 1/A\n"
            f"Пол/Возр. :Мужской / 01.01.1970\n"
            f"{header}\n"
            f"{extra}"
            f"Описание: {BODY}\n"
            f"ЗАКЛЮЧЕНИЕ\n"
            f"Синусовый ритм, толерантность к нагрузке высокая. {BODY}\n"
            f"Повторная консультация через 2 месяца (18.09.24 г).\n"
            f"01.02.2026 10:00 Подпись:\n")


class TestTheLaboratoryForm(unittest.TestCase):

    def test_the_draw_date_and_time_are_read(self):
        date, found = ingest_labs.parse_report(LAB, core.lab_markers()["markers"], source="h.pdf")
        self.assertEqual("2024-02-07T10:08", date)
        self.assertIn("glucose", found)


class TestTheStudy(unittest.TestCase):

    def test_the_header_gives_the_date_and_the_kind(self):
        st = ingest_studies.parse_study(study("04.10.23 14:15 ВЕЛОЭРГОМЕТРИЯ РЕЗУЛЬТАТ"), "h.pdf")
        self.assertEqual("2023-10-04", st["date"])
        self.assertEqual("ВЕЛОЭРГОМЕТРИЯ", st["kind"])
        self.assertTrue(st["conclusion"])

    def test_the_examination_time_wins_over_the_writing_time(self):
        st = ingest_studies.parse_study(
            study("06.10.23 11:15 ИССЛЕДОВАНИЕ ЛУЧЕВОЙ ДИАГНОСТИКИ РЕЗУЛЬТАТ",
                  "Дата/время: 04.10.2023 18:30:09\n"), "h.pdf")
        self.assertEqual("2023-10-04", st["date"])
        self.assertEqual("ИССЛЕДОВАНИЕ ЛУЧЕВОЙ ДИАГНОСТИКИ", st["kind"])

    def test_a_header_without_the_word_result_is_still_a_header(self):
        st = ingest_studies.parse_study(study("04.10.23 13:39 ЭХО КГ"), "h.pdf")
        self.assertEqual(("2023-10-04", "ЭХО КГ"), (st["date"], st["kind"]))

    def test_neither_the_birth_date_nor_the_footer_nor_a_recommendation_is_the_date(self):
        text = study("ЭКГ")          # no header: nothing on this form may be taken
        st = ingest_studies.parse_study(text, "h.pdf")
        self.assertIsNone(st["date"])

    def test_a_year_not_yet_reached_is_not_a_date(self):
        date, kind = ingest_studies._header("01.01.99 10:00 ЭКГ РЕЗУЛЬТАТ")
        self.assertIsNone(date)
        self.assertEqual("ЭКГ", kind)

    def test_a_header_file_with_no_conclusion_is_reported_as_one(self):
        text = "Рег. №: 1/A\n02.04.24 09:24 ОСМОТР РЕЗУЛЬТАТ\n" + BODY + "\n"
        self.assertEqual(ingest_studies.REASON_NOT_EXTRACTED,
                         ingest_studies.decline_reason(text, None))


if __name__ == "__main__":
    unittest.main()
