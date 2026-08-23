"""A body measurement in a bundle is the person's own, and it is not a lab result.

Task 98, third part. Importing a FHIR bundle dropped every vital sign it held:
height, weight, body mass index, temperature, heart rate, respiratory rate,
oxygen saturation — twenty-three unplaced observations, ten of which were never
analytes. Naming them «a code this build does not know» was the first repair and
only half of one: this product HAS a metrics layer, accepts a weight from the
command line and from the page, and needs those numbers — dropping them because
they arrived in a bundle was a hole, not a policy.

So a body measurement is written where one of our metrics holds the same
quantity, and refused with its reason where none does. Three rules hold it:

  * `ours` names the metric, and only where the two are the same quantity — a
    heart rate at a visit is not the resting home pulse, and a percentile of the
    body mass index against an age-and-sex reference is not the index itself;
  * `unit` is the ONE unit accepted, because nothing here converts: a weight in
    pounds joining a series in kilograms is the silence this project spends its
    time removing;
  * and the table is data, so the next code is added by whoever meets it —
    with the sentence that says where the value belongs.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys
import tempfile
import unittest

import support

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholion import core, ingest_fhir  # noqa: E402

BUNDLE = ROOT / "tests" / "fixtures" / "fhir" / "synthea_patient_clinical.json"


def _table() -> dict:
    return {k: v for k, v in (core.lab_test_meta().get("body_metrics") or {}).items()
            if isinstance(v, dict)}


class TestTheTableSaysWhereEachValueBelongs(unittest.TestCase):

    def test_every_code_is_explained(self):
        table = _table()
        self.assertTrue(table, "the table is empty — nothing is guarded")
        for code, entry in table.items():
            with self.subTest(code=code):
                self.assertTrue(entry.get("name"), "no name — the code alone cannot be checked")
                why = entry.get("why") or ""
                self.assertGreater(len(why.split()), 4,
                                   "say what the value is, so a refusal is an answer and not a shrug")
                if entry.get("ours"):
                    self.assertTrue(entry.get("unit"),
                                    "a metric that can be written must name the one unit it accepts")

    def test_a_code_is_not_both_an_analyte_and_a_body_measurement(self):
        clash = sorted(set(_table()) & set(core.loinc_index()))
        self.assertEqual([], clash,
                         "a code cannot be a laboratory analyte and a body measurement at once")


class TestTheBundleIsReadIntoTwoLayers(unittest.TestCase):

    def setUp(self):
        if not BUNDLE.exists():                              # pragma: no cover
            self.skipTest("no FHIR fixture in this tree")

    def test_the_weight_is_planned_as_a_metric_and_not_as_a_lab_point(self):
        plan = ingest_fhir.plan(BUNDLE)
        metrics = plan.get("metrics") or []
        self.assertTrue(metrics, "the bundle's body measurements were not planned at all")
        self.assertEqual({"weight"}, {m["metric"] for m in metrics})
        self.assertEqual({"kg"}, {m["unit"] for m in metrics})
        self.assertNotIn("weight", {p["key"] for p in plan["points"]},
                         "a body measurement was planned as a laboratory point")

    def test_what_no_metric_holds_is_refused_by_name(self):
        plan = ingest_fhir.plan(BUNDLE)
        said = [s for s in plan["skipped"] if s["reason"] == "loinc_is_a_body_metric"]
        self.assertTrue(said)
        for s in said:
            self.assertIsNone(s.get("ours"), "this one has a metric and should have been written")
            self.assertTrue(s.get("detail"), "the code is what somebody has to look up")

    def test_the_import_writes_it_into_the_metrics_file(self):
        d = pathlib.Path(tempfile.mkdtemp(prefix="fhir_metric_"))
        self.addCleanup(shutil.rmtree, d, True)
        code, out, err = support.run(["init", "--dir", str(d / "p")])
        self.assertEqual(0, code, err)
        code, out, err = support.run(["import-fhir", str(BUNDLE)], profile_dir=d / "p")
        self.assertEqual(0, code, err)
        data = json.loads((d / "p" / "metrics.json").read_text(encoding="utf-8"))
        series = ((data.get("metrics") or {}).get("weight") or {}).get("series") or []
        self.assertTrue(series, "the weight did not reach the metrics file")
        self.assertEqual("kg", (data["metrics"]["weight"] or {}).get("unit"))
        # And it is the owner's own measurement, marked as such (task 107).
        self.assertTrue(all(pt.get("subject") == "owner" for pt in series))
        self.assertIn("body measurements", out)


class TestAUnitThatIsNotOursIsRefused(unittest.TestCase):

    def test_pounds_do_not_join_a_series_in_kilograms(self):
        bundle = {"resourceType": "Bundle", "entry": [{"resource": {
            "resourceType": "Observation", "status": "final",
            "effectiveDateTime": "2024-03-02T10:00:00Z",
            "code": {"coding": [{"system": "http://loinc.org", "code": "29463-7",
                                 "display": "Body Weight"}]},
            "valueQuantity": {"value": 180.0, "unit": "lb", "code": "[lb_av]"}}}]}
        d = pathlib.Path(tempfile.mkdtemp(prefix="fhir_lb_"))
        self.addCleanup(shutil.rmtree, d, True)
        f = d / "pounds.json"
        f.write_text(json.dumps(bundle), encoding="utf-8")
        plan = ingest_fhir.plan(f)
        self.assertEqual([], plan.get("metrics") or [],
                         "a weight in pounds was planned into a series in kilograms")
        reasons = {s["reason"] for s in plan["skipped"]}
        self.assertIn("metric_unit_not_ours", reasons)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
