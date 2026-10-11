"""A prescription date defaults a missing start without rewriting history."""
import unittest
from unittest.mock import patch
from scholion import core, store


class PrescriptionStartDefault(unittest.TestCase):
    def resolve(self, **fields):
        original = {"name": "Synthetic treatment", **fields}
        with patch.object(core, "medications_json", return_value={"medications": [original]}):
            result = store.list_medications()[0]
        self.assertEqual(original, {"name": "Synthetic treatment", **fields})
        return result

    def test_structured_date_defaults_missing_start(self):
        for key in ("prescription_date", "scheme_date"):
            row = self.resolve(**{key: "2026-01-12"})
            self.assertEqual(row["start_date"], "2026-01-12")
            self.assertEqual(row["start_date_provenance"]["source"], key)

    def test_actual_start_wins(self):
        row = self.resolve(start_date="2025-12-01", scheme_date="2026-01-12")
        self.assertEqual(row["start_date"], "2025-12-01")
        self.assertNotIn("start_date_provenance", row)

    def test_legacy_scheme_has_one_unambiguous_date(self):
        row = self.resolve(scheme="Recorded prescription 12.01.2026 (90 days)")
        self.assertEqual(row["start_date"], "2026-01-12")

    def test_invalid_or_ambiguous_date_does_not_default(self):
        for fields in ({"scheme_date": "2026-02-30"}, {"scheme": "12.01.2026 / 15.01.2026"}, {}):
            self.assertNotIn("start_date", self.resolve(**fields))

    def test_invalid_explicit_start_is_not_silently_replaced(self):
        row = self.resolve(start_date="unknown", scheme_date="2026-01-12")
        self.assertEqual(row["start_date"], "unknown")
