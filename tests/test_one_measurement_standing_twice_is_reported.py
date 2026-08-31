"""A month point and a dated point of that month, in one series.

`add_lab_point` now notices when the same period is already present at another
resolution — «2026-07» and «2026-07-14» are one measurement standing twice, and
a series holding both will chart it twice and trend on it twice. The store says
so, and the tested part stopped there: the importer's own report, which is where
a person would actually read it, carried the flag through six lines that ran in
no test.

The importer is fed CSV rather than PDF for the same reason the table test is:
the delimiter path needs no reader and no mock, so the test is about the
reporting and nothing else.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import support

if str(support.SRC) not in sys.path:
    sys.path.insert(0, str(support.SRC))

BY_DAY = """Date,Test,Result,Units,Reference Range
2018-05-22,Ferritin,31,ng/mL,13-150
"""


class ResolutionCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.forms = self.root / "forms"
        self.forms.mkdir()
        self.profile = self.root / "profile"
        self.profile.mkdir()
        self._old = os.environ.get("SCHOLION_PROFILE_DIR")
        os.environ["SCHOLION_PROFILE_DIR"] = str(self.profile)
        from scholion import core
        core.reset_cache()

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SCHOLION_PROFILE_DIR", None)
        else:
            os.environ["SCHOLION_PROFILE_DIR"] = self._old
        from scholion import core
        core.reset_cache()
        self.tmp.cleanup()

    def ingest(self):
        from scholion import ingest_labs
        return ingest_labs.ingest(str(self.forms), force=True)


class TestTheDoublingIsNamedInTheReport(ResolutionCase):

    def test_a_month_and_a_day_of_it_are_reported_as_one_measurement_twice(self):
        # The month point is seeded through the store rather than through a
        # delimited file: a table dates every row and the importer requires a
        # full date there, so a month-resolution point reaches a series by the
        # other routes — a form that printed only the month, or a hand entry.
        from scholion import store
        self.assertTrue(store.add_lab_point("ferritin", "2018-05", 12, unit="ng/mL")["ok"])
        (self.forms / "a_day.csv").write_text(BY_DAY, encoding="utf-8")

        r = self.ingest()

        mixed = r.get("resolution_mixed") or []
        self.assertTrue(mixed, "the doubling was noticed by the store and lost by the report")
        entry = next(m for m in mixed if m["marker"] == "ferritin")
        self.assertIn("2018-05", entry["others"],
                      "the report does not say which other point it stands beside")
        self.assertTrue(str(entry["date"]).startswith("2018-05-22"),
                        "the report does not say which point raised it")

    def test_a_series_at_one_resolution_raises_nothing(self):
        """Both points dated to the day: two measurements, not one twice."""
        (self.forms / "a_day.csv").write_text(BY_DAY, encoding="utf-8")
        (self.forms / "another_day.csv").write_text(
            BY_DAY.replace("2018-05-22", "2018-06-19"), encoding="utf-8")

        r = self.ingest()

        self.assertEqual([], r.get("resolution_mixed") or [],
                         "an ordinary second measurement was called a doubling")


if __name__ == "__main__":
    unittest.main()
