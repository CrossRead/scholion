"""An archive's dates, pages and material remain distinct through an atomic import."""
from __future__ import annotations

import json
from unittest import mock

from scholion import core, lab_archive, ingest_labs, format as fmt, store
from tests.test_ingest_reads_a_table import TableCase


def synthetic_pdf(pages):
    """An actual paginated ASCII PDF, generated without a test dependency."""
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    children = []
    for lines in pages:
        number = len(objects) + 1
        children.append(f"{number} 0 R")
        commands = ["BT /F1 12 Tf 50 740 Td"]
        for line in lines:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj 0 -18 Td")
        stream = ("\n".join(commands) + "\nET").encode("ascii")
        objects.extend([
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
             f"/Resources << /Font << /F1 3 0 R >> >> /Contents {number + 1} 0 R >>").encode(),
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"])
    objects[1] = (f"<< /Type /Pages /Kids [{' '.join(children)}] /Count {len(pages)} >>").encode()
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend((f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
                   f"startxref\n{start}\n%%EOF\n").encode())
    return bytes(result)


def form(day="01.02.2026", clock="08:30", value=80, material="кровь", extra=""):
    return (f"Дата взятия биоматериала: {day} {clock}\nБиоматериал: {material}\n"
            f"{extra}Креатинин {value} мкмоль/л 60 - 110\n")


class TestReviewedArchive(TableCase):
    def setUp(self):
        super().setUp()
        self.pdf = self.forms / "synthetic-archive.pdf"
        self.pdf.write_bytes(b"SYNTHETIC PDF extraction fixture")

    def preview(self, text, token=""):
        with mock.patch.object(ingest_labs, "_ensure_extractor", return_value="synthetic"), \
                mock.patch.object(ingest_labs, "_read_any", return_value=text):
            return lab_archive.run(str(self.forms), token)

    def labs(self):
        return json.loads((self.profile / "labs.json").read_text(encoding="utf-8"))["markers"]

    def test_preview_writes_nothing_and_each_draw_keeps_its_source_pages(self):
        text = form() + "\f" + form("01.06.2026", value=90)
        before = {p.name: p.read_bytes() for p in self.profile.iterdir()}
        result = self.preview(text)
        self.assertEqual("preview", result["status"])
        self.assertEqual(2, len(result["forms"]))
        self.assertNotIn("_payload", result)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.profile.iterdir()})
        self.assertIn('80.0', fmt.ingest_labs_report(result))
        applied = self.preview(text, result["approval_token"])
        self.assertTrue(applied["ok"], applied)
        self.assertEqual(1, applied["files_processed"])
        points = self.labs()["creatinine"]["series"]
        self.assertEqual(["2026-02-01T08:30", "2026-06-01T08:30"], [p["date"] for p in points])
        self.assertEqual([[1], [2]], [p["source"]["pages"] for p in points])
        self.assertTrue(all(p["date_source"] == "form" for p in points))
        self.assertTrue(all(p["source"]["path"] == str(self.pdf.resolve()) for p in points))
        self.assertTrue(all(p["source"]["specimen"] == "blood" for p in points))

    def test_two_times_in_one_day_remain_two_observations_on_repeat_import(self):
        text = form() + "\f" + form(clock="17:30", value=90)
        for _ in range(2):
            token = self.preview(text)["approval_token"]
            self.assertTrue(self.preview(text, token)["ok"])
        self.assertEqual([80, 90], [p["value"] for p in self.labs()["creatinine"]["series"]])

    def test_a_changed_source_or_changed_profile_invalidates_the_token(self):
        text = form()
        token = self.preview(text)["approval_token"]
        self.pdf.write_bytes(b"CHANGED synthetic source")
        self.assertFalse(self.preview(text, token)["ok"])
        self.assertFalse((self.profile / "labs.json").exists())
        token = self.preview(text)["approval_token"]
        (self.profile / "labs.json").write_text('{"markers":{}}', encoding="utf-8")
        self.assertFalse(self.preview(text, token)["ok"])
        self.assertEqual('{"markers":{}}', (self.profile / "labs.json").read_text(encoding="utf-8"))

    def test_a_date_without_an_explicit_material_is_not_guessed(self):
        result = self.preview(form().replace("Биоматериал: кровь\n", ""))
        self.assertEqual("refused", result["status"])
        self.assertIsNone(result["approval_token"])
        self.assertFalse((self.profile / "labs.json").exists())

    def test_one_ambiguous_page_prevents_any_write_from_the_archive(self):
        result = self.preview(form() + "\fКреатинин 90 мкмоль/л\n")
        self.assertIsNone(result["approval_token"])
        self.assertFalse(self.preview(form(), "not-a-reviewed-token")["ok"])
        self.assertFalse((self.profile / "labs.json").exists())

    def test_a_continuation_requires_order_and_consecutive_page_numbers(self):
        first = form(extra="Заказ: SYNTHETIC\nСтраница 1 из 2\n")
        second = "Заказ: SYNTHETIC\nСтраница 2 из 2\nГлюкоза 5,1 ммоль/л\n"
        plan = self.preview(first + "\f" + second)
        self.assertEqual([1, 2], plan["forms"][0]["pages"])
        self.assertIn("glucose", plan["forms"][0]["markers"])
        self.assertTrue(self.preview(first + "\f" + second, plan["approval_token"])["ok"])
        for invalid in (second.replace('SYNTHETIC', 'OTHER'), second.replace('2 из 2', '3 из 3')):
            self.assertIsNone(self.preview(first + "\f" + invalid)["approval_token"])

    def test_an_incomplete_form_cannot_be_followed_by_an_unrelated_form(self):
        first = form(extra="Заказ: SYNTHETIC\nСтраница 1 из 2\n")
        self.assertIsNone(self.preview(first + "\f" + form("02.02.2026"))["approval_token"])
        self.assertIsNone(self.preview(first)["approval_token"])

    def test_different_materials_are_distinct_forms_and_cannot_leak_into_blood(self):
        text = form() + "\f" + form("02.02.2026", material="моча")
        result = self.preview(text)
        # A urine creatinine cannot supply a serum result even when the spelling matches.
        self.assertIsNone(result["approval_token"])
        self.assertFalse((self.profile / "labs.json").exists())
        bad = form(extra="Заказ: SYNTHETIC\nСтраница 1 из 2\n") + "\f" + (
            "Заказ: SYNTHETIC\nСтраница 2 из 2\nБиоматериал: моча\nГлюкоза 5,1 ммоль/л")
        self.assertIsNone(self.preview(bad)["approval_token"])

    def test_conflicting_values_for_one_stamp_do_not_replace_each_other(self):
        self.assertIsNone(self.preview(form() + "\f" + form(value=90))["approval_token"])
        self.assertFalse((self.profile / "labs.json").exists())

    def test_an_invalid_point_refuses_the_whole_batch_without_partial_writes(self):
        rows = [dict(key="creatinine", date="2026-02-01", value=80, unit="µmol/L", ref_low=None, ref_high=None),
                dict(key="creatinine", date="not-a-date", value=90, unit="µmol/L", ref_low=None, ref_high=None)]
        result = store.add_lab_batch(rows, from_forms=True)
        self.assertFalse(result["ok"])
        self.assertFalse((self.profile / "labs.json").exists())

    def test_the_original_single_form_api_still_refuses_a_merged_archive(self):
        text = form() + "\f" + form("01.06.2026", value=90)
        self.assertEqual((None, {}), ingest_labs.parse_report(text, core.lab_markers()["markers"]))

    def test_two_forms_on_one_page_are_not_silently_collapsed(self):
        self.assertIsNone(self.preview(form() + form(value=90))["approval_token"])
        two_orders = form(extra="Заказ: SYNTHETIC\nЗаказ: OTHER\n")
        self.assertIsNone(self.preview(two_orders)["approval_token"])

    def test_iso_english_collection_times_are_not_erased(self):
        text = "Collected: 2026-02-01 17:30\nSpecimen: blood\nCreatinine 80 µmol/L\n"
        result = self.preview(text)
        self.assertEqual("2026-02-01T17:30", result["forms"][0]["date"])
        self.assertTrue(self.preview(text, result["approval_token"])["ok"])
        self.assertEqual("2026-02-01T17:30", self.labs()["creatinine"]["series"][0]["date"])

    def test_real_pdf_extraction_preserves_two_page_boundaries_and_draws(self):
        if not ingest_labs._have_extractor():
            self.skipTest("A PDF reader is not installed in this interpreter")
        self.pdf.write_bytes(synthetic_pdf([
            ["Collected: 2026-02-01 08:30", "Specimen: blood", "Glucose 5.1 mmol/L"],
            ["Collected: 2026-06-01 17:30", "Specimen: blood", "Glucose 5.3 mmol/L"]]))
        plan = lab_archive.run(str(self.forms))
        self.assertEqual("preview", plan.get("status"), plan)
        self.assertEqual([[1], [2]], [f["pages"] for f in plan["forms"]])
        self.assertTrue(lab_archive.run(str(self.forms), plan["approval_token"])["ok"])
        self.assertEqual(["2026-02-01T08:30", "2026-06-01T17:30"],
                         [p["date"] for p in self.labs()["glucose"]["series"]])

    def test_contradictory_material_or_invalid_pagination_is_refused(self):
        for text in (form(material="blood urine"), form(extra="Page 0 of 2\n"),
                     form(extra="Page 2 of 1\n")):
            self.assertIsNone(self.preview(text)["approval_token"])
