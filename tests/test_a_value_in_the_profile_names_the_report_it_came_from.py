"""Every stored number is asked where it came from, and each answer is pinned.

`provenance.audit()` is the reverse of `reconcile`. Reconcile asks «this is in a
PDF — did it reach the profile», and so it can only find LOSSES. This asks the
question that catches the opposite and worse class: «this number is in the
profile — which report holds it?» The case it was written for was a HOMA-IR index
stored for a month whose profile has insulin and no glucose at all: no report
contains that number, and recomputing it gives a value several times larger.

It stood at 32% reach. `_close` had a test, and `audit()` had one that ran it on
an EMPTY profile and asserted the result was a dict — which exercises the two
lines that refuse and none of the machine. Seven verdicts decide whether a number
is a fact from a report, a hand entry, a second method of the same draw, or a
defect, and not one of them was distinguished from another by any test. A verdict
machine nothing distinguishes can collapse to a single answer and stay green.

So each verdict is driven here on a profile built for it, and each is checked
against the OTHERS: it is not enough that a conflict is called a conflict if a
legitimate second method is called one too.

The profiles are written into a temporary directory and `SCHOLION_PROFILE_DIR` is
pointed at it. Nothing reads a real profile, and the coverage file is written by
hand rather than by running `reconcile` over invented PDFs — the shape is the one
`reconcile` writes, and it is stated here once so that a change to it fails these
tests instead of quietly making them describe a file nobody produces any more.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, provenance

#: A marker whose dictionary entry names a preferred method, and one that does
#: not. Which is which decides between `alt_form` and `conflict`, so both are
#: taken from the real dictionary rather than invented.
WITH_PREFERRED_FORM = "testosterone"
WITHOUT_PREFERRED_FORM = "glucose"


def series(*points):
    return [{"date": ym, "value": v} for ym, v in points]


def source(value, file="lab-2026-01.pdf", form="CLIA"):
    """One entry of `sources`, in the shape `reconcile` writes."""
    return {"file": file, "draw_date": f"{file[4:11]}-15", "value": value, "form": form}


@contextmanager
def profile(markers, coverage):
    """A temporary profile holding exactly these labs and this coverage."""
    tmp = Path(tempfile.mkdtemp(prefix="provenance-"))
    (tmp / "labs.json").write_text(json.dumps({
        "_meta": {"synthetic": True},
        "markers": {k: {"unit": "u", "series": s} for k, s in markers.items()},
    }), encoding="utf-8")
    (tmp / "labs_coverage.json").write_text(json.dumps({
        "_meta": {"generated_by": "test"}, "coverage": coverage,
    }), encoding="utf-8")
    old = os.environ.get("SCHOLION_PROFILE_DIR")
    os.environ["SCHOLION_PROFILE_DIR"] = str(tmp)
    core.reset_cache()
    try:
        yield tmp
    finally:
        if old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = old
        core.reset_cache()
        shutil.rmtree(tmp, ignore_errors=True)


#: Coverage naming a marker none of these profiles hold. `audit()` refuses
#: outright on an EMPTY coverage map, and rightly: an empty map means reconcile
#: has not been run, which is a different statement from «no report holds this
#: number». A test about the derived indices therefore has to hand it a map that
#: is non-empty and beside the point.
UNRELATED_COVERAGE = {"ferritin_not_in_these_profiles":
                      {"2020-01": {"sources": [source(30.0)]}}}


def verdicts(res):
    return {(p["marker"], p["date"]): p["verdict"] for p in res["points"]}


class TestTheSevenVerdictsAreToldApart(unittest.TestCase):

    def test_a_value_a_report_holds_is_a_fact_from_that_report(self):
        with profile({WITHOUT_PREFERRED_FORM: series(("2026-01", 5.0))},
                     {WITHOUT_PREFERRED_FORM: {"2026-01": {"sources": [source(5.0)]}}}):
            res = provenance.audit()
        self.assertTrue(res["ok"])
        point = res["points"][0]
        self.assertEqual("form", point["verdict"])
        self.assertEqual("lab-2026-01.pdf", point["detail"],
                         "the verdict does not name the report it rests on, which is the "
                         "entire content of the answer")

    def test_a_small_difference_is_still_the_same_measurement(self):
        """Reports round. The tolerance is what stops rounding being called a
        conflict, and it is the reason `_close` exists at all."""
        with profile({WITHOUT_PREFERRED_FORM: series(("2026-01", 5.0))},
                     {WITHOUT_PREFERRED_FORM: {"2026-01": {"sources": [source(5.01)]}}}):
            res = provenance.audit()
        self.assertEqual("form", res["points"][0]["verdict"])

    def test_a_value_no_report_holds_at_all_is_a_hand_entry(self):
        """Not an error — a paper conclusion and an outside laboratory are both
        legitimate. But it is NOT a fact from a report, and the distinction is
        the product's whole claim."""
        with profile({WITHOUT_PREFERRED_FORM: series(("2026-01", 5.0))},
                     {"ferritin": {"2026-01": {"sources": [source(30.0)]}}}):
            res = provenance.audit()
        self.assertEqual("manual", res["points"][0]["verdict"])
        self.assertEqual(1, len(res["unverified"]))

    def test_a_report_that_says_something_else_is_a_conflict(self):
        with profile({WITHOUT_PREFERRED_FORM: series(("2026-01", 5.0))},
                     {WITHOUT_PREFERRED_FORM: {"2026-01": {"sources": [source(9.9)]}}}):
            res = provenance.audit()
        point = res["points"][0]
        self.assertEqual("conflict", point["verdict"])
        self.assertIn("9.9", point["detail"], "the conflict does not say what the report said")
        self.assertEqual(1, len(res["defects"]))

    def test_the_same_disagreement_is_not_a_conflict_where_two_methods_are_expected(self):
        """The pair that has to be told apart. Identical numbers, identical
        coverage, and the only difference is that this marker's dictionary entry
        names a preferred method — mass spectrometry against immunoassay of the
        same draw. Calling that a defect would flag a correct profile forever."""
        with profile({WITH_PREFERRED_FORM: series(("2026-01", 20.0))},
                     {WITH_PREFERRED_FORM: {"2026-01": {"sources": [source(14.0)]}}}):
            res = provenance.audit()
        self.assertEqual("alt_form", res["points"][0]["verdict"])
        self.assertEqual([], res["defects"], "a legitimate second method was called a defect")

    def test_a_derived_index_that_agrees_with_its_components_is_marked_as_derived(self):
        with profile({"insulin": series(("2026-01", 9.0)),
                      "glucose": series(("2026-01", 5.0)),
                      "homa_ir": series(("2026-01", 2.0))}, UNRELATED_COVERAGE):
            res = provenance.audit()
        v = verdicts(res)
        self.assertEqual("derived_ok", v[("homa_ir", "2026-01")],
                         "9.0 * 5.0 / 22.5 = 2.0 — the index follows from the profile")

    def test_a_derived_index_that_contradicts_its_components_is_a_defect(self):
        with profile({"insulin": series(("2026-01", 9.0)),
                      "glucose": series(("2026-01", 5.0)),
                      "homa_ir": series(("2026-01", 8.4))}, UNRELATED_COVERAGE):
            res = provenance.audit()
        point = next(p for p in res["points"] if p["marker"] == "homa_ir")
        self.assertEqual("derived_bad", point["verdict"])
        self.assertIn("2.00", point["detail"], "the defect does not say what the value should be")

    def test_a_derived_index_with_no_components_and_no_report_hangs_in_the_air(self):
        """The live case the module exists for: an index stored for a month whose
        profile holds one component and not the other. It is not a hand entry —
        it is a number with no grounds of any kind, and it gets its own class."""
        with profile({"insulin": series(("2026-01", 9.0)),
                      "homa_ir": series(("2026-01", 2.0))}, UNRELATED_COVERAGE):
            res = provenance.audit()
        point = next(p for p in res["points"] if p["marker"] == "homa_ir")
        self.assertEqual("derived_orphan", point["verdict"])
        self.assertIn("glucose", point["detail"], "the orphan does not name what is missing")
        self.assertIn("insulin", point["detail"], "nor what is present")

    def test_an_index_printed_in_a_report_is_still_checked_against_the_components(self):
        """A printed index is not an independent measurement — the laboratory
        computed it from the same two numbers. So a report holding it does not
        excuse it from agreeing with them."""
        with profile({"insulin": series(("2026-01", 9.0)),
                      "glucose": series(("2026-01", 5.0)),
                      "homa_ir": series(("2026-01", 8.4))},
                     {"homa_ir": {"2026-01": {"sources": [source(8.4)]}}}):
            res = provenance.audit()
        point = next(p for p in res["points"] if p["marker"] == "homa_ir")
        self.assertEqual("derived_bad", point["verdict"],
                         "a report was allowed to vouch for an index its own numbers refute")

    def test_a_formula_that_does_not_apply_is_skipped_rather_than_failed(self):
        """Friedewald's LDL is invalid above 4.5 mmol/L of triglycerides. The
        index is then measured directly, and comparing it against a formula that
        does not hold would manufacture a defect."""
        with profile({"cholesterol_total": series(("2026-01", 6.0)),
                      "hdl": series(("2026-01", 1.2)),
                      "triglycerides": series(("2026-01", 5.0)),
                      "ldl": series(("2026-01", 3.5))}, UNRELATED_COVERAGE):
            res = provenance.audit()
        point = next(p for p in res["points"] if p["marker"] == "ldl")
        self.assertNotEqual("derived_bad", point["verdict"])
        self.assertIn("derived", point, "nothing recorded that the formula was skipped")


class TestTheAuditAsAWhole(unittest.TestCase):

    LABS = {WITHOUT_PREFERRED_FORM: series(("2026-01", 5.0), ("2026-02", 5.2)),
            "ferritin": series(("2026-01", 30.0))}
    COVER = {WITHOUT_PREFERRED_FORM: {"2026-01": {"sources": [source(5.0)]}}}

    def test_the_counts_add_up_to_the_points(self):
        with profile(self.LABS, self.COVER):
            res = provenance.audit()
        self.assertEqual(res["total"], len(res["points"]))
        self.assertEqual(res["total"], sum(res["counts"].values()),
                         "a point landed in a verdict the counts do not name")

    def test_one_marker_can_be_asked_about_alone(self):
        with profile(self.LABS, self.COVER):
            res = provenance.audit(marker="ferritin")
        self.assertEqual({"ferritin"}, {p["marker"] for p in res["points"]})

    def test_a_profile_with_no_labs_refuses_and_says_why(self):
        with profile({}, UNRELATED_COVERAGE):
            res = provenance.audit()
        self.assertFalse(res["ok"])
        self.assertTrue(res.get("error"))

    def test_a_profile_with_no_coverage_refuses_rather_than_reporting_everything_unverified(self):
        """The dangerous shape: with no coverage file every number is «in no
        report», which reads as a profile full of defects rather than as a check
        that has not been run."""
        with profile(self.LABS, {}) as tmp:
            (tmp / "labs_coverage.json").unlink()
            res = provenance.audit(refresh=False, lab_dir=str(tmp))
        self.assertFalse(res["ok"])

    def test_refresh_rebuilds_the_coverage_from_the_folder_of_reports(self):
        """`--refresh` is the difference between auditing against yesterday's
        reading of the folder and against today's. Pointed at a folder with no
        reports in it, it must produce an empty coverage and then refuse — which
        is the honest answer, and not the same as «every number is unverified».

        Nothing here reads a real folder: `lab_dir` is an empty temporary one and
        the coverage file is written next to the temporary profile.
        """
        with profile(self.LABS, self.COVER) as tmp:
            empty = tmp / "no-reports"
            empty.mkdir()
            res = provenance.audit(refresh=True, lab_dir=str(empty))
            self.assertFalse(res["ok"], "an empty folder of reports vouched for something")
            self.assertTrue((tmp / "labs_coverage.json").exists(),
                            "the refresh did not write the coverage it had just rebuilt")

    def test_a_point_with_no_number_is_not_audited(self):
        with profile({WITHOUT_PREFERRED_FORM: [{"date": "2026-01", "value": None},
                                               {"value": 5.0}]}, self.COVER):
            res = provenance.audit()
        self.assertEqual([], res["points"], "a point with no value or no date was given a verdict")


class TestTheReport(unittest.TestCase):

    def test_a_refusal_is_rendered_rather_than_crashing(self):
        out = provenance.format_report({"ok": False, "error": "nothing to audit"})
        self.assertIn("nothing to audit", out)

    def test_the_defects_are_named_with_their_marker_date_and_value(self):
        with profile({"insulin": series(("2026-01", 9.0)),
                      "glucose": series(("2026-01", 5.0)),
                      "homa_ir": series(("2026-01", 8.4))}, UNRELATED_COVERAGE):
            out = provenance.format_report(provenance.audit())
        self.assertIn("homa_ir", out)
        self.assertIn("2026-01", out)
        self.assertIn("8.4", out)

    def test_the_hand_entries_are_listed_by_marker(self):
        with profile({"ferritin": series(("2026-01", 30.0), ("2026-02", 32.0)),
                      "glucose": series(("2026-01", 5.0))},
                     {"glucose": {"2026-01": {"sources": [source(5.0)]}}}):
            out = provenance.format_report(provenance.audit())
        self.assertIn("ferritin: 2026-01, 2026-02", out,
                      "the unverified list does not gather a marker's months together")


class TestCloseness(unittest.TestCase):
    """The tolerance is `max(0.05, |b| * tol)`, and the floor matters: without it
    every small number in the profile would conflict with itself."""

    def test_a_small_number_gets_an_absolute_floor(self):
        self.assertTrue(provenance._close(0.01, 0.05),
                        "near zero a relative tolerance is nothing at all")

    def test_a_large_number_gets_a_relative_tolerance(self):
        self.assertTrue(provenance._close(100.0, 101.0, 0.02))
        self.assertFalse(provenance._close(100.0, 110.0, 0.02))


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
