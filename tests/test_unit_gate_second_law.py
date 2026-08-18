"""Not every unit converts by a multiplier.

The unit gateway was built after a defect with one shape: a value arriving in
mg/dL, stored as written, and compared against thresholds that belong to mmol/L.
Nothing errored; the person was told the wrong thing in a document that goes to
their doctor. The fix was a conversion table — one factor per spelling.

HbA1c does not fit that table. The IFCC scale (mmol/mol) and the NGSP scale (%)
are related by the NGSP master equation

    NGSP % = 0.09148 × IFCC mmol/mol + 2.152

which is affine: the line does not pass through the origin, and no single
multiplier reproduces it. 48 mmol/mol is 6.5 %; multiplying 48 by anything at all
gives something else. Until v0.3.1 the file said so and refused the unit — honest,
and a refusal of the commonest unit on a European report.

What makes the second law dangerous is not the arithmetic, it is the interface. A
caller reading only `factor` from the gateway would apply 1.0 and store 48 as
48 % — not an error, a catastrophic diabetic reading, silently. So the arithmetic
lives in exactly one function and both entry points go through it, and the tests
below check the value, the corridor, and the fact that nothing else does the
multiplication for itself.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import support

KN = support.ROOT / "src" / "scholion" / "knowledge" / "lab_markers.json"

# Values from the NGSP conversion table, rounded as a laboratory prints them.
KNOWN = [(31, 5.0), (42, 6.0), (48, 6.5), (53, 7.0), (64, 8.0)]


class TestTheMasterEquationIsAppliedAndNotApproximated(unittest.TestCase):

    def setUp(self):
        from scholion import core
        self.core = core
        self.spec = core.lab_markers()["markers"]["hba1c"]

    def test_the_published_conversion_table_comes_out(self):
        for ifcc, ngsp in KNOWN:
            with self.subTest(mmol_per_mol=ifcc):
                got = self.core.convert_to_canonical(self.spec, "mmol/mol", ifcc)
                self.assertTrue(got["ok"], got.get("reason"))
                self.assertAlmostEqual(got["value"], ngsp, places=1,
                                       msg=f"{ifcc} mmol/mol should print as {ngsp} %")

    def test_no_multiplier_could_have_produced_these(self):
        """The point of the second law, stated as an assertion.

        If a single factor existed, every pair would share one ratio. They do not,
        and that is precisely why a `convert` entry for this unit would be wrong
        rather than imprecise.
        """
        ratios = {round(ngsp / ifcc, 4) for ifcc, ngsp in KNOWN}
        self.assertGreater(len(ratios), 1,
                           "the pairs share a ratio, so this marker does not need "
                           "the affine law after all and the extra machinery should go")

    def test_the_rule_carries_its_source(self):
        rule = self.spec["convert_affine"]["mmol/mol"]
        self.assertAlmostEqual(rule["k"], 0.09148)
        self.assertAlmostEqual(rule["b"], 2.152)
        self.assertIn("NGSP", rule.get("source", ""),
                      "a conversion constant with no citation is a number somebody "
                      "remembered")

    def test_a_unit_that_genuinely_has_no_conversion_is_still_refused(self):
        """The second law must not become a licence to convert anything.

        Lp(a) in mg/dL depends on the size of the person's apo(a) isoform, so no
        constant — affine or otherwise — relates it to nmol/L. It stays refused,
        with the reason.
        """
        lpa = self.core.lab_markers()["markers"]["lpa"]
        res = self.core.resolve_unit(lpa, "mg/dL")
        self.assertFalse(res["ok"])
        self.assertIn("isoform", res["reason"])


class TestTheCorridorTravelsWithTheValue(unittest.TestCase):
    """A reference range printed in mmol/mol and a value converted to % is the
    original defect one level down: every point reads as wildly abnormal."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="affine_"))
        (self.dir / "labs.json").write_text(json.dumps(
            {"_meta": {"purpose": "SYNTHETIC — a test fixture", "synthetic": True},
             "markers": {}}, ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _stored(self):
        return json.loads((self.dir / "labs.json").read_text(encoding="utf-8"))["markers"]["hba1c"]

    def test_both_ends_of_the_range_are_transformed_by_the_same_law(self):
        code, out, err = support.run(
            ["add-lab", "hba1c", "2026-08", "48", "--unit", "mmol/mol",
             "--ref-low", "20", "--ref-high", "42"], profile_dir=self.dir)
        self.assertEqual(code, 0, err or out)
        m = self._stored()
        self.assertEqual(m["unit"], "%")
        self.assertAlmostEqual(m["series"][0]["value"], 6.5, places=1)
        self.assertAlmostEqual(m["ref_high"], 6.0, places=1,
                               msg="the upper bound was multiplied instead of transformed")
        self.assertLess(m["ref_low"], m["ref_high"])

    def test_a_value_inside_its_corridor_stays_inside_it(self):
        """The end-to-end statement, and the one a reader would notice.

        42 mmol/mol against a corridor whose top is 42 mmol/mol must not come out
        as abnormal after conversion. If the two are transformed by different
        laws — or one of them not at all — this is where it shows.
        """
        support.run(["add-lab", "hba1c", "2026-08", "40", "--unit", "mmol/mol",
                     "--ref-low", "20", "--ref-high", "42"], profile_dir=self.dir)
        r = support.run_json(["labs"], profile_dir=self.dir)
        row = next(x for x in r["markers"] if x["key"] == "hba1c")
        self.assertEqual(row["flag"], "ok",
                         "a value inside its own corridor was flagged after conversion")


class TestNothingConvertsOnItsOwn(unittest.TestCase):
    """One law, one place. A second caller doing its own arithmetic is how the
    offset gets dropped, and dropping it is silent."""

    def test_no_module_multiplies_by_the_gateways_factor(self):
        import re
        offenders = []
        for f in sorted((support.ROOT / "src" / "scholion").glob("*.py")):
            if f.name == "core.py":
                continue
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip().startswith("#"):
                    continue
                if re.search(r'\bfactor\b', line) and "resolve_unit" not in line \
                        and re.search(r'\*\s*factor|factor\s*\*', line):
                    offenders.append(f"{f.name}:{i}: {line.strip()}")
        self.assertEqual(offenders, [],
                         "a caller applies the gateway's factor itself, which drops the "
                         "offset for any unit that converts by a formula:\n  "
                         + "\n  ".join(offenders))


if __name__ == "__main__":
    unittest.main()
