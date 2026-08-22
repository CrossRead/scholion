"""ClinVar, the ACMG list and polygenic scores close on the MEASURED input.

Task 99, and a regression this suite did not have a shape for. The gate keyed on
the carrier — `input_class == "array"` — so a chip stopped being a chip the
moment it arrived as a VCF. Measured on the reference corpus: a genotyping panel
distributed as a VCF holds 553 197 variants, a genotype table 48 838 chosen
positions, and both answered «your VCF has not been annotated yet — run the
preparation». That is not a refusal, it is an INVITATION to do the exact thing
the gate exists to prevent, and it appeared only after task 89 made those two
inputs readable at all.

Task 87 had already measured the breadth of every input. Nothing read the
measurement. This test is the reader of last resort: it walks the classes that
module declares narrow and requires each one to close all three paths.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholion.engine import genomics  # noqa: E402


def _available(profile, ready=True, **extra):
    st = {"ready": ready, "input_profile": profile,
          "input_class": ("array" if profile == "array" else "sequenced"),
          "array": {"vendor": "23andMe", "markers": 601885},
          "callset": {"observed_per_mb": 179, "imputed_share": 0.0},
          "tabular": {"rows": 48838, "kind": "genotype_table"}}
    st.update(extra)
    return st


class TestNarrowInputsCloseEveryFindingsPath(unittest.TestCase):

    def test_every_declared_narrow_class_closes_all_three_paths(self):
        for profile in sorted(genomics.NARROW_INPUTS):
            with mock.patch("scholion.genome.available", return_value=_available(profile)):
                # Named outright, not fetched with a default: a getattr that
                # silently skips a missing name is a test that goes green having
                # checked nothing, which is the failure mode this whole file is
                # about.
                for name in ("clinvar_findings", "acmg_findings", "prs_findings"):
                    fn = getattr(genomics, name)
                    out = fn()
                    self.assertFalse(out.get("available"), f"{name} stayed open on {profile}")
                    self.assertIn(out.get("status"),
                                  ("input_is_an_array", "input_too_narrow"),
                                  f"{name} stayed open on {profile}")
                    self.assertNotIn("⟦", str(out.get("message")),
                                     f"no message line for {profile}")
                    self.assertTrue(str(out.get("message", "")).strip(),
                                    f"empty message for {profile}")

    def test_a_measured_whole_genome_is_not_closed(self):
        with mock.patch("scholion.genome.available",
                        return_value=_available("whole_genome",
                                                callset={"observed_per_mb": 1609})):
            self.assertIsNone(genomics._array_only_input())

    def test_no_input_at_all_is_not_called_too_narrow(self):
        # A person with no genome must get «this has not been annotated yet»,
        # not «your genome is too narrow». Closing here would answer a question
        # nobody asked with a fact that is not true.
        with mock.patch("scholion.genome.available",
                        return_value=_available(None, ready=False)):
            self.assertIsNone(genomics._array_only_input())

    def test_the_narrow_set_covers_every_class_the_measurement_can_produce(self):
        # The two are written in different files and drift apart silently: a new
        # class added to the measurement would default to OPEN, which is the
        # dangerous side. Anything not named narrow has to be named here.
        from scholion import callset
        produced = {"whole_genome", "panel", "sparse", "imputed_panel",
                    "partial_callset_indels", "partial_callset_snvs", "unmeasured"}
        for value in produced:
            self.assertTrue(
                value in genomics.NARROW_INPUTS or value == "whole_genome",
                f"class {value} is called neither narrow nor a whole genome")
        # And the measurement must not have grown a class this test does not know.
        src = (Path(callset.__file__)).read_text(encoding="utf-8")
        for value in produced:
            self.assertIn(f'"{value}"', src, f"{value} disappeared from callset.py")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
