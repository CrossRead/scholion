"""One LOINC code, one marker — and a second code for a marker says why.

Task 98, after the analysis that rewrote it. The dictionary held one code per
marker, and LOINC does not work that way: the same analyte has a different code
by material and by method. Measured on a real Synthea bundle, four of the
twenty-three observations it could not place were analytes this dictionary
knows, under codes it does not — glucose in whole blood beside glucose in
plasma, LDL measured directly beside LDL calculated, creatinine in blood beside
creatinine in serum.

So a marker may now carry `loinc_also`. What the mechanism deliberately does NOT
do is make the pairing cheap: every additional code has to state, in prose, why
the two are the same measurement. Whole blood and plasma differ by about a tenth
— pairing them «because the names match» would put a systematic error into a
person's series, and that is exactly what `core.loinc_index` was written to
refuse («a code arrives per marker with medical verification … never from a
guess»).

The table ships with no additional codes at all. That is not an oversight: none
of the four candidates found on the bundle can be justified without a clinical
source, and inventing the justification is the failure this guards against. The
mechanism is proved by construction below rather than by its contents.
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from scholion import core  # noqa: E402

META = ROOT / "src" / "scholion" / "knowledge" / "lab_test_meta.json"


def _tests() -> dict:
    return json.loads(META.read_text(encoding="utf-8")).get("tests") or {}


class TestNoCodeIsClaimedTwice(unittest.TestCase):

    def test_the_dictionary_does_not_bind_one_code_to_two_markers(self):
        seen, clash = {}, []
        for key, meta in _tests().items():
            codes = [str((meta or {}).get("loinc"))] if (meta or {}).get("loinc") else []
            codes += [str(e["code"]) for e in ((meta or {}).get("loinc_also") or [])
                      if isinstance(e, dict) and e.get("code")]
            for code in codes:
                if code in seen and seen[code] != key:
                    clash.append(f"{code}: {seen[code]} and {key}")
                seen[code] = key
        self.assertEqual([], clash,
                         "one code cannot mean two analytes — an incoming value would land "
                         "in whichever marker the walk happened to reach first")

    def test_the_index_is_not_empty(self):
        # A walk over an empty dictionary agrees with everything.
        self.assertGreater(len(core.loinc_index()), 20, "the index did not build")


class TestASecondCodeMustSayWhy(unittest.TestCase):

    def test_every_additional_code_states_its_reason(self):
        for key, meta in _tests().items():
            for extra in ((meta or {}).get("loinc_also") or []):
                with self.subTest(marker=key, code=extra.get("code")):
                    self.assertIsInstance(extra, dict)
                    self.assertTrue(extra.get("code"), "no code")
                    self.assertTrue(extra.get("name"), "no name — the code alone cannot be checked")
                    why = extra.get("why") or ""
                    self.assertGreater(len(why.split()), 5,
                                       "«why» must say why these are the same measurement, "
                                       "in a sentence somebody can disagree with")

    def test_the_reader_reads_the_field_and_refuses_a_reasonless_entry(self):
        """The mechanism, proved by construction — the table ships empty."""
        made = {"tests": {
            "glucose": {"loinc": "2345-7",
                        "loinc_also": [{"code": "TEST-1", "name": "n",
                                        "why": "same analyte, same material, different method name"}]},
            "hdl": {"loinc": "2085-9",
                    "loinc_also": [{"code": "TEST-2", "name": "n"}]},   # no why
        }}
        original = core.lab_test_meta
        core.lab_test_meta = lambda: made                    # type: ignore[assignment]
        core.loinc_index.cache_clear() if hasattr(core.loinc_index, "cache_clear") else None
        try:
            idx = core.loinc_index()
            self.assertEqual("glucose", idx.get("TEST-1"), "the extra code was not read")
            self.assertIsNone(idx.get("TEST-2"),
                              "an entry with no reason was accepted — the reason is the whole gate")
        finally:
            core.lab_test_meta = original                    # type: ignore[assignment]
            core.loinc_index.cache_clear() if hasattr(core.loinc_index, "cache_clear") else None


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main()
