"""The hybrid engine: a model proposes a RULE, never a value (task 80).

An unrecognised row on a lab form has three possible fates and only one is
acceptable. Dropping it silently is what the tool used to do, for nineteen files
out of forty-seven. Asking a model to read the number breaks the property the
product rests on — that every number in the profile came from deterministic code
and can be reproduced. Asking a model to propose a DICTIONARY ENTRY keeps that
property: the next parse reads the row with ordinary code which now knows one
rule more, and the rule is a line of JSON a person can check by eye.

While an entry is `proposed` the value is read, stored and shown, and no
statement about the norm is made on it — the same shape as an unknown sex. These
tests hold that division, in both directions.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
import unittest

import support  # noqa: F401
from scholion import core, format as fmt, markers_local as ml
from scholion.engine import labs


class _Local(unittest.TestCase):
    #: Variables that would point the engine at a profile OTHER than the temp one
    #: built below. `SCHOLION_PROFILE_DIR` is set by `run_tests.sh` and takes
    #: precedence over `SCHOLION_REPO_DIR`, so these tests read the shared fixture
    #: instead of the marker they just proposed — and they passed anyway, because
    #: some earlier test in a full run happened to leave the variable unset. Run
    #: alone, or in a different order, they failed. A test whose result depends on
    #: which tests ran before it is measuring the run, not the code.
    _OVERRIDES = ("SCHOLION_PROFILE_DIR", "SCHOLION_GENOME_DIR", "SCHOLION_CACHE_DIR")

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._saved = {k: os.environ.pop(k, None) for k in self._OVERRIDES}
        os.environ["SCHOLION_REPO_DIR"] = self.d
        (pathlib.Path(self.d) / "profile").mkdir(parents=True, exist_ok=True)
        core.reset_cache()

    def tearDown(self):
        os.environ.pop("SCHOLION_REPO_DIR", None)
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v
        core.reset_cache()

    def _value(self, key, value, lo=0, hi=20):
        (pathlib.Path(self.d) / "profile" / "labs.json").write_text(json.dumps(
            {"markers": {key: {"name": key, "unit": "u", "ref_low": lo, "ref_high": hi,
                               "series": [{"date": "2026-07-01", "value": value}]}}}))
        core.reset_cache()


class TestAProposalIsARuleAndNotAValue(_Local):
    def test_a_proposal_reaches_the_dictionary(self):
        r = ml.propose("ebv_vca_igg", unit="U/mL", names_ru=["антитела к vca ebv, igg"])
        self.assertTrue(r["ok"], r)
        self.assertIn("ebv_vca_igg", core.lab_markers()["markers"])
        self.assertEqual(core.lab_markers()["markers"]["ebv_vca_igg"]["status"], "proposed")

    def test_a_proposal_cannot_carry_a_reference_range(self):
        """A corridor is a clinical claim; the project's own rules say a model is
        not a source for one. The function has nowhere to put it."""
        r = ml.propose("x_marker", names_en=["x marker"])
        self.assertTrue(r["ok"])
        spec = core.lab_markers()["markers"]["x_marker"]
        self.assertIsNone(spec.get("ref_low"))
        self.assertIsNone(spec.get("ref_high"))

    def test_a_local_entry_never_shadows_a_shipped_one(self):
        r = ml.propose("glucose", names_ru=["глюкоза"])
        self.assertFalse(r["ok"])
        self.assertIn("glucose", r["error"])

    def test_a_proposal_needs_a_name_to_recognise_the_row_by(self):
        self.assertFalse(ml.propose("only_a_key")["ok"])


class TestProposedKeepsTheValueAndWithholdsTheVerdict(_Local):
    def test_the_value_is_kept_and_shown(self):
        ml.propose("ebv_vca_igg", unit="U/mL", names_en=["ebv vca igg"])
        self._value("ebv_vca_igg", 142.0)
        r = labs.analyze_labs()
        self.assertEqual(r["markers"][0]["value"], 142.0,
                         "the row was lost — which is the defect this mechanism repairs")

    def test_no_claim_about_the_norm_is_made(self):
        ml.propose("ebv_vca_igg", unit="U/mL", names_en=["ebv vca igg"])
        self._value("ebv_vca_igg", 142.0)          # far above the stored corridor
        m = labs.analyze_labs()["markers"][0]
        self.assertFalse(m["abnormal"])
        self.assertTrue(m["proposed_rule"])

    def test_the_reason_and_the_remedy_are_printed(self):
        ml.propose("ebv_vca_igg", unit="U/mL", names_en=["ebv vca igg"])
        self._value("ebv_vca_igg", 142.0)
        out = fmt.labs_report(labs.analyze_labs())
        self.assertRegex(out, r"(?i)(not yet confirmed|не подтверждено)")
        self.assertIn("ebv_vca_igg", out)

    def test_confirming_turns_the_verdict_back_on(self):
        ml.propose("ebv_vca_igg", unit="U/mL", names_en=["ebv vca igg"])
        self._value("ebv_vca_igg", 142.0)
        ml.confirm("ebv_vca_igg")
        core.reset_cache()
        m = labs.analyze_labs()["markers"][0]
        self.assertTrue(m["abnormal"])
        self.assertFalse(m["proposed_rule"])


class TestTheOverlayIsAdditive(_Local):
    def test_the_shipped_dictionary_is_not_reduced(self):
        before = len(core.lab_markers()["markers"])
        ml.propose("x_marker", names_en=["x marker"])
        after = len(core.lab_markers()["markers"])
        self.assertEqual(after, before + 1,
                         "the overlay replaced the shipped dictionary instead of extending it")

    def test_the_overlay_lives_beside_the_profile_not_in_the_package(self):
        ml.propose("x_marker", names_en=["x marker"])
        self.assertTrue((pathlib.Path(self.d) / "knowledge" / "lab_markers.local.json").is_file())
        pkg = pathlib.Path(core.__file__).resolve().parent / "knowledge" / "lab_markers.json"
        self.assertNotIn("x_marker", pkg.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()


class TestTheSameMechanismCoversThreeKinds(_Local):
    """Task 80 asks for ONE mechanism over three kinds of entry — markers, units
    and their conversions, and the row-selection rules of a multi-line reference
    block. One rule governs all three, and its CONSEQUENCE differs because what
    each entry controls differs:

      · a marker entry decides what a row is called — an unconfirmed one does not
        change the number, so the value is read and shown without a verdict;
      · a unit entry decides what the number IS — an unconfirmed factor would
        rewrite the value, so it is not applied at all;
      · a row rule decides which corridor is taken — an unconfirmed one would
        pick one, so it does not run.

    One sentence underneath: a proposal never changes a number and never makes a
    claim.
    """

    def test_a_unit_proposal_needs_a_factor_or_a_reason(self):
        self.assertFalse(ml.propose_unit("lpa", "mg/dL")["ok"])

    def test_a_proposed_unit_is_not_applied(self):
        """The half that matters: an unconfirmed multiplier must not touch a value."""
        ml.propose_unit("glucose", "mg%", factor=0.0555)
        self.assertEqual(ml.confirmed_units("glucose"), {})
        self.assertTrue(ml.proposed_units("glucose"))

    def test_confirming_a_unit_puts_it_in_the_gate(self):
        ml.propose_unit("glucose", "mg%", factor=0.0555)
        ml.confirm("glucose|mg%")
        self.assertEqual(ml.confirmed_units("glucose"), {"mg%": 0.0555})

    def test_a_row_rule_needs_the_line_that_produced_it(self):
        """A pattern with no example cannot be reviewed and cannot become a
        regression fixture."""
        self.assertFalse(ml.propose_row_rule(r"стадия", kind="alien")["ok"])

    def test_a_row_rule_must_be_a_valid_expression(self):
        r = ml.propose_row_rule(r"[unclosed", kind="alien", example="x")
        self.assertFalse(r["ok"])

    def test_a_proposed_row_rule_does_not_run(self):
        ml.propose_row_rule(r"стадия\s+пубертата", kind="alien", example="Стадия пубертата II: 1 - 2")
        self.assertEqual(ml.confirmed_row_rules("alien"), [])

    def test_confirming_a_row_rule_makes_it_run(self):
        ml.propose_row_rule(r"стадия\s+пубертата", kind="alien", example="Стадия пубертата II: 1 - 2")
        ml.confirm(r"стадия\s+пубертата")
        self.assertIn(r"стадия\s+пубертата", ml.confirmed_row_rules("alien"))

    def test_all_three_kinds_appear_in_one_listing(self):
        ml.propose("x_marker", names_en=["x marker"])
        ml.propose_unit("glucose", "mg%", factor=0.0555)
        ml.propose_row_rule(r"тест\s+правило", kind="label", example="Тест правило: 1 - 2")
        kinds = {e["kind"] for e in ml.listing()["entries"]}
        self.assertEqual(kinds, {"marker", "unit", "row/label"})

    def test_confirm_reaches_any_kind(self):
        ml.propose_unit("glucose", "mg%", factor=0.0555)
        self.assertEqual(ml.confirm("glucose|mg%")["kind"], "units")
