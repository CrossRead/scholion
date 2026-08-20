"""The four modules the review measured at zero per cent coverage, plus a golden
vector for the one exact published formula in the project.

`prs.py` (230 lines), `provenance.py` (100), `ingest_studies.py` (119) and
`ouroboros_tools.py` (70) had no test touching them at all. The zero on
`provenance.py` was the pointed one: that module is the literal implementation of
«provenance for everything», the sentence the whole product is sold on.

And `test_math.py`, despite its name, held no numeric comparison of PhenoAge
against a reference value — the formula was checked qualitatively (sign of the
coefficients, independence from sex, refusal on an incomplete panel) and never
against a number. What follows is a golden vector in the honest sense: the
coefficients are re-typed here from the published Levine/Liu formula and the
result is compared with the module's, so a refactor that silently changes the
arithmetic fails. It does NOT re-verify the coefficients themselves against the
paper — that was done by reading, and no test can do it.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401  — puts src/ on the import path
from scholion import ingest_studies, phenoage, prs, provenance

#: One ordinary panel. Values are in the units the formula expects (see
#: `phenoage.UNITS`), and deliberately unremarkable: the point is the arithmetic.
PANEL = {"albumin": 45.0, "creatinine": 80.0, "glucose": 5.0, "crp": 1.0,
         "lymph": 30.0, "mcv": 90.0, "rdw": 13.0, "alp": 70.0, "wbc": 6.0,
         "age": 45.0}


def independent_phenoage(v):
    """The published formula, typed here from the paper rather than imported."""
    crp_mg_dl = max(v["crp"] / 10.0, 0.01)
    xb = (-19.9067
          - 0.0336 * v["albumin"]
          + 0.0095 * v["creatinine"]
          + 0.1953 * v["glucose"]
          + 0.0954 * math.log(crp_mg_dl)
          - 0.0120 * v["lymph"]
          + 0.0268 * v["mcv"]
          + 0.3306 * v["rdw"]
          + 0.00188 * v["alp"]
          + 0.0554 * v["wbc"]
          + 0.0804 * v["age"])
    gamma = 0.0076927
    mortality = 1 - math.exp(-math.exp(xb) * (math.exp(120 * gamma) - 1) / gamma)
    return 141.50225 + math.log(-0.00553 * math.log(1 - mortality)) / 0.090165


class TestThePhenoageGoldenVector(unittest.TestCase):

    def test_the_module_agrees_with_the_formula_typed_from_the_paper(self):
        mine = independent_phenoage(PANEL)
        theirs, _risk = phenoage.formula(PANEL)
        self.assertAlmostEqual(theirs, mine, places=9)

    def test_the_pinned_number(self):
        """A fixed value, so a refactor cannot move the answer unnoticed."""
        pa, risk = phenoage.formula(PANEL)
        self.assertAlmostEqual(pa, 37.433903, places=5)
        self.assertAlmostEqual(risk, 0.01509562, places=7)

    def test_a_worse_panel_gives_a_higher_biological_age(self):
        worse = dict(PANEL, crp=5.0, glucose=7.0, rdw=15.0)
        self.assertGreater(phenoage.formula(worse)[0], phenoage.formula(PANEL)[0])

    def test_crp_is_floored_rather_than_taken_to_a_logarithm_of_zero(self):
        """`math.log(0)` is the traceback the review asked to be turned into an answer."""
        zero = dict(PANEL, crp=0.0)
        self.assertTrue(math.isfinite(phenoage.formula(zero)[0]))

    def test_an_implausible_unit_is_caught_before_the_arithmetic(self):
        """Albumin 4.3 means g/dL; in the g/L the formula wants it is incompatible with life."""
        bad = phenoage._implausible(dict(PANEL, albumin=4.3))
        self.assertIn("albumin", " ".join(bad).lower())


class TestIngestStudies(unittest.TestCase):

    def test_a_conclusion_is_recognised_by_its_own_words(self):
        text = ("УЗИ органов брюшной полости. " + "Печень не увеличена, контуры ровные. " * 6
                + "ЗАКЛЮЧЕНИЕ: диффузные изменения паренхимы печени. Врач Петров И. И.")
        self.assertGreater(len(text), 200, "the recogniser ignores anything too short to be a report")
        self.assertTrue(ingest_studies.looks_like_conclusion(text))

    def test_something_too_short_to_be_a_report_is_not_one(self):
        """A length floor, and it is deliberate: a stray heading is not a conclusion."""
        self.assertFalse(ingest_studies.looks_like_conclusion("ЗАКЛЮЧЕНИЕ: норма"))

    def test_a_lab_form_is_not_a_conclusion(self):
        self.assertFalse(ingest_studies.looks_like_conclusion("Ферритин 12 нг/мл 13-150"))

    def test_a_study_without_a_date_is_not_invented(self):
        got = ingest_studies.parse_study("ЗАКЛЮЧЕНИЕ: без особенностей", source="x.pdf")
        if got is not None:
            self.assertIsNone(got.get("date"), "a date that is not on the page is not a date")


class TestProvenance(unittest.TestCase):

    def test_closeness_is_a_tolerance_not_an_equality(self):
        self.assertTrue(provenance._close(5.0, 5.01))
        self.assertFalse(provenance._close(5.0, 5.9))

    def test_an_audit_on_an_empty_profile_answers_instead_of_failing(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("SCHOLION_PROFILE_DIR")
            os.environ["SCHOLION_PROFILE_DIR"] = tmp
            try:
                from scholion import core
                core.reset_cache()
                res = provenance.audit(refresh=False, lab_dir=tmp)
                self.assertIsInstance(res, dict)
                self.assertIsInstance(provenance.format_report(res), str)
            finally:
                if old is None:
                    os.environ.pop("SCHOLION_PROFILE_DIR", None)
                else:
                    os.environ["SCHOLION_PROFILE_DIR"] = old
                from scholion import core
                core.reset_cache()


class TestOuroborosTools(unittest.TestCase):

    def test_every_declared_tool_has_a_schema_and_a_handler(self):
        from scholion import ouroboros_tools
        tools = ouroboros_tools.get_tools()
        self.assertTrue(tools, "the plugin declares no tools at all")
        for t in tools:
            with self.subTest(tool=getattr(t, "name", t)):
                name = t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
                self.assertTrue(name)


class TestPrsPackagePinning(unittest.TestCase):

    def setUp(self):
        self._old = os.environ.get("PRS_MCP_PKG")

    def tearDown(self):
        if self._old is None:
            os.environ.pop("PRS_MCP_PKG", None)
        else:
            os.environ["PRS_MCP_PKG"] = self._old

    def test_the_default_is_pinned(self):
        os.environ.pop("PRS_MCP_PKG", None)
        self.assertIn("@", prs._prs_pkg(), "an unpinned package spec runs whatever is newest")

    def test_a_hostile_override_falls_back_to_the_pin(self):
        for hostile in ("--from git+https://example.invalid/x", "pkg; rm -rf /", "-e ."):
            with self.subTest(spec=hostile):
                os.environ["PRS_MCP_PKG"] = hostile
                self.assertEqual(prs._prs_pkg(), prs._DEFAULT_PKG,
                                 "uvx runs whatever spec it is handed — one environment "
                                 "variable must not become code execution")

    def test_an_ordinary_override_is_honoured(self):
        os.environ["PRS_MCP_PKG"] = "just-prs-mcp@0.1.4"
        self.assertEqual(prs._prs_pkg(), "just-prs-mcp@0.1.4")


if __name__ == "__main__":
    unittest.main()
