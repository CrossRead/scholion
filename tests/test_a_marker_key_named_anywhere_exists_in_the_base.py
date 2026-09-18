"""A marker key named anywhere in the product exists in the marker base.

Two names pointed at nothing, and neither failed a thing. The A/G ratio was
declared recomputable from `albumin` and `protein_total`; the base calls total
protein `total_protein`, so the index was never recomputed and a printed ratio
was never checked against its own components. The vitamin D warning about
hypercalcaemia compared the person's `calcium`; the base has `calcium_total`,
so a measured calcium read as never taken, on the one line where it mattered.

A key that names nothing is not an error anywhere in the code — a lookup simply
misses. So every place that names a marker is read here and compared with
`lab_markers.json`. The two names below are declared ahead of the base, each
with its reason; any other miss fails.
"""
from __future__ import annotations

import json
import unittest

import support  # noqa: F401  — puts src/ on the import path
from scholion import core, provenance

#: Named on purpose before the base has them. Each entry says why, and what
#: removes it.
AHEAD_OF_THE_BASE = {
    # The recomputation of a printed non-HDL cholesterol. No lab key stores the
    # printed value yet, so the entry waits for it rather than being dropped.
    "non_hdl": "a printed non-HDL value has no key in the base yet",
    # The components of the omega-6/omega-3 ratio. Laboratories print the ratio
    # and the omega-3 index; the two sums are not stored, so this index is shown
    # as printed and cannot be recomputed. Task 200, stage C, decides them.
    "omega6": "the omega-6 sum is not stored by any form reader",
    "omega3": "the omega-3 sum is not stored by any form reader",
}

#: Where the knowledge base names markers, by file and field.
KNOWLEDGE_FIELDS = {
    "dose_evidence": ("compare_marker",),
    "drug_lab_monitoring": ("labs",),
    "lab_test_meta": ("requires",),
    "radar_domains": ("markers",),
    "system_gene_panels": ("marker",),
    "test_rules": ("marker", "covers"),
}


def _knowledge(name):
    return json.loads(core.knowledge_path(name + ".json").read_text(encoding="utf-8"))


def _values(obj, fields):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in fields:
                for x in (v if isinstance(v, list) else [v]):
                    if isinstance(x, str):
                        yield x
            yield from _values(v, fields)
    elif isinstance(obj, list):
        for x in obj:
            yield from _values(x, fields)


class TestEveryNamedMarkerExists(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = set(core.lab_markers()["markers"])
        cls.metrics = set((core.wearable_metrics().get("metrics") or {}))

    def missing(self, names):
        return sorted({n for n in names if n not in self.base and n not in AHEAD_OF_THE_BASE})

    def test_the_derived_indices_name_real_markers(self):
        names = set(provenance.DERIVED)
        for d in provenance.DERIVED.values():
            names |= set(d["needs"])
        self.assertEqual([], self.missing(names))

    def test_the_knowledge_base_names_real_markers(self):
        for name, fields in KNOWLEDGE_FIELDS.items():
            data = _knowledge(name)
            names = set(_values(data, set(fields)))
            if name == "dose_evidence":
                # This field compares a wearable metric as readily as a lab test.
                names -= self.metrics
            with self.subTest(file=name):
                self.assertTrue(names, "the field names nothing — the scan is reading the wrong place")
                self.assertEqual([], self.missing(names))

    def test_every_lab_test_property_belongs_to_a_marker(self):
        tests = _knowledge("lab_test_meta")["tests"]
        self.assertEqual([], self.missing(tests))

    def test_every_declared_exception_is_still_absent(self):
        """An exception that the base has caught up with is removed, not kept."""
        self.assertEqual([], sorted(k for k in AHEAD_OF_THE_BASE if k in self.base))


if __name__ == "__main__":
    unittest.main()
