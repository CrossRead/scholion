"""Task 143: the corridor rule left `labs.py` for `corridor.py`, and no answer moved.

The rule «may this number be compared with that corridor» was written inside
`analyze_labs` in three steps on one day (136, 138, 142) and raised that
module's budget three times. Moving it out is a refactor with one promise: the
structure `analyze_labs` returns is the same, key for key and value for value.
A promise like that is cheap to prove and expensive to take on trust, so the
proof is here — the function as it was, loaded from the commit before the
move, run beside the function as it is, on a profile built to walk every
branch of the rule.

The second claim is the facade's: a name that exists in a submodule and not
at `engine.<name>` is invisible to six consumers, so the new names must
reach it.
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, engine
from scholion.engine import corridor, labs

ROOT = Path(__file__).resolve().parents[1]
#: The last commit in which the rule still lived inside `analyze_labs`.
BEFORE = "b55f211b3e8dad1f61c793b85d528ab3221a996d"


def _labs_before():
    """`engine/labs.py` as it was before the move, loaded under the engine
    package so that its relative imports and its reads through `core` resolve
    exactly as the live module's do. None when the commit is not reachable —
    the public package carries no history, and the proof is for the tree."""
    try:
        src = subprocess.run(
            ["git", "--no-optional-locks", "show", f"{BEFORE}:src/scholion/engine/labs.py"],
            cwd=ROOT, capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if src.returncode != 0 or "def analyze_labs" not in src.stdout:
        return None
    d = Path(tempfile.mkdtemp())
    path = d / "labs_before_143.py"
    path.write_text(src.stdout, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("scholion.engine._labs_before_143", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


#: A catalogue that has one marker per branch of the rule, so the two functions
#: are compared on every path rather than on the one the fixture happens to take.
CATALOGUE = {"markers": {
    "hdl": {"ref_low": 1.0, "ref_high": None, "ref_by_sex": {"male": {"ref_low": 1.0},
                                                             "female": {"ref_low": 1.2}}},
    "ggt": {"ref_low": None, "ref_high": 55, "ref_sex": "male"},
    "psa": {"ref_low": None, "ref_high": 4.0, "applies_to_sex": "male", "ref_sex": "male"},
    "oh": {"ref_low": 1, "ref_high": 9, "ref_sex": "unreviewed"},
    "igf1": {"ref_low": 80, "ref_high": 220, "ref_sex": "any",
             "ref_age": {"min": 40, "max": 49}},
    "dheas": {"ref_low": 2, "ref_high": 12, "ref_sex": "any", "ref_age": "banded"},
    "alp": {"ref_low": 40, "ref_high": 130, "ref_sex": "any"},
    "ca_ion": {"ref_low": 1.12, "ref_high": 1.32, "ref_sex": "any"},
    "ldl": {"ref_high": 3.0, "ref_sex": "any", "status": "proposed"},
}}

PROFILE = {"markers": {
    # the catalogue default on file — the sex-adjusted branch
    "hdl": {"name": "HDL", "unit": "mmol/L", "ref_low": 1.0, "direction": "higher_better",
            "series": [{"date": "2026-01", "value": 1.1}, {"date": "2026-07", "value": 1.05}]},
    # no range on file — a corridor that belongs to one sex
    "ggt": {"name": "GGT", "unit": "U/L", "series": [{"date": "2026-07", "value": 60}]},
    # no range on file — a test that exists for one sex
    "psa": {"name": "PSA", "unit": "ng/mL", "series": [{"date": "2026-07", "value": 1.0}]},
    # no range on file — a corridor nobody reviewed
    "oh": {"name": "16a-OHE1", "unit": "x", "series": [{"date": "2026-07", "value": 5}]},
    # no range on file — an age band
    "igf1": {"name": "IGF-1", "unit": "ng/mL", "series": [{"date": "2026-07", "value": 150}]},
    # no range on file — banded, band unrecorded
    "dheas": {"name": "DHEA-S", "unit": "umol/L", "series": [{"date": "2026-07", "value": 7}]},
    # no range on file — borrowed from the base
    "alp": {"name": "ALP", "unit": "U/L", "series": [{"date": "2026-07", "value": 258}]},
    # the form printed its own corridor, and the corridors differ between draws
    "ca_ion": {"name": "Ca++", "unit": "mmol/L", "ref_low": 1.16, "ref_high": 1.32,
               "series": [{"date": "2026-01-10", "value": 1.20, "ref_low": 1.16, "ref_high": 1.32},
                          {"date": "2026-07-10", "value": 1.09, "ref_low": 1.10, "ref_high": 1.35}]},
    # a proposed rule, no verdict
    "ldl": {"name": "LDL", "unit": "mmol/L", "ref_high": 3.34, "direction": "higher_worse",
            "series": [{"date": "2026-01", "value": 4.2}, {"date": "2026-07", "value": 4.9}]},
}}

def _only_keys_of(reference, value):
    """`value` with every key the reference does not have removed, recursively.

    Keys present in the reference and missing from the value are left missing,
    so a lost field still shows up as a difference.
    """
    if isinstance(reference, dict) and isinstance(value, dict):
        return {k: _only_keys_of(reference[k], value[k])
                for k in value if k in reference}
    if isinstance(reference, list) and isinstance(value, list):
        return [_only_keys_of(r, v) for r, v in zip(reference, value)] \
            + value[len(reference):]
    return value


PERSONS = [("male", 45), ("female", 45), ("female", 60), ("male", None), (None, 45), (None, None)]


class TestTheAnswerIsTheSameBeforeAndAfterTheMove(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.before = _labs_before()

    def _both(self, sex, age, profile, catalogue):
        patches = [mock.patch.object(core, "labs", lambda: profile),
                   mock.patch.object(core, "profile_sex", lambda: sex),
                   mock.patch.object(core, "profile_age", lambda: age)]
        if catalogue is not None:
            patches.append(mock.patch.object(core, "lab_markers", lambda: catalogue))
        for p in patches:
            p.start()
        try:
            a, b = self.before.analyze_labs(), labs.analyze_labs()
            # Compared on the keys the older function had. This proof is about a
            # MOVE — that nothing the rule used to answer changed — and it would
            # otherwise also forbid the module ever gaining a field again, which
            # is a promise nobody made and one that costs a capability every
            # time it is kept. A key that DISAPPEARS still fails, because the
            # filter only ever removes keys that are new.
            b = _only_keys_of(a, b)
            was = json.dumps(a, sort_keys=True, ensure_ascii=False)
            now = json.dumps(b, sort_keys=True, ensure_ascii=False)
        finally:
            for p in patches:
                p.stop()
        return was, now

    def test_every_branch_of_the_rule_for_every_kind_of_person(self):
        if self.before is None:
            self.skipTest("the commit before the move is not in this tree's history")
        for sex, age in PERSONS:
            with self.subTest(sex=sex, age=age):
                was, now = self._both(sex, age, PROFILE, CATALOGUE)
                self.assertEqual(was, now)
                # and the comparison compared something: every flag name is there
                for name in ("ref_sex_other", "ref_sex_unreviewed", "sex_not_applicable",
                             "ref_sex_unknown", "ref_age_other", "ref_age_unknown",
                             "ref_age_unbanded", "ref_reference_base", "ref_origin",
                             "flags_comparable", "corridor_note"):
                    self.assertIn(f'"{name}"', now)

    def test_the_fixture_profile_against_the_real_catalogue(self):
        if self.before is None:
            self.skipTest("the commit before the move is not in this tree's history")
        profile = core.labs()
        for sex, age in PERSONS:
            with self.subTest(sex=sex, age=age):
                was, now = self._both(sex, age, profile, None)
                self.assertEqual(was, now)

    def test_the_refusals_fire_where_the_synthetic_profile_says_they_should(self):
        """Not equivalence — a check that the synthetic profile walks the
        branches it was built to walk, so the proof above is not vacuous."""
        with mock.patch.object(core, "labs", lambda: PROFILE), \
             mock.patch.object(core, "profile_sex", lambda: "female"), \
             mock.patch.object(core, "profile_age", lambda: 60), \
             mock.patch.object(core, "lab_markers", lambda: CATALOGUE):
            by_key = {m["key"]: m for m in labs.analyze_labs()["markers"]}
        self.assertEqual(by_key["hdl"]["ref_low"], 1.2)
        self.assertEqual(by_key["hdl"]["ref_sex"], "female")
        self.assertTrue(by_key["ggt"]["ref_sex_other"])
        self.assertTrue(by_key["psa"]["sex_not_applicable"])
        self.assertFalse(by_key["psa"]["ref_sex_other"])
        self.assertTrue(by_key["oh"]["ref_sex_unreviewed"])
        self.assertTrue(by_key["igf1"]["ref_age_other"])
        self.assertTrue(by_key["dheas"]["ref_age_unbanded"])
        self.assertTrue(by_key["alp"]["ref_reference_base"])
        self.assertEqual(by_key["alp"]["ref_origin"], "reference_base")
        self.assertEqual(by_key["ca_ion"]["ref_origin"], "form")
        self.assertEqual(by_key["ca_ion"]["ref_low"], 1.10)
        self.assertFalse(by_key["ca_ion"]["flags_comparable"])
        self.assertTrue(by_key["ca_ion"]["corridor_note"])
        self.assertEqual(by_key["ldl"]["ref_origin"], "profile")


class TestTheFacadeCarriesTheNewNames(unittest.TestCase):

    def test_the_two_answers_and_the_sex_helper_reach_engine(self):
        for name in ("point_corridor", "flags_comparable", "_sex_adjusted_bounds"):
            with self.subTest(name=name):
                self.assertIs(getattr(engine, name), getattr(corridor, name),
                              f"engine.{name} is not corridor.{name} — the facade "
                              "re-exports every name, and a consumer that imports "
                              "through it must get the same function")

    def test_analyze_labs_computes_no_corridor_of_its_own(self):
        """The rule moved, not copied: `analyze_labs` no longer reads the
        profile's sex or age or the catalogue's corridor fields, and reaches
        the corridor only through the new module. (`_threshold_value` still
        reads the sex — a decision limit stated as «3× the upper limit» is a
        sex pair, and that is a decision-limit question, not a corridor one.)"""
        body = inspect.getsource(labs.analyze_labs)
        for token in ("core.profile_sex", "core.profile_age", "ref_by_sex", "applies_to_sex",
                      "kb.get(", "_sex_adjusted_bounds", "corridors_differ"):
            self.assertNotIn(token, body, f"analyze_labs still reads «{token}» itself")
        for call in ("point_corridor(", "flags_comparable("):
            self.assertIn(call, body)
        self.assertIn("from .corridor import point_corridor, flags_comparable",
                      Path(labs.__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
