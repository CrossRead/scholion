"""Synthetic reproductions of the public 0.5.11 import and genome reports.

No personal form, reference sample or clinical identifier is invented here.
A refused merged archive is not claimed to have been split successfully.
"""
from __future__ import annotations

import gzip
import json
import unittest
from pathlib import Path
from unittest import mock

from scholion import core, engine, format as fmt, genome, ingest_labs as il
from tests.test_ingest_reads_a_table import TableCase

HEADER = "Дата взятия биоматериала: 01.02.2026 08:30\n"


class TestPublicImportReports(TableCase):
    def parse(self, row):
        return il.parse_report(HEADER + row, core.lab_markers()["markers"])[1]

    def test_issue_8_a_range_cannot_start_inside_decimal_digits(self):
        for last in (1, 2, 3, 4, 9):
            row = self.parse(f"Витамин B12 412,{last} 200,0 - 1 400,0 пг/мл")["vitamin_b12"]
            self.assertEqual(412 + last / 10, row["value"])
            self.assertEqual((200, 1400), (row["ref_low"], row["ref_high"]))

    def test_issue_4_age_is_not_a_reference_value(self):
        for age, expected in ((30, (0.8, 2.7)), (56, (None, None))):
            (self.profile / "metrics.json").write_text(json.dumps({"profile": {
                "sex": "female", "birth_year": core.datetime.date.today().year - age}}), encoding='utf-8')
            core.reset_cache()
            for caption in ("Женщины (18-50 лет):", "Женщины 18-50 лет:", "Женщины 18-50:"):
                row = self.parse("Тестостерон 1,20 Женщины нмоль/л\n"
                                 "Новорожденные: 0,70 - 2,20\n"
                                 "Шкала Таннера I: 0,07 - 0,60\n" + caption + " 0,80 - 2,70")["testosterone"]
                self.assertEqual(1.2, row["value"])
                self.assertEqual(expected, (row["ref_low"], row["ref_high"]))

    def test_issue_10_a_child_reference_does_not_erase_the_result(self):
        row = self.parse("Лютеинизирующий гормон (ЛГ) 6,1 мМЕ/мл Девочки (7-8лет): <0.1\n"
                         "Девочки (1-10лет): 0,1 - 0,5\n"
                         "Женщины, фолликулярная фаза: 2,4 - 12,6")["lh"]
        self.assertEqual(6.1, row["value"])

    def test_issue_6_mixed_blood_and_stool_is_refused_not_clamped(self):
        text = HEADER + "Креатинин 80 мкмоль/л 60 - 110\nХолестерин 6,5 ммоль/л\nКопрограмма\n"
        self.assertEqual((None, {}), il.parse_report(text, core.lab_markers()["markers"]))
        self.assertEqual(80, il._stool_score("80 отсутствуют"))
        self.assertEqual(4, il._stool_score("4 отсутствуют"))

    def test_issue_7_merged_pdf_is_named_and_writes_no_false_dates(self):
        text = HEADER + "Креатинин 80 мкмоль/л\fДата взятия биоматериала: 01.06.2026\nКреатинин 90 мкмоль/л"
        self.assertEqual((None, {}), il.parse_report(text, core.lab_markers()["markers"]))
        (self.forms / "merged.pdf").write_bytes(b"SYNTHETIC")
        with mock.patch.object(il, "_ensure_extractor", return_value="synthetic"), mock.patch.object(il, "_read_any", return_value=text):
            result = self.run_ingest()
        self.assertEqual(0, result["points_added"])
        self.assertEqual("several_draw_dates", result["not_ingested"][0]["reason"])
        self.assertFalse((self.profile / "labs.json").exists())
        repeats = HEADER + "Креатинин 80 мкмоль/л\f" + HEADER.replace("08:30", "17:30") + "Креатинин 90 мкмоль/л"
        self.assertEqual((None, {}), il.parse_report(repeats, core.lab_markers()["markers"]))
        self.assertEqual(2, len(il._form_stamps(repeats)))
        self.assertEqual(1, len(il._form_stamps(HEADER + HEADER)))

    def test_issue_5_named_clinvar_files_are_not_genomes(self):
        root = Path(self.tmp.name) / "genome"
        root.mkdir()
        for name in ("sample.full.vcf.gz", "clinvar.vcf.gz", "clinvar.chr.vcf.gz", "sample.clinvar.vcf.gz"):
            with gzip.open(root / name, "wt", encoding='utf-8') as stream:
                stream.write("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC\n")
        with mock.patch.object(genome, "_search_bases", return_value=[root]):
            self.assertEqual([root / "sample.full.vcf.gz"], genome._all_vcfs())
            with gzip.open(root / "unusual-reference.vcf.gz", "wt", encoding='utf-8') as stream:
                stream.write("##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
            self.assertEqual([root / "sample.full.vcf.gz"], genome._all_vcfs())
            (root / "broken.vcf.gz").write_bytes(b"BROKEN")
            self.assertIn(root / "broken.vcf.gz", genome._all_vcfs())

    def test_issue_9_unfavourable_zone_is_not_a_normal_range(self):
        row = self.parse("Индекс свободного ПСА 14,2 % < 18 % - неблагоприятный прогноз")["psa_free_pct"]
        self.assertEqual(14.2, row["value"])
        self.assertIsNone(row["ref_high"])
        self.assertTrue(row["reference_withheld"])
        self.assertIn("неблагоприятный", row["reference_grade"])

    def test_issue_11_scales_survive_without_a_dictionary_corridor(self):
        examples = (("hdl", "Холестерин ЛПВП 1,20 ммоль/л > 1,45 - риск отсутствует\n"
                     "0,9 - 1,45 - средний риск\n< 0,9 - высокий риск", "средний риск"),
                    ("vitamin_d", "25-ОН витамин D 25,0 нг/мл\n\nдефицит < 20\n"
                     "недостаточность 20 - 30\nадекватный уровень 30 - 100\nизбыток > 100", "недостаточность"),
                    ("ana_screen", "Антитела к ядерным антигенам (ANA-screen) 0,62 < 1,0 - отрицательный; "
                     "1,0 - 1,2 - сомнительный; > 1,2 - положительный", "отрицательный"))
        for key, text, grade in examples:
            row = self.parse(text)[key]
            self.assertEqual((None, None), (row["ref_low"], row["ref_high"]))
            self.assertEqual(grade, row["reference_grade"])
            (self.forms / "scale.txt").write_text(HEADER + text, encoding="utf-8")
            self.run_ingest()
            core.reset_cache()
            found = next(r for r in engine.analyze_labs()["markers"] if r["key"] == key)
            self.assertEqual("norange", found["flag"])
            self.assertEqual(grade, found["reference_grade"])
            self.assertIn(grade, fmt.labs_report(engine.analyze_labs()))

    def test_issue_11_time_of_day_selects_its_row_and_unknown_posture_does_not(self):
        text = "Кортизол 100 нмоль/л\nДо полудня: 171 - 536\nПосле полудня: 64 - 327"
        for time, bounds in (("08:30", (171, 536)), ("17:30", (64, 327))):
            _, rows = il.parse_report(HEADER.replace("08:30", time) + text, core.lab_markers()["markers"])
            self.assertEqual(bounds, (rows["cortisol"]["ref_low"], rows["cortisol"]["ref_high"]))
        row = self.parse("Альдостерон 100 нмоль/л\nЛёжа: 30 - 150\nСтоя: 70 - 350")["aldosterone"]
        self.assertTrue(row["reference_withheld"])
        self.assertEqual(2, len(row["reference_table"]))

    def test_issue_11_a_censored_bound_is_not_a_unique_grade(self):
        row = self.parse("25-ОН витамин D < 30,0 нг/мл\nдефицит < 20\n"
                         "недостаточность 20 - 30\nадекватный уровень 30 - 100")["vitamin_d"]
        self.assertEqual('<', row['censored'])
        self.assertIsNone(row['reference_grade'])
        self.assertTrue(all(r['matches'] is None for r in row['reference_table']))
        self.assertTrue(row['reference_withheld'])

    def test_issue_10_unknown_rows_are_named_even_in_a_partly_read_file(self):
        (self.forms / "partial.txt").write_text(HEADER + "Креатинин 80 мкмоль/л 60 - 110\nUnobtainium 123,45 U/mL\n", encoding="utf-8")
        result = self.run_ingest()
        self.assertGreater(result["points_added"], 0)
        self.assertEqual("Unobtainium", result["unrecognised_rows"][0]["rows"][0]["label"])
        rendered = fmt.ingest_labs_report(result)
        self.assertIn("Unobtainium", rendered)
        self.assertNotIn("123,45", rendered)

    def test_issue_10_wrapped_b6_and_cyrillic_oh_keep_values_and_ranges(self):
        row = self.parse("Витамин В6 (пиридоксаль 40,0 нмоль/л\n20,0 - 300,0\nфосфат)")["vitamin_b6"]
        self.assertEqual((40, 20, 300), (row["value"], row["ref_low"], row["ref_high"]))
        fsh = self.parse("ФСГ\n6,1 мМЕ/мл 2,4 - 12,6")["fsh"]
        self.assertEqual((6.1, 2.4, 12.6), (fsh["value"], fsh["ref_low"], fsh["ref_high"]))
        for label in ("Т3 общий", "T3 общий", "Total Т3", "Total T3"):
            t3 = self.parse(label + " 1,8 нмоль/л 1,3 - 3,1")["t3_total"]
            self.assertEqual(1.8, t3["value"])
        for caption in ("Антитела к ФСГ", "FSH antibodies", "FSH receptor", "ФСГи"):
            self.assertNotIn('fsh', self.parse(caption + " 6,1 мМЕ/мл 2,4 - 12,6"))
        for spelling in ("ОН", "OH"):
            row = self.parse(f"17-{spelling}-прегненолон 2,5 нмоль/л 0,5 - 10,0")["pregnenolone_17oh"]
            self.assertEqual((2.5, 0.5, 10), (row["value"], row["ref_low"], row["ref_high"]))

    def test_issue_6_count_cannot_be_written_with_score_units(self):
        (self.forms / "count.txt").write_text(HEADER + "Копрограмма\nБиоматериал: кал\nЛейкоциты 80 отсутствуют\n", encoding="utf-8")
        result = self.run_ingest()
        self.assertEqual(0, result["points_added"])
        self.assertEqual("stool_count_not_a_score", result["not_ingested"][0]["reason"])


if __name__ == "__main__":
    unittest.main()
